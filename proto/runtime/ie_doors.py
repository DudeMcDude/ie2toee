# Temple+ runtime for doors of maps converted by ie2toee (Python 2.7, runs inside the game).
#
# Baked maps (proto/ie_bake.py) carry the portals in their .sec files; start(area) attaches to them (and creates
# only missing ones, so runtime mode does not duplicate doors on reload either). setup(area) is the old always-create
# path, kept for the door probes.
#
# MVP: each IE door's default state is baked into the ground art and the .sec files by the converter. At map load
# setup(area) places one ToEE portal object per door (minimal: a scaled-down stock door model) and polls it; when the
# portal opens or closes, the door's impeded tiles are switched between the IE open/closed impeded cells and the
# matching WED tile variant is drawn over the ground ("faithful" mode).
#
# Needs two small Temple+ engine hooks (see ENGINE_HOOKS.md):
#   game.tile_flags_get(loc) / game.tile_flags_set(loc, flags)                  - sector tile flags
#   game.ground_overlay_set(id, tex, x, y, w, h) / game.ground_overlay_remove(id) - ground patches (tile swap)
# The per-area data module ie_doors_<area>.py is generated from the player's own install (never distributed).
from toee import *
from utilities import location_from_axis

PORTAL_PROTO = 39        # a stock unlocked portal; only used for interaction + ToEE door semantics
MODEL_SCALE = 30         # percent; the IE art shows the real door
POLL_MS = 250
OVERLAY_BASE = 7000

_doors = []              # [(door dict, portal handle, last_open)]
_area = None
_door_users = {}
_scripts = {}
_gen = 0             # bumped per start(): polls of an earlier load stop

def _is_open(p):
    try:
        flag = OPF_OPEN
    except NameError:
        flag = 1
    return (p.portal_flags_get() & flag) != 0

def use_key(portal, user):
    """Let the normal door action proceed when the party possesses the matching IE key."""
    if user in game.party and portal.type == obj_t_portal and portal.id in _scripts:
        spec, script = _scripts[portal.id]
        if getattr(script, 'HANDLES_CLICK', False):
            _run(spec, portal, script, user, {'Clicked': user})
    if user in game.party and portal.type == obj_t_portal and portal.portal_flags_get() & OPF_LOCKED:
        import ie_itemrt
        for spec, obj, last in _doors:
            if obj != portal or not spec.get('key'):
                continue
            key = spec['key'].lower()
            entry = ie_itemrt.ITEMS.get(key)
            if entry and entry.get('n') and any(ie_itemrt.find(pc, key) for pc in game.party):
                portal.portal_flag_unset(OPF_LOCKED)
                print("ie_doors: %s unlocked with %s" % (spec['name'], key))
            break
    if user in game.party and portal.type == obj_t_portal and not _is_open(portal) and not portal.portal_flags_get() & OPF_LOCKED:
        for spec, obj, last in _doors:
            if obj == portal and spec.get('script'):
                _door_users[portal.id] = user
                break
    return RUN_DEFAULT


def _run(spec, portal, script, user, events):
    import ie_runtime as rt
    area = _area[2:] if _area.startswith('I2AR') else _area
    rt.run_script(rt.Ctx(portal, user, spec['name'], area, events), script.BLOCKS)


def _attach_key(area, spec, portal):
    if spec.get('script'):
        try:
            module = __import__('ie_bcs_' + spec['script'].lower() + '_door')
        except ImportError:
            pass
        else:
            _scripts[portal.id] = spec, module
    if spec.get('key') or spec.get('script'):
        try:
            script = getattr(__import__('ie_bake_' + area.lower()), 'DOOR_SCRIPT', 0)
        except ImportError:
            return
        if script:
            for event in (1, 42):  # san_use, san_unlock_attempt
                if not portal.scripts[event]:
                    portal.scripts[event] = script


def _apply(idx, d, is_open):
    for u, v, base, m_open, m_closed in d['tiles']:
        mask = m_open | m_closed
        loc = location_from_axis(u, v)
        cur = game.tile_flags_get(loc)
        # keep non-door bits as they are now, replace the door bits with the new state's impeded cells
        state = m_closed
        if is_open:
            state = m_open   # (not 'is_open and m_open or m_closed': m_open is often 0)
        new = (cur & ~mask) | (base & mask) | state
        game.tile_flags_set(loc, new)
    patch = d['patches'].get(is_open and 'open' or 'closed')   # strings are truthy, safe
    if patch:
        game.ground_overlay_set(OVERLAY_BASE + idx, patch['texture'], patch['x'], patch['y'], patch['w'], patch['h'])

def setup(area, model_scale=MODEL_SCALE, proto=PORTAL_PROTO):
    global _doors, _area
    _scripts.clear()
    _door_users.clear()
    mod = __import__('ie_doors_' + area.lower())
    game.ground_overlay_remove(-1)
    _doors = []
    _area = area
    for idx in range(len(mod.DOORS)):
        d = mod.DOORS[idx]
        x, y, ox, oy = d['loc']
        p = game.obj_create(proto, location_from_axis(x, y))
        p.move(location_from_axis(x, y), ox, oy)
        p.obj_set_int(8, model_scale)   # obj_f_model_scale (percent)
        if d['locked']:
            p.portal_flag_set(OPF_LOCKED)
        else:
            p.portal_flag_unset(OPF_LOCKED)
        if _is_open(p) != bool(d['open']):
            p.portal_toggle_open()
        _apply(idx, d, bool(d['open']))
        _attach_key(area, d, p)
        _doors.append([d, p, bool(d['open'])])
    game.timeevent_add(poll, (area,), POLL_MS, 1)
    return len(_doors)

def _find_portal(x, y, ox, oy):
    """The portal standing at a door's spot (baked into the .sec, or created earlier and kept in the save)."""
    loc = location_from_axis(x, y)
    best = None
    for p in game.obj_list_vicinity(loc, OLC_PORTAL):
        if p.location == loc:
            best = p
    return best

def start(area, model_scale=MODEL_SCALE, proto=PORTAL_PROTO):
    """Map-load entry point for both modes: reuse the portals already on the map (baked prefab doors, or runtime
    doors restored from a save) and create only the missing ones, so a reload never duplicates a door. The tile
    flags and ground patches follow each portal's current (saved) state."""
    global _doors, _area, _gen
    _door_users.clear()
    _scripts.clear()
    mod = __import__('ie_doors_' + area.lower())
    game.ground_overlay_remove(-1)
    _doors = []
    _area = area
    _gen = _gen + 1
    made = 0
    for idx in range(len(mod.DOORS)):
        d = mod.DOORS[idx]
        x, y, ox, oy = d['loc']
        p = _find_portal(x, y, ox, oy)
        if p is None and d.get('previous_loc'):
            p = _find_portal(*d['previous_loc'])
            if p is not None:
                p.move(location_from_axis(x, y), ox, oy)
        if p is None:
            made = made + 1
            p = game.obj_create(proto, location_from_axis(x, y))
            p.move(location_from_axis(x, y), ox, oy)
            p.obj_set_int(8, model_scale)
            if d['locked']:
                p.portal_flag_set(OPF_LOCKED)
            if _is_open(p) != bool(d['open']):
                p.portal_toggle_open()
        now = _is_open(p)
        _apply(idx, d, now)
        _attach_key(area, d, p)
        _doors.append([d, p, now])
    game.timeevent_add(poll, (area, _gen), POLL_MS, 1)
    print("ie_doors: %s attached %d doors (%d created)" % (area, len(_doors), made))
    return len(_doors)

def poll(area, gen=None):
    if area != _area or (gen is not None and gen != _gen):
        return 0
    for idx in range(len(_doors)):
        d, p, last = _doors[idx]
        try:
            now = _is_open(p)
        except Exception:
            continue
        script = _scripts.get(p.id)
        if script and ((getattr(script[1], 'CHECKS_DOOR_FLAGS', False) and p.portal_flags_get() & OPF_LOCKED)
                       or (getattr(script[1], 'SYNC_CLOSED_DOOR', False) and not now)):
            _run(d, p, script[1], None, {})
            now = _is_open(p)
        if now != last:
            _apply(idx, d, now)
            _doors[idx][2] = now
            print("ie_doors: %s %s" % (d['name'], now and 'opened' or 'closed'))
            user = _door_users.pop(p.id, None) if d.get('script') else None
            if now and user and script:
                _run(d, p, script[1], user, {'Opened': user})
    game.timeevent_add(poll, (area, gen), POLL_MS, 1)
    return 0

def toggle(name):
    for d, p, last in _doors:
        if d['name'] == name or d['wed_id'] == name:
            p.portal_toggle_open()
            return 1
    return 0

def blocked_count(name):
    """number of Block subtile bits currently set on the door's tiles (for tests)"""
    for d, p, last in _doors:
        if d['name'] == name or d['wed_id'] == name:
            n = 0
            for u, v, base, mo, mc in d['tiles']:
                f = game.tile_flags_get(location_from_axis(u, v)) & (mo | mc)
                while f:
                    n += f & 1
                    f >>= 1
            return n
    return -1

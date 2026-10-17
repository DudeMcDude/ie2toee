# Temple+ runtime for doors of maps converted by ie2toee (Python 2.7, runs inside the game).
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

def _is_open(p):
    try:
        flag = OPF_OPEN
    except NameError:
        flag = 1
    return (p.portal_flags_get() & flag) != 0

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
        _doors.append([d, p, bool(d['open'])])
    game.timeevent_add(poll, (area,), POLL_MS, 1)
    return len(_doors)

def poll(area):
    if area != _area:
        return 0
    for idx in range(len(_doors)):
        d, p, last = _doors[idx]
        try:
            now = _is_open(p)
        except Exception:
            continue
        if now != last:
            _apply(idx, d, now)
            _doors[idx][2] = now
            print "ie_doors: %s %s" % (d['name'], now and 'opened' or 'closed')
    game.timeevent_add(poll, (area,), POLL_MS, 1)
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

# Temple+ runtime for the travel regions of maps converted by ie2toee (Python 2.7 inside the game; the syntax is also
# valid Python 3 so proto/test_travel.py can run it against a mock game). docs/travel.md has the design.
#
# Travel between converted areas uses ToEE's own clickable exit icons (map-change scenery + rules/jumppoint.tab,
# written by proto/ie_exiticons.py). Regional icons open the campaign atlas and its destination callback calls
# travel(). Walking near a travel icon never activates it. This module polls the
# party every POLL_MS for:
#   * info points (IE Trigger Points): their text floats over the leader when a party member steps in;
#   * on arrival in a converted area that has no baked data (interiors), its doors are attached (ie_doors.start).
# start() is idempotent: iwd.go() and the first heartbeat of every baked creature call it. The poll is a game time
# event, so it is saved with the game; after a load the restored event "adopts" this fresh module (a poll whose
# generation differs from the live one stops, unless nothing has polled for a while: then it takes over).
from toee import *
import time

try:
    from utilities import location_from_axis, location_to_axis
except ImportError:                      # (the test mock provides them in toee)
    pass

POLL_MS = 250
NEAR = 0.8              # tiles: "inside" also counts this close to a region's outline
ANCHOR_NEAR = 1.4       # tiles: every travel region has an anchor tile (ie2toee region_anchors); party members this close fire it
INCH_PER_TILE = 28.284271247461900976
BUSY_S = 4.0            # wall seconds after a teleport during which no new travel is started (fade + map load)
ALIVE_S = 2.0           # a poll that ran this recently means a poll is alive: start() does nothing
LOG = [None]

_gen = 0
_last_poll = 0.0        # wall clock of the last poll tick
_armed = False
_map = None             # map the party was on at the last tick
_busy_until = 0.0
_noted = {}             # exits already announced as "not in the preview"
_polls = [0]            # number of ticks (tests)
_travels = [0]


def _log(s):
    try:
        if LOG[0]:
            f = open(LOG[0], 'a'); f.write('IE_TRAVEL ' + s + '\n'); f.close()
        else:
            print('IE_TRAVEL ' + s)
    except Exception:
        pass


def _data():
    import ie_travel_data
    return ie_travel_data


def _pos(o):
    """continuous tile coordinates of an object (tile centre + sub-tile offset)"""
    x, y = location_to_axis(o.location)
    try:
        ox, oy = o.off_x, o.off_y
    except Exception:
        ox = oy = 0.0
    return x + 0.5 + ox / INCH_PER_TILE, y + 0.5 + oy / INCH_PER_TILE


def _seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0.0
    if L > 0:
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L))
    cx, cy = ax + t * dx, ay + t * dy
    return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5


def near_region(px, py, poly, near=NEAR):
    """True if (px, py) is inside the polygon or within `near` of its outline (2-point regions are segments)"""
    n = len(poly)
    if n == 0:
        return False
    if n >= 3:
        inside = False
        j = n - 1
        for i in range(n):
            xi, yi = poly[i]; xj, yj = poly[j]
            if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / (yj - yi) + xi:
                inside = not inside
            j = i
        if inside:
            return True
    if n == 1:
        return ((px - poly[0][0]) ** 2 + (py - poly[0][1]) ** 2) ** 0.5 <= near
    for i in range(n):
        a = poly[i]; b = poly[(i + 1) % n]
        if _seg_dist(px, py, a[0], a[1], b[0], b[1]) <= near:
            return True
    return False


def _party():
    try:
        return [p for p in game.party]
    except Exception:
        return []


def hit_region(area_data, pts):
    """the first region any of the points is in/near, else None"""
    for r in area_data['regions']:
        for (px, py) in pts:
            if near_region(px, py, r['poly']):
                return r
            a = r.get('anchor')
            if a and ((px - a[0] - 0.5) ** 2 + (py - a[1] - 0.5) ** 2) ** 0.5 <= ANCHOR_NEAR:
                return r
    return None


def _attach_doors(area):
    """Restore each portal's saved state and collision on arrival, including empty baked rooms."""
    try:
        import ie_doors
        __import__('ie_doors_' + area.lower())
        n = ie_doors.start(area)
        _log('%s: attached %d doors' % (area, n))
        return n
    except ImportError:
        return 0
    except Exception as e:
        _log('%s: attaching doors failed: %s' % (area, e))
        return 0


def _note_unconverted(r):
    key = (r['name'], r['dest_area'])
    if key in _noted:
        return
    _noted[key] = 1
    msg = 'This exit (%s) is not in the preview' % r['dest_area']
    _log(msg)
    try:
        game.leader.float_text_line(msg, 1)
    except Exception:
        pass


def travel(r, hours=None):
    """move the whole party to the destination entrance of region r (a data dict)"""
    global _armed, _busy_until
    d = _data()
    area = d.BY_MAP.get(game.leader.map)
    if area and _disabled(area, r['name']):
        return
    if r.get('requires_global'):
        import ie_runtime
        if not ie_runtime.get_var(None, r['requires_global'], 'GLOBAL'):
            return
    dst = d.AREAS[r['dest_area']]
    u, v, orient = dst['entrances'][r['dest_entrance']]
    _armed = False
    _busy_until = time.time() + BUSY_S
    _travels[0] += 1
    _log('%s -> %s %s (map %d tile %d,%d)' % (r['name'], r['dest_area'], r['dest_entrance'], dst['map'], u, v))
    game.fade_and_teleport(3600 * (r.get('travel_hours', 0) if hours is None else hours), 0, 0, dst['map'], u, v)


def _disabled(area, name):
    import ie_vars
    return ie_vars.get(area.upper() + ':ie_region_disabled_' + name.lower())

def set_region_active(area, name, active):
    import ie_vars
    data = _data().AREAS.get(area, {})
    regions = [r for r in data.get('regions', []) + data.get('triggers', []) if r['name'].lower() == name.lower()]
    if not regions:
        return
    ie_vars.put(area.upper() + ':ie_region_disabled_' + name.lower(), int(not active))
    for r in regions:
        tile = r.get('anchor') or r.get('icon_tile')
        if not r.get('jump_id') or not tile:
            continue
        loc = location_from_axis(*tile)
        for icon in game.obj_list_range(loc, 12, OLC_SCENERY):
            if icon.obj_get_int(obj_f_scenery_teleport_to) == r['jump_id']:
                flags = OF_CLICK_THROUGH | OF_DONTDRAW
                (icon.object_flag_unset if active else icon.object_flag_set)(flags)
                _log('%s: exit %s %s' % (area, name, 'enabled' if active else 'disabled'))

def use_world_exit(icon, user):
    data = _data()
    source = data.BY_MAP.get(icon.map)
    jump = icon.obj_get_int(obj_f_scenery_teleport_to)
    if not source or not any(r.get('world_jump') == jump for r in data.AREAS[source]['regions']):
        return RUN_DEFAULT
    if user in game.party and user.map == game.leader.map == icon.map and not game.combat_is_active():
        import ie_atlas
        ie_atlas.show(source)
    return SKIP_DEFAULT


def _revealed_exits(area, now):
    """Supply world exits missing from a previously saved sector, once unlocked."""
    global _next_exit_check
    if now < _next_exit_check:
        return
    _next_exit_check = now + 2.0
    import ie_runtime
    for route in area['regions']:
        if not route.get('world_jump'):
            continue
        jump = route.get('world_icon', route['world_jump'])
        gate = route.get('requires_global')
        unlocked = not gate or ie_runtime.get_var(None, gate, 'GLOBAL')
        if not unlocked and jump == route['world_jump']:
            continue
        loc = location_from_axis(*route['anchor'])
        nearby = game.obj_list_range(loc, 36, OLC_SCENERY)
        if jump != route['world_jump']:
            # Older saves have separate scenery icons for routes that share the same IE exit.
            for old in nearby:
                if old.obj_get_int(obj_f_scenery_teleport_to) == route['world_jump']:
                    old.object_flag_set(OF_OFF)
        if not unlocked:
            continue
        icon = next((o for o in nearby if o.obj_get_int(obj_f_scenery_teleport_to) == jump), None)
        if not icon:
            icon = game.obj_create(2011, loc)
            if icon:
                icon.obj_set_int(obj_f_scenery_teleport_to, jump)
        if icon and icon.scripts[1] != 1099:
            icon.scripts[1] = 1099  # upgrade the existing regional exit in saved sectors


_next_exit_check = 0


def tick(gen):
    """one poll of the party. Returns 1 if the poll must go on, 0 if it must stop."""
    global _gen, _last_poll, _armed, _map
    now = time.time()
    if gen != _gen:
        if now - _last_poll < ALIVE_S:
            return 0                  # another poll is alive: this one is stale (e.g. restored next to a fresh start)
        _gen = gen                    # nothing polled for a while: a restored poll after a load adopts this module
        _armed = False
        _map = None
        _log('adopted restored poll (gen %d)' % gen)
    _last_poll = now
    _polls[0] += 1
    party = _party()
    if not party:
        return 1
    try:
        cur = game.leader.map
    except Exception:
        return 1
    d = _data()
    import sys
    atlas = sys.modules.get('ie_atlas')
    if atlas and atlas.active() and (cur != _map or game.combat_is_active()):
        atlas.close()
    if cur != _map:
        _inside.clear()
        _map = cur
        _armed = False                # (re)arm only after leaving every region on this map
        area = d.BY_MAP.get(cur)
        if area:
            _attach_doors(area)
    if now < _busy_until:
        return 1                      # (fade + map load after a travel: no new travel yet)
    area = d.BY_MAP.get(cur)
    if not area:
        return 1
    _revealed_exits(d.AREAS[area], now)
    pts = [_pos(p) for p in party]
    _triggers(area, d.AREAS[area].get('triggers') or (), party, pts)
    # (travel itself is no longer polled: the converter places clickable ToEE exit icons, ie_exiticons.py)
    return 1


_inside = {}   # (area, region name) -> party member inside last poll


def _triggers(area, trigs, party, pts):
    """ARE trigger regions: when a party member steps in, run the region's script once with Entered = that member
    (IE fires Entered on entry; the scripts gate themselves on globals, e.g. CARATRG1/2 for Caravan_Quest)"""
    for r in trigs:
        k = (area, r['name'])
        if _disabled(area, r['name']):
            _inside.pop(k, None)
            continue
        who = None
        for p, (px, py) in zip(party, pts):
            if near_region(px, py, r['poly']):
                who = p
                break
        was = _inside.get(k)
        _inside[k] = who
        if who is None:
            continue
        try:
            import ie_runtime as rt
            mod = __import__(r['module'])
            events = {'Entered': who} if was is None else {}
            if getattr(mod, 'USES_IS_OVER_ME', False):
                events['IsOverMe'] = [p for p, (px, py) in zip(party, pts)
                                      if near_region(px, py, r['poly'], near=0)]
            elif was is not None:
                continue
            ident = 'area_' + area.upper()
            rt.run_script(rt.Ctx(None, who, ident, area.upper(), events), mod.BLOCKS)
            if was is None:
                _log('%s: %s entered (%s)' % (area, r['name'], r['module']))
        except Exception as e:
            _log('trigger %s %s failed: %s' % (area, r['name'], e))


def poll(gen=0):
    """time event callback"""
    try:
        keep = tick(gen)
    except Exception as e:
        import traceback
        _log('poll failed: %s %s' % (e, traceback.format_exc()))
        keep = 1
    if keep:
        game.timeevent_add(poll, (gen,), POLL_MS, 1)
    return 0


def start():
    """Start the poll unless one is already alive (called from iwd.go() and from baked creatures' first heartbeat)."""
    global _gen, _last_poll, _armed, _map
    if time.time() - _last_poll < ALIVE_S:
        return 0
    _gen = _gen + 1
    _last_poll = time.time()
    _armed = False
    _map = None
    game.timeevent_add(poll, (_gen,), POLL_MS, 1)
    _log('started (gen %d)' % _gen)
    return 1

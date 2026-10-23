# Temple+ runtime for the travel regions of maps converted by ie2toee (Python 2.7 inside the game; the syntax is also
# valid Python 3 so proto/test_travel.py can run it against a mock game). docs/travel.md has the design.
#
# IE areas are joined by "travel regions" (ARE regions of type travel): walk into one and the whole party moves to a
# named entrance of another area. Temple+ has no such trigger, so this module polls the party every POLL_MS:
#   * any party member inside a region of the current map (or within NEAR tiles of its outline) moves the whole
#     party, with game.fade_and_teleport, to the destination entrance's arrival tile (ie_travel_data.py, written by
#     ie_exits.py; ie2toee already moved each arrival tile onto walkable ground);
#   * the poll stays DISARMED until the party has been outside every region once, so arriving next to a region (or
#     loading a save made there) does not bounce the party back;
#   * an exit whose destination was not converted shows a one-time "This exit (ARxxxx) is not in the preview" note
#     and the party stays;
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
    """interiors have no baked data: attach their doors on arrival (baked areas do it in ie_bakert.area_pass)"""
    try:
        __import__('ie_bake_' + area.lower())
        return 0                      # baked: ie_bakert attaches the doors on the first heartbeat
    except ImportError:
        pass
    try:
        import ie_doors
        __import__('ie_doors_' + area.lower())
        n = ie_doors.start(area)
        _log('%s: no baked data, attached %d doors' % (area, n))
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


def travel(r):
    """move the whole party to the destination entrance of region r (a data dict)"""
    global _armed, _busy_until
    d = _data()
    dst = d.AREAS[r['dest_area']]
    u, v, orient = dst['entrances'][r['dest_entrance']]
    _armed = False
    _busy_until = time.time() + BUSY_S
    _travels[0] += 1
    _log('%s -> %s %s (map %d tile %d,%d)' % (r['name'], r['dest_area'], r['dest_entrance'], dst['map'], u, v))
    game.fade_and_teleport(0, 0, 0, dst['map'], u, v)


_in_info = set()


def info_points(area_data, pts):
    """show the text of every info point (IE Trigger Point) a party member just stepped into: floating text over the
    leader + the message log; once per entry (shown again after the party has left the region)"""
    inside = set()
    for k, r in enumerate(area_data.get('infos') or ()):
        if [1 for px, py in pts if near_region(px, py, r['poly'], 0)]:
            inside.add(k)
            if k not in _in_info:
                _log('info %s: %s' % (r['name'], r['text'][:60]))
                try:
                    game.create_history_freeform(r['text'] + '\n\n')
                    game.leader.float_text_line(r['text'], 5)   # light blue: white is lost on snow
                except Exception as e:
                    _log('info show: %s' % e)
    _in_info.clear(); _in_info.update(inside)


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
    if cur != _map:
        _map = cur
        _in_info.clear()
        _armed = False                # (re)arm only after leaving every region on this map
        area = d.BY_MAP.get(cur)
        if area:
            _attach_doors(area)
    if now < _busy_until:
        return 1                      # (fade + map load after a travel: no new travel yet)
    area = d.BY_MAP.get(cur)
    if not area:
        return 1
    pts = [_pos(p) for p in party]
    info_points(d.AREAS[area], pts)
    r = hit_region(d.AREAS[area], pts)
    if r is None:
        _armed = True
    elif _armed:
        if r.get('dest_map'):
            travel(r)
        else:
            _note_unconverted(r)
            _armed = False            # do not re-note while standing in the region; re-arms once the party steps out
    return 1


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

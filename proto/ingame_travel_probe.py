# In-game travel test (Temple+ Python 2.7), run via run_ingame.sh:
#   TP_AUTOEXEC="import sys; sys.path[:0]=[<proto>, <proto>/runtime, <out>]; import ingame_travel_probe"
# Env: IE2TOEE_BUILDING (default AR1001), IE2TOEE_TOWN (its parent area, default AR1000; e.g. AR1006 for AR1015). iwd.go() starts ie_travel and teleports to the town; the party is put on the
# town entrance of the building, runs into the building's door region (-> must arrive in the interior), then runs into the
# interior's exit region (-> must be back in the town). Lines "RESULT <step> PASS|FAIL ..." + "SHOT <name>" go to the log.
from toee import *
from utilities import location_from_axis, location_to_axis
import os
LOG = os.environ.get('IE2TOEE_PROBE_LOG', 'ie2toee_probe.log')
B = os.environ.get('IE2TOEE_BUILDING', 'AR1001')
TOWN = os.environ.get('IE2TOEE_TOWN', 'AR1000')
import ie_travel_data as D
EXT, INT = D.AREAS[TOWN], D.AREAS[B]
exit_r = [r for r in EXT['regions'] if r['dest_area'] == B][0]
back_r = [r for r in INT['regions'] if r['dest_area'] == TOWN][0]
ent = EXT['entrances']['FR' + B[2:]]          # town entrance of this building
def centre(r):
    a = r.get('anchor')    # a walkable tile at the region (a blocked click target does not move the party)
    if a:
        return a[0], a[1]
    xs = [p[0] for p in r['poly']]; ys = [p[1] for p in r['poly']]
    return int(round(sum(xs) / len(xs))), int(round(sum(ys) / len(ys)))

def log(s):
    f = open(LOG, 'a'); f.write(s + '\n'); f.close()

def where(tag):
    l = game.leader; x, y = location_to_axis(l.location)
    log("%s map=%d leader=(%d,%d) party=%s" % (tag, l.map, x, y, [(location_to_axis(o.location)[0], location_to_axis(o.location)[1], o.map) for o in game.party]))
    try:
        import ie_travel as T
        pts = [T._pos(o) for o in game.party]
        a = T.D.BY_MAP.get(l.map) if hasattr(T, 'D') else T._data().BY_MAP.get(l.map)
        log("  pos=%s armed=%s busy_left=%.1f hit=%s" % ([(round(p[0], 2), round(p[1], 2)) for p in pts], T._armed,
            T._busy_until - __import__('time').time(), (T.hit_region(T._data().AREAS[a], pts) or {}).get('name')))
    except Exception as e:
        log("  (no travel state: %s)" % e)
    return 0

def look(tag):
    where(tag); game.scroll_to(game.leader); log("SHOT " + tag); return 0

def place(mp, x, y, tag):
    if game.leader.map != mp:     # a parent area other than the town: travel there first, then place
        game.fade_and_teleport(0, 0, 0, mp, x, y); game.timeevent_add(place, (mp, x, y, tag), 4000, 1); return 0
    for i, o in enumerate(game.party):
        o.move(location_from_axis(x + (i % 2), y + (i // 2)), 0, 0)
    game.scroll_to(game.leader); where(tag); return 0

def run_to(x, y, tag):
    where('before-' + tag); log("RUN_TO %s (%d,%d)" % (tag, x, y))
    for o in game.party:
        o.run_to(location_from_axis(x, y))
    return 0

def expect(tag, mp):
    l = game.leader; ok = l.map == mp and all(o.map == mp for o in game.party)
    log("RESULT %s %s (leader map %d, want %d)" % (tag, ok and 'PASS' or 'FAIL', l.map, mp)); where(tag); return 0

def open_door(tag):
    # the building's door is closed in IE too: open the door nearest to the region (like a click on it)
    import ie_doors
    cx, cy = centre(exit_r); best = None
    for d, p, last in ie_doors._doors:
        x, y = d['loc'][0], d['loc'][1]; dd = (x - cx) ** 2 + (y - cy) ** 2
        if best is None or dd < best[0]:
            best = (dd, d)
    if best is None:
        log("RESULT open_door FAIL (no doors attached)"); return 0
    d = best[1]
    log("door nearest to %s: %s at %s open=%s dist2=%d" % (exit_r['name'], d['name'], d['loc'][:2], d['open'], best[0]))
    if not ie_doors._doors[[x[0] for x in ie_doors._doors].index(d)][2]:
        ie_doors.toggle(d['name'])
    return 0

def done():
    log("DONE"); return 0

t = [0]
def at(dt, fn, args=()):
    t[0] += dt; game.timeevent_add(fn, args, t[0], 1)

log("travel probe %s: exit region %s centre %s -> interior entrance %s; back region %s centre %s" % (
    B, exit_r['name'], centre(exit_r), D.AREAS[B]['entrances'], back_r['name'], centre(back_r)))
def go():
    import iwd
    iwd.go(); return 0
at(2000, go)      # (not at import time: that sometimes hung the game on its legal screen)
at(9000, look, ('town_start',))
at(500, place, (EXT['map'], ent[0], ent[1], 'at_town_entrance'))
at(0 if TOWN == 'AR1000' else 5000, where, ('placed',))
at(2500, open_door, ('d',))
at(2000, look, ('town_before_door',))
at(300, run_to, (centre(exit_r)[0], centre(exit_r)[1], 'door'))
at(14000, expect, ('entered_building', INT['map']))
at(5000, look, ('interior_arrival',))
at(4000, expect, ('no_bounce_in_interior', INT['map']))
at(300, run_to, (centre(back_r)[0], centre(back_r)[1], 'out'))
at(7000, where, ('mid_out',))
at(7000, expect, ('back_in_town', EXT['map']))
at(4000, look, ('town_after_exit',))
at(500, done)

# In-game test of the exit icons (Temple+ Python 2.7), run via run_ingame.sh (docs/travel.md, "Exit icons"):
#   TP_AUTOEXEC="import sys; sys.path[:0]=[<proto>, <proto>/runtime, <out>]; import ingame_exiticon_probe"
# Env: IE2TOEE_CLEAR=1 (hide non-party critters), IE2TOEE_BUILDINGS=AR1001,AR1006 (interiors to visit; AR1015:AR1006 = a side room and its parent area, default AR1000), IE2TOEE_SAVE=<slot name> (save at the end), IE2TOEE_COUNT_ONLY=1 (after an autoload: only count icons).
# For each building: start on the town tile in front of it, centre the view on the town's exit icon into it, click it
# (real mouse click; a scripted use is the fallback), check the party arrived in the interior at the entrance, then
# the same with the interior's exit icon back to town. Lines "RESULT ..." + "SHOT <name>" go to the log.
from toee import *
from utilities import location_from_axis, location_to_axis
import os
LOG = os.environ.get('IE2TOEE_PROBE_LOG', 'ie2toee_probe.log')
import ie_travel_data as D
BLD = os.environ.get('IE2TOEE_BUILDINGS', 'AR1001,AR1006').split(',')
COUNT_ONLY = os.environ.get('IE2TOEE_COUNT_ONLY')
CLEAR = os.environ.get('IE2TOEE_CLEAR') == '1'
PARENT = os.environ.get('IE2TOEE_PARENT', 'AR1000')   # default parent area (e.g. I2AR1000 with a map name prefix)   # hide the area's non-party critters (hostile maps would start combat)

def clear():
    n = 0
    for x in range(300, 700, 20):
        for y in range(300, 700, 20):
            for o in game.obj_list_vicinity(location_from_axis(x, y), OLC_CRITTERS):
                if o not in game.party and not (o.object_flags_get() & OF_OFF):
                    o.object_flag_set(OF_OFF); n += 1
    log('cleared %d critters on map %d' % (n, game.leader.map)); return 0

def log(s):
    f = open(LOG, 'a'); f.write(s + '\n'); f.close()

def icons():
    l = game.leader
    return [o for o in game.obj_list_vicinity(l.location, OLC_SCENERY) if o.obj_get_int(obj_f_scenery_teleport_to)]

def region(area, dest):
    return [r for r in D.AREAS[area]['regions'] if r['dest_area'] == dest][0]

def dist(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))

st = {}
def look(tag, dest_area):
    try:
        ic = icons()
        log('%s: map %d leader %s, %d exit icons near: %s' % (tag, game.leader.map, location_to_axis(game.leader.location), len(ic),
            [(location_to_axis(o.location), o.obj_get_int(obj_f_scenery_teleport_to)) for o in ic]))
        r = region(D.BY_MAP[game.leader.map], dest_area)
        u, v = D.AREAS[dest_area]['entrances'][r['dest_entrance']][:2]
        st['want'] = (D.AREAS[dest_area]['map'], (u, v))
        # the icon of this region sits on its anchor tile (else near the polygon centre)
        px = sum(p[0] for p in r['poly']) / len(r['poly']); py = sum(p[1] for p in r['poly']) / len(r['poly'])
        if r.get('anchor'): px, py = r['anchor']
        ic.sort(key=lambda o: dist(location_to_axis(o.location), (px, py)))
        st['icon'] = ic and ic[0] or None
        if st['icon']:
            game.scroll_to(st['icon'])
            lx, ly = location_to_axis(game.leader.location)
            st['offs'] = ' '.join('%d,%d' % (location_to_axis(o.location)[0] - lx, location_to_axis(o.location)[1] - ly) for o in ic)
    except Exception, e:
        import traceback; log('LOOK ERROR %s %s' % (e, traceback.format_exc()))
    return 0

def shot(n):
    log('SHOT ' + n); return 0

def press(tag):
    log('CLICKICON ' + st.get('offs', '')); return 0   # target icon's tile offset from the leader first

def check(tag, fallback=1):
    try:
        m, (u, v) = st['want']
        l = game.leader
        ok = l.map == m and dist(location_to_axis(l.location), (u, v)) <= 3
        if not ok and fallback and st.get('icon'):
            log('%s: click did not travel (map %d), scripted use of the icon' % (tag, l.map))
            l.anim_goal_use_object(st['icon']); st['used'] = st.get('used', 0) + 1
            return 0
        log('RESULT %s %s (map %d at %s, wanted map %d near %s)' % (tag, ok and 'PASS' or 'FAIL', l.map, location_to_axis(l.location), m, (u, v)))
    except Exception, e:
        import traceback; log('CHECK ERROR %s %s' % (e, traceback.format_exc()))
    return 0

def count(tag):
    log('RESULT count %s map %d: %d exit icons' % (tag, game.leader.map, len(icons()))); return 0

def save():
    n = os.environ.get('IE2TOEE_SAVE')
    if n:
        log('SAVE %s -> %s' % (n, game.savegame(n, 'ie2toee exit icons')))
    log('DONE')   # last event: a save holding a pending probe event would not load without this module
    return 0

def done():
    log('DONE'); return 0

t = [0]
def at(dt, fn, args=()):
    t[0] += dt; game.timeevent_add(fn, args, t[0], 1)

log('SHOT town_start')
try:
    import ie_travel; ie_travel.start()
except Exception, e:
    log('travel start: %s' % e)
if COUNT_ONLY:
    at(5000, count, ('after load',))
    b = BLD[0]; r = region(b, PARENT); u, v = D.AREAS[PARENT]['entrances'][r['dest_entrance']][:2]
    at(500, lambda: (game.fade_and_teleport(0, 0, 0, D.AREAS[PARENT]['map'], u, v), 0)[1])
    at(5000, count, ('town again',))
    at(500, done)
else:
    for b in BLD:
        b, P = (b.split(':') + [PARENT])[:2]
        r = region(b, P)                         # the interior's way out lands on this entrance of its parent area
        u, v = D.AREAS[P]['entrances'][r['dest_entrance']][:2]
        at(1000, lambda u=u, v=v, m=D.AREAS[P]['map']: (game.fade_and_teleport(0, 0, 0, m, u, v), 0)[1])
        if CLEAR: at(1500, clear)
        at(4500 if CLEAR else 6000, look, ('town->' + b, b)); at(4000, shot, ('exit-icon-town-to-' + b,)); at(1500, press, ('',)); at(12000, check, ('enter ' + b + ' via icon',)); at(15000, check, ('enter ' + b + ' (after fallback)', 0))
        at(1500, count, (b,))
        if CLEAR: at(500, clear)
        at(500, look, (b + '->town', P)); at(4000, shot, ('exit-icon-' + b + '-to-town',)); at(1500, press, ('',)); at(12000, check, ('exit ' + b + ' via icon',)); at(15000, check, ('exit ' + b + ' (after fallback)', 0))
    at(1500, count, ('town',))
    at(500, save)

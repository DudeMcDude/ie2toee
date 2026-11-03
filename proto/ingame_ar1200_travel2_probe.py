# Probe: AR1200 -> AR1201 -> AR1200 -> AR1100 (AR1100's arrival dialogue pauses time events, so AR1100 is the last stop) through the converted exit icons (scripted use of the icon).
from toee import *
from utilities import location_from_axis, location_to_axis
import os, __main__
import ie_travel_data as D
LOG = os.environ.get('IE2TOEE_PROBE_LOG', 'probe.log')
def log(s):
    f = open(LOG, 'a'); f.write(s + '\n'); f.close()
HOPS = [('I2AR1200', 'I2AR1100'), ('I2AR1100', 'I2AR1200'), ('I2AR1200', 'I2AR1201'), ('I2AR1201', 'I2AR1200')]
def go(i):
    try:
        __main__.cheats.kos = 0
    except Exception:
        pass
    if i >= len(HOPS):
        log('DONE'); return 0
    a, b = HOPS[i]
    r = [x for x in D.AREAS[a]['regions'] if x['dest_area'] == b][0]
    u, v = r['anchor']
    if game.leader.map != D.AREAS[a]['map']:
        log('hop %d: not on %s (map %d)' % (i, a, game.leader.map))
    game.fade_and_teleport(0, 0, 0, D.AREAS[a]['map'], u + 4, v + 4)     # next to the icon, not on it (the party hides it)
    game.timeevent_add(use, (i,), 5000, 1)
    return 0
def use(i):
    a, b = HOPS[i]
    r = [x for x in D.AREAS[a]['regions'] if x['dest_area'] == b][0]
    ic = [o for o in game.obj_list_vicinity(game.leader.location, OLC_SCENERY) if o.obj_get_int(obj_f_scenery_teleport_to)]
    ax = r['anchor']
    ic.sort(key=lambda o: max(abs(location_to_axis(o.location)[0] - ax[0]), abs(location_to_axis(o.location)[1] - ax[1])))
    log('hop %d %s->%s: %d icons, nearest %s' % (i, a, b, len(ic), ic and location_to_axis(ic[0].location)))
    if ic:
        game.scroll_to(ic[0])
        lx, ly = location_to_axis(game.leader.location)
        offs = ' '.join('%d,%d' % (location_to_axis(o.location)[0] - lx, location_to_axis(o.location)[1] - ly) for o in ic)
        game.timeevent_add(click, (i, offs), 2500, 1)
    else:
        game.timeevent_add(check, (i,), 1000, 1)
    return 0
def fallback(i):
    a, b = HOPS[i]
    if game.leader.map == D.AREAS[b]['map']:
        return check(i)
    ic = [o for o in game.obj_list_vicinity(game.leader.location, OLC_SCENERY) if o.obj_get_int(obj_f_scenery_teleport_to)]
    r = [x for x in D.AREAS[a]['regions'] if x['dest_area'] == b][0]; ax = r['anchor']
    ic.sort(key=lambda o: max(abs(location_to_axis(o.location)[0] - ax[0]), abs(location_to_axis(o.location)[1] - ax[1])))
    log('hop %d: click did not travel (combat %s), scripted use of icon -> jump %d' % (i, game.combat_is_active(), ic and ic[0].obj_get_int(obj_f_scenery_teleport_to) or -1))
    if ic:
        game.leader.anim_goal_use_object(ic[0])
    game.timeevent_add(check, (i,), 12000, 1)
    return 0
def click(i, offs):
    log('SHOT hop%d' % i); log('CLICKICON ' + offs)     # run_ingame.sh finds the icon on screen and clicks it
    game.timeevent_add(fallback, (i,), 10000, 1)
    return 0
def check(i):
    a, b = HOPS[i]
    ok = game.leader.map == D.AREAS[b]['map']
    log('RESULT hop %d %s -> %s %s (map %d at %s)' % (i, a, b, ok and 'PASS' or 'FAIL', game.leader.map, location_to_axis(game.leader.location)))
    log('SHOT arrive%d_%s' % (i, b))
    game.timeevent_add(go2, (i + 1,), 8000, 1)
    return 0
def go2(i):
    a = HOPS[i][0] if i < len(HOPS) else None
    if a is None:
        log('DONE'); return 0
    # walk from where the last hop landed: only teleport to the next region's anchor on the same map
    return go(i)
log('start map %d' % game.leader.map); log('KEY Escape'); log('KEY Escape')
go(0)

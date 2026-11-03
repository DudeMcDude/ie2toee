# Probe: use the return exit icons from a tile next to them (AR1201 -> AR1200, AR1100 -> AR1200); path finding check
from toee import *
from utilities import location_from_axis, location_to_axis
import os
LOG = os.environ.get('IE2TOEE_PROBE_LOG', 'probe.log')
def log(s):
    f = open(LOG, 'a'); f.write(s + '\n'); f.close()
T = [(5959, 484, 479, 488, 480, 5958), (5957, 451, 461, 448, 459, 5958)]
def go(i):
    if i >= len(T):
        log('DONE'); return 0
    m, au, av, nu, nv, dst = T[i]
    game.fade_and_teleport(0, 0, 0, m, au, av)
    game.timeevent_add(near, (i,), 8000, 1)
def icon():
    ic = [o for o in game.obj_list_vicinity(game.leader.location, OLC_SCENERY) if o.obj_get_int(obj_f_scenery_teleport_to)]
    ic.sort(key=lambda o: game.leader.distance_to(o))
    return ic and ic[0]
def near(i):
    m, au, av, nu, nv, dst = T[i]
    o = icon()
    log('t%d at %s icon %s dist %.1f' % (i, location_to_axis(game.leader.location), o and location_to_axis(o.location), o and game.leader.distance_to(o) or -1))
    log('SHOT use%d_arrive' % i)
    # first: use straight from the arrival spot, leader alone moves
    game.leader.anim_goal_use_object(o)
    game.timeevent_add(chk, (i, 0), 9000, 1)
def chk(i, k):
    m, au, av, nu, nv, dst = T[i]
    log('t%d k%d map %d at %s %s' % (i, k, game.leader.map, location_to_axis(game.leader.location), game.leader.map == dst and 'PASS' or 'FAIL'))
    if game.leader.map == dst or k == 1:
        game.timeevent_add(go, (i + 1,), 2000, 1); return 0
    for p in game.party:
        p.move(location_from_axis(nu, nv), 0.0, 0.0)
    game.timeevent_add(use2, (i,), 1500, 1)
def use2(i):
    o = icon(); log('t%d moved next to icon: dist %.1f' % (i, game.leader.distance_to(o)))
    game.leader.anim_goal_use_object(o)
    game.timeevent_add(chk, (i, 1), 9000, 1)
log('KEY Escape'); log('KEY Escape')
go(0)

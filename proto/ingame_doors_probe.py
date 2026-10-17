# In-game door test (Temple+ Python 2.7), run via run_ingame.sh with
#   TP_AUTOEXEC="import sys; sys.path[:0]=[<proto>, <proto>/runtime, <out>]; import ingame_doors_probe"
# Env: IE2TOEE_AREA, IE2TOEE_MAP, IE2TOEE_DOOR (door name from <AREA>_doors.json), IE2TOEE_START=x,y and
# IE2TOEE_TARGET=x,y on either side of the door (target reachable only through it), IE2TOEE_PARK=x,y for the rest
# of the party. Sequence: closed -> run (must fail) -> toggle open -> run (must arrive) -> toggle closed ->
# leader "uses" the door like a mouse click (opens it) -> run (must arrive).
from toee import *
from utilities import location_from_axis, location_to_axis
import os, ie_doors
LOG = os.environ.get('IE2TOEE_PROBE_LOG', 'ie2toee_probe.log')   # set by run_ingame.sh
xy = lambda k: tuple(int(c) for c in os.environ[k].split(','))
AREA, MAP, DOOR = os.environ['IE2TOEE_AREA'], int(os.environ['IE2TOEE_MAP']), os.environ['IE2TOEE_DOOR']
START, TARGET, PARK = xy('IE2TOEE_START'), xy('IE2TOEE_TARGET'), xy('IE2TOEE_PARK')

def log(s):
    f = open(LOG, 'a'); f.write(s + '\n'); f.close()

def where(tag):
    l = game.leader; x, y = location_to_axis(l.location)
    log("%s map=%d leader=(%d,%d) door_blocked_subtiles=%d" % (tag, l.map, x, y, ie_doors.blocked_count(DOOR)))
    return 0

def shot(tag):
    where(tag); log("SHOT %s" % tag); return 0

def setup():
    log("setup doors=%d" % ie_doors.setup(AREA))
    game.scroll_to(location_from_axis(*START))
    return 0

def run(tag):
    where('before-' + tag); log("RUN_TO %s %s" % (tag, TARGET))
    game.leader.run_to(location_from_axis(*TARGET))
    return 0

def back(tag):
    for o in game.party:
        o.move(location_from_axis(*(START if o == game.leader else PARK)), 0, 0)
    game.scroll_to(location_from_axis(*START))
    where(tag); return 0

def toggle(tag):
    log("TOGGLE %s -> %d" % (DOOR, ie_doors.toggle(DOOR))); return 0

def use_door(tag):
    for d, p, last in ie_doors._doors:
        if d['name'] == DOOR:
            log("USE %s %s" % (DOOR, tag)); game.leader.anim_goal_use_object(p)
    return 0

def done():
    log("DONE"); return 0

t = [0]
def at(dt, fn, args=()):
    t[0] += dt; game.timeevent_add(fn, args, t[0], 1)

log("doors probe start map=%d" % game.leader.map)
game.fade_and_teleport(0, 0, 0, MAP, START[0], START[1])
at(8000, setup)
at(500, back, ('park',))
at(2000, shot, ('closed',))
at(500, run, ('closed',))
at(9000, shot, ('closed_after_run',))
at(500, back, ('reset',))
at(1000, toggle, ('open',))
at(1500, shot, ('opened',))
at(500, run, ('open',))
at(9000, shot, ('open_after_run',))
at(500, back, ('reset2',))
at(1000, toggle, ('close',))
at(1500, shot, ('closed_again',))
at(500, use_door, ('open',))
at(6000, shot, ('used_open',))
at(500, run, ('after_use',))
at(9000, shot, ('after_use_run',))
at(500, done)

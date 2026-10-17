# In-game walk test for a converted map (Temple+ Python 2.7), run via run_ingame.sh.
# Teleports the party, takes screenshots, runs to a list of targets and logs where the leader ends up.
#   IE2TOEE_MAP=<map id> IE2TOEE_START=x,y IE2TOEE_RUNS="x,y;x,y;..." [IE2TOEE_SHOTS_PER_RUN=2]
# Writes a log the runner script watches; "SHOT <name>" lines trigger an external screenshot.
from toee import *
from utilities import location_from_axis, location_to_axis
import os
LOG = os.environ.get('IE2TOEE_PROBE_LOG', 'ie2toee_probe.log')   # set by run_ingame.sh
MAP = int(os.environ['IE2TOEE_MAP'])
START = tuple(int(c) for c in os.environ['IE2TOEE_START'].split(','))
RUNS = [tuple(int(c) for c in r.split(',')) for r in os.environ.get('IE2TOEE_RUNS', '').split(';') if r]
SHOTS = int(os.environ.get('IE2TOEE_SHOTS_PER_RUN', '2'))

def log(s):
    f = open(LOG, 'a'); f.write(s + '\n'); f.close()

def where(tag):
    l = game.leader; x, y = location_to_axis(l.location)
    log("%s map=%d leader=(%d,%d) off=(%.1f,%.1f)" % (tag, l.map, x, y, l.off_x, l.off_y))
    return 0

def look(tag):
    where(tag); game.scroll_to(game.leader); log("SHOT %s" % tag); return 0

def run(x, y, tag):
    where("before-" + tag); log("RUN_TO %s (%d,%d)" % (tag, x, y))
    for o in game.party:
        o.run_to(location_from_axis(x, y))
    return 0

def done():
    log("DONE"); return 0

t = [0]
def at(dt, fn, args=()):
    t[0] += dt; game.timeevent_add(fn, args, t[0], 1)

log("probe start map=%d" % game.leader.map)
game.fade_and_teleport(0, 0, 0, MAP, START[0], START[1])
at(9000, look, ('map%d_start' % MAP,))
for k, (x, y) in enumerate(RUNS):
    at(1000, run, (x, y, 'run%d' % k))
    for s in range(SHOTS):
        at(5000, look, ('map%d_run%d_%02ds' % (MAP, k, 5 * (s + 1)),))
at(500, done)

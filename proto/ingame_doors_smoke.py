# Smoke test: set up the doors of a converted area and toggle each one twice (Temple+ Python 2.7).
# Env: IE2TOEE_AREA, IE2TOEE_MAP, IE2TOEE_START=x,y
from toee import *
from utilities import location_from_axis
import os, ie_doors
LOG = os.environ.get('IE2TOEE_PROBE_LOG', 'ie2toee_probe.log')
AREA = os.environ['IE2TOEE_AREA']; MAP = int(os.environ['IE2TOEE_MAP'])
SX, SY = [int(c) for c in os.environ['IE2TOEE_START'].split(',')]
def log(s):
    f = open(LOG, 'a'); f.write(s + '\n'); f.close()
def setup():
    log("setup %s doors=%d" % (AREA, ie_doors.setup(AREA))); return 0
def flip(tag):
    for d, p, last in ie_doors._doors:
        b = ie_doors.blocked_count(d['name']); ie_doors.toggle(d['name'])
        log("%s %s open=%d blocked=%d" % (tag, d['name'], last, b))
    return 0
def done(): log("DONE"); return 0
t = [0]
def at(dt, fn, args=()):
    t[0] += dt; game.timeevent_add(fn, args, t[0], 1)
game.fade_and_teleport(0, 0, 0, MAP, SX, SY)
at(8000, setup); at(1000, flip, ('a',)); at(1500, flip, ('b',)); at(1500, flip, ('c',)); at(500, done)

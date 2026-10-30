# In-game check that the party can walk off the I2AR1000 start ship (developer tool, run via run_ingame.sh): teleport to
# the start tile, kos=0, make every party member walk (runoff, real pathing) to dock waypoints, log positions, screenshot.
from toee import *
from utilities import location_from_axis, location_to_axis
import os, __main__
LOG = os.environ.get('IE2TOEE_PROBE_LOG', 'ie2toee_probe.log')
def log(s):
    f = open(LOG, 'a'); f.write(s + '\n'); f.close()
MAP = int(os.environ.get('IE2TOEE_MAP', '5950'))
WAY = [tuple(int(n) for n in p.split(',')) for p in os.environ.get('IE2TOEE_WAY', '464,486;472,468;489,425').split(';')]
def start():
    game.fade_and_teleport(0, 0, 0, MAP, 450, 490); game.timevent_add(arrived, (), 6000, 1)
def arrived():
    try: __main__.cheats.kos = 0
    except Exception as e: log('kos: %s' % e)
    log('start %r' % (location_to_axis(game.leader.location),)); log('SHOT gw_0_start'); log('KEY ctrl+a')
    game.timevent_add(click, (0,), 1500, 1)
CLK = [tuple(int(n) for n in p.split(',')) for p in os.environ.get('IE2TOEE_CLICKS', '318,573;190,548').split(';')]
def click(i):
    if i >= len(CLK): log('DONE'); return
    log('CLICK %d %d' % CLK[i]); game.timevent_add(seen, (i,), 12000, 1)
def seen(i):
    log('RESULT click %d party %r' % (i, [location_to_axis(pc.location) for pc in game.party]))
    log('SHOT gw_click%d' % (i + 1)); game.timevent_add(click, (i + 1,), 1000, 1)
def go(i):
    if i >= len(WAY): log('DONE'); return
    u, v = WAY[i]
    for k, pc in enumerate(game.party): pc.runoff(location_from_axis(u + k % 2, v + k // 2))
    game.timevent_add(check, (i,), 20000, 1)
def check(i):
    log('RESULT way %d %r party %r' % (i, WAY[i], [location_to_axis(pc.location) for pc in game.party]))
    log('SHOT gw_%d_way' % (i + 1)); game.timevent_add(go, (i + 1,), 1500, 1)
start()

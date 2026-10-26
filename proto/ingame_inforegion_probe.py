# In-game test of the Temple+ info region system (feature/info-regions), run via run_ingame.sh:
#   TP_AUTOEXEC="import sys; sys.path[:0]=[<proto>, <proto>/runtime, <out>]; import ingame_inforegion_probe"
# Teleports the party next to an AR1000 info point (env IE2TOEE_INFO, default 'Trigger Point 16' = the Fishmonger sign),
# centres the view on it and has run_ingame.sh click the screen centre (CLICK). The engine log should show
# "InfoRegions: ... hit <name>", the text floats over the leader and the party does not walk there.
from toee import *
from utilities import location_from_axis, location_to_axis
import os
LOG = os.environ.get('IE2TOEE_PROBE_LOG', 'ie2toee_probe.log')
import ie_travel_data as D
A = D.AREAS['AR1000']
NAME = os.environ.get('IE2TOEE_INFO', 'Trigger Point 16')
CX, CY = [int(v) for v in os.environ.get('IE2TOEE_CENTRE', '640,400').split(',')]
R = [r for r in A['infos'] if r['name'] == NAME][0]
cu = sum(p[0] for p in R['poly']) / len(R['poly']); cv = sum(p[1] for p in R['poly']) / len(R['poly'])

def log(s):
    f = open(LOG, 'a'); f.write(s + '\n'); f.close()

def look():
    game.scroll_to(location_from_axis(int(cu), int(cv))); return 0

def click():
    log('leader before %s' % (location_to_axis(game.leader.location),)); log('CLICK %d %d' % (CX, CY)); return 0

def check():
    log('RESULT leader after %s (region %s %.1f,%.1f: %s)' % (location_to_axis(game.leader.location), NAME, cu, cv, R['text'][:40])); return 0

def shot(n):
    log('SHOT ' + n); return 0

t = [0]
def at(dt, fn, args=()):
    t[0] += dt; game.timeevent_add(fn, args, t[0], 1)

game.fade_and_teleport(0, 0, 0, A['map'], int(cu) + 5, int(cv) + 5)
at(5000, look)
at(1500, shot, ('ir_before',))
at(500, click)
at(400, shot, ('ir_float',))
at(2500, check)
at(200, shot, ('ir_after',))
at(500, lambda: log('DONE') or 0)

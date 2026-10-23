# In-game test of the AR1000 info points (Temple+ Python 2.7), run via run_ingame.sh:
#   TP_AUTOEXEC="import sys; sys.path[:0]=[<proto>, <proto>/runtime, <out>]; import ingame_info_probe"
# Starts the travel poll, teleports the party next to an info point (env IE2TOEE_INFO, default 'Trigger Point 17'),
# then walks it into the region; checks the message-log/float text was emitted (ie_travel log line "info ...").
from toee import *
from utilities import location_from_axis
import os
LOG = os.environ.get('IE2TOEE_PROBE_LOG', 'ie2toee_probe.log')
import ie_travel_data as D
A = D.AREAS['AR1000']
NAME = os.environ.get('IE2TOEE_INFO', 'Trigger Point 17')
R = [r for r in A['infos'] if r['name'] == NAME][0]
cu = int(round(sum(p[0] for p in R['poly']) / len(R['poly']))); cv = int(round(sum(p[1] for p in R['poly']) / len(R['poly'])))

def log(s):
    f = open(LOG, 'a'); f.write(s + '\n'); f.close()

def walk():
    try:
        for p in game.party:
            p.move(location_from_axis(cu, cv))
        log('walked party to %d,%d (%s: %s)' % (cu, cv, NAME, R['text'][:50]))
    except Exception, e:
        log('WALK ERROR %s' % e)
    return 0

def check():
    import ie_travel
    game.scroll_to(game.leader)
    was = sorted(ie_travel._in_info)
    ie_travel._in_info.clear()        # re-enter: shows the text again now, on screen, for the screenshot
    ie_travel.info_points(A, [ie_travel._pos(p) for p in game.party])
    log('RESULT info %s (%s inside=%s)' % (ie_travel._in_info and 'PASS' or 'FAIL', NAME, was))
    return 0

def shot(n):
    log('SHOT ' + n); return 0

t = [0]
def at(dt, fn, args=()):
    t[0] += dt; game.timeevent_add(fn, args, t[0], 1)

log('SHOT town_start')
try:
    import ie_travel; ie_travel.start()
except Exception, e:
    log('travel start: %s' % e)
game.fade_and_teleport(0, 0, 0, A['map'], cu + 6, cv + 6)
at(5000, shot, ('info_before',))
at(500, walk)
at(1500, check)
at(200, shot, ('info_float',))
at(1500, shot, ('info_after',))
at(500, lambda: log('DONE') or 0)

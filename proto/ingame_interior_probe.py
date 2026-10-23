# In-game test of an interior's baked contents (Temple+ Python 2.7), run via run_ingame.sh:
#   TP_AUTOEXEC="import sys; sys.path[:0]=[<proto>, <proto>/runtime, <out>]; import ingame_interior_probe"
# Env: IE2TOEE_BUILDING (default AR1006), IE2TOEE_DO = talk | container | shop (default talk).
# Teleports the party to the interior's town-side entrance, lists the baked critters + containers (name, proto,
# script, inventory), then talks to the first critter with a dialog script / opens the first container / talks to the
# shopkeeper and picks the first barter ("B:") answer. Lines "RESULT ..." + "SHOT <name>" go to the log.
from toee import *
from utilities import location_from_axis, location_to_axis
import os
LOG = os.environ.get('IE2TOEE_PROBE_LOG', 'ie2toee_probe.log')
B = os.environ.get('IE2TOEE_BUILDING', 'AR1006')
DO = os.environ.get('IE2TOEE_DO', 'talk')
import ie_travel_data as D
INT = D.AREAS[B]
ex, ey = INT['entrances']['FR1000'][:2]
st = {}

def log(s):
    f = open(LOG, 'a'); f.write(s + '\n'); f.close()

def survey():
    try:
        l = game.leader
        log('map=%d leader=%s' % (l.map, location_to_axis(l.location)))
        crs = [o for o in game.obj_list_vicinity(l.location, OLC_CRITTERS) if o not in game.party]
        for o in crs:
            inv = [o.inventory_item(i) for i in range(24)]
            inv = [i.description for i in inv if i != OBJ_HANDLE_NULL]
            log('NPC %s proto=%d dlgscript=%d at %s inv=%s' % (o.description, o.proto, o.scripts[san_dialog],
                                                               location_to_axis(o.location), inv))
        cons = list(game.obj_list_vicinity(l.location, OLC_CONTAINER))
        for o in cons:
            inv = [o.inventory_item(i) for i in range(48)]
            inv = [i.description for i in inv if i != OBJ_HANDLE_NULL]
            log('CONTAINER %s proto=%d at %s items=%s' % (o.description, o.proto, location_to_axis(o.location), inv))
        st['npcs'] = [o for o in crs if o.scripts[san_dialog]]; st['cons'] = cons
        log('RESULT survey %s (%d critters, %d with dialog, %d containers)' % (
            crs and 'PASS' or 'FAIL', len(crs), len(st['npcs']), len(cons)))
        game.scroll_to(st['npcs'] and st['npcs'][0] or l); log('SHOT interior_' + B)
    except Exception, e:
        import traceback; log('SURVEY ERROR %s %s' % (e, traceback.format_exc()))
    return 0

def act():
    try:
        if DO == 'container':
            c = st['cons'][0]
            game.scroll_to(c)
            r = game.leader.container_open_ui(c); log('RESULT container_open %s (%s)' % (r and 'PASS' or 'FAIL', c.description))
        else:
            want = os.environ.get('IE2TOEE_NPC')
            n = [o for o in st['npcs'] if not want or want.lower() in o.description.lower()] or st['npcs']
            n = n[0]; game.scroll_to(n)
            r = n.object_script_execute(game.leader, san_dialog)
            log('RESULT talk %s (%s, script %d, ret %s)' % (r is not None and 'PASS' or 'FAIL', n.description, n.scripts[san_dialog], r))
    except Exception, e:
        import traceback; log('ACT ERROR %s %s' % (e, traceback.format_exc()))
    return 0

def shot(n):
    log('SHOT ' + n); return 0

def key(k):
    log('KEY ' + k); return 0

def done():
    log('DONE'); return 0

t = [0]
def at(dt, fn, args=()):
    t[0] += dt; game.timeevent_add(fn, args, t[0], 1)

log('SHOT town_start')       # (retry.sh waits for this line: the game got past the menus)
log('interior probe %s (%s): entrance FR1000 %d,%d map %d' % (B, DO, ex, ey, INT['map']))
try:
    import ie_travel; ie_travel.start()
except Exception, e:
    log('travel start: %s' % e)
game.fade_and_teleport(0, 0, 0, INT['map'], ex, ey)
at(6000, survey)
at(1500, act)
at(3000, shot, (B + '_' + DO,))
if DO == 'shop':
    at(500, key, ('1',))        # first answer; the probe log shows the dialog lines (TemplePlus.log)
    at(2500, shot, (B + '_' + DO + '_2',))
at(1500, done)

# Save/reload test of a baked interior (Temple+ Python 2.7), run via run_ingame.sh (one game process per run):
#   IE2TOEE_MODE=setup: teleport into IE2TOEE_BUILDING (default AR1008), census, take the first item of the first
#     non-empty container and of the merchant's store stock into the leader's pack, census, save IE2TOEE_SAVE.
#   IE2TOEE_MODE=check (TP_AUTOLOAD=<that save>): census, leave to the town and come back (map reload from the
#     .mob files + the save's diffs), census, save IE2TOEE_SAVE again (for the next check run).
# "CENSUS <tag> {...}" lines: critters by name, containers' items, store stock count, the leader's pack.
from toee import *
from utilities import location_from_axis, location_to_axis
import os
LOG = os.environ.get('IE2TOEE_PROBE_LOG', 'ie2toee_probe.log')
B = os.environ.get('IE2TOEE_BUILDING', 'AR1008')
MODE = os.environ.get('IE2TOEE_MODE', 'setup')
SAVE = os.environ.get('IE2TOEE_SAVE', 'SlotIePersist')
RUN = os.environ.get('IE2TOEE_RUN', MODE)
import ie_travel_data as D
INT = D.AREAS[B]
ex, ey = INT['entrances']['FR1000'][:2]

def log(s):
    f = open(LOG, 'a'); f.write(s + '\n'); f.close()

def items_of(o, n=60):
    r = []
    for i in range(n):
        it = o.inventory_item(i)
        if it != OBJ_HANDLE_NULL:
            r.append(it.description)
    return r

def census(tag):
    l = game.leader
    crs = sorted(o.description for o in game.obj_list_vicinity(l.location, OLC_CRITTERS) if o not in game.party)
    cons = sorted('%s@%s:%s' % (o.description, location_to_axis(o.location), ','.join(sorted(items_of(o)))) for o in
                  game.obj_list_vicinity(l.location, OLC_CONTAINER))
    stock = {}
    for o in game.obj_list_vicinity(l.location, OLC_CRITTERS):
        try:
            b = o.substitute_inventory
        except Exception:
            b = None
        if b is not None and b != OBJ_HANDLE_NULL:
            stock[o.description] = len(items_of(b, 400))
    pack = sorted(items_of(l))
    log('CENSUS %s map=%d critters=%s containers=%s stock=%s pack=%s' % (tag, l.map, crs, cons, stock, pack))
    return 0

def take():
    l = game.leader
    for c in game.obj_list_vicinity(l.location, OLC_CONTAINER):
        if c.object_flags_get() & OF_DONTDRAW:
            continue
        it = c.inventory_item(0)
        if it != OBJ_HANDLE_NULL:
            log('TAKE %s from %s -> %s' % (it.description, c.description, l.item_get(it))); break
    for o in game.obj_list_vicinity(l.location, OLC_CRITTERS):
        try:
            b = o.substitute_inventory
        except Exception:
            b = None
        if b is not None and b != OBJ_HANDLE_NULL and b.inventory_item(0) != OBJ_HANDLE_NULL:
            it = b.inventory_item(0)
            log('BUY %s from %s -> %s' % (it.description, o.description, l.item_get(it))); break
    return 0

def step(s, run):
    if run != RUN:
        return 0
    try:
        if s == 'census1' or s == 'census2' or s == 'census3':
            census(s)
        elif s == 'take':
            take()
        elif s == 'town':
            game.fade_and_teleport(0, 0, 0, 5900, 482, 424)
        elif s == 'back':
            game.fade_and_teleport(0, 0, 0, INT['map'], ex, ey)
        elif s == 'save':
            log('SAVE %s -> %s' % (SAVE, game.savegame(SAVE, 'ie2toee persist test')))
        elif s.startswith('shot'):
            game.scroll_to(game.leader); log('SHOT %s_%s' % (MODE, s[5:]))
        elif s == 'done':
            log('DONE')
    except Exception, e:
        import traceback; log('STEP ERROR %s: %s %s' % (s, e, traceback.format_exc()))
    return 0

import ie_probe_stub
ie_probe_stub.HANDLER[0] = step
t = [0]
def at(dt, s):
    t[0] += dt; game.timeevent_add(ie_probe_stub.step, (s, RUN), t[0], 1)
log('SHOT town_start')
log('persist probe %s mode %s save %s' % (B, MODE, SAVE))
try:
    import ie_travel; ie_travel.start()
except Exception, e:
    log('travel start: %s' % e)
if MODE == 'setup':
    game.fade_and_teleport(0, 0, 0, INT['map'], ex, ey)
    for dt, s in ((6000, 'census1'), (500, 'take'), (1000, 'census2'), (500, 'shot room'), (1000, 'save')):
        at(dt, s)
else:
    for dt, s in ((5000, 'census1'), (500, 'shot room'), (500, 'town'), (5000, 'back'), (6000, 'census2'), (500, 'save')):
        at(dt, s)
at(2500, 'done')

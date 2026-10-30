# In-game check of converted IWD2 dialogue (developer tool, run via run_ingame.sh): to I2AR1000 docks, no fights
# (cheats.kos = 0), open each NPC's converted dialogue (IE2TOEE_TALK=script ids), screenshot, answer 1, screenshot.
from toee import *
from utilities import location_from_axis, location_to_axis
import os, __main__
LOG = os.environ.get('IE2TOEE_PROBE_LOG', 'ie2toee_probe.log')
def log(s):
    f = open(LOG, 'a'); f.write(s + '\n'); f.close()
MAP = int(os.environ.get('IE2TOEE_MAP', '5950')); SX, SY = [int(v) for v in os.environ.get('IE2TOEE_START', '450,490').split(',')]
TALK = [int(v.split(':')[0]) for v in os.environ.get('IE2TOEE_TALK', '1500:py01500ie_10hedron').split(',')]
MODS = [v.split(':')[1] for v in os.environ.get('IE2TOEE_TALK', '1500:py01500ie_10hedron').split(',')]
POS = dict((int(k), tuple(int(n) for n in xy.split(','))) for k, xy in [p.split('@') for p in os.environ.get('IE2TOEE_POS', '').split(';') if p])
def start():
    game.fade_and_teleport(0, 0, 0, MAP, SX, SY)
    game.timevent_add(arrived, (), 6000, 1)
def arrived():
    try:
        __main__.cheats.kos = 0
    except Exception as e:
        log('kos: %s' % e)
    log('leader map %d at %r' % (game.leader.map, location_to_axis(game.leader.location)))
    game.timevent_add(talk, (0,), 1500, 1)
def find(sid):
    for o in game.obj_list_vicinity(game.leader.location, OLC_NPC):
        if o.scripts[san_dialog] == sid: return o
    for o in game.obj_list_range(game.leader.location, 60, OLC_NPC) if hasattr(game, 'obj_list_range') else []:
        if o.scripts[san_dialog] == sid: return o
    return None
def talk(i):
    if i >= len(TALK):
        log('DONE'); return
    sid = TALK[i]; o = find(sid)
    if o is None and sid in POS and not getattr(talk, 'moved_%d' % sid, 0):    # far away: go to its IE spot first
        import ie_runtime as rt
        setattr(talk, 'moved_%d' % sid, 1); u, v = rt.ie_to_tile('AR1000', POS[sid][0], POS[sid][1])
        game.fade_and_teleport(0, 0, 0, MAP, u + 2, v + 2); game.timevent_add(talk, (i,), 3000, 1); return
    if o is None:
        log('RESULT %d not found' % sid); game.timevent_add(talk, (i + 1,), 200, 1); return
    lx, ly = location_to_axis(o.location)
    game.leader.move(location_from_axis(lx + 2, ly + 2)); game.fade_and_teleport(0, 0, 0, MAP, lx + 2, ly + 2)
    game.timevent_add(open_, (i, o), 3000, 1)
def open_(i, o):
    mod = __import__(MODS[i])
    try:
        mod.san_dialog(o, game.leader)
        log('RESULT %d %s opened' % (TALK[i], o))
    except Exception as e:
        log('RESULT %d error %s' % (TALK[i], e))
    log('SHOT dlg_%d_a' % TALK[i])
    game.timevent_add(answer, (i,), 2500, 1)
def answer(i):
    log('KEY 1'); game.timevent_add(shot2, (i,), 2000, 1)
def shot2(i):
    log('SHOT dlg_%d_b' % TALK[i]); log('KEY Escape'); game.timevent_add(talk, (i + 1,), 2000, 1)
start()

# Route-check probe (run via run_ingame.sh TP_AUTOEXEC): for each (name, from, to) tile pair in ROUTECHECK_PAIRS (json file),
# put the turn-based actor at `from`, hold ALT over `to` so the engine draws its path preview, screenshot it (CSHOT rc_NN_name)
# and log debug.pathlen numbers (needs the debug.pathlen hook) both ways. Screen coords come from tpgui.world_to_screen;
# ROUTECHECK_ORIGIN=x,y is the game client's top-left on the X screen.
from toee import *
import os, json
from utilities import location_from_axis, location_to_axis
LOG = os.environ.get('IE2TOEE_PROBE_LOG', 'ie2toee_probe.log')
PAIRS = json.load(open(os.environ['ROUTECHECK_PAIRS']))
MAP = int(os.environ.get('ROUTECHECK_MAP', '5900'))
OX, OY = [int(x) for x in os.environ.get('ROUTECHECK_ORIGIN', '128,88').split(',')]
def log(s):
    f = open(LOG, 'a'); f.write(s + '\n'); f.close()
def actor():
    try:
        import tpactions
        a = tpactions.get_current_tb_actor()
        if a and a != OBJ_HANDLE_NULL: return a
    except Exception, e:
        log('RC no tb actor %r' % (e,))
    return game.leader
def plen(crit, f, t, fl):
    try:
        import debug
        r, ln, st, pts = debug.pathlen(crit, f[0], f[1], t[0], t[1], fl)
        return '%d/%.1fft' % (r, ln)
    except Exception, e:
        return 'ERR %r' % (e,)
def start(_):
    f = PAIRS[0][1]
    game.fade_and_teleport(0, 0, 0, MAP, f[0], f[1])
    game.timeevent_add(combat, (0,), 6000, 1)
def combat(_):
    log('KEY c')
    game.timeevent_add(pair, (0,), 2500, 1)
def pair(i):
    if i >= len(PAIRS):
        log('DONE'); return
    name, f, t = PAIRS[i]
    a = actor()
    a.move(location_from_axis(f[0], f[1]))
    game.scroll_to(location_from_axis((f[0] + t[0]) / 2, (f[1] + t[1]) / 2), 0)
    game.timeevent_add(hover, (i,), 1200, 1)
def hover(i):
    import tpgui
    name, f, t = PAIRS[i]; a = actor()
    x, y = tpgui.world_to_screen(location_from_axis(t[0], t[1]))
    sx, sy = tpgui.world_to_screen(a)
    nf = 3 | 0x800000   # TO_EXACT|HAS_CRITTER|IGNORE_CRITTERS_ON_DESTINATION
    log('RC %02d %s actor %s at %s -> %s screen %d,%d actor screen %d,%d combat %d fwd %s rev %s fwd-raw %s rev-raw %s' % (
        i, name, a, location_to_axis(a.location), tuple(t), x, y, sx, sy, game.combat_is_active(),
        plen(a, f, t, nf), plen(a, t, f, nf), plen(a, f, t, 3), plen(a, t, f, 3)))
    log('XDO mousemove %d %d' % (OX + x + 4, OY + y + 3))
    log('XDO keydown alt')
    log('XDO mousemove %d %d' % (OX + x, OY + y))
    game.timeevent_add(shot, (i,), 1200, 1)
def shot(i):
    log('CSHOT rc_%02d_%s' % (i, PAIRS[i][0].replace('>', '').replace('-', '_')))
    game.timeevent_add(release, (i,), 900, 1)
def release(i):
    log('XDO keyup alt')
    game.timeevent_add(pair, (i + 1,), 400, 1)
log('route check start: %d pairs' % len(PAIRS))
game.timeevent_add(start, (0,), 500, 1)

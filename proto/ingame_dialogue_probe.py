# In-game pilot for converted IE dialogue + scripts (Temple+ Python 2.7). Developer tool; all values come from env.
#   IE2TOEE_MAP, IE2TOEE_START=x,y            map + leader start tile
#   IE2TOEE_PLACEMENT=AREA:cx,cy              ground-canvas offset of the converted area (from <AREA>_objects.json)
#   IE2TOEE_NPC=ident:proto:script_id:dx,dy   NPC to spawn near the leader with the converted script attached
#              (or ident:proto:script_id:@IEx,IEy to place at an IE coordinate)
#   IE2TOEE_AREA_SCRIPT=ident:AREA:module     area script to drive with rt.loop (optional)
#   IE2TOEE_STEPS="talk;key 1;shot name;wait 2;vars;talk;..."   test steps (2 s apart unless 'wait N')
from toee import *
from utilities import location_from_axis, location_to_axis
import os
LOG = os.environ.get('IE2TOEE_PROBE_LOG', 'ie2toee_probe.log')
def log(s):
    f = open(LOG, 'a'); f.write(s + '\n'); f.close()
import ie_runtime as rt
rt.LOG_PATH = LOG
rt.DEBUG_BLOCKS = bool(os.environ.get('IE2TOEE_DEBUG_BLOCKS'))
MAP = int(os.environ['IE2TOEE_MAP']); SX, SY = [int(v) for v in os.environ['IE2TOEE_START'].split(',')]
npcs = {}

def setup():
    try:
        pa, pc = os.environ.get('IE2TOEE_PLACEMENT', ':0,0').split(':')
        cx, cy = [int(v) for v in pc.split(',')]
        if pa:
            rt.set_placement(pa, cx, cy)
        lx, ly = location_to_axis(game.leader.location)
        log('leader at %d,%d map %d' % (lx, ly, game.leader.map))
        for spec in [s for s in os.environ.get('IE2TOEE_NPC', '').split(';') if s]:
            ident, proto, sid, pos = spec.split(':')
            if pos.startswith('@'):
                ix, iy = [int(v) for v in pos[1:].split(',')]
                u, v = rt.ie_to_tile(pa, ix, iy)
            else:
                dx, dy = [int(v) for v in pos.split(',')]; u, v = lx + dx, ly + dy
            o = game.obj_create(int(proto), location_from_axis(u, v))
            for i in range(0, 44):
                try:
                    o.scripts[i] = 0
                except Exception:
                    break
            for san in (san_dialog, san_heartbeat, san_first_heartbeat, san_dying, san_enter_combat, san_start_combat):
                o.scripts[san] = int(sid)
            area = os.environ.get('IE2TOEE_NPC_AREA', pa)
            rt.bind(o, ident, area)
            npcs[ident] = o
            log('npc %s proto %s script %s at %d,%d' % (ident, proto, sid, u, v))
        a = os.environ.get('IE2TOEE_AREA_SCRIPT')
        if a:
            ident, area, mod = a.split(':')
            m = __import__(mod)
            rt.loop(game.leader, ident, area, [m])
            log('area script %s running (%d blocks)' % (mod, len(m.BLOCKS)))
        for ident, o in npcs.items():
            if os.environ.get('IE2TOEE_TICK_NPC'):
                mods = [__import__(x) for x in os.environ['IE2TOEE_TICK_NPC'].split(',')]
                rt.loop(o, ident, rt._bound[rt._key(o)][1], mods, 1000)
                log('npc script loop %s' % ident)
    except Exception, e:
        import traceback; log('SETUP ERROR %s %s' % (e, traceback.format_exc()))
    return 0

def step(s):
    try:
        k = s.split(' ', 1); cmd = k[0]; arg = len(k) > 1 and k[1] or ''
        if cmd == 'talk':
            o = npcs[arg or npcs.keys()[0]]
            r = o.object_script_execute(game.leader, san_dialog)
            log('talk %s -> %s' % (arg, r))
        elif cmd == 'key':
            log('KEY ' + arg)
        elif cmd == 'click':
            log('CLICK ' + arg)
        elif cmd == 'shot':
            log('SHOT ' + arg)
        elif cmd == 'vars':
            for k2, i in sorted(rt.SLOTS.items()):
                v = game.global_vars[i]
                if v:
                    log('VAR %s = %d' % (k2, v))
        elif cmd == 'pos':
            for ident, o in npcs.items():
                x, y = location_to_axis(o.location)
                log('POS %s %d,%d t=%s busy=%s' % (ident, x, y, rt._now(), rt._busy.get(ident)))
        elif cmd == 'done':
            log('DONE')
    except Exception, e:
        import traceback; log('STEP ERROR %s: %s %s' % (s, e, traceback.format_exc()))
    return 0

t = [0]
def at(dt, fn, args=()):
    t[0] += dt; game.timeevent_add(fn, args, t[0], 1)
game.fade_and_teleport(0, 0, 0, MAP, SX, SY)
at(8000, setup)
for s in [x.strip() for x in os.environ.get('IE2TOEE_STEPS', '').split(';') if x.strip()]:
    if s.startswith('wait '):
        t[0] += int(float(s[5:]) * 1000); continue
    at(1500, step, (s,))
at(1500, step, ('done',))

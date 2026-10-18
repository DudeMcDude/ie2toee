# In-game pilot for converted IE creatures (Temple+ Python 2.7). Developer tool; all values come from env.
#   IE2TOEE_MAP, IE2TOEE_START=x,y        map + leader start tile
#   IE2TOEE_PLACEMENT=AREA:cx,cy          ground-canvas offset of the converted area
#   IE2TOEE_SPECS=module                  spec module written by ie_creatures.py convert (ie_creatures_<area>)
#   IE2TOEE_AREA_SCRIPT=ident:AREA:module optional area script (rt.loop)
#   IE2TOEE_STEPS="look <ident|resref>;hover;shot name;talk <ident>;key 1;stats;wait 2;..."
from toee import *
from utilities import location_from_axis, location_to_axis
import os
LOG = os.environ.get('IE2TOEE_PROBE_LOG', 'ie2toee_probe.log')
def log(s):
    f = open(LOG, 'a'); f.write(s + '\n'); f.close()
import ie_runtime as rt
import ie_critters as cr
rt.LOG_PATH = LOG
MAP = int(os.environ['IE2TOEE_MAP']); SX, SY = [int(v) for v in os.environ['IE2TOEE_START'].split(',')]
spawned = []

def find(key):
    for s, o in spawned:
        if key in (s.get('ident'), s.get('resref'), s.get('actor')):
            return s, o
    return None, None

def stats(s, o):
    g = lambda st: o.stat_level_get(st)
    log('STATS %-22s %-8s proto %5d name=%r hp %d/%d ac %d str %d dex %d con %d lvl %d bab %d F/R/W %d/%d/%d '
        'align %d kos %d scale %d items %d hp_pts %d' % (
        s.get('actor'), s.get('resref'), s['proto'], o.description, g(stat_hp_current), g(stat_hp_max), g(stat_ac),
        g(stat_strength), g(stat_dexterity), g(stat_constitution), g(stat_level),
        o.get_base_attack_bonus() if hasattr(o, 'get_base_attack_bonus') else -99,
        g(stat_save_fortitude), g(stat_save_reflexes), g(stat_save_willpower), g(stat_alignment),
        (o.npc_flags_get() & ONF_KOS) and 1 or 0, o.obj_get_int(cr._c('obj_f_model_scale')), len([i for i in range(0, 24)
                                                                                    if o.item_worn_at(i) != OBJ_HANDLE_NULL]), o.obj_get_int(cr._c('obj_f_hp_pts'))))

def setup():
    try:
        pa, pc = os.environ.get('IE2TOEE_PLACEMENT', ':0,0').split(':')
        cx, cy = [int(v) for v in pc.split(',')]
        rt.set_placement(pa, cx, cy)
        m = __import__(os.environ['IE2TOEE_SPECS'])
        for s, o in cr.spawn_area(m.CREATURES, lambda x, y: rt.ie_to_tile(pa, x, y), LOG):
            if s.get('ident'):
                rt.bind(o, s['ident'], pa)
            spawned.append((s, o))
        for s, o in spawned:
            stats(s, o)
        a = os.environ.get('IE2TOEE_AREA_SCRIPT')
        if a:
            ident, area, mod = a.split(':')
            mm = __import__(mod)
            rt.loop(game.leader, ident, area, [mm])
            log('area script %s running (%d blocks)' % (mod, len(mm.BLOCKS)))
    except Exception, e:
        import traceback; log('SETUP ERROR %s %s' % (e, traceback.format_exc()))
    return 0

def step(s):
    try:
        k = s.split(' ', 1); cmd = k[0]; arg = len(k) > 1 and k[1] or ''
        if cmd == 'look':
            sp, o = find(arg)
            if o:
                game.scroll_to(o)
                log('look %s at %s' % (arg, location_to_axis(o.location)))
            else:
                log('look %s: not spawned' % arg)
        elif cmd == 'talk':
            sp, o = find(arg)
            r = o.object_script_execute(game.leader, san_dialog)
            log('talk %s -> %s' % (arg, r))
        elif cmd == 'inv':
            sp, o = find(arg)
            log('INV %s desc_field %d worn %s found %s' % (arg, o.obj_get_int(cr._c('obj_f_description')),
                [(i, o.item_worn_at(i).proto) for i in range(16) if o.item_worn_at(i) != OBJ_HANDLE_NULL],
                [(it['proto'], o.item_find_by_proto(it['proto']) != OBJ_HANDLE_NULL) for it in sp.get('items', [])]))
        elif cmd == 'lineup':   # move one of each friendly resref next to the leader for a close-up shot
            lx, ly = location_to_axis(game.leader.location)
            seen, n = set(), 0
            for sp, o in spawned:
                if sp.get('hostility') == 'hostile' or sp['resref'] in seen:
                    continue
                seen.add(sp['resref'])
                o.move(location_from_axis(lx - 4 + (n % 6) * 2, ly - 3 - (n // 6) * 3))
                o.rotation = 2.36
                n += 1
            game.scroll_to(game.leader)
            log('lineup %d' % n)
        elif cmd == 'wear':
            for sp, o in spawned:
                cr.wear(o, sp)
        elif cmd == 'stats':
            for sp, o in spawned:
                stats(sp, o)
        elif cmd in ('key', 'click', 'move', 'shot'):
            log('%s %s' % (cmd.upper(), arg))
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

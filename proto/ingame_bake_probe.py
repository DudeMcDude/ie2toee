# In-game check of a baked map (proto/ie_bake.py; Temple+ Python 2.7). Developer tool; values come from env.
#   IE2TOEE_MAP, IE2TOEE_START=x,y, IE2TOEE_AREA      map, leader start tile, IE area (ie_bake_<area>.py)
#   IE2TOEE_STEPS="census;stats <id>;look <id>;talk <id>;key 1;door <name>;hurt <id> n;where <id>;save <slot>;
#                  load <slot>;shot name;wait 2;..."   <id>: ident / resref of a baked creature, or leader
# No objects are created: everything checked comes from the map's .mob / .sec files.
from toee import *
import toee
from utilities import location_from_axis, location_to_axis
import os
LOG = os.environ.get('IE2TOEE_PROBE_LOG', 'ie2toee_probe.log')
def log(s):
    f = open(LOG, 'a'); f.write(s + '\n'); f.close()
import ie_runtime as rt
import ie_bakert, ie_doors
rt.LOG_PATH = LOG; ie_bakert.LOG[0] = LOG
MAP = int(os.environ['IE2TOEE_MAP']); SX, SY = [int(v) for v in os.environ['IE2TOEE_START'].split(',')]
AREA = os.environ.get('IE2TOEE_AREA', 'AR1000')
BAKE = __import__('ie_bake_' + AREA.lower())
LOADED = [0]
RUN = os.environ.get('IE2TOEE_RUN', '')   # steps of an earlier run restored from its save are skipped

def find(key):
    if key == 'leader':
        return game.leader
    for g, d in BAKE.OBJS.items():
        s = d.get('spec') or {}
        if key in (s.get('ident'), s.get('resref')):
            return game.get_obj_by_id(g)
    return OBJ_HANDLE_NULL

def census():
    """Baked objects present, and how many critters / portals stand on each baked spot (duplicates show as > 1)."""
    npcs = [(g, game.get_obj_by_id(g)) for g, d in BAKE.OBJS.items() if d['k'] == 'npc']
    present = [o for g, o in npcs if o != OBJ_HANDLE_NULL]
    dup = 0; seen = {}
    for o in present:
        n = 0
        for c in game.obj_list_vicinity(o.location, OLC_NPC):
            if c.proto == o.proto and c.description == o.description and c.location == o.location:
                n = n + 1
        if n > 1:
            dup = dup + 1
    mod = __import__('ie_doors_' + AREA.lower())
    pd = []
    for d in mod.DOORS:
        x, y, ox, oy = d['loc']
        n = 0
        for p in game.obj_list_vicinity(location_from_axis(x, y), OLC_PORTAL):
            if p.location == location_from_axis(x, y):
                n = n + 1
        pd.append(n)
    allp = {}
    for d in mod.DOORS:
        for p in game.obj_list_vicinity(location_from_axis(d['loc'][0], d['loc'][1]), OLC_PORTAL):
            allp[str(p)] = 1
    log('CENSUS baked npcs present %d/%d, npc spots with duplicates %d; portals per door spot %s (max %d), '
        'distinct portals near doors %d' % (len(present), len(npcs), dup, pd, max(pd or [0]), len(allp)))

def stats(key):
    o = find(key)
    if o == OBJ_HANDLE_NULL:
        log('STATS %s: not found' % key); return
    worn = []
    for i in range(16):
        it = o.item_worn_at(i)
        if it != OBJ_HANDLE_NULL:
            worn.append('%d:%d "%s"' % (i, it.proto, it.description))
    pack = []
    for i in range(24):
        it = o.inventory_item(i)
        if it != OBJ_HANDLE_NULL:
            pack.append('%d "%s"' % (it.proto, it.description))
    ab = [o.stat_level_get(s) for s in (stat_strength, stat_dexterity, stat_constitution, stat_intelligence,
                                        stat_wisdom, stat_charisma)]
    log('STATS %s "%s" id %s proto %d at %s hp %d/%d ac %d level %d hd %d abilities %s kos %d npc_flags 0x%x '
        'scripts dlg %d hb %d worn [%s] pack [%s]' % (
        key, o.description, o.id, o.proto, location_to_axis(o.location), o.stat_level_get(stat_hp_current),
        o.stat_level_get(stat_hp_max), o.stat_level_get(stat_ac), o.stat_level_get(stat_level),
        o.hit_dice_num, ab, (o.npc_flags_get() & ONF_KOS) and 1 or 0, o.npc_flags_get(), o.scripts[san_dialog],
        o.scripts[san_heartbeat], ', '.join(worn), ', '.join(pack)))

def door_state(name=None):
    out = []
    for d, p, last in ie_doors._doors:
        if name is None or d['name'] == name:
            out.append('%s open %d blocked %d' % (d['name'], ie_doors._is_open(p) and 1 or 0, ie_doors.blocked_count(d['name'])))
    log('DOORS %s' % out)

def step(s, run=None):
    if run != RUN:
        log('STALE step from run %r skipped: %s' % (run, s)); return 0
    try:
        k = s.split(' '); cmd = k[0]; a = k[1:]
        if cmd == 'census':
            census()
        elif cmd == 'stats':
            for key in a:
                stats(key)
        elif cmd == 'look':
            game.scroll_to(find(a[0]))
        elif cmd == 'near':
            o = find(a[0]); dx, dy = [int(v) for v in a[1].split(',')]
            lx, ly = location_to_axis(game.leader.location)
            game.leader.move(location_from_axis(lx + dx, ly + dy)); game.scroll_to(game.leader)
        elif cmd == 'talk':
            o = find(a[0])
            log('talk %s -> %s' % (a[0], o.object_script_execute(game.leader, san_dialog)))
        elif cmd == 'door':           # door <name>: open / close it the way the engine does
            n = ie_doors.toggle(' '.join(a)); log('DOOR toggle %s -> %d' % (' '.join(a), n))
        elif cmd == 'doors':
            door_state(len(a) and ' '.join(a) or None)
        elif cmd == 'hurt':
            o = find(a[0]); o.damage(OBJ_HANDLE_NULL, D20DT_UNSPECIFIED, dice_new('%dd1' % int(a[1])))
            log('HURT %s %s -> hp %d' % (a[0], a[1], o.stat_level_get(stat_hp_current)))
        elif cmd == 'where':          # where <id>...: positions (patrol checks)
            try:
                gt = game.time.time_game_in_seconds(game.time)
            except Exception:
                gt = -1
            log('WHERE t=%s combat=%s %s' % (gt, game.combat_is_active(), ['%s %s' % (x, location_to_axis(find(x).location)) for x in a]))
        elif cmd == 'conds':
            o = find(a[0]); log('CONDS %s marker %x' % (a[0], o.obj_get_int(BAKE.FIELDS['npc_pad_i_3'])))
        elif cmd == 'save':
            log('SAVE %s -> %s' % (a[0], game.savegame(a[0], 'ie2toee bake test')))
        elif cmd == 'load':
            if LOADED[0]:
                log('LOAD %s skipped (already reloaded once)' % a[0]); return 0
            LOADED[0] = 1
            log('LOAD %s ...' % a[0])
            r = game.loadgame(a[0]); log('LOAD %s -> %s' % (a[0], r))
        elif cmd in ('key', 'click', 'move', 'shot'):
            log('%s %s' % (cmd.upper(), ' '.join(a)))
        elif cmd == 'done':
            log('DONE')
    except Exception, e:
        import traceback; log('STEP ERROR %s: %s %s' % (s, e, traceback.format_exc()))
    return 0

import ie_probe_stub
ie_probe_stub.HANDLER[0] = step
t = [0]
def at(dt, fn, args=()):
    t[0] += dt; game.timeevent_add(ie_probe_stub.step, args, t[0], 1)
if not os.environ.get('IE2TOEE_NO_TELEPORT'):     # (a run that autoloads a save made on the baked map stays put)
    game.fade_and_teleport(0, 0, 0, MAP, SX, SY)
t[0] = 6000
for s in [x.strip() for x in os.environ.get('IE2TOEE_STEPS', '').split(';') if x.strip()]:
    if s.startswith('wait '):
        t[0] += int(float(s[5:]) * 1000); continue
    at(1500, step, (s, RUN))
at(1500, step, ('done', RUN))

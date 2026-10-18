# In-game pilot for converted IE spells (Temple+ Python 2.7). Developer tool; all values come from env.
#   IE2TOEE_MAP, IE2TOEE_START=x,y        map + leader start tile
#   IE2TOEE_PLACEMENT=AREA:cx,cy          ground-canvas offset of the converted area
#   IE2TOEE_SPECS=module                  creature spec module (ie_creatures.py convert, with "spells"/"ai_strategy")
#   IE2TOEE_STEPS="near <id> dx,dy;cast <caster> <Action> <target> <spell>;enemy <id>;spells <id>;conds <who>;
#                  shot name;wait 2;look <id>;..."   who/target: leader | self | <ident/resref/actor>
from toee import *
import toee
from utilities import location_from_axis, location_to_axis
import os
LOG = os.environ.get('IE2TOEE_PROBE_LOG', 'ie2toee_probe.log')
def log(s):
    f = open(LOG, 'a'); f.write(s + '\n'); f.close()
import ie_runtime as rt
import ie_critters as cr
import ie_spellrt as sr
rt.LOG_PATH = LOG; sr.LOG[0] = LOG
rt.DEBUG_BLOCKS = bool(os.environ.get('IE2TOEE_DEBUG_BLOCKS'))
MAP = int(os.environ['IE2TOEE_MAP']); SX, SY = [int(v) for v in os.environ['IE2TOEE_START'].split(',')]
AREA = os.environ.get('IE2TOEE_PLACEMENT', ':0,0').split(':')[0]
spawned = []
TAKEN = set()
SPELL_CONDS = ('sp_Bless', 'sp_Hold_Person', 'sp_Prayer', 'sp_Divine_Power', 'sp_Magic_Stone', 'sp_Cure_Light_Wounds',
               'sp_Searing_Light', 'sp_Command', 'sp_Entangle', 'sp_Silence', 'sp_Shield_of_Faith')

def find(key):
    if key == 'leader':
        return {'ident': 'leader'}, game.leader
    for s, o in spawned:
        if key in (s.get('ident'), s.get('resref'), s.get('actor')):
            return s, o
    return None, None

def kos(o):
    if o.type != obj_t_npc:
        return 0
    return (o.npc_flags_get() & ONF_KOS) and 1 or 0

def conds(name, o):
    held = []
    for c in SPELL_CONDS:
        v = getattr(toee, c, None)
        if v is not None:
            try:
                if o.d20_query_has_spell_condition(v):
                    held.append(c[3:])
            except Exception:
                pass
    log('CONDS %-10s hp %d/%d kos %d spells-on %s' % (name, o.stat_level_get(stat_hp_current),
        o.stat_level_get(stat_hp_max), kos(o), held))

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
            log('SPELLS %s given %s strategy %s' % (s.get('actor'), sorted(sr._given.get(sr._okey(o), {}).items()),
                                                   bool(s.get('ai_strategy'))))
        TAKEN.update([location_to_axis(p.location) for p in game.party])
        log('PARTY %s' % [(p.description, p.stat_level_get(stat_level)) for p in game.party])
    except Exception, e:
        import traceback; log('SETUP ERROR %s %s' % (e, traceback.format_exc()))
    return 0

def step(s):
    try:
        k = s.split(' '); cmd = k[0]; a = k[1:]
        if cmd == 'look':
            sp, o = find(a[0]); game.scroll_to(o)
        elif cmd == 'near':           # near <id> dx,dy : put a creature next to the leader, facing it
            sp, o = find(a[0]); dx, dy = [int(v) for v in a[1].split(',')]
            lx, ly = location_to_axis(game.leader.location)
            p = cr.place_near(o, lx + dx, ly + dy, TAKEN)
            log('near %s -> %s' % (a[0], p)); o.turn_towards(game.leader)
            game.scroll_to(game.leader)
        elif cmd == 'cast':           # cast <caster> <IE action> <target> <spell>
            sp, me = find(a[0]); tsp, tgt = find(a[2]) if a[2] != 'self' else (sp, me)
            c = rt.ctx_for(me, game.leader, sp.get('ident'), AREA)
            spell = int(a[3]) if a[3].isdigit() else a[3]
            r = getattr(rt.A, a[1])(c, tgt, spell)
            log('cast %s %s(%s, %s) -> %s' % (a[0], a[1], a[2], a[3], r))
        elif cmd == 'enemy':          # IE Enemy(): the creature turns hostile (ToEE KOS) and its scripts react
            sp, o = find(a[0]); rt.A.Enemy(rt.ctx_for(o, None, sp.get('ident'), AREA))
            try:
                o.attack(game.leader)
            except Exception:
                pass
        elif cmd == 'talk':
            sp, o = find(a[0])
            log('talk %s -> %s' % (a[0], o.object_script_execute(game.leader, san_dialog)))
        elif cmd == 'eval':           # eval <id> <spell>: the pieces of [HaveSpell(x), See(NearestEnemyOf(Myself))]
            sp, o = find(a[0]); c = rt.ctx_for(o, None, sp.get('ident'), AREA)
            ne = rt.O(c, 'NearestEnemyOf', o)
            info = (rt.T.HaveSpell(c, int(a[1])), sr.slots(o, int(sr.entry(sr.resref(int(a[1])))['t'])), ne,
                    ne is not None and o.distance_to(ne), ne is not None and o.can_see(ne), rt.T.See(c, ne))
            log('EVAL %s HaveSpell/slots/nearest/dist/can_see/See %r' % (a[0], info))
        elif cmd == 'spells':
            sp, o = find(a[0])
            log('SPELLS %s given %s' % (a[0], sorted(sr._given.get(sr._okey(o), {}).items())))
        elif cmd == 'conds':
            for name in a:
                if name == 'party':
                    for p in game.party:
                        conds(p.description[:10], p)
                else:
                    sp, o = find(name); conds(name, o)
        elif cmd == 'heal':
            for p in game.party:
                p.heal(OBJ_HANDLE_NULL, dice_new('20d10'))
        elif cmd == 'hurt':           # hurt <who> n : damage for heal tests
            sp, o = find(a[0]); o.damage(OBJ_HANDLE_NULL, D20DT_UNSPECIFIED, dice_new('%dd1' % int(a[1])))
        elif cmd in ('key', 'click', 'move', 'shot'):
            log('%s %s' % (cmd.upper(), ' '.join(a)))
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

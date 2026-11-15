#!/usr/bin/env python3
"""Offline tests for the IWD2 script fixes (Swift Thomas' later reveal, Phaen, spawned townsfolk):
    python3 test_scripts.py        (IWD2_DIR=<install> for the data checks; they are skipped without it)
  1. ieformats.Are: the IWD2 ARE actor 'area' script slot (0x90) and <AREA>.BCS as the default area script;
     ie_creatures.actor_scripts puts the slot right after override (GemRB order)
  2. ie_bake.start_hidden ignores the 'area' slot (the AR1200 goblins left visible and Shawford stay as they were)
  3. runtime: ChangeCurrentScript(""), HideCreature on a missing named target, IWD2 CreateCreature(res, name, pt,
     face), NearestPC, AnyPCOnMap, town faction for spawned creatures (same rule as ie_bake.factions)
  4. with the IWD2 data: the converted 1000THMV unhides Swift Thomas only after Jump_Check; 12PHASPN shows Phaen once
     AR1200.BCS has set up the battle (1200_BATTLE_SETUP, PHAEN_SPAWN_TIMER)"""
import os, sys, json, shutil, subprocess, tempfile, types
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, 'runtime')]
IE = os.environ.get('IWD2_DIR', '/workspace/iwd2-data')
HAVE_IE = any(os.path.exists(os.path.join(IE, k)) for k in ('CHITIN.KEY', 'chitin.key'))

fails = []
def check(name, cond):
    print(('PASS ' if cond else 'FAIL ') + name)
    if not cond: fails.append(name)

# ---- 1. ARE 'area' slot, script order -----------------------------------------------------------------------------
import ie_creatures
order, area = ie_creatures.actor_scripts(
    {'override': '', 'general': '10THOMF0', 'class': '', 'race': '00AFLN00', 'default': '00AMVW05',
     'specific': '00TOWNI', 'area': '1000THMV'}, {})
check('area slot right after override (GemRB SCR_AREA)', order == ['1000thmv', '00towni', '00afln00', '10thomf0', '00amvw05'])
check('area slot reported', area == '1000thmv')
order, area = ie_creatures.actor_scripts({k: '' for k in ie_creatures.SCRIPT_ORDER}, {'override': 'X', 'class': 'None'})
check('empty ARE slots: the CRE scripts', order == ['x'] and area is None)

if HAVE_IE:
    import iefs, ieformats
    g = iefs.IEGame(IE)
    are = lambda a: ieformats.Are(g.read(a, 'are'))
    a1000, a1200 = are('ar1000'), are('ar1200')
    th = [x for x in a1000.actors if x['cre'].upper() == '12SWIFTH']
    check('AR1000 Swift Thomas (Hidden): area slot 1000THMV', th and th[0]['scripts'].get('area') == '1000THMV')
    ph = [x for x in a1200.actors if x['cre'].upper() == '12PHAEN']
    check('AR1200 Phaen: area slot 12PHASPN', ph and ph[0]['scripts'].get('area') == '12PHASPN')
    check('AR1200 names no area script, AR1200.BCS is the default',
          a1200.script == '' and a1200.script_or_default('AR1200', lambda n: g.exists(n, 'bcs')) == 'AR1200')
    check('AR1000 keeps its header script', a1000.script_or_default('AR1000', lambda n: True) == 'AR1000')
else:
    print('SKIP ARE checks (no IWD2 install at %s; set IWD2_DIR)' % IE)

# ---- 2. start_hidden heuristic without the area slot ----------------------------------------------------------------
if HAVE_IE:
    import ie_bake
    tmp = tempfile.mkdtemp(prefix='test_scripts_', dir=HERE)
    try:
        json.dump({'creatures': [
            {'actor': '01_Goblin_01', 'scripts': ['12atkuhp', '00t01t', '1200atng'], 'area_script': '12atkuhp'},
            {'actor': '03_Vghotan', 'scripts': ['12atkuhp', '00t03t'], 'area_script': '00t03t'},
            {'actor': '08_Phaen', 'scripts': ['12phaspn', '00t08t', '12phaen0'], 'area_script': '12phaspn'},
            {'actor': 'Shawford_Crale', 'scripts': ['12shawf0'], 'area_script': '12shawf0'}]},
            open(os.path.join(tmp, 'AR1200_creatures.json'), 'w'))
        B = ie_bake.Baker.__new__(ie_bake.Baker)
        B.a = types.SimpleNamespace(ie=IE, specs=os.path.join(tmp, 'ie_creatures_ar1200.py')); B.area = 'AR1200'
        hid = B.start_hidden()
        check('goblin with 12ATKUHP only in the area slot: not hidden by the heuristic', '01_goblin_01' not in hid)
        check('Vghotan (12ATKUHP as override) still hidden', '03_vghotan' in hid)
        check('Shawford (12SHAWF0 area slot) not hidden', 'shawford_crale' not in hid)
        check('Phaen: left to the CRE hidden flag', '08_phaen' not in hid)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    import iecre
    c = iecre.Cre(g.read('12phaen', 'cre'), '12phaen')
    check('12PHAEN: CRE hidden flag, neutral -> spec hidden (no START_HIDDEN_KEEP)',
          c.start_hidden and '12phaen' not in ie_creatures.START_HIDDEN_KEEP)

# ---- 3. runtime ---------------------------------------------------------------------------------------------------
for m in ('ie_itemrt', 'ie_bakert', 'ie_cutscene', 'ie_spellrt', 'ie_combat'):
    sys.modules[m] = None
import ie_runtime as rt
LOG = []
rt.log = lambda msg: LOG.append(msg)
OFF, KOS = 0x10, 0x1

class Obj(object):
    def __init__(self, name, hidden=False, kos=False, factions=()):
        self.name, self.oflags, self.nflags, self.type, self.facs = name, OFF if hidden else 0, KOS if kos else 0, 14, list(factions)
        self.id = name; self.map = 5040; self.attacked = None
    def object_flags_get(self): return self.oflags
    def object_flag_set(self, f): self.oflags |= f
    def object_flag_unset(self, f): self.oflags &= ~f
    def npc_flags_get(self): return self.nflags
    def npc_flag_set(self, f): self.nflags |= f
    def leader_get(self): return None
    def attack(self, o): self.attacked = o
    def turn_towards(self, o): pass
    def distance_to(self, o): return 5
    @property
    def factions(self):
        out = []
        for f in self.facs:
            if not f: break
            out.append(f)
        return tuple(out)
    def obj_set_idx_int(self, field, i, v):
        while len(self.facs) <= i: self.facs.append(0)
        self.facs[i] = v
    def __repr__(self): return self.name

class Game(object):
    party, leader = [], None
    def combat_is_active(self): return False
    def get_obj_by_id(self, k): return OBJS.get(k)

pc = Obj('pc'); Game.party = [pc]; Game.leader = pc
OBJS = {}
rt.IN_GAME, rt.game, rt.OBJ_HANDLE_NULL, rt.ONF_KOS, rt.obj_t_npc, rt.OF_OFF = True, Game(), None, KOS, 14, OFF
rt.SLOTS = {}
rt.AREA_MAPS = {'AR1000': 5031, 'AR1200': 5040}
A, T = rt.A, rt.T

def mod(name, blocks):
    m = types.ModuleType(name); m.BLOCKS = blocks; return m

# ChangeCurrentScript(""): the block fires once, later scripts run from the next round on
ran = []
m1 = mod('ie_bcs_t_drop', [(lambda c: True, [(100, [lambda c: A.ChangeCurrentScript(c, '')])])])
m2 = mod('ie_bcs_t_ai', [(lambda c: True, [(100, [lambda c: ran.append(1)])])])
gob = Obj('gob'); OBJS['gob'] = gob
rt.tick(gob, 'gob', 'AR1200', [m1, m2], force=True)
check('ChangeCurrentScript round: later scripts wait', ran == [])
rt.tick(gob, 'gob', 'AR1200', [m1, m2], force=True)
check('ChangeCurrentScript(""): script dropped, the next one runs', ran == [1])

# HideCreature: a named target that is not there must not hide the caller (area scripts: the party leader)
c = rt.Ctx(pc, None, 'area_AR1200', 'AR1200', {})
A.HideCreature(c, rt.N(c, 'DEAD_BODY_00'), 1)
check('HideCreature(missing name) leaves the leader visible', not pc.oflags & OFF)
me = Obj('me'); A.HideCreature(rt.Ctx(me, None, 'me', 'AR1200', {}), me, 1)
check('HideCreature(Myself, TRUE) still hides', me.oflags & OFF)

# IWD2 CreateCreature(res, scriptname, point, face) / IWD CreateCreature(res, point, face)
calls = []
sys.modules['ie_spawn'] = types.SimpleNamespace(create=lambda *a: calls.append(a[1:]))
A.CreateCreature(c, '12GOBD', 'DEAD_BODY_00', (2200, 2159), 14)
A.CreateCreature(c, 'IEWOLF', (10, 20), 3)
check('IWD2 CreateCreature: name, point, face', calls[0] == ('12GOBD', (2200, 2159), 14, 'DEAD_BODY_00'))
check('IWD CreateCreature: point, face', calls[1] == ('IEWOLF', (10, 20), 3, None))

check('NearestPC -> a party member', rt.O(rt.Ctx(me, None, 'me', 'AR1200', {}), 'NearestPC') is pc)
pc.map = 5040
check('AnyPCOnMap on the party map', T.AnyPCOnMap(rt.Ctx(me, None, 'me', 'AR1200', {})))
check('AnyPCOnMap: not on another area', not T.AnyPCOnMap(rt.Ctx(me, None, 'me', 'AR1000', {})))

# town faction for runtime spawns == ie_bake.factions for baked actors
F = rt.IE_TOWN_FACTION
town = Obj('townie', factions=[9, 12, 0])
check('spawned townsman (9 12) -> town faction', rt.set_town_faction(town, 'neutral') == [F] and town.factions == (F,))
gobs = Obj('gobs', factions=[0])
check('spawned goblin (factionless) stays factionless', rt.set_town_faction(gobs, 'hostile') is None and gobs.factions == ())
keg = Obj('keg', factions=[])
check('spawned keg/rat (factionless neutral) stays factionless', rt.set_town_faction(keg, 'neutral') is None and keg.factions == ())
hos = Obj('hos', factions=[9, 12, 0])
check('spawned hostile keeps proto factions', rt.set_town_faction(hos, 'hostile') is None and hos.factions == (9, 12))
import ie_bake
B = ie_bake.Baker.__new__(ie_bake.Baker)
row = lambda fac: [''] * 154 + [fac] + [''] * 179
cases = {14000: '9 12', 14186: '', 14056: '34', 99: '%d 7' % F}
B.protos = dict((k, row(v)) for k, v in cases.items())
same = all(B.factions({'proto': k, 'hostility': h}) == rt.town_factions([int(x) for x in v.split()], h)
           for k, v in cases.items() for h in ('hostile', 'neutral', 'friendly'))
check('runtime town_factions == ie_bake.factions', same and rt.IE_TOWN_FACTION == ie_bake.IE_TOWN_FACTION)

# ---- 4. converted IWD2 scripts --------------------------------------------------------------------------------------
if HAVE_IE:
    out = tempfile.mkdtemp(prefix='test_scripts_dlg_', dir=HERE)
    try:
        r = subprocess.run([sys.executable, os.path.join(HERE, 'ie_dialogue.py'), IE, out, '--strip-directions',
                            '--actor', '12swifth:AR1000:1551::1000thmv,10thomf0',
                            '--actor', '12phaen:AR1200:2395::12phaspn,12phaen0',
                            '--area-script', 'AR1200:ar1200'], capture_output=True, text=True)
        scr = os.path.join(out, 'modules', 'ToEE', 'scr')
        check('ie_dialogue converts 1000THMV / 12PHASPN / AR1200.BCS', r.returncode == 0 and
              all(os.path.exists(os.path.join(scr, f)) for f in ('ie_bcs_1000thmv.py', 'ie_bcs_12phaspn.py', 'ie_bcs_ar1200_area.py')))
        sys.path.append(scr)
        import ie_bcs_1000thmv, ie_bcs_10thomf0, ie_bcs_12phaspn, ie_bcs_12phaen0, ie_bcs_ar1200_area
        rt._mem.clear()
        thomas = Obj('12swifth', hidden=True); OBJS['12swifth'] = thomas
        S = [ie_bcs_1000thmv, ie_bcs_10thomf0]
        rt.tick(thomas, '12swifth', 'AR1000', S, force=True)
        check('Thomas stays hidden while Jump_Check = 0', thomas.oflags & OFF)
        rt.set_var(None, 'Jump_Check', 'GLOBAL', 1)
        rt.tick(thomas, '12swifth', 'AR1000', S, force=True)
        check('1000THMV shows Thomas once Jump_Check > 0', not thomas.oflags & OFF)
        # Phaen: hidden until AR1200.BCS sets up the battle (after Goblins_Attack_Palisade) and its timer runs out
        phaen = Obj('12phaen', hidden=True); OBJS['12phaen'] = phaen
        P = [ie_bcs_12phaspn, ie_bcs_12phaen0]
        rt.tick(phaen, '12phaen', 'AR1200', P, force=True)
        check('Phaen hidden before the palisade attack', phaen.oflags & OFF)
        check('Phaen (EA neutral) turns Enemy while hidden, no attack yet', phaen.nflags & KOS and phaen.attacked is None)
        rt.set_var(None, 'Goblins_Attack_Palisade', 'GLOBAL', 1)
        area = rt.Ctx(pc, None, 'area_AR1200', 'AR1200', {})
        rt.run_script(area, ie_bcs_ar1200_area.BLOCKS)
        # (offline no goblin is bound, so Dead() is true and the team states go straight on to 2)
        check('AR1200.BCS battle setup: 1200_BATTLE_SETUP and GOBLIN_TEAM_8_STATE set',
              rt.get_var(area, '1200_BATTLE_SETUP', 'GLOBAL') in (1, 2) and rt.get_var(area, 'GOBLIN_TEAM_8_STATE', 'MYAREA') >= 1)
        check('battle setup never hides the leader', not pc.oflags & OFF)
        rt.set_var(area, 'PHAEN_SPAWN_TIMER', 'MYAREA', 0)        # (the 5 s timer ran out)
        rt.tick(phaen, '12phaen', 'AR1200', P, force=True)
        check('12PHASPN shows Phaen after the battle setup', not phaen.oflags & OFF and
              rt.get_var(rt.Ctx(phaen, None, '12phaen', 'AR1200', {}), 'TEAM_8', 'MYAREA') == 1)
    finally:
        shutil.rmtree(out, ignore_errors=True)
else:
    print('SKIP converted-script checks (no IWD2 install)')

print('%d failed' % len(fails) if fails else 'all passed')
sys.exit(1 if fails else 0)

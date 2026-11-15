#!/usr/bin/env python3
"""Offline test of the save-backed IE variable store (runtime/ie_vars.py; no IE data or game needed):
    python3 test_varstore.py          (IE_OUT=<converted build> also checks every variable the converter found)
Checks: keys 'GLOBAL:x' / '<AREA>:x' / 'LOCALS:<ident>:x' (empty-scope "LOCALS:x" names too); a save writes
<save>.iev next to the save archive and a load restores it exactly (timers as absolute stamps); load clears first;
a new game (token var 0) or a save without .iev starts empty; Temple+ savehook chaining keeps the previous
(e.g. Co8) functions; thousands of variables (IWD2 Targos: 1,218) all round-trip; the file is plain JSON."""
import os, sys, types, json, tempfile, shutil, glob
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, 'runtime')]
for n_ in ('ie_itemrt', 'ie_bakert'):
    sys.modules.setdefault(n_, types.ModuleType(n_))
import ie_runtime as rt, ie_vars
from ie_runtime import T, A

fails = []
def check(name, ok):
    print('%s %s' % ('PASS' if ok else 'FAIL', name))
    if not ok:
        fails.append(name)

# a fake Temple+: game.global_vars (saved with the game) and templeplus.savehook with Co8-style previous hooks
class Game(object):
    def __init__(self): self.global_vars = [0] * 2000
game = Game()
toee = types.ModuleType('toee'); toee.game = game; sys.modules['toee'] = toee     # (after ie_runtime: stays offline)
calls = []
tp = types.ModuleType('templeplus'); sh = types.ModuleType('templeplus.savehook')
sh.load = lambda f: calls.append(('co8 load', f)); sh.post_save = lambda f: calls.append(('co8 post_save', f))
tp.savehook = sh; sys.modules['templeplus'] = tp; sys.modules['templeplus.savehook'] = sh

tmp = tempfile.mkdtemp(prefix='iev_'); cwd = os.getcwd(); os.chdir(tmp)
try:
    sd = os.path.join('modules', 'ToEE', 'save'); os.makedirs(sd)
    def engine_save(name):        # what Temple+ SaveGame leaves: the archive (+ global_vars inside it), then post_save
        open(os.path.join(sd, name + '.tfai'), 'w').close()
        saved[name] = list(game.global_vars)
        sh.post_save(name)
    def engine_load(name):        # LoadGame: game state (global_vars) first, then savehook.load
        game.global_vars[:] = saved.get(name, [0] * 2000)
        sh.load(name)
    saved = {}

    check('hooks install (chained)', ie_vars.install_hooks() and sh._ie_vars_hooked)
    check('install_hooks is idempotent', ie_vars.install_hooks())
    c = rt.Ctx(None, ident='10gob_19', area='AR1200')
    check('keys: GLOBAL / area / LOCALS / MYAREA / empty-scope LOCALS:x / spaces', (
        rt.var_key(c, 'Join_Posse', 'GLOBAL'), rt.var_key(c, 'X', 'ar1200'), rt.var_key(c, '#Timer18', 'LOCALS'),
        rt.var_key(c, 'Goblin_Team_1_State', 'MYAREA'), rt.var_key(c, 'LOCALS:Creature_State_Var', ''),
        rt.var_key(c, 'Apsel _Quest', 'GLOBAL')) == ('GLOBAL:join_posse', 'AR1200:x', 'LOCALS:10gob_19:#timer18',
        'AR1200:goblin_team_1_state', 'LOCALS:10gob_19:creature_state_var', 'GLOBAL:apsel_quest'))

    # new game: token var 0 -> empty store, fresh token
    rt.VARS['GLOBAL:stale'] = 7
    check('new game: a stale store is dropped on first use', rt.get_var(c, 'stale', 'GLOBAL') == 0 and not rt.VARS)
    tok = game.global_vars[ie_vars.TOKEN_VAR]
    check('new game: a token is written to global_vars[992]', tok != 0)
    A.SetGlobal(c, 'Join_Posse', 'GLOBAL', 1)
    A.SetGlobal(c, 'Goblin_Team_1_State', 'MYAREA', 3)
    A.StartTimer(c, 18, 30)                                       # goblin/keg style LOCALS timer
    A.SetGlobalTimer(c, 'Keg_Timer', 'AR1200', 600)
    t18, keg = rt.VARS['LOCALS:10gob_19:#timer18'], rt.VARS['AR1200:keg_timer']
    A.BitGlobal(c, 'Bits', 'GLOBAL', 4, 2)                         # OR
    A.BitGlobal(c, 'Bits', 'GLOBAL', 1, 2)
    big = dict(('GLOBAL:v%04d' % i, i + 1) for i in range(2500))
    big.update(dict(('LOCALS:npc%03d:#timer%d' % (i % 300, i % 7), 10 ** 9 + i) for i in range(1500)))
    for k, v in big.items():
        ie_vars.put(k, v)
    real = []
    out = os.environ.get('IE_OUT')
    if out:   # every variable the IWD2 converter collected (report.json 'var_keys'), when given a build
        for rp in glob.glob(os.path.join(out, '**', 'report.json'), recursive=True):
            try:
                real += json.load(open(rp)).get('var_keys', [])
            except Exception:
                pass
        for i, k in enumerate(real):
            ie_vars.put(k, 100000 + i)
    before = dict(rt.VARS)
    engine_save('Slot0001')
    f = os.path.join(sd, 'Slot0001.iev')
    check('save writes <save>.iev next to the archive', os.path.isfile(f))
    d = json.load(open(f))
    check('file is plain JSON: {version, token, vars: {str: int}}', d['version'] == 1 and d['token'] == tok and
          all(isinstance(k, str) and isinstance(v, int) for k, v in d['vars'].items()))
    check('previous (Co8) post_save still called', ('co8 post_save', 'Slot0001') in calls)

    A.SetGlobal(c, 'Join_Posse', 'GLOBAL', 5); A.SetGlobal(c, 'After_Save', 'GLOBAL', 1)
    engine_load('Slot0001')
    check('load restores every variable exactly (%d vars)' % len(before), dict(rt.VARS) == before)
    check('%d+ variables persisted (synthetic 4000%s)' % (len(before), ', IWD2 build %d' % len(real) if real else ''),
          len(before) >= 4000 and (not real or all(k in rt.VARS for k in real)))
    check('load clears first: a var set after the save is gone', rt.get_var(c, 'After_Save', 'GLOBAL') == 0)
    check('GLOBAL Join_Posse back to 1', T.Global(c, 'Join_Posse', 'GLOBAL', 1))
    check('timers are absolute stamps, unchanged', rt.VARS['LOCALS:10gob_19:#timer18'] == t18 and rt.VARS['AR1200:keg_timer'] == keg)
    check('BitGlobal mode 2 = OR', T.Global(c, 'Bits', 'GLOBAL', 5))
    check('previous (Co8) load still called', ('co8 load', 'Slot0001') in calls)

    # a second game in the same session: new game -> nothing leaks
    game.global_vars[:] = [0] * 2000
    check('new game after a load: empty', rt.get_var(c, 'Join_Posse', 'GLOBAL') == 0 and len(rt.VARS) == 0)
    A.SetGlobal(c, 'Other_Game', 'GLOBAL', 1); engine_save('Slot0002')
    engine_load('Slot0001')
    check('reload Slot0001: its vars, not the other game', T.Global(c, 'Join_Posse', 'GLOBAL', 1) and
          rt.get_var(c, 'Other_Game', 'GLOBAL') == 0)
    engine_load('Slot0002')
    check('reload Slot0002: the other game', rt.get_var(c, 'Other_Game', 'GLOBAL') == 1 and rt.get_var(c, 'Join_Posse', 'GLOBAL') == 0)
    # a save made without the hook (no .iev): starts empty instead of keeping the previous game's dict
    game.global_vars[ie_vars.TOKEN_VAR] = 12345; open(os.path.join(sd, 'Slot0003.tfai'), 'w').close()
    saved['Slot0003'] = list(game.global_vars)
    engine_load('Slot0003')
    check('save without .iev: empty store', rt.get_var(c, 'Other_Game', 'GLOBAL') == 0)
    # a .iev whose token does not match the save (copied from another save): ignored
    shutil.copy(os.path.join(sd, 'Slot0001.iev'), os.path.join(sd, 'Slot0003.iev'))
    engine_load('Slot0003')
    check('mismatched .iev token: ignored', rt.get_var(c, 'Join_Posse', 'GLOBAL') == 0)
    check('setting 0 removes the key (small files)', (A.SetGlobal(c, 'Z', 'GLOBAL', 3), A.SetGlobal(c, 'Z', 'GLOBAL', 0),
          'GLOBAL:z' not in rt.VARS)[-1])
    check('engine flags stay in global_vars only (990/991 untouched)', game.global_vars[990] == 0 and game.global_vars[991] == 0)
finally:
    os.chdir(cwd); shutil.rmtree(tmp, ignore_errors=True)

print('%d failed' % len(fails) if fails else 'all passed')
sys.exit(1 if fails else 0)

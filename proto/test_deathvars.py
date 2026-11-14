#!/usr/bin/env python3
"""Offline test of the IE death variables (no IE data, no game needed):   python3 test_deathvars.py
A dying converted creature must set what the IE engine sets (GemRB Actor::Die): GLOBAL SPRITE_IS_DEAD<script name>
+= 1 (IWD; IWD2 _DEAD<name>), the script name being the ARE actor name. Apsel's wolf quest (IWD AR1000 DAPSEL state
110) tests Global("SPRITE_IS_DEADEHWolf","GLOBAL",1); Grisella's beetles (AR1015, four actors "EHBEETLE") test
GlobalGT("SPRITE_IS_DEADEHBEETLE","GLOBAL",3)."""
import os, sys, types
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, 'runtime')]
for n_ in ('ie_itemrt', 'ie_bakert'):                                    # (py2-only modules, not needed here)
    sys.modules.setdefault(n_, types.ModuleType(n_))
sys.modules['ie_bakert'].first_heartbeat = lambda o, area: None
m = types.ModuleType('ie_creatures_ar1015')                              # converted area actors: ident -> ARE name
m.CREATURES = [{'actor': 'EHBEETLE', 'ident': 'ehbeetle'}] + [{'actor': 'EHBEETLE', 'ident': 'ehbeetle_%d' % i}
                                                               for i in (1, 2, 3)]
sys.modules['ie_creatures_ar1015'] = m
m = types.ModuleType('ie_creatures_ar1000')
m.CREATURES = [{'actor': 'Goblin Archer 1', 'ident': 'goblinarcher1'}, {'actor': 'Townsperson', 'ident': 'townsperson_8'}]
sys.modules['ie_creatures_ar1000'] = m
import ie_runtime as rt
from ie_runtime import T

fails = []
def check(name, ok):
    print('%s %s' % ('PASS' if ok else 'FAIL', name))
    if not ok:
        fails.append(name)

c = rt.Ctx(None, ident='scrimshander', area='AR1000')
check('wolf alive: Apsel state 100 (wolf still there)', T.Global(c, 'SPRITE_IS_DEADEHWolf', 'GLOBAL', 0))
rt.bind(object(), 'ehwolf', 'AR1010')            # (no ie_creatures_ar1010 here: the ident is the script name)
rt.event('ehwolf', 'Die')
check('wolf dead: Apsel state 110 (SPRITE_IS_DEADEHWolf = 1)', T.Global(c, 'SPRITE_IS_DEADEHWolf', 'GLOBAL', 1))
check('wolf dead: EHWolf_DEAD = 1', T.Global(c, 'EHWolf_DEAD', 'GLOBAL', 1))

for i, idt in enumerate(['ehbeetle', 'ehbeetle_1', 'ehbeetle_2', 'ehbeetle_3']):
    rt.bind(object(), idt, 'AR1015')
    if i == 3:
        check('3 beetles: not GlobalGT(SPRITE_IS_DEADEHBEETLE, 3)', not T.GlobalGT(c, 'SPRITE_IS_DEADEHBEETLE', 'GLOBAL', 3))
    rt.event(idt, 'Die')
check('4 beetles (idents ehbeetle, ehbeetle_1..3): GlobalGT(SPRITE_IS_DEADEHBEETLE, 3)',
      T.GlobalGT(c, 'SPRITE_IS_DEADEHBEETLE', 'GLOBAL', 3))

rt.bind(object(), 'goblinarcher1', 'AR1000')
rt.event('goblinarcher1', 'Die')
check('ARE actor name with spaces: SPRITE_IS_DEAD"Goblin Archer 1"', T.Global(c, 'SPRITE_IS_DEADGoblinArcher1', 'GLOBAL', 1))
check('script name: ident -> ARE actor name', rt.script_name('townsperson_8', 'AR1000') == 'Townsperson')
check('script name: spawn copy veira#2 -> veira', rt.script_name('veira#2') == 'veira')

rt.death_vars('Pomab'); rt.death_vars('Pomab')
check('death_vars counts (IE increments SPRITE_IS_DEAD)', T.Global(c, 'SPRITE_IS_DEADPomab', 'GLOBAL', 2))
rt.SLOTS['global:_deadhedron'] = 1     # an IWD2 dialogue reads _DEAD<name>
rt.death_vars('Hedron')
check('IWD2 _DEAD<name> when a converted script reads it', rt._mem.get('global:_deadhedron') == 1)
rt.death_vars('None'); rt.death_vars('')
check('no script name: nothing set', 'global:sprite_is_deadnone' not in rt._mem)

import ie_bake
src = ie_bake.GENERIC_SCRIPT % {'area': 'AR1015'}
compile(src, 'generic', 'exec')
check('baked critters without IE scripts get san_dying (generic script)', 'def san_dying' in src
      and 'ie_bakert.died' in src)

print('\nall passed' if not fails else '\n%d FAILED' % len(fails))
sys.exit(1 if fails else 0)

#!/usr/bin/env python3
"""Offline tests for the Targos townsfolk fixes (no IE data or game needed):   python3 test_hostility.py
  1. runtime AttackedBy/HitBy honour the IE object filter: a townsman fighting goblins is not "attacked by
     [GOODCUTOFF]" (00T02ET / 00TOWNI would make him Enemy() and attack the party)
  2. ie_bake.factions: non-hostile actors share IE_TOWN_FACTION, hostile ones never get it, factionless stay so
  3. iecre: IWD2 CRE byte 0x29c -> start_hidden, ie_bake bakes such an actor OF_OFF (with the IWD2 data if present:
     12SWIFTH vs 12SWIFT)"""
import os, sys, types
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, 'runtime')]

fails = []
def check(name, cond):
    print(('PASS ' if cond else 'FAIL ') + name)
    if not cond: fails.append(name)

# ---- 1. runtime triggers against a mock Temple+ -----------------------------------------------------------------
sys.modules['ie_itemrt'] = None       # (Python 2 only: the runtime falls back to item protos)
import ie_runtime as rt
KOS, WHO = 0x1, 9001

class Obj(object):
    def __init__(self, name, kos=False, leader=None):
        self.name, self.flags, self.leader, self.hit_by, self.type = name, KOS if kos else 0, leader, None, 14
    def npc_flags_get(self): return self.flags
    def npc_flag_set(self, f): self.flags |= f
    def object_flags_get(self): return 0
    def leader_get(self): return self.leader
    def obj_get_obj(self, f): return self.hit_by if f == WHO else None
    def attack(self, o): self.attacked = o
    def __repr__(self): return self.name

class Game(object):
    party = []
    leader = None

pc1, pc2 = Obj('pc1'), Obj('pc2')
Game.party = [pc1, pc2]; Game.leader = pc1
rt.IN_GAME, rt.game, rt.OBJ_HANDLE_NULL, rt.ONF_KOS, rt.obj_t_npc, rt.OF_OFF = True, Game(), None, KOS, 14, 0x10
rt.obj_f_npc_who_hit_me_last = WHO
T = rt.T
reig, gob = Obj('reig'), Obj('goblin', kos=True)

def ctx(me, ev):
    return rt.Ctx(me, None, me.name, 'AR1000', dict(ev))

# san_start_combat records the critter itself, san_enter_combat its own target: neither is an attack by the party
check('townsman: start_combat event is not AttackedBy([GOODCUTOFF])',
      not T.AttackedBy(ctx(reig, {'AttackedBy': reig}), pc1, 0))
check('townsman: enter_combat vs a goblin is not AttackedBy([GOODCUTOFF])',
      not T.AttackedBy(ctx(reig, {'AttackedBy': gob}), pc1, 0))
reig.hit_by = gob
check('townsman hit by a goblin: not AttackedBy([GOODCUTOFF])', not T.AttackedBy(ctx(reig, {'AttackedBy': reig}), pc1, 0))
check('townsman hit by a goblin: HitBy(goblin side)', T.HitBy(ctx(reig, {'HitBy': gob}), gob, 0))
reig.hit_by = pc2
check('townsman hit by a party member: AttackedBy([GOODCUTOFF]) (party = side of Player1)',
      T.AttackedBy(ctx(reig, {'AttackedBy': reig}), pc1, 0))
summon = Obj('summon', leader=pc1); reig.hit_by = summon
check('townsman hit by a party summon: AttackedBy([GOODCUTOFF])', T.AttackedBy(ctx(reig, {'AttackedBy': reig}), pc1, 0))
check('KOS goblin, attacker unknown: AttackedBy([GOODCUTOFF]) as before', T.AttackedBy(ctx(gob, {'AttackedBy': gob}), pc1, 0))
check('no event: False', not T.AttackedBy(ctx(gob, {}), pc1, 0))
check('no filter (obj None): any attack', T.AttackedBy(ctx(reig, {'AttackedBy': gob}), None, 0))
c = ctx(reig, {'AttackedBy': reig}); reig.hit_by = None
T.AttackedBy(c, pc1, 0)
check('unmatched event stays for another block', 'AttackedBy' in c.events)
# the generated 00T02ET round: no TEAM_2 / Enemy() for a townsman that only fights goblins
reig.hit_by = gob
rt.VARS.clear()
c = ctx(reig, {'AttackedBy': reig})
if T.AttackedBy(c, pc1, 0) and not T.Global(c, 'TEAM_2', 'MYAREA', 1):
    rt.A.SetGlobal(c, 'TEAM_2', 'MYAREA', 1)
if not T.Allegiance(c, reig, 255) and not T.Global(c, 'TEAM_2', 'MYAREA', 0):
    rt.A.Enemy(c)
check('00T02ET round: townsman fighting goblins stays non-hostile', not reig.flags & KOS)

# ---- 2. bake factions ---------------------------------------------------------------------------------------------
import ie_bake
B = ie_bake.Baker.__new__(ie_bake.Baker)
row = lambda fac: [''] * 154 + [fac] + [''] * 179
B.protos = {14000: row('9 12'), 14186: row(''), 14056: row('34'), 99: row('%d 7' % ie_bake.IE_TOWN_FACTION)}
F = ie_bake.IE_TOWN_FACTION
check('townsman (proto 9 12) -> town faction', B.factions({'proto': 14000, 'hostility': 'neutral'}) == [F])
check('town cat (proto 34) -> town faction', B.factions({'proto': 14056, 'hostility': 'neutral'}) == [F])
check('goblin (factionless) keeps the proto (none)', B.factions({'proto': 14186, 'hostility': 'hostile'}) is None)
check('factionless neutral (keg) keeps the proto (none)', B.factions({'proto': 14186, 'hostility': 'neutral'}) is None)
check('hostile never gets the town faction', B.factions({'proto': 99, 'hostility': 'hostile'}) == [7])
check('foreign-mesh proto missing from protos.tab: keep', B.factions({'proto': 14199, 'hostility': 'neutral'}) is None)

# ---- 3. start hidden -------------------------------------------------------------------------------------------------
ie = os.environ.get('IWD2_DIR', '/workspace/iwd2-data')
if os.path.exists(os.path.join(ie, 'CHITIN.KEY')) or os.path.exists(os.path.join(ie, 'chitin.key')):
    import iefs, iecre
    g = iefs.IEGame(ie)
    check('12SWIFTH starts hidden', iecre.Cre(g.read('12swifth', 'cre'), '12swifth').start_hidden)
    check('12SWIFT does not', not iecre.Cre(g.read('12swift', 'cre'), '12swift').start_hidden)
    check('10REIG does not', not iecre.Cre(g.read('10reig', 'cre'), '10reig').start_hidden)
    toee = os.environ.get('TOEE_DIR')
    if toee:
        import ie_creatures, ieformats, toeedata
        cv = ie_creatures.Converter(g, ie_creatures.ToEEIndex(toeedata.ToEEData(toee)))
        actors = ieformats.Are(g.read('AR1200', 'are')).actors
        siege = []
        for actor in actors:
            cre = iecre.Cre(actor['embedded_cre'] or g.read(actor['cre'], 'cre'), actor['cre'])
            spec = cv.convert(cre, actor)
            if spec.get('hostility') == 'hostile' and cre.start_hidden:
                siege.append(bool(spec.get('hidden')))
        check('AR1200 conversion preserves all 57 source-hidden siege hostiles', len(siege) == 57 and all(siege))
    else:
        print('SKIP palisade conversion (set TOEE_DIR to the destination game)')
else:
    print('SKIP CRE checks (no IWD2 install at %s; set IWD2_DIR)' % ie)

print('%d failed' % len(fails) if fails else 'all passed')
sys.exit(1 if fails else 0)

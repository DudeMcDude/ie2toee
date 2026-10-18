# ie2toee: per-round IE combat layer for Temple+ (Python 2.7). Generated actor scripts call round_start() from
# san_start_combat, which ToEE fires at the start of every NPC turn, before its AI acts.
#
# Design after Anatoliy Savchak's ToEE module framework (github.com/anatoliy-savchak/toee.zmod.forge, scr/):
#   ctrl_behaviour.CtrlBehaviourAI.start_combat   skip turns the critter cannot act in, recon, build one round of
#                                                 tactics, ai_strategy_set_custom(..., 0), RUN_DEFAULT
#   utils_npc_spells.NPCSpells                    the module's own spell book-keeping (counts, prep_spell)
#   utils_npc_spells_tactics.SpellTactic.execute  feasibility before committing: spells left, target already
#                                                 affected, verbal/somatic components, range, approach (EDOT_* codes)
#   utils_tactics.TacticsHelper                   strategy triplets incl. Temple+ "target obj", "five foot step",
#                                                 "approach", "cast single", "total defence", "stop"
#   ctrl_behaviour.create_tactics_default_melee   ends with "stop": "otherwise default T+ AI will be working"
# Here the decisions come from the converted IE script (BCS blocks, top-down): a block whose Spell/Attack action is not
# feasible this round falls through to the next block; the static converted strategy is only the fallback.
from toee import *
import toee

OK = 0
NO_SPELLS_LEFT, TARGET_TOO_FAR, ALREADY_AFFECTED, CANNOT_CAST_VERBAL, CANNOT_CAST_SOMATIC, NO_LOS, TARGET_DEAD, \
    UNMAPPED, CANNOT_REACH, NOT_HURT, NO_TARGET = range(1, 12)
REASON = {OK: 'OK', NO_SPELLS_LEFT: 'NO_SPELLS_LEFT', TARGET_TOO_FAR: 'TARGET_TOO_FAR', ALREADY_AFFECTED: 'ALREADY_AFFECTED',
          CANNOT_CAST_VERBAL: 'CANNOT_CAST_VERBAL', CANNOT_CAST_SOMATIC: 'CANNOT_CAST_SOMATIC', NO_LOS: 'NO_LOS',
          TARGET_DEAD: 'TARGET_DEAD', UNMAPPED: 'UNMAPPED', CANNOT_REACH: 'CANNOT_REACH', NOT_HURT: 'NOT_HURT',
          NO_TARGET: 'NO_TARGET'}
CLASS_NAME = {'clr': 'class_cleric', 'drd': 'class_druid', 'wiz': 'class_wizard', 'sor': 'class_sorcerer',
              'brd': 'class_bard', 'pal': 'class_paladin', 'rgr': 'class_ranger', 'domain_special': 'domain_special'}
LOG = [None]
STATE = {}       # critter key -> {'rounds', 'history': [(round, what, reason)], 'cast': {(res, target key): round}}
CUR = [None]     # the Round being planned (set while the IE script round runs inside san_start_combat)


def log(msg):
    line = 'IE_COMBAT ' + msg
    if LOG[0]:
        try:
            f = open(LOG[0], 'a'); f.write(line + '\n'); f.close()
        except Exception:
            pass
    try:
        print(line)
    except Exception:
        pass


def _key(o):
    try:
        return str(o.id)
    except Exception:
        return str(o)


def state(o):
    return STATE.setdefault(_key(o), {'rounds': 0, 'history': [], 'cast': {}})


def _hp(o):
    return o.stat_level_get(stat_hp_current)


def _dead(o):
    try:
        return o is None or _hp(o) <= -10 or (o.object_flags_get() & (OF_DESTROYED | OF_OFF)) != 0
    except Exception:
        return True


def _q(o, name):
    q = getattr(toee, name, None)
    try:
        return q is not None and o.d20_query(q)
    except Exception:
        return False


def _hourglass():
    try:
        import tpactions
        tb = tpactions.get_cur_seq().tb_status
        return tb.hourglass_state if tb else None
    except Exception:
        return None


def cannot_act(npc):
    """The turns Anatoliy's start_combat skips with SKIP_DEFAULT (nothing to decide)."""
    hp = _hp(npc)
    if hp < 0:
        return 'dying'
    for q, why in (('Q_Unconscious', 'unconscious'), ('Q_Helpless', 'helpless'), ('Q_Critter_Is_Stunned', 'stunned'),
                   ('Q_Critter_Is_Held', 'held')):
        if _q(npc, q):
            return why
    if _hourglass() == getattr(toee, 'D20ACT_NULL', 0) and _hourglass() is not None:
        return 'no actions left'
    return None


def _reach(npc):
    try:
        return npc.get_reaches()[0]
    except Exception:
        return 5.0


def can_move(npc):
    hg = _hourglass()
    return hg is None or hg >= getattr(toee, 'D20ACT_Move_Action', 1)


def _threatened(npc, foes):
    for f in foes:
        try:
            if f.distance_to(npc) <= _reach(f) and not _q(f, 'Q_Helpless'):
                return True
        except Exception:
            pass
    return False


class Round(object):
    """One combat turn: recon once, feasibility checks for the IE script's actions, then the Temple+ strategy."""
    def __init__(self, npc, ident, foes):
        self.npc, self.ident, self.foes = npc, ident, foes
        self.tac = []           # strategy triplets (without the name)
        self.what = None        # the action that was committed
        self.st = state(npc)

    def add(self, name, middle='', spell=''):
        self.tac += [name, middle, spell]

    # ------------------------------------------------------------------ spells (SpellTactic.execute)
    def check_spell(self, res, target, mode):
        import ie_spellrt as sr
        npc = self.npc
        e = sr.entry(res) if res else None
        if not e or e.get('t') is None:
            return UNMAPPED, None
        sid = int(e['t'])
        key = sr.class_for(npc, e)
        lvl = sr.level_for(e, key)
        if mode == 'spell' and not sr.have(npc, res):
            return NO_SPELLS_LEFT, None
        if mode == 'spell':
            store = self._store(sid)
            if store is not None and not npc.can_cast_spell(store):
                return NO_SPELLS_LEFT, None
        personal, rng, comps = False, None, 0
        try:
            import tpdp
            se = tpdp.SpellEntry(sid)
            personal = se.spell_range_type == tpdp.SpellRangeType.SRT_Personal
            if not personal:
                cl = max(1, npc.stat_level_get(stat_level))
                rng = se.spell_range if se.spell_range_type == tpdp.SpellRangeType.SRT_Specified \
                    else se.get_spell_range_exact(cl, npc)
            comps = se.spell_component_flags
        except Exception:
            pass
        if target is None or personal:
            target = npc
        if _dead(target):
            return TARGET_DEAD, None
        # Anatoliy also blocks verbal spells when deafened; in 3.5 that is a 20 % failure chance, so only Silence here
        if comps & getattr(toee, 'SCF_VERBAL', 0) and (self._has_cond(npc, 'Silence') or
                                                         self._has_cond(npc, 'Silence Hit')):
            return CANNOT_CAST_VERBAL, None
        if comps & getattr(toee, 'SCF_SOMATIC', 0) and (_q(npc, 'Q_Critter_Is_Grappling') or _q(npc, 'Q_Helpless')):
            return CANNOT_CAST_SOMATIC, None
        name = e.get('n') or ''
        ai = e.get('ai') or ''
        if target is not npc and ai.startswith('ai_action_offensive') and \
                (self._has_cond(target, name) or _q(target, 'Q_Critter_Is_Held') or _q(target, 'Q_Helpless')):
            return ALREADY_AFFECTED, None
        if ai.startswith('ai_action_defensive') and self._has_cond(target, name):
            return ALREADY_AFFECTED, None
        if ai.startswith('ai_action_heal') and _hp(target) >= target.stat_level_get(stat_hp_max):
            return NOT_HURT, None
        approach = False
        if target is not npc and rng is not None:
            dist = npc.distance_to(target)
            if dist > rng:
                speed = npc.stat_level_get(stat_movement_speed)
                if can_move(npc) and dist - rng <= speed and npc.can_find_path_to_obj(target):
                    approach = True
                else:
                    return TARGET_TOO_FAR, None
            if not approach and not npc.has_los(target):
                if can_move(npc) and npc.can_find_path_to_obj(target):
                    approach = True
                else:
                    return NO_LOS, None
        return OK, dict(sid=sid, key=key, lvl=lvl, target=target, approach=approach, name=name, res=res)

    def _store(self, sid):
        try:
            for m in self.npc.spells_memorized:
                if m.spell_enum == sid and not m.is_used_up():
                    return m
        except Exception:
            pass
        return None

    def _has_cond(self, o, name):
        c = getattr(toee, 'sp_' + name.replace(' ', '_').replace("'", ''), None) if name else None
        try:
            return c is not None and o.d20_query_has_spell_condition(c)
        except Exception:
            return False

    def plan_spell(self, res, target, mode):
        import ie_spellrt as sr
        if self.what:
            return False
        code, p = self.check_spell(res, target, mode)
        if code:
            self.note('spell %s' % res, code)
            return False
        npc = self.npc
        if mode in sr.FORCE_MODES:
            sr.grant(npc, p['sid'], p['key'], p['lvl'], 1)   # SPL-ADJ-17
        else:
            d = sr._given.get(sr._okey(npc), {})
            d[res] = d.get(res, 0) - 1                        # like Anatoliy's NPCSpells.prep_spell
        if p['approach']:
            self.add('target obj', p['target'].id); self.add('approach')
        elif _threatened(npc, self.foes) and p['target'] is not npc:
            self.add('five foot step')
        if p['target'] is npc:
            self.add('target self')
        else:
            self.add('target obj', p['target'].id)
        try:
            sname = game.get_spell_mesline(p['sid']).replace("'", '')
        except Exception:
            sname = p['name']
        self.add('cast single', '', "'%s' %s %d" % (sname, CLASS_NAME.get(p['key'], 'domain_special'), p['lvl']))
        self.what = 'cast %s (%s) on %s%s' % (res, sname, p['target'], ' after approach' if p['approach'] else '')
        self.st['cast'][(res, _key(p['target']))] = self.st['rounds']
        return True

    # ------------------------------------------------------------------ attacks (create_tactics_default_melee)
    def check_attack(self, target):
        npc = self.npc
        if target is None:
            return NO_TARGET, None
        if _dead(target) or _hp(target) < 0:
            return TARGET_DEAD, None
        ranged = False
        try:
            w = npc.item_worn_at(item_wear_weapon_primary)
            ranged = bool(w) and game.is_ranged_weapon(w.obj_get_int(obj_f_weapon_type))
        except Exception:
            pass
        if ranged:
            return (OK, dict(target=target, approach=False)) if npc.has_los(target) else (NO_LOS, None)
        if npc.distance_to(target) <= _reach(npc):
            return OK, dict(target=target, approach=False)
        if can_move(npc) and npc.can_find_path_to_obj(target):
            return OK, dict(target=target, approach=True)
        return CANNOT_REACH, None

    def plan_attack(self, target):
        if self.what:
            return False
        code, p = self.check_attack(target)
        if code:
            self.note('attack', code)
            return False
        self.npc.obj_set_obj(obj_f_npc_combat_focus, p['target'])
        self.add('target obj', p['target'].id)
        self.add('attack')                     # includes approaching
        self.what = 'attack %s%s' % (p['target'], ' (approach)' if p['approach'] else '')
        return True

    def note(self, what, code):
        self.st['history'].append((self.st['rounds'], what, REASON[code]))
        log('%s r%d: %s not feasible: %s' % (self.ident, self.st['rounds'], what, REASON[code]))

    # ------------------------------------------------------------------ fallback (the static strategy)
    def fallback(self, spec_strategy, script_first):
        """No script block committed an action: the converted static strategy, with spell entries whose slot is
        gone removed (SPL-ADJ-18 script_first: no spell entries at all), ending with "stop" so Temple+ does not fall
        through to its built-in DefaultCast."""
        t = list(spec_strategy or ['', 'attack', '', '', 'approach', '', '', 'attack', '', ''])[1:]
        out = []
        for i in range(0, len(t) - 2, 3):
            name, mid, spell = t[i], t[i + 1], t[i + 2]
            if name.startswith('cast'):
                if script_first or not self._spell_code_castable(spell):
                    continue
            if name == 'stop':
                continue
            out += [name, mid, spell]
        return out + ['total defence', '', '', 'stop', '', '']

    def _spell_code_castable(self, code):
        try:
            name = code.split("'")[1]
            for m in self.npc.spells_memorized:
                if not m.is_used_up() and game.get_spell_mesline(m.spell_enum).replace("'", '') == name:
                    return self.npc.can_cast_spell(m)
        except Exception:
            pass
        return False


def round_start(npc, ident, foes, run_script_round, spec_strategy=None, script_first=True):
    """san_start_combat body. run_script_round(round) evaluates the IE blocks with feasibility checks. Returns
    SKIP_DEFAULT (cannot act) or RUN_DEFAULT after setting this round's Temple+ strategy."""
    st = state(npc)
    st['rounds'] += 1
    why = cannot_act(npc)
    if why:
        log('%s r%d: skip (%s)' % (ident, st['rounds'], why))
        st['history'].append((st['rounds'], 'skip', why))
        return SKIP_DEFAULT
    r = Round(npc, ident, foes)
    CUR[0] = r
    try:
        run_script_round(r)
    except Exception, e:
        log('%s: script round error %s' % (ident, e))
    CUR[0] = None
    if r.what:
        tac = r.tac + ['total defence', '', '', 'stop', '', '']
        st['history'].append((st['rounds'], r.what, 'OK'))
        log('%s r%d: IE script -> %s' % (ident, st['rounds'], r.what))
    else:
        tac = r.fallback(spec_strategy, script_first)
        st['history'].append((st['rounds'], 'fallback', 'static strategy'))
        log('%s r%d: no feasible IE block -> static strategy %s' % (ident, st['rounds'], tac[0::3]))
    try:
        npc.ai_strategy_set_custom(['ie2toee_r%d' % st['rounds']] + tac, 0)
    except Exception, e:
        log('%s: ai_strategy_set_custom failed %s' % (ident, e))
    return RUN_DEFAULT

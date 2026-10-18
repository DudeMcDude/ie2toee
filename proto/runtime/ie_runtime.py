# ie_runtime: shared Temple+ runtime for dialogue and scripts converted from Infinity Engine DLG / BCS files
# (Python 2.7, runs inside the game; also importable outside it for tests -- the toee module is optional).
#
# Generated code (see dlg2toee.py / bcs2py.py) only calls into this module:
#   T.<Trigger>(c, args...)  -> bool        triggers (Global, See, NumTimesTalkedTo, ...)
#   A.<Action>(c, args...)   -> None|wait   actions  (SetGlobal, StartDialog, GiveItem, ActionOverride, ...)
#   O(c, 'Player1'), O(c, 'NearestEnemyOf', O(c, 'Myself')), N(c, 'deathvar'), F(c, EA=255)   object references
# Unknown triggers/actions never raise: they are logged once (IE_UNSUPPORTED) and a trigger evaluates to False.
#
# Context `c` = Ctx(me, other): `me` is the object running the script ("Myself"), `other` is the dialogue partner
# (LastTalkedToBy / Protagonist fallback). Each converted object has an IE identity string (its IE script name /
# death variable) that keys LOCALS and NumTimesTalkedTo.
#
# Variables: IE GLOBAL / LOCALS / <area> / MYAREA variables are kept in game.global_vars slots that the converter
# allocated (module ie_varslots: SLOTS = {'global:name': index, ...}); unallocated ones fall back to an in-memory
# dict (logged, not saved). Timers (SetGlobalTimer) store the expiry time in game seconds.
import random
try:
    _NUM = (int, long, float)
except NameError:      # python 3 (offline tests)
    _NUM = (int, float)

try:
    from toee import *
    from utilities import location_from_axis, location_to_axis
    IN_GAME = True
except ImportError:          # unit tests / offline
    IN_GAME = False
    game = None

LOG_PATH = None              # set by the test harness; default: the Temple+ console via print
_logged = {}

def log(msg):
    line = 'IE_RT ' + msg
    if LOG_PATH:
        try:
            f = open(LOG_PATH, 'a'); f.write(line + '\n'); f.close()
        except Exception:
            pass
    try:
        print(line)
    except Exception:
        pass

def log_once(key, msg):
    if key not in _logged:
        _logged[key] = 1
        log(msg)

# ------------------------------------------------------------------------------------------------ variables
SLOTS = {}
try:
    import ie_varslots
    SLOTS = ie_varslots.SLOTS
except ImportError:
    pass
_mem = {}

_clk = [None, 0.0]   # [last game time seen, real time when it changed]

def _real():
    import time
    return time.time()

def _now():
    """Script clock in seconds: game time, advanced by real time while game time stands still (Temple+ keeps the
    game clock frozen outside combat/rest/travel, the IE clock always runs). Rebased whenever game time moves
    (rest, travel), so IE timers stored in it survive saves (they may run a little long after a reload)."""
    try:
        gt = game.time.time_game_in_seconds(game.time)
    except Exception:
        return _real()
    if gt != _clk[0]:
        _clk[0], _clk[1] = gt, _real()
    return gt + int(_real() - _clk[1])

def var_key(c, name, scope):
    s = (scope or 'GLOBAL').upper(); n = name.lower()
    if s == 'GLOBAL':
        return 'global:' + n
    if s == 'LOCALS':
        return 'locals:%s:%s' % (c.ident.lower(), n)
    if s == 'MYAREA':
        s = c.area.upper()
    return 'area:%s:%s' % (s.lower(), n)

def get_var(c, name, scope):
    k = var_key(c, name, scope)
    i = SLOTS.get(k)
    if i is not None and IN_GAME:
        return game.global_vars[i]
    if i is None:
        log_once('slot:' + k, 'IE_VAR_UNALLOCATED %s (kept in memory, not saved)' % k)
    return _mem.get(k, 0)

def set_var(c, name, scope, value):
    k = var_key(c, name, scope)
    i = SLOTS.get(k)
    if i is not None and IN_GAME:
        game.global_vars[i] = int(value)
    else:
        if i is None:
            log_once('slot:' + k, 'IE_VAR_UNALLOCATED %s (kept in memory, not saved)' % k)
        _mem[k] = int(value)
    log('SET %s = %d' % (k, int(value)))

# ------------------------------------------------------------------------------------------------ context
class Ctx(object):
    def __init__(self, me, other=None, ident='', area='', events=None):
        self.me, self.other, self.ident, self.area = me, other, ident, area
        self.events = events or {}
        self.last_trigger = None
    def __repr__(self):
        return 'Ctx(%s)' % self.ident

_bound = {}          # ToEE object id/handle -> (ident, area)
_queues = {}         # ident -> [pending action thunks]
_busy = {}           # ident -> game-seconds until which the actor is busy
_events = {}         # ident -> {event name: other object}
_placement = {}      # area -> (canvas_x, canvas_y, scale, cal_x, cal_y)
DIALOG_RANGE = {}

def set_placement(area, cx, cy, scale=1.0, calx=8428, caly=-4366):
    _placement[area.lower()] = (cx, cy, scale, calx, caly)

def ie_to_tile(area, x, y):
    cx, cy, s, calx, caly = _placement.get(area.lower(), (0, 0, 1.0, 8428, -4366))
    X = cx + x * s; Y = cy + y * s
    a = (X - calx) / 20.0; b = (Y - caly) / 14.0
    return int(round((b - a) / 2.0)), int(round((b + a) / 2.0))

def ctx_for(obj, other=None, ident=None, area=None):
    if ident is None:
        ident, area2 = _bound.get(_key(obj), ('', ''))
        area = area or area2
    return Ctx(obj, other, ident or '', area or '', _events.get(ident or '', {}))

def _key(obj):
    try:
        return obj.id
    except Exception:
        return id(obj)

def bind(obj, ident, area):
    _bound[_key(obj)] = (ident, area)

def _party():
    if not IN_GAME:
        return []
    try:
        return [p for p in game.party]
    except Exception:
        return []

def _pc(c):
    if c.other is not None:
        return c.other
    if IN_GAME:
        return game.leader
    return None

# ------------------------------------------------------------------------------------------------ objects
def O(c, name, inner=None):
    """object.ids reference (Myself, Player1, Protagonist, LastTalkedToBy, NearestEnemyOf(x), ...)."""
    n = name.lower()
    base = inner if inner is not None else c.me
    if n in ('myself',):
        return c.me
    if n in ('nothing',):
        return None
    if n in ('protagonist', 'player1', 'lasttalkedtoby', 'lastheardby', 'lastseenby', 'lasttrigger', 'gabber'):
        if n == 'lasttalkedtoby' or n == 'gabber':
            return _pc(c)
        if n in ('lasttrigger',) and c.last_trigger is not None:
            return c.last_trigger
        if n == 'lastheardby' or n == 'lastseenby':
            return _pc(c)
        p = _party()
        return p[0] if p else _pc(c)
    if n.startswith('player') and n[6:].isdigit():
        p = _party(); i = int(n[6:]) - 1
        return p[i] if i < len(p) else None
    if n in ('nearestenemyof', 'nearest', 'secondnearestenemyof'):
        return _nearest_enemy(base)
    if n in ('lastattackerof', 'lasthitter', 'lasttargetedby', 'lasthelp'):
        ev = c.events
        return ev.get('AttackedBy') or ev.get('HitBy') or ev.get('Help')
    log_once('obj:' + n, 'IE_UNSUPPORTED object %s' % name)
    return None

def N(c, name):
    """Object by IE script name / death variable."""
    if IN_GAME:
        for k, (ident, area) in _bound.items():
            if ident.lower() == name.lower():
                try:
                    o = game.get_obj_by_id(k)
                    if o:
                        return o
                except Exception:
                    pass
    log_once('objname:' + name.lower(), 'IE_OBJ_NOT_FOUND "%s"' % name)
    return None

def F(c, **filt):
    """[EA.GENERAL.RACE...] filter; only EA (PC/ENEMY/GOODCUTOFF/EVILCUTOFF) is honoured for now."""
    ea = filt.get('EA', 0)
    if ea in (2, 30) or ea == 'PC' or ea == 'GOODCUTOFF':
        p = _party()
        return p[0] if p else None
    if ea in (255, 200) or ea == 'ENEMY' or ea == 'EVILCUTOFF':
        return _nearest_enemy(c.me)
    log_once('filt:%r' % (sorted(filt.items()),), 'IE_UNSUPPORTED object filter %r' % (filt,))
    return None

def _kos(o):
    try:
        return (o.npc_flags_get() & ONF_KOS) != 0
    except Exception:
        return False

def _hostile(me, o):
    """IE-style enmity: an NPC is an enemy of the party once it is ENEMY (KOS in ToEE, set by Enemy())."""
    a, b = me in game.party, o in game.party
    if a == b:
        return False
    return _kos(o if a else me)

def _nearest_enemy(me):
    if not IN_GAME or me is None:
        return None
    best = None
    try:
        for o in game.obj_list_vicinity(me.location, OLC_CRITTERS):
            if o == me or _dead(o):
                continue
            hostile = _hostile(me, o)
            if hostile and (best is None or me.distance_to(o) < me.distance_to(best)):
                best = o
    except Exception as e:
        log_once('nearest', 'IE_ERR nearest enemy: %s' % e)
    return best

# ------------------------------------------------------------------------------------------------ triggers
class _Triggers(object):
    def __getattr__(self, name):
        def unsupported(c, *args):
            log_once('t:' + name, 'IE_UNSUPPORTED trigger %s%r -> False' % (name, args))
            return False
        return unsupported

    def True_(self, c): return True
    def False_(self, c): return False

    def Global(self, c, name, scope, v): return get_var(c, name, scope) == v
    def GlobalGT(self, c, name, scope, v): return get_var(c, name, scope) > v
    def GlobalLT(self, c, name, scope, v): return get_var(c, name, scope) < v
    def BitGlobal(self, c, name, scope, bits, mode=0):
        v = get_var(c, name, scope)
        return (v & bits) != 0 if mode in (0, 1) else (v & bits) == 0
    def GlobalTimerExpired(self, c, name, scope):
        t = get_var(c, name, scope)
        return _now() >= t           # an unset timer (0) counts as expired, like the IE
    def GlobalTimerNotExpired(self, c, name, scope):
        return not self.GlobalTimerExpired(c, name, scope)
    def TimerActive(self, c, tid): return _now() < get_var(c, '#timer%d' % tid, 'LOCALS')
    def TimerExpired(self, c, tid):
        t = get_var(c, '#timer%d' % tid, 'LOCALS')
        return t != 0 and _now() >= t

    def NumTimesTalkedTo(self, c, n): return times_talked(c) == n
    def NumTimesTalkedToGT(self, c, n): return times_talked(c) > n
    def NumTimesTalkedToLT(self, c, n): return times_talked(c) < n

    # EE TRIGGER.IDS names / extra triggers
    NumberOfTimesTalkedTo = NumTimesTalkedTo
    NumberOfTimesTalkedToGT = NumTimesTalkedToGT
    NumberOfTimesTalkedToLT = NumTimesTalkedToLT
    def ActionListEmpty(self, c): return _busy.get(c.ident, 0) <= _now() and c.ident not in _queues
    def RandomNum(self, c, rng, n): return random.randint(1, max(1, rng)) == n
    def RandomNumGT(self, c, rng, n): return random.randint(1, max(1, rng)) > n
    def RandomNumLT(self, c, rng, n): return random.randint(1, max(1, rng)) < n
    def Detect(self, c, obj): return self.See(c, obj)
    def IsGabber(self, c, obj): return obj is not None and obj == c.other
    def InParty(self, c, obj): return IN_GAME and obj is not None and obj in game.party
    def NumInPartyGT(self, c, n): return len(_party()) > n
    def NumInPartyLT(self, c, n): return len(_party()) < n
    def NumInParty(self, c, n): return len(_party()) == n
    def Died(self, c, obj=None): return self._event(c, 'Die')
    def InMyArea(self, c, obj):
        try:
            return obj is not None and obj.map == c.me.map
        except Exception:
            return False
    def NextTriggerObject(self, c, obj):
        log_once('nto', 'IE_PARTIAL NextTriggerObject: redirection of the next trigger not modelled')
        c.last_trigger = obj
        return True
    def Kit(self, c, obj, k):
        log_once('kit', 'IE_UNSUPPORTED trigger Kit -> False (no ToEE kits)'); return False
    def StateCheck(self, c, obj, st):
        if st & 0x800 and obj is not None:      # STATE_DEAD
            return _dead(obj)
        log_once('state:%x' % st, 'IE_UNSUPPORTED StateCheck state 0x%x -> False' % st); return False
    def OnCreation(self, c): return bool(c.events.pop('OnCreation', None))
    def AttackedBy(self, c, obj=None, style=0): return self._event(c, 'AttackedBy')
    def HitBy(self, c, obj=None, dmg=0): return self._event(c, 'HitBy')
    def Die(self, c): return self._event(c, 'Die')
    def Entered(self, c, obj=None): return self._event(c, 'Entered')
    def Opened(self, c, obj=None): return self._event(c, 'Opened')
    def Unlocked(self, c, obj=None): return self._event(c, 'Unlocked')
    def _event(self, c, ev):
        if ev in c.events:
            c.last_trigger = c.events.pop(ev)
            return True
        return False

    def Exists(self, c, obj): return obj is not None
    def HaveSpell(self, c, spell):
        if not IN_GAME:
            return False
        import ie_spellrt
        return ie_spellrt.have(c.me, spell)
    HaveSpellRES = HaveSpell
    def Dead(self, c, name):
        o = N(c, name)
        return o is None or _dead(o)
    def See(self, c, obj):
        if obj is None or c.me is None or not IN_GAME:
            return False
        try:
            return c.me.distance_to(obj) < 40 and c.me.can_see(obj)
        except Exception:
            return False
    def LOS(self, c, obj, rng): return self.See(c, obj)
    def Range(self, c, obj, rng):
        try:
            return c.me.distance_to(obj) <= rng / 3.0     # IE search-map units ~ 1/3 ToEE ft (rough)
        except Exception:
            return False
    def Allegiance(self, c, obj, ea):
        if obj is None:
            return False
        if not IN_GAME:
            return False
        inparty = obj in game.party
        if ea in (2, 30):      # PC / GOODCUTOFF
            return inparty
        if ea in (255, 200):   # ENEMY / EVILCUTOFF
            return not inparty and _kos(obj)
        if ea == 128:          # NEUTRAL
            return not inparty
        return False
    def HPPercentLT(self, c, obj, pct): return _hp_pct(obj) < pct
    def HPPercentGT(self, c, obj, pct): return _hp_pct(obj) > pct
    def HP(self, c, obj, hp): return _hp(obj) == hp
    def HPGT(self, c, obj, hp): return _hp(obj) > hp
    def HPLT(self, c, obj, hp): return _hp(obj) < hp
    def PartyGoldGT(self, c, n): return _party_gold() > n
    def PartyGoldLT(self, c, n): return _party_gold() < n
    def PartyHasItem(self, c, res):
        for pc in _party():
            if item_find(pc, res):
                return True
        return False
    def HasItem(self, c, res, obj=None):
        o = obj if obj is not None else c.me
        return bool(item_find(o, res))
    def Gender(self, c, obj, g):
        try:   # IE gender.ids 1 MALE 2 FEMALE; ToEE stat_gender: gender_male = 1, gender_female = 0
            return {1: 1, 2: 0}.get(g, -1) == obj.stat_level_get(stat_gender)
        except Exception:
            return False
    def Race(self, c, obj, r): return _cmp_stat(c, obj, 'race', r)
    def Class(self, c, obj, k): return _cmp_stat(c, obj, 'class', k)
    def ClassEx(self, c, obj, k): return _cmp_stat(c, obj, 'class', k)
    def Alignment(self, c, obj, a): return _cmp_stat(c, obj, 'align', a)
    def CheckStat(self, c, obj, v, stat): return _ie_stat(obj, stat) == v
    def CheckStatGT(self, c, obj, v, stat): return _ie_stat(obj, stat) > v
    def CheckStatLT(self, c, obj, v, stat): return _ie_stat(obj, stat) < v
    def NearLocation(self, c, obj, x, y, rng):
        o = obj if obj is not None else c.me
        if not IN_GAME or o is None:
            return False
        u, v = ie_to_tile(c.area, x, y)
        try:
            lx, ly = location_to_axis(o.location)
        except Exception:
            return False
        # IE range is in search-map units (~16 px); a ToEE tile is ~28 px along its axes -> about rng/2 tiles
        return (lx - u) ** 2 + (ly - v) ** 2 <= (2 + rng / 2.0) ** 2
    def NearSavedLocation(self, c, *args):
        return True    # the saved location is the spawn point; ToEE NPCs return to their standpoint themselves

T = _Triggers()
setattr(_Triggers, 'True', lambda self, c: True)
setattr(_Triggers, 'False', lambda self, c: False)

def _dead(o):
    try:
        return o.is_dead_or_destroyed() if hasattr(o, 'is_dead_or_destroyed') else o.stat_level_get(stat_hp_current) <= -10
    except Exception:
        return True

def _hp(o):
    try:
        return o.stat_level_get(stat_hp_current)
    except Exception:
        return 0

def _hp_pct(o):
    try:
        m = o.stat_level_get(stat_hp_max)
        return 100 * o.stat_level_get(stat_hp_current) // max(1, m)
    except Exception:
        return 100

def _party_gold():
    try:
        return game.party[0].money_get() // 100     # copper -> gp
    except Exception:
        return 0

# IE -> ToEE value maps (guidance data, editable): IDS values to ToEE stats/constants
MAPS = {
    'race': {1: 0, 2: 1, 3: 6, 4: 2, 5: 4, 6: 3, 7: 5},      # IE race.ids -> ToEE race (human elf dwarf gnome halfelf halforc halfling)
    'class': {1: 'class_wizard', 2: 'class_fighter', 3: 'class_cleric', 4: 'class_rogue', 5: 'class_bard',
              6: 'class_paladin', 11: 'class_druid', 12: 'class_ranger', 20: 'class_sorcerer', 21: 'class_monk'},
    'stat': {38: 'stat_strength', 39: 'stat_intelligence', 40: 'stat_wisdom', 41: 'stat_dexterity',
             42: 'stat_constitution', 43: 'stat_charisma', 34: 'stat_level'},
}

def _cmp_stat(c, obj, kind, ieval):
    if obj is None or not IN_GAME:
        return False
    try:
        if kind == 'race':
            want = MAPS['race'].get(ieval)
            return want is not None and obj.stat_level_get(stat_race) == want
        if kind == 'class':
            want = MAPS['class'].get(ieval)
            return want is not None and obj.stat_level_get(globals()[want]) > 0
        if kind == 'align':
            a = obj.critter_get_alignment()
            return _align_match(ieval, a)
    except Exception as e:
        log_once('cmp:' + kind, 'IE_ERR %s: %s' % (kind, e))
    return False

def _align_match(ieval, toee):
    # IE alignmen.ids: 0xLG (L: 1 lawful 2 neutral 3 chaotic, G: 1 good 2 neutral 3 evil), 0x01..0x03 / 0x10.. masks
    # ToEE: ALIGNMENT_LAWFUL=1 CHAOTIC=2 GOOD=4 EVIL=8 (neutral = 0 bits)
    lc = (toee & 1) and 1 or ((toee & 2) and 3 or 2)
    ge = (toee & 4) and 1 or ((toee & 8) and 3 or 2)
    hi, lo = (ieval >> 4) & 0xF, ieval & 0xF
    if hi and lo:
        return hi == lc and lo == ge
    if hi:
        return hi == lc
    if lo:
        return lo == ge
    return True

def _ie_stat(obj, stat):
    n = MAPS['stat'].get(stat)
    if n is None or obj is None or not IN_GAME:
        log_once('stat:%s' % stat, 'IE_UNSUPPORTED stat %s' % stat)
        return 0
    return obj.stat_level_get(globals()[n])

# items: IE resref -> converted item (ie_itemrt + the generated ie_itemmap; docs/items.md). Unknown items are logged.
try:
    import ie_itemrt
except ImportError:
    ie_itemrt = None

def item_proto(res):
    if ie_itemrt is None:
        log_once('item:' + res.lower(), 'IE_ITEM_UNMAPPED %s' % res)
        return None
    return ie_itemrt.proto(res)

def item_find(holder, res):
    if ie_itemrt is None or holder is None:
        return None
    return ie_itemrt.find(holder, res)

def item_give(res, holder):
    if ie_itemrt is None or holder is None:
        return None
    return ie_itemrt.give(res, holder)

# ------------------------------------------------------------------------------------------------ dialogue
def times_talked(c):
    return get_var(c, '#talked', 'LOCALS')

def dlg_start(npc, pc, ident, area, states, entry):
    """Called from the generated san_dialog. `states` = [(state_line, cond_fn)] in IE evaluation order (state
    trigger table order); the first whose condition holds is the entry line. NumTimesTalkedTo counts up after."""
    c = Ctx(npc, pc, ident, area)
    bind(npc, ident, area)
    line = None
    for ln, cond in states:
        try:
            ok = cond(c)
        except Exception as e:
            log('IE_ERR state %d condition: %s' % (ln, e)); ok = False
        if ok:
            line = ln; break
    if line is None:
        line = entry
    set_var(c, '#talked', 'LOCALS', times_talked(c) + 1)
    if line is None:
        log('DLG %s: no valid start state' % ident)
        try:
            npc.float_text_line('...', 1)
        except Exception:
            pass
        return SKIP_DEFAULT if IN_GAME else None
    log('DLG %s start line %d (talked %d)' % (ident, line, times_talked(c) - 1))
    try:
        npc.turn_towards(pc)
    except Exception:
        pass
    pc.begin_dialog(npc, line)
    return SKIP_DEFAULT if IN_GAME else None

def dlg_cond(npc, pc, ident, area, fn):
    try:
        return bool(fn(Ctx(npc, pc, ident, area)))
    except Exception as e:
        log('IE_ERR dialog condition %s: %s' % (ident, e))
        return False

def dlg_do(npc, pc, ident, area, actions, journal=None):
    """Dialogue transition effect: run the IE actions (queued on the NPC, like the IE) and note journal text."""
    c = Ctx(npc, pc, ident, area)
    if journal is not None:
        log('JOURNAL %s' % journal)
    run_actions(c, actions)
    return 1

# ------------------------------------------------------------------------------------------------ actions
CONTINUE = object()

def run_actions(c, actions):
    """Execute a response's actions in order. An action may return a delay (game seconds) -> the rest are
    scheduled after it (IE action queue semantics, simplified)."""
    q = list(actions)
    _run_q(c, q)

def _run_q(c, q):
    while q:
        fn = q.pop(0)
        try:
            r = fn(c)
        except Exception as e:
            log('IE_ERR action in %s: %s' % (c.ident, e)); r = None
        if r is CONTINUE or r is None:
            continue
        if isinstance(r, _NUM) and r > 0:
            if MODE['round']:          # a combat round plans one action; IE waits do not carry into later rounds
                continue
            _busy[c.ident] = _now() + r
            if q and IN_GAME:
                game.timeevent_add(_resume, (c.me, c.other, c.ident, c.area, len(q)), int(r * 1000), 1)
                _queues[c.ident] = (c, q)
            return
    _busy.pop(c.ident, None)

def _resume(me, other, ident, area, n):
    ent = _queues.pop(ident, None)
    if ent:
        _run_q(ent[0], ent[1])
    return 1

MODE = {'round': False, 'dry': False, 'probe': False, 'fail': []}
# actions that are checked for feasibility in a combat round; every other action is a no-op during the dry run
COMBAT_ACTIONS = set(['Spell', 'SpellNoDec', 'ForceSpell', 'ForceSpellRange', 'ReallyForceSpell', 'ReallyForceSpellDead',
                      'ApplySpell', 'SpellPoint', 'SpellPointNoDec', 'ForceSpellPoint', 'ForceSpellPointRange',
                      'ReallyForceSpellPoint', 'SpellRES', 'ForceSpellRES', 'ReallyForceSpellRES', 'ApplySpellRES',
                      'Attack', 'AttackOneRound', 'AttackReevaluate'])

def _noop(*args):
    return None

class _Actions(object):
    def __getattribute__(self, name):
        if MODE['dry'] and name[:1] != '_' and name not in COMBAT_ACTIONS:
            return _noop
        return object.__getattribute__(self, name)

    def __getattr__(self, name):
        def unsupported(c, *args):
            log_once('a:' + name, 'IE_UNSUPPORTED action %s%r' % (name, args))
        return unsupported

    def Continue(self, c): return CONTINUE
    def NoAction(self, c): return None
    def MultiPlayerSync(self, c): return None
    def SetGlobal(self, c, name, scope, v): set_var(c, name, scope, v)
    def IncrementGlobal(self, c, name, scope, v): set_var(c, name, scope, get_var(c, name, scope) + v)
    def BitGlobal(self, c, name, scope, bits, mode):
        v = get_var(c, name, scope)
        v = {0: v & bits, 1: v | bits, 2: v ^ bits, 3: v & ~bits, 4: v ^ bits}.get(mode, v)   # BITMODE.IDS
        set_var(c, name, scope, v)
    def SetGlobalTimer(self, c, name, scope, secs): set_var(c, name, scope, _now() + secs)
    def StartTimer(self, c, tid, secs): set_var(c, '#timer%d' % tid, 'LOCALS', _now() + secs)
    def StartRandomTimer(self, c, tid, lo, hi): set_var(c, '#timer%d' % tid, 'LOCALS', _now() + random.randint(lo, max(lo, hi)))
    def SetNumTimesTalkedTo(self, c, n): set_var(c, '#talked', 'LOCALS', n)
    def Wait(self, c, secs): return secs
    def SmallWait(self, c, ticks): return max(1, ticks // 15)
    def SetDialogueRange(self, c, r): DIALOG_RANGE[c.ident] = r
    def ClearAllActions(self, c):
        _queues.pop(c.ident, None); _busy.pop(c.ident, None)

    def ActionOverride(self, c, obj, action):
        if obj is None:
            log('IE_OBJ_NOT_FOUND ActionOverride target'); return None
        ident, area = _bound.get(_key(obj), (c.ident + '>', c.area))
        c2 = Ctx(obj, c.other, ident, area, _events.get(ident, {}))
        run_actions(c2, [action])

    def Dialog(self, c, obj): return self.StartDialog(c, None, obj)
    def StartDialogNoSet(self, c, obj): return self.StartDialog(c, None, obj)
    def StartDialog(self, c, dlg, obj):
        if obj is None or not IN_GAME:
            return
        log('DIALOG %s -> %s' % (c.ident, obj))
        try:
            if obj in game.party:
                c.me.object_script_execute(obj, san_dialog)    # same path as the player clicking the NPC
            else:
                obj.object_script_execute(c.me, san_dialog)
        except Exception as e:
            log('IE_ERR StartDialog: %s' % e)
    def StartStore(self, c, store, obj):
        log('STORE %s' % store)
        try:
            if ie_itemrt is not None and ie_itemrt.STORES.has_key(store.lower()):
                ie_itemrt.open_store(store, c.me, obj or _pc(c))
            else:
                (obj or _pc(c)).barter(c.me)
        except Exception as e:
            log('IE_ERR StartStore: %s' % e)
    def Enemy(self, c):
        log('ENEMY %s' % c.ident)
        if IN_GAME and c.me is not None:
            try:
                c.me.npc_flag_set(ONF_KOS)
                c.me.attack(game.leader)
            except Exception as e:
                log('IE_ERR Enemy: %s' % e)
    def Attack(self, c, obj):
        if MODE.get('probe'):
            MODE['fail'].append('Attack'); return None
        r = _round_for(c)
        if r is not None:                      # combat round: feasibility check / plan, executed by Temple+ AI
            if MODE['dry']:
                code, p = r.check_attack(obj)
                if code:
                    MODE['fail'].append('Attack: %s' % _reason(code))
            else:
                r.plan_attack(obj)
            return None
        if IN_GAME and obj is not None:
            c.me.attack(obj)
    def AttackOneRound(self, c, obj): self.Attack(c, obj); return 6
    def EscapeArea(self, c):
        log('ESCAPE %s' % c.ident)
        if IN_GAME and c.me is not None:
            try:
                c.me.runoff(c.me.location - 3)
            except Exception:
                pass
            game.timeevent_add(_destroy, (c.me,), 2500, 1)
    def EscapeAreaDestroy(self, c, delay=0): self.EscapeArea(c)
    def DestroySelf(self, c):
        log('DESTROY %s' % c.ident)
        if IN_GAME and c.me is not None:
            c.me.destroy()
    def AddXPVar(self, c, name, xp):
        log('XP party %d (%s)' % (xp, name))
        for pc in _party():
            try:
                pc.award_experience(xp // max(1, len(_party())))
            except Exception:
                pass
    AddXpVar = AddXPVar
    def AddexperienceParty(self, c, xp): self.AddXPVar(c, '', xp)
    def GiveItem(self, c, res, obj):
        if obj is not None and IN_GAME:
            it = item_find(c.me, res)
            if it:
                obj.item_get(it)
            else:
                item_give(res, obj)
        log('GIVE %s -> %s' % (res, obj is not None and 'target' or 'none'))
    def GiveItemCreate(self, c, res, obj, a=0, b=0, d=0):
        if obj is not None and IN_GAME:
            item_give(res, obj)
        log('CREATE_ITEM %s' % res)
    def TakePartyItem(self, c, res):
        log('TAKE %s' % res)
        if IN_GAME:
            for pc in _party():
                it = item_find(pc, res)
                if it:
                    it.destroy(); return
    def TakePartyGold(self, c, gp):
        log('TAKE_GOLD %d' % gp)
        if IN_GAME:
            game.party[0].money_adj(-gp * 100)
    def GiveGoldForce(self, c, gp):
        if IN_GAME:
            game.party[0].money_adj(gp * 100)
    def FloatMessage(self, c, obj, strref): return self.DisplayStringHead(c, obj, strref)
    def DisplayString(self, c, obj, strref): return self.DisplayStringHead(c, obj, strref)
    def DisplayStringHead(self, c, obj, strref):
        txt = text(strref)
        log('FLOAT %s' % txt)
        if IN_GAME and (obj or c.me) is not None:
            try:
                (obj or c.me).float_text_line(txt, 0)
            except Exception:
                pass
    def Face(self, c, d):
        # IE orientation: 16 steps, 0 = south (screen down), clockwise: 4 = west, 8 = north, 12 = east
        if IN_GAME and c.me is not None:
            import math
            th = d * math.pi / 8.0; dx, dy = -math.sin(th), math.cos(th)
            du = (dy / 14.0 - dx / 20.0) / 2.0 * 60; dv = (dy / 14.0 + dx / 20.0) / 2.0 * 60
            try:
                u, v = location_to_axis(c.me.location)
                c.me.turn_towards_loc(location_from_axis(int(round(u + du)), int(round(v + dv))))
            except Exception as e:
                log('IE_ERR Face: %s' % e)
    def FaceObject(self, c, obj):
        if IN_GAME and obj is not None:
            c.me.turn_towards(obj)
    def MoveToPoint(self, c, pt):
        u, v = ie_to_tile(c.area, pt[0], pt[1])
        log('MOVE %s -> IE(%d,%d) tile(%d,%d)' % (c.ident, pt[0], pt[1], u, v))
        if IN_GAME and c.me is not None:
            try:
                _walk(c.me, u, v)
            except Exception as e:
                log('IE_ERR MoveToPoint: %s' % e)
        return 3
    def MoveToObject(self, c, obj):
        if IN_GAME and obj is not None:
            try:
                c.me.run_to(obj.location)
            except Exception:
                pass
        return 2
    def CutSceneId(self, c, obj): return None
    def SetInterrupt(self, c, flag): return None
    def CreateCreature(self, c, cre, pt, face=0):
        log('IE_UNSUPPORTED CreateCreature %s at %r (needs CRE -> proto guidance)' % (cre, pt))
    def SetHomeLocation(self, c, pt): return None
    def MoveToSavedLocationn(self, c, name, scope): return None
    MoveToSavedLocation = MoveToSavedLocationn
    def AttackReevaluate(self, c, obj, ticks): self.Attack(c, obj); return max(1, ticks // 15)
    def DisplayStringNoNameDlg(self, c, obj, strref): return self.DisplayStringHead(c, obj, strref)
    DisplayStringNoName = DisplayStringNoNameDlg
    def AddJournalEntry(self, c, strref, kind=0): log('JOURNAL %s' % text(strref))
    def EraseJournalEntry(self, c, strref): log('JOURNAL_ERASE %d' % strref)
    def SetQuestDone(self, c, strref): log('QUEST_DONE %d' % strref)
    def AddXP2DA(self, c, row):
        xp = XP2DA.get(row.upper())
        log('XP2DA %s -> %s' % (row, xp))
        if xp:
            self.AddXPVar(c, row, xp)
    def RevealAreaOnMap(self, c, area): log('REVEAL %s' % area)
    def StartMovie(self, c, res): log('MOVIE %s (not played)' % res)
    def ReturnToSavedLocation(self, c): return None
    def LeaveAreaLUA(self, c, area, parchment, pt, face=0):
        m = AREA_MAPS.get(area.upper())
        log('LEAVE_AREA %s -> map %s' % (area, m))
        if m and IN_GAME:
            u, v = ie_to_tile(area, pt[0], pt[1])
            game.fade_and_teleport(0, 0, 0, m, u, v)
    LeaveArea = LeaveAreaLUA
    def StartCutSceneMode(self, c): log('CUTSCENE_MODE on')
    def EndCutSceneMode(self, c): log('CUTSCENE_MODE off')
    def HideCreature(self, c, obj=None, flag=1):
        o = obj or c.me
        if IN_GAME and o is not None:
            (o.object_flag_set if flag else o.object_flag_unset)(OF_OFF)
    def ChangeEnemyAlly(self, c, obj, ea):
        if ea in (255, 200):
            self.Enemy(Ctx(obj, c.other, c.ident, c.area))

    # ---- spells (ie_spellrt: IE resref / SPELL.IDS -> Temple+ spell via the converter's ie_spellmap). A cast takes
    # one IE round (6 s); Temple+ runs it as a normal cast action of the caster.
    def _cast(self, c, obj, spell, mode, pt=None):
        if not IN_GAME:
            log('SPELL %s %s -> %r' % (mode, spell, obj)); return 6
        r = _round_for(c)
        if MODE.get('probe') and (mode != 'apply' or obj is None or obj == c.me):
            MODE['fail'].append('%s %s' % (mode, spell)); return None
        if r is not None and (mode != 'apply' or obj is None or obj == c.me):
            import ie_spellrt
            res = ie_spellrt.resref(spell)
            tgt = obj
            if pt is not None and tgt is None:
                tgt = ie_spellrt._near_point(c.me, ie_to_tile(c.area, pt[0], pt[1]))
            m = 'force' if mode == 'apply' else mode
            if MODE['dry']:
                code, p = r.check_spell(res, tgt, m)
                if code:
                    MODE['fail'].append('%s %s: %s' % (mode, res, _reason(code)))
            else:
                r.plan_spell(res, tgt, m)
            return None
        try:
            import ie_spellrt
            ie_spellrt.LOG[0] = LOG_PATH
            point = ie_to_tile(c.area, pt[0], pt[1]) if pt is not None else None
            ie_spellrt.cast(c.me, spell, obj, mode, point)
        except Exception as e:
            log('IE_ERR spell %s %s: %s' % (mode, spell, e))
        return 6
    def Spell(self, c, obj, spell): return self._cast(c, obj, spell, 'spell')
    def SpellNoDec(self, c, obj, spell): return self._cast(c, obj, spell, 'spell')
    def ForceSpell(self, c, obj, spell): return self._cast(c, obj, spell, 'force')
    def ForceSpellRange(self, c, obj, spell): return self._cast(c, obj, spell, 'force')
    def ReallyForceSpell(self, c, obj, spell): return self._cast(c, obj, spell, 'really')
    def ReallyForceSpellDead(self, c, obj, spell): return self._cast(c, obj, spell, 'really')
    def ApplySpell(self, c, obj, spell): return self._cast(c, obj, spell, 'apply')
    def SpellPoint(self, c, pt, spell): return self._cast(c, None, spell, 'spell', pt)
    def SpellPointNoDec(self, c, pt, spell): return self._cast(c, None, spell, 'spell', pt)
    def ForceSpellPoint(self, c, pt, spell): return self._cast(c, None, spell, 'force', pt)
    def ForceSpellPointRange(self, c, pt, spell): return self._cast(c, None, spell, 'force', pt)
    def ReallyForceSpellPoint(self, c, pt, spell): return self._cast(c, None, spell, 'really', pt)
    # EE ...RES forms compile to the same opcode (the resref arrives in the spell slot), but keep the names callable
    SpellRES, ForceSpellRES, ReallyForceSpellRES, ApplySpellRES = Spell, ForceSpell, ReallyForceSpell, ApplySpell
    SpellPointRES, ForceSpellPointRES, ReallyForceSpellPointRES = SpellPoint, ForceSpellPoint, ReallyForceSpellPoint

A = _Actions()

def _walk(o, u, v):
    loc = location_from_axis(u, v)
    try:   # ToEE NPCs walk back to their standpoint when idle: move it with them (IE has no such pull)
        for sp in (STANDPOINT_DAY, STANDPOINT_NIGHT):
            o.standpoint_set(sp, -1, loc, game.leader.map, 0.0, 0.0)
    except Exception as e:
        log_once('standpoint', 'IE_ERR standpoint_set: %s' % e)
    try:
        o.run_to(loc)       # Temple+: makes NPCs path to the location (walk/run per AI)
    except Exception:
        o.move(loc)

def _destroy(o):
    try:
        o.destroy()
    except Exception:
        pass
    return 1

def create_item_in_inventory(proto, obj):
    try:
        it = game.obj_create(proto, obj.location)
        obj.item_get(it)
    except Exception as e:
        log('IE_ERR create item %s: %s' % (proto, e))

# XPLIST.2DA style rows used by AddXP2DA (filled from the player's 2DA by the converter: ie_xp.py)
XP2DA = {}
try:
    import ie_xp
    XP2DA = ie_xp.XP
except ImportError:
    pass

# IE area -> ToEE map id (+ placements), written by the converter as ie_areas.py
AREA_MAPS = {}
try:
    import ie_areas
    AREA_MAPS = ie_areas.MAPS
    for _a, _p in getattr(ie_areas, 'PLACEMENTS', {}).items():
        set_placement(_a, *_p)
except ImportError:
    pass

# text lookup for strrefs used by actions (FloatMessage...); the converter writes ie_strings.py from dialog.tlk
STRINGS = {}
try:
    import ie_strings
    STRINGS = ie_strings.STRINGS
except ImportError:
    pass

def text(strref):
    return STRINGS.get(strref, '[strref %d]' % strref)

# ------------------------------------------------------------------------------------------------ scripts
DEBUG_BLOCKS = False
_lastblock = {}
ROUND_SECS = 1      # IE evaluates scripts once per AI round (~1 s)
_last_tick = {}
_first = {}

def run_script(c, blocks):
    """IE script round: blocks = [(cond_fn, [(weight, [action_fns])])]. Top-down; the first block whose condition
    holds runs one weighted-random response. If that response ends with Continue(), evaluation goes on."""
    for cond, responses in blocks:
        try:
            ok = cond(c)
        except Exception as e:
            log('IE_ERR condition in %s: %s' % (c.ident, e)); ok = False
        if not ok:
            continue
        resp = _pick(responses)
        if resp is None:
            continue
        bi = blocks.index((cond, responses)) if DEBUG_BLOCKS else -1
        if DEBUG_BLOCKS and _lastblock.get(c.ident) != bi:
            _lastblock[c.ident] = bi
            log('BLOCK %s #%d' % (c.ident, bi))
        acts = list(resp)
        cont = bool(acts) and getattr(acts[-1], 'is_continue', False)
        if MODE['round']:
            # combat round (san_start_combat): dry-run the response first; if one of its Spell/Attack actions is not
            # feasible right now (no slot, out of range, no LOS, target already affected, ...) the block does not fire
            # and evaluation falls through to the next block, as if its trigger had been false.
            MODE['dry'] = True; MODE['fail'] = []
            try:
                for fn in acts:
                    try:
                        fn(c)
                    except Exception:
                        pass
            finally:
                MODE['dry'] = False
            if MODE['fail']:
                log('BLOCK %s #%d not feasible: %s' % (c.ident, blocks.index((cond, responses)), '; '.join(MODE['fail'])))
                continue
        elif IN_GAME and _hostile_npc(c.me):
            # a hostile creature outside a combat round: Spell/Attack would start combat out of turn order (the cast
            # used to land before round 1).  Defer the block: KOS makes Temple+ start combat, and the round evaluates it.
            MODE['dry'] = True; MODE['probe'] = True; MODE['fail'] = []
            try:
                for fn in acts:
                    try:
                        fn(c)
                    except Exception:
                        pass
            finally:
                MODE['dry'] = False; MODE['probe'] = False
            if MODE['fail']:
                if _lastdefer.get(c.ident) != blocks.index((cond, responses)):
                    _lastdefer[c.ident] = blocks.index((cond, responses))
                    log('DEFER %s #%d to the combat round: %s' % (c.ident, _lastdefer[c.ident], '; '.join(MODE['fail'])))
                return True
        run_actions(c, acts)
        if not cont:
            return True
    return False

def _pick(responses):
    tot = sum([w for w, a in responses])
    if tot <= 0:
        return responses and responses[0][1] or None
    r = random.randint(1, tot)
    for w, a in responses:
        r -= w
        if r <= 0:
            return a
    return responses[-1][1]

def tick(obj, ident, area, scripts, force=False):
    """Run one script round for a creature/area. `scripts` = list of generated BCS modules in IE priority order
    (override, specifics, class, race, general, default). Throttled to ROUND_SECS; skipped while the object's
    action queue is busy (unless an event is pending)."""
    now = _now()
    ev = _events.setdefault(ident, {})
    if ident not in _first:
        _first[ident] = 1; ev['OnCreation'] = obj
        bind(obj, ident, area)
        script_ai(obj, ident, scripts)
    if not force and now - _last_tick.get(ident, -99) < ROUND_SECS:
        return
    if not MODE['round'] and IN_GAME and _in_combat(obj):
        return                         # turn-based combat: the critter's script runs from san_start_combat only
    _last_tick[ident] = now
    if _busy.get(ident, 0) > now and not ev:
        return
    c = Ctx(obj, None, ident, area, ev)
    for m in scripts:
        if run_script(c, m.BLOCKS):
            break
    # IE: AttackedBy/HitBy are true for one script round; left pending they also bypassed the busy check above, so
    # a heal cast was issued again on the next tick before the first resolved (double-spent IE count, EE test)
    for k in ('AttackedBy', 'HitBy'):
        ev.pop(k, None)

def script_ai(obj, ident, scripts):
    """SPL-ADJ-18: a creature whose IE scripts cast spells keeps only the non-spell part of its Temple+ AI strategy."""
    if not IN_GAME or not [m for m in scripts if getattr(m, 'CASTS', False)]:
        return
    try:
        import ie_spellrt
        if ie_spellrt.script_first(obj):
            log('SCRIPT_AI %s: IE script casts; Temple+ strategy without spells' % ident)
    except Exception as e:
        log('IE_ERR script_ai %s: %s' % (ident, e))

_lastdefer = {}

def _hostile_npc(obj):
    try:
        return (obj is not None and obj.type == obj_t_npc and obj.leader_get() == OBJ_HANDLE_NULL
                and (obj.npc_flags_get() & ONF_KOS) != 0)
    except Exception:
        return False

def _in_combat(obj):
    try:
        return game.combat_is_active() and obj.type == obj_t_npc   # rounds belong to san_start_combat
    except Exception:
        return False

def _round_for(c):
    """The ie_combat.Round being planned for this actor, or None (outside san_start_combat / another actor)."""
    if not MODE['round'] or not IN_GAME:
        return None
    import ie_combat
    r = ie_combat.CUR[0]
    return r if r is not None and c.me == r.npc else None

def _reason(code):
    import ie_combat
    return ie_combat.REASON.get(code, code)

def _foes(me):
    out = []
    try:
        for o in game.obj_list_vicinity(me.location, OLC_CRITTERS):
            if o != me and not _dead(o) and _hostile(me, o):
                out.append(o)
    except Exception:
        pass
    return out

def combat_round(obj, ident, area, scripts):
    """san_start_combat, every turn of the critter: one IE script round with feasibility checks (ie_combat). The
    first feasible block's Spell/Attack becomes this round's Temple+ strategy; with no feasible block the converted
    static strategy is the fallback. Both end in "stop", so Temple+ never adds its own DefaultCast."""
    if not IN_GAME:
        return 1
    if ident not in _first:
        _first[ident] = 1; bind(obj, ident, area); script_ai(obj, ident, scripts)
    _busy.pop(ident, None)
    import ie_combat, ie_spellrt
    ie_combat.LOG[0] = LOG_PATH; ie_spellrt.LOG[0] = LOG_PATH
    def run(r):
        MODE['round'] = True
        try:
            tick(obj, ident, area, scripts, force=True)
        finally:
            MODE['round'] = False; MODE['dry'] = False
    return ie_combat.round_start(obj, ident, _foes(obj), run, ie_spellrt.strategy_of(obj), ie_spellrt.script_first_on())

def event(ident, name, other=None):
    """Hook helper for san_* handlers: record an IE event trigger (AttackedBy, HitBy, Die, Entered...)."""
    _events.setdefault(ident, {})[name] = other

def loop(obj, ident, area, mods, period_ms=1000):
    """Drive tick() from a time event (used for area scripts and in tests; creatures use san_heartbeat)."""
    _loops[ident] = (obj, area, mods, period_ms)
    game.timeevent_add(_loop_step, (obj, ident), period_ms, 1)

_loops = {}

def _loop_step(obj, ident):
    ent = _loops.get(ident)
    if not ent:
        return 1
    o, area, mods, period = ent
    try:
        tick(o, ident, area, mods, force=True)
    except Exception as e:
        log('IE_ERR tick %s: %s' % (ident, e))
    game.timeevent_add(_loop_step, (obj, ident), period, 1)
    return 1

def stop_loop(ident):
    _loops.pop(ident, None)

def CONT(c):
    """Continue(): marks a response whose script evaluation goes on to the next block."""
    return CONTINUE
CONT.is_continue = True

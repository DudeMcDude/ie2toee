"""Script/area spawns for converted IE creatures (ToEE side, Python 2.2-compatible style).

* CreateCreature("cre", [x.y], face) -> ie_spawnables.SPECS[cre] (converted by ie_creatures.py spawnables), placed at the
  IE point of the calling script's area ([-1.-1] = next to the caller), IE facing -> ToEE rotation.
* Generic monsters get a per-instance portrait: the spec carries its family pool ('portrait_pool', the upgraded pool for
  elite resrefs, flips included) and one is picked by a stable hash of resref + area + point + spawn count.
* Area .INI spawns (ie_spawnables.INI_SPAWNS[area], parsed by ieformats.parse_spawn_ini): the [spawn_main] enter=
  groups run on every area load, events= groups every `interval` IE ticks (15/s of game time) from the map tick.
  Per critter: spec_var condition (GLOBAL, equal_to / greater_than / less_than; no operation = always) and
  spec_var_inc, spec_qty = cap on living copies (counted by converted name), create_qty per run, spawn_point list
  (point_select s = sequential, else random), script_name = the IE name scripts address it by.
* A spawn whose CRE has a dialog or scripts gets the spec's script_id: the generated pyNNNNNie_<ident>.py (written
  by ie_dialogue.py with AREA = "") runs its override/class/race/general/default BCS and its dialogue, per instance
  (instance_ident + ie_runtime.who), like a .mob-placed actor.
* Several spawns of one batch go to distinct free tiles near their point (ie_critters.free_spot).
* Rest encounters (ARE rest table -> REST[area]): hook_rest() wraps Co8's random_encounter.can_sleep /
  check_sleep_encounter / encounter_create in memory (installed when an IE area starts; the file is not touched).
  On a map that is not a converted IE area the wrappers call the original Co8 function unchanged.
"""
from toee import *
import ie_runtime as rt

_DATA = [None]
_N = [0]

def _data():
    if _DATA[0] is None:
        try:
            import ie_spawnables
            _DATA[0] = ie_spawnables
        except ImportError:
            _DATA[0] = 0
    return _DATA[0]

def _hash(s):
    try:
        import zlib
        return zlib.crc32(s) & 0xffffffffL
    except Exception:
        h = 0
        for ch in s:
            h = (h * 31 + ord(ch)) & 0xffffffffL
        return h

def portrait_for(s, seed):
    pool = s.get('portrait_pool')
    if pool:
        return pool[int(_hash('%s:%s' % (s.get('resref', '').lower(), seed)) % len(pool))]
    return s.get('portrait')

def spawn(res, area, u, v, face=None, seed=None, near=None, taken=None, ident=None, script_id=None):
    """Spawn converted CRE `res` at tile (u, v); returns the object or None."""
    d = _data()
    s = d and d.SPECS.get(res.lower())
    if not s:
        rt.log_once('spawn:' + res.lower(), 'IE_UNSUPPORTED CreateCreature %s (no converted spec)' % res)
        return None
    import ie_critters as cr
    from utilities import location_from_axis
    s = dict(s)
    _N[0] += 1
    por = portrait_for(s, seed or '%s:%d:%d:%d' % (area.upper(), u, v, _N[0]))
    if por:
        s['portrait'] = por
    if face is not None:
        s['orient'] = face
    try:
        o = cr.spawn(s, location_from_axis(u, v), script_id)
        try:
            cr.place_near(o, u, v, _taken() if taken is None else taken)
        except Exception:
            pass
    except Exception, e:
        rt.log('IE_ERR spawn %s: %s' % (res, e)); return None
    rt.bind(o, instance_ident(ident or s.get('ident') or res.lower()), area)
    rt.log('SPAWN %s at tile(%d,%d) portrait %s' % (res, u, v, por))
    if script_id or s.get('script_id'):
        game.timeevent_add(_heartbeat, (o, 1), HEARTBEAT_MS, 1)
    return o

# The engine schedules NPC heartbeats only for objects whose scripts were set when they entered the map, so a
# runtime spawn's san_first_heartbeat / san_heartbeat would never run: drive them from a time event instead
# (tick() is throttled to ROUND_SECS, so an engine heartbeat on top of this does no harm).
HEARTBEAT_MS = 1000

def _heartbeat(o, first=0):
    try:
        if o == OBJ_HANDLE_NULL or (o.object_flags_get() & (OF_DESTROYED | OF_OFF)):
            return 0
        if first:
            o.object_script_execute(o, san_first_heartbeat)
        if o.stat_level_get(stat_hp_current) <= -10:
            return 0
        o.object_script_execute(o, san_heartbeat)
    except Exception, e:
        rt.log('IE_ERR spawn heartbeat %s: %s' % (o, e)); return 0
    game.timeevent_add(_heartbeat, (o, 0), HEARTBEAT_MS, 1)
    return 0

def create(c, res, pt, face=0):
    """IE CreateCreature(res, point, face)."""
    if not rt.IN_GAME:
        rt.log('SPAWN %s at %r (dry)' % (res, pt)); return None
    x, y = (pt[0], pt[1]) if isinstance(pt, (tuple, list)) and len(pt) >= 2 else (-1, -1)
    if x < 0 or y < 0:
        from utilities import location_to_axis
        me = c.me or game.leader
        u, v = location_to_axis(me.location)
    else:
        u, v = rt.ie_to_tile(c.area, x, y)
    return spawn(res, c.area or '', u, v, face, seed='%s:%s:%s' % ((c.area or '').upper(), x, y) if x >= 0 and _N[0] == 0 else None)

_IDS = {}

def instance_ident(base):
    """First copy answers to the IE script name itself (N("Veira")); further copies get base#2, base#3.. so each runs
    its own script round, timers and events (ie_runtime keys those by ident)."""
    n = _IDS.get(base, 0) + 1
    _IDS[base] = n
    if n == 1:
        return base
    return '%s#%d' % (base, n)

_TK = {'t': None, 'at': -99999}

def _taken():
    """Tiles handed out to spawns of the current burst (calls within 2 s share it), so they do not stack."""
    now = rt._now()
    if _TK['t'] is None or now - _TK['at'] > 2000:
        _TK['t'] = set()
    _TK['at'] = now
    return _TK['t']

def _gsecs():
    try:
        return game.time.time_game_in_seconds(game.time)
    except Exception:
        return rt._now() / 1000

def _rsecs():
    try:
        import time
        return time.time()
    except Exception:
        return rt._now() / 1000

def _alive_named(nid, near):
    n = 0
    try:
        import ie_critters as cr
        f = cr._c('obj_f_description')
        for o in game.obj_list_vicinity(near, OLC_NPC):
            if o.obj_get_int(f) == nid and o.stat_level_get(stat_hp_current) > -10:
                n += 1
    except Exception:
        pass
    return n

_SEQ = {}

def _cond(c):
    v = c.get('var')
    if not v:
        return 1
    x, want, op = rt.get_var(None, v, 'GLOBAL') or 0, c.get('value', 0), c.get('op')
    if op == 'equal_to': return x == want
    if op == 'greater_than': return x > want
    if op == 'less_than': return x < want
    if op == 'not_equal_to': return x != want
    if op == 'less_or_equal_to': return x <= want
    if op == 'greater_or_equal_to': return x >= want
    return x != 0          # spec_var without an operation: spawn while the variable is set (GemRB IniSpawn)

SPECIFICS = {}     # object key -> IE SPECIFICS (INI ai_specifics), for spec = [..specifics] counts
SEE_FT = 90        # "the party can see the point": a party member this close (ToEE has no IE visibility map)

def _area_diff(area):
    """IWD2 area difficulty 1..3: average party level against the ARE V9.1 thresholds (ini['diff'])."""
    t = (_ini(area) or {}).get('diff')
    if not t:
        return 1
    try:
        p = [x for x in game.party]
        lvl = sum([x.stat_level_get(stat_level) for x in p]) / max(1, len(p))
    except Exception:
        return 1
    if t[1] and lvl >= t[1]: return 3
    if t[0] and lvl >= t[0]: return 2
    return 1

def _seen(loc):
    try:
        for p in game.party:
            if p.distance_to(loc) < SEE_FT:
                return 1
    except Exception:
        pass
    return 0

def _alive(o):
    try:
        return o.stat_level_get(stat_hp_current) > -10 and not (o.object_flags_get() & OF_DESTROYED)
    except Exception:
        return 0

def _count_spec(spec):
    """Living spawns matching an INI spec [EA.GENERAL.RACE.CLASS.SPECIFICS..]: by SPECIFICS (the only field the
    IWD2 INIs set); None when the spec names nothing countable."""
    if len(spec) < 6 or not spec[5]:
        return None
    n = 0
    for k, sp in SPECIFICS.items():
        if sp == spec[5]:
            try:
                o = game.get_obj_by_id(k)
            except Exception:
                o = None
            if o and _alive(o):
                n += 1
    return n

def ini_critter(area, c):
    """Run one INI critter section; returns the number spawned."""
    d = _data()
    s = d and d.SPECS.get(c['cre'])
    if not s or not c.get('points') or not _cond(c):
        return 0
    if c.get('no_diff') and _area_diff(area) in c['no_diff']:
        return 0
    if c.get('spec_name') and rt.N(None, c['spec_name']) is not None:
        return 0
    if c.get('select') == 's':
        k = _SEQ.get((area, c['name']), 0); _SEQ[(area, c['name'])] = k + 1
        x, y, f = c['points'][k % len(c['points'])]
    else:
        x, y, f = c['points'][game.random_range(0, len(c['points']) - 1)]
    u, v = rt.ie_to_tile(area, x, y)
    from utilities import location_from_axis
    loc = location_from_axis(u, v)
    if not c.get('ignore_can_see') and _seen(loc):
        return 0
    qty = c.get('qty', 1)
    if c.get('spec_qty'):
        have = _count_spec(c['spec']) if c.get('spec') else None
        if have is None:
            have = _alive_named(s.get('name_id'), loc)
        qty = min(qty, c['spec_qty'] - have)
    n = 0
    for i in range(max(0, min(qty, 12))):
        o = spawn(c['cre'], area, u, v, f, ident=c.get('ident') or (c.get('script_name') or '').lower() or None,
                  script_id=c.get('script_id'))
        if o:
            n += 1
            sp = (c.get('ai') or {}).get('specifics')
            if sp:
                SPECIFICS[rt._key(o)] = sp
    if n and c.get('inc'):
        rt.set_var(None, c['var'], 'GLOBAL', (rt.get_var(None, c['var'], 'GLOBAL') or 0) + c['inc'] * n)
    return n

def _ini(area):
    d = _data()
    return d and getattr(d, 'INI_SPAWNS', {}).get(area.upper())

def area_spawns(area):
    """INI enter= groups: run on each load of the area (spec_qty / spec_var keep them from piling up)."""
    ini = _ini(area)
    if not ini or not rt.IN_GAME:
        return 0
    n = 0
    for g in ini.get('enter', ()):
        for c in g['critters']:
            n += ini_critter(area.upper(), c)
    rt.log('AREA_SPAWNS %s enter: %d creatures' % (area.upper(), n))
    return n

_EV = {}

def tick(area):
    """INI events= groups, from the area map tick: each group every interval/15 seconds. Counted in game time
    (so resting 8 hours fires an 8-hour group) or in real time on the map, whichever passed first (the ToEE clock
    stands still while nothing happens)."""
    ini = _ini(area)
    if not ini or not ini.get('events'):
        return 0
    g_now, r_now, n = _gsecs(), _rsecs(), 0
    for g in ini['events']:
        key = (area.upper(), g['name'])
        per = max(1, g.get('interval', 1) / 15)
        last = _EV.get(key)
        if last is None:
            _EV[key] = (g_now, r_now); continue
        if g_now - last[0] >= per or r_now - last[1] >= per:
            _EV[key] = (g_now, r_now)
            k = n
            for c in g['critters']:
                n += ini_critter(area.upper(), c)
            if n > k:
                rt.log('AREA_SPAWNS %s event %s: %d creatures' % (area.upper(), g['name'], n - k))
    return n

# --- rest encounters (None from a hook = not an IE map: the Co8 original runs) ---
def hook_rest():
    try:
        import random_encounter as m
    except Exception, e:
        rt.log_once('resthook', 'IE_ERR rest hook: random_encounter: %s' % e); return 0
    if getattr(m, '_ie2toee_rest', 0):
        return 1
    def wrap(orig, hook):
        def f(*a):
            try:
                r = hook(*a[-1:])
            except Exception, e:
                rt.log('IE_ERR rest hook %s: %s' % (orig.__name__, e)); r = None
            if r is None:
                return orig(*a)
            return r
        return f
    m.can_sleep = wrap(m.can_sleep, lambda *a: rest_can_sleep())
    m.check_sleep_encounter = wrap(m.check_sleep_encounter, rest_check)
    m.encounter_create = wrap(m.encounter_create, rest_spawn)
    m._ie2toee_rest = 1
    rt.log('REST_HOOK installed')
    return 1

REST_ID = 4900
FORCE = [0]      # tests: 1 = next rest check hits

def _cur_area():
    try:
        m = game.leader.map
    except Exception:
        return None
    for a, mm in rt.AREA_MAPS.items():
        if mm == m:
            return a.upper()
    return None

def _rest(a):
    d = _data()
    return d and getattr(d, 'REST', {}).get(a)

def rest_can_sleep():
    a = _cur_area()
    if a is None:
        return None
    return _rest(a) and SLEEP_DANGEROUS or SLEEP_SAFE

def rest_check(encounter):
    a = _cur_area()
    if a is None:
        return None
    r = _rest(a)
    if not r:
        return 0
    try:
        day = game.is_daytime()
    except Exception:
        day = 1
    ch = day and r.get('day', 0) or r.get('night', 0)
    hit = FORCE[0] or game.random_range(1, 100) <= ch
    rt.log('REST_CHECK %s chance %d%% -> %s' % (a, ch, hit and 'encounter' or 'quiet'))
    if not hit:
        return 0
    FORCE[0] = 0
    encounter.id = REST_ID
    encounter.map = game.leader.map
    return 1

def rest_spawn(encounter):
    if encounter.id != REST_ID:
        return None
    a = _cur_area()
    r = a and _rest(a)
    if not r:
        return 0
    d = _data()
    cres = [c for c in r['creatures'] if c in d.SPECS]
    if not cres:
        rt.log('REST_SPAWN %s: no converted creature in %r' % (a, r['creatures'])); return 0
    n_ = max(1, min(r.get('max') or 1, (r.get('difficulty') or 1) + game.random_range(0, 1)))
    from utilities import location_to_axis
    u, v = location_to_axis(game.leader.location)
    taken, n = set(), 0
    for k in range(n_):
        if spawn(cres[game.random_range(0, len(cres) - 1)], a, u + game.random_range(-4, 4), v + game.random_range(-4, 4), taken=taken):
            n += 1
    rt.log('REST_SPAWN %s: %d creatures' % (a, n))
    return 1

# --- summon spells (ie_spellmap.SUMMONS, from SPL opcode 67 / IWD2 410 friendly, 411 hostile) ---
SUMMON_SECS = 300      # IE duration 0: no fixed time; ToEE has no dismissal UI for these, so they leave after 5 min

def _caster_level(o):
    try:
        return max(1, o.stat_level_get(stat_level))
    except Exception:
        return 1

def _unsummon(o):
    try:
        if o.stat_level_get(stat_hp_current) > -10:
            try:
                o.leader_get().ai_follower_remove(o)
            except Exception:
                pass
            o.destroy()
            rt.log('UNSUMMON %s' % o)
    except Exception:
        pass
    return 0

def summon(caster, res, target=None, pt=None):
    """IE summon spell cast by a script (Spell/ForceSpell...): roll the ability band for the caster level, create
    the IE creature(s) next to the target point / target / caster, on the caster's side (opcode 411: against it),
    and dismiss them when the duration ends. Returns the number summoned, or None if `res` is no summon spell."""
    try:
        import ie_spellmap
        bands = getattr(ie_spellmap, 'SUMMONS', {}).get(res)
    except ImportError:
        bands = None
    if not bands:
        return None
    lvl = _caster_level(caster)
    band = bands[0][1]
    for m, l in bands:
        if m <= lvl:
            band = l
    roll = game.random_range(1, 100)
    pick = [x for x in band if x[0] <= roll <= x[1]] or band[-1:]
    lo, hi, cre, n, secs, side = pick[0]
    from utilities import location_to_axis
    if pt is not None:
        u, v = pt
    else:
        u, v = location_to_axis((target or caster).location)
    area = _cur_area() or ''
    party = caster in game.party or caster.leader_get() != OBJ_HANDLE_NULL
    kos = (caster.npc_flags_get() & ONF_KOS) != 0 if caster.type == obj_t_npc else 0
    if side == 'foe':
        party, kos = 0, not kos or party
    taken, k = set(), 0
    for i in range(max(1, min(n, 8))):
        o = spawn(cre, area, u, v, taken=taken)
        if o is None:
            continue
        k += 1
        try:
            if party:
                o.npc_flag_unset(ONF_KOS)
                (caster.leader_get() if caster.type == obj_t_npc and caster.leader_get() != OBJ_HANDLE_NULL
                 else caster).ai_follower_add(o)
            elif kos:
                o.npc_flag_set(ONF_KOS)
                if game.combat_is_active():
                    o.attack(game.leader)
            else:
                o.npc_flag_unset(ONF_KOS)
        except Exception, e:
            rt.log('IE_ERR summon side %s: %s' % (cre, e))
        game.timeevent_add(_unsummon, (o,), int(1000 * (secs or SUMMON_SECS)), 1)
    rt.log('SUMMON %s by %s (lvl %d, roll %d): %d x %s side %s for %ds' % (
        res, caster, lvl, roll, k, cre, party and 'party' or kos and 'hostile' or 'neutral', secs or SUMMON_SECS))
    return k

# ie2toee runtime: IE spells -> Temple+ casting (Python 2.7, runs inside Temple+; importable offline for tests).
#
#   give_spells(obj, spec)          converted NPC spell lists (ie_creatures "spells" / "ai_strategy") -> known +
#                                   memorised Temple+ spells and a custom AI strategy that casts them
#   cast(caster, res, target, mode) IE script spell actions (Spell, ForceSpell, ReallyForceSpell, ApplySpell, *Point)
#
# The IE resref -> Temple+ spell map is ie_spellmap.MAP, written on the player's machine by
# `ie_spells.py convert` (it names spells from both games, so it is never distributed). See docs/spells.md.
try:
    from toee import *
    import toee
    IN_GAME = True
except ImportError:
    IN_GAME = False
    toee = None

MAP = {}
try:
    import ie_spellmap
    MAP = ie_spellmap.MAP
except ImportError:
    pass

DOMAIN_SPECIAL = 23          # Temple+ Domain_Special: monster spell-like abilities, caster level = hit dice
KEY_STAT = {'clr': 'stat_level_cleric', 'drd': 'stat_level_druid', 'wiz': 'stat_level_wizard',
            'sor': 'stat_level_sorcerer', 'brd': 'stat_level_bard', 'pal': 'stat_level_paladin',
            'rgr': 'stat_level_ranger'}
TYPE_KEYS = {'wizard': ('wiz', 'sor', 'brd'), 'priest': ('clr', 'drd', 'pal', 'rgr')}
FORCE_MODES = ('force', 'really', 'apply')
LOG = [None]
_given = {}                  # object key -> {resref: memorised count} (HaveSpell; Spell decrements, like IE)


def _okey(o):
    try:
        return str(o.id)
    except Exception:
        return str(o)


def slots(o, sid):
    """Unused memorised Temple+ slots of spell enum sid (None if the engine can't tell). Keeps the IE counts honest
    when the Temple+ AI strategy has already spent a slot."""
    try:
        n = 0
        for m in o.spells_memorized:
            if m.spell_enum == sid and not m.is_used_up():
                n += 1
        return n
    except Exception:
        return None


def have(o, spell):
    res = resref(spell)
    if not (res and _given.get(_okey(o), {}).get(res, 0) > 0):
        return False
    e = entry(res)
    left = slots(o, int(e['t'])) if e and e.get('t') is not None else None
    return left is None or left > 0


def log(msg):
    line = 'IE_SPELL ' + msg
    if LOG[0]:
        try:
            f = open(LOG[0], 'a'); f.write(line + '\n'); f.close()
        except Exception:
            pass
    try:
        print(line)
    except Exception:
        pass


def resref(v):
    """SPELL.IDS number, symbol-resolved number or resref string -> lower-case resref (IE: 1xxx SPPR, 2xxx SPWI,
    3xxx SPIN, 4xxx SPCL + the last three digits)."""
    if isinstance(v, str) or type(v).__name__ == 'unicode':
        return v.lower() or None
    try:
        v = int(v)
    except Exception:
        return None
    pre = {1: 'sppr', 2: 'spwi', 3: 'spin', 4: 'spcl'}.get(v // 1000)
    return pre + '%03d' % (v % 1000) if pre and v > 0 else None


def entry(res):
    return MAP.get(res)


def _stat(key):
    return getattr(toee, KEY_STAT[key])


def class_for(o, e):
    """The Temple+ class key an object casts an IE spell with: one of its own casting classes that has the mapped
    spell on its list, else domain_special (monsters / innate abilities, SPL-ADJ-6/7)."""
    keys = TYPE_KEYS.get(e.get('ty'), ())
    for k in keys:
        if k in e.get('lv', {}) and o.stat_level_get(_stat(k)) > 0:
            return k
    for k in keys:
        if o.stat_level_get(_stat(k)) > 0:
            return k
    return 'domain_special'


def level_for(e, key):
    if key != 'domain_special' and key in e.get('lv', {}):
        return e['lv'][key]
    return max(1, min(9, e.get('l') or 1))


def grant(o, sid, key, lvl, n=1):
    """Add a known spell plus n memorised copies (n may be 0 for a wizard's spellbook-only spell)."""
    if key == 'domain_special':
        o.spell_known_add(sid, DOMAIN_SPECIAL, lvl, 1)
        for _ in range(n):
            o.spell_memorized_add(sid, DOMAIN_SPECIAL, lvl, 1)
    else:
        st = _stat(key)
        o.spell_known_add(sid, st, lvl)
        for _ in range(n):
            o.spell_memorized_add(sid, st, lvl)


def give_spells(o, spec):
    got = []
    for s in spec.get('spells') or ():
        try:
            grant(o, int(s['toee']), s['cls'], int(s['lvl']), int(s.get('n', 0)))
            d = _given.setdefault(_okey(o), {})
            d[s['res']] = d.get(s['res'], 0) + int(s.get('n', 0))
            got.append((s['res'], s['toee'], s['cls'], s['lvl'], s.get('n', 0)))
        except Exception, e:
            log('grant %s failed: %s' % (s, e))
    strat = spec.get('ai_strategy')
    _strategy[_okey(o)] = strat
    if strat:
        try:
            o.ai_strategy_set_custom(list(strat), 1)
        except Exception, e:
            log('ai_strategy_set_custom failed: %s' % e)
    return got


_strategy = {}               # object key -> converted static strategy (the per-round fallback, ie_combat)

def strategy_of(o):
    return _strategy.get(_okey(o))

def script_first_on():
    try:
        from ie_spellmap import OPTIONS
    except Exception:
        OPTIONS = {}
    return OPTIONS.get('npc_ai', 'script_first') == 'script_first'


MELEE = ['ie2toee_script', 'use potion', '', '', 'attack', '', '', 'approach', '', '', 'attack', '', '']
_script_first = {}

def script_first(o):
    """SPL-ADJ-18 'script_first': replace the converted strategy with its non-spell tail (once per creature)."""
    try:
        from ie_spellmap import OPTIONS
    except Exception:
        OPTIONS = {}
    k = _okey(o)
    if OPTIONS.get('npc_ai', 'script_first') != 'script_first' or k in _script_first:
        return False
    _script_first[k] = 1
    o.ai_strategy_set_custom(list(MELEE), 1)
    return True


def _near_point(caster, pt):
    """IE *Point actions target a location; Temple+ cast_spell wants an object: the critter nearest the point
    (area spells are centred on its location), else the caster."""
    try:
        from utilities import location_from_axis
        loc = location_from_axis(pt[0], pt[1])
        best, bd = None, 9999
        for c in game.obj_list_vicinity(loc, OLC_CRITTERS):
            d = c.distance_to(loc) if hasattr(c, 'distance_to') else 0
            if d < bd:
                best, bd = c, d
        if best is not None and bd < 15:
            return best
    except Exception, e:
        log('point target: %s' % e)
    return caster


def cast(caster, spell, target=None, mode='spell', point=None):
    """IE spell action -> Temple+ cast. mode: 'spell' (Spell/SpellNoDec: the caster must have it memorised),
    'force' (ForceSpell: no memorisation needed), 'really' (ReallyForceSpell), 'apply' (ApplySpell: the target
    casts it on itself). Returns the Temple+ spell id cast, or None."""
    res = resref(spell)
    e = entry(res) if res else None
    if not e or e.get('t') is None:
        log('UNMAPPED %s (%s) mode=%s class=%s' % (res, spell, mode, (e or {}).get('c')))
        return None
    if caster is None:
        return None
    if mode == 'apply' and target is not None:
        caster = target
    if point is not None and target is None:
        target = _near_point(caster, point)
    if target is None:
        target = caster
    sid = int(e['t'])
    key = class_for(caster, e)
    lvl = level_for(e, key)
    if mode in FORCE_MODES:
        grant(caster, sid, key, lvl, 1)     # SPL-ADJ-17: force casts do not need the spell memorised
    else:
        d = _given.get(_okey(caster), {})
        if d.get(res, 0) <= 0 or slots(caster, sid) == 0:
            log('NOT_MEMORISED %s by %s (IE Spell() fails)' % (res, caster))
            return None
        d[res] -= 1
    try:
        caster.cast_spell(sid, target)
        log('CAST %s -> %d (%s) by %s on %s mode=%s class=%s lvl=%d' % (res, sid, e.get('n'), caster, target, mode,
                                                                       key, lvl))
        return sid
    except Exception, ex:
        log('cast %s failed: %s' % (res, ex))
        return None

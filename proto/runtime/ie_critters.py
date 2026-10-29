# ie2toee runtime: spawn converted IE creatures (Temple+ Python 2.7).
# The specs come from proto/ie_creatures.py ("convert"), generated on the player's machine from their own install.
# A spec is a plain dict; see ie_creatures.convert_area for the keys. Base template protos are vanilla ToEE NPCs; the
# converted stat block is applied on top of them here, so no proto rows have to be generated.
from toee import *
import toee
from utilities import location_from_axis
import math

def _const(n):   # feat_* / skill_* constant: toee module, else Temple+'s constants module
    if n in globals(): return globals()[n]
    from templeplus import constants
    return getattr(constants, n)

LOG = [None]

def _log(s):
    if LOG[0]:
        f = open(LOG[0], 'a'); f.write(s + '\n'); f.close()

# Object field numbers as Temple+'s obj_get_int/obj_set_int count them (checked in game by dumping a vanilla villager).
# These win over the toee module's constants: below obj_f_hp_pts the vanilla Python constants are off by two
# (toee.obj_f_description is 23, the field holding the description id is 25).
FIELDS = {'obj_f_critter_inventory_source': 311, 'obj_f_critter_alignment': 295, 'obj_f_critter_level_idx': 287,
          'obj_f_npc_hitdice_idx': 387, 'obj_f_model_scale': 8, 'obj_f_description': 25, 'obj_f_hp_pts': 27, 'obj_f_hp_damage': 29,
          'obj_f_critter_gender': 289, 'obj_f_npc_save_reflexes_bonus': 373, 'obj_f_npc_save_fortitude_bonus': 374,
          'obj_f_npc_save_willpower_bonus': 375, 'obj_f_npc_ac_bonus': 376,
          'obj_f_critter_description_unknown': 312}

def _c(name):
    return FIELDS[name] if name in FIELDS else getattr(toee, name, None)

CLASS_STAT = {'fighter': 'stat_level_fighter', 'ranger': 'stat_level_ranger', 'paladin': 'stat_level_paladin',
              'cleric': 'stat_level_cleric', 'druid': 'stat_level_druid', 'wizard': 'stat_level_wizard',
              'sorcerer': 'stat_level_sorcerer', 'rogue': 'stat_level_rogue', 'bard': 'stat_level_bard',
              'monk': 'stat_level_monk', 'barbarian': 'stat_level_barbarian'}
ABIL = ('stat_strength', 'stat_dexterity', 'stat_constitution', 'stat_intelligence', 'stat_wisdom', 'stat_charisma')
SAVE_F = ('obj_f_npc_save_fortitude_bonus', 'obj_f_npc_save_reflexes_bonus', 'obj_f_npc_save_willpower_bonus')
# ToEE equipment slots (item_wield): IE CRE slot name -> ToEE slot
WEAR_SLOT = {'helmet': 0, 'amulet': 1, 'gloves': 2, 'weapon1': 3, 'shield': 11, 'armor': 5, 'lring': 6, 'rring': 7,
             'boots': 8, 'quiver1': 9, 'cloak': 10}
SCRIPT_EVENTS = ('san_dialog', 'san_heartbeat', 'san_first_heartbeat', 'san_dying', 'san_enter_combat', 'san_start_combat')

def _mod(v):
    return (v - 10) // 2

def _set(o, field, v, idx=None):
    f = _c(field)
    if f is None:
        _log('  no field %s' % field); return
    try:
        if idx is None:
            o.obj_set_int(f, v)
        else:
            o.obj_set_idx_int(f, idx, v)
    except Exception, e:
        _log('  set %s failed: %s' % (field, e))

def apply(o, s):
    """Apply a converted stat block to a freshly created critter."""
    _set(o, 'obj_f_critter_inventory_source', 0)   # no random template gear on top of the converted items
    ab = s.get('abilities')
    if ab:
        for k, v in zip(ABIL, ab):
            o.stat_base_set(_c(k), int(v))
    levels = s.get('levels') or []
    hd = s.get('monster_hd')
    # hit dice: class levels replace the template's monster HD; commoners / monsters keep [count, die, bonus]
    if levels:
        for i in range(3):
            _set(o, 'obj_f_npc_hitdice_idx', 0, i)
        n = 0
        for cls, lv in levels:
            st = _c(CLASS_STAT.get(cls, 'stat_level_fighter'))
            for i in range(lv):
                _set(o, 'obj_f_critter_level_idx', st, n); n += 1
        total = n
    elif hd:
        for i in range(3):
            _set(o, 'obj_f_npc_hitdice_idx', int(hd[i]), i)
        total = int(hd[0])
    else:
        total = 1
    con = ab[2] if ab else o.stat_level_get(stat_constitution)
    if s.get('hp'):
        _set(o, 'obj_f_hp_pts', max(1, int(s['hp']) - _mod(con) * total))
        _set(o, 'obj_f_hp_damage', 0)
    if s.get('natural_ac') is not None:
        _set(o, 'obj_f_npc_ac_bonus', int(s['natural_ac']))
    for f, b in zip(SAVE_F, s.get('save_bonus') or ()):
        if b:
            _set(o, f, int(b))
    if s.get('alignment') is not None:
        _set(o, 'obj_f_critter_alignment', int(s['alignment']))
    if s.get('gender'):
        _set(o, 'obj_f_critter_gender', 0 if s['gender'] == 'female' else 1)
    if s.get('scale') and int(s['scale']) != 100:
        _set(o, 'obj_f_model_scale', int(s['scale']))
    if s.get('mesh'):   # a mesh other than the proto's (e.g. IWD2 kegs: barrel mesh on a critter)
        o.obj_set_int(37, int(s['mesh'])); o.obj_set_int(38, int(s['mesh']))   # obj_f_base_mesh, obj_f_base_anim
    if s.get('hostility') == 'hostile':
        o.npc_flag_set(ONF_KOS)
    else:
        o.npc_flag_unset(ONF_KOS)
    if s.get('no_flee') and _c('ONF_NO_FLEE') is not None:  # not a vanilla flag; Temple+ AI reads morale elsewhere
        o.npc_flag_set(_c('ONF_NO_FLEE'))
    if s.get('invulnerable') and _c('OF_INVULNERABLE') is not None:
        o.object_flag_set(OF_INVULNERABLE)
    for c in s.get('conditions') or ():
        try:
            args = list(c[1:]) + [0] * max(0, 2 - len(c[1:]))
            o.condition_add_with_args(c[0], *args)
        except Exception, e:
            _log('  condition %s failed: %s' % (c, e))
    if s.get('to_hit_bonus'):
        _log('  ADJ-6 to-hit bonus +%s not applied (no generic Temple+ condition yet)' % s['to_hit_bonus'])
    got = []
    for it in s.get('items') or ():
        try:
            item = None
            if it.get('res'):
                try:
                    import ie_itemrt
                    ie_itemrt.LOG[0] = LOG[0]
                    item = ie_itemrt.make(it['res'], o.location)
                except ImportError:
                    item = None
            if item is None:
                item = game.obj_create(int(it['proto']), o.location)
            r = o.item_get(item)
            got.append((it, item, r))
            _log('  item_get %s %s -> %s' % (it['proto'], it.get('res', ''), r))
        except Exception, e:
            _log('  item %s failed: %s' % (it, e))
    wear(o, s)
    try:
        o.d20_status_init()
    except Exception:
        pass
    apply_3e(o, s)
    fix_hp(o, s)
    if s.get('spells'):
        try:
            import ie_spellrt
            ie_spellrt.LOG[0] = LOG[0]
            got = ie_spellrt.give_spells(o, s)
            _log('  spells %s%s' % (got, ' + ai strategy' if s.get('ai_strategy') else ''))
        except Exception, e:
            _log('  spells failed: %s' % e)
    if s.get('portrait'):
        _set(o, 'obj_f_critter_portrait', int(s['portrait']))
    if s.get('name_id'):
        _set(o, 'obj_f_description', int(s['name_id']))
        _set(o, 'obj_f_critter_description_unknown', int(s['name_id']))   # IE shows names without an introduction

def wear(o, s):
    try:
        o.item_wield_best_all()
    except Exception, e:
        _log('  wield_best_all failed: %s' % e)
    for it in s.get('items') or ():   # anything still unworn: wield into its natural slot (garb/boots/armour/shield)
        slot = WEAR_SLOT.get(it.get('slot'))
        item = o.item_find_by_proto(int(it['proto']))
        if slot is not None and item != OBJ_HANDLE_NULL and o.item_worn_at(slot) == OBJ_HANDLE_NULL:
            o.item_wield(item, slot)
    _log('  worn %s' % [o.item_worn_at(i).proto for i in range(16) if o.item_worn_at(i) != OBJ_HANDLE_NULL])

def fix_hp(o, s):
    # stat_hp_max adds Con x HD, racial HD and condition bonuses to obj_f_hp_pts; correct for whatever the engine adds
    if s.get('hp'):
        f = _c('obj_f_hp_pts')
        for i in range(3):
            d = int(s['hp']) - o.stat_level_get(stat_hp_max)
            if not d:
                break
            o.obj_set_int(f, max(1, o.obj_get_int(f) + d))
        _set(o, 'obj_f_hp_damage', 0)

def apply_3e(o, s):
    """IWD2 (iwd2_rules): feats and skill ranks as Temple+ constants."""
    for f in s.get('feats') or ():
        try:
            o.feat_add(_const(f))
        except Exception, e:
            _log('  feat %s failed: %s' % (f, e))
    for k, n in (s.get('skills') or {}).items():
        try:
            o.skill_ranks_set(_const(k), n)
        except Exception, e:
            _log('  skill %s failed: %s' % (k, e))


def spawn(s, loc, script_id=None, rotation=None):
    o = game.obj_create(int(s['proto']), loc)
    for i in range(0, 44):
        try:
            o.scripts[i] = 0
        except Exception:
            break
    apply(o, s)
    sid = script_id or s.get('script_id')
    if sid:
        for san in SCRIPT_EVENTS:
            o.scripts[_c(san)] = int(sid)
    if rotation is None and s.get('orient') is not None:
        # IE orientation: 16 steps, 0 = south, clockwise (IESDP ARE actor 0x34); ToEE rotation is radians
        rotation = (5.0 * math.pi / 4.0 + int(s['orient']) * math.pi / 8.0) % (2 * math.pi)
    if rotation is not None:
        o.rotation = rotation
    return o

def spawn_area(specs, to_tile, log_path=None, filt=None):
    """to_tile(x, y) -> (tile x, tile y) for IE area pixels (ie_runtime.ie_to_tile). Returns [(spec, obj)]."""
    LOG[0] = log_path
    out = []
    for s in specs:
        if filt and not filt(s):
            continue
        u, v = to_tile(s['x'], s['y'])
        try:
            o = spawn(s, location_from_axis(u, v))
            out.append((s, o))
            _log('spawned %s %s proto %s at %d,%d hp %d/%d ac %d lvl %d' % (
                s.get('actor'), s.get('resref'), s['proto'], u, v, o.stat_level_get(stat_hp_current),
                o.stat_level_get(stat_hp_max), o.stat_level_get(stat_ac), o.stat_level_get(stat_level)))
        except Exception, e:
            import traceback
            _log('spawn %s failed: %s %s' % (s.get('actor'), e, traceback.format_exc()))
    return out


# ------------------------------------------------------------------------------------------------ placement
# subtile Block* (0x200-0x20000) and FlyOver* (0x40000-0x4000000) bits + the legacy TF_Blocks bit: a tile with any
# of them is not fully walkable (converted IE search maps mark impassable cells and water this way)
NOT_WALKABLE = 0x1 | 0x7FFFE00

def walkable(x, y):
    """Tile (x, y) is free ground: no blocked / fly-over subtile (needs the harness' game.tile_flags_get; without it
    every tile counts as walkable) and no critter or blocking object standing on it."""
    loc = location_from_axis(x, y)
    try:
        if game.tile_flags_get(loc) & NOT_WALKABLE:
            return False
    except AttributeError:
        pass
    try:
        for o in game.obj_list_vicinity(loc, OLC_CRITTERS | OLC_SCENERY | OLC_CONTAINER | OLC_PORTAL):
            if o.location == loc and not (o.type == obj_t_scenery and (o.object_flags_get() & OF_NO_BLOCK)):
                return False
    except Exception:
        pass
    return True

def free_spot(x, y, taken=None, radius=8):
    """Nearest walkable tile to (x, y) not in `taken` (a set of (x, y) it is added to), searching outwards ring by
    ring; None if there is none within radius. Prefers tiles whose 4 neighbours are walkable too (no edge-of-water)."""
    taken = taken if taken is not None else set()
    for strict in (True, False):
        for r in range(radius + 1):
            ring = [(x + dx, y + dy) for dx in range(-r, r + 1) for dy in range(-r, r + 1) if max(abs(dx), abs(dy)) == r]
            for p in ring:
                if p in taken or not walkable(p[0], p[1]):
                    continue
                if strict and not all(walkable(p[0] + a, p[1] + b) for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    continue
                taken.add(p)
                return p
    return None

def place_near(o, x, y, taken=None, radius=8):
    p = free_spot(x, y, taken, radius)
    if p is None:
        return None
    o.move(location_from_axis(p[0], p[1]))
    return p

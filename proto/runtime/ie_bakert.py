# ie2toee runtime for baked maps (docs/mapfiles.md, "Baking"). Python 2.7 inside Temple+.
#
# proto/ie_bake.py writes the converted creatures, their items and the area's containers as prefab .mob files and the
# doors into the .sec object lists. Everything a .mob can hold is baked (stats, levels, hit dice, gear, scripts,
# standpoints, waypoints, names). What the file format cannot hold without engine knowledge stays here and runs once
# per object, on the first heartbeat after the map loads:
#   critters: conditions (condition_add_with_args), spells + AI strategy (ie_spellrt), the hp correction (fix_hp)
#   items:    wielder conditions (their argument count is only known to the engine), magical / identified flags
# A persisted marker field (npc_pad_i_3 / item_pad_i_1, set to STAMP) makes it idempotent across save / load;
# session-only state (the in-memory AI strategy table) is re-registered on every load.
# Data: ie_bake_<area>.py, generated on the player's machine (never distributed):
#   AREA, FIELDS {name: engine field index}, OBJS {"G_...": {"k": "npc"|"item"|"container", ...}}
from toee import *
import time
import re

LOG = [None]
STAMP = 0x1E2B0001
BACKUP_STAMP = 0x1E2B0002
_last = {}           # area -> wall clock of the last area pass
_members = {}        # area -> {guid: 1} of the critters whose first heartbeat ran since the last area pass


def _log(s):
    try:
        if LOG[0]:
            f = open(LOG[0], 'a'); f.write(s + '\n'); f.close()
        else:
            print s
    except Exception:
        pass


def _data(area):
    try:
        return __import__('ie_bake_' + area.lower())
    except ImportError:
        return None


def _guid(o):
    try:
        return str(o.id)
    except Exception:
        return ''


_siege_raider = re.compile(r'^0[1-8]_(?:goblin(?:_archer|_elite)?_\d+|wolf_\d+|vghotan|ghotrag|phaen)$|^06_caballus$', re.I)


# AR1200's gate defenders, training squads, and named siege allies.
_siege_defenders = frozenset((
    '12tarsol', '12archer', '12merc', '12drill', '12recrui', '12traine', '12weapon',
    '12black', '12blanc', '12anson', '12kadenc', '12olap',
))


def mark_targos_combatant(o, data, guid):
    if data is None or data.__name__ not in ('ie_bake_i2ar1004', 'ie_bake_i2ar1200'):
        return
    spec = data.OBJS.get(guid, {}).get('spec', {})
    if data.__name__ == 'ie_bake_i2ar1004':
        if spec.get('resref', '').lower() in ('10catf', '10firth'):
            o.condition_add("IE Firtha Household")
        return
    # The other Caballus actors stage cutscenes. Only the wave 6 actor fights.
    if spec.get('resref', '').lower() in _siege_defenders:
        import ie_runtime as rt
        if rt.targos_guard is not None and not o.faction_has(rt.targos_guard.FACTION):
            o.faction_add(rt.targos_guard.FACTION)
        o.condition_add("IE Palisade Defender")
    elif _siege_raider.match(spec.get('actor', '')) and not o.d20_query("Dies at Zero HP"):
        o.condition_add("IE Siege Raider")


def finalize_critter(o, d, F):
    import ie_critters
    s = d['spec']
    ie_critters.passive_prop(o, s)
    mark = F['npc_pad_i_3']
    first = o.obj_get_int(mark) not in (STAMP, BACKUP_STAMP)
    if first:
        for c in s.get('conditions') or ():
            try:
                args = list(c[1:]) + [0] * max(0, 2 - len(c[1:]))
                o.condition_add_with_args(c[0], *args)
            except Exception, e:
                _log('IE_BAKE condition %s failed: %s' % (c, e))
    if s.get('spells') or s.get('ai_strategy'):
        try:
            import ie_spellrt
            if first:
                ie_spellrt.give_spells(o, s)
            else:     # spells are in the save; only the session strategy table needs refilling
                ie_spellrt._strategy[ie_spellrt._okey(o)] = s.get('ai_strategy')
                if s.get('ai_strategy'):
                    o.ai_strategy_set_custom(list(s['ai_strategy']), 1)
        except Exception, e:
            _log('IE_BAKE spells %s: %s' % (s.get('ident') or s.get('resref'), e))
    if first:
        try:
            o.d20_status_init()
        except Exception:
            pass
        ie_critters.apply_3e(o, s)
        ie_critters.fix_hp(o, s)
        o.obj_set_int(mark, STAMP)
        if s.get('dead'):   # IE STATE_DEAD corpse
            try:
                o.critter_kill_by_effect()
            except Exception, e:
                _log('IE_BAKE kill corpse %s: %s' % (s.get('ident') or s.get('resref'), e))
    if not s.get('dead'):
        faction = s.get('company_faction')
        if faction and o.npc_flags_get() & ONF_KOS and not o.faction_has(faction):
            o.faction_add(faction)
        if s.get('melee_backup') and o.obj_get_int(mark) != BACKUP_STAMP and not o.is_dead_or_destroyed():
            if ie_critters.give_melee_backup(o, s):
                o.obj_set_int(mark, BACKUP_STAMP)
        arm(o, s)
    return first


def arm(o, s):
    """Safety net (every load, also fixes old saves): a living critter with an empty main hand that carries a
    weapon wields its best gear (the bake puts weapons in the wielded slot; this catches saves / spawns that lost it)."""
    try:
        if s.get('redeem_weapon'):
            import ie_itemrt
            token, weapon = s['redeem_weapon']
            it = ie_itemrt.find(o, token)
            if it:
                real = ie_itemrt.make(weapon, o.location)
                if real:
                    o.item_get(real)
                    if real in ie_itemrt._inv(o):
                        it.destroy()
                        o.item_wield(real, item_wear_weapon_primary)
                    else:
                        real.destroy()
        if o.item_worn_at(3) != OBJ_HANDLE_NULL:     # item_wear_weapon_primary
            return
        if s.get('primary_weapon'):
            weapon = o.item_find_by_proto(s['primary_weapon'])
            if weapon != OBJ_HANDLE_NULL:
                o.item_wield(weapon, item_wear_weapon_primary)
            return
        if not any(it.get('slot') in ('weapon', 'weapon1', 'quiver', 'ranged') or 'weapon' in str(it.get('slot'))
                   for it in s.get('items') or ()):
            return
        o.item_wield_best_all()
        if o.item_worn_at(3) != OBJ_HANDLE_NULL:
            _log('IE_BAKE armed %s' % (s.get('ident') or s.get('resref')))
    except Exception, e:
        _log('IE_BAKE arm %s: %s' % (s.get('ident') or s.get('resref'), e))

def ready_company_melee(o, area):
    """The native weapon picker can stow a bow when threatened. Use the CRE's melee set."""
    if area not in ('AR2102', 'I2AR2102') or o.item_worn_at(item_wear_weapon_primary) or o.npc_flags_get() & ONF_NO_EQUIP:
        return
    data = _data('I2AR2102')
    s = data and data.OBJS.get(_guid(o), {}).get('spec', {})
    if not s or not s.get('company_faction'):
        return
    pid = s['melee_backup'][1] if s.get('melee_backup') else s.get('primary_weapon')
    weapon = o.item_find_by_proto(pid) if pid else None
    if weapon and not weapon.obj_get_int(obj_f_weapon_flags) & OWF_RANGED_WEAPON:
        o.item_wield(weapon, item_wear_weapon_primary)


def finalize_item(o, d, F):
    mark = F['item_pad_i_1']
    if o.obj_get_int(mark) == STAMP:
        return 0
    try:
        import ie_itemrt
        e = ie_itemrt.entry(d['res']) or {}
        for c in e.get('c') or ():
            try:
                o.item_condition_add_with_args(c[0], ie_itemrt._arg(c[1]), ie_itemrt._arg(c[2]))
            except Exception, ex:
                _log('IE_BAKE item %s condition %s failed: %s' % (d['res'], c, ex))
    except ImportError:
        pass
    o.obj_set_int(mark, STAMP)
    return 1


def omit_placement(o, spec):
    if not spec.get('area_spawn'):
        return False
    import ie_runtime
    if ie_runtime.area_spawn_allowed(spec):
        return False
    if o and o != OBJ_HANDLE_NULL:
        ie_runtime._bound.pop(o.id, None)
        ie_runtime._bound.pop(_guid(o), None)
        # The owner's separately baked items still point to it on reload.
        # OF_OFF suppresses AI and interaction while preserving that link.
        if not o.object_flags_get() & OF_OFF:
            o.object_flag_set(OF_OFF)
    return True


def hide_retired_npc(o):
    if o and o != OBJ_HANDLE_NULL:
        import ie_runtime
        ie_runtime._bound.pop(ie_runtime._key(o), None)
        if not o.object_flags_get() & OF_OFF:
            o.object_flag_set(OF_OFF)

def area_pass(area):
    """Finalize every baked object of the area that is still in the world, attach the doors."""
    m = _data(area)
    if m is None and _data('I2' + area) is not None:
        area = 'I2' + area            # IWD2 scripts name the area AR1200, the baked data/doors are I2AR1200
        m = _data(area)
    if m is None:
        return 0
    import ie_runtime as rt
    # Keep the backing objects and their inventory links valid for saved mobile diffs.
    for guid in getattr(m, 'RETIRED_NPCS', ()):
        hide_retired_npc(game.get_obj_by_id(guid))
    # Old saves can already contain the visible version of the palisade mobs.
    before_siege = area == 'I2AR1200' and not any(rt.get_var(None, flag, 'GLOBAL') for flag in
        ('Goblins_Attack_Palisade', '1200_BATTLE_SETUP', 'Goblin_Palisade_Quest'))
    F = m.FIELDS
    n = {'npc': 0, 'item': 0, 'missing': 0, 'first': 0, 'omitted': 0}
    holders = []
    for g, d in m.OBJS.items():          # items first: the wielder's status init then sees their conditions
        if d['k'] == 'container':
            box = game.get_obj_by_id(g)
            if box and box != OBJ_HANDLE_NULL:
                box.object_flag_set(OF_NO_BLOCK)
            continue
        if d['k'] != 'item':
            continue
        o = game.get_obj_by_id(g)
        if o == OBJ_HANDLE_NULL or o is None:
            n['missing'] += 1; continue
        n['item'] += 1
        n['first'] += finalize_item(o, d, F)
    for g, d in m.OBJS.items():
        if d['k'] != 'npc':
            continue
        o = game.get_obj_by_id(g)
        if omit_placement(o, d['spec']):
            n['omitted'] += 1
            continue
        ident = d['spec'].get('ident')
        if ident:
            # OF_OFF actors receive no engine heartbeat. Register the baked GUID for
            # hidden_tick and named cutscene actions even before its sector is loaded.
            rt._bound[g] = (ident, m.AREA)
        if o == OBJ_HANDLE_NULL or o is None:
            n['missing'] += 1; continue
        n['npc'] += 1
        if before_siege and d['spec'].get('starts_hidden_hostile') and not (o.object_flags_get() & OF_OFF):
            if not o.is_dead_or_destroyed():
                o.object_flag_set(OF_OFF)
        n['first'] += finalize_critter(o, d, F) and 1 or 0
        mark_targos_combatant(o, m, g)
    nd = 0
    try:
        import ie_doors
        nd = ie_doors.start(area)
    except ImportError:
        pass
    _log('IE_BAKE %s pass: %d npcs, %d items, %d newly finalized, %d not in world, %d doors attached, %d omitted by level' % (
        area, n['npc'], n['item'], n['first'], n['missing'], nd, n['omitted']))
    return 1


def died(o, area):
    """san_dying of a baked critter without IE scripts (GENERIC_SCRIPT): the engine's death variables for its ARE
    actor name (ie_runtime.death_vars: SPRITE_IS_DEAD<name> += 1), which other actors' dialogue / scripts may test."""
    m = _data(area) or _data('I2' + area)
    d = m and m.OBJS.get(_guid(o))
    if m and not d:
        for g, d_ in m.OBJS.items():
            if d_['k'] == 'npc' and game.get_obj_by_id(g) == o:
                d = d_; break
    if not d or not d.get('spec', {}).get('actor'):
        return
    try:
        import ie_runtime
        ie_runtime.death_vars(d['spec']['actor'], d['spec'].get('death_counters', ()))
    except Exception, e:
        _log('IE_BAKE died %s: %s' % (d['spec'].get('actor'), e))


def first_heartbeat(o, area):
    """Called from every baked critter's san_first_heartbeat (directly or through ie_runtime.bind). The engine runs
    first heartbeats once per object per map load, so the first call, or a second call for the same critter (= the
    map was loaded again: new visit or a loaded save), starts an area pass."""
    try:      # the Easthaven travel poll (ie_travel.start() is idempotent); it needs the map's travel data
        import ie_travel
        ie_travel.start()
    except ImportError:
        pass
    except Exception, e:
        _log('IE_BAKE travel start failed: %s' % e)
    try:      # the converted intro movie, once per new game
        import ie_movies_rt
        ie_movies_rt.play_intro()
    except ImportError:
        pass
    except Exception, e:
        _log('IE_BAKE intro movie failed: %s' % e)
    a = area.upper(); g = _guid(o)
    if a in ('AR1004', 'I2AR1004', 'AR1200', 'I2AR1200'):
        # A sector may become available after the map-wide pass.
        mark_targos_combatant(o, _data('I2' + a[-6:]), g)
    # Sectors can load after the area pass. Apply the same gate on their first heartbeat.
    data = _data(a) or _data('I2' + a)
    if data and g in getattr(data, 'RETIRED_NPCS', ()):
        hide_retired_npc(o)
        return
    if data and omit_placement(o, data.OBJS.get(g, {}).get('spec', {})):
        return
    seen = _members.get(a)
    now = time.time()
    if seen is not None and (not seen.has_key(g) or now - _last[a] < 2.0):
        seen[g] = 1      # (scripts also call bind from dialog / first tick: repeats within 2 s are not a new load)
        return
    _members[a] = {g: 1}
    _last[a] = now
    _hidden_gen[0] += 1
    game.timeevent_add(hidden_tick, (_hidden_gen[0], o.map), 1000, 1)
    try:      # the area's own IE script (ARE header) and the new-game IE globals
        import ie_cutscene
        ie_cutscene.area_start(area)      # (not in area_pass: IWD2 areas have no ie_bake_<area> module)
    except ImportError:
        pass
    try:
        area_pass(area)
    except Exception, e:
        import traceback
        _log('IE_BAKE pass failed: %s %s' % (e, traceback.format_exc()))


# IE creatures that start hidden (baked OF_OFF, ie_bake.start_hidden) still run their scripts in IE (12caba05 waits
# hidden for the goblin teams and then starts its cutscene), but Temple+ gives an OF_OFF critter no heartbeat. This
# loop runs their converted heartbeat script for them while the map is loaded (bind on the first pass).
_hidden_gen = [0]
_hb_mods = {}

def _hb_module(sid, ident):
    """the critter's generated script module py<sid>ie_<ident> (the scr dir may live in a .dat or an overlay)"""
    if sid not in _hb_mods:
        m = None
        try:
            m = __import__('py%05die_%s' % (sid, ident.lower()))
        except ImportError:
            pass
        except Exception, e:
            _log('IE_BAKE hidden script %d: %s' % (sid, e))
        _hb_mods[sid] = m
    return _hb_mods[sid]

def _names(f, out):
    co = getattr(f, 'func_code', f)
    out.update(getattr(co, 'co_names', ()))
    for k in getattr(co, 'co_consts', ()) or ():
        if hasattr(k, 'co_names'):
            _names(k, out)

def _wants_hidden(m):
    """A hidden KOS critter only runs scripts written for the hidden state (12caba05: wait hidden, then StartCutScene;
    12atkuhp: CreatureHidden(Myself) -> unhide); the ordinary combat scripts of a hidden goblin wave would see the
    party and attack from hiding. Hidden non-hostile critters always run theirs, as in the IE (Firtha's hidden voice
    10FIRTHH: 10FIRTHV floats her cries for help; Swift Thomas' 1000THMV waits for Jump_Check)."""
    k = 'wants_' + m.__name__
    if k not in _hb_mods:
        ns = set()
        for sm in getattr(m, 'SCRIPTS', []):
            for cond, resps in getattr(sm, 'BLOCKS', []):
                _names(cond, ns)
                for r in resps:
                    for a in r[1]:
                        _names(a, ns)
        hidden_speaker = {'SetDialogueRange', 'Dialogue', 'ChangeEnemyAlly'}.issubset(ns)
        _hb_mods[k] = 'CreatureHidden' in ns or 'StartCutScene' in ns or hidden_speaker
    return _hb_mods[k]

def hidden_tick(gen, mapid):
    if gen != _hidden_gen[0]:
        return 0
    try:
        l = game.leader
        if l == OBJ_HANDLE_NULL or l.map != mapid:
            return 0
        n = 0
        import ie_runtime as rt
        for k in list(rt._bound.keys()):      # (obj_list_range skips OF_OFF objects; area_pass binds every baked npc)
            try:
                o = game.get_obj_by_id(k)
            except Exception:
                continue
            if o is None or o == OBJ_HANDLE_NULL or o.map != mapid:
                continue
            if not (o.object_flags_get() & OF_OFF) or (o.object_flags_get() & OF_DESTROYED):
                continue
            m = _hb_module(o.scripts[san_heartbeat], rt._bound[k][0])
            if m is None or not hasattr(m, 'IDENT'):
                continue
            if not _wants_hidden(m) and (o.npc_flags_get() & ONF_KOS):
                continue      # (a hidden hostile's ordinary combat scripts would attack from hiding)
            m.san_heartbeat(o, o); n += 1
        if n and not _hb_mods.get('logged%d' % gen):
            _hb_mods['logged%d' % gen] = 1; _log('IE_BAKE hidden tick: %d hidden critters run their scripts' % n)
    except Exception, e:
        _log('IE_BAKE hidden tick: %s' % e)
    game.timeevent_add(hidden_tick, (gen, mapid), 1000, 1)
    return 0

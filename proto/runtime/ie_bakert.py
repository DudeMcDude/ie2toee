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

LOG = [None]
STAMP = 0x1E2B0001
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


def finalize_critter(o, d, F):
    import ie_critters
    s = d['spec']
    mark = F['npc_pad_i_3']
    first = o.obj_get_int(mark) != STAMP
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
        ie_critters.fix_hp(o, s)
        o.obj_set_int(mark, STAMP)
    return first


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


def area_pass(area):
    """Finalize every baked object of the area that is still in the world, attach the doors."""
    m = _data(area)
    if m is None:
        return 0
    F = m.FIELDS
    n = {'npc': 0, 'item': 0, 'missing': 0, 'first': 0}
    holders = []
    for g, d in m.OBJS.items():          # items first: the wielder's status init then sees their conditions
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
        if o == OBJ_HANDLE_NULL or o is None:
            n['missing'] += 1; continue
        n['npc'] += 1
        n['first'] += finalize_critter(o, d, F) and 1 or 0
    nd = 0
    try:
        import ie_doors
        nd = ie_doors.start(area)
    except ImportError:
        pass
    _log('IE_BAKE %s pass: %d npcs, %d items, %d newly finalized, %d not in world, %d doors attached' % (
        area, n['npc'], n['item'], n['first'], n['missing'], nd))
    return 1


def first_heartbeat(o, area):
    """Called from every baked critter's san_first_heartbeat (directly or through ie_runtime.bind). The engine runs
    first heartbeats once per object per map load, so the first call, or a second call for the same critter (= the
    map was loaded again: new visit or a loaded save), starts an area pass."""
    a = area.upper(); g = _guid(o)
    seen = _members.get(a)
    now = time.time()
    if seen is not None and (not seen.has_key(g) or now - _last[a] < 2.0):
        seen[g] = 1      # (scripts also call bind from dialog / first tick: repeats within 2 s are not a new load)
        return
    _members[a] = {g: 1}
    _last[a] = now
    try:
        area_pass(area)
    except Exception, e:
        import traceback
        _log('IE_BAKE pass failed: %s %s' % (e, traceback.format_exc()))

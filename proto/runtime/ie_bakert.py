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
    if m is None and _data('I2' + area) is not None:
        area = 'I2' + area            # IWD2 scripts name the area AR1200, the baked data/doors are I2AR1200
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
    """Only scripts written for the hidden state run while hidden (12caba05: wait hidden, then StartCutScene;
    12atkuhp: CreatureHidden(Myself) -> unhide). The ordinary combat scripts of a hidden goblin wave would see the
    party and attack from hiding."""
    k = 'wants_' + m.__name__
    if k not in _hb_mods:
        ns = set()
        for sm in getattr(m, 'SCRIPTS', []):
            for cond, resps in getattr(sm, 'BLOCKS', []):
                _names(cond, ns)
                for r in resps:
                    for a in r[1]:
                        _names(a, ns)
        _hb_mods[k] = 'CreatureHidden' in ns or 'StartCutScene' in ns
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
            if m is None or not hasattr(m, 'IDENT') or not _wants_hidden(m):
                continue
            m.san_heartbeat(o, o); n += 1
        if n and not _hb_mods.get('logged%d' % gen):
            _hb_mods['logged%d' % gen] = 1; _log('IE_BAKE hidden tick: %d hidden critters run their scripts' % n)
    except Exception, e:
        _log('IE_BAKE hidden tick: %s' % e)
    game.timeevent_add(hidden_tick, (gen, mapid), 1000, 1)
    return 0

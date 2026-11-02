"""IE area scripts and cutscenes in ToEE (Temple+ python).

* Area scripts (ARE header script, e.g. AR1000.BCS -> ie_bcs_ar1000_area): evaluated once per second while the party
  leader is on the area's map (ie_areas.SCRIPTS / MAPS). Started from ie_bakert's area pass on every map load; a
  generation counter retires stale loops (time events are pickled into saves, so their args stay plain values).
* Cutscenes (StartCutScene("res") -> ie_bcs_<res>_area): IE runs every true block of a cutscene script once, each
  block on its own actor (CutSceneId) and action queue; Wait/SmallWait/MoveToPoint delays come from ie_runtime's
  queue. Cutscene mode (StartCutSceneMode .. EndCutSceneMode) pauses the creature scripts and is reported by
  InCutsceneMode(). Party mouse input is locked by a full-screen invisible tpgui button (Temple+ python UI) that
  swallows clicks until EndCutSceneMode (or the 120 s safety timeout).
* Each cutscene block's actions run on its CutSceneId actor's own queue: two blocks for the same actor run one after
  the other (IE action-queue semantics), not at the same time.
"""
from toee import *
import ie_runtime as rt

STATE = {'gen': 0, 'cut': 0, 'cut_since': 0, 'hook': 0}   # hook: Temple+ map_tick.on_tick drives the area scripts
AREA_TICK_MS = 1000
_area = {}          # area -> (gen, module)

NEWGAME_FLAG = 991  # ToEE global var: the new-game IE globals are set (ie_areas.NEWGAME, e.g. IWD2 CHAPTER = -1)

def new_game_init():
    try:
        import ie_areas
        ng = getattr(ie_areas, 'NEWGAME', {})
    except ImportError:
        return
    if not ng or game.global_vars[NEWGAME_FLAG]:
        return
    game.global_vars[NEWGAME_FLAG] = 1
    for k, v in sorted(ng.items()):
        rt.set_var(None, k, 'GLOBAL', v)

def area_start(area):
    """(Re)start the area script loop of `area` (idempotent per map load)."""
    A_ = area.upper()
    new_game_init()
    try:
        if game.leader.map == rt.AREA_MAPS.get(A_):
            import ie_spawn
            ie_spawn.area_spawns(A_)      # ARE spawn points: once per game, on the first visit
    except Exception as e:
        rt.log('IE_ERR area spawns %s: %s' % (A_, e))
    try:
        import ie_areas
        name = getattr(ie_areas, 'SCRIPTS', {}).get(A_)
        if not name:
            return 0
        mod = __import__(name)
    except ImportError:
        return 0
    if STATE['hook']:
        if A_ in _area:
            return 1                  # engine tick: already running for this map visit
        try:
            if game.leader.map != rt.AREA_MAPS.get(A_):
                return 0              # a critter of another area woke up here: its area script is not this map's
        except Exception:
            pass
    STATE['gen'] += 1
    _area[A_] = (STATE['gen'], mod)
    ev = rt._events.setdefault('area_' + A_, {})
    ev['OnCreation'] = game.leader     # IE: OnCreation() is true on the first script round after the area loads
    rt.log('AREA_SCRIPT %s start (%s)%s' % (A_, name, STATE['hook'] and ' [engine tick]' or ''))
    if not STATE['hook']:     # fallback for Temple+ builds without the map tick: game-clock time event loop
        game.timeevent_add(_area_step, (A_, STATE['gen']), 500)
    return 1

def map_tick(map_id, elapsed_ms):
    """Temple+ engine tick (map_tick.on_tick): run the area script(s) of the current map."""
    if not STATE['hook']:
        STATE['hook'] = 1; rt.log('AREA_SCRIPT engine map tick active (%d ms)' % AREA_TICK_MS)
    for area, m in rt.AREA_MAPS.items():
        if m != map_id:
            continue
        if area not in _area:         # e.g. the map tick ran before the first critter heartbeat
            area_start(area)
        if area in _area:
            _run_area(area, _area[area][1])
    for area in [a for a in _area.keys() if rt.AREA_MAPS.get(a) != map_id]:
        _area.pop(area, None); rt.log('AREA_SCRIPT %s stop (left the map)' % area)
    return AREA_TICK_MS

def _area_step(area, gen):
    if STATE['hook']:
        return 1                      # the engine tick took over
    ent = _area.get(area)
    if not ent or ent[0] != gen:
        return 1
    try:
        l = game.leader
        if l == OBJ_HANDLE_NULL or l.map != rt.AREA_MAPS.get(area):
            _area.pop(area, None); rt.log('AREA_SCRIPT %s stop (left the map)' % area)
            return 1
        _run_area(area, ent[1])
    except Exception as e:
        rt.log('IE_ERR area loop %s: %s' % (area, e))
    game.timeevent_add(_area_step, (area, gen), AREA_TICK_MS)   # always reschedule (an exception must not end the loop)
    return 1

def _run_area(area, mod):
    l = game.leader
    if l == OBJ_HANDLE_NULL:
        return
    ident = 'area_' + area
    if rt._busy.get(ident, 0) <= rt._now():
        c = rt.Ctx(l, None, ident, area, rt._events.setdefault(ident, {}))
        try:
            rt.run_script(c, mod.BLOCKS)
        except Exception as e:
            rt.log('IE_ERR area script %s: %s' % (area, e))

# ------------------------------------------------------------------------------------------------ cutscenes
_LOCK = {'w': None, 'clicks': 0}

def _lock(on):
    """Party input lock: a full-screen transparent button on top of the UI eats mouse clicks (tpgui, Temple+ only)."""
    try:
        import tpgui
    except ImportError:
        return
    try:
        if _LOCK['w'] is None:
            if not on:
                return
            root = tpgui._add_root_container('ie_cutscene_lock', 4096, 4096)
            if root is None:
                root = tpgui._get_container('ie_cutscene_lock')
            b = tpgui._add_button('ie_cutscene_lock', 'ie_cutscene_lock_btn', 4096, 4096)
            def eat():
                _LOCK['clicks'] += 1
            b.set_click_handler(eat)
            _LOCK['w'] = root
        if on:
            _LOCK['w'].show(); _LOCK['w'].bring_to_front()
        else:
            _LOCK['w'].hide()
    except Exception as e:
        rt.log('IE_ERR input lock: %s' % e)

def mode(on):
    STATE['cut'] = on and 1 or 0
    STATE['cut_since'] = rt._now()
    if rt.IN_GAME:
        _lock(on)
    rt.log('CUTSCENE_MODE %s' % (on and 'on' or 'off'))

def active():
    if STATE['cut'] and rt._now() - STATE['cut_since'] > 120:     # safety: a cutscene that never ended
        mode(0)
    return bool(STATE['cut'])

def start(res, c):
    name = 'ie_bcs_%s_area' % res.lower()
    try:
        mod = __import__(name)
    except ImportError:
        rt.log('IE_UNSUPPORTED cutscene %s (not converted)' % res); mode(0)
        return None
    rt.log('CUTSCENE %s (%d blocks) by %s' % (res, len(mod.BLOCKS), c.ident))
    mode(1)
    for i, (cond, resps) in enumerate(mod.BLOCKS):
        c2 = rt.Ctx(c.me, c.other, 'cs_%s_%d' % (res.lower(), i), c.area, {})
        try:
            ok = cond(c2)
        except Exception as e:
            rt.log('IE_ERR cutscene %s #%d: %s' % (res, i, e)); ok = False
        if ok and resps:
            _run_block(c2, list(resps[0][1]))
    return None

def _run_block(c2, acts):
    """Run a cutscene block: a leading CutSceneId picks the actor; the rest joins that actor's action queue."""
    if acts and getattr(acts[0], '__name__', '') == '<lambda>':
        try:
            r = acts[0](c2)       # CutSceneId(...) (sets c2.me / c2.ident) or an ordinary first action
        except Exception as e:
            rt.log('IE_ERR cutscene action: %s' % e); r = None
        acts = acts[1:]
        if r is not None and r is not rt.CONTINUE and isinstance(r, rt._NUM) and r > 0:
            acts = [lambda c, r=r: r] + acts
    pend = rt._queues.get(c2.ident)
    if pend:                      # the actor is still busy with an earlier block: queue behind it
        pend[1].extend(acts); return
    left = rt._busy.get(c2.ident, 0) - rt._now()
    if left > 0 and rt.IN_GAME and acts:
        rt._queues[c2.ident] = (c2, acts)
        game.timeevent_add(rt._resume, (c2.me, c2.other, c2.ident, c2.area, len(acts)), int(left * 1000), 1)
        return
    rt.run_actions(c2, acts)

def cutscene_id(c, obj):
    """CutSceneId(obj): the rest of this block acts as obj."""
    if obj is None:
        rt.log('IE_OBJ_NOT_FOUND CutSceneId'); return None
    c.me = obj
    b = rt._bound.get(rt._key(obj))
    if b:
        c.area = b[1] or c.area
    # the block now runs on obj's own queue (LOCALS of obj; blocks for the same actor queue up)
    c.ident = (b and b[0]) or 'cs_obj_%s' % rt._key(obj)
    rt.log('CUTSCENE_ID %s' % c.ident)
    return None

"""IE area scripts and cutscenes in ToEE (Temple+ python).

* Area scripts (ARE header script, e.g. AR1000.BCS -> ie_bcs_ar1000_area): evaluated once per second while the party
  leader is on the area's map (ie_areas.SCRIPTS / MAPS). Started from ie_bakert's area pass on every map load; a
  generation counter retires stale loops (time events are pickled into saves, so their args stay plain values).
* Cutscenes (StartCutScene("res") -> ie_bcs_<res>_area): IE runs every true block of a cutscene script once, each
  block on its own actor (CutSceneId) and action queue; Wait/SmallWait/MoveToPoint delays come from ie_runtime's
  queue. Cutscene mode (StartCutSceneMode .. EndCutSceneMode) pauses the creature scripts and is reported by
  InCutsceneMode(); party input is not locked (no Python hook for it).
"""
from toee import *
import ie_runtime as rt

STATE = {'gen': 0, 'cut': 0, 'cut_since': 0}
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
        import ie_areas
        name = getattr(ie_areas, 'SCRIPTS', {}).get(A_)
        if not name:
            return 0
        mod = __import__(name)
    except ImportError:
        return 0
    STATE['gen'] += 1
    _area[A_] = (STATE['gen'], mod)
    ev = rt._events.setdefault('area_' + A_, {})
    ev['OnCreation'] = game.leader     # IE: OnCreation() is true on the first script round after the area loads
    rt.log('AREA_SCRIPT %s start (%s)' % (A_, name))
    game.timeevent_add(_area_step, (A_, STATE['gen']), 500, 1)
    return 1

def _area_step(area, gen):
    ent = _area.get(area)
    if not ent or ent[0] != gen:
        return 1
    l = game.leader
    try:
        if l == OBJ_HANDLE_NULL or l.map != rt.AREA_MAPS.get(area):
            _area.pop(area, None); rt.log('AREA_SCRIPT %s stop (left the map)' % area)
            return 1
    except Exception:
        return 1
    ident = 'area_' + area
    if rt._busy.get(ident, 0) <= rt._now():
        c = rt.Ctx(l, None, ident, area, rt._events.setdefault(ident, {}))
        try:
            rt.run_script(c, ent[1].BLOCKS)
        except Exception as e:
            rt.log('IE_ERR area script %s: %s' % (area, e))
    game.timeevent_add(_area_step, (area, gen), 1000, 1)
    return 1

# ------------------------------------------------------------------------------------------------ cutscenes
def mode(on):
    STATE['cut'] = on and 1 or 0
    STATE['cut_since'] = rt._now()
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
            rt.run_actions(c2, list(resps[0][1]))
    return None

def cutscene_id(c, obj):
    """CutSceneId(obj): the rest of this block acts as obj."""
    if obj is None:
        rt.log('IE_OBJ_NOT_FOUND CutSceneId'); return None
    c.me = obj
    b = rt._bound.get(rt._key(obj))
    if b:
        c.area = b[1] or c.area
    return None

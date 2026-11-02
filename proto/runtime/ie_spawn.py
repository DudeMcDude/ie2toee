"""Script/area spawns for converted IE creatures (ToEE side, Python 2.2-compatible style).

* CreateCreature("cre", [x.y], face) -> ie_spawnables.SPECS[cre] (converted by ie_creatures.py spawnables), placed at the
  IE point of the calling script's area ([-1.-1] = next to the caller), IE facing -> ToEE rotation.
* Generic monsters get a per-instance portrait: the spec carries its family pool ('portrait_pool', the upgraded pool for
  elite resrefs, flips included) and one is picked by a stable hash of resref + area + point + spawn count.
* ARE spawn points (ie_spawnables.SPAWN_POINTS[area]) spawn once per game on the first visit of the area.
Rest-encounter spawns (ARE rest tables) are listed in REST but not hooked: ToEE's resting has no Python hook here.
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

def spawn(res, area, u, v, face=None, seed=None, near=None):
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
        o = cr.spawn(s, location_from_axis(u, v))
        try:
            cr.place_near(o, u, v)
        except Exception:
            pass
    except Exception, e:
        rt.log('IE_ERR spawn %s: %s' % (res, e)); return None
    rt.bind(o, s.get('ident') or res.lower(), area)
    rt.log('SPAWN %s at tile(%d,%d) portrait %s' % (res, u, v, por))
    return o

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

def area_spawns(area):
    """ARE spawn points: spawn base_count creatures (cycling through the point's list) once per game."""
    d = _data()
    pts = d and getattr(d, 'SPAWN_POINTS', {}).get(area.upper())
    if not pts or not rt.IN_GAME:
        return 0
    key = '#spawned_' + area.upper()
    if rt.get_var(None, key, 'GLOBAL'):
        return 0
    rt.set_var(None, key, 'GLOBAL', 1)
    n = 0
    for p in pts:
        cres = [c_ for c_ in p['creatures'] if c_.lower() in d.SPECS]
        u, v = rt.ie_to_tile(area, p['x'], p['y'])
        for k in range(max(1, min(p.get('count') or 1, 6)) if cres else 0):
            if spawn(cres[k % len(cres)], area, u, v, seed='%s:%s:%d' % (area.upper(), p['name'], k)):
                n += 1
    rt.log('AREA_SPAWNS %s: %d creatures' % (area.upper(), n))
    return n

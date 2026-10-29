#!/usr/bin/env python3
"""Clickable exit icons for the IE travel regions (docs/travel.md, "Exit icons").

ToEE joins maps with map-change icons: static scenery objects (proto 2011, the standard exit icon) in the map's .sec
files whose scenery_teleport_to names a row of rules/jumppoint.tab (id, name, map, tile x, tile y). Clicking the icon
moves the party there. This tool gives every usable IE travel region (ie_travel_data.py, ie_exits.py) one such icon:
  * placed on the region's anchor tile when it has one (ie2toee.region_anchors: the walkable tile, reachable from
    the area start, nearest the region; IE regions often lie on door frames behind a closed door, where the party
    cannot walk up to an icon and clicking it does nothing), else on a tile inside the polygon: the vertex centroid
    if it is inside, else the inside tile nearest to it;
  * its jump point is the destination entrance's arrival tile (ie2toee moved it onto walkable ground);
  * static sector objects like vanilla's icons and the converted doors: part of the map, never duplicated in saves.
Jump point ids are JP_BASE + n in a stable order (area, region name). The module's rules/jumppoint.tab holds only
these rows (the IWD module needs none of vanilla's).

  ie_exiticons.py --travel <w>/ie_travel_data.py --maps <bake>/modules/ToEE/maps --jumppoints <M>/rules/jumppoint.tab
"""
import argparse, glob, os, runpy, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import toeemob as T
import ie_pathnodes as P
from toee_sectors import load_map_subtiles

JP_BASE = 2000
ICON_PROTO = 2011
# from a vanilla exit icon (Hommlet exterior): flags, radius, render height; the engine also sets them for a fresh one
ICON_FLAGS = -1874852816
ICON_RADIUS, ICON_HEIGHT = 34.32571029663086, 56.51353454589844
USE_REACH = 2   # tiles: the use goal walks the party to within ~2 tiles of the icon (GoalSetRadiusTo2); a party
                # member (radius 25) must fit on some tile that close, else Temple+ finds no path and a click on the
                # icon does nothing (I2AR1000 -> AR1004: the icon sat in a niche between a wall and the door frame)


def use_room(K, u, v, reach=USE_REACH):
    """tiles within `reach` of (u, v) where a radius-25 mover fits (the engine's exact-point check)"""
    return [(u + du, v + dv) for du in range(-reach, reach + 1) for dv in range(-reach, reach + 1)
            if P.walk_tile(K, u + du, v + dv) and P.fits(K, u + du, v + dv)]


def roomy_icon(K, u, v, reach=5):
    """(u, v) if the party can stand within use range of it, else the nearest tile, walking along walkable tiles from
    (u, v) for at most `reach` steps, that has such room: IE doorways can be narrower than a ToEE party member
    (I2AR1000 To1004: a one-tile diagonal ramp), so the icon moves back along it to where the party can stand,
    staying on the door's approach; (u, v) if there is none (needs a hand fix: anchor_fix or widening)"""
    return (u, v) if use_room(K, u, v) else walk_to_room(K, u, v, lambda q: use_room(K, *q), reach)


def walk_to_room(K, u, v, good, reach=5):
    """the tile nearest (u, v) among the first walkable tiles reached from it (<= reach steps) that are `good`"""
    seen = {(u, v)}; ring = [(u, v)]
    for _ in range(reach):
        nxt = []
        for a, b in ring:
            for du in (-1, 0, 1):
                for dv in (-1, 0, 1):
                    q = (a + du, b + dv)
                    if q not in seen and P.walk_tile(K, *q):
                        seen.add(q); nxt.append(q)
        ok = [q for q in nxt if good(q)]
        if ok: return min(ok, key=lambda q: (q[0] - u) ** 2 + (q[1] - v) ** 2)
        ring = nxt
    return u, v


def inside(x, y, poly):
    if len(poly) < 3:
        return False
    c = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]; xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            c = not c
        j = i
    return c


def icon_tile(poly):
    cx = sum(p[0] for p in poly) / len(poly); cy = sum(p[1] for p in poly) / len(poly)
    if inside(cx, cy, poly):
        return int(cx), int(cy)
    xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
    best = None
    for u in range(int(min(xs)), int(max(xs)) + 1):
        for v in range(int(min(ys)), int(max(ys)) + 1):
            if inside(u + 0.5, v + 0.5, poly):
                d = (u + 0.5 - cx) ** 2 + (v + 0.5 - cy) ** 2
                if best is None or d < best[0]:
                    best = (d, u, v)
    if best:
        return best[1], best[2]
    # degenerate (2-point segment / tiny strip): the point of the outline nearest the centroid
    p = min(poly, key=lambda q: (q[0] - cx) ** 2 + (q[1] - cy) ** 2)
    return int((p[0] + cx) / 2), int((p[1] + cy) / 2)


def build(areas):
    """-> (icons {area: [(u, v, jp)]}, jumppoint rows [(id, name, map, x, y)], skipped [str])"""
    icons, rows, skipped = {}, [], []
    n = 0
    for area in sorted(areas):
        for r in sorted(areas[area]['regions'], key=lambda r: r['name']):
            if not r.get('dest_map'):
                skipped.append('%s %s -> %s (not converted)' % (area, r['name'], r['dest_area'])); continue
            u, v, _o = areas[r['dest_area']]['entrances'][r['dest_entrance']]
            jp = JP_BASE + n; n += 1
            rows.append((jp, '%s-%s-to-%s' % (area, r['name'], r['dest_area']), r['dest_map'], int(u), int(v)))
            iu, iv = r['anchor'] if r.get('anchor') else icon_tile(r['poly'])
            icons.setdefault(area, []).append((iu, iv, jp))
    return icons, rows, skipped


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--travel', required=True); ap.add_argument('--maps', required=True)
    ap.add_argument('--jumppoints', required=True)
    a = ap.parse_args()
    areas = runpy.run_path(a.travel)['AREAS']
    icons, rows, skipped = build(areas)
    placed = 0
    for area in sorted(icons):   # re-runnable: drop the icons an earlier run put into this area's sectors
        for p in glob.glob(os.path.join(a.maps, area, '*.sec')):
            sec = T.Sector.read(open(p, 'rb').read()); n0 = len(sec.objects)
            sec.objects = [ob for ob in sec.objects if not (ob.proto_num == ICON_PROTO and ob.get('scenery_teleport_to'))]
            if len(sec.objects) != n0: open(p, 'wb').write(sec.write())
    for area, lst in sorted(icons.items()):
        K = load_map_subtiles(os.path.join(a.maps, area))[0] if os.path.isdir(os.path.join(a.maps, area)) else None
        for u, v, jp in lst:
            if K is not None:
                nu, nv = roomy_icon(K, u, v)
                if (nu, nv) != (u, v):
                    print('  icon %d (%s): no room to use it at %d,%d -> moved to %d,%d' % (jp, area, u, v, nu, nv))
                    u, v = nu, nv
                elif not use_room(K, u, v):
                    print('  icon %d (%s) at %d,%d: no room to use it within 2 tiles (fix by hand)' % (jp, area, u, v))
            p = os.path.join(a.maps, area, '%d.sec' % T.sector_of(u, v))
            if not os.path.exists(p):
                skipped.append('%s icon at %d,%d: sector file missing' % (area, u, v)); continue
            sec = T.Sector.read(open(p, 'rb').read())
            o = T.GameObject(T.OBJ_TYPES.index('scenery'), ICON_PROTO)
            o.set('location', T.location(u, v)).set('offset_x', 0.0).set('offset_y', 0.0)
            o.set('flags', ICON_FLAGS).set('radius', ICON_RADIUS).set('3d_render_height', ICON_HEIGHT)
            o.set('scenery_teleport_to', jp)
            sec.objects.append(o)
            # The engine writes a sector's save diffs in tile order (row by row) and reads them back in file order,
            # so a static object appended out of tile order breaks the map on reload ("Cannot read diff footer").
            sec.objects.sort(key=lambda ob: T.loc_xy(ob.get('location'))[::-1])
            b = sec.write(); assert T.Sector.read(b).write() == b
            open(p, 'wb').write(b)
            placed += 1
    # arrivals: a party member must fit on the jump point, else the engine drops the party on some free tile nearby,
    # possibly across a wall (I2AR1004 -> town landed on the far side of the ramp to the door): walk back to room
    by_map = {areas[x]['map']: x for x in areas}
    for k, (jp, name, m, u, v) in enumerate(rows):
        d = os.path.join(a.maps, by_map.get(m, ''))
        if by_map.get(m) and os.path.isdir(d):
            K = load_map_subtiles(d)[0]
            if not P.fits(K, u, v):
                nu, nv = walk_to_room(K, u, v, lambda q: P.fits(K, *q))
                if (nu, nv) != (u, v):
                    print('  jump point %d: no room at %d,%d -> %d,%d' % (jp, u, v, nu, nv))
                    rows[k] = (jp, name, m, nu, nv)
    os.makedirs(os.path.dirname(a.jumppoints), exist_ok=True)
    with open(a.jumppoints, 'w', newline='\r\n') as f:
        f.write('0\tDO NOT USE\t0\t0\t0\n')
        for row in rows:
            f.write('%d\t%s\t%d\t%d\t%d\n' % row)
    print('ie_exiticons: %d exit icons, %d jump points -> %s' % (placed, len(rows), a.jumppoints))
    for s in skipped:
        print('  no icon: ' + s)


if __name__ == '__main__':
    main()

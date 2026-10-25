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
import argparse, os, runpy, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import toeemob as T

JP_BASE = 2000
ICON_PROTO = 2011
# from a vanilla exit icon (Hommlet exterior): flags, radius, render height; the engine also sets them for a fresh one
ICON_FLAGS = -1874852816
ICON_RADIUS, ICON_HEIGHT = 34.32571029663086, 56.51353454589844


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
    for area, lst in sorted(icons.items()):
        for u, v, jp in lst:
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

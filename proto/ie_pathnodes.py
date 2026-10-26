#!/usr/bin/env python3
"""Rewrite each converted map's pathnode.pnd from the baked .sec blocking, with nodes at the places the party walks to.

Temple+ finds long paths (and every path when it has no clearance.bin) through the map's path nodes: it takes the
node nearest (straight-line distance) to the start and to the goal, chains nodes between them, and needs clear
straight lines for the first and last legs. ie2toee's coarse node grid (one node every 10 tiles on fully walkable
tiles) left gaps: the AR1000->AR1001 icon's nearest node was in a separate component, the last leg to the
AR1000->AR1009 icon was blocked, and small interiors like AR1009 had no node at all, so clicks on those exit icons
pushed a walk that failed at once ("Nodes attempt result: 0 ... PF failed").
This pass (run after ie_exiticons) seeds a denser grid plus a node on every exit icon, entrance/arrival tile and
critter position, links mutually visible nodes, and joins stray components to the main one where a clear line exists.

  ie_pathnodes.py --travel <w>/ie_travel_data.py --maps <bake>/modules/ToEE/maps [--spacing 6] [--link 24]
"""
import argparse, glob, math, os, runpy, struct, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import toeemob as T
from toee_sectors import load_map_subtiles


def walk_tile(K, u, v):
    return (K[3 * u:3 * u + 3, 3 * v:3 * v + 3] == 0).all()


def clear(K, p, q):
    n = int(max(abs(p[0] - q[0]), abs(p[1] - q[1])) * 3) + 1
    for s in range(n + 1):
        t = s / n
        if K[int((p[0] + (q[0] - p[0]) * t) * 3 + 1), int((p[1] + (q[1] - p[1]) * t) * 3 + 1)] != 0:
            return False
    return True


def walk_path(K, starts, goals):
    ctr = lambda K, u, v: K[3 * u + 1, 3 * v + 1] == 0
    """tile-level BFS over fully walkable tiles (8-neighbour, no corner cutting) -> [tile...] from a start to a goal"""
    from collections import deque
    prev = {p: None for p in starts}; q = deque(starts)
    while q:
        p = q.popleft()
        if p in goals:
            out = []
            while p is not None: out.append(p); p = prev[p]
            return out[::-1]
        for du in (-1, 0, 1):
            for dv in (-1, 0, 1):
                r = (p[0] + du, p[1] + dv)
                if r in prev or not (0 < r[0] < 959 and 0 < r[1] < 959) or not ctr(K, *r): continue
                if du and dv and not (ctr(K, p[0] + du, p[1]) and ctr(K, p[0], p[1] + dv)): continue
                prev[r] = p; q.append(r)
    return None


def components(n, nb):
    comp = [-1] * n; c = 0
    for s in range(n):
        if comp[s] >= 0: continue
        st = [s]; comp[s] = c
        while st:
            x = st.pop()
            for y in nb[x]:
                if comp[y] < 0: comp[y] = c; st.append(y)
        c += 1
    return comp


def build(K, extra, spacing, link):
    have = np.argwhere((K >= 0).reshape(960, 3, 960, 3).all((1, 3)))
    if not len(have):
        return [], {}
    u0, v0 = have.min(0); u1, v1 = have.max(0)
    pts = set()
    for u in range(int(u0) + spacing // 2, int(u1) + 1, spacing):
        for v in range(int(v0) + spacing // 2, int(v1) + 1, spacing):
            if walk_tile(K, u, v): pts.add((u, v))
    for p in extra:
        p = (int(p[0]), int(p[1]))
        if 0 < p[0] < 959 and 0 < p[1] < 959 and K[3 * p[0] + 1, 3 * p[1] + 1] == 0: pts.add(p)
    nodes = sorted(pts); n = len(nodes)
    nb = {i: set() for i in range(n)}
    for i in range(n):
        for j in range(i + 1, n):
            if math.dist(nodes[i], nodes[j]) <= link and clear(K, nodes[i], nodes[j]):
                nb[i].add(j); nb[j].add(i)
    nodes = list(nodes)
    islands = set()
    for _ in range(200):          # join stray components to the biggest one
        comp = components(len(nodes), nb)
        sizes = np.bincount(comp)
        if len(sizes) <= 1: break
        main = int(np.argmax(sizes)); progress = False
        for c in range(len(sizes)):
            if c == main or not sizes[c]: continue
            mine = [i for i in range(len(nodes)) if comp[i] == c]
            if nodes[mine[0]] in islands: continue
            path = walk_path(K, [nodes[i] for i in mine], set(nodes[i] for i in range(len(nodes)) if comp[i] == main))
            if not path: islands.update(nodes[i] for i in mine); continue    # a real island (not reachable on foot)
            prev = mine[[nodes[i] for i in mine].index(path[0])]
            for k in range(3, len(path) + 2, 3):   # nodes along the walk, each linked to the one before
                q = path[min(k, len(path) - 1)]
                if q in nodes: j = nodes.index(q)
                else:
                    nodes.append(q); j = len(nodes) - 1; nb[j] = set()
                if clear(K, nodes[prev], q) or k == 3:
                    nb[prev].add(j); nb[j].add(prev)
                prev = j
                if k >= len(path) - 1: break
            progress = True; break   # components changed: recompute
        if not progress: break
    for i in range(len(nodes)):  # Temple+ holds at most 64 neighbours per node: keep the nearest 48
        if len(nb[i]) > 48:
            keep = set(sorted(nb[i], key=lambda j: math.dist(nodes[i], nodes[j]))[:48])
            for j in nb[i] - keep: nb[j].discard(i)
            nb[i] = keep
    return nodes, nb


def write(path, nodes, nb):
    out = bytearray(struct.pack('<i', len(nodes)))
    for i, (u, v) in enumerate(nodes):
        ns = sorted(nb[i])
        out += struct.pack('<iIIffi', i, u, v, 0.0, 0.0, len(ns)) + struct.pack('<%di' % len(ns), *ns)
    open(path, 'wb').write(out)


def critter_tiles(mapdir):
    pts = []
    for f in glob.glob(os.path.join(mapdir, '*.mob')):
        try:
            o = T.read_mob(open(f, 'rb').read())
            pts.append(T.loc_xy(o.get('location')))
        except Exception:
            pass
    return pts


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--travel', required=True); ap.add_argument('--maps', required=True)
    ap.add_argument('--spacing', type=int, default=6); ap.add_argument('--link', type=float, default=24)
    a = ap.parse_args()
    areas = runpy.run_path(a.travel)['AREAS']
    for area in sorted(areas):
        mapdir = os.path.join(a.maps, area)
        if not os.path.isdir(mapdir): continue
        K, _ = load_map_subtiles(mapdir)
        d = areas[area]
        extra = [e[:2] for e in d.get('entrances', {}).values()]
        extra += [r['anchor'] for r in d.get('regions', []) if r.get('anchor')]
        extra += critter_tiles(mapdir)
        nodes, nb = build(K, extra, a.spacing, a.link)
        write(os.path.join(mapdir, 'pathnode.pnd'), nodes, nb)
        comp = components(len(nodes), nb)
        print('ie_pathnodes: %s %d nodes, %d components' % (area, len(nodes), len(set(comp))))


if __name__ == '__main__':
    main()

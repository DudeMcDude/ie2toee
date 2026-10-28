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


LEADER = 2   # subtiles of clearance (tile centre to the nearest blocked subtile) a party leader needs to pass
ROOMY = 3    # clearance a node needs: the engine bakes node links with the leader's radius, and a node in a tighter
             # spot gets no links (it showed up as a stray one-node group in AR1000/AR1007/AR1008)


def walk_path(K, starts, goals, need=LEADER):
    ctr = lambda K, u, v: K[3 * u + 1, 3 * v + 1] == 0 and clearance(K, u, v, need) >= need
    """tile-level BFS over tiles the leader fits through (8-neighbour, no corner cutting) -> [tile...] start to goal"""
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


def clearance(K, u, v, cap=6):
    """subtiles from the tile centre to the nearest non-walkable subtile (Chebyshev), capped"""
    cu, cv = 3 * u + 1, 3 * v + 1
    for r in range(cap):
        if (K[max(cu - r, 0):cu + r + 1, max(cv - r, 0):cv + r + 1] != 0).any(): return r
    return cap


SUBTILE_IN = 9.4280901   # inches per subtile (a tile is 3x3)
FIT_RADIUS = 25.0         # nominal PC radius (protos.tab obj_f_radius of the medium PC protos), same as the bake


def edge_dist(S, su, sv, cap=6):
    """inches from the centre of subtile (su, sv) to the nearest non-walkable (blocked, flyover or off-map) subtile.
    Mirrors Temple+ PathDestIsClear: a raycast circle of the mover's radius at the destination that stops at the
    first sector blocker or flyover subtile; a destination is clear when that circle touches none of them."""
    best = cap * SUBTILE_IN
    for i in range(su - cap, su + cap + 1):
        for j in range(sv - cap, sv + cap + 1):
            if 0 <= i < S.shape[0] and 0 <= j < S.shape[1] and S[i, j] == 0: continue
            dx = max(0, abs(i - su) - 0.5); dy = max(0, abs(j - sv) - 0.5)
            best = min(best, math.hypot(dx, dy) * SUBTILE_IN)
    return best


def fits(S, u, v, r=FIT_RADIUS):
    """the engine's exact-point fit check for a mover of radius r at the centre of tile (u, v)"""
    return edge_dist(S, 3 * u + 1, 3 * v + 1) >= r


def nudge(K, p, reach=2, nearest=False):
    """p if a radius-25 mover fits at its centre, else the walkable tile within `reach` tiles where it fits with the
    most room (nearest=True: the nearest such tile, for points that must stay put, like arrivals by a door); p if none"""
    if fits(K, *p): return p
    best = None
    for du in range(-reach, reach + 1):
        for dv in range(-reach, reach + 1):
            q = (p[0] + du, p[1] + dv)
            if not (0 < q[0] < 959 and 0 < q[1] < 959 and walk_tile(K, *q)): continue
            room = edge_dist(K, 3 * q[0] + 1, 3 * q[1] + 1)
            if room < FIT_RADIUS: continue
            key = (du * du + dv * dv, -room) if nearest else (-room, du * du + dv * dv)
            if best is None or key < best[0]: best = (key, q)
    return best[1] if best else p


def roomy(K, p, need=3, reach=3):
    """p, or the nearest fully walkable tile within reach tiles with >= need subtiles of clearance (None: drop it).
    Critters stand behind counters / beside beds: a node in such a pocket gets links out of it, but the engine can't
    path to it exactly, so the baked graph had one-way links and islands there (AR1002/1004/1008/1013)."""
    best = None
    for du in range(-reach, reach + 1):
        for dv in range(-reach, reach + 1):
            q = (p[0] + du, p[1] + dv)
            if 0 < q[0] < 959 and 0 < q[1] < 959 and walk_tile(K, *q) and clearance(K, *q) >= need:
                d = du * du + dv * dv
                if best is None or d < best[0]: best = (d, q)
    return best and best[1]


def build(K, extra, spacing, link, loose=()):
    have = np.argwhere((K >= 0).reshape(960, 3, 960, 3).all((1, 3)))
    if not len(have):
        return [], {}
    u0, v0 = have.min(0); u1, v1 = have.max(0)
    pts = set()
    for u in range(int(u0) + spacing // 2, int(u1) + 1, spacing):
        for v in range(int(v0) + spacing // 2, int(v1) + 1, spacing):
            q = roomy(K, (u, v), need=ROOMY, reach=1)
            if q: pts.add(q)
    keep_pts = set()
    for p in extra:          # entrances / region anchors: a roomy tile nearby if there is one (tight doorway spots gave
        p = (int(p[0]), int(p[1]))   # one-way links in the engine bake, AR1004/AR1013), else the spot itself
        q = roomy(K, p, need=ROOMY, reach=3) or roomy(K, p, need=LEADER, reach=2)
        if q: pts.add(q); keep_pts.add(q)
    for p in set((int(p[0]), int(p[1])) for p in loose):   # critter spots: only where the engine can path in
        q = roomy(K, p, need=ROOMY)
        if q: pts.add(q)
    moved = {p: nudge(K, p) for p in pts}   # borderline spots: move where the engine's exact-point check passes
    keep_pts = set(moved[p] for p in keep_pts)
    build.moved = sum(1 for p, q in moved.items() if p != q)
    pts = set(moved.values())
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
                if k < len(path) - 1: q = max(path[k - 1:k + 2], key=lambda t: clearance(K, *t))   # roomiest step
                if q in nodes: j = nodes.index(q)
                else:
                    nodes.append(q); j = len(nodes) - 1; nb[j] = set()
                if clear(K, nodes[prev], q) or k == 3:
                    nb[prev].add(j); nb[j].add(prev)
                prev = j
                if k >= len(path) - 1: break
            progress = True; break   # components changed: recompute
        if not progress: break
    # islands no walking route reaches (closed-off pockets, behind counters) with no entrance/exit icon in them: drop
    comp = components(len(nodes), nb); main = int(np.argmax(np.bincount(comp))) if len(nodes) else 0
    drop = set()
    for c in set(int(x) for x in comp) - {main}:
        mem = [i for i in range(len(nodes)) if comp[i] == c]
        if nodes[mem[0]] in islands and (len(mem) == 1 or not any(nodes[i] in keep_pts for i in mem)): drop.update(mem)   # a lone anchor node off the walkable net only splits the graph
    if drop:
        idx = {o: k for k, o in enumerate(i for i in range(len(nodes)) if i not in drop)}
        nodes = [nodes[i] for i in idx]
        nb = {idx[i]: set(idx[j] for j in nb[i] if j in idx) for i in idx}
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
    ap.add_argument('--areas', nargs='*', help='only these areas (default: all in the travel data)')
    ap.add_argument('--spacing', type=int, default=6); ap.add_argument('--link', type=float, default=24)
    a = ap.parse_args()
    areas = runpy.run_path(a.travel)['AREAS']
    for area in sorted(areas):
        mapdir = os.path.join(a.maps, area)
        if not os.path.isdir(mapdir) or (a.areas and area not in a.areas): continue
        K, _ = load_map_subtiles(mapdir)
        d = areas[area]
        extra = [e[:2] for e in d.get('entrances', {}).values()]
        extra += [r['anchor'] for r in d.get('regions', []) if r.get('anchor')]
        nodes, nb = build(K, extra, a.spacing, a.link, critter_tiles(mapdir))
        write(os.path.join(mapdir, 'pathnode.pnd'), nodes, nb)
        comp = components(len(nodes), nb)
        print('ie_pathnodes: %s %d nodes, %d components, %d nudged' % (area, len(nodes), len(set(comp)), build.moved))


if __name__ == '__main__':
    main()

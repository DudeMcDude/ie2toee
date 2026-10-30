#!/usr/bin/env python3
"""Offline navigability check of converted maps (baked .sec blocking): from each area's start (the new-game tile or an
entrance), which entrances/arrivals, exit icons, jump-point arrivals and baked objects (.mob: critters, containers,
icons) a party leader reaches (ie_pathnodes.walk_path rule: LEADER subtiles of clearance, no corner cutting), and
whether a radius-25 PC fits on each exit icon / arrival tile (cramped check).

  nav_check.py --travel <w>/ie_travel_data.py --maps <bake>/modules/ToEE/maps [--jumps jumppoint.tab] [--start AREA:u,v]
"""
import argparse, glob, os, runpy, sys
from collections import deque
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import toeemob as T
from toee_sectors import load_map_subtiles
from ie_pathnodes import clearance, fits, LEADER

def reach(K, starts, need=LEADER):
    ok = lambda u, v: 0 < u < 959 and 0 < v < 959 and K[3 * u + 1, 3 * v + 1] == 0 and clearance(K, u, v, need) >= need
    seen = set(s for s in starts if ok(*s)); q = deque(seen)
    while q:
        p = q.popleft()
        for du in (-1, 0, 1):
            for dv in (-1, 0, 1):
                r = (p[0] + du, p[1] + dv)
                if r in seen or not ok(*r): continue
                if du and dv and not (ok(p[0] + du, p[1]) and ok(p[0], p[1] + dv)): continue
                seen.add(r); q.append(r)
    return seen

def near(R, p, d=2):
    return any((p[0] + a, p[1] + b) in R for a in range(-d, d + 1) for b in range(-d, d + 1))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--travel', required=True); ap.add_argument('--maps', required=True)
    ap.add_argument('--jumps'); ap.add_argument('--start', action='append', default=[])
    a = ap.parse_args()
    areas = runpy.run_path(a.travel)['AREAS']; st = dict((s.split(':')[0], tuple(map(int, s.split(':')[1].split(',')))) for s in a.start)
    J = {}
    if a.jumps:
        for ln in open(a.jumps):
            f = ln.strip().split('\t')
            if len(f) == 5 and f[0] != '0': J.setdefault(int(f[2]), []).append((f[1], (int(f[3]), int(f[4]))))
    bad = 0
    for area in sorted(areas):
        md = os.path.join(a.maps, area)
        if not os.path.isdir(md): continue
        K, _ = load_map_subtiles(md); d = areas[area]
        ents = dict((n, tuple(e[:2])) for n, e in d.get('entrances', {}).items())
        s0 = st.get(area) or next(iter(ents.values()))
        R = reach(K, [s0] + [(s0[0] + x, s0[1] + y) for x in (-1, 0, 1) for y in (-1, 0, 1)])
        rows = [('start', s0, bool(R))]
        rows += [('entrance ' + n, p, near(R, p)) for n, p in sorted(ents.items())]
        rows += [('arrival ' + n, p, near(R, p)) for n, p in J.get(d['map'], [])]
        rows += [('icon ' + r['name'], tuple(r['anchor']), near(R, tuple(r['anchor']), 3)) for r in d.get('regions', []) if r.get('dest_map')]
        objs = []
        for f in glob.glob(os.path.join(md, '*.mob')):
            try:
                o = T.read_mob(open(f, 'rb').read()); objs.append(tuple(T.loc_xy(o.get('location'))))
            except Exception:
                pass
        unr = [p for p in objs if not near(R, p, 3)]
        cr = [(n, p) for n, p, _ in rows[1:] if (n.startswith('arrival') or n.startswith('entrance')) and not fits(K, *p)]
        fails = [r for r in rows if not r[2]]
        bad += len(fails)
        print('%s: reach %d tiles from %s; %d/%d checks ok; objects %d/%d reachable; cramped %d' % (
            area, len(R), s0, len(rows) - len(fails), len(rows), len(objs) - len(unr), len(objs), len(cr)))
        for n, p, _ in fails: print('   FAIL %s %s' % (n, p))
        for n, p in cr: print('   CRAMPED %s %s' % (n, p))
        if unr: print('   unreachable objects: %s' % unr[:12])
    sys.exit(1 if bad else 0)

if __name__ == '__main__':
    main()

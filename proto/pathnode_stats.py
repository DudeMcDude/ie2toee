"""Offline check of baked path nodes: per map nodes / links / max neighbours / non-reciprocal links / components and
whether pathnodedist.pnd + clearance.bin are present.   python pathnode_stats.py <maps dir> [areas...]"""
import os, struct, sys

def read_pnd(path):
    b = open(path, 'rb').read(); n, = struct.unpack_from('<i', b, 0); o = 4; nodes = {}
    for _ in range(n):
        i, x, y, ox, oy, c = struct.unpack_from('<iIIffi', b, o); o += 24
        nodes[i] = ((x, y), list(struct.unpack_from('<%di' % c, b, o))); o += 4 * c
    return nodes

def stats(d):
    f = os.path.join(d, 'pathnodenew.pnd')
    baked = os.path.isfile(f)
    nodes = read_pnd(f if baked else os.path.join(d, 'pathnode.pnd'))
    links = sum(len(v[1]) for v in nodes.values()); mx = max([len(v[1]) for v in nodes.values()] or [0])
    nonrecip = sum(1 for i, v in nodes.items() for j in v[1] if j not in nodes or i not in nodes[j][1])
    seen, comps = set(), 0
    for s in nodes:
        if s in seen: continue
        comps += 1; st = [s]; seen.add(s)
        while st:
            for j in nodes[st.pop()][1]:
                if j in nodes and j not in seen: seen.add(j); st.append(j)
    return baked, len(nodes), links, mx, nonrecip, comps, os.path.isfile(os.path.join(d, 'pathnodedist.pnd')), os.path.isfile(os.path.join(d, 'clearance.bin'))

if __name__ == '__main__':
    M = sys.argv[1]; areas = sys.argv[2:] or sorted(a for a in os.listdir(M) if os.path.isfile(os.path.join(M, a, 'pathnode.pnd')))
    print('area    baked nodes links maxnb nonrecip comps dist clearance')
    for a in areas:
        print('%-7s %-5s %5d %5d %5d %8d %5d %-4s %s' % ((a,) + stats(os.path.join(M, a))))

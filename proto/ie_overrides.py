#!/usr/bin/env python3
"""Per-map hand overrides that survive a reconversion: overrides/<game>/<AREA>/ (see overrides/README.md).

  * Temple+ DM tile edits (*.json, format "templeplus-dm-tile-edits", the files "Save Tile Edits" writes to
    <Saved Games>\\TemplePlus\\dm_tile_edits\\<module>\\map<id>.json, dropped in unchanged): ie2toee.py applies them
    to the tile flags right after the search map (incl. "searchmap_fix") is turned into tiles, before the .sec files
    are written, so the path node generator and everything after it see the edited map.
  * Engine path node data (pathnodenew.pnd, pathnodedist.pnd, clearance.bin; any subset): copied into the map folder
    after the path node generator (ie_pathnodes.py) and again after the optional engine bake (--engine-pathnodes),
    so they win. Temple+ loads pathnodenew.pnd in preference to the generator's pathnode.pnd.

  python3 ie_overrides.py show [--root overrides/iwd]
  python3 ie_overrides.py install-pathnodes --maps "<ToEE>/modules/IWD/maps" [--root overrides/iwd] [--area AR1000]
      (copies the path node overrides into an existing install, no reconversion)
The override files hold only tile coordinates / bit masks and engine path node data (no IE game data).
"""
import argparse, glob, json, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = {'iwd': os.path.join(HERE, 'overrides', 'iwd')}
TILE_FORMAT = 'templeplus-dm-tile-edits'
EDITABLE = 0x0FFFFE00          # block 0x200<<s, flyover 0x40000<<s (s = sy*3+sx), cover 0x8000000
BLOCK0, FLY0 = 0x200, 0x40000
PATHNODE_FILES = ('pathnodenew.pnd', 'pathnodedist.pnd', 'clearance.bin')


def area_dir(root, area):
    """overrides/<game>/<AREA> (case-insensitive match), or None"""
    if not root or not os.path.isdir(root):
        return None
    for n in os.listdir(root):
        if n.upper() == area.upper() and os.path.isdir(os.path.join(root, n)):
            return os.path.join(root, n)
    return None


def load_tile_edits(root, area, warn=print):
    """[(u, v, set, clear, before), ...] from every DM tile edit file in overrides/<game>/<AREA>/, oldest saved_utc
    first (applied in order, so a newer file wins per bit). A file whose map_name names another area is skipped."""
    d = area_dir(root, area)
    if not d:
        return []
    docs = []
    for f in sorted(glob.glob(os.path.join(d, '*.json'))):
        try:
            j = json.load(open(f, encoding='utf-8'))
        except (OSError, ValueError) as e:
            warn('overrides: skip %s: %s' % (f, e)); continue
        if not isinstance(j, dict) or j.get('format') != TILE_FORMAT:
            continue
        if int(j.get('version', 1)) != 1:
            warn('overrides: skip %s: unknown version %s' % (f, j.get('version'))); continue
        if j.get('map_name') and j['map_name'].upper() != area.upper():
            warn('overrides: skip %s: it is for %s, not %s' % (f, j['map_name'], area)); continue
        docs.append((j.get('saved_utc', ''), f, j))
    out = []
    for _, f, j in sorted(docs):
        for t in j.get('tiles', []):
            s, c = int(t.get('set', 0)) & EDITABLE, int(t.get('clear', 0)) & EDITABLE
            out.append((int(t['x']), int(t['y']), s, c & ~s, t.get('before')))
    return out


def door_bits(are_doors, door_cell_masks, pl, sr_shape):
    """{(u, v): mask} of the Block bits doors switch at runtime (runtime/ie_doors.py rewrites them from the
    converter's base + the door state), the same cells the Temple+ tile editor protects"""
    m = {}
    for d in are_doors:
        for cells in (d['open_cells'], d['closed_cells']):
            for k, b in door_cell_masks(cells, pl, sr_shape).items():
                m[k] = m.get(k, 0) | b
    return m


def apply_tile_edits(edits, bbox, flags, kind=None, doors=None, stats=None):
    """Apply edits to a bbox-relative tile grid in place: flags[a, b] = (flags & ~clear) | set, minus door bits;
    kind[a, b, i, j] (0 walk, 1 block, 2 flyover; subtile i = x, j = y) is rebuilt from the new flags.
    stats (dict) collects tiles / door_bits_dropped / stale / outside counts."""
    st = stats if stats is not None else {}
    for k in ('tiles', 'door_bits_dropped', 'stale', 'outside'):
        st.setdefault(k, 0)
    u0, v0 = bbox[0], bbox[2]
    for u, v, s, c, before in edits:
        a, b = u - u0, v - v0
        if not (0 <= a < flags.shape[0] and 0 <= b < flags.shape[1]):
            st['outside'] += 1; continue
        dm = (doors or {}).get((u, v), 0)
        if dm & (s | c):
            st['door_bits_dropped'] += bin(dm & (s | c)).count('1')
            s &= ~dm; c &= ~dm
        cur = int(flags[a, b])
        if before is not None and (cur & EDITABLE) != (int(before) & EDITABLE):
            st['stale'] += 1     # the converted tile differs from what was painted on (applied anyway, like Temple+)
        f = (cur & ~c) | s
        flags[a, b] = f
        if kind is not None:
            for i in range(3):
                for j in range(3):
                    sh = i + 3 * j
                    kind[a, b, i, j] = 1 if f & (BLOCK0 << sh) else (2 if f & (FLY0 << sh) else 0)
        st['tiles'] += 1
    return st


def install_pathnodes(root, area, mapdir):
    """copy overrides/<game>/<AREA>/{pathnodenew.pnd,pathnodedist.pnd,clearance.bin} (those present) into mapdir"""
    d = area_dir(root, area)
    if not d or not os.path.isdir(mapdir):
        return []
    done = []
    for n in PATHNODE_FILES:
        p = os.path.join(d, n)
        if os.path.isfile(p):
            shutil.copyfile(p, os.path.join(mapdir, n)); done.append(n)
    return done


def areas(root):
    return sorted(n.upper() for n in os.listdir(root) if os.path.isdir(os.path.join(root, n))) if root and os.path.isdir(root) else []


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=('show', 'install-pathnodes'))
    ap.add_argument('--root', default=DEFAULT_ROOT['iwd'])
    ap.add_argument('--maps', help='install-pathnodes: the installed module maps folder (<ToEE>/modules/IWD/maps)')
    ap.add_argument('--area', action='append', default=[])
    a = ap.parse_args()
    want = [x.upper() for x in a.area] or areas(a.root)
    for ar in want:
        if a.cmd == 'show':
            e = load_tile_edits(a.root, ar)
            d = area_dir(a.root, ar)
            pn = [n for n in PATHNODE_FILES if d and os.path.isfile(os.path.join(d, n))]
            print('%s: %d tile edit(s)%s' % (ar, len(e), (', path nodes: ' + ' '.join(pn)) if pn else ''))
        else:
            if not a.maps:
                sys.exit('--maps is required')
            md = os.path.join(a.maps, ar)
            got = install_pathnodes(a.root, ar, md)
            print('%s: %s' % (ar, ' '.join(got) if got else ('no map folder %s' % md if not os.path.isdir(md) else 'nothing to copy')))


if __name__ == '__main__':
    main()

"""Rewrite converted IE inventory icons so transparent pixels are (0,0,0,0).

ToEE's equipped-slot widgets ignore alpha and show leftover IE green (0,255,0)
in the RGB channels. The inventory bag uses alpha, so those icons already looked fine.

  python fix_inventory_icons.py "C:\\path\\to\\ToEE copy"
"""
import glob, os, struct, sys


def _rewrite(path):
    data = open(path, 'rb').read()
    if len(data) < 18:
        return False
    idlen, cmap, itype, cmaporg, cmaplen, cmapdepth, x0, y0, w, h, bpp, desc = struct.unpack_from(
        '<BBBHHBHHHHBB', data)
    off = 18 + idlen
    if itype != 2 or bpp != 32 or w <= 0 or h <= 0:
        return False
    px = bytearray(data[off:off + w * h * 4])
    if len(px) < w * h * 4:
        return False
    changed = False
    for i in range(0, len(px), 4):
        # TGA is BGRA; alpha 0 with any RGB left over (typically IE green)
        if px[i + 3] == 0 and (px[i] or px[i + 1] or px[i + 2]):
            px[i] = px[i + 1] = px[i + 2] = 0
            changed = True
    if changed:
        open(path, 'wb').write(data[:off] + px + data[off + len(px):])
    return changed


def main(argv):
    if len(argv) != 2:
        sys.exit('Usage: fix_inventory_icons.py "C:\\path\\to\\ToEE copy"')
    root = os.path.abspath(argv[1])
    idir = os.path.join(root, 'data', 'art', 'interface', 'inventory')
    files = sorted(glob.glob(os.path.join(idir, 'ie2toee_*.tga')))
    if not files:
        sys.exit('No ie2toee_*.tga icons in %s' % idir)
    n = sum(1 for f in files if _rewrite(f))
    print('Updated %d of %d converted inventory icons in %s' % (n, len(files), idir))


if __name__ == '__main__':
    main(sys.argv)

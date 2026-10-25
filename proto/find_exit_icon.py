#!/usr/bin/env python3
"""Developer tool for run_ingame.sh (CLICKICON): print the screen position of a ToEE exit icon (the bright blue
map-change marker) in a screenshot of the test desktop, or nothing if none is visible.
  find_exit_icon.py shot.png [dx,dy ...]
With tile offsets (icon minus party leader, the wanted icon first) it picks the blob whose neighbours best match the
other icons' predicted isometric screen offsets; without them, the most prominent blob."""
import sys
import numpy as np
from PIL import Image
a = np.asarray(Image.open(sys.argv[1]).convert('RGB')).astype(int)
r, g, b = a[..., 0], a[..., 1], a[..., 2]
m = (b > 180) & (b > r + 120) & (g > 80)
m[:100, :] = False                              # window title bar
m[630:, 960:] = False; m[630:, :300] = False    # HUD (radial buttons, portraits)
H, W = m.shape; B = 12
c = m[:H // B * B, :W // B * B].reshape(H // B, B, W // B, B).sum((1, 3))
blobs = []                                      # strongest cells, merged when close
for i in np.argsort(c.ravel())[::-1]:
    if c.ravel()[i] < 30:
        break
    x0, y0 = i % c.shape[1] * B + B // 2, i // c.shape[1] * B + B // 2
    if all(abs(x0 - x) > 40 or abs(y0 - y) > 50 for x, y in blobs):
        ys, xs = np.nonzero(m[max(0, y0 - 24):y0 + 24, max(0, x0 - 18):x0 + 18])
        blobs.append((int(xs.mean()) + max(0, x0 - 18), int(ys.mean()) + max(0, y0 - 24)))
if not blobs:
    sys.exit(0)
offs = [tuple(int(t) for t in s.split(',')) for s in sys.argv[2:]]
def screen(d):                                  # tile offset -> approximate screen offset (1280x800 view)
    return 20 * (d[1] - d[0]), 15 * (d[0] + d[1])
best = blobs[0]
if offs:
    def score(bl):
        tx, ty = screen(offs[0]); lx, ly = bl[0] - tx, bl[1] - ty
        s = 0
        for d in offs[1:]:
            px, py = lx + screen(d)[0], ly + screen(d)[1]
            if 130 < px < 1150 and 100 < py < 630:   # predicted on screen: should be near a blob
                s += min(min(abs(px - x) + abs(py - y) for x, y in blobs), 300)
        for x, y in blobs:                           # every blob should be explained by some icon
            s += min(min(abs(lx + screen(d)[0] - x) + abs(ly + screen(d)[1] - y) for d in offs), 300)
        return s
    best = min(blobs, key=score)
print('%d %d' % best)

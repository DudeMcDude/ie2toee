#!/usr/bin/env python3
"""Re-read a converted map from the ToEE side only (ground JPGs + .sec files) and paint the blocking onto
the reassembled ground art: red = Block, blue = FlyOver subtiles. If the art and the blocking line up, the
converter's projection is consistent with the engine's.
  python3 verify_toee_output.py --out <outdir> --area AR1000 [--cal dx dy] [--scale-down 2]
"""
import argparse, glob, os, re, sys
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ie2toee as T
from toee_sectors import load_map_subtiles

ap = argparse.ArgumentParser()
ap.add_argument('--out', required=True); ap.add_argument('--area', required=True)
ap.add_argument('--cal', type=float, nargs=2, default=(0, 0)); ap.add_argument('--scale-down', type=int, default=2)
a = ap.parse_args()
gdir = os.path.join(a.out, 'art', 'ground', a.area)
tiles = {}
for f in glob.glob(os.path.join(gdir, '*.jpg')):
    m = re.match(r'([0-9a-f]{4})([0-9a-f]{4})\.jpg', os.path.basename(f))
    tiles[(int(m.group(2), 16), int(m.group(1), 16))] = f
xs = [k[0] for k in tiles]; ys = [k[1] for k in tiles]
x0, y0 = min(xs) * 256, min(ys) * 256
canvas = Image.new('RGB', ((max(xs) + 1) * 256 - x0, (max(ys) + 1) * 256 - y0))
for (tx, ty), f in tiles.items():
    canvas.paste(Image.open(f), (tx * 256 - x0, ty * 256 - y0))
K, _ = load_map_subtiles(os.path.join(a.out, 'maps', a.area))
pl = T.Placement(1, 1, cal=a.cal)   # only CAL matters for tile_to_canvas
ov = Image.new('RGBA', canvas.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
su, sv = np.nonzero(K > 0)
for s, t in zip(su, sv):
    u, v = s / 3.0, t / 3.0
    pts = [pl.tile_to_canvas(u + du, v + dv) for du, dv in ((0, 0), (1 / 3, 0), (1 / 3, 1 / 3), (0, 1 / 3))]
    pts = [(float(X) - x0, float(Y) - y0) for X, Y in pts]
    if all(-50 < p[0] < canvas.size[0] + 50 and -50 < p[1] < canvas.size[1] + 50 for p in pts):
        d.polygon(pts, fill=(255, 0, 0, 110) if K[s, t] == 1 else (0, 90, 255, 110))
out = Image.alpha_composite(canvas.convert('RGBA'), ov).convert('RGB')
if a.scale_down > 1:
    out = out.resize((out.size[0] // a.scale_down, out.size[1] // a.scale_down), Image.LANCZOS)
p = os.path.join(a.out, f'{a.area}_verify.png'); out.save(p); print(p, out.size)

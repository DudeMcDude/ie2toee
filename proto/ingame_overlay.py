#!/usr/bin/env python3
"""Register an in-game screenshot against the converted ground art (FFT template match), then draw the
converted map's Block/FlyOver subtiles and the leader's logged tile on top of the screenshot.
  python3 ingame_overlay.py --out ../out --area AR1000 --shot shot.png --leader 470 451 0 0 --dst overlay.png
"""
import argparse, glob, os, re, sys
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ie2toee as T
from toee_sectors import load_map_subtiles

ap = argparse.ArgumentParser()
ap.add_argument('--out', required=True); ap.add_argument('--area', required=True)
ap.add_argument('--shot', required=True); ap.add_argument('--dst', required=True)
ap.add_argument('--leader', type=float, nargs=4, help='tile x y and off_x off_y (inches)')
ap.add_argument('--leader-screen', type=float, nargs=2, help='skip matching: leader is drawn at this screen px (after scroll_to)')
ap.add_argument('--patch', type=int, nargs=4, default=None, help='screenshot patch x y w h used for matching')
a = ap.parse_args()

tiles = {}
for f in glob.glob(os.path.join(a.out, 'art', 'ground', a.area, '*.jpg')):
    m = re.match(r'([0-9a-f]{4})([0-9a-f]{4})\.jpg', os.path.basename(f)); tiles[(int(m[2], 16), int(m[1], 16))] = f
xs = [k[0] for k in tiles]; ys = [k[1] for k in tiles]; x0, y0 = min(xs) * 256, min(ys) * 256
canvas = Image.new('RGB', ((max(xs) + 1) * 256 - x0, (max(ys) + 1) * 256 - y0))
for (tx, ty), f in tiles.items():
    canvas.paste(Image.open(f), (tx * 256 - x0, ty * 256 - y0))
C = np.asarray(canvas.convert('L'), np.float32)
shot = Image.open(a.shot).convert('RGB'); S = np.asarray(shot.convert('L'), np.float32)
px, py, pw, ph = a.patch or (S.shape[1] // 2 - 250, S.shape[0] // 2 - 330, 220, 160)  # default: above-left of centre
P = S[py:py + ph, px:px + pw]; P = P - P.mean()
# zero-mean cross-correlation, normalised by local canvas energy
F = np.fft.rfft2(C); n = C.shape
corr = np.fft.irfft2(F * np.conj(np.fft.rfft2(P, n)), n)
O = np.conj(np.fft.rfft2(np.ones_like(P), n))
ones = np.fft.irfft2(np.fft.rfft2(C * C) * O, n)
sums = np.fft.irfft2(F * O, n)
var = ones - sums ** 2 / P.size
var = np.where(var > 0.05 * var.max(), var, np.inf)   # ignore flat (saturated snow / black) windows
ncc = corr / np.sqrt(var * (P ** 2).sum())
cy, cx = np.unravel_index(np.argmax(ncc), ncc.shape)
score = float(ncc[cy, cx])
# canvas pixel (cx + x0, cy + y0) appears at screen (px, py)
offX, offY = cx + x0 - px, cy + y0 - py      # canvas = screen + off
if a.leader_screen:
    pl0 = T.Placement(1, 1)
    LX, LY = pl0.tile_to_canvas(a.leader[0] + 0.5 + a.leader[2] / T.INCH_PER_TILE, a.leader[1] + 0.5 + a.leader[3] / T.INCH_PER_TILE)
    offX, offY = float(LX) - a.leader_screen[0], float(LY) - a.leader_screen[1]
    # report how well the art matches at that offset
    sx, sy = int(round(offX - x0 + px)), int(round(offY - y0 + py))
    Q = C[sy:sy + ph, sx:sx + pw]; Q = Q - Q.mean()
    score = float((P * Q).sum() / np.sqrt((P ** 2).sum() * (Q ** 2).sum()))
print(f'match ncc={score:.3f} canvas-screen offset=({offX},{offY})')
K, _ = load_map_subtiles(os.path.join(a.out, 'maps', a.area))
pl = T.Placement(1, 1)
ov = Image.new('RGBA', shot.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
W, H = shot.size
# subtiles visible on screen
cu, cv = pl.canvas_to_tile(offX + W / 2, offY + H / 2)
r = int(max(W, H) / 20) + 4
for s in range(max(0, int((cu - r) * 3)), min(2880, int((cu + r) * 3))):
    for t in range(max(0, int((cv - r) * 3)), min(2880, int((cv + r) * 3))):
        k = K[s, t]
        if k <= 0:
            continue
        u, v = s / 3.0, t / 3.0
        pts = [pl.tile_to_canvas(u + du, v + dv) for du, dv in ((0, 0), (1 / 3, 0), (1 / 3, 1 / 3), (0, 1 / 3))]
        pts = [(float(X) - offX, float(Y) - offY) for X, Y in pts]
        if all(-30 < p[0] < W + 30 and -30 < p[1] < H + 30 for p in pts):
            d.polygon(pts, fill=(255, 0, 0, 70) if k == 1 else (0, 90, 255, 70))
if a.leader:
    lx, ly, ox, oy = a.leader
    u = lx + 0.5 + ox / T.INCH_PER_TILE; v = ly + 0.5 + oy / T.INCH_PER_TILE
    X, Y = pl.tile_to_canvas(u, v); X -= offX; Y -= offY
    d.ellipse([X - 6, Y - 6, X + 6, Y + 6], outline=(255, 255, 0, 255), width=3)
    d.line([X - 14, Y, X + 14, Y], fill=(255, 255, 0, 255), width=1); d.line([X, Y - 14, X, Y + 14], fill=(255, 255, 0, 255), width=1)
    print(f'leader predicted at screen ({X:.0f},{Y:.0f})')
d.rectangle([px, py, px + pw, py + ph], outline=(0, 255, 0, 255), width=2)
dj = os.path.join(a.out, f'{a.area}_doors.json')
if os.path.exists(dj):
    import json
    for door in json.load(open(dj))['doors']:
        p = door['patches'].get('closed')
        if p:
            d.rectangle([p['x'] - offX, p['y'] - offY, p['x'] + p['w'] - offX, p['y'] + p['h'] - offY], outline=(255, 255, 0, 255), width=2)
            d.text((p['x'] - offX + 3, p['y'] - offY + 3), door['name'], fill=(255, 255, 0, 255))
Image.alpha_composite(shot.convert('RGBA'), ov).convert('RGB').save(a.dst)
print(a.dst)

#!/usr/bin/env python3
"""Side-by-side closed/open crops per door: WED tile variant patch + that state's impeded cells (red).
  python3 door_debug.py --game IWD --area AR5404 --out ../out"""
import argparse, json, os, sys
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ie2toee as T
ap = argparse.ArgumentParser(); ap.add_argument('--game'); ap.add_argument('--area'); ap.add_argument('--out')
a = ap.parse_args()
guid = json.loads(json.dumps(T.DEFAULT_GUIDANCE))
g, are, wed, img, sr, closed, tis_for = T.load_area(a.game, a.area, guid)
W, H = wed.size_px; pl = T.Placement(W, H)
D = json.load(open(os.path.join(a.out, f'{a.area}_doors.json')))['doors']
rows = []
for d, ad in zip(D, are.doors):
    if not d['patches']:
        continue
    p = d['patches']['closed']; x0, y0 = p['x'] - pl.cx - 32, p['y'] - pl.cy - 32; w, h = p['w'] + 64, p['h'] + 64
    pair = []
    for state, cells in (('closed', ad['closed_cells']), ('open', ad['open_cells'])):
        base = Image.fromarray(img[max(0, y0):y0 + h, max(0, x0):x0 + w, :3].copy())
        pt = d['patches'][state]
        patch = Image.open(os.path.join(a.out, pt['texture']))
        base.paste(patch.convert('RGB'), (pt['x'] - pl.cx - max(0, x0), pt['y'] - pl.cy - max(0, y0)), patch.convert('RGBA'))
        dr = ImageDraw.Draw(base, 'RGBA')
        for cx, cy in cells:
            X, Y = cx * 16 - max(0, x0), cy * 12 - max(0, y0)
            dr.rectangle([X, Y, X + 15, Y + 11], fill=(255, 0, 0, 110))
        dr.text((4, 4), f"{d['name']} {state}", fill=(255, 255, 0, 255))
        pair.append(base)
    row = Image.new('RGB', (pair[0].width * 2 + 8, pair[0].height)); row.paste(pair[0], (0, 0)); row.paste(pair[1], (pair[0].width + 8, 0))
    rows.append(row)
out = Image.new('RGB', (max(r.width for r in rows), sum(r.height + 8 for r in rows)))
y = 0
for r in rows:
    out.paste(r, (0, y)); y += r.height + 8
p = os.path.join(a.out, f'{a.area}_doors_debug.png'); out.save(p); print(p, out.size)

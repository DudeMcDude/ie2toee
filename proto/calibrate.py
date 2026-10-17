#!/usr/bin/env python3
"""Calibrate the art->tile placement of a converted IE area against a hand-made ToEE map.

Generates subtile walkability from the IE search map (with the default placement/CAL), then finds
the integer subtile shift (du, dv) that maximises 3-class agreement (walk/block/flyover) with the
reference .sec files, via FFT cross-correlation. Reports agreement %, confusion matrix, and the
implied canvas-pixel correction.
  python3 calibrate.py --game IWD --area AR1000 --ref <ToEE map dir> [--scale 1.0] [--out dir]
"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ie2toee as T
from toee_sectors import load_map_subtiles


def generated_subtiles(sr, pl, guidance):
    """kind[2880,2880] for the whole map; -1 outside the IE image."""
    n = 2880
    s = (np.arange(n) + 0.5) / 3.0
    SU, SV = np.meshgrid(s, s, indexing='ij')
    kind, mat = T.sample_kinds(sr, pl, guidance, SU, SV)
    X, Y = pl.tile_to_ie(SU, SV)
    inside = (X >= 0) & (Y >= 0) & (X < sr.shape[1] * T.SR_CELL_W) & (Y < sr.shape[0] * T.SR_CELL_H)
    return np.where(inside, kind, -1).astype(np.int8)


def xcorr(A, B, maxs):
    """C[du,dv] = sum_x A[x] * B[x + d] for |d|<=maxs."""
    n = A.shape[0] + maxs
    fa = np.fft.rfft2(A.astype(np.float32), (n * 2, n * 2))
    fb = np.fft.rfft2(B.astype(np.float32), (n * 2, n * 2))
    c = np.fft.irfft2(np.conj(fa) * fb, (n * 2, n * 2))
    idx = np.r_[np.arange(-maxs, maxs + 1)] % (n * 2)
    return c[np.ix_(idx, idx)]


def score(G, R, du, dv):
    """Compare generated G shifted by (du,dv) with reference R where both defined."""
    Gs = np.full_like(G, -1)
    sl = lambda d, n: (slice(max(0, -d), n - max(0, d)), slice(max(0, d), n - max(0, -d)))
    a, b = sl(du, G.shape[0]); c, d = sl(dv, G.shape[1])
    Gs[b, d] = G[a, c]
    m = (Gs >= 0) & (R >= 0)
    conf = np.zeros((3, 3), int)
    for i in range(3):
        for j in range(3):
            conf[i, j] = int(((Gs == i) & (R == j) & m).sum())
    return Gs, m, conf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--game', required=True); ap.add_argument('--area', required=True)
    ap.add_argument('--ref', required=True); ap.add_argument('--out', default='.')
    ap.add_argument('--scale', type=float, default=1.0); ap.add_argument('--maxshift', type=int, default=360); ap.add_argument('--fine', type=int, default=6)
    a = ap.parse_args()
    guid = json.loads(json.dumps(T.DEFAULT_GUIDANCE)); guid['scale'] = a.scale
    g, are, wed, img, sr, _, _ = T.load_area(a.game, a.area, guid)
    W, H = wed.size_px
    pl = T.Placement(W, H, a.scale)
    G = generated_subtiles(sr, pl, guid)
    R, _ = load_map_subtiles(a.ref)
    R = np.where(R < 0, -1, R)
    # 1) coarse: FFT cross-correlation of the walk/non-walk indicator (+1/-1, 0 = undefined), integer subtiles.
    #    (3-class correlation is unreliable: hand-made maps often paint IE obstacles as FlyOver.)
    A = np.where(G < 0, 0, np.where(G == 0, 1.0, -1.0)); B = np.where(R < 0, 0, np.where(R == 0, 1.0, -1.0))
    tot = xcorr(A, B, a.maxshift)
    du, dv = np.unravel_index(np.argmax(tot), tot.shape); du -= a.maxshift; dv -= a.maxshift
    t2 = tot.copy(); c0 = (du + a.maxshift, dv + a.maxshift)
    t2[max(0, c0[0] - 15):c0[0] + 16, max(0, c0[1] - 15):c0[1] + 16] = -1e18
    peak_ratio = float(tot.max() / t2.max())
    dtu, dtv = du / 3.0, dv / 3.0
    coarse = [(dtu - dtv) * 20.0, -(dtu + dtv) * 14.0]   # CAL correction (canvas px) equivalent to the shift

    def agreement(cal):
        Gc = generated_subtiles(sr, T.Placement(W, H, a.scale, cal=cal), guid)
        m = (Gc >= 0) & (R >= 0)
        return (((Gc == 0) == (R == 0)) & m).sum() / m.sum(), Gc, m
    # 2) fine: regenerate with fractional CAL around the coarse optimum
    best = None
    for ddx in range(-a.fine, a.fine + 1, 2):
        for ddy in range(-a.fine, a.fine + 1, 2):
            cal = (round(coarse[0]) + ddx, round(coarse[1]) + ddy)
            ag = agreement(cal)[0]
            if best is None or ag > best[1]:
                best = (cal, ag)
    cal = best[0]
    _, Gs, m = agreement(cal)
    ag0, _, m0 = agreement((0, 0))
    conf = np.zeros((3, 3), int)
    for i in range(3):
        for j in range(3):
            conf[i, j] = int(((Gs == i) & (R == j) & m).sum())
    eq = ((Gs == 0) == (R == 0)) | ~m
    tile_eq = eq.reshape(960, 3, 960, 3).all((1, 3)); tile_def = m.reshape(960, 3, 960, 3).all((1, 3))
    rw, gw = (R == 0) & m, (Gs == 0) & m
    res = dict(area=a.area, scale=a.scale, coarse_shift_subtiles=[int(du), int(dv)], coarse_cal_px=coarse,
               peak_ratio_vs_second=peak_ratio, best_cal_px=list(cal),
               agreement_walk_binary=float(best[1]), agreement_walk_binary_at_cal0=float(ag0),
               agreement_3class=float(np.trace(conf) / conf.sum()),
               agreement_tiles_all9_binary=float(tile_eq[tile_def].mean()), compared_tiles=int(tile_def.sum()),
               compared_subtiles=int(m.sum()),
               walk_iou=float((rw & gw).sum() / (rw | gw).sum()),
               confusion_gen_rows_ref_cols_walk_block_fly=conf.tolist())
    print(json.dumps(res, indent=1))
    os.makedirs(a.out, exist_ok=True)
    json.dump(res, open(os.path.join(a.out, f'{a.area}_calibration.json'), 'w'), indent=1)
    np.save(os.path.join(a.out, f'{a.area}_gen_shifted.npy'), Gs)
    # diff image (subtile grid, u down, v right): green agree-walk, grey agree-nonwalk, red gen-walk/ref-not, yellow ref-walk/gen-not
    from PIL import Image
    im = np.zeros(R.shape + (3,), np.uint8)
    im[(Gs == R) & m & (R == 0)] = (60, 170, 60)
    im[(Gs == R) & m & (R != 0)] = (90, 90, 90)
    im[m & (Gs == 0) & (R != 0)] = (230, 40, 40)
    im[m & (Gs != 0) & (R == 0)] = (240, 220, 0)
    im[m & (Gs == 1) & (R == 2)] = (120, 60, 160)
    im[m & (Gs == 2) & (R == 1)] = (160, 60, 120)
    ys, xs = np.nonzero(m)
    Image.fromarray(im[ys.min():ys.max() + 1, xs.min():xs.max() + 1]).save(os.path.join(a.out, f'{a.area}_calibration_diff.png'))


if __name__ == '__main__':
    main()

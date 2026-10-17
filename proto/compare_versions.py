"""Compare one area between two IE installs (e.g. classic IWD vs IWD:EE): background art diff,
search-map (walkability) agreement, ARE object counts. Writes images/JSON to --out (local only)."""
import argparse, json, os, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from iefs import IEGame
from ie2toee import load_area
from ieformats import load_index_bmp

def walk_mask(sr):
    import ie2toee
    f = getattr(ie2toee, 'sr_walkable', None)
    if f:
        return f(sr)
    return ~np.isin(sr, (0, 8, 10, 12, 13))  # converter's default terrain table: 0/10/13 block, 8/12 flyover


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--a', required=True); ap.add_argument('--b', required=True)
    ap.add_argument('--area', required=True); ap.add_argument('--out', required=True)
    o = ap.parse_args(); os.makedirs(o.out, exist_ok=True)
    A = load_area(IEGame(o.a), o.area, {}, False); B = load_area(IEGame(o.b), o.area, {}, False)
    ia, ib = [np.asarray(x[3])[..., :3].astype(np.int16) for x in (A, B)]
    rep = {'size_a': ia.shape[:2], 'size_b': ib.shape[:2]}
    if ia.shape == ib.shape:
        d = np.abs(ia - ib).max(-1)
        rep.update(art_mean_abs=float(np.abs(ia - ib).mean()), art_px_gt16=float((d > 16).mean()),
                   art_px_gt48=float((d > 48).mean()), art_psnr=float(10 * np.log10(255 ** 2 / max(1e-9, ((ia - ib) ** 2).mean()))))
        Image.fromarray(np.clip(d * 4, 0, 255).astype(np.uint8)).save(f'{o.out}/{o.area}_artdiff.png')
        h = ia.shape[0]
        side = np.concatenate([ia, ib], 1).astype(np.uint8)
        Image.fromarray(side).resize((side.shape[1] // 2, h // 2)).save(f'{o.out}/{o.area}_side_by_side.png')
    sa, sb = A[4], B[4]
    if sa.shape == sb.shape:
        rep['sr_identical'] = float((sa == sb).mean())
        rep['walk_agree'] = float((walk_mask(sa) == walk_mask(sb)).mean())
    rep['doors'] = (len(A[1].doors), len(B[1].doors)); rep['doors_closed'] = (len(A[5]), len(B[5]))
    for k in ('actors', 'regions', 'containers', 'entrances', 'animations'):
        la, lb = getattr(A[1], k, None), getattr(B[1], k, None)
        if la is not None and lb is not None:
            rep[k] = (len(la), len(lb))
    rep['night'] = (bool(A[1].has_night), bool(B[1].has_night))
    json.dump(rep, open(f'{o.out}/{o.area}_compare.json', 'w'), indent=1); print(json.dumps(rep, indent=1))


if __name__ == '__main__':
    main()

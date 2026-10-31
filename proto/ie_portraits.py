"""Commissioned (AI-generated, owner's own) NPC portraits -> ToEE portrait TGAs + portraits.mes entries.

Ids are 9900+ in steps of 10 (Co8 uses 9000-9754). Per id: +0 _b 130x150, +1 _m 42x37, +2 _s 53x47, +3 _s_grey, +4 _m_grey,
the vanilla NPC layout (vanilla leaves +0 empty for NPCs; we put the big portrait there like the PC entries do).
Sources: art/portraits/<key>/ie_<key>_{big,m,s}.png (see /workspace/portrait-commission specs).
"""
import os, re, sys
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(os.path.dirname(HERE), 'art', 'portraits')
# key -> (portraits.mes base id, display name used in file names)
ART_IDS = {
    'hrothgar': (9900, 'Hrothgar'), 'everard': (9910, 'Everard'), 'arundel': (9920, 'Arundel'),
    'poquelin': (9930, 'Poquelin'), 'belhifet': (9940, 'Belhifet'), 'yxunomei': (9950, 'Yxunomei'),
    'kresselack': (9960, 'Kresselack'), 'conlan': (9970, 'Conlan'),
}
SIZES = {'b': (130, 150), 'm': (42, 37), 's': (53, 47)}


def grey(im):
    g = im.convert('L').point(lambda v: int(0.65 * v + 33))   # matches vanilla *_grey.tga levels
    out = Image.merge('RGBA', (g, g, g, im.getchannel('A')))
    return out


def files_for(key):
    base, name = ART_IDS[key]
    return {base: 'NPC_%d_b_%s.tga' % (base, name), base + 1: 'NPC_%d_m_%s.tga' % (base + 1, name),
            base + 2: 'NPC_%d_s_%s.tga' % (base + 2, name), base + 3: 'NPC_%d_s_%s_grey.tga' % (base + 3, name),
            base + 4: 'NPC_%d_m_%s_grey.tga' % (base + 4, name)}


def build(out_dir, vanilla_mes=None):
    """Write the TGAs and a portraits.mes (vanilla entries + ours) into out_dir (= data/art/interface/portraits)."""
    os.makedirs(out_dir, exist_ok=True)
    mes = dict(vanilla_mes or {})
    for key, (base, name) in ART_IDS.items():
        src = os.path.join(ART, key, 'ie_%s_%s.png')
        if not os.path.isfile(src % (key, 'big')):
            continue
        ims = {k: Image.open(src % (key, 'big' if k == 'b' else k)).convert('RGBA') for k in SIZES}
        for k, sz in SIZES.items():
            if ims[k].size != sz:
                ims[k] = ims[k].resize(sz, Image.LANCZOS)
        fn = files_for(key)
        imgs = {base: ims['b'], base + 1: ims['m'], base + 2: ims['s'], base + 3: grey(ims['s']), base + 4: grey(ims['m'])}
        for i, f in fn.items():
            if i in mes and mes[i] and mes[i] != f:
                raise SystemExit('portrait id clash %d: %s vs %s' % (i, mes[i], f))
            imgs[i].save(os.path.join(out_dir, f))
            mes[i] = f
    with open(os.path.join(out_dir, 'portraits.mes'), 'w', encoding='latin-1') as f:
        f.write(''.join('{%d} {%s}\n' % kv for kv in sorted(mes.items())))
    return mes


def vanilla(toee):
    import toeedata
    return toeedata.ToEEData(toee).mes('art/interface/portraits/portraits.mes')


if __name__ == '__main__':   # ie_portraits.py <out>/data/art/interface/portraits [toee root]
    build(sys.argv[1], vanilla(sys.argv[2]) if len(sys.argv) > 2 else None)

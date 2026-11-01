"""Commissioned (AI-generated, owner's own) NPC portraits -> ToEE portrait TGAs + portraits.mes entries.

Ids are 9900+ in steps of 10 (batches 2-3 run past 9999: 10000-10134) (Co8 uses 9000-9754). Per id: +0 _b 130x150, +1 _m 42x37, +2 _s 53x47, +3 _s_grey, +4 _m_grey,
the vanilla NPC layout (vanilla leaves +0 empty for NPCs; we put the big portrait there like the PC entries do).
Sources: art/portraits/<key>/ie_<key>_{big,m,s}.png (see /workspace/portrait-commission specs).
"""
import os, re, sys
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(os.path.dirname(HERE), 'art', 'portraits')
MASTERS = os.environ.get('IE_PORTRAIT_MASTERS', '/workspace/portrait-art/masters')   # ie_<key>/ie_<key>_master.png
# key -> (portraits.mes base id, display name used in file names)
ART_IDS = {
    'hrothgar': (9900, 'Hrothgar'), 'everard': (9910, 'Everard'), 'arundel': (9920, 'Arundel'),
    'poquelin': (9930, 'Poquelin'), 'belhifet': (9940, 'Belhifet'), 'yxunomei': (9950, 'Yxunomei'),
    'kresselack': (9960, 'Kresselack'), 'conlan': (9970, 'Conlan'),
    # batch 2: IWD2
    'ulbrec': (9980, 'Ulbrec'), 'shawford': (9990, 'Shawford'), 'hedron': (10000, 'Hedron'), 'oswald': (10010, 'Oswald'),
    'nathaniel': (10020, 'Nathaniel'), 'isair': (10030, 'Isair'), 'madae': (10040, 'Madae'), 'ennelia': (10050, 'Ennelia'),
    # batch 3: IWD2 secondary NPCs
    'elytharra': (10060, 'Elytharra'), 'deirdre': (10070, 'Deirdre'), 'koluhm': (10080, 'Koluhm'), 'phaen': (10090, 'Phaen'),
    'reig': (10100, 'Reig'), 'guthewulf': (10110, 'Guthewulf'), 'iselore': (10120, 'Iselore'), 'kickshaw': (10130, 'Kickshaw'),
}
# Face boxes on the 1200x1384 master, set by eye: (centre x, top of head/hair/crown, bottom of chin/beard).
# _m/_s are recropped from these (whole head + margin under the chin, like vanilla NPC_6001_m_Terjon);
# the commissioned _m/_s PNGs are cropped too tight. A key without a box keeps its source _m/_s.
FACE = {
    'hrothgar': (590, 120, 800), 'everard': (630, 120, 820), 'arundel': (530, 90, 770), 'poquelin': (620, 80, 790),
    'belhifet': (420, 170, 860), 'yxunomei': (580, 110, 840), 'kresselack': (620, 50, 880), 'conlan': (650, 170, 850),
    'ulbrec': (520, 150, 730), 'shawford': (560, 180, 830), 'hedron': (580, 130, 810), 'oswald': (620, 120, 800),
    'nathaniel': (500, 200, 880), 'isair': (560, 150, 850), 'madae': (600, 120, 870), 'ennelia': (600, 220, 880),
    'elytharra': (590, 90, 700), 'deirdre': (560, 90, 700), 'koluhm': (650, 150, 870), 'phaen': (600, 100, 810),
    'reig': (565, 120, 820), 'guthewulf': (670, 150, 800), 'iselore': (625, 120, 900), 'kickshaw': (550, 160, 830),
}
TOP_PAD, CHIN_PAD = 0.06, 0.14   # fraction of head height above the top / below the chin
SIZES = {'b': (130, 150), 'm': (42, 37), 's': (53, 47)}


def face_crop(master, box, size):
    """Crop master to size's aspect around box = (cx, top, chin), whole head in frame, then downscale."""
    cx, top, chin = box; h = chin - top
    y0 = top - TOP_PAD * h; ch = h * (1 + TOP_PAD + CHIN_PAD); cw = ch * size[0] / size[1]
    x0 = min(max(cx - cw / 2, 0), master.width - cw); y0 = min(max(y0, 0), master.height - ch)
    return master.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize(size, Image.LANCZOS)


def recrop(key):
    """Rewrite art/portraits/<key>/ie_<key>_{m,s}.png from the master (masters live outside the repo: MASTERS dir)."""
    src = os.path.join(MASTERS, 'ie_%s' % key, 'ie_%s_master.png' % key)
    m = Image.open(src).convert('RGB')
    for k in ('m', 's'):
        face_crop(m, FACE[key], SIZES[k]).save(os.path.join(ART, key, 'ie_%s_%s.png' % (key, k)))


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


if __name__ == '__main__':   # ie_portraits.py <out>/data/art/interface/portraits [toee root] | ie_portraits.py recrop [key...]
    if sys.argv[1] == 'recrop':
        for k in sys.argv[2:] or sorted(FACE):
            recrop(k)
        sys.exit()
    build(sys.argv[1], vanilla(sys.argv[2]) if len(sys.argv) > 2 else None)

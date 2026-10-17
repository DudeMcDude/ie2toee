"""Classic Infinity Engine BAM bitmap font -> TrueType (pixel outlines), so Temple+'s text engine can use the
player's own classic font. Written from the IESDP BAM description: cycle N holds the glyph of character N+1
(code page 1252), frame centre y = pixels above the baseline, advance = frame width.

Each lit pixel becomes a square (horizontal runs merged); grey anti-aliasing levels (lighter = less ink) are thresholded."""
import numpy as np
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

UPM = 1024


def bam_to_ttf(bam, family, out_path, threshold=128):
    glyphs = {}
    for c, cyc in enumerate(bam.cycles):
        code = c + 1
        if not cyc or code < 32 or code > 255:
            continue
        i = cyc[0]
        f = bam.frames[i]
        lum = (255 - f[..., :3].min(axis=2).astype(int)) * (f[..., 3] > 0)   # dark = ink (palette is recoloured)
        glyphs[code] = (lum >= threshold, bam.centres[i][1], f.shape[1])
    if not glyphs:
        raise ValueError('no glyphs')
    asc_px = max(cy for _, cy, _ in glyphs.values())
    desc_px = max(max(m.shape[0] - cy, 0) for m, cy, _ in glyphs.values())
    px = UPM // (asc_px + desc_px)                  # one bitmap pixel in font units; em = line height
    names, cmap, adv, outl = ['.notdef'], {}, {'.notdef': (px * 4, 0)}, {}
    outl['.notdef'] = TTGlyphPen(None).glyph()
    for code, (m, cy, w) in sorted(glyphs.items()):
        ch = bytes([code]).decode('cp1252', 'replace')
        if ch == '\ufffd':
            continue
        n = 'g%d' % code
        pen = TTGlyphPen(None)
        for y in range(m.shape[0]):
            row, x = m[y], 0
            while x < len(row):
                if row[x]:
                    x0 = x
                    while x < len(row) and row[x]:
                        x += 1
                    top, bot = (cy - y) * px, (cy - y - 1) * px
                    pen.moveTo((x0 * px, bot)); pen.lineTo((x0 * px, top))
                    pen.lineTo((x * px, top)); pen.lineTo((x * px, bot)); pen.closePath()
                else:
                    x += 1
        names.append(n); cmap[ord(ch)] = n; outl[n] = pen.glyph(); adv[n] = (w * px, 0)
    if 32 not in cmap:
        names.append('space'); cmap[32] = 'space'; outl['space'] = TTGlyphPen(None).glyph(); adv['space'] = (px * 3, 0)
    fb = FontBuilder(UPM, isTTF=True)
    fb.setupGlyphOrder(names); fb.setupCharacterMap(cmap); fb.setupGlyf(outl)
    fb.setupHorizontalMetrics(adv)
    fb.setupHorizontalHeader(ascent=asc_px * px, descent=-desc_px * px)
    fb.setupNameTable({'familyName': family, 'styleName': 'Regular'})
    fb.setupOS2(sTypoAscender=asc_px * px, sTypoDescender=-desc_px * px, usWinAscent=asc_px * px,
                usWinDescent=desc_px * px)
    fb.setupPost()
    fb.save(out_path)
    return {'line_px': asc_px + desc_px, 'ascent_px': asc_px}

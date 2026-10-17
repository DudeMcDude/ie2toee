"""Infinity Engine GUI resources: CHU V1 (window/control layout), MOS V1/MOSC/MOS V2 (panel backgrounds),
BAM V1/BAMC/BAM V2 (button and font frames). Written from the IESDP format descriptions only.

Used by the dialogue-skin exporter (ie_dialog_skin.py) to turn the player's own GUI art into PNG/TGA files and a
layout JSON for Temple+'s IE-style dialogue window. Nothing produced here is meant to be redistributed.
"""
import struct, zlib
import numpy as np
from ieformats import cstr, decode_pvrz

CTRL_TYPES = {0: 'button', 1: 'progress', 2: 'slider', 3: 'textedit', 5: 'textarea', 6: 'label', 7: 'scrollbar'}


def _rgba(b, o):
    r, g, bl, a = struct.unpack_from('<BBBB', b, o)
    return [r, g, bl, a]


# ----------------------------------------------------------------------------- CHU
class Chu:
    """CHU V1: header, window table (0x1C bytes each), control table (offset,len pairs), control records."""

    def __init__(self, data):
        assert data[:8] == b'CHUIV1  ', 'not a CHU V1'
        nwin, ctoff, woff = struct.unpack_from('<III', data, 8)
        self.windows = []
        for i in range(nwin):
            o = woff + i * 0x1C
            wid, _u, x, y, w, h, flags, nctl = struct.unpack_from('<8H', data, o)
            mos = cstr(data[o + 0x10:o + 0x18])
            first = struct.unpack_from('<H', data, o + 0x18)[0]
            win = dict(id=wid, x=x, y=y, w=w, h=h, flags=flags, mos=mos if flags & 1 else '', controls=[])
            for c in range(first, first + nctl):
                coff, clen = struct.unpack_from('<II', data, ctoff + c * 8)
                win['controls'].append(self._control(data[coff:coff + clen]))
            self.windows.append(win)

    @staticmethod
    def _control(b):
        cid, x, y, w, h = struct.unpack_from('<IHHHH', b, 0)
        t = b[0x0C]
        c = dict(id=cid, x=x, y=y, w=w, h=h, type=CTRL_TYPES.get(t, t))
        if t == 0 and len(b) >= 0x20:
            c.update(bam=cstr(b[0x0E:0x16]), cycle=b[0x16], textflags=b[0x17],
                     frames=dict(up=b[0x18], down=b[0x1A], selected=b[0x1C], disabled=b[0x1E]))
        elif t == 5 and len(b) >= 0x2E:
            c.update(font_initials=cstr(b[0x0E:0x16]), font=cstr(b[0x16:0x1E]),
                     color_initials=_rgba(b, 0x1E), color_text=_rgba(b, 0x22), color_bg=_rgba(b, 0x26),
                     scrollbar=struct.unpack_from('<I', b, 0x2A)[0])
        elif t == 6 and len(b) >= 0x24:
            c.update(strref=struct.unpack_from('<i', b, 0x0E)[0], font=cstr(b[0x12:0x1A]),
                     color1=_rgba(b, 0x1A), color2=_rgba(b, 0x1E), justify=struct.unpack_from('<H', b, 0x22)[0])
        elif t == 7 and len(b) >= 0x28:
            cyc, uu, ud, du, dd, trough, slider = struct.unpack_from('<7H', b, 0x16)
            c.update(bam=cstr(b[0x0E:0x16]), cycle=cyc, frames=dict(up=uu, up_pressed=ud, down=du,
                     down_pressed=dd, trough=trough, slider=slider), textarea=struct.unpack_from('<I', b, 0x24)[0])
        return c


# ----------------------------------------------------------------------------- MOS
def decode_mos(data, pvrz_loader=None):
    """Return an RGBA uint8 array. MOS V1 = per-block palettes + 8-bit pixels (palette index 0 / pure green
    transparent); MOSC = zlib(MOS V1); MOS V2 (EE) = rectangles copied out of PVRZ pages."""
    if data[:8] == b'MOSCV1  ':
        data = zlib.decompress(data[12:])
    if data[:8] == b'MOS V1  ':
        w, h, cols, rows, bs, poff = struct.unpack_from('<HHHHII', data, 8)
        nb = cols * rows
        toff = poff + nb * 1024
        doff = toff + nb * 4
        out = np.zeros((h, w, 4), np.uint8)
        for r in range(rows):
            for c in range(cols):
                i = r * cols + c
                bw, bh = min(bs, w - c * bs), min(bs, h - r * bs)
                pal = np.frombuffer(data, np.uint8, 1024, poff + i * 1024).reshape(256, 4)
                rgba = np.empty((256, 4), np.uint8)
                rgba[:, 0], rgba[:, 1], rgba[:, 2], rgba[:, 3] = pal[:, 2], pal[:, 1], pal[:, 0], 255
                green = (pal[:, 1] == 255) & (pal[:, 0] == 0) & (pal[:, 2] == 0)
                rgba[green, 3] = 0
                o = doff + struct.unpack_from('<I', data, toff + i * 4)[0]
                px = np.frombuffer(data, np.uint8, bw * bh, o).reshape(bh, bw)
                out[r * bs:r * bs + bh, c * bs:c * bs + bw] = rgba[px]
        return out
    if data[:8] == b'MOS V2  ':
        w, h, nblk, boff = struct.unpack_from('<IIII', data, 8)
        out = np.zeros((h, w, 4), np.uint8)
        for i in range(nblk):
            page, sx, sy, bw, bh, dx, dy = struct.unpack_from('<7I', data, boff + i * 28)
            pg = pvrz_loader('mos%04d' % page)
            out[dy:dy + bh, dx:dx + bw] = pg[sy:sy + bh, sx:sx + bw]
        return out
    raise ValueError('not a MOS: %r' % data[:8])


# ----------------------------------------------------------------------------- BAM
class Bam:
    """frames[i] -> RGBA array, centre (cx, cy); cycles[c] -> list of frame indices."""

    def __init__(self, data, pvrz_loader=None):
        if data[:8] == b'BAMCV1  ':
            data = zlib.decompress(data[12:])
        self.frames, self.centres, self.cycles = [], [], []
        if data[:8] == b'BAM V1  ':
            nfr, ncyc, rle_idx, froff, poff, lutoff = struct.unpack_from('<HBBIII', data, 8)
            pal = np.frombuffer(data, np.uint8, 1024, poff).reshape(256, 4)
            rgba = np.empty((256, 4), np.uint8)
            rgba[:, 0], rgba[:, 1], rgba[:, 2] = pal[:, 2], pal[:, 1], pal[:, 0]
            a = pal[:, 3].copy(); a[a == 0] = 255          # EE adds palette alpha; classic leaves it 0 (=opaque)
            rgba[:, 3] = a
            # transparent colour: the first green (0,255,0) entry if any, else index 0 (IESDP)
            green = np.nonzero((pal[:, 1] == 255) & (pal[:, 0] == 0) & (pal[:, 2] == 0))[0]
            rgba[green[0] if len(green) else 0, 3] = 0
            for i in range(nfr):
                w, h, cx, cy, d = struct.unpack_from('<HHhhI', data, froff + i * 12)
                off, raw = d & 0x7FFFFFFF, bool(d & 0x80000000)
                n = w * h
                if raw:
                    px = np.frombuffer(data, np.uint8, n, off)
                else:
                    px, o = bytearray(), off
                    while len(px) < n:
                        v = data[o]; o += 1
                        if v == rle_idx:
                            px += bytes([v]) * (data[o] + 1); o += 1
                        else:
                            px.append(v)
                    px = np.frombuffer(bytes(px[:n]), np.uint8)
                self.frames.append(rgba[px.reshape(h, w)] if n else np.zeros((max(h, 1), max(w, 1), 4), np.uint8))
                self.centres.append((cx, cy))
            coff = froff + nfr * 12
            for c in range(ncyc):
                cnt, first = struct.unpack_from('<HH', data, coff + c * 4)
                self.cycles.append([struct.unpack_from('<H', data, lutoff + (first + k) * 2)[0] for k in range(cnt)])
        elif data[:8] == b'BAM V2  ':
            nfr, ncyc, nblk, froff, cyoff, boff = struct.unpack_from('<6I', data, 8)
            for i in range(nfr):
                w, h, cx, cy, b0, bn = struct.unpack_from('<HHhhHH', data, froff + i * 12)
                out = np.zeros((max(h, 1), max(w, 1), 4), np.uint8)
                for k in range(b0, b0 + bn):
                    page, sx, sy, bw, bh, dx, dy = struct.unpack_from('<7I', data, boff + k * 28)
                    pg = pvrz_loader('mos%04d' % page)
                    out[dy:dy + bh, dx:dx + bw] = pg[sy:sy + bh, sx:sx + bw]
                self.frames.append(out); self.centres.append((cx, cy))
            for c in range(ncyc):
                cnt, first = struct.unpack_from('<HH', data, cyoff + c * 4)
                self.cycles.append(list(range(first, first + cnt)))
        else:
            raise ValueError('not a BAM: %r' % data[:8])

    def frame(self, cycle, idx):
        cyc = self.cycles[cycle] if cycle < len(self.cycles) else []
        return self.frames[cyc[idx]] if idx < len(cyc) else None


def pvrz_loader_for(game):
    cache = {}

    def load(ref):
        if ref not in cache:
            cache[ref] = decode_pvrz(game.read(ref, 'pvrz'))
        return cache[ref]
    return load

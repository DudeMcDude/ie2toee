"""Parsers for the IE area formats needed to rebuild a map: TIS (palette + PVRZ), WED V1.3,
ARE V1.0 (BG/IWD) and V9.1 (IWD2), and the SR/HT/LM bitmaps. Layouts per IESDP."""
import io, struct, zlib
import numpy as np
from PIL import Image

TILE = 64


def cstr(b):
    return b.split(b'\0')[0].decode('latin-1')


# ----------------------------------------------------------------------------- TIS
class Tis:
    def __init__(self, data, pvrz_loader=None):
        assert data[:4] == b'TIS ', 'not a TIS'
        self.count, self.tsize, self.hsize, self.dim = struct.unpack_from('<IIII', data, 8)
        self.data, self.pvrz_loader = data, pvrz_loader
        self.pvrz = self.tsize == 12
        self._pages = {}

    def tile(self, i):
        """Return tile i as a 64x64 RGBA uint8 array. Palette index 0 (and pure green in
        palette TIS) is transparent, which matters for overlay masks."""
        o = self.hsize + i * self.tsize
        if not self.pvrz:
            pal = np.frombuffer(self.data, np.uint8, 1024, o).reshape(256, 4)
            rgba = np.empty((256, 4), np.uint8)
            rgba[:, 0], rgba[:, 1], rgba[:, 2] = pal[:, 2], pal[:, 1], pal[:, 0]
            rgba[:, 3] = 255
            rgba[0, 3] = 0
            green = (pal[:, 1] == 255) & (pal[:, 0] == 0) & (pal[:, 2] == 0)
            rgba[green, 3] = 0
            px = np.frombuffer(self.data, np.uint8, 4096, o + 1024).reshape(64, 64)
            return rgba[px]
        page, x, y = struct.unpack_from('<iII', self.data, o)
        if page == -1:
            out = np.zeros((64, 64, 4), np.uint8); out[..., 3] = 255
            return out
        if page not in self._pages:
            self._pages[page] = self.pvrz_loader(page)
        return self._pages[page][y:y + 64, x:x + 64]


def decode_pvrz(data):
    """PVRZ = uint32 uncompressed size + zlib(PVR v3). EE tilesets use DXT1 (fmt 7) or DXT5 (fmt 11).
    Verified on IWD:EE 2.7 (area tilesets are DXT1; GUI/MOS pages also use DXT5); BCn decode via Pillow."""
    pvr = zlib.decompress(data[4:])
    assert pvr[:4] == b'PVR\x03', 'not PVR v3'
    fmt = struct.unpack_from('<Q', pvr, 8)[0]
    h, w = struct.unpack_from('<II', pvr, 24)
    meta = struct.unpack_from('<I', pvr, 48)[0]
    px = pvr[52 + meta:]
    n = {7: 1, 11: 3}.get(fmt)
    if n is None:
        raise NotImplementedError(f'PVR pixel format {fmt}')
    img = Image.frombuffer('RGBA', (w, h), px, 'bcn', n)
    return np.asarray(img.convert('RGBA'))


# ----------------------------------------------------------------------------- WED
class Wed:
    def __init__(self, data):
        assert data[:8] == b'WED V1.3', 'not WED V1.3'
        nover, ndoor, ooff, shoff, doff, dtoff = struct.unpack_from('<6I', data, 8)
        self.overlays = []
        for i in range(nover):
            w, h, tis, uniq, mov, tmoff, tioff = struct.unpack_from('<HH8sHHII', data, ooff + i * 0x18)
            ncell = w * h
            cells = []
            for c in range(ncell):
                start, cnt, alt, flags = struct.unpack_from('<HHHB', data, tmoff + c * 10)
                cells.append((start, cnt, alt, flags))
            # tile index lookup table length: max(start+count) over cells
            nlook = max((s + n for s, n, _, _ in cells), default=0)
            lookup = list(struct.unpack_from(f'<{nlook}H', data, tioff)) if nlook else []
            self.overlays.append(dict(w=w, h=h, tis=cstr(tis), movement=mov, cells=cells, lookup=lookup))
        npoly, poff, voff, wgoff, pioff = struct.unpack_from('<5I', data, shoff)
        self._data, self._voff = data, voff
        self.walls = [self._poly(poff + i * 18) for i in range(npoly)]
        self.doors = []
        for i in range(ndoor):
            name, closed, first, cnt, nopen, nclosed, oopen, oclosed = struct.unpack_from('<8sHHHHHII', data, doff + i * 0x1a)
            cellidx = list(struct.unpack_from(f'<{cnt}H', data, dtoff + first * 2)) if cnt else []
            self.doors.append(dict(
                name=cstr(name), closed=bool(closed), cells=cellidx,
                open_polys=[self._poly(oopen + k * 18) for k in range(nopen)],
                closed_polys=[self._poly(oclosed + k * 18) for k in range(nclosed)]))

    def _poly(self, off):
        first, cnt, flags, height, x0, x1, y0, y1 = struct.unpack_from('<IIBbHHHH', self._data, off)
        pts = [struct.unpack_from('<hh', self._data, self._voff + (first + k) * 4) for k in range(cnt)]
        # gemRB WEDImporter semantics: flag bit1 ("hovering") => first two points are an explicit
        # baseline, excluded from the outline; flag bit0 => baseline is the first edge.
        base = None
        if flags & 2 and len(pts) >= 2:
            base, pts = (pts[0], pts[1]), pts[2:]
        elif flags & 1 and len(pts) >= 2:
            base = (pts[0], pts[1])
        return dict(flags=flags, height=height, bbox=(x0, y0, x1, y1), points=pts, baseline=base)

    @property
    def size_px(self):
        b = self.overlays[0]
        return b['w'] * TILE, b['h'] * TILE


def render_background(wed, tis, overlay_tis=None, closed_doors=(), anim_frame=0):
    """Compose the base layer into one RGBA image (like the IE renderer, minus animation).
    closed_doors: WED door names to draw closed (all others are drawn open)."""
    base = wed.overlays[0]
    W, H = base['w'], base['h']
    img = np.zeros((H * TILE, W * TILE, 4), np.uint8)
    # Door cells: primary tiles = open, alternate ("secondary") tiles = closed. (Checked on IWD AR5404/AR1000:
    # the WED door 'closed' word is 1 for every door and does not say which state the primary tiles show.)
    want_closed = {n.lower() for n in closed_doors}
    door_cells = set()
    for d in wed.doors:
        if d['name'].lower() in want_closed:
            door_cells.update(d['cells'])
    for c, (start, cnt, alt, flags) in enumerate(base['cells']):
        y, x = divmod(c, W)
        dst = img[y * TILE:(y + 1) * TILE, x * TILE:(x + 1) * TILE]
        prim = base['lookup'][start + (anim_frame % cnt if cnt else 0)] if cnt else None
        use_alt = alt != 0xFFFF and (c in door_cells)
        ov = flags >> 1  # bits1..7 -> overlay 1..7
        if ov and overlay_tis is not None and alt != 0xFFFF:
            # overlay cell (e.g. water): draw the overlay tile, then the masked alt tile over it
            for k in range(1, 8):
                if ov & (1 << (k - 1)) and k < len(wed.overlays) and k in overlay_tis:
                    o = wed.overlays[k]
                    oc = o['cells'][(y % o['h']) * o['w'] + (x % o['w'])]
                    dst[:] = overlay_tis[k].tile(o['lookup'][oc[0]])
            t = tis.tile(alt)
            m = t[..., 3:4] > 0
            dst[:] = np.where(m, t, dst)
            continue
        t = tis.tile(alt if use_alt else prim)
        dst[:] = t
        dst[..., 3] = 255
    return img


def door_cell_tiles(wed, tis, door, closed):
    """[(cell_index, x_px, y_px, RGBA 64x64)] for one WED door drawn open or closed."""
    base = wed.overlays[0]
    out = []
    for c in door['cells']:
        start, cnt, alt, flags = base['cells'][c]
        prim = base['lookup'][start] if cnt else None
        use_alt = alt != 0xFFFF and closed
        t = tis.tile(alt if use_alt else prim).copy()
        t[..., 3] = 255
        y, x = divmod(c, base['w'])
        out.append((c, x * TILE, y * TILE, t))
    return out


# ----------------------------------------------------------------------------- ARE
class Are:
    """Subset of ARE needed for maps: header, actors, regions, entrances, containers, doors,
    animations, vertices. V9.1 (IWD2) has 16 extra header bytes at 0x54, so every header
    offset after that is +0x10; the record layouts used here are identical."""

    def __init__(self, data):
        sig = data[:8]
        if sig == b'AREAV1.0':
            s = 0
        elif sig == b'AREAV9.1':
            s = 0x10
        else:
            raise ValueError(f'unsupported ARE {sig!r} (PST V1.0 uses the same header but other records)')
        self.version = sig[4:].decode()
        self.wed = cstr(data[8:16])
        self.flags = struct.unpack_from('<I', data, 0x14)[0]
        self.area_type = struct.unpack_from('<H', data, 0x48)[0]  # bit0 outdoor, bit1 day/night ...
        u = lambda fmt, off: struct.unpack_from(fmt, data, off + s)[0]
        act_off, act_n = u('<I', 0x54), u('<H', 0x58)
        reg_n, reg_off = u('<H', 0x5a), u('<I', 0x5c)
        ent_off, ent_n = u('<I', 0x68), u('<I', 0x6c)
        con_off, con_n = u('<I', 0x70), u('<H', 0x74)
        vtx_off, vtx_n = u('<I', 0x7c), u('<H', 0x80)
        self.script = cstr(data[0x94 + s:0x9c + s])
        door_n, door_off = u('<I', 0xa4), u('<I', 0xa8)
        anim_n, anim_off = u('<I', 0xac), u('<I', 0xb0)
        self.vertices = [struct.unpack_from('<hh', data, vtx_off + i * 4) for i in range(vtx_n)]
        V = self.vertices
        self.actors = []
        for o in (act_off + i * 0x110 for i in range(act_n)):
            emb_off, emb_size = struct.unpack_from('<II', data, o + 0x88)
            self.actors.append(dict(
                name=cstr(data[o:o + 32]), x=struct.unpack_from('<H', data, o + 0x20)[0],
                y=struct.unpack_from('<H', data, o + 0x22)[0],
                dest=struct.unpack_from('<HH', data, o + 0x24),
                flags=struct.unpack_from('<I', data, o + 0x28)[0],      # bit0: CRE not attached (resref used)
                animation=struct.unpack_from('<I', data, o + 0x30)[0],
                orient=struct.unpack_from('<H', data, o + 0x34)[0],
                schedule=struct.unpack_from('<I', data, o + 0x40)[0] & 0xFFFFFF,
                dialog=cstr(data[o + 0x48:o + 0x50]),
                scripts=dict(zip(('override', 'general', 'class', 'race', 'default', 'specific'),
                                 (cstr(data[k:k + 8]) for k in range(o + 0x50, o + 0x80, 8)))),
                cre=cstr(data[o + 0x80:o + 0x88]),
                embedded_cre=data[emb_off:emb_off + emb_size] if emb_off and emb_size else None))
        # spawn points (0xC8 each) and the single rest-interruption record (0xE4): creature resrefs or
        # SPAWNGRP.2DA group names
        sp_off, sp_n = u('<I', 0x60), u('<I', 0x64)
        self.spawn_points = []
        for o in (sp_off + i * 0xC8 for i in range(sp_n if sp_off else 0)):
            n = struct.unpack_from('<H', data, o + 0x74)[0]
            self.spawn_points.append(dict(
                name=cstr(data[o:o + 32]), x=struct.unpack_from('<H', data, o + 0x20)[0],
                y=struct.unpack_from('<H', data, o + 0x22)[0],
                creatures=[cstr(data[o + 0x24 + k * 8:o + 0x2c + k * 8]) for k in range(min(n, 10))],
                base_count=struct.unpack_from('<H', data, o + 0x76)[0],
                method=struct.unpack_from('<H', data, o + 0x7a)[0],
                schedule=struct.unpack_from('<I', data, o + 0x88)[0] & 0xFFFFFF))
        ri_off = u('<I', 0xc0)
        self.rest_spawns = []
        if ri_off and ri_off + 0xE4 <= len(data):
            n = struct.unpack_from('<H', data, ri_off + 0x98)[0]
            self.rest_spawns = [c for c in (cstr(data[ri_off + 0x48 + k * 8:ri_off + 0x50 + k * 8])
                                            for k in range(min(n, 10))) if c]
        self.regions = []
        for i in range(reg_n):
            o = reg_off + i * 0xC4
            typ = struct.unpack_from('<H', data, o + 0x20)[0]
            nv, fv = struct.unpack_from('<HI', data, o + 0x2a)
            self.regions.append(dict(name=cstr(data[o:o + 32]), type=('trap', 'info', 'travel')[typ] if typ < 3 else typ,
                                     poly=V[fv:fv + nv], dest_area=cstr(data[o + 0x38:o + 0x40]),
                                     dest_entrance=cstr(data[o + 0x40:o + 0x60]),
                                     script=cstr(data[o + 0x7c:o + 0x84])))
        self.entrances = [dict(name=cstr(data[o:o + 32]), x=struct.unpack_from('<H', data, o + 0x20)[0],
                               y=struct.unpack_from('<H', data, o + 0x22)[0],
                               orient=struct.unpack_from('<H', data, o + 0x24)[0])
                          for o in (ent_off + i * 0x68 for i in range(ent_n))]
        self.containers = []
        for i in range(con_n):
            o = con_off + i * 0xC0
            fv, nv = struct.unpack_from('<IH', data, o + 0x50)
            self.containers.append(dict(name=cstr(data[o:o + 32]), x=struct.unpack_from('<H', data, o + 0x20)[0],
                                        y=struct.unpack_from('<H', data, o + 0x22)[0],
                                        type=struct.unpack_from('<H', data, o + 0x24)[0], poly=V[fv:fv + nv]))
        self.doors = []
        for i in range(door_n):
            o = door_off + i * 0xC8
            f_open, n_open, n_closed, f_closed = struct.unpack_from('<IHHI', data, o + 0x2c)
            obb = struct.unpack_from('<4H', data, o + 0x38); cbb = struct.unpack_from('<4H', data, o + 0x40)
            f_io, n_io, n_ic, f_ic = struct.unpack_from('<IHHI', data, o + 0x48)
            p1 = struct.unpack_from('<2H', data, o + 0x90); p2 = struct.unpack_from('<2H', data, o + 0x94)
            self.doors.append(dict(
                name=cstr(data[o:o + 32]), wed_id=cstr(data[o + 0x20:o + 0x28]),
                flags=struct.unpack_from('<I', data, o + 0x28)[0],          # bit0 open, bit1 locked, bit7 secret ...
                open_poly=V[f_open:f_open + n_open], closed_poly=V[f_closed:f_closed + n_closed],
                open_bbox=obb, closed_bbox=cbb,
                # impeded cells: search-map cell coordinates (16x12 px) blocked in that state
                open_cells=V[f_io:f_io + n_io], closed_cells=V[f_ic:f_ic + n_ic],
                key=cstr(data[o + 0x78:o + 0x80]), script=cstr(data[o + 0x80:o + 0x88]),
                lock_difficulty=struct.unpack_from('<I', data, o + 0x8c)[0],
                toggle_points=[p1, p2],
                open_sound=cstr(data[o + 0x58:o + 0x60]), close_sound=cstr(data[o + 0x60:o + 0x68])))
        self.animations = [dict(name=cstr(data[o:o + 32]), x=struct.unpack_from('<H', data, o + 0x20)[0],
                                y=struct.unpack_from('<H', data, o + 0x22)[0], bam=cstr(data[o + 0x28:o + 0x30]),
                                flags=struct.unpack_from('<I', data, o + 0x34)[0])
                           for o in (anim_off + i * 0x4C for i in range(anim_n))]

    @property
    def has_night(self):
        return bool(self.area_type & 2)


# ----------------------------------------------------------------------------- bitmaps
def load_index_bmp(data):
    """SR/HT/LM bitmaps: return the raw palette *indices* (search map value 0..15)."""
    im = Image.open(io.BytesIO(data))
    if im.mode != 'P':
        im = im.convert('P')
    return np.asarray(im)

"""Infinity Engine resource resolution: override/ -> chitin.key + BIF/BIFC.

Reads the player's own game install in place; never copies assets anywhere
except into the converter's output (which stays on the player's machine).
Formats per IESDP: KEY V1, BIFF V1, BIF V1.0 (zlib monoblock), BIFC V1.0 (block-compressed).
"""
import os, struct, zlib

RESTYPE = {
    0x001: 'bmp', 0x002: 'mve', 0x004: 'wav', 0x005: 'wfx', 0x006: 'plt',
    0x3e8: 'bam', 0x3e9: 'wed', 0x3ea: 'chu', 0x3eb: 'tis', 0x3ec: 'mos',
    0x3ed: 'itm', 0x3ee: 'spl', 0x3ef: 'bcs', 0x3f0: 'ids', 0x3f1: 'cre',
    0x3f2: 'are', 0x3f3: 'dlg', 0x3f4: '2da', 0x3f5: 'gam', 0x3f6: 'sto',
    0x3f7: 'wmp', 0x3f8: 'eff', 0x3f9: 'bs', 0x3fa: 'chr', 0x3fb: 'vvc',
    0x3fc: 'vef', 0x3fd: 'pro', 0x3fe: 'bio', 0x3ff: 'wbm', 0x400: 'fnt',
    0x402: 'gui', 0x403: 'sql', 0x404: 'pvrz', 0x405: 'glsl', 0x408: 'menu',
    0x409: 'lua', 0x40a: 'ttf', 0x40b: 'png', 0x44c: 'bah', 0x802: 'ini',
    0x803: 'src',
}
EXT2TYPE = {v: k for k, v in RESTYPE.items()}


def _ci_find(root, rel):
    """Case-insensitive path lookup (IE installs mix cases; Linux/Wine is case-sensitive)."""
    rel = rel.replace('\\', '/').strip('/')
    cur = root
    for part in rel.split('/'):
        if not part:
            continue
        try:
            names = os.listdir(cur)
        except OSError:
            return None
        hit = next((n for n in names if n.lower() == part.lower()), None)
        if hit is None:
            return None
        cur = os.path.join(cur, hit)
    return cur


class Bif:
    def __init__(self, path):
        raw = open(path, 'rb').read()
        sig = raw[:8]
        if sig == b'BIFFV1  ':
            self.data = raw
        elif sig == b'BIF V1.0':  # zlib monoblock
            nlen = struct.unpack_from('<I', raw, 8)[0]
            o = 12 + nlen
            ulen, clen = struct.unpack_from('<II', raw, o)
            self.data = zlib.decompress(raw[o + 8:o + 8 + clen])
        elif sig == b'BIFCV1.0':  # block-compressed
            ulen = struct.unpack_from('<I', raw, 8)[0]
            o, out = 12, bytearray()
            while o < len(raw):
                dlen, clen = struct.unpack_from('<II', raw, o); o += 8
                out += zlib.decompress(raw[o:o + clen]); o += clen
            self.data = bytes(out)
        else:
            raise ValueError(f'{path}: unknown BIF signature {sig!r}')
        nfile, ntile, off = struct.unpack_from('<III', self.data, 8)
        self.files, self.tilesets = {}, {}
        for i in range(nfile):
            loc, doff, size, typ, _ = struct.unpack_from('<IIIHH', self.data, off + i * 16)
            self.files[loc & 0x3FFF] = (doff, size, typ)
        toff = off + nfile * 16
        for i in range(ntile):
            loc, doff, cnt, tsize, typ, _ = struct.unpack_from('<IIIIHH', self.data, toff + i * 20)
            self.tilesets[(loc >> 14) & 0x3F] = (doff, cnt, tsize)

    def get(self, locator, restype):
        if restype == EXT2TYPE['tis']:
            doff, cnt, tsize = self.tilesets[(locator >> 14) & 0x3F]
            # BIF-stored TIS has no header; synthesize one so callers see a normal TIS file
            hdr = b'TIS V1  ' + struct.pack('<IIII', cnt, tsize, 24, 64)
            return hdr + self.data[doff:doff + cnt * tsize]
        doff, size, _ = self.files[locator & 0x3FFF]
        return self.data[doff:doff + size]


class IEGame:
    """Resolve resources like the engine: override/ first, then chitin.key -> BIF.
    Works for classic installs (Data/, CDn/, .cbf) and EE installs (data/*.bif, lowercase paths, no override/)."""

    def __init__(self, root):
        self.root = root
        self.keys = {}  # (resref.lower(), ext) -> (bifname, locator)
        self.bifs = []
        self._bifcache = {}
        key = _ci_find(root, 'chitin.key')
        if key:
            self._read_key(key)
        self.override = _ci_find(root, 'override')

    def _read_key(self, path):
        b = open(path, 'rb').read()
        assert b[:8] == b'KEY V1  ', 'not a KEY V1 file'
        nbif, nres, boff, roff = struct.unpack_from('<IIII', b, 8)
        for i in range(nbif):
            ln, noff, nlen, flags = struct.unpack_from('<IIHH', b, boff + i * 12)
            name = b[noff:noff + nlen].split(b'\0')[0].decode('latin-1')
            self.bifs.append((name, flags))  # flags = location bits (HD/CD1..), see IESDP
        for i in range(nres):
            name, typ, loc = struct.unpack_from('<8sHI', b, roff + i * 14)
            ref = name.split(b'\0')[0].decode('latin-1').lower()
            self.keys[(ref, RESTYPE.get(typ, hex(typ)))] = (loc >> 20, loc)

    def _bif(self, idx):
        if idx not in self._bifcache:
            name, flags = self.bifs[idx]
            path = self.bif_path(idx)
            if path is None:
                raise FileNotFoundError(f'BIF {name} not found under {self.root}')
            self._bifcache[idx] = Bif(path)
        return self._bifcache[idx]

    def bif_path(self, idx):
        """Find a KEY-listed BIF on disk. Original (non-EE) installs keep CD-only BIFs in CDn/Data/ and,
        for IWD/IWD:HoW/IWD2, as compressed .cbf. Location flags (IESDP): bit0 = HD data dir, bit(n+1) = CDn."""
        name, flags = self.bifs[idx]
        norm = name.replace('\\', '/').lstrip('/')
        base = norm.rsplit('.', 1)[0]
        cds = [n for n in range(1, 7) if flags & (1 << (n + 1))] + [n for n in range(1, 7)]
        prefixes = [''] + [f'cd{n}/' for n in dict.fromkeys(cds)]
        for pre in prefixes:
            for cand in (norm, base + '.cbf', base + '.bif'):
                p = _ci_find(self.root, pre + cand)
                if p:
                    return p
        return None

    def exists(self, resref, ext):
        return self.find(resref, ext) is not None

    def find(self, resref, ext):
        resref, ext = resref.lower(), ext.lower()
        if self.override:
            p = _ci_find(self.override, f'{resref}.{ext}')
            if p:
                return ('override', p)
        if (resref, ext) in self.keys:
            return ('bif',) + self.keys[(resref, ext)]
        return None

    def read(self, resref, ext):
        hit = self.find(resref, ext)
        if hit is None:
            raise FileNotFoundError(f'{resref}.{ext}')
        if hit[0] == 'override':
            return open(hit[1], 'rb').read()
        _, bifidx, loc = hit
        return self._bif(bifidx).get(loc, EXT2TYPE[ext])

    def list(self, ext):
        ext = ext.lower()
        out = {r for (r, e) in self.keys if e == ext}
        if self.override:
            out |= {n.rsplit('.', 1)[0].lower() for n in os.listdir(self.override) if n.lower().endswith('.' + ext)}
        return sorted(out)

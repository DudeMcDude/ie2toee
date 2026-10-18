"""Read the few ToEE/Temple+ data files the creature converter needs (protos.tab, meshes.mes, description.mes,
spell_enum.mes) straight from the player's own ToEE install: loose files under data/ or modules/<mod>/ first, then the
TIG .dat archives (zlib-compressed entries, directory table at the end of the archive).
"""
import os, re, struct, zlib


class DatArchive(object):
    def __init__(self, path):
        self.path = path
        d = open(path, 'rb').read()
        dsize = struct.unpack_from('<I', d, len(d) - 4)[0]
        p = len(d) - dsize
        n = struct.unpack_from('<I', d, p)[0]; p += 4
        ents = []
        for _ in range(n):
            ln = struct.unpack_from('<I', d, p)[0]; p += 4
            name = d[p:p + ln].rstrip(b'\0').decode('latin-1'); p += ln
            _u, flags, usize, csize, off, parent, _fc, _ns = struct.unpack_from('<IIIIIiii', d, p); p += 32
            ents.append((name, flags, usize, csize, off, parent))
        self._d, self.files = d, {}
        for i, (name, flags, usize, csize, off, parent) in enumerate(ents):
            if flags & 0x400:   # directory
                continue
            parts, j = [name], parent
            while j >= 0:
                parts.append(ents[j][0]); j = ents[j][5]
            self.files['/'.join(reversed(parts)).lower()] = (flags, csize, off)

    def read(self, rel):
        flags, csize, off = self.files[rel.lower().replace('\\', '/')]
        raw = self._d[off:off + csize]
        return zlib.decompress(raw) if flags & 2 else raw


class ToEEData(object):
    """Lookup order (later wins, like the engine's mount order): ToEE*.dat, then module dats, then loose data/ and
    modules/<module>/ files."""

    def __init__(self, root, module='ToEE'):
        self.root = root
        self.sources = []
        for n in sorted(os.listdir(root)):
            if re.match(r'toee\d*\.dat$', n, re.I):
                self.sources.append(DatArchive(os.path.join(root, n)))
        mdir = os.path.join(root, 'modules')
        if os.path.isdir(mdir):
            for n in sorted(os.listdir(mdir)):
                # Temple+ mounts <module>_core.dat and <module>.dat only (TemplePlus.log), not the Steam
                # edition's ToEESteam*.dat, so protos that only exist there cannot be created in game
                if n.lower() in ((module + '_core.dat').lower(), (module + '.dat').lower()):
                    self.sources.append(DatArchive(os.path.join(mdir, n)))
        self.loose = [os.path.join(root, 'data'), os.path.join(root, 'modules', module)]

    def read(self, rel):
        for base in reversed(self.loose):
            p = os.path.join(base, rel)
            if os.path.isfile(p):
                return open(p, 'rb').read()
        for s in reversed(self.sources):
            try:
                return s.read(rel)
            except KeyError:
                continue
        raise FileNotFoundError(rel)

    def mes(self, rel):
        out = {}
        try:
            txt = self.read(rel).decode('latin-1')
        except FileNotFoundError:
            return out
        for m in re.finditer(r'\{(\d+)\}\s*\{([^}]*)\}', txt):
            out.setdefault(int(m.group(1)), m.group(2))
        return out

    def protos(self):
        """{proto id: list of 334 column strings} for every row in rules/protos.tab."""
        rows = {}
        for line in self.read('rules/protos.tab').decode('latin-1').split('\n'):
            r = line.split('\t')
            if r and r[0].isdigit():
                rows.setdefault(int(r[0]), r + [''] * (334 - len(r)))
        return rows


# protos.tab columns used here (column table read from temple.dll, cross-checked with Temple+ temple_enums.h)
COL = dict(type=1, name=22, description=23, size=24, hp_pts=25, model=34, flags_critter=99, str=101, race=108, gender=109,
           alignment=113, npc_flags=152, cr=157, save_ref=158, save_fort=159, save_will=160, ac_bonus=161, hit_dice=162,
           mc_type=163, mc_subtype=164, class1=228, level1=229, strategy=333)

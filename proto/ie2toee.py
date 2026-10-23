#!/usr/bin/env python3
"""Prototype: convert one IE area (BG/IWD/IWD2) into a ToEE/Temple+ map folder.

  python3 ie2toee.py --game <IE install> --area AR1000 --out <outdir> [--map-id 5900] [--ground-id 900]
                     [--guidance guidance/iwd.json] [--closed-doors] [--preview]

Writes (all derived from the player's own files, on the player's machine):
  art/ground/<AREA>/yyyyxxxx.jpg  256x256 background tiles (+ <AREA>_night if an N variant exists)
  maps/<AREA>/*.sec               per-subtile Block/FlyOver bits + footstep material from the SR map
  maps/<AREA>/map.prp, mapinfo.txt, global.lit, fog.col, gmesh.gmf/gmi (empty), pathnode.pnd
  maps/<AREA>/clipping.cgf/.cif + art/clip/<AREA>/*.dag   occluders built from WED wall polygons
  <AREA>_snippets.txt  lines for art/ground/ground.mes, rules/MapList.mes, mes/map_names.mes
  <AREA>_objects.json  entrances/actors/doors/containers/regions/animations in ToEE tile coords
  <AREA>_doors.json, ie_doors_<area>.py   per door: default state, portal position, open/closed Block masks per tile
  art/ground/<AREA>_doors/*.tga  open/closed WED tile variants of every door (ground patches for runtime/ie_doors.py)
  <AREA>_preview.png   (optional) background with walkability overlay
"""
import argparse, json, math, os, struct, sys
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from iefs import IEGame
from ieformats import Tis, Wed, Are, render_background, load_index_bmp, decode_pvrz, door_cell_tiles

INCH_PER_TILE = 28.284271247461900976  # infrastructure/location.h
GROUND_TILE = 256                       # TerrainSystem::TileSize
GROUND_W, GROUND_H = 66 * 256, 71 * 256 # TerrainSystem::MapWidthTiles/HeightTiles
MAP_LIMIT = 960
SECTOR = 64
COS_ELEV = math.cos(0.77539754)         # gfx::WorldCamera pitch: screen px per inch of height
# Ground-canvas pixel of the top vertex of tile (u,v): ((v-u)*20 + CAL_X, (u+v)*14 + CAL_Y).
# Derived from TerrainSystem::Render + LocationSys::ToTranslation (map centre tile 480,480);
# CAL_DX/CAL_DY are empirical corrections from calibration (see calibrate.py / plan.md).
CAL_X0 = 8448 - 40 + 20
CAL_Y0 = 9088 - 14 - 960 * 14
CAL_DX, CAL_DY = 0.0, 0.0
SR_CELL_W, SR_CELL_H = 16, 12

BLOCK0, FLY0 = 0x200, 0x40000
DOOR_BLOCK_VALUE = 0   # search-map value used for impeded door cells (block)
MATERIAL = dict(ReservedBlocked=0, ReservedFlyOver=1, Dirt=2, Grass=3, Water=4, DeepWater=5,
                Ice=6, Fire=7, Wood=8, Stone=9, Metal=10, Marsh=11)

DEFAULT_GUIDANCE = {
    # IWD/IWD2 terrain.2da PASSABLE row (gemRB unhardcoded/iwd*): 1 walk, 2 travel, 4 opaque, 8 sidewall
    "searchmap": {
        "0": ["block", "ReservedBlocked"], "1": ["walk", "Dirt"], "2": ["walk", "Wood"],
        "3": ["walk", "Wood"], "4": ["walk", "Stone"], "5": ["walk", "Grass"], "6": ["walk", "Water"],
        "7": ["walk", "Stone"], "8": ["flyover", "ReservedFlyOver"], "9": ["walk", "Wood"],
        "10": ["block", "ReservedBlocked"], "11": ["walk", "Ice"], "12": ["flyover", "DeepWater"],
        "13": ["block", "ReservedBlocked"], "14": ["walk", "Dirt"], "15": ["walk", "Grass"]},
    "scale": 1.0,
    "jpeg_quality": 92,
    "pathnode_spacing_tiles": 10,
    "pathnode_link_tiles": 28,
    "placement": "centre",   # or [cx, cy] canvas offset of the IE image's top-left pixel
    "cal": [0.0, 0.0],       # extra canvas-pixel correction (CAL_DX, CAL_DY)
    "areas": {}
}


class Placement:
    """IE pixel <-> ToEE ground-canvas pixel <-> continuous ToEE tile coords."""

    def __init__(self, w, h, scale=1.0, offset=None, cal=(CAL_DX, CAL_DY)):
        self.scale = scale
        self.w, self.h = int(round(w * scale)), int(round(h * scale))
        if self.w > GROUND_W or self.h > GROUND_H:
            raise ValueError(f'area {self.w}x{self.h}px exceeds ToEE ground canvas {GROUND_W}x{GROUND_H}')
        if offset is None or offset == 'centre':
            self.cx, self.cy = (GROUND_W - self.w) // 2, (GROUND_H - self.h) // 2
        else:
            self.cx, self.cy = offset
        self.calx, self.caly = CAL_X0 + cal[0], CAL_Y0 + cal[1]

    def ie_to_canvas(self, x, y):
        return self.cx + np.asarray(x, float) * self.scale, self.cy + np.asarray(y, float) * self.scale

    def canvas_to_tile(self, X, Y):
        a = (np.asarray(X) - self.calx) / 20.0   # v - u
        b = (np.asarray(Y) - self.caly) / 14.0   # u + v
        return (b - a) / 2.0, (b + a) / 2.0

    def tile_to_canvas(self, u, v):
        u = np.asarray(u, float); v = np.asarray(v, float)
        return (v - u) * 20.0 + self.calx, (u + v) * 14.0 + self.caly

    def ie_to_tile(self, x, y):
        return self.canvas_to_tile(*self.ie_to_canvas(x, y))

    def tile_to_ie(self, u, v):
        X, Y = self.tile_to_canvas(u, v)
        return (X - self.cx) / self.scale, (Y - self.cy) / self.scale

    def tile_bbox(self):
        xs = np.array([0, self.w, 0, self.w]) / self.scale
        ys = np.array([0, 0, self.h, self.h]) / self.scale
        us, vs = self.ie_to_tile(xs, ys)
        return (int(math.floor(us.min())), int(math.ceil(us.max())), int(math.floor(vs.min())), int(math.ceil(vs.max())))


def write_ground(img, pl, outdir, quality):
    os.makedirs(outdir, exist_ok=True)
    if pl.scale != 1.0:
        img = np.asarray(Image.fromarray(img).resize((pl.w, pl.h), Image.LANCZOS))
    rgb = img[..., :3]
    n = 0
    for ty in range(pl.cy // GROUND_TILE, (pl.cy + pl.h - 1) // GROUND_TILE + 1):
        for tx in range(pl.cx // GROUND_TILE, (pl.cx + pl.w - 1) // GROUND_TILE + 1):
            tile = np.zeros((GROUND_TILE, GROUND_TILE, 3), np.uint8)
            x0, y0 = tx * GROUND_TILE - pl.cx, ty * GROUND_TILE - pl.cy
            sx0, sy0 = max(0, x0), max(0, y0)
            sx1, sy1 = min(pl.w, x0 + GROUND_TILE), min(pl.h, y0 + GROUND_TILE)
            tile[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = rgb[sy0:sy1, sx0:sx1]
            Image.fromarray(tile).save(os.path.join(outdir, f'{ty:04x}{tx:04x}.jpg'), quality=quality)
            n += 1
    return n


def sample_kinds(sr, pl, guidance, SU, SV):
    """kind (0 walk,1 block,2 flyover) and material for continuous tile points."""
    X, Y = pl.tile_to_ie(SU, SV)
    cx = np.floor(X / SR_CELL_W).astype(int)
    cy = np.floor(Y / SR_CELL_H).astype(int)
    inside = (X >= 0) & (Y >= 0) & (cx < sr.shape[1]) & (cy < sr.shape[0])
    val = np.where(inside, sr[np.clip(cy, 0, sr.shape[0] - 1), np.clip(cx, 0, sr.shape[1] - 1)], 255)
    kind = np.full(val.shape, 1, np.int8)
    mat = np.full(val.shape, MATERIAL['ReservedBlocked'], np.int16)
    for k, (what, m) in guidance['searchmap'].items():
        sel = val == int(k)
        kind[sel] = {'walk': 0, 'block': 1, 'flyover': 2}[what]
        mat[sel] = MATERIAL[m]
    return kind, mat


def build_tile_grid(sr, pl, guidance, bbox):
    """Per tile in bbox: flags (Block/FlyOver per subtile, sampled at the 3x3 subtile centres) and
    footstep material. Outside the IE image = blocked."""
    u0, u1, v0, v1 = bbox
    U, V = np.meshgrid(np.arange(u0, u1), np.arange(v0, v1), indexing='ij')
    sub = (np.arange(3) + 0.5) / 3.0
    SU = U[..., None, None] + sub[None, None, :, None]   # [..., i(x), j(y)]
    SV = V[..., None, None] + sub[None, None, None, :]
    kind, mat = sample_kinds(sr, pl, guidance, SU, SV)
    shift = (np.arange(3)[:, None] + 3 * np.arange(3)[None, :])   # i + 3j  (BlockX{i}Y{j})
    flags = ((kind == 1) * (BLOCK0 << shift)).sum((-1, -2)) | ((kind == 2) * (FLY0 << shift)).sum((-1, -2))
    walk = (kind == 0).reshape(*kind.shape[:2], 9)
    fm = mat.reshape(*mat.shape[:2], 9)
    tmat = fm[..., 4].copy()
    for a, b in zip(*np.nonzero(walk.any(-1))):
        vals, cnt = np.unique(fm[a, b][walk[a, b]], return_counts=True)
        tmat[a, b] = vals[cnt.argmax()]
    return U, V, flags.astype(np.uint32), tmat.astype(np.uint8), kind


def sector_bytes(tiles_flags, tiles_mat):
    """Minimal vanilla-compatible .sec (layout checked against vanilla sectors / OpenTemple)."""
    out = bytearray(struct.pack('<i', 0))
    t = np.zeros((4096, 16), np.uint8)
    t[:, 0] = tiles_mat
    t[:, 4:8] = np.asarray(tiles_flags, '<u4').view(np.uint8).reshape(4096, 4)
    out += t.tobytes()
    out += struct.pack('<iIi3i3i3ii', 1, 0xAA0004, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    return bytes(out)


def write_sectors(U, V, flags, mats, mapdir, margin=1):
    allblock = sum(BLOCK0 << s for s in range(9))
    su0, su1 = U.min() // SECTOR - margin, U.max() // SECTOR + margin
    sv0, sv1 = V.min() // SECTOR - margin, V.max() // SECTOR + margin
    gF = np.full((MAP_LIMIT, MAP_LIMIT), allblock, np.uint32)  # [u, v]
    gM = np.zeros((MAP_LIMIT, MAP_LIMIT), np.uint8)
    ok = (U >= 0) & (V >= 0) & (U < MAP_LIMIT) & (V < MAP_LIMIT)
    gF[U[ok], V[ok]] = flags[ok]; gM[U[ok], V[ok]] = mats[ok]
    n = 0
    for sy in range(max(0, sv0), min(MAP_LIMIT // SECTOR - 1, sv1) + 1):
        for sx in range(max(0, su0), min(MAP_LIMIT // SECTOR - 1, su1) + 1):
            # tile index inside the sector = ly*64 + lx  (x = u, y = v)
            f = gF[sx * 64:(sx + 1) * 64, sy * 64:(sy + 1) * 64].T.reshape(-1)
            m = gM[sx * 64:(sx + 1) * 64, sy * 64:(sy + 1) * 64].T.reshape(-1)
            open(os.path.join(mapdir, f'{(sy << 26) | sx}.sec'), 'wb').write(sector_bytes(f, m))
            n += 1
    return n


def _ear_clip(pts):
    pts = list(pts)
    if len(pts) < 3:
        return []
    area = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))
    idx = list(range(len(pts))) if area > 0 else list(range(len(pts)))[::-1]
    cross = lambda a, b, c: (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    tris, guard = [], 0
    while len(idx) > 3 and guard < 20000:
        guard += 1
        for k in range(len(idx)):
            a, b, c = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            if cross(pts[a], pts[b], pts[c]) <= 0:
                continue
            if any(cross(pts[a], pts[b], pts[p]) > 0 and cross(pts[b], pts[c], pts[p]) > 0 and cross(pts[c], pts[a], pts[p]) > 0
                   for p in idx if p not in (a, b, c)):
                continue
            tris.append((a, b, c)); idx.pop(k); break
        else:
            break
    if len(idx) == 3:
        tris.append(tuple(idx))
    return tris


def wall_mesh(walls, pl, img_h):
    """IE wall polygon -> vertical curtain on its baseline. Vertex (sx,sy) sits above ground point
    (sx, baseline_y(sx)) at height (baseline_y - sy)/cos(pitch): projects exactly onto the polygon with
    the baseline's depth (IE: actor behind wall iff beyond baseline). No baseline -> always in front."""
    verts, tris = [], []
    for w in walls:
        pts = w['points']
        if len(pts) < 3:
            continue
        if w['baseline']:
            (x0, y0), (x1, y1) = w['baseline']
        else:
            x0, x1, y0, y1 = 0, 1, img_h + 400, img_h + 400
        base = len(verts)
        for (sx, sy) in pts:
            yb = y0 if x1 == x0 else y0 + (y1 - y0) * (sx - x0) / (x1 - x0)
            gu, gv = pl.ie_to_tile(sx, yb)
            h = (yb - sy) * pl.scale / COS_ELEV
            # clipping_vs.hlsl, rotation 0, scale 1, instance at origin: world = (-x, z, -y)
            verts.append((-float(gu) * INCH_PER_TILE, -float(gv) * INCH_PER_TILE, float(h)))
        tris += [(base + a, base + b, base + c) for a, b, c in _ear_clip(pts)]
    return verts, tris


def dag_bytes(verts, tris):
    v = np.array(verts, np.float32).reshape(-1, 3)
    c = v.mean(0) if len(v) else np.zeros(3, np.float32)
    r = float(np.sqrt(((v - c) ** 2).sum(1)).max()) if len(v) else 0.0
    vtx_off = 24 + 16
    idx_off = vtx_off + 12 * len(v)
    return (struct.pack('<4fii', *c, r, 1, 24) + struct.pack('<4i', len(v), len(tris), vtx_off, idx_off)
            + v.tobytes() + np.array(tris, np.uint16).reshape(-1).tobytes())


def write_clipping(walls, pl, img_h, mapdir, clipdir, name):
    verts, tris = wall_mesh(walls, pl, img_h)
    os.makedirs(clipdir, exist_ok=True)
    chunks, cur_v, cur_t, remap = [], [], [], {}
    for t in tris:
        if len(cur_v) + 3 > 65000:
            chunks.append((cur_v, cur_t)); cur_v, cur_t, remap = [], [], {}
        nt = []
        for i in t:
            if i not in remap:
                remap[i] = len(cur_v); cur_v.append(verts[i])
            nt.append(remap[i])
        cur_t.append(tuple(nt))
    if cur_t:
        chunks.append((cur_v, cur_t))
    cgf = struct.pack('<i', len(chunks)); cif = struct.pack('<i', len(chunks))
    for k, (cv, ct) in enumerate(chunks):
        fn = f'{name}_{k}.dag'
        open(os.path.join(clipdir, fn), 'wb').write(dag_bytes(cv, ct))
        cgf += f'art\\clip\\{name}\\{fn}'.encode().ljust(260, b'\0')
        cif += struct.pack('<I7f', k, 0, 0, 0, 1, 1, 1, 0)
    open(os.path.join(mapdir, 'clipping.cgf'), 'wb').write(cgf)
    open(os.path.join(mapdir, 'clipping.cif'), 'wb').write(cif)
    return len(chunks), len(tris)


def write_pathnodes(U, V, kind, mapdir, spacing, link):
    """Seed nodes on a coarse grid of fully walkable tiles and link mutually visible ones.
    Temple+ then builds clearance.bin in game (debug.generate_clearance_file())."""
    walk_tile = (kind == 0).all((-1, -2))
    u0, v0 = int(U.min()), int(V.min())
    sub = np.zeros((walk_tile.shape[0] * 3, walk_tile.shape[1] * 3), bool)
    for i in range(3):
        for j in range(3):
            sub[i::3, j::3] = kind[..., i, j] == 0
    nodes = [(a, b) for a in range(spacing // 2, walk_tile.shape[0], spacing)
             for b in range(spacing // 2, walk_tile.shape[1], spacing) if walk_tile[a, b]]

    def clear(p, q):
        n = int(max(abs(p[0] - q[0]), abs(p[1] - q[1])) * 3) + 1
        for t in np.linspace(0, 1, n):
            if not sub[int((p[0] + (q[0] - p[0]) * t) * 3 + 1), int((p[1] + (q[1] - p[1]) * t) * 3 + 1)]:
                return False
        return True

    nb = {i: [] for i in range(len(nodes))}
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            if math.dist(nodes[i], nodes[j]) <= link and clear(nodes[i], nodes[j]):
                nb[i].append(j); nb[j].append(i)
    out = bytearray(struct.pack('<i', len(nodes)))
    for i, (a, b) in enumerate(nodes):
        out += struct.pack('<iIIffi', i, u0 + a, v0 + b, 0.0, 0.0, len(nb[i])) + struct.pack(f'<{len(nb[i])}i', *nb[i])
    open(os.path.join(mapdir, 'pathnode.pnd'), 'wb').write(out)
    return len(nodes)


def door_cell_masks(cells, pl, sr_shape):
    """ToEE tiles covered by IE impeded search-map cells -> {(u,v): Block mask of the covered subtiles}."""
    out = {}
    for cx, cy in cells:
        if not (0 <= cy < sr_shape[0] and 0 <= cx < sr_shape[1]):
            continue
        X0, Y0 = cx * SR_CELL_W, cy * SR_CELL_H
        us, vs = pl.ie_to_tile(np.array([X0, X0 + SR_CELL_W, X0, X0 + SR_CELL_W]), np.array([Y0, Y0, Y0 + SR_CELL_H, Y0 + SR_CELL_H]))
        for u in range(int(math.floor(us.min())), int(math.ceil(us.max()))):
            for v in range(int(math.floor(vs.min())), int(math.ceil(vs.max()))):
                for i in range(3):
                    for j in range(3):
                        X, Y = pl.tile_to_ie(u + (i + 0.5) / 3, v + (j + 0.5) / 3)
                        if X0 <= X < X0 + SR_CELL_W and Y0 <= Y < Y0 + SR_CELL_H:
                            out[(u, v)] = out.get((u, v), 0) | (BLOCK0 << (i + 3 * j))
    return out


def write_doors(g, are, wed, tis_for, pl, guidance, sr, bbox, outdir, name, doors_closed):
    """Per door: default state, ToEE position, per-tile blocking for both states (to switch at runtime), and the
    'faithful' extra: both WED tile variants as ground-overlay patches (TGA, canvas coords) for a runtime tile swap.
    Writes <AREA>_doors.json and art/ground/<AREA>_doors/*.tga (derived from the player's files: local only)."""
    tis = tis_for(wed.overlays[0]['tis'])
    U, V, flags_nod, _, _ = build_tile_grid(are.sr_nodoors, pl, guidance, bbox)
    u0, v0 = bbox[0], bbox[2]
    pdir = os.path.join(outdir, 'art', 'ground', name + '_doors')
    os.makedirs(pdir, exist_ok=True)
    closed_set = {n.lower() for n in doors_closed}
    doors = []
    for k, d in enumerate(are.doors):
        wd = next((w for w in wed.doors if w['name'].lower() == d['wed_id'].lower()), None)
        m_open = door_cell_masks(d['open_cells'], pl, sr.shape)
        m_closed = door_cell_masks(d['closed_cells'], pl, sr.shape)
        tiles = []
        for (u, v) in sorted(set(m_open) | set(m_closed)):
            a, b = u - u0, v - v0
            base = int(flags_nod[a, b]) if 0 <= a < flags_nod.shape[0] and 0 <= b < flags_nod.shape[1] else 0
            tiles.append([u, v, base, m_open.get((u, v), 0), m_closed.get((u, v), 0)])
        cells = d['closed_cells'] or d['open_cells']
        if cells:   # door object on the ground at the centre of its impeded cells
            px = np.mean([c[0] for c in cells]) * SR_CELL_W + SR_CELL_W / 2
            py = np.mean([c[1] for c in cells]) * SR_CELL_H + SR_CELL_H / 2
        else:
            x0, y0, x1, y1 = d['closed_bbox'] if d['closed_bbox'][0] != 65535 else d['open_bbox']
            px, py = (x0 + x1) / 2, y1
        u, v = pl.ie_to_tile(px, py); u, v = float(u), float(v)
        tu, tv = pl.ie_to_tile(*d['toggle_points'][0])
        patches = {}
        if wd and wd['cells']:
            for state in ('open', 'closed'):
                ct = door_cell_tiles(wed, tis, wd, state == 'closed')
                xs = [c[1] for c in ct]; ys = [c[2] for c in ct]
                X0, Y0, X1, Y1 = min(xs), min(ys), max(xs) + 64, max(ys) + 64
                img = np.zeros((Y1 - Y0, X1 - X0, 4), np.uint8)
                for _, x, y, t in ct:
                    img[y - Y0:y - Y0 + 64, x - X0:x - X0 + 64] = t
                fn = f'{d["wed_id"].lower()}_{state}.tga'
                Image.fromarray(img).save(os.path.join(pdir, fn))
                cx, cy = pl.ie_to_canvas(X0, Y0)
                patches[state] = dict(texture=f'art/ground/{name}_doors/{fn}', x=int(cx), y=int(cy), w=X1 - X0, h=Y1 - Y0)
        doors.append(dict(
            index=k, name=d['name'], wed_id=d['wed_id'], open=d['wed_id'].lower() not in closed_set,
            locked=bool(d['flags'] & 2), secret=bool(d['flags'] & 0x80), lock_difficulty=d['lock_difficulty'],
            key=d['key'], script=d['script'],
            loc=[int(math.floor(u)), int(math.floor(v)),
                 round((u - math.floor(u) - 0.5) * INCH_PER_TILE, 2), round((v - math.floor(v) - 0.5) * INCH_PER_TILE, 2)],
            toggle_tile=[int(tu), int(tv)], tiles=tiles, patches=patches,
            wed_primary_closed=bool(wd['closed']) if wd else None))
    json.dump(dict(area=name, doors=doors), open(os.path.join(outdir, f'{name}_doors.json'), 'w'), indent=1)
    # Python 2.7 data module for the Temple+ runtime (ie_doors.py)
    with open(os.path.join(outdir, f'ie_doors_{name.lower()}.py'), 'w') as f:
        f.write('# generated by ie2toee from the player\'s own IE install - do not distribute\n')
        f.write('DOORS = ' + repr(json.loads(json.dumps(doors))).replace("True", "1").replace("False", "0").replace("None", "0") + '\n')
    return dict(count=len(doors), closed=sum(not x['open'] for x in doors), with_patches=sum(bool(x['patches']) for x in doors))


def _walkable(kind, bbox, a, b, strict=True):
    """tile (a, b) in the bbox-relative grid: all 9 subtiles walkable (strict) or the centre one plus >= 5 of 9."""
    if not (0 <= a < kind.shape[0] and 0 <= b < kind.shape[1]):
        return False
    k = kind[a, b]
    return bool((k == 0).all()) if strict else bool(k[1, 1] == 0 and (k == 0).sum() >= 5)


def arrival_tile(kind, bbox, u, v, radius=5):
    """(tile u, tile v, moved) where a party arriving at IE entrance (u, v) is put: the entrance's own tile if it is
    walkable, else the nearest walkable tile within `radius` tiles (fully walkable tiles first, then mostly walkable
    ones); (floor u, floor v, None) if there is none (the entrance stays where it is)."""
    iu, iv = int(math.floor(u)), int(math.floor(v))
    for strict in (True, False):
        best = None
        for du in range(-radius, radius + 1):
            for dv in range(-radius, radius + 1):
                d = math.hypot(iu + du + 0.5 - u, iv + dv + 0.5 - v)
                if d <= radius + 0.5 and _walkable(kind, bbox, iu + du - bbox[0], iv + dv - bbox[2], strict):
                    if best is None or d < best[0]:
                        best = (d, iu + du, iv + dv)
        if best:
            return best[1], best[2], (best[1], best[2]) != (iu, iv)
    return iu, iv, None


def load_area(game, area, guidance, closed_doors=False):
    g = IEGame(game) if isinstance(game, str) else game
    are = Are(g.read(area, 'are'))
    wed = Wed(g.read(are.wed, 'wed'))

    def tis_for(name):
        night = name.upper().endswith('N') and len(name) > 6
        loader = lambda page: decode_pvrz(g.read(f'{name[0]}{name[2:6]}{"N" if night else ""}{page:02d}', 'pvrz'))
        return Tis(g.read(name, 'tis'), loader)
    ag = guidance.get('areas', {}).get(area.upper(), {})
    # Door state: ARE flag bit0 = open. Default: bake each door in its ARE state (closed_doors=True forces all closed).
    if closed_doors:
        doors_closed = [d['wed_id'] for d in are.doors]
    else:
        doors_closed = [d['wed_id'] for d in are.doors if not (d['flags'] & 1)]
    over = ag.get('door_state', {})   # {"DOOR1": "open"|"closed"}
    doors_closed = [n for n in doors_closed if over.get(n.upper(), 'closed') == 'closed'] + \
                   [n for n, st in over.items() if st == 'closed' and n not in doors_closed]
    tis = tis_for(wed.overlays[0]['tis'])
    ov = {k: tis_for(o['tis']) for k, o in enumerate(wed.overlays) if k and o['tis'] and g.exists(o['tis'], 'tis')}
    img = render_background(wed, tis, ov, doors_closed)
    sr = load_index_bmp(g.read(area + 'SR', 'bmp'))
    sr_nodoors = sr.copy()
    # bake the default state's impeded cells (IE blocks them at runtime) into the search map
    sr = sr.copy()
    closed_set = {n.lower() for n in doors_closed}
    for d in are.doors:
        cells = d['closed_cells'] if d['wed_id'].lower() in closed_set else d['open_cells']
        for cx, cy in cells:
            if 0 <= cy < sr.shape[0] and 0 <= cx < sr.shape[1]:
                sr[cy, cx] = DOOR_BLOCK_VALUE
    are.sr_nodoors = sr_nodoors
    for x, y, w, h, val in ag.get('searchmap_fix', []):
        sr = sr.copy(); sr[y:y + h, x:x + w] = val
    return g, are, wed, img, sr, doors_closed, tis_for


def convert(game, area, outdir, map_id, ground_id, guidance, preview=False, closed_doors=False):
    g, are, wed, img, sr, doors_closed, tis_for = load_area(game, area, guidance, closed_doors)
    W, H = wed.size_px
    ag = guidance.get('areas', {}).get(area.upper(), {})
    pl = Placement(W, H, guidance.get('scale', 1.0), ag.get('placement', guidance.get('placement')), ag.get('cal', guidance.get('cal', (0, 0))))
    name = area.upper()
    mapdir = os.path.join(outdir, 'maps', name)
    os.makedirs(mapdir, exist_ok=True)
    report = dict(area=name, are_version=are.version, size_px=[W, H], canvas_offset=[pl.cx, pl.cy])
    report['ground_tiles'] = write_ground(img, pl, os.path.join(outdir, 'art', 'ground', name), guidance['jpeg_quality'])
    if are.has_night and g.exists(are.wed + 'N', 'wed'):
        wn = Wed(g.read(are.wed + 'N', 'wed'))
        report['night_tiles'] = write_ground(render_background(wn, tis_for(wn.overlays[0]['tis']), None, doors_closed), pl,
                                             os.path.join(outdir, 'art', 'ground', name + '_night'), guidance['jpeg_quality'])
    bbox = pl.tile_bbox()
    U, V, flags, mats, kind = build_tile_grid(sr, pl, guidance, bbox)
    report['tile_bbox'] = bbox
    report['sectors'] = write_sectors(U, V, flags, mats, mapdir)
    report['walkable_subtiles'] = int((kind == 0).sum())
    nclip, ntri = write_clipping(wed.walls, pl, H, mapdir, os.path.join(outdir, 'art', 'clip', name), name)
    report['clipping'] = dict(meshes=nclip, triangles=ntri, wall_polygons=len(wed.walls))
    report['pathnodes'] = write_pathnodes(U, V, kind, mapdir, guidance['pathnode_spacing_tiles'], guidance['pathnode_link_tiles'])
    open(os.path.join(mapdir, 'map.prp'), 'wb').write(struct.pack('<iiQQ', ground_id, 0, MAP_LIMIT, MAP_LIMIT))
    open(os.path.join(mapdir, 'global.lit'), 'wb').write(struct.pack('<2i3f3f2f3f', 1, 3, 1.5, 1.5, 1.5, 0, 0, 0, -0.6324094, -0.7746344, 0, 0, 0))
    open(os.path.join(mapdir, 'fog.col'), 'wb').write(struct.pack('<2i', 671088640, 1056964608))
    open(os.path.join(mapdir, 'gmesh.gmf'), 'wb').write(struct.pack('<i', 0))
    open(os.path.join(mapdir, 'gmesh.gmi'), 'wb').write(struct.pack('<i', 0))
    open(os.path.join(mapdir, 'mapinfo.txt'), 'w').write('')
    report['doors'] = write_doors(g, are, wed, tis_for, pl, guidance, sr, bbox, outdir, name, doors_closed)
    # start = first entrance that lands on a walkable tile
    def tl(x, y):
        u, v = pl.ie_to_tile(x, y); return [round(float(u), 2), round(float(v), 2)]
    start = None
    for e in are.entrances + [dict(x=W // 2, y=H // 2)]:
        u, v = tl(e['x'], e['y'])
        a, b = int(u) - bbox[0], int(v) - bbox[2]
        if 0 <= a < kind.shape[0] and 0 <= b < kind.shape[1] and (kind[a, b] == 0).all():
            start = (int(u), int(v)); break
    start = start or tuple(int(t) for t in tl(W // 2, H // 2))
    report['start_tile'] = start
    open(os.path.join(mapdir, 'startloc.txt'), 'w').write(f'{start[0]}\r\n{start[1]}\r\n')
    flags_s = ['Flag: OUTDOOR'] if are.area_type & 1 else []
    if 'night_tiles' in report:
        flags_s.append('Flag: DAYNIGHT_XFER')
    sn = ['# art/ground/ground.mes', f'{{{ground_id}}}{{{name}}}']
    # The terrain system switches to groundId+1000 whenever it is night, even without DAYNIGHT_XFER,
    # so always provide the night id (falls back to the day art).
    sn.append(f'{{{ground_id + 1000}}}{{{name}_night}}' if 'night_tiles' in report else f'{{{ground_id + 1000}}}{{{name}}}')
    sn += ['# rules/MapList.mes', f'{{{map_id}}}{{{name}, {start[0]}, {start[1]}' + ''.join(', ' + f for f in flags_s) + '}',
           '# mes/map_names.mes', f'{{{map_id}}}{{{name}}}']
    open(os.path.join(outdir, f'{name}_snippets.txt'), 'w').write('\n'.join(sn) + '\n')
    def _arrival(e):
        u, v = tl(e['x'], e['y'])
        au, av, moved = arrival_tile(kind, bbox, u, v)
        if moved is None:
            print(f'warning: {name} entrance {e["name"]} has no walkable tile within 5 tiles', file=sys.stderr)
        return dict(arrival=[au, av], arrival_moved=bool(moved))
    objs = dict(
        placement=dict(canvas_offset=[pl.cx, pl.cy], scale=pl.scale, cal=[pl.calx - CAL_X0, pl.caly - CAL_Y0]),
        entrances=[dict(e, toee=tl(e['x'], e['y']), **_arrival(e)) for e in are.entrances],
        actors=[dict(a, toee=tl(a['x'], a['y'])) for a in are.actors],
        containers=[dict(c, toee=tl(c['x'], c['y']), poly=[tl(*p) for p in c['poly']]) for c in are.containers],
        regions=[dict(r, poly=[tl(*p) for p in r['poly']]) for r in are.regions],
        doors=[dict(d, wed=next((dict(cells=len(w['cells']), closed_polys=len(w['closed_polys'])) for w in wed.doors
                                 if w['name'].lower() == d['wed_id'].lower()), None)) for d in are.doors],
        animations=[dict(a, toee=tl(a['x'], a['y'])) for a in are.animations])
    json.dump(objs, open(os.path.join(outdir, f'{name}_objects.json'), 'w'), indent=1)
    if preview:
        Y, X = np.mgrid[0:H, 0:W]
        val = sr[np.clip(Y // SR_CELL_H, 0, sr.shape[0] - 1), np.clip(X // SR_CELL_W, 0, sr.shape[1] - 1)]
        kk = np.ones_like(val, np.int8)
        for k, (what, _) in guidance['searchmap'].items():
            kk[val == int(k)] = {'walk': 0, 'block': 1, 'flyover': 2}[what]
        ov = img[..., :3].astype(np.float32)
        ov[kk == 1] = ov[kk == 1] * 0.45 + np.array([255, 0, 0]) * 0.55
        ov[kk == 2] = ov[kk == 2] * 0.45 + np.array([0, 80, 255]) * 0.55
        pim = Image.fromarray(ov.astype(np.uint8)); d = ImageDraw.Draw(pim)
        for w in wed.walls:
            if len(w['points']) > 1:
                d.line(w['points'] + w['points'][:1], fill=(255, 255, 0), width=2)
            if w['baseline']:
                d.line(list(w['baseline']), fill=(0, 255, 0), width=3)
        for e in are.entrances:
            d.ellipse([e['x'] - 6, e['y'] - 6, e['x'] + 6, e['y'] + 6], outline=(255, 255, 255), width=2)
        pim.save(os.path.join(outdir, f'{name}_preview.png'))
    json.dump(report, open(os.path.join(outdir, f'{name}_report.json'), 'w'), indent=1)
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--game', required=True); ap.add_argument('--area', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--map-id', type=int, default=5900); ap.add_argument('--ground-id', type=int, default=900)
    ap.add_argument('--guidance'); ap.add_argument('--preview', action='store_true')
    ap.add_argument('--closed-doors', action='store_true')
    a = ap.parse_args()
    guid = json.loads(json.dumps(DEFAULT_GUIDANCE))
    if a.guidance:
        guid.update(json.load(open(a.guidance)))
    print(json.dumps(convert(a.game, a.area, a.out, a.map_id, a.ground_id, guid, a.preview, a.closed_doors), indent=1))


if __name__ == '__main__':
    main()

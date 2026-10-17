# ie2toee

Converts Infinity Engine areas (Icewind Dale, Icewind Dale II, Baldur's Gate) into maps for
**The Temple of Elemental Evil** running on [Temple+](https://github.com/GrognardsFromHell/TemplePlus).
It is meant for total conversions such as the Co8 IWD / IWD2 projects. The conversion is a one-time offline step
that each player runs on their own copy of the IE game.

Status: **working prototype**. Real IWD1 areas convert and load in Temple+: art, walkability, occlusion, start
position and doors. Actors, containers, travel regions, lighting, sound and animations are exported as data but not
turned into ToEE objects yet. See [docs/design.md](docs/design.md).

## Legal model: no IE assets are distributed

* This repository contains **only code and documentation**. It has no Infinity Engine art, maps, strings, names or
  any other content, and nothing derived from them.
* A TC ships this converter plus small per-area *guidance* files: facts and choices such as map ids, terrain-type
  mapping, door state overrides and fix-up rectangles. Guidance never contains IE pixels, text or names.
* **The player** runs the converter on **their own legally owned** IE installation. Everything it generates (ground
  art, `.sec` blocking, clipping meshes, door patches, JSON) is derived from the player's files. It stays on the
  player's machine and **must never be committed, uploaded or redistributed**. `.gitignore` excludes the usual
  outputs (`out/`, images, map binaries, IE resource types) as a safety net.
* The code is a clean-room implementation written from the public file-format documentation in
  [IESDP](https://gibberlings3.github.io/iesdp/). It is **not derived from GemRB** (GPL): no GemRB code was copied or
  translated, and GemRB was at most consulted as a behavioural reference.
* Licence: [MIT](LICENSE), the same as Temple+.

## What it does

1. Resolves resources like the IE engine: `override/`, then `chitin.key` to BIF / compressed BIF (`.cbf`, BIFC) on
   disk or in `CDn/` folders.
2. Renders the area background from WED overlay 0 + TIS (palette or PVRZ), plus the night variant if one exists.
3. Places it on the ToEE ground canvas and slices it into `art/ground/<AREA>/*.jpg`. A tile's top vertex is at
   canvas pixel `((v-u)*20 + 8428, (u+v)*14 - 4366)`.
4. Samples the IE search map at ToEE subtile centres and writes `.sec` files: Block / FlyOver bits and a footstep
   material from a guidance terrain table.
5. Turns WED wall polygons into ToEE clipping meshes (occlusion).
6. Writes `map.prp`, `mapinfo.txt`, start location, empty lighting/fog, path nodes, and the `.mes` lines to register
   the map.
7. **Doors**: each door is baked in its ARE default state, both in the art (WED door tile cells) and in the blocking
   (ARE closed/open impeded cells). It also writes `<AREA>_doors.json` and `ie_doors_<area>.py`, holding per door
   the portal position, lock, key, script, toggle point and the Block masks of both states. The open and closed tile
   variants go to `art/ground/<AREA>_doors/*.tga` (see "Doors" below).
8. Exports entrances, actors, containers, regions and animations as `<AREA>_objects.json` in ToEE tile
   coordinates, for later TC work.

## Usage

Requires Python 3.9+ with `numpy` and `pillow`.

    cd proto
    python3 ie2toee.py --game "<IE install>" --area AR1000 --out ../out --map-id 5900 --ground-id 900 \
        [--guidance guidance/<game>.json] [--closed-doors] [--preview]
    python3 verify_toee_output.py --out ../out --area AR1000      # paints the .sec blocking over the ground art
    python3 door_debug.py --game "<IE install>" --out ../out --area AR1000   # closed/open patch + impeded cells per door

Supported installs: classic Icewind Dale (palette TIS, `Data/`, `CDn/`, compressed `.cbf` BIFs) and
Icewind Dale: Enhanced Edition (TIS V2 pointing into PVRZ pages: zlib + PVR v3, DXT1/DXT5). Point `--game` at the
folder holding `chitin.key`. Area layouts, search maps, doors and strrefs match between the two; only the tile
storage differs. `compare_versions.py --a <classic> --b <EE> --area <AREA> --out <dir>` diffs one area between
two installs (art, search map, object counts).

Install into a **private** copy of ToEE (loose files in `modules/ToEE` override the .dat files):

    MES_SRC=<vanilla ground.mes/MapList.mes/map_names.mes extracted from your ToEE> \
        ./install_testmap.sh ../out <ToEE copy> AR1000

### Doors at runtime (Temple+)

`proto/runtime/ie_doors.py` is a Temple+ Python 2.7 module. Call `ie_doors.setup('AR1000')` when the map loads.
For each door it:

* places a stock ToEE portal (scaled down, since the IE art already shows the door) at the door position, which
  gives normal ToEE door interaction (click/use, locks, key);
* watches that portal. When it opens or closes, the door's tiles are switched between the IE open and closed
  impeded cells, and the matching WED tile variant is drawn over the ground.

This needs two small engine hooks, described in [ENGINE_HOOKS.md](ENGINE_HOOKS.md) with a patch
(`proto/runtime/templeplus-hooks.diff`). Without the hooks, use the MVP: the baked default state, and a portal
that only provides interaction.

### Developer tools

* `calibrate.py`: compares the converted blocking with a hand-made ToEE map of the same area (FFT alignment, then
  agreement statistics).
* `run_ingame.sh` + `ingame_probe.py` / `ingame_doors_probe.py` / `ingame_doors_smoke.py`: automated in-game tests.
  They need a Temple+ build with a small test harness that loads a save and runs Python from the `TP_AUTOLOAD` and
  `TP_AUTOEXEC` environment variables (not part of this repo). Runs in a private wine prefix.
* `ingame_overlay.py`: aligns a screenshot with the ground art and draws the blocking and door rectangles over it.

## Files

| file | purpose |
|---|---|
| `proto/iefs.py` | KEY/BIF/CBF/BIFC resource access, override, CD folders, case-insensitive paths |
| `proto/ieformats.py` | TIS, WED V1.3, ARE V1.0/V9.1 (incl. full door records), SR/HT/LM bitmaps, background renderer |
| `proto/ie2toee.py` | the converter |
| `proto/toee_sectors.py` | reads ToEE `.sec` files into a subtile grid |
| `proto/runtime/ie_doors.py` | Temple+ door runtime |
| `proto/guidance/*.json` | guidance format example (placeholders only) |

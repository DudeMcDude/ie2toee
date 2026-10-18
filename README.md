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

### IE-style dialogue window (Temple+)

`proto/ie_dialog_skin.py` rebuilds the IWD conversation window (EE or classic) from your install as a Temple+
dialog skin, selectable per module and per dialogue. It needs a Temple+ build with dialog skin support
(branch `feature/ie-dialog-skin` of DudeMcDude/TemplePlus). See [docs/dialog_skin.md](docs/dialog_skin.md).

### Creatures (prototype)

`proto/ie_creatures.py` surveys every creature an IE game places (area actors, rest spawns, `CreateCreature*` in
scripts and dialogs) and converts an area's actors into Temple+ critters. Classic IWD (CRE V9.0) and IWD:EE (V1.0) are
supported. Monsters map to ToEE models and template protos through an authored guidance table
(`proto/guidance/creatures_iwd.json`); NPCs are converted by formula (AD&D 2e → 3.5, following the WotC Conversion
Manual). `proto/runtime/ie_critters.py` spawns them in game. Rules, the adjudication list, the model coverage and
the free-model candidates are in [docs/creatures.md](docs/creatures.md).

### Spells (prototype)

`proto/ie_spells.py` surveys the spells an IE game uses and maps them to Temple+ spells. It reads SPL / PRO / EFF with
`proto/iespl.py`, and uses an authored guidance table of resref → Temple+ spell ids per flavour
(`proto/guidance/spells_iwd.json`). Converted NPCs get their spell lists and a custom Temple+ AI strategy. IE
`Spell` / `ForceSpell` / `ReallyForceSpell` / `ApplySpell` actions, `HaveSpell`, and a creature's own script on its
combat turn all cast through Temple+ (`proto/runtime/ie_spellrt.py`). The design, coverage, the SPL-ADJ adjudication
list and the plan for IWD-only spells are in [docs/spells.md](docs/spells.md).

### Developer tools

* `calibrate.py`: compares the converted blocking with a hand-made ToEE map of the same area (FFT alignment, then
  agreement statistics).
* `run_ingame.sh` + `ingame_probe.py` / `ingame_doors_probe.py` / `ingame_doors_smoke.py` / `ingame_creatures_probe.py` / `ingame_spells_probe.py`
  (`ingame_fields_test.py` dumps raw object fields): automated in-game tests.
  They need a Temple+ build with a small test harness that loads a save and runs Python from the `TP_AUTOLOAD` and
  `TP_AUTOEXEC` environment variables (not part of this repo). Runs in a private wine prefix.
* `ingame_overlay.py`: aligns a screenshot with the ground art and draws the blocking and door rectangles over it.

### Baked maps (prototype)
`proto/ie_bake.py bake` writes the converted objects of an area into the ToEE map files: creatures, items and
containers as prefab `.mob` files with stable permanent GUIDs, doors as portals in the `.sec` object lists
(saves then store only differences). `runtime/ie_bakert.py` finishes what the files cannot hold. The runtime spawner
stays available as a fallback. Format notes, WorldBuilder discrepancies, patrol buckets: [docs/mapfiles.md](docs/mapfiles.md).

### Items (prototype)

`proto/ie_items.py` surveys every item an IE game uses: creature inventories, area containers, stores, and
`GiveItem` / `CreateItem` in scripts and dialogs. It reads ITM / STO with `proto/ieitm.py` and maps each item to a
ToEE proto, either directly or as a base proto plus Temple+ item conditions. The mapping uses an authored guidance
table of resref → ToEE proto ids (`proto/guidance/items_iwd.json`), and the spells guidance for scrolls, potions and
wands. `convert` exports the IE inventory icons to ToEE TGAs on the player's machine. These go in the game's `data/`
folder, because the UI reads them before modules mount. At runtime (`proto/runtime/ie_itemrt.py`), converted
creatures carry their converted items, IE containers are filled, and IE stores open the ToEE barter screen. The
ITEM-ADJ adjudication list, coverage and open items are in [docs/items.md](docs/items.md).

## Player preview

`proto/ie2toee_preview.py` is a one-command build for players: it runs the map, spell, item, creature, dialogue,
dialog-skin and bake steps for the town area AR1000 on the player's own IWD or IWD:EE install, and assembles a ToEE
module overlay (`modules/ToEE`, `modules/ToEE_core`, `data/`) that it can also copy into a ToEE folder:

    python proto/ie2toee_preview.py --iwd "<IWD or IWD:EE>" --toee "<ToEE copy>" --tp "<preview Temple+>" --install

In game: `import iwd; iwd.go()` in the Temple+ console travels to the town. The player package (Windows) wraps it
in `preview/convert.bat` with `preview/requirements.txt`; `preview/README.txt` is the player README. The package
also needs the Temple+ build with the dialog skin and the door hooks (`proto/runtime/templeplus-hooks.diff`).

## Files

| file | purpose |
|---|---|
| `proto/iefs.py` | KEY/BIF/CBF/BIFC resource access, override, CD folders, case-insensitive paths |
| `proto/iebamfont.py` | classic BAM bitmap font -> pixel-outline TTF (fontTools) |
| `proto/ieformats.py` | TIS, WED V1.3, ARE V1.0/V9.1 (incl. full door records), SR/HT/LM bitmaps, background renderer |
| `proto/ie2toee.py` | the converter |
| `proto/toee_sectors.py` | reads ToEE `.sec` files into a subtile grid |
| `proto/runtime/ie_doors.py` | Temple+ door runtime |
| `proto/iegui.py` | CHU, MOS (V1/MOSC/V2) and BAM (V1/BAMC/V2) readers |
| `proto/ie_dialog_skin.py` | IE dialogue window exporter (Temple+ dialog skins) |
| `proto/iecre.py` | CRE (V1.0 / V9.0) and ITM readers |
| `proto/ie_rules.py` | AD&D 2e → D&D 3.5 conversion rules and adjudication options |
| `proto/ie_creatures.py` | creature survey + converter |
| `proto/toeedata.py` | reads the player's ToEE install (dat archives, protos.tab, meshes, spell enum) |
| `proto/runtime/ie_critters.py` | Temple+ creature spawner |
| `proto/guidance/creatures_iwd.json` | authored creature/model/item mapping (ids and labels only) |
| `proto/iespl.py` | SPL V1, PRO and EFF V2 readers (IESDP) |
| `proto/ie_spells.py` | spell survey, coverage, mapper and runtime map writer; SPL-ADJ options |
| `proto/runtime/ie_spellrt.py` | Temple+ spell runtime (spell lists, IE casting actions) |
| `proto/guidance/spells_iwd.json` | authored IE resref → Temple+ spell mapping per flavour (ids and Temple+ labels only) |
| `proto/ieitm.py` | ITM V1 (classic + EE), STO and ARE container-item readers |
| `proto/ie_items.py` | item survey, coverage, mapper and runtime map / icon / name writer; ITEM-ADJ options |
| `proto/runtime/ie_itemrt.py` | Temple+ item runtime (create, give, find, containers, stores) |
| `proto/guidance/items_iwd.json` | authored IE resref → ToEE proto mapping (ids and ToEE labels only) |
| `proto/toeemob.py` | ToEE object files: .mob and .sec object list reader/writer (byte-exact round trip), docs/mapfiles.md |
| `proto/ie_bake.py` | bakes converted creatures / items / containers (prefab MOBs) and doors (.sec portals) into a map |
| `proto/ie_patrol.py` | IE patrol survey (fixed loop / wander / conditional / reactive) and waypoint routes |
| `proto/runtime/ie_bakert.py` | Temple+ finalize for baked maps (conditions, spells, item conditions; once per object) |
| `proto/guidance/*.json` | guidance format example (placeholders only) |

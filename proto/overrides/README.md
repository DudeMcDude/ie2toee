# Per-map hand overrides

Hand fixes to converted maps that must survive a reconversion. One folder per game and area:
`overrides/iwd/<AREA>/` (IWD only for now; IE games reuse area names, so `ie2toee.py` only reads a folder it is given
with `--overrides`, which `ie2toee_preview.py` does for `overrides/iwd`). Code: `ie_overrides.py`.
The files hold only tile coordinates / bit masks and Temple+ path node data, no IE game data.

| file | what | applied |
|---|---|---|
| `*.json` (format `templeplus-dm-tile-edits`) | Temple+ DM "Save Tile Edits" file, dropped in unchanged (e.g. `map5012.json`) | map step (`ie2toee.py`): after the search map + `searchmap_fix` become tile flags, before the `.sec` files are written; so the path node generator, arrivals and exit icon anchors see the edited map |
| `pathnodenew.pnd`, `pathnodedist.pnd`, `clearance.bin` (any subset) | hand-culled nodes + Temple+ neighbour recalc / clearance (DM window) | copied into the map folder after the path node generator (`ie_pathnodes.py`), and again after `--engine-pathnodes`: the override wins. Temple+ loads `pathnodenew.pnd` before the generator's `pathnode.pnd` |

Tile edits: `flags = (flags & ~clear) | set` per tile (block subtile (sx,sy) = `0x200 << (sy*3+sx)`, flyover =
`0x40000 << (sy*3+sx)`, cover = `0x8000000`). Bits on door cells (the ones `runtime/ie_doors.py` switches) are dropped,
as the in-game tile editor protects them. Several files per area are fine: applied oldest `saved_utc` first, so the
newest wins per bit. A file whose `map_name` is another area is skipped. The map report (`<AREA>_report.json`,
`tile_edits`) counts the tiles applied, door bits dropped and "stale" tiles (the converted tile no longer matches the
file's `before`: still applied, but worth a look in game).

## Adding a map

1. In game (Temple+ with `dungeonMaster=true`): paint in the DM window's Sector Tiles section, press **Save Tile
   Edits**; it writes `<Saved Games>\TemplePlus\dm_tile_edits\IWD\map<id>.json`. Copy that file to
   `overrides/iwd/<AREA>/` (`map_name` in the file is the area).
2. Path nodes (optional, after the tile edits are in): cull / add nodes in game, run the neighbour recalc and the
   clearance generation, then copy `pathnodenew.pnd`, `pathnodedist.pnd` and `clearance.bin` from
   `<ToEE>\modules\IWD\maps\<AREA>\` to `overrides/iwd/<AREA>/`. Do not copy `pathnode.pnd` (the generator's file).
3. Reconvert (`convert.bat`). `python3 ie_overrides.py show` lists what is there;
   `python3 ie_overrides.py install-pathnodes --maps "<ToEE>/modules/IWD/maps"` copies the path node files into an
   existing install without a reconversion.

A path node override is tied to the map it was made on: if a converter change later moves walls or nodes on that
area, re-check it in game (and redo or delete the override).

Current overrides (Shai, 2026-11-11): AR1000 Easthaven (125 painted tiles; 204 nodes after culling 51 of the
generator's 255, 7564 links, clearance), AR1010 (21 painted tiles).

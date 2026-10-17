# Temple+ engine hooks for imported IE doors

In Infinity Engine areas the doors are part of the background art. The WED door tile cells have an alternate tile
for the closed state, and the ARE door record lists the search-map cells that are impeded in the open and the
closed state. ToEE doors are 3D portal objects instead. To keep the IE look, `proto/runtime/ie_doors.py` keeps the
art and swaps it at runtime. Stock Temple+ has no Python access to tile flags or ground art, so it needs two small
hooks. The patch is in [`proto/runtime/templeplus-hooks.diff`](proto/runtime/templeplus-hooks.diff), against
Temple+ master 03d72045: about 100 lines in `python_game.cpp` and `graphics/mapterrain.{h,cpp}`.

## 1. Sector tile flags

    game.tile_flags_get(loc) -> int
    game.tile_flags_set(loc, flags) -> bool

These are thin wrappers over `sectorSys.GetTileFlags` / `SetTileFlags`. The flags are the `.sec` `TileFlags`
(Block subtile bits `0x200 << s`, FlyOver bits `0x40000 << s`, with s = i + 3*j). Pathfinding and raycasts read
these flags directly, so a change takes effect at once. This was verified in game: with the door closed the path
fails; when it opens, the same `run_to` succeeds.

Notes:
* The changes live in the loaded sector only. They are not written to the save, so `ie_doors.setup()` must
  re-apply them after a map load (it applies each door's current portal state).
* If a map has a `clearance.bin` (Temple+'s precomputed pathfinding clearance), the clearance of the door's
  sector also has to be recomputed after a switch. Converted maps currently ship without one.

## 2. Ground overlays (runtime tile swap, the "faithful" mode)

    game.ground_overlay_set(id, texture_path, canvas_x, canvas_y, w, h)
    game.ground_overlay_remove(id)        # id = -1 removes all

This draws a texture in ground-canvas pixel space (the space of the 256 px ground JPG tiles) right after the ground
tiles in `TerrainSystem::Render`, so objects, clipping and fog are still drawn over it. The converter writes each
door's open and closed WED tile variants as one TGA patch per state (`art/ground/<AREA>_doors/<door>_{open,closed}.tga`),
together with its canvas rectangle. The runtime shows the patch of the current state.

Notes:
* Overlays are global (static). `setup()` clears them; a map-change hook should clear them too.
* Day/night: the patch comes from the day WED. A night patch could be added the same way.

## What works without the hooks (MVP)

The converter always bakes each door's default ARE state into the ground art and the `.sec` blocking. Without the
hooks, a TC can still place a portal for interaction (locks, keys, scripts), but opening it will not change the art
or the blocking.

## Possible upstream shape

A Temple+ PR could expose the two functions as above. A more general option is a "tile patch" object type that
the engine toggles together with a portal, so no polling is needed. The runtime currently polls every 250 ms.

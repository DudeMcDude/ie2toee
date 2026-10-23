# Design notes: importing Infinity Engine areas into ToEE / Temple+

## Goal
Let the co8 IWD / IWD2 TCs convert every area automatically from the player's own install (nothing derived is shipped):
TC ships code + per-area guidance JSON; player runs the converter on their IWD/IWD2 folder.

## Pipeline (offline converter, proto/)
1. Resolve resources: chitin.key -> BIF/CBF (CD folders), override/.
2. Render the background from WED overlay 0 + TIS (doors in their ARE default state); night WED (N) if present.
3. Place the image on the 66x71x256 ToEE ground canvas (centred); slice to `art/ground/<AREA>/yyyyxxxx.jpg`.
4. Tile mapping: canvas pixel of tile (u,v) top vertex = ((v-u)*20 + 8428, (u+v)*14 - 4366)  (exact, from Temple+
   TerrainSystem::Render + LocationSys::ToTranslation + WorldCamera; confirmed in game to within a few px).
5. Walkability: sample the SR map at the 3x3 subtile centres; IWD terrain table -> walk / Block / FlyOver + footstep material.
6. Occlusion: WED wall polygons -> vertical "curtain" meshes on their baselines -> clipping DAG (projects onto the polygon).
7. Objects (entrances, actors, doors, containers, regions, animations) exported as JSON in ToEE tile coords; turning them
   into .mob / protos / scripts is TC work (next milestone).

## Real-data results (IWD1, 2026-10-17)
- All 128 IWD areas resolve and parse; AR1000, AR2100, AR1001 converted and loaded in Temple+ (maps 5900-5902).
- Calibration against an independent hand-made World Builder conversion of the same area: 89.1 % subtile walk/non-walk agreement, 80.2 % of tiles
  agree on all 9 subtiles, after a (+7, +124) px art offset (that map's art placement vs our centred placement).
- In game: background, blocking and pathing work (party paths around the lake over the bridge, refuses lake targets);
  overlays of the converted .sec on screenshots line up with the art and with the PC's logged tile.

## Doors (2026-10-17)
- Converter: default ARE state baked into art (WED door cells: primary tile = open art, alternate = closed art) and
  blocking (ARE impeded cells of that state). Per door: portal position (centre of the impeded cells), Block masks
  for both states per ToEE tile, and TGA patches of both tile variants.
- Runtime (proto/runtime/ie_doors.py + two Temple+ hooks): a small stock portal per door. Opening or closing it,
  whether by script or by a PC using it, switches the blocking and the ground patch. Tested in game on a 3-door
  area: closed = unreachable; open = the PC walks through; closed again = blocked; art swaps each time.
  Smoke-tested on a 14-door area.
- Open: a saved game re-running setup() would create the portals again (it should find the existing ones);
  portals have no rotation or real geometry; closed doors now block pathing, so critters no longer auto-open
  them on the way (ToEE behaviour: they path through doors and open them); the 250 ms poll could become an
  engine callback.

## Travel (2026-10-24)
Travel regions of the converted areas become a poll in the runtime (`runtime/ie_travel.py`) driven by data collected at
convert time (`ie_exits.py` -> `ie_travel_data.py`); the preview converter also converts Easthaven's 14 interiors
(AR1001-AR1014). Details, limits and the in-game result: [travel.md](travel.md).

## Hard parts / open issues
- Semantics: IE "impassable" (SR 0 obstacles, SR 8 water/sidewall) vs ToEE Block vs FlyOver; hand maps paint obstacles as FlyOver.
  Choose per game in guidance; edge fringes / exits need per-area fixes (searchmap_fix rects).
- Animations (BAM), lighting (LM -> global.lit/lights), height map (HT),
  ambient sound, actors -> protos: not done. (Travel regions: Easthaven only, see docs/travel.md.)
- Pathing: no clearance.bin is generated yet (Temple+ falls back to tile-flag checks); generating one would also
  require recomputing it when a door switches.
- IWD2: ARE V9.1 offsets (+0x10) handled; CRE V9.0 and IWD2 TIS/WED specifics untested on real data.
- Legal: Temple+ MIT; gemRB GPL (reference only); never redistribute IE assets or converted output.

## Milestones
M1 (done) maps: art + blocking + clipping + start. M2 doors (done, see ENGINE_HOOKS.md) / regions / jump points. M3 actors/containers -> mobs.
M4 lighting/sound/animations. M5 batch convert all areas + guidance per TC + installer step for players.

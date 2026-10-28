# Travel between converted areas (Easthaven)

IE areas are joined by *travel regions* (ARE regions of type `travel`): walk into one and the party arrives at a named
*entrance* of another area. ToEE instead uses clickable **exit icons** (map-change scenery that walks the party to it
and jumps to a `jumppoint.tab` row), so the preview turns every travel region into one ToEE exit icon.

## Areas
| IE area | role | map id | ground id |
|---|---|---|---|
| AR1000 | Easthaven town (baked: NPCs, items, doors) | 5900 | 900 |
| AR1001-AR1014 | the 14 building interiors (map + doors only) | 5901-5914 | 901-914 |
| AR1015 (off AR1006), AR1016 (off AR1007) | side rooms (map, exits, actors, containers) | 5915-5916 | 915-916 |
| AR1200 (hill road off the town's map edge; exits To1000, To1201) | road (map, exits, actors) | 5917 | 917 |
| AR1201 (Orc Cave, dead end) | cave (map, exit, actors, 3 containers) | 5918 | 918 |

`ie2toee_preview.py` converts the interiors after the town, with `ie2toee.py` per interior (map id = 5900 + n, ground
id = 900 + n; the night ground id is +1000 as for the town). An interior that fails is skipped with a message and its
door stays a dead end. Snippets (`ground.mes`, `MapList.mes`, `map_names.mes`) of all converted areas are merged and
each interior's `ie_doors_<area>.py` is copied next to the town's.

## Convert time
* `ie2toee.py` gives every entrance an **arrival tile** (`arrival`, `arrival_moved` in `<AREA>_objects.json`): the
  entrance's tile if all its 9 subtiles are walkable, else the nearest fully walkable tile within 5 tiles, else the
  nearest tile whose centre and at least 5 of 9 subtiles are walkable; if there is none the tile is kept and a warning
  is printed.
* `ie_exits.py <workdir> --area AR1000:5900 ... --out ie_travel_data.py` collects, per converted area, the map id, the
  entrances (arrival tile + orientation) and the travel regions (polygon in ToEE tile coordinates, destination area
  and entrance). Exits whose destination area or entrance is not converted are listed and get `dest_map: 0`.
  Easthaven: 15 areas, 31 travel regions, 3 unusable (AR1000 -> AR1200, AR1006 -> AR1015, AR1007 -> AR1016).
  With AR1015/AR1016/AR1200/AR1201 converted: 19 areas, 36 travel regions, none unusable.
* **Anchors.** The party often cannot stand on or next to a region's outline: IE regions lie on door frames and the
  IE search map is coarser than ToEE pathing (a ToEE critter also stands on 1/3-tile slots, up to ~0.8 tile off a
  tile centre). `ie2toee.region_anchors` therefore gives every travel region an `anchor` tile: the fully walkable tile,
  reachable from the area start with every door open and not on or next to a door frame, nearest to the polygon
  (<= 6 tiles).
* **Exit icons** (`ie_exiticons.py`, run by `ie2toee_preview.py` after baking): per travel region with a converted
  destination, one static scenery object of proto 2011 (the standard ToEE exit icon; flags, radius and height copied
  from a vanilla icon) in the area's `.sec`, with `scenery_teleport_to` = a jump point id from 2000 up. The icon stands
  on the region's anchor tile (fallback: the polygon centroid if inside, else the nearest tile inside the polygon).
  Anchor placement (2026-10-25, to centre icons on doors): among the walkable tiles reachable from the area start
  (so on the party's side: outside for town doors, inside for interior exits), not on a door's own tiles and within
  6 tiles of the polygon, the one nearest the centre of the door tiles within 3 tiles of the region; without a door,
  nearest the polygon's centroid. Icons now stand ~1-2 tiles in front of the door's middle.
  `IE2TOEE_ANCHOR_DEBUG=1` prints each region's target and anchor.
  `rules/jumppoint.tab` gets one row per icon: destination map + the destination entrance's arrival tile. Being sector
  objects (not mobiles) the icons have no ids and are never duplicated by saves. The sector's objects are kept sorted
  by tile (row by row): the engine writes a sector's save diffs in that order and reads them back in file order, so an
  appended icon broke re-entering the town ("Cannot read diff footer") until sorted.
  Easthaven: 28 icons (14 town doors, 14 interior exits). No icon for the 3 unconverted exits, including the town's
  only map-edge exit (AR1000 -> AR1200 road).

## Runtime (`runtime/ie_travel.py`, Python 2.7 inside Temple+)
* Travel is **not polled** any more (2026-10-25): the old 250 ms poll teleported the party whenever a member stood in
  or near a region, e.g. right after a fight next to a door. Travel only happens when the player clicks an exit icon
  (the engine's own map change). Unconverted exits have no icon and no note.
* The poll still runs for map-change housekeeping: on arrival in a converted area without baked data (interiors) it attaches the area's doors (`ie_doors.start`); baked
  areas (the town) do that in `ie_bakert`.
* `start()` is idempotent: `iwd.go()` and the first heartbeat of every baked creature (`ie_bakert.first_heartbeat`)
  call it, and it does nothing if a poll ran in the last 2 s. The time event is saved with the game; after a load the
  restored poll **adopts** the fresh module state (the poll carries a generation number; a poll of another generation
  stops if a live poll exists, and takes over if nothing has polled for 2 s).

## Tests
* `proto/test_travel.py`: offline, mock Temple+ game (polling never teleports, door attach on arrival, load adoption,
  stale poll, `ie_exits`, `arrival_tile`, icon tile / anchor / jump points / no icon for unconverted exits). `python3 proto/test_travel.py`.
* `proto/ingame_travel_probe.py` via `run_ingame.sh`: town -> building door -> interior -> exit -> town in the real
  engine (screenshots + log); `IE2TOEE_BUILDING=AR10xx` picks the building. It opens the building's door, runs the party
  to the region's anchor tile and then to the interior's exit anchor.

* `proto/ingame_exiticon_probe.py` via `run_ingame.sh` (`IE2TOEE_BUILDINGS=AR1001,AR1006`): real mouse clicks on the
  icons (`CLICKICON`: `find_exit_icon.py` finds the blue icons in a screenshot and picks the wanted one from the icons'
  tile offsets), town -> interior -> town, arrival tiles, icon counts, then a save; `IE2TOEE_COUNT_ONLY=1` with
  `TP_AUTOLOAD` reloads it and counts again.

## Not done / judgment calls
* Interiors: actors, containers and stores are baked (ie2toee_preview.py, verified with proto/ingame_interior_probe.py: talk / container / shop). Still missing: area scripts, journal, info regions, ambient sound.
* AR1200/AR1201 (converted; AR1000 To1200 anchor (457,552), arrival FR1200 (462,548)). Known chokepoint, not widened:
  AR1200 To1201 icon (481,459) sits at the end of a 1-tile corridor (u=481, v=459-462, clearance 21-28) that a
  strict (PC-radius) path does not fit; the reachable end is (481,463). Fix options: move the anchor to (481,463) or
  widen those 4 tiles by hand. AR1201 Chest1 (489,435) and Chest2 (506,500) have no strictly reachable tile within 6
  tiles from FR1200 (Crate1 is reachable). AR1201 orcs are hostile and start combat on arrival.
* IE entrances have no facing in ToEE: the party arrives at the tile with default facing (`orient` is kept in the data).
* The icon is the stock ToEE map-change icon (same look for doors and map edges).

## In-game result (Temple+ under wine, 2026-10-24)
All 14 Easthaven buildings (AR1001-AR1014): town entrance -> door region -> interior (map 59xx, no bounce) -> exit
region -> town (map 5900), PASS. Two findings along the way: (1) with only the 0.8-tile outline test 9 of 14 doors could
not be entered (the party stops 1.3-2.5 tiles from the region) - hence the anchors; (2) a click on a blocked tile
(a door frame) does not move the party at all, so the anchor avoids door frames.
Proof (derived from the IE/ToEE data, local only): screenshots `town_before_door`, `interior_arrival`, `town_after_exit`
and the `TemplePlus.log` lines `IE_TRAVEL To1001 -> AR1001 FR1000 ...` / `IE_TRAVEL To1000 -> AR1000 FR1001 ...`.

## Exit icons in-game (2026-10-25)
Real mouse clicks: town -> AR1001 (arrived 481,491, entrance 482,492) -> town (481,423 vs 482,424); town -> AR1006
(486,485 vs 485,484) -> town (435,476 vs 436,477), PASS. Icons: 4 near the AR1001 door, 3 near AR1006, 1 in each
interior; after save and reload the same 3 (then 4), no duplicates, no diff errors. Screenshots `exit-icon-*.png`
(local only).
Re-placed icons (in front of the door middle), real clicks again: town -> AR1001 -> town, town -> AR1006 -> town PASS;
save + reload: 3 icons before and after. Screenshots `exit-icon2-*.png` (taken before the click).

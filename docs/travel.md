# Travel between converted areas (Easthaven)

IE areas are joined by *travel regions* (ARE regions of type `travel`): walk into one and the party arrives at a named
*entrance* of another area. ToEE has no such trigger (its jump points are map-level and one-way), so the preview
converts the regions to data and polls them from the runtime.

## Areas
| IE area | role | map id | ground id |
|---|---|---|---|
| AR1000 | Easthaven town (baked: NPCs, items, doors) | 5900 | 900 |
| AR1001-AR1014 | the 14 building interiors (map + doors only) | 5901-5914 | 901-914 |
| AR1200 (road), AR1015, AR1016 (interior side doors) | not converted | - | - |

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

## Runtime (`runtime/ie_travel.py`, Python 2.7 inside Temple+)
* A game time event polls every 250 ms. A party member counts as "in" a region if its position (tile + sub-tile
  offset) is inside the polygon or within 0.8 tile of its outline (2-point regions are segments). One member is enough:
  the **whole party** goes to the destination entrance's arrival tile with `game.fade_and_teleport`.
* **Disarmed** after start, after every map change and after every travel, until a poll sees the whole party outside
  every region of its map. Arriving next to a region or loading a save made inside one therefore never bounces. A
  4 s wall-clock quiet period after a travel covers the fade and map load.
* An exit whose destination isn't converted shows a **one-time** floating note "This exit (AR1200) is not in the
  preview" (once per exit and session) and the party stays.
* On arrival in a converted area without baked data (interiors) it attaches the area's doors (`ie_doors.start`); baked
  areas (the town) do that in `ie_bakert`.
* `start()` is idempotent: `iwd.go()` and the first heartbeat of every baked creature (`ie_bakert.first_heartbeat`)
  call it, and it does nothing if a poll ran in the last 2 s. The time event is saved with the game; after a load the
  restored poll **adopts** the fresh module state (the poll carries a generation number; a poll of another generation
  stops if a live poll exists, and takes over if nothing has polled for 2 s).

## Tests
* `proto/test_travel.py`: offline, mock Temple+ game (geometry, arming, no bounce, whole-party move, unconverted note,
  door attach on arrival, load adoption, stale poll, `ie_exits`, `arrival_tile`). `python3 proto/test_travel.py`.
* `proto/ingame_travel_probe.py` via `run_ingame.sh`: town -> building door -> interior -> exit -> town in the real
  engine (screenshots + log). Result: see the bottom of this file.

## Not done / judgment calls
* Interiors are empty: creatures, containers, shops, area scripts, journal, info regions, ambient sound.
* The road exit (AR1200) and AR1015/AR1016 only show the note. Converting AR1200 would make a first outdoor area.
* IE entrances have no facing in ToEE: the party arrives at the tile with default facing (`orient` is kept in the data).
* Real-time (not game-time) polling: travel does not happen while the game is paused.

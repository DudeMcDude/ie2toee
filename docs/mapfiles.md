# ToEE map object files and baking (MOB / SEC)

The converter can write converted IE objects straight into ToEE map files ("baking") instead of
spawning them from Python at run time. Code: `proto/toeemob.py` (format), `proto/ie_bake.py` (baker),
`proto/ie_patrol.py` (patrol survey and waypoints), `proto/runtime/ie_bakert.py` (in-game finalize).

Sources:
* **Co8 ToEE World Builder** (fan editor, C#; `github.com/13xforever/toee-world-builder`, the last
  commit is from 2013): `Helpers/MobHelper.cs`, `SecHelper.cs`, `WaypointHelper.cs`,
  `supplements/MOB property list.txt`. We used it as the main reference.
* **Temple+** (`gamesystems/objects/gameobject.cpp` Write, `objsystem.cpp` LoadFromFile /
  ReadFieldValue, `objfields.cpp`, `temple_enums.h`, `ai.cpp`) and **OpenTemple** (C# port:
  `MapSectorSystem`, `WaypointSystem`, `AiSystem`, `ObjectSystem`, `*Flag.cs`). We used these to
  cross-check WorldBuilder and fill in what it leaves out.
* **Stock data:** every `.mob` and `.sec` file in the ToEE dats. These were the final arbiter.

## Static (prefab) vs dynamic objects

| | prefab, static | prefab, mobile | dynamic |
|---|---|---|---|
| object types | portal, scenery, trap (without `OF_DYNAMIC`) | everything else: npc, container, every item type | any type created at run time (`obj_create`) |
| where it lives | object list at the end of a `.sec` sector file | one `maps/<map>/G_<guid>.mob` file each | only in the save |
| id | null in the file; a *positional* id (x, y, index in the sector list, map) is made when referenced | *permanent* GUID (kind 2), equal to the file name | permanent GUID, made at creation |
| save stores | `<sector>.dif`: changed fields only | `mobile.md`: changed fields only; `mobile.des`: destroyed ids | `mobile.mdy`: the whole object |

Engine rule (Temple+ / OpenTemple `IsStatic`): portal, scenery and trap are static unless
`OF_DYNAMIC` (0x2000) is set. Temple+ clears `OF_DYNAMIC` on objects it loads from a `.mob`.

**Stock data confirms this:**
* All 2332 sector objects are scenery (2142) or portal (190), and all have null ids.
* The 5846 MOBs are: armor 1475, npc 1270, money 1115, weapon 1092, food 299, ammo 195, generic 150,
  scroll 119, container 106, key 19, written 5, bag 1.

So the placement is:
* **Doors and scenery go in sectors.** Shai's guess was right.
* **Containers are MOBs, not sector objects** (106 stock containers, none in sectors).
* **Every inventory item is its own MOB**, linked to its holder both ways (the holder's inventory
  list and the item's `item_parent`).

## Object record (shared by .mob and .sec)

```
u32 0x77 | ObjectId proto | ObjectId id | u32 type | u16 prop_count | u32 bitmap[blocks(type)] | values
ObjectId (24 bytes) = u16 kind | u16 pad | i32 unused | 16-byte body
```

**ObjectId kinds:**
* 0 = null
* 1 = prototype (body: u32 proto number)
* 2 = permanent (body: Windows GUID, `bytes_le`)
* 3 = positional (x, y, temp id, map id; only made at run time)
* 0xFFFE = handle, 0xFFFF = blocked (in-memory only)

`LoadFromFile` requires a kind-1 proto id, and an object id that is either permanent or null (null
is allowed only for sector objects).

**Bitmap:**
* The bit for field *f* is `(f - 1) / 32`, `(f - 1) % 32`, counted over the global `obj_f` enum
  (405 entries including the section begin/end markers).
* Blocks per type: portal 4, container 4, scenery 5, projectile 5, weapon 7, ammo 7, armor 8,
  money 8, food 8, scroll 8, key 9, written 9, generic 9, bag 9, pc 11, npc 13, trap 13.
* `prop_count` equals the number of set bits in every stock file.

**Values** come in field-enum order over the type's sections: the base section, then item + subtype,
or critter + pc/npc.
* Int32 and Float32: 4 bytes, with no presence byte.
* Int64, String, Obj and arrays: `u8 present` first, then:
  * Int64: 8 bytes
  * String: u32 len, then len + 1 bytes
  * Obj: an ObjectId
  * Array: `u32 el_size, u32 count, u32 idx-map id (stale; written back as is), count * el_size
    bytes, u32 n, u32 index_bitmap[n]`. Arrays are **sparse**: bit *i* set means index *i* is
    present, and the data is packed in index order.

**`.mob`** is exactly one record. Stock files are named in lowercase, `g_<guid>.mob`. Temple+
`check_mobs` reports GUID/name mismatches and duplicates.

**`.sec` layout** (OpenTemple `MapSectorSystem`):
1. Lights: count, then 0x40 bytes each. Add +8 bytes if `flags & 0x10`, otherwise +0x2C if
   `flags & 0x40`.
2. 4096 × 16 tile bytes.
3. Roof list: an int; 1 means none, otherwise 0x400 bytes follow.
4. Section header 0xAA0000..0xAA0004. In order:
   * ≥1: tile scripts (count + 0x18 each)
   * ≥2: sector script (12)
   * ≥3: town map, aptitude, light scheme (12)
   * ≥4: sound list (12)
5. Object records.
6. A trailing u32 object count. The engine reads the count from the **end**, and the temp id is the
   index in the list.

**Sector file name:** `(sector_y << 26) | sector_x`, with sectors 64 tiles square. All 2332 stock
sector objects lie in the file this formula names.

**Round trip** (`toeemob.read_*` then `write_*`): all **5846 .mob and 1144 .sec files in the stock
dats are byte-identical** (6990/6990). This includes stale array idx-map ids and over-long array
index bitmaps, which are both kept verbatim. The baker re-reads and re-writes every file it produces
as a self-check.

### Fields used by stock objects

| object | fields set by stock MOBs |
|---|---|
| npc | `location`, offsets, `flags` 0x90004030, `rotation`, `radius`, `3d_render_height`, `dispatcher` -1, `permanent_mods` / `permanent_mod_data`, `critter_inventory_num` / `critter_inventory_list_idx`, `critter_money_idx`, `critter_teleport_dest`, `npc_flags`, `npc_standpoints`, `npc_waypoints_idx` (117 NPCs), `npc_ai_flags64` |
| inventory item | `location` (= holder's), `flags` 0x90001434 (`OF_INVENTORY` + flat / see / shoot-through / no-block), `radius`, `3d_render_height`, `item_parent` (holder GUID), `item_inv_location` (0.. pack, 200 + slot worn), `money_quantity` |
| container | `location`, offsets, `flags`, `rotation`, `container_inventory_num` / `container_inventory_list_idx` |
| portal (.sec) | `location`, offsets, `flags` 0x90004000, `rotation`, `radius`, `3d_render_height` |

Stock NPCs override almost nothing: there is one proto per NPC. Our NPCs share a few template protos,
so their MOBs carry the converted stat block as field overrides instead. Anything not set falls back
to the proto.

**Standpoints:**
* `npc_standpoints` is an Int64 array: day at [0..3], night at [10..13].
* Each standpoint is `mapId u32, pad, loc i64, offx f, offy f, jumpPointId i32, pad`.

**Waypoints** (`npc_waypoints_idx`, Int64 array):
* [0] = count. [1] is unused; the current waypoint is in `npc_waypoint_current`.
* Then 8 int64 per waypoint, read as 16 ints: flags (1 fixed rotation, 2 delay, 4 animate),
  x, y, offx, offy, rotation, 8 anim bytes, delay in ms, then unused ints.
* Walked by the AI when `ONF_WAYPOINTS_DAY` (2) or `ONF_WAYPOINTS_NIGHT` (4) is set
  (`AiSystem` 0x1005B950).

### WorldBuilder vs Temple+ / stock data: discrepancies

1. **Header.** WorldBuilder reads the 28 bytes after the version as "proto id + in-memory handle" and
   fills bytes 6–11 with random values. In Temple+ these bytes are the id's u16 pad and an unused
   i32: they are never read, and stock files have zeros there. `GenerateObjId` likewise randomises
   bytes inside the proto id body, which isn't needed.
2. **Sector file names.** WorldBuilder's `SecHelper.GetSecNameFromXY` puts **x** in the high bits
   (`secX << 26 | secY`, with x limited to 0..0x3f). The engine (OpenTemple `SectorLoc`) and every
   stock sector object use `y << 26 | x`.
3. **Arrays.** WorldBuilder treats the field bitmap as a string of flags and does not model array
   index bitmaps (sparse arrays) or the stale idx-map id. Writing them densely is accepted by the
   engine, but it does not round-trip stock files.
4. **Missing detail.** WorldBuilder does not document the positional id kind, the static/dynamic rule
   (`OF_DYNAMIC` only appears as a checkbox), or how saves store `.dif` / `mobile.md` / `.mdy`.
   These come from Temple+ / OpenTemple.
5. **Agreement.** Waypoint layout (`WaypointHelper.cs`), standpoint layout, bitmap block counts per
   type and field order all match Temple+.

## Baking (ie_bake.py)

```
ie_bake.py bake --area AR1000 --flavour IWD --specs <ie_creatures_ar1000.py> --items <ie_itemmap.py> \
   --doors <ie_doors_ar1000.py> --maps <converted map dir> --map-id 5900 --placement <cx,cy> \
   --toee <ToEE> --ie <IE install> --out <dir>
```

**Outputs:** `<out>/modules/ToEE/maps/<area>/`, a copy of the converted sectors with:
* **Creatures** as npc MOBs. Each gets:
  * the template proto, location, IE orientation as rotation, and day/night standpoints
    (`critter_teleport_dest` as in stock files);
  * `npc_flags`: KOS for hostile creatures, plus waypoints for fixed-loop patrollers;
  * the converted stat block: abilities, class levels as `stat_level_*` entries, hit dice, hp,
    natural AC, saves, alignment, gender, scale, name ids;
  * `critter_inventory_source` 0 (no random template gear);
  * the converted script id in the scripts array (dialog, heartbeat, first heartbeat, dying,
    enter/start combat);
  * the inventory list.
* **Items** as one MOB each. Each gets:
  * `item_parent`;
  * `item_inv_location`: worn in its natural slot (200 + slot), otherwise in the pack;
  * name / unidentified name, icon, worth and quantity;
  * item flags: the proto's flags, plus magical / identified.
* **Containers** as MOBs with their contents (stock practice). A lock sets `container_flags`
  LOCKED + `lock_dc`.
* **Doors** as portal objects appended to the `.sec` object list (proto 39, model scale 30, open /
  locked portal flags, lock DC). These **replace** the runtime-created doors.
* **Scenery:** none. The IE area art is baked into the ground; IE has no separate scenery models
  to convert (see open items).

`<out>/ie_bake_<area>.py` (runtime data) and `<out>/modules/ToEE/scr/py01099ie_baked.py` are also
written. The latter is a first-heartbeat script for baked critters that have no IE script.

**GUIDs** are `uuid5(ns, "ie2toee/<flavour>/<area>/<kind>/<key>")`. They are stable across
re-bakes, so saves made on a baked map remain valid after re-converting. Only local outputs contain
them, and they are derived from indices, not names.

**What stays at run time** (`ie_bakert.py`, on the first heartbeat after the map loads; one area
pass per load):
* Creature conditions, spells and AI strategy, and the hp correction (the engine adds Con / racial
  bonuses).
* Item wielder conditions: their argument count is only known to the engine's condition table.

Each object is finalized once: a marker (`npc_pad_i_3` / `item_pad_i_1` = 0x1E2B0001) is saved with
the object. The session-only AI strategy table is refilled on each load. The pass also calls
`ie_doors.start(area)`, which attaches to the portals already on the map and re-applies tile
blocking and ground patches from each portal's saved state.

**Fallback:** the runtime spawner still works (`ie_critters.spawn_area`, `ie_itemrt.fill_containers`,
`ie_doors.start`): install the plain converted sectors and no MOBs. `ie_doors.start` now creates
only the doors that are missing, so runtime mode no longer duplicates doors on reload either. The
old always-create `ie_doors.setup` remains for the door probes.

## Patrols (ie_patrol.py)

For every placed creature, the survey walks its scripts in IE order (override, specific, class,
race, general, default; the actor's slots, falling back to the CRE's) and buckets its movement:

| bucket | rule | ToEE |
|---|---|---|
| fixed_loop | ≥ 2 MoveToPoint-family targets, all in blocks whose triggers only read the creature's own state (no trigger, `True`, its own timers / LOCALS counters, `NearLocation`) | baked as waypoints (route in block order, 3 s delay each), `ONF_WAYPOINTS_DAY \| NIGHT`; the runtime's `MoveToPoint` steps aside for such creatures |
| wander | `RandomWalk` / `RandomWalkContinuous` / `RandomFly` / `Wander`, with no fixed targets | script runtime |
| conditional | point moves gated by world state (See, globals, area, time, ...) or a single target | script runtime |
| reactive | only `MoveToObject` / `RunAwayFrom` / `EscapeArea`-style movement (combat, flight) | script runtime |
| none | no movement | |

**Counts** (all placed creatures in all areas):

| | placed | fixed_loop | wander | conditional | reactive | none |
|---|---|---|---|---|---|---|
| classic | 2168 | 48 | 451 | 42 | 1304 | 323 |
| EE | 3269 | 111 | 1039 | 69 | 1510 | 540 |

AR1000 has six fixed-loop patrollers in both flavours (routes of 2, 2, 10, 2, 14 and 14 points).
Their scripts are the "movement list" pattern: a LOCALS index plus a timer, ping-ponging over the
points.

## In-game results (AR1000, classic and EE)

**Setup:** Temple+ dist-iedlg, with the dialog skin `iwd` for classic and `iwdee` for EE. Private
overlay, prefix and display. Probe: `proto/ingame_bake_probe.py`; helper: `bake_ar1000` in the local
test script.

**Run 1** teleports to the baked map. The engine log shows `ReadMapMobiles: Loading 74 map mobiles`
for classic (70 for EE). No Python object creation happens. Results:
* **Objects:** all baked creatures are present (classic 24/24, EE 23/23); 25 / 23 objects are
  finalized once by the area pass.
* **Stats and gear** read back as converted. Examples:
  * an 11th-level fighter: hp 114/114, AC 21, the converted abilities, plate + shield +1 worn, a
    bastard sword in the pack;
  * townsfolk: level 1 with dagger, garb and boots worn;
  * KOS flag off, and the dialog / heartbeat script ids set.
* **Dialogue:** an NPC's dialogue opens in the IE dialog skin, and its script runs (journal entry,
  LOCALS).
* **Door:** opening a baked door toggles the portal, and the door's blocking subtiles go from 23 to 0
  with the open-state ground patch drawn.
* **Patrol:** a 14-point patroller walks its waypoints (tile positions sampled every 5–10 s:
  527,458 → 503,441 → 484,430 → 483,420). Two others cycle short routes.
* **Duplicates:** census before saving shows one portal per door spot (14 portals near the 14
  doors) and no duplicate creature on any spot.

**Run 2** is a new game process that autoloads the save from run 1:
* `LoadGame returned true`.
* **No duplicates:** the census is the same (one portal per door spot, all baked creatures present,
  none duplicated).
* **State persisted:**
  * the opened door is still open, and its tiles are unblocked again because the area pass
    re-applies them from the portal state;
  * the damaged NPC still has hp 109/114;
  * the finalize markers were kept (0 objects re-finalized, so no doubled conditions);
  * the patrollers are where they were when saved;
  * talking to the same NPC again starts at its "talked to before" state (classic).
* **Patrols after reload:** engine log lines `pathed successfully` show they continue walking. One
  patroller keeps failing to path to its next waypoint, which sits next to the party at the door.

**Screenshots (local only):**
* `out/ingame/bake1_{IWD,IWDEE}/`: start, talk1–4 (and a per-NPC look shot), door_closed, door_open, patrol1–2.
* `out/ingame/bake2_{IWD,IWDEE}/`: reloaded, reloaded_door, reloaded_patrol, reloaded_talk (classic).

## Open items

* **Scenery:** IE areas have no separate scenery models to bake (animations and the background are
  ground art). The `.sec` writer supports scenery objects if a mapping is added later.
* **Waypoint delays:** fixed at 3 s. The IE timer lengths (`SetGlobalTimer` in the movement-list
  blocks) are not read yet.
* One AR1000 patroller (a 10-point route) stays at its first waypoint; possibly an unwalkable
  converted tile. Not investigated.
* The `.mdy` of a save with no dynamic objects logs "Couldn't read the object header" on load. This
  is harmless and probably happens with stock saves too.
* MOB `flags` omit `HEIGHT_SET` / `RADIUS_SET`, so the engine computes radius and height. Stock MOBs
  store them.
* `permanent_mods` (the stock editor saved computed condition hashes) are not written; conditions
  come from the proto plus finalize.
* Container baking is implemented, but AR1000 has no IE containers, so it is only checked offline
  (round trip).
* In the EE reload run, the probe's later steps (including talking after the reload) did not fire,
  although the game kept running. The same check passed in classic. This is a harness issue to look
  at.
* Probe harness: a save made by a probe pickles its pending step events. Steps now go through
  `proto/ie_probe_stub.py` (installed in `scr/`), so a later run can load the save; stale steps are
  dropped by a run token.
* The test harness's in-process `game.loadgame` from a Python time event leaves the AI stopped. The
  save/reload test therefore restarts the game and autoloads the save (a fresh process), which is
  the stronger test anyway.

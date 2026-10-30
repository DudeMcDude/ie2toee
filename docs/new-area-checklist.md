# New module / area checklist

Template for adding a game (IWD, IWD2, later BG) or a single area to ie2toee.
Every item is something that bit us during the IWD/IWD2 conversions.

## 0. Setup
- [ ] Guidance file `proto/guidance/<game>.json` and map-id/prefix block in `ie_areas.py` (IWD 59xx, IWD2 `I2` 5950+). Why: per-game map names and ids must not collide.
- [ ] Reader handles the game's file versions (CRE V1/V2.2, ITM V2.0 ability stride 0x38, BCS object layout). Why: wrong strides silently corrupt items/scripts.
- [ ] Keep the game's native rules where they exist (IWD2 3e stats); preserve difficulty flags/gates in creature data.

## 1. New-game start
- [ ] Start point from the game's `STARTARE.2DA`, not the first area's entrance. Why: IWD started mid-town, IWD2 top-left corner.
- [ ] MapList `Flag: NEW_GAME_START` + `NewGameX/Y` point at that tile (read by `mapsystem.cpp`).
- [ ] Start tile is walkable and connected to the rest of the map (see 2).

## 2. Navigability
- [ ] Run `route_check.py` (offline, `ROUTECHECK_CLEAR`) from start/arrival tiles to every exit, container and NPC. Why: Targos gangway trapped the party at start.
- [ ] Look for pinches: gangways, bridges, stairs, cave mouths, dock planks. Check against the nominal PC radius (~25, needs ~3 subtiles clearance).
- [ ] Widen only manually and minimally (`searchmap_fix`, shave a few cells at the narrowest point). `widen_narrow` stays off. Drop widenings that don't help (AR1200's 9 cells).
- [ ] Engine path-node bake: `pathnode_bake.sh` / `--engine-pathnodes`, then `pathnode_stats.py`: no islands, no one-way links, entrances/anchors on roomy tiles.
- [ ] In game: `ingame_route_check` probe, ALT path-preview screenshots + `debug.pathlen`. Long winding clicks can fail (engine gives up); test a closer click and note it, or add path nodes.
- [ ] DM sector tile editor edits actually persist/apply on this map (blocking, flyover, subtile brush).

## 3. Exit icons / travel
- [ ] Icon (proto 2011) sits next to its door; only a small inward nudge (`anchor_fix`). Not on door frames.
- [ ] Cramped check: icon/arrival not in a spot too tight for the party; not within 2 tiles of an arrival tile (party hides it).
- [ ] No spawn standing on the icon/ramp tile (`spawn_fix`, e.g. I2AR1000 goblin).
- [ ] Travel works both directions (`ingame_exiticon_probe.py`, `ingame_travel_probe.py`, parent area syntax `AR1015:AR1006`).
- [ ] Test outside combat: Temple+ ignores icon clicks during combat (end fights with kos, below).
- [ ] Arrival landing checked (I2AR1002 is ~7 tiles off).
- [ ] Installer copies maps where the module needs them (modules/IWD vs modules/ToEE) and the new maps are really in the zip.

## 4. Creatures
- [ ] Vanilla ToEE portraits only; per-NPC mapping. Orcs/orogs: Pintark/Tuelk (6470/6480).
- [ ] Creature-only weapons (`001dXy`, goblin bows) mapped to ToEE stand-ins, else they fight unarmed (nonlethal).
- [ ] IE STATE_DEAD creatures killed at load/bake finalize (corpses).
- [ ] Name ids clear of item description ids (IWD2 items 22000-27503 -> creature names 28000+). Why: goblins labelled "Scroll".
- [ ] Variant names where tlk names collide (Axe Goblin, Goblin Archer); ignore death vars that don't match the actor.
- [ ] Feats: Weapon Finesse -> Temple+'s single feat; Improved Critical from the equipped weapon.
- [ ] Monsters on PC-body meshes get worn ToEE gear within a natural-AC budget; missing bodies get a documented stand-in (beetle = giant tick).
- [ ] Kegs/breakable scenery -> NPC critters with barrel mesh (11013); check click targets attack, not a dialogue.

## 5. Scripts
- [ ] BCS decode rate (`iescript.py`): IWD2 2489/2493; recheck the other game is unchanged.
- [ ] Per-area/actor script ids unique (actors 1300+ clear of baked objects; dialogue 1500+100i). No duplicate ids across areas.
- [ ] Shared area script (1099) not overwritten by each area; give each area its own.

## 6. Dialogue / journal
- [ ] DLG -> ToEE dlg for every NPC with a DLG (`--strip-directions` for IWD2 voice notes); `ingame_dialogue_probe.py`.
- [ ] List unmapped triggers/actions (cutscenes, item taking, multi-speaker lines) and note them; no crash on unparsed actions.
- [ ] Journal/quest ids in a free range (IWD from 1, IWD2 150-199); logbook text <=250 chars (long text hangs), ASCII-folded.
- [ ] Empty description .mes is not written (hangs the game).
- [ ] Dialogue skin: `ie_dialog_skin` falls back to classic skin on old installs; check it renders.

## 7. Containers, stores, info regions
- [ ] Containers placed on their IE polygon centre (`container_fix`) so they match the art; reachable (test points not on walls).
- [ ] Loot/barter open (`ingame_interior_probe.py`); save/reload keeps state (`ingame_persist_probe.py`).
- [ ] Info regions written and hover/click works (`ingame_inforegion_probe.py`).

## 8. Clipping
- [ ] WED wall polygons -> `maps/<AREA>/clipping.cgf/.cif` + `art/clip/<AREA>/*.dag`.
- [ ] In game `debug.clipping(1)` (clip-debug build): mesh covers buildings to the roof line; PC behind a building is hidden. Note gaps in IWD's own polygons.

## 9. Testing tips
- [ ] Stop fights with `import __main__; __main__.cheats.kos = 0` (not by deleting creatures); `kuf()` kills unfriendlies.
- [ ] `C` toggles combat; ALT shows path preview.
- [ ] Screenshots with a PC placed in the scene; CSHOT for cursor shots.
- [ ] Kill only your own game processes.

## 10. Release
- [ ] No game data in commits or zips (IWD/IWD2 files, tlk text, art). Run `/workspace/leakscan.sh` on staged files before every push.
- [ ] Push only to DudeMcDude forks; never upstream; Codex never pushes.
- [ ] Releases as drafts; Shai publishes. Release notes and the in-zip README current.
- [ ] Temple+ build from the fork's `build/*-ci` branch; source diff + `IE-PREVIEW-SOURCE.txt` updated.
- [ ] Fresh install from the zip + bat tested once.

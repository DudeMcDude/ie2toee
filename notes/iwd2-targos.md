# IWD2 first experiment: AR1000 (Targos docks)

- Source: player's own GOG installer (v2.01_fixes), extracted with innoextract to a local dir outside the repo.
- `ie2toee.py --game <iwd2> --area AR1000 --map-id 5950 --ground-id 950 --guidance guidance/iwd2.example.json --preview`
  converted with no code changes: 25 sectors, 35462 walkable subtiles, 182 wall polygons -> clipping, 6 doors with
  patches, 32 path nodes, start tile (489,425). Objects: 7 entrances, 56 actors, 25 containers, 17 regions, 9 anims.
- Map ids 5950+ / ground 950+ reserved for IWD2 (IWD uses 5900-5918).
- Not done yet: creature/item bake (CRE V2.2 untested), exit icons, in-game load test in a separate overlay.

## Session 2 (2026-10-29)
- Map folders take a per-game prefix (guidance `map_name_prefix`, IWD2 = "I2"): IWD2 AR1000 -> I2AR1000, so it can sit
  next to IWD's AR1000. ie_exits.py prefixes travel destinations the same way. Empty prefix = old behaviour.
- guidance/iwd2.json: chitin.key size/sha1 (GOG 2.01), prefix, map 5950 / ground 950 for AR1000.
- iecre.py parses CRE V2.2 (IESDP cre_v2.2): compat 2e-style fields (thac0 = 20-BAB, AC = 20-AC3e) plus `rules3e`
  (BAB, Fort/Ref/Will, per-class levels, feats, skills). ie_creatures.py uses the native 3e levels/BAB/saves when
  present (no level ability bumps, no 2e save conversion). V2.2 spells are 2DA-indexed and not resolved yet.
- AR1000: 56/56 actors convert (goblins -> 14186, townsfolk/soldiers class-based); difficulty gates: none found
  (no EFDEL-style DestroySelf scripts on this map); portraits fall back to the vanilla proto portraits.
- In game (separate overlay ~/games/ToEE-iwd2 + prefix ~/.wine-toee-iwd2, dist-inforeg, save slot0101): pathnode
  bake OK (25 clearance sectors), creatures baked, party walks; goblin attack starts combat at the docks.
- Exit icons: none placed yet: every AR1000 exit leads to an unconverted area (AR1001-1006, AR1100).

## Session 3 (2026-10-29): Targos interiors + AR1100
Maps 5951-5956 = I2AR1001-1006, 5957 = I2AR1100 (outdoor). Bake outputs named by map_dir; exiticon probe takes IE2TOEE_PARENT.
In-game (dist-iedlg/inforeg, slot0101): real-click round trip PASS for AR1006 and AR1100; AR1005 enter PASS (click), exit FAIL;
AR1001/1003 travel only via scripted icon use (AR1003 both ways PASS, AR1001 back FAIL: combat on arrival); AR1002 exit FAIL; AR1004 enter FAIL.
Open: click misses on some icons, combat-on-arrival blocks exit, kegs/Guthewulf no model, 00ax1h05 unmapped, item icons skipped, door-patch light square not looked at.

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

## Session 4 (2026-10-29): non-working exit icons
In-game diagnosis (proto/ingame_icon_diag.py, IE2TOEE_DIAG_USE=1: stand next to each icon, use it by script):
every IWD2 icon travels when no combat is running; all jump ids / map ids / arrival tiles are right.
Root causes: (1) combat: Temple+ ignores exit-icon clicks in combat (mainloop.cpp: returns if the leader is in
combat mode) and the use goal never runs in turn-based mode; IWD2 interiors AR1001/1002/1004/1005 hold hostile
goblins that start combat on arrival (genuine game content). Hiding critters (OF_OFF) does not end a started fight.
(2) cramped icon: I2AR1000 To1004 sat on a 1-tile diagonal ramp where no party member (radius 25) fits within use
range; the engine finds no path (can_find_path_to_obj 0 from every entrance). The FR1004 arrival was on the same ramp.
Fix: ie_exiticons moves an icon with no use room back along walkable tiles (<= 5 steps) to the nearest tile with room
(2003: 540,495 -> 537,492), moves cramped jump points the same way (2010: 539,494 -> 535,490), and is re-runnable.
Probe: destroys critters + ends the turn (space) when a fight is running; IE2TOEE_TOL arrival tolerance.
IWD AR1200 To1201 (2034): offline the icon (481,463) has room (6 tiles) and its arrival fits, so not this cause;
in-game test still to do.
The in-game re-test after the fix could not run: wine is no longer installed on the box (wine: command not found).

## Oct 29: probe uses the "kos" cheat instead of destroying critters
`cheats.kos = 0` (vanilla console cheat, Python `cheats` object in __main__) sets the AI "NPCs may fight" global
0x102BD4E0 to 0 -> ai.cpp forces every NPC fight status to none. Run: all I2AR1001-1006 + I2AR1100 both ways PASS by real
click except I2AR1004 (critters left visible: a Targos NPC stands between the party's start tile and the cramped
AR1004 door icon 2003, so neither the click nor scripted use reaches it). With IE2TOEE_HIDE=1 (hide, no destroy)
AR1004 passes both ways by real click. Worth a look: a townsfolk NPC can block that cramped door in normal play.

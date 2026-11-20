ICEWIND DALE IN THE TEMPLE OF ELEMENTAL EVIL ENGINE - PLAYER PREVIEW (2026-11-20b)
=================================================================================

IMPORTANT: PYTHON 3.9 OR NEWER MUST BE INSTALLED
  The converter is a Python program. Before you start, install Python 3.9+ from
  https://www.python.org/downloads/ and, in the installer, tick "Add python.exe to PATH".
  Without it convert.bat stops with a message. You also need your own Icewind Dale or Icewind Dale: EE.

PROLOGUE PLAYTEST UPDATE (2026-11-20b)

Easthaven now plays its English opening movie, narrated prologue and avalanche when converted with the media tools. Targos plays its existing intro followed by its narrated prologue. The converter reports missing opening entries and looks for RAD Video Tools on PATH.

The Easthaven party reached Kuldahar Pass with all six sidequests. In Targos the autoplayer installs Jorun's wheel, pursues the remaining siege attackers, and can finish fallen raiders that the area script still counts as alive. Town defenders can leave initiative after the scripted victory. The same party completed all sixteen sidequests and received Ulbrec's assignment to Shaengarne across checkpoint replays with combat assistance enabled.

Extract the ZIP for your game to a fresh folder. Before running its conversion batch file, put ffmpeg.exe and ffprobe.exe on PATH or in a media-tools folder next to the batch file. Include any DLLs required by your FFmpeg build. For IWD, install RAD Video Tools or put radvideo64.exe on PATH or in media-tools. You can also set RADVIDEO to its full executable path. IWD2 already supplies its intro in Bink format. Rerun conversion against your own games and start a new campaign to see the opening.

Known issues include unreachable containers at the Snowdrift Inn and in several Targos interiors, shared stock portraits on several Targos residents, and a possible delay after Hedron's dialogue. The previously reported native siege crash did not recur in this playtest.

PREVIOUS PREVIEW (2026-11-20)
--------------------------------
The Kuldahar Pass Hermit has a new portrait. More Easthaven townsfolk and squirrels use the commissioned portrait set.

Small Infinity Engine loot piles now put one or two item stacks directly on the ground. On the Targos docks you can pick up dropped weapons, gold and ammunition individually. Larger piles and heaps with scripts, traps, locks or keys retain their containers.

Hover over a painted barrel, chest or other container to outline its original shape. Hold Tab to outline painted containers that still have items. Click the shape to use it. Locks, traps, scripts and inventory still belong to the original container. The new engine reads these shapes from the converted maps.

Extract to a fresh preview folder and rerun the converter against your own game files. Launch the included TemplePlus.exe for manual play, or use the chapter autoplayer. For the clearest comparison with an earlier conversion, enter the map in a fresh game.

The Easthaven orc cave uses a 12-tile ally alert distance. The chapter autoplayer regroups and heals after the entrance fight. Reconverted weapons can be shown in the orcs' hands.
The chapter autoplayer shows its current goals in the upper right. Dialogue and cutscene timing and combat movement have also been revised.

PREVIOUS PREVIEW (2026-11-17)
--------------------------------
  The chapter autoplayer walks between objectives, follows the action with the camera,
  and checks sidequest outcomes. Its PCs receive a combat boost and heal between fights.
  The route includes six Easthaven errands on the way to Kuldahar Pass. The converter
  fixes quest rewards and item handling used along the route.
  Extract this preview to a fresh folder and rerun the conversion command below against
  your own game files to pick up the converter changes. See Autoplayer\README.txt for
  the chapter commands and combat assist setting.

PREVIOUS PREVIEW (2026-11-15)
--------------------------------
  Still an early-preview, AI-assisted experiment: not a playable or polished conversion.
  * The prologue now ends in AR2000 Kuldahar Pass (map 5051): Hrothgar greets the party in Winter's Cradle on a
    new game, the posse / caravan / Pomab steps work, and "Let us be off" plays the departure and the avalanche.
  * IE script fixes: Dead("name") reads the death variables (a dying creature sets SPRITE_IS_DEAD<name>, which
    fixes Apsel's wolf quest), BitGlobal modes, Continue() ordering, LOCALS names, PartySlotN,
    StartDialogueNoSet.
  * IE variables (globals, area and actor locals, timers) are kept in a file next to each save (<save>.iev)
    instead of a fixed block of ToEE global slots, so there is no limit on their number.
  * Bundled Temple+ 0.2.98 (see TemplePlus\IE-PREVIEW-SOURCE.txt): the info-point magnifier cursor no longer
    leaves a stale cursor (e.g. the portrait drag icon) on screen.
  * New: an autoplayer (Autoplayer\README.txt) that starts a new game and plays the prologue to AR2000 by
    itself, for testing. It takes over the game window while it runs.
  * Saves: start a NEW game. Older saves load, but their quest/dialogue variables start from zero because of the
    new variable store.
  * Pathing: the engine path node bake (clearance.bin and engine-relinked path nodes) still runs only in the
    developer's Linux/Wine setup, not in convert.bat; Windows converts use the generator's nodes, plus shipped
    per-map overrides (AR1000). If you fix tiles with the DM Sector Tiles editor ("Save Tile Edits") or make a
    better path node set for a map, please send the files (%USERPROFILE%\Saved Games\TemplePlus\dm_tile_edits\
    <module>\map<id>.json, and the map's pathnodenew.pnd / pathnodedist.pnd / clearance.bin) with the map id,
    so they can ship as overrides.

EARLIER (2026-11-11b)
--------------------------------
  * Per-map overrides: hand tile edits and culled pathnodes now survive a reconvert. After the generator
    runs, the override wins. This preview includes AR1000 Easthaven (map 5012): 125 tile edits and a culled
    path node set (pathnodenew.pnd / pathnodedist.pnd / clearance.bin, 204 nodes), and AR1010 (map 5022):
    21 tile edits. Door cells are protected so a saved block cannot seal a door. Fresh installs get these
    from convert (baked into the .sec files, and the path node files are copied into
    modules\IWD\maps\AR1000). Existing playtest installs already have the files; a reconvert is needed
    for the exit-icon change below, and to bake the tile edits into .sec for installs that do not have the
    Saved Games tile-edit overlay.
  * Exit icon for Churin's house (AR1000 -> AR1011, To1011): the gold ToEE exit icon had been planted on a
    closed door tile, because the whole-tile walk search never reached the south-west pier (the approach is
    partly walkable stairs/planks) and fell back to the doorway centre. A sub-tile flood-fill fallback now
    places it on the pier at (532,496). Needs a reconvert. Not yet re-checked in game after the fix.
  * Bundled Temple+ 0.2.97 (see TemplePlus\IE-PREVIEW-SOURCE.txt). The magnifier cursor for IE info points
    (signs and the like) could stay on after leaving the region: the hover flag was only updated on a plain
    mouse move inside the game view. Leaving via the party bar, scrolling the map under a still mouse,
    dragging, or opening a radial menu could leave it stuck until you moved again in the game view. Each
    frame now re-checks that the mouse is over the game view, no radial menu is open, and the region is
    still under the cursor. Drop-in: no reconvert for the cursor fix. Not yet re-checked in game after
    the fix.
  * Saves: the map ids are unchanged (5012-5030), so 2026-11-10 and 2026-11-11 saves should still load. Saves
    from before 2026-11-10 (old 59xx ids) don't work; start a NEW game. Temple+ 0.2.97 can be dropped in
    without a reconvert. For the Churin exit icon, and to bake the tile/pathnode overrides into a fresh
    install, reconvert.

EARLIER (2026-11-11)
--------------------------------
  * Bundled Temple+ 0.2.96. The DM Sector Tiles editor has "Save Tile Edits". Only the tiles you painted by
    hand are saved, as JSON in %USERPROFILE%\Saved Games\TemplePlus\dm_tile_edits\<module>\map<id>.json,
    and they are re-applied when a sector loads. Door cells set by scripts are protected from painting and
    saving.
  * Equipped inventory icons: the IE transparent colour (green) no longer shows behind items in the paper-doll
    slots. The bag view was already fine; the equipped slots ignore alpha. New converts write clean icons. For an
    existing ToEE copy, run  fix_inventory_icons.bat "C:\GOG Games\ToEE-IWD"  instead of a full reconvert.
  * IWD:EE older than 2.5 (no ui.menu / bgee.lua): the converter now stops with a message asking you to update
    IWD:EE and run convert.bat again (no special flag). It no longer falls back to the classic dialogue window.
    Classic Icewind Dale is unchanged.

EARLIER (2026-11-10)
--------------------------------
  * Town maps (mini maps): every converted area has a town map built from its own background, and the town map
    list names the IWD places (Easthaven, the Snowdrift Inn, Pomab's Emporium...) instead of ToEE ones.
  * IE dialogue window: the speaker's side portrait is shown only when a real big portrait exists (no blurry
    upscaled small portrait or placeholder head; the slot stays empty otherwise). The IWD dialogue scrollbar
    is fixed (it showed a column of small button tiles).
  * Movies and slides can be skipped with Space, Enter, Esc or a mouse click. A slide whose sound fails to play
    now ends after 3 seconds instead of waiting for a key, and a small in-game notice asks you to report it.
  * Bundled Temple+ 0.2.92.
  * The converted maps got new map ids (5012-5030); saves from before 2026-11-10 don't work.

EARLIER (2026-11-07)
--------------------------------
  * Commissioned portraits, batch 8 finished (art generated via Gemini): a redone Quimby, the scrimshaw
    apprentice, Kuldahar, Reghed and Ten Towns townsfolk pools, 16 elite or boss portraits and 34 location-themed
    monster portraits, with mirrored copies; about 300 IWD monster variants now use them.

EARLIER (2026-11-04)
--------------------------------
  * Summon spells: IE summoning spells now conjure their creatures (picked by caster level, as in IE), using
    vanilla ToEE or Co8 creatures as stand-ins where the IE creature has no ToEE match (e.g. dire rats, efreeti,
    elementals); the summon hexagram effect plays when they appear.
  * Spawned creatures run their own IE scripts and dialogue; cutscenes can pan the camera, hide the GUI, and
    show speech bubbles for floating text. Dialogue-only cutscenes simply start the dialogue.
  * Commissioned portraits, batch 8 part A (art generated via Gemini): Easthaven NPCs (Pomab, Accalia,
    Hildreth, Erevain, Elisia, Jhonen, Gaspar, Grisella, Apsel, Old Jed, Churin), Pomab in his tower, the
    Cyclops, the Cryshal Sentry, siege survivors, a Tempus acolyte and townsfolk pools (fishermen, fishwife,
    dockworkers, Tempus priest/priestess) with mirrored copies. Quimby keeps a stand-in for now.

EARLIER (2026-11-02)
--------------------------------
  * Cutscenes: black letterbox bars and a faint dark wash while a cutscene runs, and mouse clicks are blocked
    until it ends (or a dialogue opens). PlaySequence now plays ToEE animations (attack, cast, hit, fall...)
    instead of only being logged; several cutscene steps for one character run one after another.
  * Creature spawns: script CreateCreature spawns appear (facing and portrait), area spawn .INI files are
    converted (spawns on entering an area and timed spawns, with their variable conditions and caps), and
    spawned groups spread out instead of stacking on one tile.
  * Rest encounters: on converted IE maps, the area's rest table decides whether resting is safe and what
    interrupts it, through hooks on ToEE/Co8's random_encounter.py (vanilla maps keep Co8's behaviour).
  * Kegs and other scripted objects spawn as named barrel critters.
  * Script error fixes: See()/Range() argument errors and .lower errors on object handles are gone.
  * Portrait batch 6: 30 commissioned monster portraits (hook horror, snow and ice trolls, yuan-ti, lizard men,
    dire wolves, Malarites, wights, salamanders, armored skeletons, umber hulk, beetles, orcs, goblins, wyvern
    and two bosses) with "elite" variants for the tougher versions and mirrored copies for variety.
  * Still an early, AI-assisted experiment: not playable or polished.

EARLIER (2026-11-01)
--------------------------------
  * Area scripts now run on a game-time map tick in the bundled Temple+ build: they pause with menus and the
    inventory and keep running after save/load.
  * First cutscenes: an IE cutscene sequencer (StartCutScene, fades, floating text), chapter screens as ToEE
    slides with subtitles.
  * Movies: the converter converts the intro/cut movies from YOUR OWN install, on your PC (classic IWD MVE from
    the game's BIFs, or IWD:EE movies with --movies-ee). This needs ffmpeg and RAD Video Tools (binkc) on PATH;
    without them the movie step is skipped and the rest of the conversion continues.
  * Commissioned NPC portraits: 50 new portraits (IWD and IWD2 characters, Targos children, townsfolk, and monsters
    such as yetis, frost giants and winter wolves with an "upgraded" variant and mirrored copies; a monster group
    picks among them so it doesn't look cloned). They are installed into data\art\interface\portraits.
  * Known issues: during a cutscene the input may stay locked (load a save); PlaySequence is only logged; some IE
    script triggers (See(), Range()) log argument errors and don't fire; untested on a clean Windows install.

EARLIER (2026-10-26)
--------------------------------
  * Exit icons: building doors and the town exits show a clickable travel icon. Click it and the party walks
    there and travels.
  * Dialogue paging: conversations with more than 5 replies show all of them, paged with More... / Back.
  * Better pathing: the converter places many more path nodes, so long walks across Easthaven (and clicks on far
    exit icons) find a route instead of the party standing still.
  * Known issue: the exit icon of one building (AR1009) may still not react to a click from some spots. If the party
    doesn't move, walk closer to it and click again.
  * Old saves: saves made with an earlier preview keep the old maps' state. Start a NEW game after converting and
    installing this preview (and reconvert: run convert.bat again into your ToEE copy).

WHAT THIS IS
------------
A preliminary adaptation that loads an Icewind Dale map into the ToEE engine (Temple+). It converts the
first town, Easthaven (IE area AR1000), from YOUR OWN copy of Icewind Dale and lets you walk around it in ToEE:

  * the IE area art, walkable and blocked tiles
  * IE doors: the door art opens and closes, and closed doors block movement
  * the town's creatures, converted to ToEE critters with their IE equipment, some of them on IE patrol routes
  * IE items with their own inventory icons (the town's shops are in its interiors, which are still empty)
  * the 14 building interiors (AR1001-AR1014): walk into a building's door and the whole party enters it, walk
    into the interior's exit and it is back in town. Interiors are bare maps with their doors: no people, no
    furniture objects, no shops, no scripts yet
  * IE journal entries as ToEE logbook quests, with titles, under an "Easthaven" tab (a solved step is shown as
    the same quest, completed)
  * dialogue in an IE-style dialogue window (IWD look for classic, IWD:EE look for the Enhanced Edition)
  * IE spells mapped to ToEE/Temple+ spells where an equivalent exists, and IE creature/area scripts
  * everything is baked into the map files, so it survives saving and loading like a normal ToEE map

This is NOT a playable conversion of Icewind Dale. There is no campaign, no travel beyond Easthaven's buildings, no quests
beyond what the town's scripts and dialogue happen to do, and many rules are approximations. It's a technology
preview to try out and to send feedback on.

No Icewind Dale data is included in this download. The converter reads it from your own install, on your PC.

REQUIREMENTS
------------
  * The Temple of Elemental Evil (GOG or Steam).
  * Icewind Dale (classic, GOG/CD) or Icewind Dale: Enhanced Edition (GOG/Steam/Beamdog), installed.
    IWD:EE must be patch 2.5 or later. 2016-era 1.4 installs lack the Enhanced Edition UI and are not
    supported; convert.bat will stop with a message. Update IWD:EE and run convert.bat again (no special flag;
    just point it at the updated IWD:EE folder). Classic Icewind Dale is unchanged.
  * Windows.
  * Python 3.9 or newer, installed BEFORE you run the converter: https://www.python.org/downloads/
    In the installer, tick "Add python.exe to PATH". The converter then installs its three Python packages
    itself (numpy, pillow, fonttools).
  * The Temple+ build in the TemplePlus folder of this download. It's Temple+ 1.0.98 plus the preview
    features: the IE dialogue window, the door/tile hooks, and module support (a module can choose where a new
    game starts). Official Temple+ can't show the converted doors or the IE dialogue window, and doesn't start
    new games in Easthaven.

INSTALL
-------
1. Make a COPY of your ToEE folder, e.g. "C:\GOG Games\ToEE-IWD", and use the copy from here on. The preview adds
   files to the ToEE folder and switches every dialogue to the IE window, so keep your normal game separate.
2. Unzip this download anywhere, e.g. C:\IWD-in-ToEE-preview.
3. Run the converter once, with your Icewind Dale folder and the ToEE copy. It takes a few minutes:

     convert.bat "C:\GOG Games\Icewind Dale" "C:\GOG Games\ToEE-IWD"

   (For the Enhanced Edition, give its folder: the one with chitin.key and the lang folder. It must be
   IWD:EE 2.5 or later; older 1.4 installs are not supported.) The converter
   writes the module into output\install and copies it into the ToEE copy. If it stops with an error, the
   message names the step that failed.
4. Run TemplePlus\TemplePlusConfig.exe. Set the ToEE folder to your ToEE COPY, choose windowed or full
   screen as you like, and save. Decline any offer to update Temple+; an update would replace the preview
   build with official Temple+.
   (If you already use Temple+: the settings are shared, so switch the folder back for your normal game.)
5. Optional, for a copy converted with an older preview: fix_inventory_icons.bat "C:\GOG Games\ToEE-IWD"
   clears the green behind equipped icons without a full reconvert.

HOW TO START
------------
The converter installs Icewind Dale as its own Temple+ module, "IWD" (modules\IWD.dat, modules\IWD and
modules\IWD_core in the ToEE copy). Your normal ToEE module is left alone.
modules\IWD.dat is not new data: it's your own modules\ToEE.dat, hard-linked (or copied, if a link isn't
possible) under the module's name, because Temple+ needs a <module>.dat to list a module. The converter makes it;
if you delete it, copy modules\ToEE.dat to modules\IWD.dat yourself (or run the converter again).
1. In TemplePlus\TemplePlusConfig.exe, pick the module "IWD" in the module list and save.
2. Start TemplePlus\TemplePlus.exe and start a NEW game with any party. It begins in Easthaven; no console
   command is needed. (To play normal ToEE again, pick the module "ToEE" in TemplePlusConfig.)
3. Saves from the 2026-11-10 and 2026-11-11 previews should still load. Saves from older previews don't work
   (the maps have new ids since 2026-11-10); start a new game.
4. Click townsfolk to talk to them (IE dialogue window) and click doors to open and close them. Walk into a
   building's doorway to go inside, and into the exit area inside to come out. Save and load as usual.
   To leave Easthaven for good, load a save from before the trip.

KNOWN ISSUES
------------
  * Pathfinding: generated nodes are dense (6-tile spacing) with some redundant nodes in open areas, and
    link distances are straight-line / aerial rather than the actual walking route, which can look wrong.
    A later unify-pass and walk-path linking are planned but are not in this preview. Manual per-map
    pathnode overrides (as shipped for AR1000) are the current way to ship a culled set.
  * The converted IWD font can look jaggy.
  * Two other Easthaven exit icons (To1009 and To1012) may have little room around them for a party member;
    they passed an earlier in-game check (2026-10-24) but are worth another look if a click seems fussy.
  * The Churin exit-icon and info-cursor fixes above are in this build but have not been re-tested in game
    yet (the bugs themselves were found in playtest).
  * The cutscene lock blocks mouse clicks only; some PlaySequence animations are a best-guess ToEE match.
  * Some spawn .INI options are ignored; summons don't check that the caster has the spell memorised.
  * Portraits checked in game only for a few characters and spawned monsters so far.
  * Not tested on a clean Windows install yet. Feedback is very welcome.
  * Easthaven and its 14 building interiors are converted, but the interiors are empty (no people, shops or
    scripts yet) and are still a technology preview, not a full campaign. The road south (to AR1200) and two
    interior side doors (AR1015, AR1016) lead to areas that are not in the preview: you get a one-time
    "This exit (ARxxxx) is not in the preview" note and stay put. The world map doesn't know Easthaven.
  * Travel is a 4-times-a-second check of where your party is, so it works in a loaded save too; after arriving
    (or loading) it only fires once the party has stepped out of every exit area, so it never bounces you back.
  * Rules are approximations: IE stats, THAC0 and saves are mapped to D&D 3.5 equivalents. Some IE spells have no
    ToEE counterpart yet and are left out (the creature just doesn't cast them). Item usability restrictions are
    dropped, and some weapons map to their nearest ToEE type.
  * Fights work but use simplified IE combat scripts; there's no IE-style target selection.
  * Patrols: walkers pause a fixed 3 s at each waypoint, and one patroller stays at its first waypoint.
  * Potions can stack into another potion of the same ToEE type.
  * Copies converted before 2026-11-11 may show a green background on equipped icons (IE's transparent
    colour). New converts fix this; for an existing ToEE copy, run fix_inventory_icons.bat on that folder.
  * Wands and other charged items show no charges.
  * Converted NPCs may carry a few extra default ToEE items.
  * IWD:EE: one NPC of the classic town isn't in the EE version of the area.
  * Some IE script actions and triggers aren't supported yet; they are skipped (Temple+ log: IE_UNSUPPORTED).
  * The IE dialogue window is used for every conversation in the ToEE copy, including ToEE's own NPCs.
  * Temple+ may log harmless warnings when loading the map.

UNINSTALL
---------
Delete the ToEE copy and this folder. Set the ToEE folder in TemplePlusConfig back to your normal game.

FEEDBACK
--------
Please post feedback, screenshots and bug reports in the Icewind Dale / ie2toee thread on co8.org (Circle of
Eight forums). Include the converter's messages, your edition (classic or EE), and
%USERPROFILE%\Saved Games\TemplePlus\TemplePlus.log after the problem happened.

CREDITS / LICENCES
------------------
Converter: ie2toee (https://github.com/DudeMcDude/ie2toee), see converter\LICENSE.txt.
Engine: Temple+ (https://github.com/GrognardsFromHell/TemplePlus, MIT licence). The preview changes to Temple+
are listed in TemplePlus\IE-PREVIEW-SOURCE.txt. Source: https://github.com/DudeMcDude/TemplePlus/tree/feature/dm-tile-edits-save
Icewind Dale is (c) its publishers. You need your own legal copy;
nothing from it is redistributed here. The Temple of Elemental Evil is (c) its publishers.
The portrait art in art\portraits was commissioned for this project (AI-assisted, via Gemini).

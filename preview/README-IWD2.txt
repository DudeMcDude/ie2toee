ICEWIND DALE II (TARGOS) IN THE TEMPLE OF ELEMENTAL EVIL ENGINE - EARLY PREVIEW (2026-11-10)
==========================================================================================

An early-preview, AI-assisted experiment. It converts the opening of Icewind Dale II - Targos (the docks
I2AR1000, its interiors AR1001-AR1006, AR1100, the palisade AR1200 and AR1201) - from YOUR OWN copy of Icewind Dale II into maps for
The Temple of Elemental Evil running on the bundled Temple+ build. No Icewind Dale II data is included in this
download: the converter reads it from your install, on your PC. This is not a playable conversion of IWD2.

NEXT PREVIEW (not in the 2026-11-10 zip; on the iwd2-targos branch)
--------------------------------
  * IE dialogue window for IWD2: convert_iwd2.bat now builds it from YOUR Icewind Dale II's own GUI (the
    GUIW08.CHU message panel, its scrollbar and NORMAL font) and installs it into modules\ToEE
    (art\interface\dialog_ie). The 2026-11-10 converter never installed it, so conversations used the stock
    ToEE window. Re-run convert_iwd2.bat (no new flag) to get it.
  * An Enhanced Edition folder without ui.menu/bgee.lua stops the convert with a message to update it.
  * Equipped inventory icons: leftover IE green on transparent pixels is cleared (the bag already looked
    fine; paper-doll slots ignore alpha). New converts fix this; for an existing ToEE copy, run
    fix_inventory_icons.bat on that folder (no full reconvert needed for the icons alone).

EARLIER (2026-11-10)
--------------------------------
  * Town maps (mini maps): every converted area has a town map built from its own background, and the town map
    list names the Targos places instead of ToEE ones.
  * Prologue narration: the chapter slide's narration plays again (it was silent and the slide could stall).
    Movies and slides can be skipped with Space, Enter, Esc or a mouse click; a slide whose sound fails to play
    ends after 3 seconds and a small in-game notice asks you to report it.
  * IE dialogue window (only once convert_iwd2.bat installs it - see NEXT PREVIEW above): the side portrait
    is shown only when a real big portrait exists (no blurry upscaled small portrait or placeholder head); the
    dialogue scrollbar art is fixed.
  * Commissioned portraits, batch 8 (art generated via Gemini): generic monster and townsfolk art for about 310
    IWD2 creatures in 20 families (goblins, orcs, orogs, spiders, shadows, zombies, ogres, harpies, trolls,
    wolves, townspeople and more); elites and chiefs get the stronger-looking art.
  * Bundled Temple+ 0.2.92 (see TemplePlus\IE-PREVIEW-SOURCE.txt).
  * OLD SAVES DON'T WORK: the converted maps have new map ids (5031-5040). Start a NEW game after converting.

EARLIER (2026-11-04)
--------------------------------
  * New areas: the Targos palisade (AR1200) and its small interior (AR1201).
  * Palisade cutscene: after the first goblin bands fall, the goblin sorcerer Caballus breaches the wall with a
    Fireball, conjures in a goblin wave (summon hexagram) and teleports away.
  * Summon spells: IE summoning spells conjure their creatures by caster level, with vanilla ToEE / Co8 stand-ins
    where needed (dire rats, efreeti, elementals, ice devil for gelugon...).
  * Spawned creatures run their own IE scripts and dialogue; cutscene camera pans, GUI hiding and speech bubbles.
  * Commissioned portraits, batch 7 (art generated via Gemini): 25 Targos NPCs and goblin leaders - Caballus,
    Ghotrag, Vghotan, Black Geoffrey, Blanchard Pike, Olap, Jorun, Swift Thomas, Illigmar, Gohar, Magdar, Lumbar,
    Nolan, Firtha, Brogan, Screed, Tarran, Anson, Isherwood, Gable, Kadence, Niles, Honest Jon, Tabard Mooncalf
    and the drill sergeants.

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
  * Area scripts run on a game-time map tick in the bundled Temple+ build (pause with menus/inventory, survive
    save/load).
  * First cutscenes (IE cutscene sequencer, fades, floating text); the chapter screens show as ToEE slides with
    subtitles; the IWD2 intro movie is copied from your own install (IWD2's movies are already Bink).
  * Commissioned NPC portraits: Targos NPCs (Ulbrec, Shawford, Hedron, Reig, Guthewulfe, Kickshaw, Oswald...),
    the Targos children, and monster portraits (yeti, frost giant, winter wolf, verbeeg, boring beetle) with an
    upgraded variant and mirrored copies. Installed into data\art\interface\portraits.
  * Fixes: the party can walk off the start ship (wider gangway), hint-text markers are no longer spawned as
    people, NPCs always wield their weapons.

REQUIREMENTS
------------
  * The Temple of Elemental Evil (GOG or Steam), a COPY used only for this preview (not your IWD1 preview copy).
  * Icewind Dale II (GOG 2.01 or retail), installed.
  * Windows, and Python 3.9+ from https://www.python.org/downloads/ (tick "Add python.exe to PATH").
  * The Temple+ build in the TemplePlus folder of this download (official Temple+ lacks the preview features,
    including the area-script map tick). The converter also reads its spell tables, so always run it through
    convert_iwd2.bat (it passes --tp TemplePlus).

INSTALL
-------
1. Copy your ToEE folder, e.g. "C:\GOG Games\ToEE-IWD2".
2. Unzip this download anywhere and run:
     convert_iwd2.bat "C:\GOG Games\Icewind Dale 2" "C:\GOG Games\ToEE-IWD2"
3. Run TemplePlus\TemplePlusConfig.exe, set the ToEE folder to the copy, module "ToEE", save. Decline updates.
4. Start TemplePlus\TemplePlus.exe and start a NEW game: it begins at the Targos docks.
   Conversations use the IE dialogue window that step 2 built from your IWD2 GUI. After updating the converter,
   run convert_iwd2.bat again to rebuild and reinstall it.

KNOWN ISSUES
------------
  * Already-converted inventories may show a green background on equipped icons (IE's transparent
    colour). New converts fix this; for an existing ToEE copy, run fix_inventory_icons.bat on that folder.
  * The cutscene input lock blocks mouse clicks only; keyboard shortcuts still work. Some PlaySequence animations
    are a best guess at the matching ToEE animation.
  * Spawned creatures don't run their own IE scripts or dialogue yet; some spawn .INI options (e.g. per-difficulty
    variants) are read but ignored. Targos has no rest table, so resting there stays quiet.
  * Portraits were checked in game for Hedron, Guthewulfe and a few spawned monsters (snow trolls) only.
  * Goblins in the interiors start combat on arrival; a townsperson can block the AR1004 door.
  * IWD2 journal text isn't shown yet; some feats/spells have no ToEE equivalent.
  * AR1201 -> AR1200: use the exit with the party close to it. The battle after the palisade cutscene is not
    tuned yet, and summons don't check that the caster has the spell memorised.
  * Not yet tested on a clean Windows install. Feedback welcome.

FEEDBACK / CREDITS
------------------
Feedback in the ie2toee thread on co8.org, with %USERPROFILE%\Saved Games\TemplePlus\TemplePlus.log.
Converter: ie2toee (https://github.com/DudeMcDude/ie2toee), see converter\LICENSE.txt.
Engine: Temple+ (MIT, https://github.com/GrognardsFromHell/TemplePlus); preview changes listed in
TemplePlus\IE-PREVIEW-SOURCE.txt, source https://github.com/DudeMcDude/TemplePlus/tree/feature/dlg-log-portrait
Portrait art (art\portraits) was commissioned for this project (AI-assisted, via Gemini).
Icewind Dale II and The Temple of Elemental Evil are (c) their publishers; nothing from them is redistributed.

ICEWIND DALE IN THE TEMPLE OF ELEMENTAL EVIL ENGINE - PLAYER PREVIEW (2026-10-18)
=================================================================================

IMPORTANT: PYTHON 3.9 OR NEWER MUST BE INSTALLED
  The converter is a Python program. Before you start, install Python 3.9+ from
  https://www.python.org/downloads/ and, in the installer, tick "Add python.exe to PATH".
  Without it convert.bat stops with a message. You also need your own Icewind Dale or Icewind Dale: EE.

WHAT THIS IS
------------
A preliminary adaptation that loads an Icewind Dale map into the ToEE engine (Temple+). It converts the
first town, Easthaven (IE area AR1000), from YOUR OWN copy of Icewind Dale and lets you walk around it in ToEE:

  * the IE area art, walkable and blocked tiles
  * IE doors: the door art opens and closes, and closed doors block movement
  * the town's creatures, converted to ToEE critters with their IE equipment, some of them on IE patrol routes
  * IE items with their own inventory icons (the town's shops are in its interiors, which aren't in this preview)
  * dialogue in an IE-style dialogue window (IWD look for classic, IWD:EE look for the Enhanced Edition)
  * IE spells mapped to ToEE/Temple+ spells where an equivalent exists, and IE creature/area scripts
  * everything is baked into the map files, so it survives saving and loading like a normal ToEE map

This is NOT a playable conversion of Icewind Dale. There is no campaign, no travel to other IE areas, no quests
beyond what the town's scripts and dialogue happen to do, and many rules are approximations. It's a technology
preview to try out and to send feedback on.

No Icewind Dale data is included in this download. The converter reads it from your own install, on your PC.

REQUIREMENTS
------------
  * The Temple of Elemental Evil (GOG or Steam).
  * Icewind Dale (classic, GOG/CD) or Icewind Dale: Enhanced Edition (GOG/Steam/Beamdog), installed.
  * Windows.
  * Python 3.9 or newer, installed BEFORE you run the converter: https://www.python.org/downloads/
    In the installer, tick "Add python.exe to PATH". The converter then installs its three Python packages
    itself (numpy, pillow, fonttools).
  * The Temple+ build in the TemplePlus folder of this download. It's Temple+ 1.0.98 plus two preview
    features: the IE dialogue window and the door/tile hooks. Official Temple+ can't show the converted doors
    or the IE dialogue window.

INSTALL
-------
1. Make a COPY of your ToEE folder, e.g. "C:\GOG Games\ToEE-IWD", and use the copy from here on. The preview adds
   files to the ToEE folder and switches every dialogue to the IE window, so keep your normal game separate.
2. Unzip this download anywhere, e.g. C:\IWD-in-ToEE-preview.
3. Run the converter once, with your Icewind Dale folder and the ToEE copy. It takes a few minutes:

     convert.bat "C:\GOG Games\Icewind Dale" "C:\GOG Games\ToEE-IWD"

   (For the Enhanced Edition, give its folder: the one with chitin.key and the lang folder.) The converter
   writes the module into output\install and copies it into the ToEE copy. If it stops with an error, the
   message names the step that failed.
4. Run TemplePlus\TemplePlusConfig.exe. Set the ToEE folder to your ToEE COPY, choose windowed or full
   screen as you like, and save. Decline any offer to update Temple+; an update would replace the preview
   build with official Temple+.
   (If you already use Temple+: the settings are shared, so switch the folder back for your normal game.)

HOW TO START
------------
1. Start TemplePlus\TemplePlus.exe (or "Play" in TemplePlusConfig).
2. Start a new game with any party, or load any save. You need to be in the game world, not in the menu.
3. Press Shift+~ (Shift and the key left of 1) to open the console, type

     import iwd; iwd.go()

   and press Enter. Press Shift+~ again to close the console. The party travels to Easthaven.
4. Click townsfolk to talk to them (IE dialogue window) and click doors to open and close them. Save and load
   as usual. To leave Easthaven, load a save from before the trip.

KNOWN ISSUES
------------
  * Only the outdoor town of Easthaven is converted: no building interiors (so no shops), its exits don't lead
    anywhere, and the world map doesn't know it.
  * Rules are approximations: IE stats, THAC0 and saves are mapped to D&D 3.5 equivalents. Some IE spells have no
    ToEE counterpart yet and are left out (the creature just doesn't cast them). Item usability restrictions are
    dropped, and some weapons map to their nearest ToEE type.
  * Fights work but use simplified IE combat scripts; there's no IE-style target selection.
  * Patrols: walkers pause a fixed 3 s at each waypoint, and one patroller stays at its first waypoint.
  * Potions can stack into another potion of the same ToEE type.
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
are in TemplePlus\ie-preview-changes.diff (against Temple+ master 03d72045). Source:
https://github.com/DudeMcDude/TemplePlus/tree/feature/ie-dialog-skin
commit 644ceb9f (https://github.com/DudeMcDude/TemplePlus/commit/644ceb9fbc84c3aae7aa930f966c0b92767fcbed). Icewind Dale is (c) its publishers. You need your own legal copy;
nothing from it is redistributed here. The Temple of Elemental Evil is (c) its publishers.

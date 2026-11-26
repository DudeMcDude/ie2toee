Icewind Dale in Temple+ | Chapter 1 preview (2026-11-26b) | Windows guide
=========================================================================

Requires: Windows, Python 3.9 or newer, your own Icewind Dale (classic or
Enhanced Edition 2.5+), and your own Temple of Elemental Evil.

An early, AI-assisted conversion of Icewind Dale's opening and Chapter 1
into Temple+, using ToEE combat rules. Start in Easthaven, travel to
Kuldahar, explore the Vale of Shadows and Kresselack's tomb, the Temple of
the Forgotten God, and reach Dragon's Eye at the start of Chapter 2.

What you need
-------------

* Python 3.9 or newer with pip. Enable "Add python.exe to PATH" during
  setup. The batch file installs NumPy, Pillow and fontTools through pip,
  so allow internet access for the first setup.
  https://www.python.org/downloads/windows/
* Your installed copy of Icewind Dale classic (with its CD movie BIFs) or
  Icewind Dale: Enhanced Edition 2.5 or newer. This ZIP contains no
  Icewind Dale data: the converter reads it from your installation.
* Your own Temple of Elemental Evil (GOG or Steam). Make a separate copy of
  its game folder for this preview. Use the Temple+ supplied in this ZIP.

Media tools | install before conversion
---------------------------------------

Download a Windows FFmpeg build containing ffmpeg.exe and ffprobe.exe,
with the libmp3lame encoder.
  https://ffmpeg.org/download.html

FFmpeg is needed for the narrated chapter slides, area music, area
ambient sounds and NPC dialogue voices. All of them are converted from
your own game installation while convert runs. Without FFmpeg the
conversion still finishes, but those are skipped.

Extract the build. Put its bin directory on PATH, or create a folder named
media-tools next to the convert batch file and copy the contents of bin
there. Keep any DLLs supplied with the executables. FFmpeg is used only
during conversion, not while you play.

IWD also needs RAD Video Tools to encode the opening movie, the avalanche
and the chapter movies. Download the 64-bit Windows tools from the
official page and follow its installation instructions.
  https://www.radgametools.com/bnkdown.htm
For a custom install, set RADVIDEO in the same Command Prompt first, e.g.
  set "RADVIDEO=C:\Tools\RADVideo\radvideo64.exe"

Install and start a new campaign
--------------------------------

1. Extract this ZIP into a fresh folder. Open Command Prompt there.
2. Run, substituting your game and your ToEE copy (keep the quotes):

   convert.bat "C:\Games\Icewind Dale" "C:\Games\ToEE-IWD"

3. Check MOVIE SUMMARY at the end and any warnings about missing tools.
   To repair missing media, install the named tools, reopen Command Prompt
   and run the same command again.
4. Open TemplePlus\TemplePlusConfig.exe. Set the game folder to your
   ToEE-IWD copy, select module "IWD", and save. Keep the bundled Temple+
   version if the config program offers an update.
5. Launch TemplePlus\TemplePlus.exe and start a NEW campaign. Temple+
   shares its configuration across installs: switch the game folder and
   module back before playing your regular ToEE.

In the game
-----------

Click people to talk. Use the exit icons to travel; regional exits open
the original world map, with travel times. Hover over a painted container
to see its outline, or hold Tab to highlight containers that hold loot.

Optional: the chapter autoplayer can play the campaign by itself for
testing; it takes over the game window. See Autoplayer\README.txt.

Known gaps
----------

* This is an early, AI-assisted conversion preview, not a finished port.
  Expect rough edges in combat balance, pathing, containers and quests.
  Chapter 1 was tested with the assisted chapter autoplayer (boosted
  party, checkpoint replays), not by a full unassisted human playthrough.
* Without FFmpeg the conversion still runs, but music, area ambients, NPC
  voices and narrated slides are skipped. The converter prints a warning.
* Icewind Dale: Dragon's Eye exterior (AR4000) is converted, the cavern
  interior (AR4001) and the rest of Chapter 2 are not.
* Icewind Dale II: the trip ends at Oswald's laboratory (AR4001). The
  exterior beyond it (AR4000) and the rest of Chapter 2 are not converted.
  Ennelia's reunion journal entry (16068) has no quest-log slot yet.
* Saves from earlier previews are not supported. Reconvert and start a
  new campaign.

Feedback and credits
--------------------

Report issues in the ie2toee thread on the Circle of Eight forums. Include
the game edition, area or quest, the installer summary, and the relevant
section of the game log.
  %USERPROFILE%\Saved Games\TemplePlus\TemplePlus.log
  https://co8.org/

The converter reads all original game data, music, sounds and voices from
your own installations at conversion time; none of it is in this ZIP.
Character portraits in art\portraits are original AI-generated art
(Google Gemini), commissioned for this project; they are not taken from
the Icewind Dale games. See converter\LICENSE.txt for the converter
license and TemplePlus\IE-PREVIEW-SOURCE.txt for engine sources. Earlier
previews and source links:
  https://github.com/DudeMcDude/ie2toee/releases

Icewind Dale in Temple+ | Windows player guide
============================================

Start in Easthaven, investigate the caravan and orc cave, and leave with
Hrothgar for Kuldahar Pass. This preview uses ToEE combat rules.

What you need
-------------

* Windows and Python 3.9 or newer with pip. Enable "Add python.exe to PATH"
  during setup. The batch file installs NumPy, Pillow and fontTools through
  pip, so allow internet access for the first setup.
  https://www.python.org/downloads/windows/
* Your installed copy of Icewind Dale classic (with its CD movie BIFs) or Icewind Dale: Enhanced
  Edition 2.5 or newer.
* Your own Temple of Elemental Evil (GOG or Steam). Make a separate copy of
  its game folder for this preview. Use the Temple+ supplied in this ZIP.

Movie tools | install before conversion
---------------------------------------

Download a Windows FFmpeg build containing ffmpeg.exe and ffprobe.exe.
Choose a build with the libmp3lame encoder for chapter narration.
  https://ffmpeg.org/download.html

Extract the build. Put its bin directory on PATH, or create a folder named
media-tools next to convert.bat and copy the contents of bin there.
Keep any DLLs supplied with the executables. Both tools are used during
conversion. They do not need to be running when you play.

IWD also needs RAD Video Tools to encode the opening movie and avalanche.
Download the 64-bit Windows tools from the official page and follow its
installation instructions.
  https://www.radgametools.com/bnkdown.htm

The converter checks the usual RADVideo install folders, PATH and the
RADVIDEO environment variable. For a custom installation, set RADVIDEO in
the same Command Prompt before conversion, for example

  set "RADVIDEO=C:\Tools\RADVideo\radvideo64.exe"

Install and start a new game
---------------------------

1. Extract the preview ZIP into a fresh folder. Open Command Prompt there.
2. Run the command below, substituting your installed game and ToEE copy.
   Keep the quotes if the paths contain spaces.

   convert.bat "C:\Games\Icewind Dale" "C:\Games\ToEE-Easthaven"

3. Look for MOVIE SUMMARY at the end. A warning during installation lists
   missing tools and the conversion continues. The final summary names the
   prologue scenes ready for playback and anything missing from this build.
   To repair missing media, install the named tools, reopen Command Prompt
   if you changed PATH, and run the same conversion command again.
4. Open TemplePlus\TemplePlusConfig.exe. Set the game folder to your
   ToEE-Easthaven copy, select module "IWD", and save. Keep the bundled
   Temple+ version if the config program offers an update.
5. Launch TemplePlus\TemplePlus.exe and start a new game. Use a fresh party
   after reconverting to see the opening and changes to previously visited
   areas. Temple+ shares its configuration across installs. Switch the
   game folder and module back before playing your regular ToEE game.

In the game
-----------

Click people to talk. Walk into doorway exits to travel. Hover over a
painted container to see its outline, click to open it, or hold Tab to
highlight containers that hold loot. Select a player character to loot.

The chapter autoplayer completed all six sidequests and reached Kuldahar
Pass from a fresh party. The opening film ran 4:56, the narrated prologue
0:36 and the departure avalanche 1:21. The three Snowdrift Inn containers
could not be reached from the entrance.

For optional assisted chapter autoplay, see Autoplayer\README.txt. From
Autoplayer\TemplePlus, run

  ieap.bat iwd-ch1 menu "C:\Games\ToEE-Easthaven"

Feedback and credits
--------------------

Report issues in the ie2toee thread on the Circle of Eight forums. Include
the game edition, area or quest, the installer summary for movie issues,
and the relevant section of the game log.
  %USERPROFILE%\Saved Games\TemplePlus\TemplePlus.log
  https://co8.org/

The converter reads the original game assets from your own installations.
See converter\LICENSE.txt for the converter license and
TemplePlus\IE-PREVIEW-SOURCE.txt for engine changes and sources. Gemini
contributed the commissioned portrait art. For earlier changes, see
  https://github.com/DudeMcDude/ie2toee/releases

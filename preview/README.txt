Icewind Dale II in Temple+ | Windows player guide
===============================================

Start on the Targos docks, help the town, defend the palisade and report
to Ulbrec for the assignment to Shaengarne. This preview uses ToEE combat rules.

What you need
-------------

* Windows and Python 3.9 or newer with pip. Enable "Add python.exe to PATH"
  during setup. The batch file installs NumPy, Pillow and fontTools through
  pip, so allow internet access for the first setup.
  https://www.python.org/downloads/windows/
* Your installed copy of Icewind Dale II (GOG 2.01 or retail).
* Your own Temple of Elemental Evil (GOG or Steam). Make a separate copy of
  its game folder for this preview. Use the Temple+ supplied in this ZIP.

Movie tools | install before conversion
---------------------------------------

Download a Windows FFmpeg build containing ffmpeg.exe and ffprobe.exe.
Choose a build with the libmp3lame encoder for chapter narration.
  https://ffmpeg.org/download.html

Extract the build. Put its bin directory on PATH, or create a folder named
media-tools next to convert_iwd2.bat and copy the contents of bin there.
Keep any DLLs supplied with the executables. Both tools are used during
conversion. They do not need to be running when you play.

IWD2 copies the Targos intro from the original game even when these tools
are missing. FFmpeg and ffprobe are needed for the narrated chapter slides.
IWD2 does not require RAD Video Tools.

Install and start a new game
---------------------------

1. Extract the preview ZIP into a fresh folder. Open Command Prompt there.
2. Run the command below, substituting your installed game and ToEE copy.
   Keep the quotes if the paths contain spaces.

   convert_iwd2.bat "C:\Games\Icewind Dale II" "C:\Games\ToEE-Targos"

3. Look for MOVIE SUMMARY at the end. A warning during installation lists
   missing tools and the conversion continues. The final summary names the
   prologue scenes ready for playback and anything missing from this build.
   To repair missing media, install the named tools, reopen Command Prompt
   if you changed PATH, and run the same conversion command again.
4. Open TemplePlus\TemplePlusConfig.exe. Set the game folder to your
   ToEE-Targos copy, select module "ToEE", and save. Keep the bundled
   Temple+ version if the config program offers an update.
5. Launch TemplePlus\TemplePlus.exe and start a new game. Use a fresh party
   after reconverting to see the opening and changes to previously visited
   areas. Temple+ shares its configuration across installs. Switch the
   game folder and module back before playing your regular ToEE game.

Portraits in Targos
------------------

Gemini contributed fifteen additional character portraits for the trade
depot, pavilion, palisade and warehouse. Harlesford, Caulder, Menon and
the Weapon Instructor now each have their own portrait. Reconvert and
visit these areas in a fresh campaign to see all updated assignments.

In the game
-----------

Click people to talk. Walk into doorway exits to travel. Hover over a
painted container to see its outline, click to open it, or hold Tab to
highlight containers that hold loot. Select a player character to loot.

The chapter autoplayer completed all sixteen sidequests, defended the
palisade and received Ulbrec's assignment across same-party checkpoint
replays. The opening film ran 3:06 and the narrated prologue 1:31. Some
containers in the dock storehouse, Council Chambers and Weeping Widow are
unreachable. Hedron's scene can
pause before returning control. A previously reported siege crash did not
recur in this playtest. One movie test crashed during shutdown.

For optional assisted chapter autoplay, see Autoplayer\README.txt. From
Autoplayer\TemplePlus, run

  ieap.bat iwd2-ch1 menu "C:\Games\ToEE-Targos"

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

NOVEMBER 21, 2026 | PUBLIC PLAYER TEST
The November 21 release uses the same Temple+ build for the player and chapter autoplayer.
Targos covers sixteen tested sidequests, the palisade battle, and the assignment to Shaengarne.
The siege defenders recognize allies, and enemies leave the practice barrels alone.

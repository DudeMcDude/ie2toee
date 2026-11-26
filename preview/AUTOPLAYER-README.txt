AUTOPLAYER (early preview, an AI-assisted experiment)
=====================================================

What it is
----------
A test driver that plays the converted opening by itself: it starts a new game with the pregenerated party,
talks to the quest givers along the critical path, travels between areas and logs what it sees. It is meant
for testing the conversion (does the story still advance?), not as a way to play. It is based on the Temple+
autoplayer test framework (DudeMcDude/toee_autoplayer). Expect rough edges.

It needs its OWN Temple+ build, in the Autoplayer\TemplePlus folder of this zip. It is the same Temple+ build as the player
TemplePlus folder plus the autoplayer scripts (see AUTOPLAYER-SOURCE.txt). Do not copy it over your normal
TemplePlus folder; run it from where it is.

Before you start
----------------
1. Convert as usual (README.txt) into a separate ToEE copy, e.g. C:\GOG Games\ToEE-IWD (IWD) or
   C:\GOG Games\ToEE-IWD2 (IWD2), and check that the normal TemplePlus.exe starts a new game there.
2. Save anything you care about: the driver starts NEW games and the game writes its usual autosave
   (modules\<module>\Save\SlotAuto) on the way. Your numbered save slots are not touched.
3. Use a game window, not full screen, if you want to keep using the PC. See "It takes over the screen" below.

Running it
----------
Open a Command Prompt in Autoplayer\TemplePlus. To play past the prologue into Chapter 1, set
IWDAP_NEXT_REGION=1 first, then run ieap.bat:

  set IWDAP_NEXT_REGION=1
  ieap.bat iwd-ch1  menu "C:\Games\ToEE-IWD"
      IWD: Easthaven prologue, Kuldahar, the Vale of Shadows and Kresselack's tomb, Lysan, the Temple of
      the Forgotten God, Arundel's report, then the world map to Dragon's Eye (start of Chapter 2).

  set IWDAP_NEXT_REGION=1
  ieap.bat iwd2-ch1 menu "C:\Games\ToEE-IWD2"
      IWD2: Targos prologue, Shaengarne Ford, mill, dam and bridge, the Horde Fortress (wardstones, Guthma,
      Braston's escape), Ennelia, Ulbrec, then Oswald's airship (start of Chapter 2).

  Without IWDAP_NEXT_REGION=1 the driver stops at the end of the prologue, as in earlier previews.
  These runs used the combat assist (see below) and checkpoint replays during testing; a single unbroken
  run from a new game to Chapter 2 has not been verified, so expect to resume from autosaves.

  The last argument is your converted ToEE copy. ieap.bat points TemplePlus.ini (toeeDir, defaultModule) at it
  for the run and restores the ini afterwards. "menu" means: no save is loaded; the driver starts the new game
  from the main menu itself.

  The older quest-giver tours are still there: ieap.bat iwd SAVE GAMEDIR / ieap.bat iwd2 SAVE GAMEDIR
  (SAVE = a save of yours in that module, e.g. slot0007, from which the tour starts).

Environment variables (optional; ieap.bat sets the required ones)
--------------------------------------------------------------------
  IWDAP_COMBAT_ASSIST   Enabled by default for iwd-ch1 and iwd2-ch1. Each player character gets at least
                        24 base STR, DEX and CON and 64 base HP. Living PCs recover lethal and subdual
                        damage on starting or resuming the chapter and when combat ends.
                        To run without assistance, enter set IWDAP_COMBAT_ASSIST=0 in the same
                        Command Prompt before launching a new game. Boosts persist in assisted saves.
  AUTOPLAYER_SCENARIO   iwd_ch1 | iwd2_ch1 | easthaven | targos   (set by ieap.bat from its first argument)
  TP_AUTOEXEC           Python run at startup; ieap.bat sets it to start the autoplayer. Unset = normal game.
  TP_AUTOLOAD           a save to load at startup (ieap.bat: the SAVE argument, unless it is "menu")
  IWDAP_LOG             the driver's log file (ieap.bat: ieap-<scenario>.log next to ieap.bat)
  IWDAP_CH1_FROM        start the chapter driver at a later step, from a loaded save (TP_AUTOLOAD), e.g.
                        IWDAP_CH1_FROM=depart TP_AUTOLOAD=SlotAuto. Steps: see STEPS / STEPS2 in
                        tpdata\scr\iwd_ch1_driver.py
  IWDAP_MOVIES=1        play the intro/chapter movies instead of skipping them
  IWDAP_IGNORE_FOCUS=1  keep driving when the game window is not focused (otherwise it pauses while you are
                        in another window)

What to expect
--------------
  * The game starts, goes to the main menu, creates the party (pregenerated characters), and then plays.
    The party walks to speakers, area exits and combat targets. The camera follows the action.
  * Read ieap-iwd-ch1.log or ieap-iwd2-ch1.log beside the launcher. ASSIST reports boosts and healing.
    SIDEQUEST and SUMMARY report quest outcomes, including partial completion.
  * The chapter launcher can resume from an autosave after a crash or the last safe chapter checkpoint
    after a combat defeat. Checkpoint retries are limited.
  * When it is done, the game stays open on the last screen. Quit it normally (or close the window).

How to stop it
--------------
  Close the game window, or press Alt+F4 / Ctrl+Alt+Del -> Task Manager -> end TemplePlus.exe, then close the
  Command Prompt (or press Ctrl+C there) so ieap.bat does not relaunch it. If the ini was not restored (the
  console was closed first), copy %USERPROFILE%\Saved Games\TemplePlus\TemplePlus.ini.ieap-backup back over
  TemplePlus.ini.

It takes over the screen
------------------------
  While it runs it sends key presses and clicks to the game window (the in-game menu, the new-game screens, the
  party pool). Don't type or click into the game while it plays, and expect the game window to come to the front.
  Running it in a window, on a PC you are not using at the time, is the easiest way.

Source: https://github.com/DudeMcDude/toee_autoplayer (branch release/chapter1-autoplay-20261126). MIT licensed.

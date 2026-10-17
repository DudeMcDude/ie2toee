# Dialogue and scripts: IE DLG / BCS / TLK -> Temple+

Status: pilot. Works on classic IWD data; built to also read IWD:EE installs (see "Classic vs Enhanced Edition").
Same rule as the map converter: it runs on the player's machine, reads their own install, and writes the result
into their own ToEE module. The repository holds code only. Text, script logic, resource names and the generated
files are derived from the game and are never committed or distributed.

## Pieces

| file | role |
|---|---|
| `proto/iescript.py` | parsers written from the IESDP format pages: TLK V1, IDS, DLG V1.0, compiled BCS, and the text trigger/action syntax found inside DLG files. All of them produce one common AST (`Call`, `Obj`, `Sym`, `Point`) |
| `proto/ie_inventory.py` | counts which triggers, actions and object functions an install uses (BCS and DLG separately), so the runtime covers the common ones first |
| `proto/iecodegen.py` | AST -> Python 2.7 expressions that only call `ie_runtime`; resolves IDS symbols at convert time and collects variable names and strrefs |
| `proto/ie_dialogue.py` | converter CLI: DLG -> ToEE `.dlg` plus a per-NPC script, BCS -> `ie_bcs_<res>.py`, variable slot table, string table, area map table |
| `proto/runtime/ie_runtime.py` | the shared in-game library: variables, timers, triggers `T.*`, actions `A.*`, object resolution, action queue, script rounds |
| `proto/ingame_dialogue_probe.py` | developer probe: spawns converted NPCs on a test map, starts conversations, presses keys, runs area and creature scripts |

## Usage (player side)

```
python3 proto/ie_dialogue.py <IE install> <out> \
    --actor IDENT:AREA:SCRIPT_ID[:DLG][:BCS,BCS...]      # one per NPC
    --area-script AREA:BCS                               # area scripts
    --area-map AREA:TOEE_MAP[:canvas_x,canvas_y]         # for LeaveAreaLUA / coordinates (from <AREA>_objects.json)
    [--tlk path/dialog.tlk | --lang en_US] [--fallback opcodes.json] [--slot-base 1000 --slot-max 1999]
```

Copy `<out>/modules/ToEE/{dlg,scr}` and `ie_runtime.py` into the module. Script discovery runs before the module
folder is mounted, so a loose test install must put them in `modules/<Module>_core/` (or pack them into the module
DAT). Any `SCRIPT_ID` works (tested 993, 5000 and 12345 as `san_dialog`/heartbeat from `modules/ToEE_core/scr`).
If the files are in a folder that isn't mounted yet at discovery (e.g. loose `modules/ToEE/scr`), the engine logs
`Script: cache_add: ERROR: Failed to build script name: <id>` and the NPC does nothing; that message means
"script file not found", for any id, not an id limit.

## Mapping

### DLG -> ToEE dialogue

* Line numbers: state *i* becomes NPC line `(i+1)*stride`, and its transitions become the PC lines that follow it.
  `stride` is 10, or 100 when a state has more than 8 transitions. Dialogues reached through a transition into
  another DLG get appended with a +20000 base each. The speaker change is not modelled yet and gets logged in the
  report.
* NPC text uses the male/female ToEE fields. IE tokens become ToEE tokens: `<CHARNAME>`/`<GABBER>` -> `@pcname@`,
  and gendered tokens (`<PRO_HESHE>`, `<SIRMAAM>`, `<LADYLORD>`...) are expanded per gender field. Braces are
  escaped.
* A transition with no text becomes `[Continue]`, or `[End dialogue]` when it ends the dialogue. A state with no
  transitions gets an `[End dialogue]` line.
* Transition trigger -> ToEE `test` field `ie_c<line>(npc, pc)`. Transition action plus journal ->
  `effect` field `ie_a<line>(npc, pc)`. Both are generated functions in the NPC's script that call
  `rt.dlg_cond` / `rt.dlg_do`.
* Entry state: `san_dialog` calls `rt.dlg_start`. It checks the triggered states **in state-trigger-table order**
  (the order the IE engine uses, which differs from state order) and opens the first one that passes. If no
  triggered state passes, it falls back to the first untriggered root state. NumTimesTalkedTo counts up when the
  dialogue starts.
* The text comes from the player's TLK at convert time. With no TLK available, lines read `[strref N]`, so structure
  and logic can still be tested.

### BCS -> Python

* `ie_bcs_<res>.py` holds `BLOCKS = [(condition, [(weight, [actions])])]`. `rt.run_script` runs the IE script round:
  it evaluates the blocks top-down, runs one weighted-random response of the first true block, and only keeps
  evaluating when that response ends in `Continue()`. `OR(n)` groups are honoured.
* Creature scripts: the NPC's ToEE script (`py<id>ie_<ident>.py`) imports its BCS modules in IE priority order and
  ticks them from `san_heartbeat` (throttled to one round per second). `san_first_heartbeat` sets `OnCreation`.
  `san_dying` -> `Die`, `san_enter_combat`/`san_start_combat` -> `AttackedBy`. These are event triggers that the
  next round consumes.
* Area scripts: driven by `rt.loop(holder, 'area_<AREA>', AREA, [module])`, a real-time time event. In the pilot the
  holder is the party leader. For release, the converter should place an invisible holder object per map with a
  `san_heartbeat`.
* Action queue: actions run in order. Actions that take time (`Wait`, `MoveToPoint`, `AttackOneRound`...) return a
  duration, and the rest of the response resumes after it. While an actor is busy, its script rounds are skipped
  unless an event is pending (a simplification of IE interruption rules).
* Object references: `O(c, 'Myself' | 'Player1' | 'Protagonist' | 'LastTalkedToBy' | 'NearestEnemyOf', inner)`,
  `N(c, "scriptname")`, and `F(c, EA=...)` filters (only EA is honoured so far). Compiled BCS objects store the
  identifier chain innermost-first; the parser flips it to the text order.

### Variables, timers

* GLOBAL, LOCALS (per IE identity), `<AREA>` and `MYAREA` variables map to `game.global_vars` slots that the
  converter allocates (`ie_varslots.py`, default 1000-1999), so they persist in saves. Unallocated names fall back
  to memory and get logged.
* Timers keep their expiry time on a script clock. That clock is game time, plus real time while the Temple+ game
  clock stands still (outside combat, rest and travel the ToEE clock is frozen; the IE clock always runs). An unset
  timer counts as expired, as in the IE.

### Unsupported things

Unknown or unimplemented triggers log `IE_UNSUPPORTED trigger X -> False`. Actions log `IE_UNSUPPORTED action X`
and continue. Nothing raises into the game.

## Implemented so far (runtime)

Triggers: Global/GlobalGT/GlobalLT, BitGlobal, GlobalTimerExpired/NotExpired, TimerActive/Expired,
NumTimesTalkedTo/GT/LT, True/False, OnCreation, AttackedBy, HitBy, Die, Entered, Opened, Unlocked, Exists, Dead, See,
LOS, Range, Allegiance, HP/HPGT/HPLT, HPPercentLT/GT, PartyGoldGT/LT, PartyHasItem, HasItem, Gender, Race,
Class/ClassEx, Alignment, CheckStat/GT/LT (ability scores), NearLocation, NearSavedLocation.

Actions: Continue, NoAction, MultiPlayerSync, SetGlobal, IncrementGlobal, BitGlobal, SetGlobalTimer,
StartTimer/StartRandomTimer, SetNumTimesTalkedTo, Wait/SmallWait, SetDialogueRange, ClearAllActions, ActionOverride,
Dialog/StartDialog/StartDialogNoSet, StartStore (ToEE barter), Enemy, Attack, AttackOneRound, EscapeArea,
DestroySelf, AddXPVar/AddexperienceParty, GiveItem, GiveItemCreate, TakePartyItem, TakePartyGold, GiveGoldForce,
FloatMessage/DisplayString/DisplayStringHead, Face, FaceObject, MoveToPoint, MoveToObject, CutSceneId,
Start/EndCutSceneMode (logged), StartMovie (logged), HideCreature, ChangeEnemyAlly, LeaveAreaLUA/LeaveArea,
ReturnToSavedLocation.

Not done yet: spells (Spell, ForceSpell, HaveSpell, RemoveSpell), cutscenes, stores' contents, journal/quest UI,
item mapping data (`ie_items.py`: IE resref -> ToEE proto, guidance data), creature stats (CRE -> ToEE proto),
interjections and speaker changes, and IE interrupt semantics.

## Classic vs Enhanced Edition

* **TLK:** `find_tlk()` checks `<root>/dialog.tlk` (classic) first, then `lang/<locale>/dialog.tlk` (EE; `--lang`,
  default en_US). `dialogf.tlk` is supported through `female=True`. Both are TLK V1.
* **IDS:** opcode names and signatures always come from the install's own TRIGGER.IDS/ACTION.IDS (EE adds ids such
  as extra triggers and actions). The IESDP-derived fallback table is only for incomplete dev installs.
  Unknown opcodes keep their raw number (`Trigger_0x4xxx`, `Action_N`) and get logged.
* **BCS objects:** 12 ints for IWD/BG2/EE (EE may append fields, which are ignored); PST layout auto-detected (14).
  IWD2 still needs checking.
* **DLG:** EE transition flags bit 9 (immediate actions) and bit 10 (clear actions) are parsed but not yet acted on.
* **Resources:** EE keeps BIFs uncompressed under `data/`, and overrides in `override/`. `iefs` resolves both
  layouts.

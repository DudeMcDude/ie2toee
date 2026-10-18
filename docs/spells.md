# Spells: IE SPL → Temple+ spells

Status: **prototype**. The SPL / PRO / EFF parser, the spell survey, the guidance table, the converter and the
Temple+ runtime are written for classic Icewind Dale (`iwd/IWD`) and IWD:EE (`iwd/IWDEE`). In game, a converted NPC
casts mapped spells on request (ForceSpell, Spell) and a converted creature's own IE combat script casts a spell on
its combat turn. Both were tested in the first town area (AR1001) on the classic install.

As with creatures, every input is read on the player's machine from their own installs. Survey reports, the
generated `ie_spellmap.py`, spec modules and screenshots stay local (`out/`, git-ignored). The repository ships code, the
rules as options, and an authored table of identifiers (see "What guidance data may contain").

## Pieces

| file | role |
|---|---|
| `proto/iespl.py` | SPL V1 reader (header, extended headers, feature blocks, casting effects), PRO reader (type, AoE section: trigger/explosion radius, cone flag), EFF V2 reader, ITM ability effects. Written from IESDP. |
| `proto/ie_spells.py` | `survey` (counts, uses, opcode frequency), `coverage` (how much of what the game uses maps), `convert` (writes `ie_spellmap.py` for the runtime), `TPSpells` (reads the Temple+ spell rules from the player's ToEE + Temple+ install), `SpellMapper`, and `SPELL_OPTIONS` (SPL-ADJ-1 … 18) |
| `proto/guidance/spells_iwd.json` | authored table: IE resref → mapping class and Temple+ spell enum, per flavour (classic / EE) |
| `proto/ie_creatures.py` | `npc_spells()` turns a CRE's known / memorised spells into a Temple+ spell list (`spells`) and a custom AI strategy (`ai_strategy`) |
| `proto/iescript.py` | spell arguments in triggers/actions resolve through SPELL.IDS; EE `…RES` actions carry the resref |
| `proto/runtime/ie_spellrt.py` | Temple+ side (Python 2.7): grants spell lists, keeps IE memorisation counts, casts (`cast_spell`) for Spell / ForceSpell / ReallyForceSpell / ApplySpell and the *Point forms |
| `proto/runtime/ie_runtime.py` | IE actions `Spell`, `SpellNoDec`, `ForceSpell(Range)`, `ReallyForceSpell(Dead)`, `ApplySpell`, `SpellPoint(NoDec)`, `ForceSpellPoint(Range)`, `ReallyForceSpellPoint` (+ `…RES`), trigger `HaveSpell(RES)`; `combat_tick` runs one IE script round per combat turn |
| `proto/ingame_spells_probe.py` | in-game test: spawns an area's creatures with their spells, makes them cast, turns one hostile, logs hp / conditions, screenshots |

## Format notes (IESDP)

* **SPL V1** header (0x72 bytes): name strref 0x08, flags 0x18, type 0x1c (0 special, 1 wizard, 2 priest, 3 psionic,
  4 innate, 5 bard song), exclusion flags 0x1e (classic IWD: bit 30 druid only, bit 31 cleric only), school 0x25,
  secondary type 0x27, level 0x34, extended headers at 0x64 (count 0x68), feature blocks 0x6a, casting effects
  0x6e / 0x70.
* **Extended header** (0x28 bytes): target 0x0c, range 0x0e, minimum caster level 0x10, casting time 0x12, effect
  count / index 0x1e / 0x20, projectile 0x26 (PROJECTL.IDS value + 1). A spell has one header per caster-level band.
* **Effects** are EFF V1 blocks (0x30 bytes), the same as in CRE / ITM.
* **PRO**: type at 0x08; area projectiles have an AoE section at 0x200 (flags, trigger radius, explosion radius;
  radius in feet ≈ value / 17; flag bit 11 = cone). Classic IWD ships no PRO files (projectiles are built in).
* **Opcodes**: classic IWD uses the IESDP *iwd1totl* numbering; EE uses the bgee numbering. Spell-calling opcodes
  (cast 146 / 148, learn 147, innate 171 / 172, EE 232 / 234 / 256 / 258 / 260 / 326 / 333 / 341 / 344) and EFF-calling
  opcodes (177, EE 183 / 248 / 249 / 272 / 283) are followed when counting use.
* **SPELL.IDS** numbers map to resrefs by convention: 1xxx → `SPPR`, 2xxx → `SPWI`, 3xxx → `SPIN`, 4xxx → `SPCL`, plus
  the last three digits.
* **Classic and EE numbering diverge.** The same resref is often a different spell in the two games. The guidance table is therefore keyed per flavour, and
  `ie_spells.flavor()` detects the flavour (EE installs have a `lang/` directory).

## Survey (local: `out/spell_survey.md`, `.json`)

`python3 proto/ie_spells.py survey iwd/IWD iwd/IWDEE --md out/spell_survey.md --json out/spell_survey.json`

"Used" means a spell is reached from a creature's spell list, a script or dialog action/trigger, an item ability,
or another used spell. "Player" means castable by a party member (priest spells on the class lists, wizard spells
with a scroll).

| | classic IWD | IWD:EE |
|---|---|---|
| SPL files | 331 (wizard 155, priest 92, innate 70, special 14) | 1225 (innate 520, wizard 366, priest 301, special 26, bard song 12) |
| used | 249 | 535 |
| player-castable | 198 | 392 |
| used ∪ player | 258 | 596 |
| used per source: creature lists / scripts / dialogs / items / scrolls | 132 / 167 / 0 / 158 / 107 | 195 / 307 / 51 / 312 / 227 |

The most used spells are cures, hold and silence effects. The most frequent opcodes are cosmetic (sound, visual, icon,
string), then damage and spell immunity.

## Mapping

Each IE spell gets one mapping class in the guidance table:

| class | meaning | runtime |
|---|---|---|
| `direct` | same spell in 3.5 / Temple+ | cast the Temple+ spell |
| `close` | a Temple+ spell with nearly the same effect (renamed, or level / area differs) | cast the Temple+ spell |
| `new_srd` | an SRD spell Temple+ does not implement yet | unmapped for now (logged) |
| `new_unique` | an IWD-only spell, with no 3.5 equivalent | unmapped for now; plan below |
| `innate` | creature ability / item power (breath, gaze, aura) | unmapped unless authored; SPL-ADJ-7 |
| `meta` | technical spell (cutscene, script helper, visual) | ignored |
| `sub` | sub-spell, only reached from another spell | follows its parent |

The lookup order is guidance (per flavour), then a name match over the Temple+ spells (CM rename list), restricted to
spells Temple+ actually implements. Summons are re-mapped by level (SPL-ADJ-4).

Guidance entries: classic 261 (direct 111, close 59, innate 39, new_unique 23, new_srd 23, sub 3, meta 3), EE 693
(innate 177, direct 167, close 127, new_unique 79, new_srd 66, sub 56, meta 21).

### Coverage (direct + close, `out/spell_coverage.json`)

| flavour | player spells | used spells | used, weighted by use | in creature lists | cast by scripts |
|---|---|---|---|---|---|
| classic | 78.8 % | 66.7 % | 76.8 % | 81.2 % | 81.1 % |
| EE | 67.6 % | 49.1 % | 72.6 % | 73.8 % | 73.1 % |

EE has many more innate and script-helper spells. Counting the `innate` entries that have a Temple+ equivalent raises
EE to 53.4 % of used spells (77.2 % weighted, 81.0 % of script casts).

## Runtime

* **Conversion.** `ie_spells.py convert <IE> <out> --toee <ToEE> --tp <Temple+>` writes `ie_spellmap.py`
  (`MAP[resref] = {t: spell enum, c: class, ty: IE type, l: IE level, lv: Temple+ class levels, ai: ai_type}` plus
  `OPTIONS`). `ie_creatures.py convert … --tp` adds `spells` and `ai_strategy` to each creature spec.
* **NPC spell lists.** When the critter spawns, `ie_critters.apply` calls `ie_spellrt.give_spells`. Each spell is
  added as known plus its IE memorised count, under the NPC's casting class. A creature without a matching class
  gets `domain_special` (spell-like abilities, caster level = hit dice). The custom Temple+ strategy is built from the
  list in this order: self-buffs, heals on a hurt friend, offensive spells and summons at the closest enemy, then
  potion and melee. It names each Temple+ spell once.
* **Script casting.** IE `Spell(target, SPELL)` needs the spell memorised and spends one copy, as in the IE.
  `HaveSpell` checks the IE count and the Temple+ slot, so a slot the Temple+ AI already used counts as gone.
  `ForceSpell` and `ReallyForceSpell` grant the spell for the cast (SPL-ADJ-17). `ApplySpell` makes the target cast the
  spell on itself. The *Point forms target the creature nearest the point, or else the caster.
* **Combat turns.** See *Combat rounds* below. In short, the IE script decides each turn from `san_start_combat`.
  Each Spell or Attack is checked against the engine first. The converted static strategy is used only when no block
  is feasible.

## Combat rounds (`san_start_combat`)

### How Temple+ runs an NPC turn

1. `combat.cpp` (Subturn, non-player actor) calls `san_start_combat(attachee, attachee)` at the start of each turn.
2. If the script returns `SKIP_DEFAULT` (0), the engine logs "Skipping AI Process" and calls `CombatAdvanceTurn`, so
   the NPC does nothing more that turn. Anything the script queued without performing is lost.
3. Otherwise `AiProcess` runs:
   * `AiPacket` may first pick a random offensive, defensive or heal spell, by the `ai_params.mes` spell chances.
     That route goes to `AiStrategDefaultCast`.
   * If no spell is picked, the route is `StrategyParse`.
4. `StrategyParse` first calls the Python hook `d20_ai.combat_strategy.execute_strategy(obj, target)`. If the hook
   returns an int, it decides the turn.
5. Otherwise it loops over the tactics of the critter's `obj_f_critter_strategy`. The first tactic that succeeds is
   performed.
6. If none succeeds, it falls back to `Default` (melee or DefaultCast).
7. `AiStrategDefaultCast` also runs the strategy's tactics first, and casts its own spell only if all of them fail.
8. A script can install a per-turn strategy with `obj.ai_strategy_set_custom([name, tac, mid, spell, ...], 0)`. The
   Temple+ extra tactics include `target obj` (object id in the middle field), `cast single` (spell code
   `"'Name' class_x lvl"`), `five foot step`, `approach`, `attack`, `total defence` and `stop`. `stop` always
   succeeds and does nothing, which ends tactic evaluation.

### Anatoliy Savchak's start-combat framework (reference only, not vendored)

Repos surveyed under [github.com/anatoliy-savchak](https://github.com/anatoliy-savchak) (fan-made module
conversions):

* toee.zmod.iwd2, toee.zmod.forge, toee.zmod.skirmish, toee.zmod.falcons_hollow,
  ToEE.ZMOD.ShatteredGatesOfSlaughtergarde, toee.zmod.rev and toee.zmod.coe.
* coe, rev and Slaughtergarde have the early form (a ~180-line `ctrl_behaviour.py`, no `ait/`).
* The most developed form is in **toee.zmod.forge**:
  * Last commit 2022-10-13.
  * `utils_npc_spells_tactics.py` is 450 lines, against 410 in iwd2 and 154 in skirmish and falcons_hollow.
  * Its `ait/` package is identical to the iwd2, skirmish and falcons_hollow copies.
* iwd2 also has an IE-script layer (`inf_scripting.py`, `ctrl_behaviour_ie.py`), but its combat `Attack` and `Spell`
  actions are not implemented. The design here follows forge.

Files in [toee.zmod.forge `src/zmod_forge_core/scr`](https://github.com/anatoliy-savchak/toee.zmod.forge/tree/main/src/zmod_forge_core/scr):

* [`ctrl_behaviour.py`](https://github.com/anatoliy-savchak/toee.zmod.forge/blob/main/src/zmod_forge_core/scr/ctrl_behaviour.py)
  * Module-level `san_start_combat` gets the critter's controller (`CtrlBehaviour.get_from_obj`) and calls
    `start_combat`.
  * `CtrlBehaviourAI.start_combat` returns `SKIP_DEFAULT` for a dying, unconscious, helpless, stunned or held critter,
    or one with no hourglass actions left.
  * Otherwise:
    * `tactics_recon` gathers foes that are adjacent, threatening, sensed, in LOS and approachable
      (`can_find_path_to_obj` / `find_path_to_obj`), plus reach and whether the critter can move out.
    * `tactics_process_critical` handles healing at 0 HP and coup de grace.
    * `create_tactics` / `create_tactics_default2` choose what to do.
    * `set_strategy` installs the result, then the function returns `RUN_DEFAULT`.
  * `create_tactics_default_melee` ends with `add_total_defence()` and `add_stop()`, commented "otherwise default T+
    AI will be working".
  * `on_execute_strategy` is a hook installed into `d20_ai.combat_strategy.execute_strategy` by
    [`combat_strategy_hooks.py`](https://github.com/anatoliy-savchak/toee.zmod.forge/blob/main/src/zmod_forge_core/scr/combat_strategy_hooks.py).
* [`utils_npc_spells_tactics.py`](https://github.com/anatoliy-savchak/toee.zmod.forge/blob/main/src/zmod_forge_core/scr/utils_npc_spells_tactics.py)
  * `SpellTactic.execute` returns `EDOT_*` codes: `OK`, `NO_SPELLS_LEFT`, `TARGET_TOO_FAR`, `CANNOT_BE_AFFECTED`,
    `CANNOT_CAST_VERBAL`, `CANNOT_CAST_SOMATIC`, `TARGET_TOO_FAR_FOR_APPROACH`. It checks:
    * spells left;
    * "already affected" (`_check_already`: a query, or the spell condition, on the target);
    * component inhibition (`_check_uninhibited`);
    * range from `tpdp.SpellEntry`, approaching when the gap is within movement.
  * Only then does it add five-foot step or approach, `target obj` or `target self`, and `cast single`.
  * Subclasses (Hold Person, Bless, ...) set the "already affected" checks.
* [`utils_npc_spells.py`](https://github.com/anatoliy-savchak/toee.zmod.forge/blob/main/src/zmod_forge_core/scr/utils_npc_spells.py):
  `NPCSpells` keeps per-NPC spell counts. `prep_spell` decrements the count, memorises the spell and returns the
  `cast single` code. This is the state that the static strategy lacks.
* [`utils_tactics.py`](https://github.com/anatoliy-savchak/toee.zmod.forge/blob/main/src/zmod_forge_core/scr/utils_tactics.py):
  `TacticsHelper` builds the tactic triplets (`add_target_obj`, `add_cast_single_code`, `add_five_foot_step`,
  `add_approach`, `add_attack`, `add_total_defence`, `add_stop`, ...). `set_strategy` calls
  `ai_strategy_set_custom(list, 0)`.
* [`utils_npc.py`](https://github.com/anatoliy-savchak/toee.zmod.forge/blob/main/src/zmod_forge_core/scr/utils_npc.py):
  reach, could-be-attacked and can-sense helpers.
* [`ait/tactition.py`](https://github.com/anatoliy-savchak/toee.zmod.forge/blob/main/src/zmod_forge_core/scr/ait/tactition.py):
  `TacticBase` (assess, check prerequisites), `TacticOutcome`, `TacticManager` (reachable spots via `tpai.PathQuery`,
  action budget) and `StrategyBase`. This is outcome scoring, which is not used here.

### ie2toee design (`proto/runtime/ie_combat.py`, `ie_runtime.combat_round`)

1. **Entry.** The generated actor script's `san_start_combat` raises `AttackedBy` and returns
   `rt.combat_round(attachee, IDENT, AREA, SCRIPTS)`.
2. **Skip states.** `ie_combat.round_start` follows Anatoliy's skip list. A dying, unconscious, helpless, stunned or
   held critter, or one with no actions left, returns `SKIP_DEFAULT`.
3. **One IE script round.** The blocks are evaluated top-down, as in the IE. When a block's trigger is true, its
   response is first dry-run:
   * Spell and Attack actions only run their feasibility checks.
   * Other actions are no-ops.
   * If any check fails, the log gets `BLOCK <ident> #n not feasible: <action>: <reason>` and evaluation goes on to
     the next block, as if the trigger had been false.
   * Otherwise the response runs for real, with Spell and Attack *planned* instead of executed.
4. **Feasibility checks** (`Round.check_spell` / `check_attack`, reason codes modelled on `EDOT_*`):
   * the IE memorised count and the engine slot (`can_cast_spell` on a memorised store);
   * target dead;
   * verbal component under Silence;
   * somatic component while grappled or helpless;
   * already affected: an offensive spell on a target that already has that spell's condition, or is held or helpless;
     a buff that is already on the target;
   * heal on a target at full HP;
   * range from `tpdp.SpellEntry`, approaching when the gap is within movement and a path exists;
   * line of sight, approaching when a path exists;
   * attack: LOS for ranged weapons; reach, or a path plus the ability to move, for melee.
5. **Plan.** The first planned action becomes the per-round strategy, installed with
   `ai_strategy_set_custom(['ie2toee_r<n>', ...], 0)`, and the function returns `RUN_DEFAULT`:
   * `target obj <id>` plus `approach` (or `five foot step` when threatened);
   * then `cast single` with the spell's Temple+ name, class and level, or `attack`;
   * then `total defence` and `stop`.

   Temple+ then performs exactly that sequence.
6. **State per critter** (`ie_combat.STATE`):
   * rounds;
   * a history of (round, action, reason);
   * casts by (spell, target) and round;
   * the IE spell counts and engine slots (`ie_spellrt`).
7. **Fallback.** With no feasible block, the converted static strategy is installed for the round, also ending in
   `total defence` and `stop`:
   * Its casting entries are removed: all of them under `script_first`, otherwise the ones the critter cannot cast.
   * What remains is target selection, potion, melee and approach.
8. **The DefaultCast gap, closed without an engine change.**
   * Every per-round list ends in `stop`, so neither `StrategyParse`'s `Default` nor `AiStrategDefaultCast`'s own
     spell is reached.
   * When `AiPacket` picks a random spell, `AiStrategDefaultCast` runs our list first, and `stop` succeeds.
   * In the in-game logs there is no "trying DefaultCast" and no unplanned spell is debited.
9. **Out-of-combat ticks.**
   * While combat is active, the heartbeat no longer runs a critter's script.
   * A hostile (KOS) creature whose chosen response contains Spell or Attack defers it to the first combat round
     (`DEFER` in the log), instead of casting before initiative.
   * `AttackedBy` and `HitBy` now last one script round. Left pending, they bypassed the busy check and caused a
     double heal cast.

### In-game test (AR1001; local only)

Run by `spells_ar1001` in `out/local_tests.sh`. It uses a private overlay, wine prefix and Xvfb display, and the
`feature/ie-dialog-skin` Temple+ build with the classic `iwd` dialog skin.

* A converted priest NPC casts *Bless* on the party leader through `ForceSpell`.
* A second converted priest casts *Cure Moderate Wounds* on the wounded leader through `Spell`. The IE
  memorised count drops by one.
* That NPC is turned hostile (`Enemy()`), with a real classic IWD cleric AI script attached. On its combat turn the
  script's first block (`HaveSpell` + `See(NearestEnemyOf(Myself))`) fires. It casts *Hold Person* on the leader,
  Temple+ debits the slot, and the held leader's turn ends. Afterwards `HaveSpell` is false.
* Combat rounds, classic:
  * Round 1: `IE script -> cast` *Hold Person* (planned, then performed by Temple+, one slot debited).
  * Rounds 2-3: `HaveSpell` is false, so the attack block plans `attack`.
  * The non-scripted priest uses the fallback (no casting, ends in `stop`). No DefaultCast and no other spell is
    debited.
* Fall-through, classic: the leader is already paralysed (helpless). Each round the *Hold Person* block is logged
  `not feasible: ALREADY_AFFECTED`, and evaluation falls through to the attack block. The slot is kept.
* EE (`iwdee` dialog skin), with an EE cleric combat script on the converted priest:
  * Round 1: the attack block.
  * After it is wounded below 50 %, round 2 plans *Cure Moderate Wounds* on itself (a `Continue()` block) and Temple+
    casts it (7 → 18 HP).

## SPL-ADJ: adjudication list

Every entry is a key in `ie_spells.SPELL_OPTIONS`. Switch it per run with `--option key=value`. The defaults are the
recommendations.

| # | question | options | recommendation |
|---|---|---|---|
| SPL-ADJ-1 | rules of a mapped spell | `35` run the Temple+ spell as-is; `ie_numbers` patch IE damage/duration in | **35**. The mapped spell is the 3.5 spell; IE numbers only matter for new spells. |
| SPL-ADJ-2 | how spells are matched | `guidance` authored table, then name match; `name` | **guidance**. Name matching alone mis-maps renamed and renumbered spells. |
| SPL-ADJ-3 | slot level | `toee` the 3.5 level of the mapped spell; `ie` | **toee**, so Temple+ slot tables stay valid. |
| SPL-ADJ-4 | Monster / Animal Summoning N | `by_level` Summon Monster / Summon Nature's Ally of the same spell level; `by_name` (CM list) | **by_level**. CM's name mapping lands on the wrong 3.5 levels. |
| SPL-ADJ-5 | NPC spell lists | `cap_level` keep the IE list, drop spells above the NPC's 3.5 maximum level; `keep_ie`; `fit_slots` | **cap_level**. `fit_slots` (trim to the 3.5 per-day table) is closer to RAW but removes many encounter spells. |
| SPL-ADJ-6 | caster level | `class` the CM-converted class level, hit dice for monsters; `ie` | **class** |
| SPL-ADJ-7 | innate abilities | `domain_special` Temple+ spell-like abilities with the IE uses per day; `skip` | **domain_special** |
| SPL-ADJ-8 | spells that strip magical protections | `dispel` Dispel Magic / Greater Dispelling; `new` port them | **dispel**. 3.5 has no spell-protection layer to strip. |
| SPL-ADJ-9 | saves of new spells | `by_effect` Fort / Ref / Will from what the effect does; `by_category` (2e category) | **by_effect** |
| SPL-ADJ-10 | save DC of new spells | `35` 10 + spell level + ability modifier; `ie_bonus` add the IE save bonus | **35** |
| SPL-ADJ-11 | durations of new spells | `rounds` IE seconds / 6 = rounds, 2e turn = 3.5 minute; `hours_kept` | **rounds** |
| SPL-ADJ-12 | damage of new spells | `35_by_level` cap dice like 3.5 spells of that level (5/5/10/10/15/15/20…); `ie` | **35_by_level** |
| SPL-ADJ-13 | spell resistance of new spells | `from_ie_flags` SR applies when the IE effects can be resisted; `always` | **from_ie_flags** |
| SPL-ADJ-14 | level / list of IWD-unique spells | `ie` keep the IE level and class list; `review` flag each for hand balancing | **ie** for the first pass, then `review` per spell |
| SPL-ADJ-15 | schools | `renamed` alteration → transmutation, invocation → evocation, healing → conjuration; `ie` | **renamed** |
| SPL-ADJ-16 | casting time | `standard` standard action; IE casting time 10 (1 round) → full round; `ie_speed` | **standard** |
| SPL-ADJ-17 | `ForceSpell` / `ApplySpell` by a caster that lacks the spell | `force_known` grant it for the cast; `fail` | **force_known**. That is what the IE does. |
| SPL-ADJ-18 | creature with its own spell-casting IE script | `script_first`: the IE script picks spells each combat round (feasibility-checked, see *Combat rounds*); the static fallback strategy has no casting. `strategy`: the fallback keeps the castable spells | **script_first**. With `strategy`, the Temple+ AI spends the slots the script expects. |

## What guidance data may contain

The repository may only ship material we author. `spells_iwd.json` holds, per flavour:
* IE spell resrefs (identifiers of the file set);
* the mapping class;
* the Temple+ spell enum (a number in the player's Temple+ install);
* for mapped spells, the **Temple+** spell's own name as a label.

It does not contain IE spell names, descriptions, numbers (damage, durations, levels) or any other text from either
game. The authoring helpers that read IE names to produce the table are kept local and are not committed.

## Plan: IWD-unique spells as new Temple+ spells

Ranked by use in the survey (creature lists + script casts + items; the counts stay in the local survey). Resrefs are given for classic / EE. Sketches use
our own wording, are 3.5-style, and are not final.

| rank | resref (classic / EE) | type, level | sketch |
|---|---|---|---|
| 1 | `sppr412` / `sppr420` | priest 4, self | Charged aura. For 1 round / level, a bolt strikes one hostile creature within 30 ft each round: 1d6 electricity per 2 caster levels (max 10d6), Reflex half, SR yes. Begin-round hook on a caster condition. |
| 2 | `spwi417` / `spwi422` | wizard 4, one creature | Necromantic damage over time. The target takes fire damage each round for 1d4+1 rounds, Fortitude negates, SR yes. Condition with a per-round damage hook. |
| 3 | `spwi119` / `spwi119` | wizard 1, one creature | Minor drain. Touch-range ray: 1d4 + 1 / 2 levels (max +5) negative damage; the caster gains the same as temporary hit points for 1 hour. |
| 4 | `spwi318` / `spwi327` | wizard 3, one creature | Cold lance. Ranged touch: 1d6 / level cold (max 10d6); Fortitude or stunned 1 round. |
| 5 | `sppr310` / `sppr310` | priest 3, one creature | Spellcasting disruption. Will negates: the target's spells fail 50 % (arcane and divine) for 1 round / level. Uses the spell-failure dispatcher. |
| 6 | `spwi220` / `spwi204` | wizard 2, point | Cold burst. 10 ft radius: 1d4 cold / 2 levels (max 5d4), Reflex half. A small-area evocation template. |
| 7 | `sppr511` / `sppr518` | priest 5, allies around caster | Battle fervour. Allies within 30 ft: +2 morale to attack and damage, 1d8 + 1 / level temporary hp, immune to fatigue; 1 round / level. |
| 8 | `spwi511` / `spwi524` | wizard 5, one creature | Fire shroud. The target is wreathed in flame: 2d6 fire per round to it and to creatures adjacent to it, Reflex half each round; ends early if extinguished (dispel or water). |
| 9 | `spwi610` / — | wizard 6, self | Necrotic touch. The caster's hands become a melee touch weapon: 1d10 + 1 / 2 levels negative damage, Fortitude or paralysed 1d4 rounds; 1 round / level. |
| 10 | — / `spwi515` | wizard 5, area | Revealing burst. Dispels illusions and invisibility of a chosen school on all creatures within 30 ft (caster-level check like Dispel Magic). |

Implementation order: 1–4 first. They cover most of the use in both flavours and need only damage, condition and
targeting hooks that Temple+ spell scripts already use. Each new spell is a Temple+ spell file plus a `Spell<enum>.py`
script in an `ie2toee` spell range. Its guidance class then becomes `direct`, pointing at the new enum.

## Open items

* `new_srd` spells: SRD spells Temple+ does not implement yet (classic 23, EE 66). Unmapped until they are written.
* `new_unique` spells (classic 23, EE 79): see the plan above. None are implemented yet.
* `innate` abilities need per-ability authored mappings (breaths, gazes, auras).
* *Point targeting picks the critter nearest the point. Real location targeting needs a Temple+ `cast_spell` at a
  location.
* `HaveSpell` / `Spell` counts track only lists given by conversion. Spells a script adds with `AddSpell`-type actions
  are not tracked yet.
* IWD:EE data marks some NPCs as class `INNOCENT` (155) even though their CRE has priest spells. They convert as
  commoners and cast through `domain_special` (caster level = hit dice).
* The Temple+ strategy uses the converted list as-is; it has no IE-like target selection (e.g. "cast Silence at
  the nearest spellcaster").
* The DefaultCast gap is closed by the per-round strategies that end in `stop` (see *Combat rounds*). Outside
  combat, Temple+'s real-time `AiPacket` heal and buff picks can still fire for non-hostile NPCs.
* Not adopted from Anatoliy's framework:
  * the `ait/` outcome scoring (comparing several feasible actions);
  * the `execute_strategy` hook.

  IE scripts already give a priority order, so the first feasible block wins.
* "Already affected" for an offensive spell relies on the Temple+ condition named `sp_<Spell Name>`. Spells whose
  condition is named differently are only caught by the held/helpless check.
* *Point spells still target the nearest creature.
* EE has no counterpart of the classic cleric combat script used in the test. The EE run uses another EE cleric
  combat script.
* In the test, an NPC of the same faction joins when its neighbour turns hostile (ToEE faction rules, not IE
  `Enemy()` semantics).

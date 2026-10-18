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
* **Combat turns.** ToEE runs `san_start_combat` on each NPC turn. The generated actor script runs one IE script round
  there. If the round cast a spell, it returns `SKIP_DEFAULT`, so Temple+ AI does not also act. If the creature's own
  script casts spells (`CASTS` in the generated module), its Temple+ strategy keeps only potion and melee
  (SPL-ADJ-18), and the script decides what to cast.

### In-game test (classic, AR1001; local only)

Run by `spells_ar1001` in `out/local_tests.sh`. It uses a private overlay, wine prefix and Xvfb display, and the
`feature/ie-dialog-skin` Temple+ build with the classic `iwd` dialog skin.

* A converted priest NPC casts *Bless* on the party leader through `ForceSpell`.
* A second converted priest casts *Cure Moderate Wounds* on the wounded leader through `Spell`. The IE
  memorised count drops by one.
* That NPC is turned hostile (`Enemy()`), with a real classic IWD cleric AI script attached. On its combat turn the
  script's first block (`HaveSpell` + `See(NearestEnemyOf(Myself))`) fires. It casts *Hold Person* on the leader,
  Temple+ debits the slot, and the held leader's turn ends. Afterwards `HaveSpell` is false.

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
| SPL-ADJ-18 | creature with its own spell-casting IE script | `script_first` the IE script picks spells, Temple+ AI keeps potion / melee; `strategy` both | **script_first**. With `strategy`, the Temple+ AI spends the slots the script expects. |

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
* With `script_first`, the Temple+ AI still falls back to its built-in *DefaultCast* when its melee tactics fail (e.g.
  no path to the target), so a scripted caster can still cast an unscripted spell. A strategy-level "no casting" flag
  (Temple+ side) would close this.
* In the test, an NPC of the same faction joins when its neighbour turns hostile (ToEE faction rules, not IE
  `Enemy()` semantics).
* EE in-game run: the conversion is done for both flavours, but only classic was run in game so far.

# Creatures: IE CRE → ToEE / Temple+ critters

Status: **prototype**. The CRE parser, the area survey, the converter and the Temple+ runtime spawner are written,
and the actors of the first town area (AR1000) are converted and placed in game for both the classic and the Enhanced
Edition installs. This document describes the design, the rules, and every judgement call the conversion makes.

All game data is read on the player's machine from their own installs. Nothing this pipeline produces is
distributed: names, stats, survey reports, generated spec modules and `.mes` files stay local, like the converted
maps and dialogues. What the repository ships is code plus **authored** mapping rules (see "What guidance data may
contain").

## Pieces

| file | role |
|---|---|
| `proto/iecre.py` | CRE reader (V1.0 BG/IWD:EE, V9.0 classic IWD; V2.2 IWD2 is detected and rejected for now), with embedded effects (EFF V1 / V2), the item table, the 40-word slot table, and a small ITM reader (flags, type, enchantment, equip effects). Written from IESDP. |
| `proto/ieformats.py` | ARE actors (incl. dialog/script overrides, embedded CREs), spawn points, rest interruptions |
| `proto/ie_rules.py` | AD&D 2e → D&D 3.5 rules, one function per rule, with an options dict for every judgement call (`DEFAULT_OPTIONS`, ADJ-1 … ADJ-14) |
| `proto/guidance/creatures_iwd.json` | authored guidance table: creature families → ToEE model / template proto ids, item type → ToEE item proto, class-based humanoid rules |
| `proto/toeedata.py` | reads the player's ToEE install (TIG `.dat` archives + loose files): `protos.tab`, `meshes.mes`, `spell_enum.mes` |
| `proto/ie_creatures.py` | `survey` (every creature used by areas, rest spawns and `CreateCreature*` calls in scripts/dialogs) and `convert` (an area's actors → spawn specs + name `.mes`, and `--actor` args for `ie_dialogue.py`) |
| `proto/runtime/ie_critters.py` | Temple+ (Python 2.7) spawner: creates a template proto and applies the converted stat block |
| `proto/ingame_creatures_probe.py` | in-game test: spawns an area's creatures, logs their computed stats, lines them up, takes screenshots, talks to them |

```
python3 proto/ie_creatures.py survey <IWD dir> [<IWD:EE dir>] --md out/creature_survey.md --json out/creature_survey.json
python3 proto/ie_creatures.py convert <IE dir> <ToEE dir> out/creatures_X --area AR1000 --script-base 1100
python3 proto/ie_dialogue.py <IE dir> out/creatures_X/dialogue $(cat out/creatures_X/dialogue_actors.txt) --area-script AR1000:ar1000
```

## Format notes (IESDP)

* V1.0 and V9.0 share the header up to 0x270. V9.0 then inserts 0x68 bytes (visibility flag, extra death variables,
  saved location), so the IDS bytes (EA, general, race, class, specific, gender, alignment) and every section offset
  move by +0x68. The dialog resref is at 0x2cc (+0x68).
* The slot table is always 40 words: 38 slots, then the selected weapon and its ability. In both IWD variants the
  item table comes *before* the slot table in the file, so "slot table size = items offset − slots offset" is wrong.
* Classic IWD CREs have no embedded effects. Monster abilities (regeneration, resistances, weapon immunity, minimum
  HP) come from **non-droppable equipped items** (ITM flags bit 2 clear). The converter folds the equip effects of those
  items into the creature. Droppable items are real gear and become ToEE items. IWD:EE also embeds effects
  (mostly opcode 233, proficiencies).
* Classic IWD and IWD:EE use **different animation ids** for many creatures (e.g. goblins). The guidance table
  therefore keys families by `classic` and `ee` id lists separately.
* Classic `ANIMATE.IDS` names contain spaces, so parse whole lines.
* IWD has no ARE spawn points; random encounters are rest interruptions (ARE 0xc0, 0xE4 bytes each). Classic
  scripts mostly reveal pre-placed hidden actors (`HideCreature`) rather than calling `CreateCreature`; EE scripts
  create far more. The survey counts both.

## Two tracks

**Track A, monsters.** The animation id picks a *family* from the guidance table, for example "goblin", "ice troll"
or "ghoul". The family names a ToEE model, plus a preferred vanilla template proto with that model. When the
preferred proto is absent (a Co8-only proto, say), the first vanilla proto using the model is taken. By default
(ADJ-13 `srd`) the template keeps its SRD ability scores, type, natural attacks, feats and CR. From the CRE we take:
* hit dice (IE level, never below the template's),
* HP (ADJ-4),
* morale,
* faction/hostility from EA,
* resistances, MR and weapon immunities, as Temple+ monster conditions,
* gear,
* a natural-armour override when the IE AC is clearly better.

This is what the Conversion Manual tells DMs to do with monsters: use the *Monster Manual* creature that is closest
(CM p.20–22).

**Track B, NPCs and class-based humanoids.** Animations in the IE character ranges (0x5000–0x6fff, peasants and
townsfolk 0xc000+) are humans, elves, dwarves and the like, with a PC class. We convert them by formula, following
the CM's character conversion:
* class and levels (multiclass per CM p.3),
* abilities including exceptional strength (CM p.3–4),
* BAB and saves from the 3.5 class tables, cross-checked against THAC0 and 2e saves (ADJ-5/6),
* HP (ADJ-4),
* AC from equipped armour plus a natural/misc bonus (CM p.11, p.21),
* alignment, gender, and race. The race picks the template proto (vanilla human/elf/dwarf/… villager protos) and
  the model scale.

Unarmoured townsfolk get ToEE peasant garb and boots. Without them the ToEE body model renders unclothed.

The engine side is the same for both tracks. We spawn the template proto and set the stat block at runtime
(`ie_critters.apply`). No proto rows are generated, so there is no 1000-proto NPC limit and no conflict with
other mods. Generating `rules/protos/ie2toee_*.tab` rows by copying the template row is a straightforward later
option if pre-placed (MOB) critters are wanted.

## Rules (Conversion Manual references)

The *D&D 3rd Edition Conversion Manual* (Wizards of the Coast, 2000) is the reference throughout. We cite it by
page. Nothing from it is copied into data files; the rules below are re-stated in our own words and implemented as
code in `ie_rules.py`.

| topic | rule | CM |
|---|---|---|
| multiclass | level = highest class level + ⅓ of the others (min 1 each) | p.3 |
| exceptional STR | 18/01–50 → 19, /51–75 → 20, /76–90 → 21, /91–99 → 22, 18/00 → 23; 19–20 → 24, 21–22 → 25, 23 → 26, 24–25 → 27 | p.3–4 |
| ability bumps | +1 to an ability per 4 character levels | p.4 |
| HP | keep the old HP or recalculate (3.5 HD + Con) | p.5 |
| thief skills | 3e ranks ≈ (2e % ÷ 5) − 5 | p.9 |
| attack | 3e attack bonus ≈ 20 − THAC0 | p.11 |
| AC | 3e AC ≈ 20 − 2e AC; natural armour = AC − 10 − Dex − size | p.11, 21 |
| saves | 3e save ≈ 15 − 2e save. Fort from paralyzation/poison/death, Ref/Will from spell | p.12 |
| spells | renamed list (e.g. *Armor* → *Mage Armor*, *Monster Summoning N* → *Summon Monster N*) | p.15–16 |
| monsters | keep HD, die by type, speed ×2.5 ft, BAB/saves by type and HD | p.20–21 |
| monster defences | "hit only by +N / silver" → DR 10/magic or /silver; SR = 11 + MR/5 | p.22 |
| CR | by comparison with similar MM monsters | p.22 |

## ADJUDICATION LIST

Every entry is an option in `ie_rules.DEFAULT_OPTIONS` and can be switched per conversion run
(`--option key=value`). The recommendations below are the defaults.

| # | question | options | recommendation |
|---|---|---|---|
| ADJ-1 | 18/xx strength | `cm` official CM table (18/00 → 23); `compressed` 18/01–50 → 19, 51–99 → 20, 00 → 21; `ignore` (18) | **cm**. It is the published rule. `compressed` keeps 3.5 power closer to IE feel (an 18/00 fighter with 23 STR is very strong at ToEE levels); offer it as the mod's "low power" toggle. |
| ADJ-2 | +1 ability per 4 levels | apply to the class key ability / don't | **apply** (CM p.4). Without it high-level NPCs end up weaker than PCs built at the same level. |
| ADJ-3 | multiclass levels | `cm` highest + others/3; `sum` | **cm**. `sum` makes F/M/T NPCs absurd under 3.5 BAB/saves stacking. |
| ADJ-4 | hit points | `ie` keep CRE HP; `3e` average 3.5 HD + Con; `max_ie_3e` the higher of the two | **max_ie_3e**. IE HP are tuned for real-time 2e. 3.5 damage output is higher, so never go below the 3.5 average. |
| ADJ-5 | saves | off; `bonus_if_better` add an NPC save bonus when 15 − 2e save beats the 3.5 save by ≥ 2 | **bonus_if_better**. Keeps "resistant" uniques resistant without inflating ordinary NPCs. |
| ADJ-6 | attack | off; `bonus_if_better` when 20 − THAC0 beats 3.5 BAB by ≥ 3 | **bonus_if_better**. It is logged only so far: Temple+ has no generic "to-hit bonus" condition yet. A small Python condition is needed. |
| ADJ-7 | energy resistance % | `banded`: < 20 % ignored, 20–49 % → resist 5 (10 at 8+ HD), 50–99 % → 10 (20 at 8+ HD), ≥ 100 % → immunity, ≤ −50 % → vulnerability | **banded**. Stays on the MM's resist 5/10/20 steps (the CM has no rule, only "use a similar MM creature", p.22). Vulnerability has no Temple+ condition yet and is logged. |
| ADJ-8 | physical resistance % and weapon immunity | two of slashing/crushing/piercing resisted ≥ 25 % and the third not → DR 5 (10 at ≥ 50 %)/the unresisted type (skeletons → /bludgeoning); all three → DR 5–10/–; "hit only by magic/silver/cold iron" (opcode 120) → DR 10/magic or /silver (CM p.22) | **as stated** |
| ADJ-8b | IE regeneration | Temple+ *Monster Regeneration* (needs a damage-type bypass) or *Monster Fast Healing* | **fast healing** of the same HP/round, capped at 10; true regeneration only where the template already has it (trolls). |
| ADJ-9 | magic resistance | CM SR = 11 + MR/5; MR ≥ 100 → spell immunity | **cm** |
| ADJ-10 | morale | IE morale break 0 / morale 20 → never flees; otherwise ToEE AI default | **no_flee_if_unbreakable** |
| ADJ-11 | CR / XP | template CR (+1 per 4 HD advanced past the template) for monsters, level for NPCs; IE XP value only reported | **proto_or_level**. Party XP stays 3.5-native. |
| ADJ-12 | 0-level / 1st-level "fighter" townsfolk | `monster_hd` 1 HD humanoid commoner without a PC class; `class` keep fighter 1 | **monster_hd**. 2e towns are full of "F1" peasants that are not warriors in 3.5 terms. EE already marks most of them INNOCENT. |
| ADJ-13 | track A stats | `srd` template abilities/AC/attacks with IE HD/HP/defences; `ie` IE abilities and AC; `max` | **srd**. It gives MM-consistent monsters. Switch to `ie` per family when a fight is clearly mis-tuned. |
| ADJ-14 | IE "minimum HP" (opcode 208) on ambient creatures/plot NPCs | make the critter invulnerable (drop its DR/regeneration); ignore | **invulnerable**. IE uses it for unkillable ambient animals and plot NPCs. |

Open questions that are not options yet:
* Size. IE has no size field; it comes from the family/template. Class-based races use race defaults.
* Kits. The kit is read (big-endian 0x244) but not converted. Map kits to prestige classes or feats later (CM p.11).
* Proficiencies → feats. EE opcode 233 is read; "1 feat + 1 per 3 levels" (CM p.7) is not applied yet.
* Thief skills (CM p.9) are computed but not yet written to ToEE skill ranks.
* Spells: see [spells.md](spells.md). Known and memorised spells map through the authored guidance table, then by
  name, and only to spells Temple+ implements. They are given to the NPC at spawn with a custom AI strategy, and the
  IE spell actions cast them in game.
* Innate abilities (IE `innate` spells) need per-ability authored mappings (breath weapons, gazes).

## What guidance data may contain

The repository may only ship material we author. For creatures that means:
* **ids and keys:** IE animation ids, IDS values, item type numbers and opcode numbers (numeric facts of the file
  format, documented by IESDP), mapped to ToEE model ids and template proto ids (numbers in the player's own ToEE install);
* **our own labels and notes** ("Goblin", "Ice troll stand-in"). These are generic D&D creature types, not text
  copied from either game;
* **rules as code** (`ie_rules.py`), re-stated from the Conversion Manual with page citations.

It must **not** contain:
* game text (names, descriptions, dialog);
* stat tables extracted from either game;
* copied Monster Manual / SRD text;
* any IWD resource reference list beyond what a rule needs.

Spell mapping uses an authored table of IE resref → Temple+ spell enum pairs (`guidance/spells_iwd.json`, see spells.md), then a
name match at conversion time. A mapping of resref → proto id is a fact about how two
file sets relate and contains no creative content from either. We keep even those to the minimum.

## Artwork: IE animations → ToEE models

The guidance table is the model map. Family status:

* **match** (a ToEE model of the same creature): goblin, goblin elite, hobgoblin, gnoll, skeleton, zombie, ghoul, ghast,
  shadow, troll (incl. ice/snow trolls as tinted/scaled trolls), umber hulk, vodyanoi, ogre, minotaur, ettin, the four
  elementals, salamander, giant spider, wolf/winter wolf, dog, bears, carrion crawler, shrieker, lizardfolk,
  glabrezu, harpy, chicken, basilisk, oozes. Class-based humanoids are all covered by the ToEE PC/NPC body models with
  equipment.
* **stand-in** (a related model, scaled or retinted): orc (→ ToEE orc NPCs), orog, kobold, skeletal fiend, wight,
  mummy (Co8 has a mummy model), ghost, cyclops, frost/fire giants and verbeeg (→ hill giant), white dragon (→ ToEE's
  dragon model), myconid, deep gnome (→ gnome NPC), animated armour, golems, large demons, sahuagin, boar, snakes,
  rats and small animals, werewolves, shambling mound.
* **missing** (no usable ToEE model): yuan-ti, yeti, giant beetles, wyvern, lich (Co8 has 1206/1207), remorhaz,
  devils (Co8 bearded devil 1183), insect swarm, livestock (cow, horse), birds/bats, great cats, and the BG2-engine
  extras in IWD:EE (imps, djinni, rakshasa, beholders, mind flayers, devas).

**Free-model pipeline candidates** (Blender plugin, `tools/fit_free_model.py`), roughly in order of how often IWD
uses them:
1. yuan-ti (the most-placed missing family),
2. yeti,
3. giant beetles,
4. wyvern,
5. lich,
6. remorhaz,
7. birds/bats,
8. great cats,
9. livestock,
10. devil.

Insect swarms are better done as a particle effect than a skinned model.

**Coverage.** The local survey reports coverage per install, by placement and by distinct CRE, split into
`class-based`, `match`, `stand-in` and `missing`. Roughly 90 % of IWD creature placements have a match, a stand-in
or are class-based; only about 10–13 % need new art. The report itself stays local.

## Runtime notes (found in game)

* The toee module's `obj_f_*` constants below `obj_f_hp_pts` (27) are **off by two** relative to the field numbers
  Temple+'s `obj_get_int`/`obj_set_int` use. `toee.obj_f_description` is 23, but the description id lives in field
  25, and writing 23 breaks item wielding. `ie_critters.FIELDS` therefore holds the verified numbers (description 25,
  model scale 8, hp_pts 27, hp_damage 29, gender 289, alignment 295, inventory source 311, unknown description 312,
  NPC save bonuses 373–375, NPC AC bonus 376, NPC hit dice 387).
* Template protos with an inventory source (villagers) get random gear on first activation, which replaces the
  converted items. The spawner clears `obj_f_critter_inventory_source`.
* `stat_hp_max` = `obj_f_hp_pts` + Con × HD + racial HD + condition bonuses. The spawner writes the target max HP
  and corrects for the difference.
* Temple+ re-applies racial ability adjustments, so for non-human class-based NPCs the base scores are the IE
  scores minus the SRD racial adjustment.
* Extra `mes/description/*.mes` files are picked up from `modules/ToEE_core` (on the VFS at startup).
* Converted names are written to both the description and the "unknown description" field, because IE shows names
  without an introduction.

- Items phase changes:
  - `toeedata.py` now mounts only what Temple+ mounts. It dropped `ToEESteam*.dat`, so some Steam-only protos that
    Temple+ can't create no longer appear as choices.
  - It reads `protos.tab` split on `\n` only.
  - Creature gear defaults to the real converted items (`gear=items`, see [items.md](items.md)). The stand-in gear
    is the fallback.

## Prototype: the first town area (AR1000)

`out/local_tests.sh cre_ar1000 IWD|IWDEE` (local) runs the test as follows:
1. It installs the converted dialogs/scripts, the names `.mes` and the runtime into a private overlay
   (`ToEE-iecre`) and a private wine prefix (`~/.wine-toee-iecre`) on a private Xvfb display.
2. It spawns every AR1000 actor at its IE position on the converted map (`rt.ie_to_tile`).
3. It logs each critter's engine-computed stats (HP, AC, abilities, level, BAB, saves, alignment, hostility,
   scale, worn items).
4. It lines up one of each friendly creature next to the party, frames the goblin pack, and opens the converted
   dialog of an attached NPC.

## IWD2 (CRE V2.2)

Not handled yet. V2.2 is a different header: 3e-style stats, per-class levels, skills and feats bitfields, and
spell tables per class and level. It is in some ways *easier*, since it is already 3e. `iecre.Cre` raises
`NotImplementedError` for it. Add a separate `Cre22` reader when IWD2 support starts.

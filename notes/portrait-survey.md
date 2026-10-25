# ie2toee portrait survey (Easthaven, AR1000-AR1014)

Read-only survey, 2026-10-25. Sources: converted specs `/tmp/iwdout/work/cre*/AR1*_creatures.json` (latest preview build), IWD:EE CREs via chitin.key, ToEE `art/interface/portraits/portraits.mes` + `rules/protos.tab`.

## How portraits are assigned today

- The converter never sets a portrait. Each spawn gets the portrait of its template proto (protos.tab column 123, `critter_portrait`).
- Every male human villager uses proto 14000 -> 7830 HommletMan; every female uses 14001 -> 7840 HommletWoman. So 23 of 46 spawns share one face and 10 share another.
- portraits.mes ids are bases: +1 mini (combat queue), +2 small, +3/+4 grey variants. Base itself has no file.
- `ie_dialog_skin.py` can already copy an IE CRE portrait into the dialogue skin (`--portrait ID:CRE`), but no Easthaven CRE has one.

## 1. Easthaven creatures (46 spawns, 38 unique CREs)

| Area | CRE | Name | Race | Sex | Class | Hostility | Dlg | Proto | ToEE portrait now | IE portrait (S/L) |
|---|---|---|---|---|---|---|---|---|---|---|
| AR1000 | damien | Damien | HUMAN | male | INNOCENT | neutral | Y | 14000 | 7830 HommletMan | None/None |
| AR1000 | apsel | Scrimshander | HUMAN | male | INNOCENT | neutral | Y | 14000 | 7830 HommletMan | None/None |
| AR1000 | eboy1 | Boy 1 | HUMAN | male | INNOCENT | neutral | Y | 14000 | 7830 HommletMan | None/None |
| AR1000 | eboy2 | Boy 2 | HUMAN | male | INNOCENT | neutral | Y | 14000 | 7830 HommletMan | None/None |
| AR1000 | egirl1 | Girl | HUMAN | female | INNOCENT | neutral | Y | 14001 | 7840 HommletWoman | None/None |
| AR1000 | egirl2 | Girl | HUMAN | female | INNOCENT | neutral | Y | 14001 | 7840 HommletWoman | None/None |
| AR1000 | squirel | Squirrel | NO_RACE | male | FOOD_CREATURE | neutral |  | 14056 | 3510 GiantRat | None/None |
| AR1000 | towniem1 | Townsperson | HUMAN | male | INNOCENT | neutral | Y | 14000 | 7830 HommletMan | None/None |
| AR1000 | towniem3 | Townsperson | HUMAN | male | INNOCENT | neutral | Y | 14000 | 7830 HommletMan | None/None |
| AR1000 | towniem4 | Townsperson | HUMAN | male | INNOCENT | neutral | Y | 14000 | 7830 HommletMan | None/None |
| AR1000 | townief1 | Townsperson | HUMAN | female | INNOCENT | neutral | Y | 14001 | 7840 HommletWoman | None/None |
| AR1000 | townief2 | Townsperson | HUMAN | female | INNOCENT | neutral | Y | 14001 | 7840 HommletWoman | None/None |
| AR1000 | townief3 | Townsperson | HUMAN | female | INNOCENT | neutral | Y | 14001 | 7840 HommletWoman | None/None |
| AR1000 | elisia | Elisia | ELF | female | FIGHTER | neutral | Y | 14072 | 7520 Chanda | None/None |
| AR1000 | jhonen | Jhonen | HUMAN | male | INNOCENT | neutral | Y | 14000 | 7830 HommletMan | None/None |
| AR1000 | gobobow | Goblin Archer 1 | GOBLIN | male | NO_CLASS | hostile |  | 14186 | 3810 Goblin | None/None |
| AR1000 | gobobow | Goblin Archer 2 | GOBLIN | male | NO_CLASS | hostile |  | 14186 | 3810 Goblin | None/None |
| AR1000 | goboaxe | Goblin Axe 1 | GOBLIN | male | NO_CLASS | hostile |  | 14186 | 3810 Goblin | None/None |
| AR1000 | goboaxe | Goblin Axe 2 | GOBLIN | male | NO_CLASS | hostile |  | 14186 | 3810 Goblin | None/None |
| AR1000 | gobehq1 | Goblin Bow Elite (Quest) | GOBLIN | male | NO_CLASS | hostile |  | 14183 | 3820 Goblin (elite) | None/None |
| AR1000 | goboaxe | Goblin Axe 3 | GOBLIN | male | NO_CLASS | hostile |  | 14186 | 3810 Goblin | None/None |
| AR1000 | goboaxe | Goblin Axe 4 | GOBLIN | male | NO_CLASS | hostile |  | 14186 | 3810 Goblin | None/None |
| AR1000 | goboaxe | Goblin Axe 5 | GOBLIN | male | NO_CLASS | hostile |  | 14186 | 3810 Goblin | None/None |
| AR1001 | everard | Everard | HUMAN | male | CLERIC | neutral | Y | 14000 | 7830 HommletMan | None/None |
| AR1001 | accalia | Accalia | HUMAN | female | INNOCENT | neutral | Y | 14001 | 7840 HommletWoman | None/None |
| AR1002 | townief1 | Townsperson | HUMAN | female | INNOCENT | neutral | Y | 14001 | 7840 HommletWoman | None/None |
| AR1004 | hroth | Hrothgar | HUMAN | male | FIGHTER | neutral | Y | 14000 | 7830 HommletMan | None/None |
| AR1005 | gaspar | Gaspar | HUMAN | male | INNOCENT | neutral | Y | 14000 | 7830 HommletMan | None/None |
| AR1006 | barkeep | Townsperson | HUMAN | female | INNOCENT | neutral | Y | 14001 | 7840 HommletWoman | None/None |
| AR1006 | hildreth | Hildreth Highhammer | DWARF | female | INNOCENT | neutral | Y | 14334 | 7890 Ogavick | None/None |
| AR1006 | stoolm1 | Townsperson | HUMAN | male | INNOCENT | neutral | Y | 14000 | 7830 HommletMan | None/None |
| AR1006 | stoolm2 | Townsperson | HUMAN | male | INNOCENT | neutral | Y | 14000 | 7830 HommletMan | None/None |
| AR1006 | chairm1 | Townsperson | HUMAN | male | INNOCENT | neutral | Y | 14000 | 7830 HommletMan | None/None |
| AR1006 | chairm2 | Townsperson | HUMAN | male | INNOCENT | neutral | Y | 14000 | 7830 HommletMan | None/None |
| AR1006 | chairm3 | Townsperson | HUMAN | male | INNOCENT | neutral | Y | 14000 | 7830 HommletMan | None/None |
| AR1006 | hroth | Hrothgar | HUMAN | male | FIGHTER | neutral | Y | 14000 | 7830 HommletMan | None/None |
| AR1007 | pomab | Pomab | HUMAN | male | INNOCENT | neutral | Y | 14000 | 7830 HommletMan | None/None |
| AR1008 | innkpr | Innkeeper | HUMAN | male | INNOCENT | neutral | Y | 14000 | 7830 HommletMan | None/None |
| AR1008 | erevain | Erevain Blacksheaf | ELF | male | INNOCENT | neutral | Y | 14201 | 7850 ElfPrisoner1 | None/None |
| AR1009 | oldjed | EHOldJed | HUMAN | male | INNOCENT | neutral | Y | 14000 | 7830 HommletMan | None/None |
| AR1010 | wolf | EHWolf | WOLF | female | WOLF | hostile |  | 14050 | 3730 Wolf | None/None |
| AR1011 | churin | Churin | HUMAN | male | INNOCENT | neutral | Y | 14000 | 7830 HommletMan | None/None |
| AR1011 | towniem2 | Townsperson | HUMAN | male | INNOCENT | neutral | Y | 14000 | 7830 HommletMan | None/None |
| AR1011 | towniem3 | Townsperson | HUMAN | male | INNOCENT | neutral | Y | 14000 | 7830 HommletMan | None/None |
| AR1012 | townief4 | Townsperson | HUMAN | female | INNOCENT | neutral | Y | 14001 | 7840 HommletWoman | None/None |
| AR1014 | townief5 | Townsperson | HUMAN | female | INNOCENT | neutral | Y | 14001 | 7840 HommletWoman | None/None |

## 2. IWD:EE portrait resources

- **No Easthaven CRE references a portrait.** All 38 have small/large portrait = `None`. Native NPC portraits: 0.
- Stock party portraits (BMP, L/M/S sets): 70 sets plus `noportl`. Human: hmf..hmf7, hmw..hmw4, hmc..hmc4, hmb/hmb2, hft/hft2, hff/hff2, hfw..hfw3, hfd; elf: emf/emf2, emt, emw, emc, eff, efw/efw2, efc; half-elf: hemf, hemt, hemw, hefb, hefc, heff, hefw; dwarf: dmf/dmf2, dmt, dmc, dff; halfling: hamf, hamt, haff, haft; gnome: gmt, gmw, gfw; EE extras 2fbar1, 2fhum4, 2forc1, 2mbar1, 2mhum1, 2morc1; bdtma..bdtmk (11 sets, likely Black Pits/BD-style extras).
- Also present: `arXXXXlm` area minimaps (not portraits). These party portraits are IWD player art; using them for NPCs would be local-only conversion output (never redistributed), same rule as other IWD data.

## 3. ToEE portraits usable for mapping

- 359 portrait sets in the ToEE-ie install portraits.mes: 37 PC sets (human 10, elf 7, half-elf 2, dwarf 6, halfling 2, half-orc 7, gnome 3), monster sets 3500-5999, and ~200 NPC sets 6000-8080.
- Generic villager candidates: HommletMan 7830, HommletWoman 7840, CE_Peasant_01/02/03 6600-6620, PeasantLaborer 7020, LG_Survivor 6700, NulbMan/NulbWoman 7660/7670, FemalePrisoner1/2 7910/7920, Dala 7620, Mona 7690.
- Role candidates: Terjon 6000 (priest), Ostler 6050 (innkeeper), Rannos 6040 / Gremag 6090 (merchants), CaptainRenton 6330, ElvenMaiden 7740, ElvenRanger 7750, Pirate 7640.
- No child portraits exist in ToEE.

## 4. Draft mapping (unique where possible)

| CRE | Name | Proposed id | Portrait | Note |
|---|---|---|---|---|
| damien | Damien | - | GAP | child; no ToEE child portraits |
| apsel | Scrimshander | 7020 | PeasantLaborer | older craftsman; AI art preferred |
| eboy1 | Boy 1 | - | GAP | child |
| eboy2 | Boy 2 | - | GAP | child |
| egirl1 | Girl | - | GAP | child |
| egirl2 | Girl | - | GAP | child |
| squirel | Squirrel | - | GAP (keep 3510 GiantRat) | animal, low priority |
| towniem1 | Townsperson | 7830 | HommletMan | generic townsman (rotated) |
| towniem3 | Townsperson | 6620 | CE_Peasant_03 | generic townsman (rotated) |
| towniem4 | Townsperson | 6700 | LG_Survivor | generic townsman (rotated) |
| townief1 | Townsperson | 7840 | HommletWoman | generic townswoman (rotated) |
| townief2 | Townsperson | 7670 | NulbWoman | generic townswoman (rotated) |
| townief3 | Townsperson | 7910 | FemalePrisoner1 | generic townswoman (rotated) |
| elisia | Elisia | 7740 | ElvenMaiden | elf female fighter |
| jhonen | Jhonen | 7640 | Pirate | sailor/fisher, tentative |
| gobobow | Goblin Archer 1 | 3810 | Goblin | unchanged |
| gobobow | Goblin Archer 2 | 3810 | Goblin | unchanged |
| goboaxe | Goblin Axe 1 | 3810 | Goblin | unchanged |
| goboaxe | Goblin Axe 2 | 3810 | Goblin | unchanged |
| gobehq1 | Goblin Bow Elite (Quest) | 3820 | Goblin elite | unchanged |
| goboaxe | Goblin Axe 3 | 3810 | Goblin | unchanged |
| goboaxe | Goblin Axe 4 | 3810 | Goblin | unchanged |
| goboaxe | Goblin Axe 5 | 3810 | Goblin | unchanged |
| everard | Everard | 6000 | Terjon | priest -> Hommlet priest |
| accalia | Accalia | 6250 | Myella |  |
| hroth | Hrothgar | 6330 | CaptainRenton | town captain; AI art preferred |
| gaspar | Gaspar | 6040 | RannosDavi | shady merchant |
| barkeep | Townsperson | 7620 | Dala | barmaid |
| hildreth | Hildreth Highhammer | 2040 | DWF fighter (PC set) | dwarf female |
| stoolm1 | Townsperson | 7660 | NulbMan | generic townsman (rotated) |
| stoolm2 | Townsperson | 7830 | HommletMan | generic townsman (rotated) |
| chairm1 | Townsperson | 6620 | CE_Peasant_03 | generic townsman (rotated) |
| chairm2 | Townsperson | 6700 | LG_Survivor | generic townsman (rotated) |
| chairm3 | Townsperson | 7660 | NulbMan | generic townsman (rotated) |
| pomab | Pomab | 6100 | Filiken | shopkeeper, tentative |
| innkpr | Innkeeper | 6050 | OstlerGundigoot | innkeeper -> innkeeper |
| erevain | Erevain Blacksheaf | 1040 | ELM ranger (PC set) | elf male |
| oldjed | EHOldJed | 6140 | BrotherSmyth | old man; AI art preferred |
| wolf | EHWolf | 3730 | Wolf | unchanged |
| churin | Churin | 6610 | CE_Peasant_02 |  |
| towniem2 | Townsperson | 7830 | HommletMan | generic townsman (rotated) |
| townief4 | Townsperson | 6600 | CE_Peasant_01 | generic townswoman (rotated) |
| townief5 | Townsperson | 7840 | HommletWoman | generic townswoman (rotated) |

### Coverage

- Unique named/role NPCs (non-generic, non-monster): 19 CREs; 14 mapped to distinct ToEE portraits, 5 children are gaps.
- Generic townspeople: 4 male + 5 female ToEE sets rotated, so no single face repeats more than 3 times (was 23x).
- Gaps needing AI art: damien, eboy1, eboy2, egirl1, egirl2 (children) + squirrel (low priority). Recommended AI upgrades even though mapped: apsel (Scrimshander), hroth (Hrothgar), oldjed, pomab.
- Monsters (goblins, wolf) keep their current ToEE portraits.

## Implementation note (not done)

- Add a `PORTRAITS` table keyed by CRE resref in the converter and set `obj_f_critter_portrait` at spawn (or emit per-NPC protos). Generic townsfolk rotate by spawn index.
- AI-generated art would go in as new portraits.mes ids (e.g. 9000+) with m/s TGA pairs.

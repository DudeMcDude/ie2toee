# Items (prototype)

IE items (ITM) become Temple+ items: a ToEE base proto, plus Temple+ item conditions, plus the IE name, icon, price
and identification state, all applied at runtime when the item is created. As with every other phase, no IE data is
committed. The converter writes its tables into the player's local output, built from the player's own installs.

## Pieces

| file | role |
|---|---|
| `proto/ieitm.py` | ITM V1 (classic IWD, BG/IWD:EE) reader with extended headers (melee / ranged / launcher / ammo, charges, depletion), equipping and per-ability effects (EFF V1 inline), usability and kit flags; STO V1.0/V1.1/V9.0 reader; ARE container items |
| `proto/ie_items.py` | `survey`, `coverage`, `convert`; `ItemMapper` (status per item, base proto, conditions, price); `ITEM_OPTIONS` (ITEM-ADJ-1 … 16) |
| `proto/guidance/items_iwd.json` | authored rules and per-resref overrides (IE resrefs, ToEE proto ids, ToEE's own labels only) |
| `proto/runtime/ie_itemrt.py` | Temple+ runtime: create an IE item by resref, give, find, fill area containers, stock a store, open the barter screen |
| `proto/ingame_items_probe.py` | in-game test driver (local) |

`ie_runtime.py` routes IE `GiveItem`, `GiveItemCreate`, `TakePartyItem`, `HasItem`, `PartyHasItem` and
`StartStore` to the item runtime. Converted creatures carry their real converted items (creature option
`gear=items`, the default). The creatures-phase stand-in gear is still there as a fallback (`gear=standin`).

## Format notes (IESDP)

- ITM V1 header 0x72 bytes; extended headers 0x38; feature blocks 0x30. EE items are V1 with the same layout; EE uses
  more opcodes (206/267/296/318/319 …) but no new header fields that matter here.
- ARE item records: `charges[0]` holds the stack quantity of stackable items (gold, ammo, potions).
- STO: V1.0 and V9.0 headers are read; the item-for-sale record carries the "infinite" flag.

## Survey (local: `out/item_survey.md`, `.json`)

| | classic IWD | IWD:EE |
|---|---|---|
| items | 1456 (0 parse failures) | 1857 (0 parse failures) |
| used anywhere | 799 (445 magic) | 1058 (667 magic) |
| uses: creatures / containers / stores / scripts / dialogs | 2002 / 607 / 909 / 113 / 186 | 3430 / 880 / 957 / 358 / 383 |
| item → spell links (scrolls cast+learn, wands, charged) | 262 / 33 / 10 | 497 / 47 / 12 |

The most frequent equipping opcodes are 7 (colour), 0 (AC), 261/206 (immunity / restore), 8, 1, 142/144/145 (icons
and disables). Those are mostly cosmetic or have no 3.5 equivalent. The ones that map are listed under
`_equip_effects` in `ie_items.py`.

## Mapping and statuses

| status | meaning |
|---|---|
| direct | an existing ToEE / Temple+ proto as-is (mundane weapons, armor, gems, gold, matching potions, scrolls, wands) |
| built | ToEE base proto plus Temple+ conditions (enhancement, deflection, resistance, attribute enhancement, SR, DR, Weapon Masterwork, …) |
| base | base proto only; IE effects with no Temple+ condition are dropped (listed in the notes) |
| generic | stand-in proto for quest items, books, misc and containers (IE name, icon, price and weight) |
| new | IWD-unique; closest base plus whatever maps; a new Temple+ condition or proto is needed (later phase) |
| unmapped | nothing usable |

Scrolls, potions and wands go to the Temple+ spell item for the same spell through the spells guidance
(`spells_iwd.json`). An index of Temple+ scroll/potion/wand protos is keyed by spell id. IE wands that don't carry a
spell link in the ITM are mapped by resref overrides.

### Coverage weighted by use (`coverage` command)

| | direct | built | generic | base | new | unmapped |
|---|---|---|---|---|---|---|
| classic IWD (items) | 473 | 275 | 373 | 72 | 241 | 22 |
| classic IWD (% of uses) | 60.6 | 8.3 | 21.9 | 1.2 | 8.0 | 0.0 |
| IWD:EE (items) | 455 | 344 | 485 | 78 | 412 | 83 |
| IWD:EE (% of uses) | 51.5 | 9.5 | 25.8 | 1.0 | 12.3 | 0.0 |

So 92 % (classic) and 88 % (EE) of what the games actually hand out lands on a working ToEE item. All unmapped items
are unused. The "new" share is mostly unique potions, scrolls of IWD-only spells, belts (ToEE has no belt slot) and
EE-only weapons.

## Runtime

- `ie_itemrt.make(res)` creates the base proto and then applies:
  - the conditions;
  - the IE name (description id = `22000 + 2n`; unidentified name = the next id);
  - the icon (`inv_aid` = 651 + n);
  - worth;
  - stack quantity;
  - `OIF_IS_MAGICAL`;
  - `OIF_IDENTIFIED` (ITEM-ADJ-9).
- Names go into `mes/description/ie2toee_items.mes`. Temple+ only reads `description.mes` overrides for ids
  below 30000; ids from 30000 up need `gamedesc` and show "OBJ_HANDLE_NULL".
- Icons: each IE inventory BAM (frame 1 for the large icon, else frame 0) becomes a 64×64 32-bit TGA. The file is
  `data/art/interface/inventory/ie2toee_<res>.tga`, plus a merged `inventory.mes` (vanilla 413 entries, max id 650,
  IE icons from 651). **They must go in the game's `data/` folder.** The UI asset table loads before modules are
  mounted, so a copy under `modules/ToEE/art/...` is never read (verified: vanilla icons under new ids stayed blank
  there).
- Containers: `fill_containers(area)` creates the IE container at its converted position with its contents, its lock
  (OCOF_LOCKED, DC 10 + IE lock/5, at most 40) and its proto (chest, barrel, crate, … from the guidance).
- Stores: `stock_store(npc, store)` makes a hidden container (`OF_DONTDRAW | OF_CLICK_THROUGH`) with the store's
  items, all identified, set as the merchant's `substitute_inventory`. Infinite stock = 5 copies. The ToEE barter
  screen only opens from a dialogue reply whose text starts with `B:` (the vanilla convention), and `pc.barter(npc)`
  called outside dialogue shows nothing. So `ie_dialogue.py` now prefixes every reply whose actions include
  `StartStore` with `B:`.
- `proto/toeedata.py` now mounts what Temple+ mounts (`tig.dat`, `ToEE1-4.dat`, `tpgamefiles.dat`, the module's
  `_core.dat` and `.dat`) and no longer reads `ToEESteam*.dat`. Several protos that only exist in the Steam dats
  (4408, 4412, 6272–6274, 8101+, 9653+) can't be created in Temple+. In the `protos.tab` that Temple+ loads, the
  description id is column 23.

## ITEM-ADJ: adjudication list (switch: `--option key=value`; **default in bold**)

1. **Weapon stats** (`weapon_stats`): **ToEE base weapon dice, crit range and multiplier** | `ie_dice`. 3.5 balance
   lives in the base weapon. IE dice differ mostly by size category.
2. **Weapon speed and size** (`weapon_speed`): **dropped** | `initiative` (speed/2 as an initiative penalty). 3.5
   has neither.
3. **Armor** (`armor_stats`): **ToEE base armor bonus, max Dex, check penalty and ASF**. For magic armor, the
   enhancement is the mundane IE AC minus the item's AC. | `ie_ac`.
4. **Enchantment** (`enchantment`): the IE enchantment field or the THAC0 bonus, whichever is higher, becomes
   **enhancement +N capped at +5** | `uncapped`. A mundane IE THAC0 bonus becomes Weapon Masterwork.
5. **Charges** (`charges`): **keep the IE charge count**; recharging items get N uses per day | `35` (SRD: wands 50).
   (Not yet applied at runtime, see the open items.)
6. **Cursed items** (`cursed`): **keep their effects, flagged in the notes, removable** (ToEE has no
   cannot-remove) | `skip`.
7. **Stat-setting items** (`stat_set`): "STR set to X" becomes an **enhancement bonus by table (18 → +2, 19–20 →
   +4, 21+ → +6)**, and "+N" stays +N | `ie_set`. This uses Attribute Enhancement Bonus.
8. **Prices** (`prices`): **3.5 price (ToEE base worth + SRD bonus price)** | `ie` (IE gp 1:1). 8b. **Store markup**
   (`store_markup`): **ToEE barter (Appraise)** | `ie` (IE sell/buy %).
9. **Identify** (`identify`): **magic items with IE lore > 0 start unidentified** (ToEE Identify, shop identify) |
   `all_identified`. IE Lore vs Spellcraft: no roll at pickup.
10. **2e protection +N** (`protection_items`): **ring → Ring of Protection +N (deflection); cloak → Cloak of
    Resistance +N; other slots get both** | `both`.
11. **Saves** (`saves`): **2e categories folded** (death/poly → Fort, wands/breath → Ref, spells → Will; highest per
    3.5 save) | `all_three`.
12. **Resistances** (`resistances`): **% resistance steps down to resist energy 5/10/20/30** (<50, <75, <100,
    100 %). MR % becomes **SR 10 + MR/5**, and physical % becomes **DR (pct/10)/–** | `drop_physical`.
13. **Usability** (`usability`): **class, kit and alignment restrictions dropped** (3.5 proficiency + UMD) | `note`.
14. **Shields** (`shields`): **medium/large → heavy steel; small/buckler → light/buckler** | `large_tower`.
15. **Potions** (`potions`): **Temple+ potion with the same main effect**; heal amount picks CLW/CMW/CSW/CCW |
    `skip`.
16. **IWD-unique items** (`unique`): **closest base + whatever maps, unmapped effects in notes** (status `new`) |
    `skip`.

## Artwork

- Inventory icons: IE BAMs become ToEE TGAs on the player's machine (`convert`). Classic gave 697 icons (7 BAMs
  failed or were missing); EE gave 947 (1 failed). In the ToEE inventory, barter and loot screens the IE large icons
  (centred in a 64×64 TGA) fill ToEE's cells well. They read clearly and sit naturally next to ToEE's own icons;
  they look slightly more painterly and saturated.
- Ground and paperdoll art come from the base proto, so a +1 long sword looks and is worn like a ToEE long sword. Per
  resref model overrides are possible in the guidance (`overrides.<res>.proto`).

## In-game test (local only; screenshots under `out/ingame/`)

- AR1001, classic (`items_ar1001_IWD/`):
  - `inventory.png`: converted magic items show their IE names, icons and 3.5 prices. The red border on the sword
    and armour is ToEE's "can't use" marker for the sorcerer leader.
  - `store.png`: the barter screen opens through the converted dialogue (`B:` reply). It shows the store's potions
    and scrolls (×5 for infinite stock).
- `items_loot/loot.png`: the AR1001 priest NPC's corpse loot window, with his converted war hammer, plate +1 and boots.
  `items_loot2/looted_inv.png`: the same items in the party inventory. They are unidentified (`identified 0` in the log).
- AR5404, classic (`items_box_IWD/`): the IE chest is placed at its converted spot, locked, with its contents (a
  generic book and 30 gp). The contents were checked from the log; the chest sits on a ledge the party couldn't
  reach in the test.
- EE: `items_ar1001_IWDEE/` (`inventory.png`, `talk.png` with the iwdee skin, `store.png`).
  `items_loot_IWDEE/looted_inv.png` shows the corpse's converted items in the party inventory (scripted take; the
  EE corpse click missed). In `items_box_IWDEE/`, the EE chest also holds a scroll (stand-in proto, IE icon).

## What guidance data may contain

IE resrefs, ToEE / Temple+ proto ids and condition names, and ToEE's own labels. It may not contain IE names, texts
or stats (those are read from the player's install at convert time).

## Open items

- Wand / charged-item charges aren't written at runtime (`SET_CHARGES = 0`). An early run hung after giving a wand
  and the cause wasn't pinned down. Re-enable it and test.
- Potions and gold stack with existing items of the same proto (ToEE stacking), so a stacked IE potion takes on
  the identity of the stack. Use different protos or turn stacking off for IE items.
- Converted NPCs still carry their ToEE proto's default inventory (the AR1001 priest: rusty rapier, padded boots, farmer
  garb). Clear proto inventory on spawn.
- Some spells have no ToEE scroll or wand proto (scrolls of IWD-only spells are status `new`).
- Store "cures" (temple healing services) aren't converted yet; IE store buy/sell markups are ignored (ITEM-ADJ-8b).
- Store icons for direct-mapped potions and scrolls use the ToEE proto's own icon. Only entries we stamp get the IE
  icon.
- Infinite stock is approximated as 5 copies.
- Usability restrictions are dropped (ITEM-ADJ-13). Belts have no ToEE slot (status `new`).
- Halberd → glaive (reach) and flail → heavy flail are the nearest engine-valid protos.
- ADJ-6 to-hit bonuses on non-enhanced items (THAC0 on magic weapons beyond the enhancement) have no generic Temple+
  condition yet.
- No Temple+ "corrosive" weapon condition; IWD acid weapons get notes only.
- Test-harness wrinkles: the barter window is modal, so take loot shots in a separate run. The AR5404 chest is on a
  ledge the party can't reach. Edge scrolling moves the camera when the mouse is parked outside the window.
- Dialogue triggers: `ClassEx` with `class_paladin` raises IE_ERR (constant name lookup). an EE NPC's levels read
  as [1,6,0].

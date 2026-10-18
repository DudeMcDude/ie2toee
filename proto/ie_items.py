"""Items: IE ITM -> ToEE / Temple+ items.

  survey    count every item of an install by IE category, magic vs mundane, and record where each one is used
            (creature inventories weighted by placements, area containers, stores, script/dialog item actions,
            spell-scroll links); tabulate effect opcodes on equip / on use
  coverage  apply the authored guidance table (proto/guidance/items_iwd.json) and report coverage (by use)
  convert   write the runtime item map module (ie_itemmap.py: IE resref -> ToEE base proto + item conditions, spells,
            charges, price, names), the item name .mes, inventory icons (TGA) + an inventory.mes, and the area
            container / store contents

Reads the player's own IE and ToEE/Temple+ installs. Reports and generated modules stay on the player's machine
(they contain names and art from both games); the repository ships code and the id-only guidance table.
See docs/items.md.

usage:
  python3 ie_items.py survey <IWD dir> [<IWD:EE dir>] --toee <ToEE dir> --md out.md --json out.json
  python3 ie_items.py coverage <IE dir>... --toee <ToEE dir> [--tp <Temple+ dir>]
  python3 ie_items.py convert <IE dir> <out dir> --toee <ToEE dir> [--tp <Temple+ dir>] [--area AR1001]
                      [--store RES] [--icons] [--option key=value ...]
"""
import os, re, sys, json, struct, argparse, collections
import iefs, iecre, ieitm, iescript as S

HERE = os.path.dirname(os.path.abspath(__file__))
GUIDANCE = os.path.join(HERE, 'guidance', 'items_iwd.json')

# IE item types -> conversion kind
KIND = {}
for t in (15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 44, 57, 69):
    KIND[t] = 'weapon'
for t in (5, 14, 31):
    KIND[t] = 'ammo'
for t in (2, 60, 61, 62, 63, 64, 65, 66, 67, 68):
    KIND[t] = 'armor'
for t in (12, 41, 47, 49, 53):
    KIND[t] = 'shield'
KIND.update({9: 'potion', 11: 'scroll', 35: 'wand', 51: 'wand', 10: 'ring', 1: 'amulet', 3: 'belt', 4: 'boots',
             6: 'bracers', 73: 'bracers', 7: 'helmet', 72: 'helmet', 32: 'cloak', 34: 'gem', 33: 'gold',
             13: 'food', 71: 'food', 56: 'food', 36: 'container', 58: 'container'})
GIVE_ACTIONS = {'giveitemcreate', 'createitem', 'createitemnumglobal', 'createitemglobal', 'giveitem',
                'takepartyitem', 'takepartyitemnum', 'takepartyitemall', 'takeitemreplace', 'destroyitem',
                'destroypartyitem', 'useitem', 'equipitem', 'dropitem', 'createvisualeffect_'}
ITEM_TRIGGERS = {'hasitem', 'partyhasitem', 'hasitemslot', 'hasitemequiped', 'hasitemequipedreal', 'numitems',
                 'numitemsgt', 'numitemslt', 'numitemsparty', 'numitemspartygt', 'numitemspartylt', 'contains',
                 'partyhasitemidentified', 'hasitemtypeslot'}
STATUSES = ('direct', 'built', 'generic', 'base', 'new', 'unmapped')
USE_KINDS = ('creature', 'container', 'store', 'script', 'dialog')


def flavor(game):
    import ie_spells
    return ie_spells.flavor(game)


def kind_of(it):
    k = KIND.get(it.type)
    if k:
        return k
    if it.spell_links():
        return 'charged'
    return 'misc'


def _tlk(game):
    p = S.find_tlk(game.root)
    return S.StrrefText(S.Tlk.load(p) if p else None)


def load_items(game):
    out, bad = {}, []
    for r in game.list('itm'):
        try:
            out[r] = ieitm.Itm(game.read(r, 'itm'), r)
        except FileNotFoundError:
            bad.append((r, 'missing'))
        except Exception as e:
            bad.append((r, str(e)[:80]))
    return out, bad


def item_uses(game, ids, items):
    """resref -> Counter(kind -> count) and resref -> set(where)."""
    import ie_creatures
    uses = collections.defaultdict(collections.Counter)
    where = collections.defaultdict(set)
    refs, _w, _a, _n = ie_creatures.creature_refs(game, ids)
    for cr in game.list('cre'):
        placed = refs.get(cr, 0)
        if not placed:
            continue
        try:
            c = iecre.Cre(game.read(cr, 'cre'), cr)
        except Exception:
            continue
        for i in c.items:
            r = i['resref']
            it = items.get(r)
            k = 'creature' if it is None or 'droppable' in it.flags else 'creature_only'
            uses[r][k] += placed; where[r].add(cr + '.cre')
    for ar in game.list('are'):
        try:
            cons = ieitm.are_container_items(game.read(ar, 'are'))
        except Exception:
            continue
        for c in cons:
            for i in c['items']:
                uses[i['resref']]['container'] += 1; where[i['resref']].add(ar + '.are')
    for st in game.list('sto'):
        try:
            s = ieitm.Sto(game.read(st, 'sto'), st)
        except Exception:
            continue
        for i in s.items:
            uses[i['resref']]['store'] += 1; where[i['resref']].add(st + '.sto')

    def calls(cs, kind, src):
        for c in S.walk_calls(cs):
            n = c.name.lower()
            if n in GIVE_ACTIONS or n in ITEM_TRIGGERS:
                a = next((x for x in c.args if isinstance(x, str) and x), None)
                if a and a.lower() in items:
                    k = kind if n in GIVE_ACTIONS else kind + '_check'
                    uses[a.lower()][k] += 1; where[a.lower()].add(src)
    for ref in game.list('bcs'):
        try:
            b = S.Bcs(game.read(ref, 'bcs'), ids, ref)
        except Exception:
            continue
        for trig, resp in b.blocks:
            calls(trig, 'script', ref + '.bcs')
            for _, acts in resp:
                calls(acts, 'script', ref + '.bcs')
    objn = list(ids['object'].by_name)
    for ref in game.list('dlg'):
        try:
            d = S.Dlg(game.read(ref, 'dlg'), ref)
        except Exception:
            continue
        for s in d.state_triggers + d.trans_triggers + d.actions:
            try:
                calls(S.parse_script_text(s, objn), 'dialog', ref + '.dlg')
            except Exception:
                pass
    return uses, where


def survey(game, log=print):
    ids = S.IdsSet(game)
    items, bad = load_items(game)
    uses, where = item_uses(game, ids, items)
    by_type = collections.defaultdict(lambda: collections.Counter())
    eq_ops, ab_ops = collections.Counter(), collections.Counter()
    scroll_links = collections.Counter()
    rows = {}
    for r, it in items.items():
        k = kind_of(it)
        u = uses.get(r, collections.Counter())
        used = sum(v for kk, v in u.items() if kk in USE_KINDS)
        by_type[it.type_name]['items'] += 1
        by_type[it.type_name]['magic' if it.magical else 'mundane'] += 1
        by_type[it.type_name]['used'] += 1 if used else 0
        by_type[it.type_name]['uses'] += used
        for e in it.equip_effects:
            eq_ops[e.opcode] += 1
        for a in it.abilities:
            for e in a.effects:
                ab_ops[e.opcode] += 1
        links = it.spell_links()
        for how, s in links:
            scroll_links['%s:%s' % (k, how)] += 1
        rows[r] = dict(type=it.type_name, kind=k, magic=it.magical, ench=it.enchantment, price=it.price,
                       lore=it.lore, flags=it.flags, uses=dict(u), used=used, links=links,
                       equip_ops=sorted({e.opcode for e in it.equip_effects}),
                       ability_ops=sorted({e.opcode for a in it.abilities for e in a.effects}))
    kinds = collections.Counter()
    for r, x in rows.items():
        kinds[(x['kind'], 'magic' if x['magic'] else 'mundane', 'used' if x['used'] else 'unused')] += 1
    missing = sorted(r for r in uses if r not in items)
    rep = dict(root=game.root, flavor=flavor(game), items=len(items), bad=bad, missing_referenced=missing,
               by_type={k: dict(v) for k, v in sorted(by_type.items(), key=lambda kv: -kv[1]['items'])},
               kinds={'%s/%s/%s' % k: v for k, v in sorted(kinds.items())},
               use_totals={k: sum(u.get(k, 0) for u in uses.values()) for k in
                           USE_KINDS + ('creature_only', 'script_check', 'dialog_check')},
               used_items=sum(1 for x in rows.values() if x['used']),
               magic_used=sum(1 for x in rows.values() if x['used'] and x['magic']),
               spell_links=dict(scroll_links), equip_opcodes=eq_ops.most_common(), ability_opcodes=ab_ops.most_common(),
               rows=rows)
    log('%s: %d items (%d used, %d magic used), uses %s' % (game.root, len(items), rep['used_items'],
                                                            rep['magic_used'], rep['use_totals']))
    return rep


def survey_md(reps, cov=None):
    L = ['# Item survey (local only: contains resrefs of the player\'s installs)', '']
    for rep in reps:
        L.append('## %s (%s)' % (rep['root'], rep['flavor']))
        L.append('')
        L.append('- items: %d, parse failures: %d, referenced but missing: %d' % (
            rep['items'], len([b for b in rep['bad'] if b[1] != 'missing']), len(rep['missing_referenced'])))
        L.append('- used: %d items (%d magic); uses by source: %s' % (rep['used_items'], rep['magic_used'],
                 ', '.join('%s %d' % kv for kv in rep['use_totals'].items())))
        L.append('- spell links (kind:how): %s' % ', '.join('%s %d' % kv for kv in sorted(rep['spell_links'].items())))
        L.append('- equip opcodes (top 25): %s' % ', '.join('%d:%d' % kv for kv in rep['equip_opcodes'][:25]))
        L.append('- ability opcodes (top 25): %s' % ', '.join('%d:%d' % kv for kv in rep['ability_opcodes'][:25]))
        L.append('')
        L.append('| IE category | items | magic | mundane | used | uses |')
        L.append('|---|---|---|---|---|---|')
        for k, v in rep['by_type'].items():
            L.append('| %s | %d | %d | %d | %d | %d |' % (k, v.get('items', 0), v.get('magic', 0), v.get('mundane', 0),
                                                          v.get('used', 0), v.get('uses', 0)))
        L.append('')
        L.append('| kind / magic / used | items |')
        L.append('|---|---|')
        for k, v in rep['kinds'].items():
            L.append('| %s | %d |' % (k, v))
        L.append('')
        if cov and rep['root'] in cov:
            c = cov[rep['root']]
            L.append('### Coverage (guidance + rules)')
            L.append('')
            L.append('| status | items | used items | uses |')
            L.append('|---|---|---|---|')
            for k in sorted(c['by_status']):
                v = c['by_status'][k]
                L.append('| %s | %d | %d | %d |' % (k, v['items'], v['used'], v['uses']))
            L.append('')
            L.append('- weighted by use (%%): %s' % ', '.join('%s %.1f' % kv for kv in sorted(c['weighted'].items())))
            L.append('')
            L.append('| kind | ' + ' | '.join(STATUSES) + ' |')
            L.append('|---|' + '---|' * len(STATUSES))
            for k, v in sorted(c['by_kind'].items()):
                L.append('| %s | %s |' % (k, ' | '.join(str(v.get(s_, 0)) for s_ in STATUSES)))
            L.append('')
    return '\n'.join(L) + '\n'


# --------------------------------------------------------------------------------------------- adjudication
# 2e -> 3.5 judgement calls for items (docs/items.md, ITEM-ADJ-n). Every one is a switch; the value here is the
# recommended default. Override per run with --option key=value.
ITEM_OPTIONS = {
    'weapon_stats': 'toee_base',     # ITEM-ADJ-1  damage dice / crit range / crit multiplier of the ToEE base weapon | 'ie_dice'
    'weapon_speed': 'drop',          # ITEM-ADJ-2  2e speed factor and IE weapon size dropped (3.5 has neither) | 'initiative'
    'armor_stats': 'toee_base',      # ITEM-ADJ-3  3.5 armor bonus / max Dex / check penalty / spell failure of the ToEE base armor,
                                     #             magic = IE (mundane AC - item AC) as Armor Enhancement Bonus | 'ie_ac'
    'enchantment': 'cap5',           # ITEM-ADJ-4  IE +N (enchantment field or THAC0 bonus, whichever is higher) -> enhancement +N,
                                     #             capped at +5 | 'uncapped'
    'charges': 'ie',                 # ITEM-ADJ-5  keep the IE charge count; recharging items -> N uses per day | '35' (wands 50)
    'cursed': 'flag',                # ITEM-ADJ-6  cursed items keep their (bad) effects, are flagged in the notes, can be removed | 'skip'
    'stat_set': 'enh_table',         # ITEM-ADJ-7  "set STR/DEX/... to X" -> enhancement bonus by table (18: +2, 19-20: +4, 21+: +6);
                                     #             "+N" -> +N | 'ie_set'
    'prices': '35',                  # ITEM-ADJ-8  3.5 price (ToEE base worth + SRD bonus price) | 'ie' (IE gp price, 1 gp = 1 gp)
    'store_markup': 'toee',          # ITEM-ADJ-8b ToEE barter (Appraise-based) instead of IE sell/buy markups | 'ie'
    'identify': 'lore',              # ITEM-ADJ-9  magic items with IE lore > 0 start unidentified (Identify / shop identify in ToEE);
                                     #             lore 0 identified | 'all_identified'
    'protection_items': 'srd',       # ITEM-ADJ-10 2e "protection +N" (AC +N and all saves +N): ring -> Ring of Protection +N
                                     #             (deflection), cloak -> Cloak of Resistance +N, other slots -> both bonuses | 'both'
    'saves': 'fold',                 # ITEM-ADJ-11 2e save bonuses folded to 3.5: death/polymorph -> Fort, wands/breath -> Ref,
                                     #             spells -> Will (highest per 3.5 save) | 'all_three'
    'resistances': 'step',           # ITEM-ADJ-12 IE % resistance -> 3.5 resist energy 5/10/20/30 (<50, <75, <100, 100 %);
                                     #             MR % -> SR 10 + MR/5; physical % -> DR (pct/10)/- | 'drop_physical'
    'usability': 'drop',             # ITEM-ADJ-13 2e class/kit/alignment restrictions dropped (3.5 proficiency + UMD instead) | 'note'
    'shields': 'heavy',              # ITEM-ADJ-14 IE medium and large shields -> heavy steel shield; buckler/small -> buckler/light | 'large_tower'
    'potions': 'by_effect',          # ITEM-ADJ-15 potions -> the Temple+ potion with the same main effect; heal amount picks
                                     #             CLW/CMW/CSW/CCW | 'skip'
    'unique': 'base_plus',           # ITEM-ADJ-16 IWD-unique items: closest base + whatever conditions exist, unmapped effects listed
                                     #             as notes (status 'new') | 'skip'
}

DMG = {27: 'Acid', 28: 'Cold', 29: 'Electricity', 30: 'Fire', 84: 'Fire', 85: 'Cold'}
SAVE_FOLD = {33: 'fortitude', 35: 'fortitude', 34: 'reflex', 36: 'reflex', 37: 'will'}
STAT_ATTR = {44: 'strength', 15: 'dexterity', 10: 'constitution', 19: 'intelligence', 49: 'wisdom', 6: 'charisma'}
SKILL_OPS = {59: 'skill_move_silently', 90: 'skill_open_lock', 91: 'skill_search', 92: 'skill_pick_pocket',
             275: 'skill_hide', 276: 'skill_spot', 277: 'skill_search'}
# IE on-hit damage type (opcode 12 param2 high word) -> Temple+ weapon special ability
ONHIT = {0x0002: 'Weapon Frost', 0x0004: 'Weapon Shock', 0x0008: 'Weapon Flaming'}
ONHIT_ENH = {'Weapon Frost': 1, 'Weapon Shock': 1, 'Weapon Flaming': 1}
COSMETIC = {144, 145, 7, 8, 9, 50, 51, 52, 53, 61, 65, 66, 138, 139, 140, 141, 142, 174, 215, 233, 240, 271, 291, 327, 336}


def _dice(a):
    return '%dd%d' % (a.dice_n, a.dice_sides) if a.dice_n else ''


def _norm(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


class ItemMapper(object):
    """IE ITM -> {status, proto, label, conds, worth, ...} from the guidance rules (docs/items.md)."""

    def __init__(self, game, toee, tp=None, options=None, guidance=GUIDANCE):
        import toeedata
        self.game = game
        self.opt = dict(ITEM_OPTIONS); self.opt.update(options or {})
        self.g = json.load(open(guidance))
        td = toeedata.ToEEData(toee)
        self.protos = td.protos()
        self.descr = td.mes('mes/description.mes')
        self.items, _ = load_items(game)
        self.text = _tlk(game)
        self.spells = None
        if tp is not None or toee:
            import ie_spells
            try:
                self.spells = ie_spells.SpellMapper(game, ie_spells.TPSpells(toee, tp))
            except Exception:
                self.spells = None
        self._spell_items()

    def label(self, pid):
        r = self.protos.get(pid)
        if not r:
            return '?'
        d = r[23].strip() or r[22].strip()       # description id (column 23 in the protos.tab Temple+ loads)
        return self.descr.get(int(d), '?') if d.isdigit() else '?'

    def worth(self, pid):
        r = self.protos.get(pid)
        try:
            return int(r[52])
        except Exception:
            return 0

    def _spell_items(self):
        """Temple+ spell -> proto, per item kind (scroll / potion / wand), from the spell columns of protos.tab."""
        self.spell_items = {'scroll': {}, 'potion': {}, 'wand': {}}
        tp = self.spells.tp if self.spells else None
        for pid, r in sorted(self.protos.items()):
            kind = {'obj_t_scroll': 'scroll', 'obj_t_food': 'potion'}.get(r[1])
            if r[1] == 'obj_t_generic' and 'wand' in self.label(pid).lower():
                kind = 'wand'
            if not kind:
                continue
            for c in r[312:332]:
                m = re.match(r"\s*'([^']+)'", c)
                if m and tp:
                    sid = tp.by_name.get(_norm(m.group(1)).replace(' ', ''))
                    if sid is None:
                        sid = next((k for k, v in tp.names.items() if _norm(v) == _norm(m.group(1))), None)
                    if sid is not None:
                        self.spell_items[kind].setdefault(sid, pid)
                    break

    # ---- rules
    def weapon_base(self, it):
        a = next((x for x in it.abilities if x.attack_type in ('melee', 'ranged', 'launcher')), None)
        for rule in self.g['weapons']:
            if it.type not in rule['types']:
                continue
            if 'prof' in rule and it.proficiency not in rule['prof']:
                continue
            if 'anim' in rule and it.anim.upper() not in rule['anim']:
                continue
            if 'dice' in rule and (not a or _dice(a) not in rule['dice']):
                continue
            if 'two_handed' in rule and ('two_handed' in it.flags) != rule['two_handed']:
                continue
            if 'attack' in rule and (not a or a.attack_type not in rule['attack']):
                continue
            if 'speed_min' in rule and (not a or a.speed < rule['speed_min']):
                continue
            return rule['proto'], rule['label']
        return None, None

    def armor_base(self, it):
        mods = {(e.param1, e.param2) for e in it.equip_effects if e.opcode == 0 and e.param2 in (1, 2, 4, 8)}
        for rule in self.g['armor']:
            if it.anim.upper() not in rule['anim']:
                continue
            if 'has_mod' in rule and not any(tuple(m) in mods or any(p2 == m[1] and p1 == m[0] for p1, p2 in mods)
                                             for m in rule['has_mod']):
                continue
            return rule
        return None

    def map(self, res):
        it = self.items.get(res)
        if it is None:
            return dict(res=res, status='unmapped', notes=['no ITM'])
        k = kind_of(it)
        e = dict(res=res, kind=k, ie_type=it.type_name, magic=it.magical, status='base', proto=None, label='',
                 conds=[], notes=[], qty=0, charges=0, ench=0, spell=None, ie_price=it.price, icon=it.icon,
                 ground=it.ground_icon, weight=it.weight)
        ov = self.g.get('overrides', {}).get(res)
        handler = getattr(self, '_k_' + k, self._k_misc)
        handler(it, e)
        if ov:
            e['proto'], e['label'] = ov['proto'], ov.get('label', self.label(ov['proto']))
            if ov.get('status'):
                e['status'] = ov['status']; e.pop('dropped', None)
        if k in ('weapon', 'armor', 'shield', 'ring', 'amulet', 'belt', 'boots', 'bracers', 'helmet', 'cloak'):
            self._equip_effects(it, e)
        if 'cursed' in it.flags:
            e['notes'].append('cursed (ITEM-ADJ-6: %s)' % self.opt['cursed'])
        if it.unusable_by and self.opt['usability'] == 'note':
            e['notes'].append('IE unusable by: %s' % ','.join(it.unusable_by))
        if e['kind'] == 'scroll' and e['spell'] and e['spell'].get('label'):
            e['label'] = 'scroll: ' + e['spell']['label']
        if e['proto'] is None:
            e['status'] = 'unmapped'
        elif e['kind'] in ('misc', 'container') and e['status'] == 'base' and not e['conds']:
            e['status'] = 'generic'          # ToEE stand-in object carrying the IE name, icon and price
        elif e['status'] == 'base' and not it.magical and not e.get('dropped') and \
                all(c[0] == 'Weapon Masterwork' for c in e['conds']):
            e['status'] = 'direct'
        elif e['status'] == 'base' and e['conds']:
            e['status'] = 'built'
        if e['status'] in ('built', 'base') and e.get('dropped'):
            e['status'] = 'new' if it.magical else e['status']
        e['ident'] = not (it.magical and it.lore > 0) or self.opt['identify'] == 'all_identified'
        e['worth'] = self._price(it, e)
        return e

    # ---- per kind
    def _k_weapon(self, it, e):
        e['proto'], e['label'] = self.weapon_base(it)
        a = next((x for x in it.abilities if x.attack_type in ('melee', 'ranged', 'launcher')), None)
        enh = max(it.enchantment, a.thac0_bonus if a else 0) if it.magical else 0
        if not it.magical and a and a.thac0_bonus > 0:
            e['conds'].append(['Weapon Masterwork', 0, 0])     # IE "high quality" (+1 to hit, not magical)
        if self.opt['enchantment'] == 'cap5':
            enh = min(enh, 5)
        if enh > 0:
            e['conds'].append(['Weapon Enhancement Bonus', enh, 0]); e['ench'] = enh
        if a:
            for fx in a.effects:
                if fx.opcode == 12:
                    sp = ONHIT.get((fx.param2 >> 16) & 0xffff)
                    if sp and not any(c[0] == sp for c in e['conds']):
                        e['conds'].append([sp, 0, 0])
                    elif not sp:
                        e.setdefault('dropped', []).append('on-hit damage type 0x%x' % (fx.param2 >> 16))
                elif fx.opcode not in COSMETIC:
                    e.setdefault('dropped', []).append('on-hit op %d' % fx.opcode)
        if 'silver' in it.flags:
            e['conds'].append(['Weapon Silver', 0, 0])
        if self.opt['weapon_speed'] == 'drop' and a and it.magical and a.speed < 3:
            e['notes'].append('IE speed %d dropped (ITEM-ADJ-2)' % a.speed)

    def _k_ammo(self, it, e):
        tbl = self.g['ammo'].get(str(it.type), {})
        a = next(iter(it.abilities), None)
        enh = max(it.enchantment, a.thac0_bonus if a else 0)
        best = tbl.get(str(min(enh, max(int(x) for x in tbl) if tbl else 0)))
        if best:
            e['proto'], e['label'] = best
            e['status'] = 'direct'
        e['qty'] = max(1, it.stack and 20)
        if a:
            for fx in a.effects:
                if fx.opcode == 12 and ONHIT.get((fx.param2 >> 16) & 0xffff):
                    e['conds'].append([ONHIT[(fx.param2 >> 16) & 0xffff], 0, 0]); e['status'] = 'base'

    def _k_armor(self, it, e):
        rule = self.armor_base(it)
        if not rule:
            return
        e['proto'], e['label'] = rule['proto'], rule['label']
        setac = [x.param1 for x in it.equip_effects if x.opcode == 0 and x.param2 == 16]
        if rule.get('robe'):
            if setac and setac[0] < 10:
                e['conds'].append(['Armor Bonus', 10 - setac[0], 0])
            return
        if setac:
            enh = rule['mundane_ac'] - setac[0]
            if enh > 0:
                enh = min(enh, 5) if self.opt['enchantment'] == 'cap5' else enh
                e['conds'].append(['Armor Enhancement Bonus', enh, 0]); e['ench'] = enh
        elif it.magical:
            e['notes'].append('no base-AC effect')

    def _k_shield(self, it, e):
        b = self.g['shields'].get(str(it.type))
        if self.opt['shields'] == 'large_tower' and it.type == 53:
            b = self.g['shield_tower']
        if not b:
            return
        e['proto'], e['label'] = b
        gen = [x.param1 for x in it.equip_effects if x.opcode == 0 and x.param2 == 0]
        if gen and gen[0] > 1:
            enh = min(gen[0] - 1, 5)
            e['conds'].append(['Shield Enhancement Bonus', enh, 0]); e['ench'] = enh

    def _accessory(self, it, e, slot):
        b = self.g['accessory_base'].get(slot)
        if b:
            e['proto'], e['label'] = b

    def _k_ring(self, it, e):
        self._accessory(it, e, 'ring')

    def _k_amulet(self, it, e):
        self._accessory(it, e, 'amulet')

    def _k_boots(self, it, e):
        self._accessory(it, e, 'boots')

    def _k_bracers(self, it, e):
        self._accessory(it, e, 'bracers')

    def _k_helmet(self, it, e):
        self._accessory(it, e, 'helmet')

    def _k_cloak(self, it, e):
        self._accessory(it, e, 'cloak')

    def _k_belt(self, it, e):
        st = [s for s in it.stat_effects() if s[0] == 'STR']
        if not st:
            m = self.g['misc']['generic']; e['proto'], e['label'] = m
            if it.magical:
                e.setdefault('dropped', []).append('belt without STR effect (no ToEE belt slot base)')

    def _spell_item(self, it, e, kind):
        links = it.spell_links()
        cast = [s for h, s in links if h == 'cast'] or [s for h, s in links]
        if not cast or not self.spells:
            return False
        m = self.spells.lookup(cast[0])
        e['spell'] = dict(ie=cast[0], toee=m['toee'], label=m['label'], cls=m['cls'])
        pid = self.spell_items[kind].get(m['toee']) if m['toee'] is not None else None
        if pid:
            e['proto'], e['label'] = pid, self.label(pid); e['status'] = 'direct'
            return True
        e['status'] = 'new'
        e.setdefault('dropped', []).append('no ToEE %s carries %s' % (kind, m['label'] or cast[0]))
        return False

    def _k_scroll(self, it, e):
        if not self._spell_item(it, e, 'scroll'):
            m = self.g['misc']['note']; e['proto'], e['label'] = m
            if not e['spell']:
                e['status'] = 'base'

    def _k_wand(self, it, e):
        a = next((x for x in it.abilities if x.charges), None)
        e['charges'] = a.charges if a else 0
        if not self._spell_item(it, e, 'wand'):
            m = self.g['misc']['generic']; e['proto'], e['label'] = m

    def _k_charged(self, it, e):
        self._k_wand(it, e)

    def _k_potion(self, it, e):
        if self._spell_item(it, e, 'potion'):
            return
        ops = [(fx.opcode, fx.param1) for a in it.abilities for fx in a.effects if fx.opcode not in COSMETIC]
        for rule in self.g['potion_opcodes']:
            hit = [p1 for op, p1 in ops if op == rule['op']]
            if hit and ('max' not in rule or hit[0] <= rule['max']):
                e['proto'], e['label'] = rule['proto'], rule['label']; e['status'] = 'direct'
                return
        m = self.g['misc']['food']; e['proto'], e['label'] = m
        e['status'] = 'new'; e.setdefault('dropped', []).append('potion effects %s' % sorted({o for o, _ in ops})[:6])

    def _k_gem(self, it, e):
        best = self.g['gems_by_worth_gp'][0]
        for row in self.g['gems_by_worth_gp']:
            if it.price >= row[0]:
                best = row
        e['proto'], e['label'] = best[1], best[2]; e['status'] = 'direct'

    def _k_gold(self, it, e):
        e['proto'], e['label'] = self.g['money']['gold']; e['status'] = 'direct'; e['qty'] = 1

    def _k_food(self, it, e):
        self._k_potion(it, e)

    def _k_container(self, it, e):
        e['proto'], e['label'] = self.g['misc']['generic']

    def _k_misc(self, it, e):
        k = 'book' if it.type in (37,) else 'key' if it.type == 37 else 'generic'
        if it.type == 37:
            k = 'book'
        e['proto'], e['label'] = self.g['misc'][k]
        if it.magical and it.abilities:
            self._spell_item(it, e, 'wand')

    # ---- equip effects -> item conditions
    def _equip_effects(self, it, e):
        saves, conds = {}, e['conds']
        acgen = 0
        for fx in it.equip_effects:
            op, p1, p2 = fx.opcode, fx.param1, fx.param2
            if op == 0:
                if p2 == 0 and e['kind'] not in ('shield',):
                    acgen = max(acgen, p1)
                elif p2 == 16 and e['kind'] == 'bracers':
                    n = max(0, min(8, 10 - p1))
                    named = self.g['named']['bracers_of_armor'].get(str(n))
                    if named and not conds:
                        e['proto'], e['label'] = named; e['status'] = 'direct'
                    else:
                        conds.append(['Armor Bonus', n, 0])
                elif p2 == 16 and e['kind'] not in ('armor',):
                    conds.append(['Armor Bonus', max(0, 10 - p1), 0])
            elif op in SAVE_FOLD:
                s = SAVE_FOLD[op] if self.opt['saves'] == 'fold' else None
                for sv in ([s] if s else ['fortitude', 'reflex', 'will']):
                    saves[sv] = max(saves.get(sv, -99), p1)
            elif op in STAT_ATTR:
                n = p1 if p2 == 0 else self._stat_set(p1) if p2 == 1 else 0
                if n:
                    conds.append(['Attribute Enhancement Bonus', 'attribute_' + STAT_ATTR[op], n])
            elif op in DMG:
                v = self._resist(p1)
                if v:
                    conds.append(['Elemental Resistance', DMG[op], v])
            elif op == 166:
                conds.append(['Armor Spell Resistance', min(30, 10 + p1 // 5), 0])
            elif op == 54 and p1 > 0:
                conds.append(['To Hit Bonus', p1, 0])
            elif op == 73 and p1 > 0:
                conds.append(['Damage Bonus', p1, 0])
            elif op in (86, 87, 88, 89) and self.opt['resistances'] == 'step' and p1 >= 10:
                if not any(c[0] == 'Monster DR All' for c in conds):
                    conds.append(['Monster DR All', max(1, p1 // 10), 0])
            elif op in SKILL_OPS and p1:
                conds.append(['Skill Circumstance Bonus', SKILL_OPS[op], max(1, p1 // 5)])
            elif op == 126 and p1 > 0:
                conds.append(['Boots of speed', 10, 10])
            elif op == 20:
                conds.append(['Ring of Invisibility', 0, 0])
            elif op not in COSMETIC and op not in (1, 2, 3, 4, 5, 97, 101, 206, 261, 267, 296, 318, 319, 324):
                e.setdefault('dropped', []).append('equip op %d' % op)
        prot = acgen and saves and len(saves) >= 2
        named = None
        if prot and self.opt['protection_items'] == 'srd':
            n = str(min(acgen, 3))
            if e['kind'] == 'ring':
                named = self.g['named']['ring_of_protection'].get(n)
            elif e['kind'] == 'cloak':
                named = self.g['named']['cloak_of_resistance'].get(str(min(max(saves.values()), 4)))
        if named and not conds:
            e['proto'], e['label'] = named; e['status'] = 'direct'
            return
        if acgen and e['kind'] not in ('armor', 'shield'):
            conds.append(['Deflection Bonus', acgen, 0])
        for sv, n in sorted(saves.items()):
            if n:
                conds.append(['Saving Throw Resistance Bonus', 'saving_throw_' + sv, n])
        # named stat items (ITEM-ADJ-7)
        st = [c for c in conds if c[0] == 'Attribute Enhancement Bonus']
        if len(conds) == 1 and st:
            a, n = st[0][1], st[0][2]
            key = {('attribute_strength', 'bracers'): 'strength_gloves', ('attribute_strength', 'belt'): 'strength_belt',
                   ('attribute_dexterity', 'bracers'): 'dexterity_gloves'}.get((a, e['kind']))
            nm = self.g['named'].get(key, {}).get(str(n)) if key else None
            if nm:
                e['proto'], e['label'] = nm; e['status'] = 'direct'; del conds[:]
        if e['kind'] == 'belt' and st and e['proto'] is None:
            e['proto'], e['label'] = self.g['named']['strength_belt']['4']
            e['conds'][:] = [c for c in conds if c is not st[0]] + [['Attribute Enhancement Bonus', st[0][1], st[0][2]]]

    def _stat_set(self, v):
        if self.opt['stat_set'] == 'ie_set':
            return max(0, v - 10)
        return 2 if v <= 18 else 4 if v <= 20 else 6

    def _resist(self, pct):
        if pct <= 0:
            return 0
        return 5 if pct < 50 else 10 if pct < 75 else 20 if pct < 100 else 30

    # ---- price (ITEM-ADJ-8), ToEE copper
    def _price(self, it, e):
        if self.opt['prices'] == 'ie' or e['proto'] is None:
            return it.price * 100
        base = self.worth(e['proto'])
        if e['status'] == 'direct' or not e['conds']:
            return base if base else it.price * 100
        gp = 0
        k = e['kind']
        bonus = 0
        for c in e['conds']:
            n = c[1] if isinstance(c[1], int) else c[2] if isinstance(c[2], int) else 0
            if c[0] in ('Weapon Enhancement Bonus', 'Armor Enhancement Bonus', 'Shield Enhancement Bonus'):
                bonus += n
            elif c[0] in ONHIT_ENH:
                bonus += ONHIT_ENH[c[0]]
            elif c[0] == 'Deflection Bonus':
                gp += 2000 * n * n
            elif c[0] in ('Saving Throw Resistance Bonus',):
                gp += 1000 * n * n // 3
            elif c[0] in ('Attribute Enhancement Bonus', 'Armor Bonus'):
                gp += 1000 * n * n
            elif c[0] == 'Elemental Resistance':
                gp += {5: 6000, 10: 12000, 20: 28000, 30: 44000}.get(n, 12000)
            elif c[0] == 'Armor Spell Resistance':
                gp += max(10000, (n - 12) * 10000)
            else:
                gp += 2000
        if bonus:
            gp += (2000 if k in ('weapon', 'ammo') else 1000) * bonus * bonus + (300 if k == 'weapon' else 150)
        return base + gp * 100


def coverage(mapper, rep):
    """Map every item; tabulate statuses by items, used items and uses (survey weights)."""
    by = collections.defaultdict(lambda: dict(items=0, used=0, uses=0))
    by_kind = collections.defaultdict(lambda: collections.Counter())
    entries = {}
    for r in sorted(mapper.items):
        e = mapper.map(r)
        u = rep['rows'].get(r, {}).get('used', 0) if rep else 0
        entries[r] = e
        b = by[e['status']]
        b['items'] += 1; b['used'] += 1 if u else 0; b['uses'] += u
        by_kind[e['kind']][e['status']] += u
    tot = sum(v['uses'] for v in by.values()) or 1
    return dict(by_status=dict(by), by_kind={k: dict(v) for k, v in by_kind.items()},
                weighted={k: round(100.0 * v['uses'] / tot, 1) for k, v in by.items()}), entries


# --------------------------------------------------------------------------------------------- convert
NAME_BASE = 22000          # item names in mes/description/ie2toee_items.mes: above description.mes (20207), below the
                           # creatures' 27000; Temple+ only serves ids < 30000 from mes/description/ before a gamedesc exists
ICON_BASE = 651            # new inventory.mes ids follow the vanilla ones (650 is the highest)
ICON_PREFIX = 'ie2toee_'   # art/interface/inventory/ie2toee_<res>.tga (flat: the engine does not take sub-folders here)


def _tga64(rgba):
    """64x64 32-bit TGA (bottom-left origin, 8 alpha bits), the format of ToEE's inventory icons."""
    import numpy as np
    h, w = rgba.shape[:2]
    k = max(1, min(60 // max(w, 1), 60 // max(h, 1)))
    if k > 1:
        rgba = rgba.repeat(k, 0).repeat(k, 1)
        h, w = rgba.shape[:2]
    if w > 64 or h > 64:
        from PIL import Image
        im = Image.fromarray(rgba, 'RGBA'); im.thumbnail((62, 62)); rgba = np.asarray(im); h, w = rgba.shape[:2]
    can = np.zeros((64, 64, 4), np.uint8)
    y0, x0 = (64 - h) // 2, (64 - w) // 2
    can[y0:y0 + h, x0:x0 + w] = rgba
    bgra = can[:, :, [2, 1, 0, 3]][::-1]
    return struct.pack('<BBBHHBHHHHBB', 0, 0, 2, 0, 0, 0, 0, 0, 64, 64, 32, 8) + bgra.tobytes()


def icon_frame(game, ref, loader=None):
    import iegui
    b = iegui.Bam(game.read(ref, 'bam'), loader)
    cand = [c[0] for c in b.cycles if c] or [0]
    best = max(cand, key=lambda i: b.frames[i].shape[0] * b.frames[i].shape[1])
    return b.frames[best]


def convert(game, out, toee, tp=None, options=None, areas=(), stores=(), objects=None, icons=True, log=print):
    m = ItemMapper(game, toee, tp, options)
    rep = None
    wanted = set(m.items)
    names, entries = {}, {}
    for i, r in enumerate(sorted(wanted)):
        e = m.map(r); it = m.items[r]
        nid = NAME_BASE + 2 * i
        names[nid] = m.text(it.name_id) if it.name_id >= 0 else ''
        names[nid + 1] = m.text(it.name_unid) if it.name_unid >= 0 else names[nid]
        if not names[nid].strip():
            names[nid] = names[nid + 1] or r
        e['name'] = nid
        entries[r] = e
    # inventory icons
    icon_ids = {}
    if icons:
        import iegui, toeedata
        loader = iegui.pvrz_loader_for(game)
        idir = os.path.join(out, 'data', 'art', 'interface', 'inventory')   # data/: the UI reads it before modules mount
        os.makedirs(idir, exist_ok=True)
        td = toeedata.ToEEData(toee)
        inv = td.mes('art/interface/inventory/inventory.mes')
        if tp:
            p = os.path.join(tp, 'tpdata', 'tpgamefiles.dat')
            if os.path.isfile(p):
                a = toeedata.DatArchive(p)
                if 'art/interface/inventory/inventory.mes' in a.files:
                    for mm in re.finditer(r'\{(\d+)\}\s*\{([^}]*)\}', a.read('art/interface/inventory/inventory.mes').decode('latin-1')):
                        inv[int(mm.group(1))] = mm.group(2)
        nxt = max(ICON_BASE, max(inv) + 1)
        done = {}
        for r, e in sorted(entries.items()):
            ref = m.items[r].icon
            if not ref:
                continue
            if ref not in done:
                try:
                    fr = icon_frame(game, ref, loader)
                except Exception as ex:
                    done[ref] = None; continue
                open(os.path.join(idir, ICON_PREFIX + ref + '.tga'), 'wb').write(_tga64(fr))
                inv[nxt] = '%s%s.tga' % (ICON_PREFIX, ref); done[ref] = nxt; nxt += 1
            if done[ref] is not None:
                e['icon_id'] = done[ref]
        with open(os.path.join(idir, 'inventory.mes'), 'w',
                  encoding='latin-1', errors='replace') as f:
            f.write(''.join('{%d}{%s}\n' % kv for kv in sorted(inv.items())))
        log('icons: %d BAMs -> TGA (%d failed)' % (sum(1 for v in done.values() if v), sum(1 for v in done.values() if v is None)))
    # names
    md = os.path.join(out, 'modules', 'ToEE', 'mes', 'description')
    os.makedirs(md, exist_ok=True)
    with open(os.path.join(md, 'ie2toee_items.mes'), 'w', encoding='latin-1', errors='replace') as f:
        f.write(''.join('{%d}{%s}\n' % (k, re.sub(r'[\x00-\x1f]+', ' ', v).replace('{', '(').replace('}', ')').strip())
                        for k, v in sorted(names.items())))
    # containers + stores
    cons = {}
    objs = json.load(open(objects)) if objects else {}
    for ar in areas:
        cl = ieitm.are_container_items(game.read(ar.lower(), 'are'))
        oc = {c['name']: c for c in objs.get('containers', [])} if objs else {}
        lst = []
        for c in cl:
            b = m.g['containers'].get(str(c['type']), m.g['containers']['default'])
            lst.append(dict(name=c['name'], ie=[c['x'], c['y']], toee=(oc.get(c['name']) or {}).get('toee'),
                            proto=b[0], label=b[1], lock=c['lock'], trapped=c['trapped'], key=c['key'],
                            items=[[i['resref'], max(1, i['charges'][0])] for i in c['items']]))
        cons[ar.upper()] = lst
    sto = {}
    for s in stores:
        S_ = ieitm.Sto(game.read(s.lower(), 'sto'), s)
        sto[s.lower()] = dict(type=S_.type, sell=S_.sell_markup, buy=S_.buy_markup, allow=S_.allow,
                              items=[[i['resref'], (5 if i['infinite'] else max(1, i['stock']))] for i in S_.items],
                              cures=len(S_.cures), container=m.g['store_container'][0])
    keep = ('proto', 'conds', 'worth', 'name', 'icon_id', 'ident', 'qty', 'charges', 'magic', 'kind', 'status', 'weight')
    short = {'proto': 'p', 'conds': 'c', 'worth': 'w', 'name': 'n', 'icon_id': 'i', 'ident': 'id', 'qty': 'q',
             'charges': 'ch', 'magic': 'm', 'kind': 'k', 'status': 's', 'weight': 'wt'}
    items = {r: {short[k]: e[k] for k in keep if e.get(k) not in (None, [], 0, '') or k == 'ident'}
             for r, e in entries.items() if e.get('proto')}
    with open(os.path.join(out, 'ie_itemmap.py'), 'w') as f:
        f.write('# generated by proto/ie_items.py convert (local only: IE resrefs of the player\'s install)\n')
        f.write('ITEMS = %r\n' % items)
        f.write('CONTAINERS = %r\n' % cons)
        f.write('STORES = %r\n' % sto)
    json.dump(entries, open(os.path.join(out, 'item_map.json'), 'w'), indent=0)
    log('items: %d mapped of %d -> %s' % (len(items), len(entries), out))
    return entries, cons, sto


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd')
    a = sub.add_parser('survey'); a.add_argument('ie', nargs='+'); a.add_argument('--toee'); a.add_argument('--tp')
    a.add_argument('--md'); a.add_argument('--json')
    c = sub.add_parser('coverage'); c.add_argument('ie', nargs='+'); c.add_argument('--toee', required=True)
    c.add_argument('--tp'); c.add_argument('--option', action='append', default=[])
    v = sub.add_parser('convert'); v.add_argument('ie'); v.add_argument('out'); v.add_argument('--toee', required=True)
    v.add_argument('--tp'); v.add_argument('--area', action='append', default=[]); v.add_argument('--store', action='append', default=[])
    v.add_argument('--objects'); v.add_argument('--no-icons', action='store_true'); v.add_argument('--option', action='append', default=[])
    o = ap.parse_args(argv)
    opts = lambda l: dict(x.split('=', 1) for x in l)
    if o.cmd == 'survey' or o.cmd == 'coverage':
        reps, cov = [], {}
        for root in o.ie:
            g = iefs.IEGame(root)
            rep = survey(g)
            reps.append(rep)
            if o.toee:
                m = ItemMapper(g, o.toee, o.tp, opts(getattr(o, 'option', [])))
                cv, ent = coverage(m, rep)
                cov[g.root] = cv; rep['coverage'] = cv
                rep['map'] = {r: {k: e.get(k) for k in ('status', 'proto', 'label', 'conds', 'notes', 'dropped', 'spell')}
                              for r, e in ent.items()}
                print('coverage %s: %s (by use %%: %s)' % (g.root, {k: v['items'] for k, v in cv['by_status'].items()},
                                                           cv['weighted']))
        if getattr(o, 'md', None):
            open(o.md, 'w').write(survey_md(reps, cov))
        if getattr(o, 'json', None):
            json.dump(reps, open(o.json, 'w'), indent=1, default=list)
    elif o.cmd == 'convert':
        os.makedirs(o.out, exist_ok=True)
        convert(iefs.IEGame(o.ie), o.out, o.toee, o.tp, opts(o.option), o.area, o.store, o.objects, not o.no_icons)
    else:
        ap.print_help()


if __name__ == '__main__':
    main()

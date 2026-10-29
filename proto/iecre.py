"""IE creature (CRE) and item (ITM) readers, written from the IESDP file-format pages only.

  CRE V1.0  BG/BG2/EE (IWD:EE stores every creature as V1.0)
  CRE V9.0  classic IWD / HoW / TotL: same header as V1.0 up to 0x270, then 0x68 bytes of extra IWD fields
            (visibility, death variables, saved location), so the IDS bytes and section offsets move by +0x68
  CRE V2.2  IWD2: different header (3e stats, feats, skills, per-class levels). Parsed into the same attribute names
            (2e-equivalent compat values: thac0 = 20 - BAB, descending AC = 20 - AC) plus a `rules3e` dict holding
            the native 3e numbers (BAB, Fort/Ref/Will, per-class levels, feats, skills) for 3e-aware converters
  ITM V1    the fields the creature converter needs (type, proficiency, enchantment, damage of each ability)

Everything read here comes from the player's own install at conversion time; nothing is stored in this repo.
"""
import struct

SLOT_NAMES = (['helmet', 'armor', 'shield', 'gloves', 'lring', 'rring', 'amulet', 'belt', 'boots',
               'weapon1', 'weapon2', 'weapon3', 'weapon4', 'quiver1', 'quiver2', 'quiver3', 'quiver4',
               'cloak', 'quick1', 'quick2', 'quick3'] + ['inv%d' % i for i in range(1, 17)] + ['magic_weapon'])
EFF_V1_SIZE, EFF_V2_SIZE = 0x30, 0x108   # CRE-embedded V2 effects omit the 8-byte EFF header


def cstr(b):
    return b.split(b'\0')[0].decode('latin-1')


class Effect(object):
    __slots__ = ('opcode', 'target', 'power', 'param1', 'param2', 'timing', 'duration', 'prob1', 'prob2',
                 'resource', 'dice_n', 'dice_s', 'save_type', 'save_bonus')

    @classmethod
    def v1(cls, d, o):
        e = cls()
        e.opcode, e.target, e.power, e.param1, e.param2, e.timing, _, e.duration, e.prob1, e.prob2 = \
            struct.unpack_from('<HBBiiBBIBB', d, o)
        e.resource = cstr(d[o + 0x14:o + 0x1c])
        e.dice_n, e.dice_s, e.save_type, e.save_bonus = struct.unpack_from('<IIIi', d, o + 0x1c)
        return e

    @classmethod
    def v2(cls, d, o):   # offsets of EFF V2 minus 8 (embedded form)
        e = cls()
        e.opcode, e.target, e.power, e.param1, e.param2 = struct.unpack_from('<IIIii', d, o + 0x08)
        e.timing = struct.unpack_from('<H', d, o + 0x1c)[0]
        e.duration = struct.unpack_from('<I', d, o + 0x20)[0]
        e.prob1, e.prob2 = struct.unpack_from('<HH', d, o + 0x24)
        e.resource = cstr(d[o + 0x28:o + 0x30])
        e.dice_n, e.dice_s, e.save_type, e.save_bonus = struct.unpack_from('<IIIi', d, o + 0x30)
        return e

    def as_dict(self):
        return {k: getattr(self, k) for k in self.__slots__}


class Cre(object):
    """Parsed creature. Attribute names follow IESDP descriptions; ids are raw IDS values (resolve with IdsSet)."""

    def __init__(self, data, resref=''):
        self.resref = resref.lower()
        sig, ver = data[:4], data[4:8]
        if sig != b'CRE ':
            raise ValueError('%s: not a CRE (%r)' % (resref, sig))
        self.version = ver.decode('latin-1').strip()
        self.rules3e = None
        if self.version == 'V2.2':
            self._parse_v22(data)
            return
        if self.version not in ('V1.0', 'V9.0'):
            raise NotImplementedError('%s: CRE %s' % (resref, self.version))
        u = lambda f, o: struct.unpack_from(f, data, o)
        self.name_strref, self.tooltip_strref, self.flags = u('<iiI', 0x08)
        self.xp_value, self.power_level, self.gold, self.state = u('<IIII', 0x14)
        self.hp, self.max_hp = u('<HH', 0x24)
        self.animation = u('<I', 0x28)[0]
        self.colors = dict(zip(('metal', 'minor', 'major', 'skin', 'leather', 'armor', 'hair'), data[0x2c:0x33]))
        self.eff_version = data[0x33]
        self.portrait_small, self.portrait_large = cstr(data[0x34:0x3c]), cstr(data[0x3c:0x44])
        self.reputation, self.hide_in_shadows = u('<bB', 0x44)
        (self.ac_natural, self.ac_effective, self.ac_crushing, self.ac_missile, self.ac_piercing,
         self.ac_slashing) = u('<6h', 0x46)
        self.thac0, self.attacks = data[0x52], data[0x53]
        self.saves = dict(zip(('death', 'wands', 'polymorph', 'breath', 'spells'), data[0x54:0x59]))
        self.resist = dict(zip(('fire', 'cold', 'electricity', 'acid', 'magic', 'magic_fire', 'magic_cold',
                                'slashing', 'crushing', 'piercing', 'missile'), data[0x59:0x64]))
        (self.detect_illusion, self.set_traps, self.lore, self.lockpicking, self.stealth, self.find_traps,
         self.pick_pockets, self.fatigue, self.intoxication) = data[0x64:0x6d]
        self.luck = u('<b', 0x6d)[0]
        self.proficiencies = list(data[0x6e:0x82])
        self.turn_undead, self.tracking = data[0x82], data[0x83]
        self.levels = list(data[0x234:0x237])
        self.sex = data[0x237]
        (self.str, self.str_bonus, self.int, self.wis, self.dex, self.con, self.cha) = data[0x238:0x23f]
        self.morale, self.morale_break, self.racial_enemy = data[0x23f], data[0x240], data[0x241]
        self.morale_recovery = u('<H', 0x242)[0]
        self.kit = u('>I', 0x244)[0]   # IESDP: stored big-endian style
        self.scripts = dict(zip(('override', 'class', 'race', 'general', 'default'),
                                (cstr(data[o:o + 8]) for o in range(0x248, 0x270, 8))))
        s = 0x68 if self.version == 'V9.0' else 0
        if s:
            self.visible = data[0x270]
            self.death_var_secondary = cstr(data[0x27e:0x29e])
            self.death_var_tertiary = cstr(data[0x29e:0x2be])
            self.saved_xy = u('<HH', 0x2c0)
        (self.ea, self.general, self.race, self.cls, self.specific, self.gender) = data[0x270 + s:0x276 + s]
        self.object_ids = list(data[0x276 + s:0x27b + s])
        self.alignment = data[0x27b + s]
        self.death_var = cstr(data[0x280 + s:0x2a0 + s])
        (ks_off, ks_n, mi_off, mi_n, ms_off, ms_n, slot_off, it_off, it_n, ef_off, ef_n) = u('<11I', 0x2a0 + s)
        self.dialog = cstr(data[0x2cc + s:0x2d4 + s])

        self.known_spells = [dict(resref=cstr(data[o:o + 8]).lower(), level=u('<H', o + 8)[0] + 1,
                                  type=('priest', 'wizard', 'innate')[min(u('<H', o + 10)[0], 2)])
                             for o in (ks_off + i * 12 for i in range(ks_n))]
        mem = [(cstr(data[o:o + 8]).lower(), u('<I', o + 8)[0]) for o in (ms_off + i * 12 for i in range(ms_n))]
        self.spell_slots, self.memorized = [], []
        for o in (mi_off + i * 16 for i in range(mi_n)):
            lvl, n, n_eff, typ, first, cnt = u('<HHHHII', o)
            t = ('priest', 'wizard', 'innate')[min(typ, 2)]
            self.spell_slots.append(dict(level=lvl + 1, type=t, slots=n, slots_effective=n_eff))
            for ref, flag in mem[first:first + cnt]:
                self.memorized.append(dict(resref=ref, level=lvl + 1, type=t, memorized=bool(flag & 1)))
        self.items = [dict(resref=cstr(data[o:o + 8]).lower(), charges=list(u('<3H', o + 0x0a)),
                           flags=u('<I', o + 0x10)[0]) for o in (it_off + i * 20 for i in range(it_n))]
        # item slots: one word per slot (0xFFFF = empty), then selected weapon + ability. V9.0 (IWD) and V1.0 (BG2/EE)
        # both use 38 slot words; the trailing pair is "selected weapon"/"selected ability".
        nslots = (it_off - slot_off) // 2 if it_off > slot_off else 40
        words = list(u('<%dH' % min(nslots, 40), slot_off)) if slot_off else []
        names = SLOT_NAMES if len(words) >= 40 else [n for n in SLOT_NAMES if n != 'quiver4']
        self.slots = {}
        for n, w in zip(names, words[:len(words) - 2]):
            if w != 0xFFFF and w < len(self.items):
                self.slots[n] = self.items[w]['resref']
        self.selected_weapon = words[-2] if len(words) >= 2 else 1000
        sz, rd = (EFF_V2_SIZE, Effect.v2) if self.eff_version == 1 else (EFF_V1_SIZE, Effect.v1)
        self.effects = [rd(data, ef_off + i * sz) for i in range(ef_n)]

    CLASSES_3E = ('barbarian', 'bard', 'cleric', 'druid', 'fighter', 'monk', 'paladin', 'ranger', 'rogue', 'sorcerer',
                  'wizard')
    SLOT_NAMES_V22 = (['helmet', 'armor', 'shield', 'gloves', 'lring', 'rring', 'amulet', 'belt', 'boots',
                       'weapon1', 'shield1', 'weapon2', 'shield2', 'weapon3', 'shield3', 'weapon4', 'shield4',
                       'quiver1', 'quiver2', 'quiver3', 'quiver4', 'cloak', 'quick1', 'quick2', 'quick3'] +
                      ['inv%d' % i for i in range(1, 25)] + ['magic_weapon'])

    def _parse_v22(self, data):
        """CRE V2.2 (IESDP cre_v2.2). Spells are 2DA-index based in V2.2 and are not resolved here yet."""
        u = lambda f, o: struct.unpack_from(f, data, o)
        self.name_strref, self.tooltip_strref, self.flags = u('<iiI', 0x08)
        self.xp_value, self.power_level, self.gold, self.state = u('<IIII', 0x14)
        self.hp, self.max_hp = u('<HH', 0x24)
        self.animation = u('<I', 0x28)[0]
        self.colors = dict(zip(('metal', 'minor', 'major', 'skin', 'leather', 'armor', 'hair'), data[0x2c:0x33]))
        self.eff_version = data[0x33]
        self.portrait_small, self.portrait_large = cstr(data[0x34:0x3c]), cstr(data[0x3c:0x44])
        self.reputation, self.hide_in_shadows = u('<bB', 0x44)
        ac3, cr, mi, pi, sl = u('<5h', 0x46)
        bab, self.attacks, fort, ref, will = data[0x50:0x55]
        self.ac_natural = self.ac_effective = 20 - ac3          # compat: descending 2e-style AC
        self.ac_crushing, self.ac_missile, self.ac_piercing, self.ac_slashing = -cr, -mi, -pi, -sl
        self.thac0 = max(0, 20 - bab)                            # compat
        self.resist = dict(zip(('fire', 'cold', 'electricity', 'acid', 'magic', 'magic_fire', 'magic_cold',
                                'slashing', 'crushing', 'piercing', 'missile'), data[0x55:0x60]))
        self.fatigue, self.intoxication = data[0x65], data[0x66]
        self.luck = u('<b', 0x67)[0]
        self.turn_undead, self.tracking = data[0x68], 0
        self.proficiencies = []
        cl = dict(zip(self.CLASSES_3E, data[0x8b:0x96]))
        top = sorted((n for n in cl.values() if n), reverse=True) or [max(1, data[0x8a])]
        self.levels = (top + [0, 0])[:3]                         # compat: highest class levels first
        self.saves = None                                        # 2e save table does not exist; see rules3e
        self.str, self.int, self.wis, self.dex, self.con, self.cha = data[0x266:0x26c]
        self.str_bonus = 0
        self.morale, self.morale_break, self.racial_enemy, self.morale_recovery = 10, 1, data[0x25b], 0
        self.kit = u('<I', 0x270)[0]
        self.scripts = {'override': cstr(data[0x274:0x27c]), 'special3': cstr(data[0x27c:0x284]),
                        'special2': cstr(data[0x284:0x28c]), 'combat': cstr(data[0x28c:0x294]),
                        'movement': cstr(data[0x294:0x29c]), 'team': cstr(data[0x1ac:0x1b4]),
                        'special1': cstr(data[0x1b4:0x1bc])}
        self.visible = data[0x29c]
        self.death_var_secondary = cstr(data[0x2aa:0x2ca]); self.death_var_tertiary = cstr(data[0x2ca:0x2ea])
        self.saved_xy = u('<HH', 0x2ec)
        (self.ea, self.general, self.race, self.cls, self.specific, self.gender) = data[0x384:0x38a]
        self.object_ids = list(data[0x38a:0x38f]); self.alignment = data[0x38f]
        self.death_var = cstr(data[0x394:0x3b4])
        self.dialog = cstr(data[0x626:0x62e])
        self.rules3e = dict(bab=bab, fort=fort, ref=ref, will=will, ac=ac3, total_level=data[0x8a],
                            class_levels={k: v for k, v in cl.items() if v}, subrace=data[0x263],
                            feats=list(u('<3I', 0x1c0)), skills=list(data[0x218:0x228]), xp_category=data[0x25a],
                            enchantment=data[0x1bc])
        self.known_spells, self.memorized, self.spell_slots = [], [], []
        # spell lists: 7 classes x 9 levels (bard cleric druid paladin ranger sorcerer wizard), then 9 domain levels and
        # innates; entries are (2DA row index, max, remaining, ?), resolved through listspll/listdomn/listinnt by the caller
        self.spells_v22 = []
        lists = [('class', c, lv, 0x3ba + 4 * (c * 9 + lv), 0x4b6 + 4 * (c * 9 + lv)) for c in range(7) for lv in range(9)]
        lists += [('domain', 1, lv, 0x5b2 + 4 * lv, 0x5d6 + 4 * lv) for lv in range(9)] + [('innate', 0, 0, 0x5fa, 0x5fe)]
        for kind, c, lv, oo, no in lists:
            off, cnt = u('<I', oo)[0], u('<I', no)[0]
            for k in range(cnt if off and off + 16 * cnt <= len(data) else 0):
                idx, mx, rem, _ = u('<4I', off + 16 * k)
                self.spells_v22.append((kind, c, lv + 1, idx, mx))
        slot_off, it_off, it_n, ef_off, ef_n = u('<5I', 0x612)
        self.items = [dict(resref=cstr(data[o:o + 8]).lower(), charges=list(u('<3H', o + 0x0a)),
                           flags=u('<I', o + 0x10)[0]) for o in (it_off + i * 20 for i in range(it_n))]
        n = len(self.SLOT_NAMES_V22)
        words = list(u('<%dH' % n, slot_off)) if slot_off and slot_off + 2 * n <= len(data) else []
        self.slots = {k: self.items[w]['resref'] for k, w in zip(self.SLOT_NAMES_V22, words)
                      if w != 0xFFFF and w < len(self.items)}
        self.selected_weapon = u('<H', slot_off + 2 * n)[0] if words else 1000
        sz, rd = (EFF_V2_SIZE, Effect.v2) if self.eff_version == 1 else (EFF_V1_SIZE, Effect.v1)
        self.effects = [rd(data, ef_off + i * sz) for i in range(ef_n)]

    @property
    def equipped(self):
        """Slots that matter for appearance and combat (worn items + the weapon in the selected slot)."""
        out = {k: v for k, v in self.slots.items() if not k.startswith(('inv', 'quick', 'quiver'))}
        sel = self.selected_weapon
        if self.rules3e is not None:   # V2.2: weapon/shield pairs; only the selected set is in hand
            out = {k: v for k, v in out.items() if not k.startswith(('weapon', 'shield')) or k == 'shield'}
            if sel != 1000 and 0 <= sel < 4:
                for k in ('weapon', 'shield'):
                    if self.slots.get('%s%d' % (k, sel + 1)):
                        out['selected_weapon' if k == 'weapon' else 'shield'] = self.slots['%s%d' % (k, sel + 1)]
            return out
        if sel != 1000 and 0 <= sel < 4:
            w = self.slots.get('weapon%d' % (sel + 1))
            if w:
                out['selected_weapon'] = w
        return out

    def as_dict(self):
        d = {k: v for k, v in self.__dict__.items()}
        d['effects'] = [e.as_dict() for e in self.effects]
        return d


ITEM_TYPES = {0: 'misc', 1: 'amulet', 2: 'armor', 3: 'belt', 4: 'boots', 5: 'arrow', 6: 'bracers', 7: 'helmet',
              8: 'key', 9: 'potion', 10: 'ring', 11: 'scroll', 12: 'shield', 13: 'food', 14: 'bullet', 15: 'bow',
              16: 'dagger', 17: 'mace', 18: 'sling', 19: 'small_sword', 20: 'large_sword', 21: 'hammer',
              22: 'morning_star', 23: 'flail', 24: 'dart', 25: 'axe', 26: 'quarterstaff', 27: 'crossbow',
              28: 'fist', 29: 'spear', 30: 'halberd', 31: 'bolt', 32: 'cloak', 33: 'gold', 34: 'gem', 35: 'wand',
              36: 'container', 37: 'books', 38: 'familiar', 39: 'tattoo', 40: 'lenses', 41: 'buckler',
              42: 'candle', 43: 'child_body', 44: 'club', 45: 'female_body', 46: 'key2', 47: 'large_shield',
              48: 'male_body', 49: 'medium_shield', 50: 'notes', 51: 'rod', 52: 'skull', 53: 'small_shield',
              54: 'spider_body', 55: 'telescope', 56: 'drink', 57: 'great_sword', 58: 'container2', 59: 'fur',
              60: 'leather_armor', 61: 'studded_leather', 62: 'chain_mail', 63: 'splint_mail', 64: 'half_plate',
              65: 'full_plate', 66: 'hide_armor', 67: 'robe', 68: 'scale_mail', 69: 'bastard_sword',
              70: 'scarf', 71: 'food2', 72: 'hat', 73: 'gauntlet'}


class Itm(object):
    def __init__(self, data, resref=''):
        self.resref = resref.lower()
        if data[:4] != b'ITM ':
            raise ValueError('%s: not an ITM' % resref)
        self.version = data[4:8].decode('latin-1').strip()
        u = lambda f, o: struct.unpack_from(f, data, o)
        self.name_unid, self.name_id = u('<ii', 0x08)
        self.flags, self.type = u('<IH', 0x18)
        self.type_name = ITEM_TYPES.get(self.type, 'type%d' % self.type)
        self.anim = data[0x22:0x24].decode('latin-1').strip('\0 ')
        self.proficiency = data[0x31]
        self.price, self.stack = u('<IH', 0x34)
        self.weight = u('<I', 0x4c)[0]
        self.enchantment = u('<I', 0x60)[0]
        eh_off, eh_n = u('<IH', 0x64)
        fb_off, eq_idx, eq_n = u('<IHH', 0x6a)
        self.abilities = []
        for o in (eh_off + i * 0x38 for i in range(eh_n)):
            self.abilities.append(dict(
                attack_type=data[o], range=u('<H', o + 0x0e)[0], speed=data[o + 0x12],
                thac0_bonus=u('<h', o + 0x14)[0], dice_sides=data[o + 0x16], dice_n=data[o + 0x18],
                damage_bonus=u('<h', o + 0x1a)[0], damage_type=u('<H', o + 0x1c)[0],
                launcher=data[o + 0x10]))
        self.equip_effects = [Effect.v1(data, fb_off + (eq_idx + k) * EFF_V1_SIZE) for k in range(eq_n)]

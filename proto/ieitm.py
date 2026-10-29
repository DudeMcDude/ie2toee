"""IE item (ITM) and store (STO) readers, plus ARE container items. Written from the IESDP file-format pages only.

  ITM V1    BG/BG2/IWD/HoW/TotL and every EE game (EE adds meanings to flag bits, not new fields)
  ITM V1.1  PST (0x72-byte header + 0x9a extra bytes) -- header fields read the same, extras ignored
  ITM V2.0  IWD2 (16 extra header bytes) -- detected; header read, abilities read with the shifted offsets
  STO V1.0  BG/IWD:EE, STO V9.0 classic IWD (longer header, same item records)
  ARE       container -> item list (0x14-byte item records, as in CRE)

Everything read here comes from the player's own install at conversion time; nothing is stored in this repo.
"""
import struct
from iecre import Effect, EFF_V1_SIZE, ITEM_TYPES, cstr

# header flags (0x18), IESDP "Header flags" (byte 0..2; EE meanings in brackets)
FLAG_NAMES = ['critical', 'two_handed', 'droppable', 'displayable', 'cursed', 'no_scribe', 'magical', 'left_handed',
              'silver', 'cold_iron', 'off_handed', 'conversable', 'fake_two_handed', 'forbid_off_hand',
              'usable_in_inventory', 'adamantine', 'undispellable', 'toggle_crit_aversion']
# usability (0x1e): a SET bit means "unusable by"
USABILITY_NAMES = ['chaotic', 'evil', 'good', 'ge_neutral', 'lawful', 'lc_neutral', 'bard', 'cleric', 'cleric_mage',
                   'cleric_thief', 'cleric_ranger', 'fighter', 'fighter_druid', 'fighter_mage', 'fighter_cleric',
                   'fighter_mage_cleric', 'fighter_mage_thief', 'fighter_thief', 'mage', 'mage_thief', 'paladin',
                   'ranger', 'thief', 'elf', 'dwarf', 'half_elf', 'halfling', 'human', 'gnome', 'monk', 'druid',
                   'half_orc']
ATTACK_TYPES = {0: 'none', 1: 'melee', 2: 'ranged', 3: 'magical', 4: 'launcher'}
LOCATIONS = {0: 'none', 1: 'weapon', 2: 'spell', 3: 'equipment', 4: 'innate'}
TARGETS = {0: 'invalid', 1: 'living', 2: 'inventory', 3: 'dead', 4: 'point', 5: 'caster', 6: 'crash', 7: 'caster_instant'}
LAUNCHERS = {0: None, 1: 'bow', 2: 'crossbow', 3: 'sling', 40: 'spear', 100: 'throwing_axe'}
DAMAGE_TYPES = {0: 'none', 1: 'piercing', 2: 'crushing', 3: 'slashing', 4: 'missile', 5: 'fist',
                6: 'piercing_crushing', 7: 'piercing_slashing', 8: 'crushing_slashing', 9: 'blunt_missile'}
DEPLETION = {0: 'remains', 1: 'vanishes', 2: 'replace', 3: 'recharges'}
# ability flags (0x26)
ABILITY_FLAG_NAMES = {0: 'add_strength', 1: 'breakable', 2: 'strength_damage', 3: 'strength_thac0',
                      9: 'break_sanctuary_invis', 10: 'hostile', 11: 'recharge', 16: 'keen_edge', 17: 'bypass_armor',
                      18: 'ignore_dex', 19: 'ex_damage'}
# opcodes that matter for item classification (IESDP effect list)
OP_LEARN_SPELL, OP_CAST_SPELL, OP_CAST_SPELL_POINT = 147, 146, 148
OP_STAT = {44: 'STR', 6: 'CHR', 10: 'CON', 15: 'DEX', 19: 'INT', 49: 'WIS', 97: 'STR_bonus'}


def bits(v, names):
    return [n for i, n in enumerate(names) if v & (1 << i)]


class Ability(object):
    def __init__(self, d, o, fb_off):
        u = lambda f, k: struct.unpack_from(f, d, o + k)
        self.attack_type = ATTACK_TYPES.get(d[o], d[o])
        self.id_required = d[o + 1]
        self.location = LOCATIONS.get(d[o + 2], d[o + 2])
        self.use_icon = cstr(d[o + 4:o + 12]).lower()
        self.target = TARGETS.get(d[o + 0x0c], d[o + 0x0c])
        self.target_count = d[o + 0x0d]
        self.range = u('<H', 0x0e)[0]
        self.launcher = LAUNCHERS.get(d[o + 0x10], d[o + 0x10])
        self.speed = d[o + 0x12]
        self.thac0_bonus = u('<h', 0x14)[0]
        self.dice_sides, self.school, self.dice_n, self.sectype = d[o + 0x16], d[o + 0x17], d[o + 0x18], d[o + 0x19]
        self.damage_bonus = u('<h', 0x1a)[0]
        self.damage_type = DAMAGE_TYPES.get(u('<H', 0x1c)[0], u('<H', 0x1c)[0])
        n_fx, i_fx = u('<HH', 0x1e)
        self.charges = u('<H', 0x22)[0]
        self.depletion = DEPLETION.get(u('<H', 0x24)[0], u('<H', 0x24)[0])
        f = u('<I', 0x26)[0]
        self.flags = [n for b, n in ABILITY_FLAG_NAMES.items() if f & (1 << b)]
        self.projectile = u('<H', 0x2a)[0]
        self.melee_anim = list(u('<3H', 0x2c))
        self.ammo_qualifiers = list(u('<3H', 0x32))   # is arrow / bolt / bullet
        self.effects = [Effect.v1(d, fb_off + (i_fx + k) * EFF_V1_SIZE) for k in range(n_fx)]

    def as_dict(self):
        out = {k: v for k, v in self.__dict__.items() if k != 'effects'}
        out['effects'] = [e.as_dict() for e in self.effects]
        return out


class Itm(object):
    def __init__(self, data, resref=''):
        self.resref = resref.lower()
        if data[:4] != b'ITM ':
            raise ValueError('%s: not an ITM' % resref)
        self.version = data[4:8].decode('latin-1').strip()
        s = 0x10 if self.version == 'V2.0' else 0     # IWD2: 16 extra bytes in the header before the ext headers
        u = lambda f, o: struct.unpack_from(f, data, o)
        self.name_unid, self.name_id = u('<ii', 0x08)
        self.replacement = cstr(data[0x10:0x18]).lower()
        self.flags_raw, self.type = u('<IH', 0x18)
        self.flags = bits(self.flags_raw, FLAG_NAMES)
        self.type_name = ITEM_TYPES.get(self.type, 'type%d' % self.type)
        self.unusable_raw = u('<I', 0x1e)[0]
        self.unusable_by = bits(self.unusable_raw, USABILITY_NAMES)
        self.anim = data[0x22:0x24].decode('latin-1').strip('\0 ')
        self.min_level, self.min_str = u('<HH', 0x24)
        self.min_str_bonus, self.min_int, self.min_dex, self.min_wis, self.min_con = \
            data[0x28], data[0x2a], data[0x2c], data[0x2e], data[0x30]
        self.kit_unusable = [data[0x29], data[0x2b], data[0x2d], data[0x2f]]
        self.proficiency = data[0x31]
        self.min_cha = u('<H', 0x32)[0]
        self.price, self.stack = u('<IH', 0x34)
        self.icon = cstr(data[0x3a:0x42]).lower()
        self.lore = u('<H', 0x42)[0]
        self.ground_icon = cstr(data[0x44:0x4c]).lower()
        self.weight = u('<I', 0x4c)[0]
        self.desc_unid, self.desc_id = u('<ii', 0x50)
        self.desc_icon = cstr(data[0x58:0x60]).lower()
        self.enchantment = u('<I', 0x60)[0]
        eh_off, eh_n = u('<IH', 0x64)
        fb_off, eq_idx, eq_n = u('<IHH', 0x6a)
        self.abilities = []
        for i in range(eh_n):
            o = eh_off + i * 0x38   # V2.0 abilities are V1-sized (only the header grew)
            if o + 0x38 > len(data):
                break
            self.abilities.append(Ability(data, o, fb_off))
        self.equip_effects = [Effect.v1(data, fb_off + (eq_idx + k) * EFF_V1_SIZE) for k in range(eq_n)
                              if fb_off + (eq_idx + k + 1) * EFF_V1_SIZE <= len(data)]

    # ---- classification helpers
    @property
    def magical(self):
        return 'magical' in self.flags or self.enchantment > 0

    def spell_links(self):
        """[(how, spell resref)]: learn (scrolls: opcode 147), cast (146/148: scrolls, wands, potions, charged items)."""
        out = []
        for a in self.abilities:
            for e in a.effects:
                if e.opcode == OP_LEARN_SPELL and e.resource:
                    out.append(('learn', e.resource.lower()))
                elif e.opcode in (OP_CAST_SPELL, OP_CAST_SPELL_POINT) and e.resource:
                    out.append(('cast', e.resource.lower()))
        return out

    def stat_effects(self):
        """Equip effects that change ability scores: [(stat, mode, value)] (param2 0 = add, 1 = set, 2 = percent)."""
        return [(OP_STAT[e.opcode], e.param2, e.param1) for e in self.equip_effects if e.opcode in OP_STAT]

    def as_dict(self):
        out = {k: v for k, v in self.__dict__.items() if k not in ('abilities', 'equip_effects')}
        out['abilities'] = [a.as_dict() for a in self.abilities]
        out['equip_effects'] = [e.as_dict() for e in self.equip_effects]
        return out


class Sto(object):
    TYPES = {0: 'store', 1: 'tavern', 2: 'inn', 3: 'temple', 4: 'container', 5: 'container'}

    def __init__(self, data, resref=''):
        self.resref = resref.lower()
        if data[:4] != b'STOR':
            raise ValueError('%s: not a STO' % resref)
        self.version = data[4:8].decode('latin-1')
        u = lambda f, o: struct.unpack_from(f, data, o)
        t, self.name, self.flags, self.sell_markup, self.buy_markup, self.depreciation = u('<IiIIII', 0x08)
        self.type = self.TYPES.get(t, t)
        self.steal_fail = u('<H', 0x20)[0]
        bo, bn, so, sn, self.lore, self.id_price = u('<IIIIII', 0x2c)
        self.buys = list(u('<%dI' % bn, bo)) if bn else []
        self.items = []
        for o in (so + i * 0x1c for i in range(sn)):
            self.items.append(dict(resref=cstr(data[o:o + 8]).lower(), charges=list(u('<3H', o + 0x0a)),
                                   flags=u('<I', o + 0x10)[0], stock=u('<I', o + 0x14)[0],
                                   infinite=u('<I', o + 0x18)[0]))
        co, cn = u('<II', 0x70)
        self.cures = [dict(spell=cstr(data[o:o + 8]).lower(), price=u('<I', o + 8)[0])
                      for o in (co + i * 12 for i in range(cn))]
        self.allow = dict(buy=bool(self.flags & 1), sell=bool(self.flags & 2), identify=bool(self.flags & 4),
                          steal=bool(self.flags & 8), cures=bool(self.flags & 32), drinks=bool(self.flags & 64))


def are_container_items(data):
    """ARE V1.0 / V9.1: [{name, x, y, type, lock, flags, trap, key, items: [{resref, charges, flags}]}] per container."""
    s = 0x10 if data[:8] == b'AREAV9.1' else 0
    u = lambda f, o: struct.unpack_from(f, data, o)
    con_off, con_n = u('<I', 0x70 + s)[0], u('<H', 0x74 + s)[0]
    it_n, it_off = u('<H', 0x76 + s)[0], u('<I', 0x78 + s)[0]
    items = [dict(resref=cstr(data[o:o + 8]).lower(), charges=list(u('<3H', o + 0x0a)), flags=u('<I', o + 0x10)[0])
             for o in (it_off + i * 0x14 for i in range(it_n))]
    out = []
    for i in range(con_n):
        o = con_off + i * 0xC0
        first, cnt = u('<II', o + 0x40)
        out.append(dict(name=cstr(data[o:o + 32]), x=u('<H', o + 0x20)[0], y=u('<H', o + 0x22)[0],
                        type=u('<H', o + 0x24)[0], lock=u('<H', o + 0x26)[0], flags=u('<I', o + 0x28)[0],
                        trapped=u('<H', o + 0x30)[0], key=cstr(data[o + 0x78:o + 0x80]).lower(),
                        items=items[first:first + cnt]))
    return out

"""IE spell (SPL V1), projectile (PRO V1.0) and effect (EFF V2) readers, written from the IESDP file-format pages only.

  SPL V1     header 0x72, extended headers 0x28 each (one per caster-level band), feature blocks 0x30 (EFF V1 layout)
  PRO V1.0   projectile type at 0x08; area-of-effect section at 0x200 (flags, trigger radius, explosion radius)
  EFF V2     stand-alone effect files (EE): 'EFF V2.0' + the 0x108-byte V2 effect body
  ITM V1     abilities with their feature blocks (the creature converter's iecre.Itm only reads equip effects)

Classic IWD (TotL) uses SPL V1 too, but has no PRO files (projectiles are hard-coded there) and its effect opcodes
above ~186 differ from the BG2/EE numbering (IESDP opcodes/iwd1totl.htm). Everything is read from the player's own
install at conversion time; nothing read here is stored in the repository.
"""
import struct
from iecre import Effect, EFF_V1_SIZE, cstr

SPELL_TYPES = {0: 'special', 1: 'wizard', 2: 'priest', 3: 'psionic', 4: 'innate', 5: 'bardsong'}
# SPL primary type (IWD: SCHOOL.2DA, BG2/EE: MSCHOOL.2DA) - school numbers are the same in both
SCHOOLS = {0: 'none', 1: 'abjuration', 2: 'conjuration', 3: 'divination', 4: 'enchantment', 5: 'illusion',
           6: 'evocation', 7: 'necromancy', 8: 'transmutation', 9: 'generalist'}
TARGETS = {0: 'invalid', 1: 'creature', 2: 'inventory', 3: 'dead', 4: 'point', 5: 'self', 6: 'crash', 7: 'self_instant'}
EFF_TARGETS = {0: 'none', 1: 'self', 2: 'preset', 3: 'party', 4: 'everyone', 5: 'everyone_but_party',
               6: 'caster_group', 7: 'target_group', 8: 'everyone_but_self', 9: 'original_caster'}
# effect timing modes (IESDP effect "Timing Mode"); duration is in seconds of game time (1 round = 6 s)
TIMING = {0: 'duration', 1: 'permanent', 2: 'while_equipped', 3: 'delayed_duration', 4: 'delayed_permanent',
          5: 'delayed_equipped', 6: 'duration_after_delay', 7: 'permanent_after_delay', 8: 'equipped_after_delay',
          9: 'permanent_after_death', 10: 'duration_ticks', 4096: 'absolute'}
SAVE_BITS = {0: 'spell', 1: 'breath', 2: 'death', 3: 'wands', 4: 'polymorph'}   # BG/IWD save-type bits 0..4

# Opcodes that reference another resource. Numbers per IESDP (bgee.htm = EE numbering, iwd1totl.htm = classic IWD).
SPELL_REF_OPS = {
    'ee':   {146: 'cast', 148: 'cast_point', 147: 'learn', 171: 'give_innate', 172: 'remove_innate',
             232: 'contingency', 234: 'contingency', 256: 'sequencer', 258: 'sequencer', 260: 'trigger',
             326: 'apply', 333: 'static_charge', 341: 'critical_hit', 344: 'enemy_hit'},
    'iwd1': {146: 'cast', 148: 'cast_point', 147: 'learn', 171: 'give_innate', 172: 'remove_innate'},
}
EFF_REF_OPS = {'ee': {177, 183, 248, 249, 272, 283}, 'iwd1': {177}}


def _bits(v, table):
    return [n for b, n in table.items() if v & (1 << b)]


class Spl(object):
    def __init__(self, data, resref=''):
        self.resref = resref.lower()
        if data[:4] != b'SPL ':
            raise ValueError('%s: not a SPL (%r)' % (resref, data[:4]))
        self.version = data[4:8].decode('latin-1').strip()
        u = lambda f, o: struct.unpack_from(f, data, o)
        self.name_strref, _ = u('<ii', 0x08)
        self.sound = cstr(data[0x10:0x18])
        self.flags, self.type_id = u('<IH', 0x18)
        self.type = SPELL_TYPES.get(self.type_id, 'type%d' % self.type_id)
        self.exclusion = u('<I', 0x1e)[0]
        self.casting_graphics = u('<H', 0x22)[0]
        self.school_id, self.sectype = data[0x25], data[0x27]
        self.school = SCHOOLS.get(self.school_id, 'school%d' % self.school_id)
        self.level = u('<I', 0x34)[0]
        self.icon = cstr(data[0x3a:0x42])
        self.desc_strref = u('<i', 0x50)[0]
        eh_off, eh_n = u('<IH', 0x64)
        fb_off, cast_idx, cast_n = u('<IHH', 0x6a)
        fx = lambda i, n: [Effect.v1(data, fb_off + (i + k) * EFF_V1_SIZE) for k in range(n)
                           if fb_off + (i + k + 1) * EFF_V1_SIZE <= len(data)]
        self.casting_effects = fx(cast_idx, cast_n)
        self.abilities = []
        for o in (eh_off + i * 0x28 for i in range(eh_n)):
            if o + 0x28 > len(data):
                break
            n_fx, i_fx = u('<HH', o + 0x1e)
            self.abilities.append(dict(
                form=data[o], location=u('<H', o + 2)[0], target=TARGETS.get(data[o + 0x0c], data[o + 0x0c]),
                target_count=data[o + 0x0d], range=u('<H', o + 0x0e)[0], level=u('<H', o + 0x10)[0],
                casting_time=u('<H', o + 0x12)[0], projectile=u('<H', o + 0x26)[0], effects=fx(i_fx, n_fx)))

    # ---- convenience
    @property
    def priest_class(self):
        """Priest spells: IESDP exclusion bits 30/31 mark cleric-only / druid-only (classic + EE)."""
        if self.type != 'priest':
            return None
        if self.exclusion & (1 << 30) and not self.exclusion & (1 << 31):
            return 'druid'       # bit 30 = unusable by cleric/paladin
        if self.exclusion & (1 << 31) and not self.exclusion & (1 << 30):
            return 'cleric'      # bit 31 = unusable by druid/ranger
        return 'both'

    def all_effects(self):
        for e in self.casting_effects:
            yield 'cast', e
        for i, a in enumerate(self.abilities):
            for e in a['effects']:
                yield i, e

    def summary(self):
        """Structure facts only (no text): used by the survey and the adjudication heuristics."""
        top = self.abilities[-1] if self.abilities else {}
        first = self.abilities[0] if self.abilities else {}
        ops = sorted({e.opcode for _, e in self.all_effects()})
        durs = sorted({e.duration for _, e in self.all_effects() if e.timing in (0, 3, 6) and e.duration})
        saves = sorted({n for _, e in self.all_effects() for n in _bits(e.save_type, SAVE_BITS)})
        dice = sorted({(e.dice_n, e.dice_s) for _, e in self.all_effects() if e.dice_n and e.dice_s})
        return dict(type=self.type, level=self.level, school=self.school, sectype=self.sectype,
                    priest_class=self.priest_class, n_abilities=len(self.abilities),
                    level_bands=[a['level'] for a in self.abilities], target=first.get('target'),
                    range=first.get('range'), casting_time=first.get('casting_time'),
                    projectile=first.get('projectile'), opcodes=ops, durations=durs, saves=saves, dice=dice,
                    top_dice=sorted({(e.dice_n, e.dice_s) for e in top.get('effects', []) if e.dice_n}))


class Pro(object):
    def __init__(self, data, resref=''):
        if data[:4] != b'PRO ':
            raise ValueError('%s: not a PRO' % resref)
        u = lambda f, o: struct.unpack_from(f, data, o)
        self.resref = resref.lower()
        self.type, self.speed = u('<HH', 0x08)
        self.aoe = None
        if self.type == 3 and len(data) >= 0x210:
            flags, trap, radius = u('<IHH', 0x200)
            self.aoe = dict(flags=flags, trigger_radius=trap, radius=radius,
                            radius_ft=round(abs(radius) / 17.0, 1),   # IESDP: diameter in feet ~ value / 8.5
                            cone=bool(flags & (1 << 11)))


class Eff(object):
    """Stand-alone EFF V2.0 file: one effect."""
    def __init__(self, data, resref=''):
        if data[:8] != b'EFF V2.0':
            raise ValueError('%s: not an EFF V2.0' % resref)
        self.resref = resref.lower()
        self.effect = Effect.v2(data, 8)


def itm_abilities(data):
    """ITM V1 abilities with their feature blocks: [{'attack_type', 'location', 'target', 'charges', 'effects'}].
    Equip effects are listed under ability index 'equip'."""
    u = lambda f, o: struct.unpack_from(f, data, o)
    eh_off, eh_n = u('<IH', 0x64)
    fb_off, eq_idx, eq_n = u('<IHH', 0x6a)
    fx = lambda i, n: [Effect.v1(data, fb_off + (i + k) * EFF_V1_SIZE) for k in range(n)
                       if fb_off + (i + k + 1) * EFF_V1_SIZE <= len(data)]
    out = [dict(index='equip', effects=fx(eq_idx, eq_n))]
    for j, o in enumerate(eh_off + i * 0x38 for i in range(eh_n)):
        if o + 0x38 > len(data):
            break
        n_fx, i_fx, charges = u('<HHH', o + 0x1e)
        out.append(dict(index=j, attack_type=data[o], location=data[o + 2], target=data[o + 0x0c],
                        charges=charges, effects=fx(i_fx, n_fx)))
    return out

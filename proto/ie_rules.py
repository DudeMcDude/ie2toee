"""AD&D 2nd edition (Infinity Engine) -> D&D 3.5 (Temple+) conversion rules.

Every rule cites where it comes from:
  CM p.N  = Wizards of the Coast, "D&D 3rd Edition Conversion Manual" (Skip Williams, 2000, free download), page N
  SRD     = the d20 System Reference Document 3.5 (creature type tables)
  ADJ-n   = our proposal; listed with alternatives in docs/creatures.md ("Adjudication list") for Shai and the co8 rules folks

Pure functions over plain numbers: no game data in here. `options` (dict) selects between the alternatives of each ADJ item.
"""

DEFAULT_OPTIONS = {
    'strength_table': 'cm',       # ADJ-1: 'cm' (CM p.3-4 table) | 'compressed' (18/01-50=19, 51-99=20, 00=21) | 'ignore'
    'level_ability_bumps': True,  # ADJ-2: CM p.4 "+1 to one ability per 4 levels" (applied to the class's key ability)
    'multiclass': 'cm',           # ADJ-3: CM p.3 highest + others/3 (min 1) | 'sum' (keep every level)
    'hp': 'max_ie_3e',            # ADJ-4: 'ie' | '3e' (Temple+ rolls) | 'max_ie_3e' (higher of IE HP and 3e average)
    'saves_from_ie': 'bonus_if_better',  # ADJ-5: 'off' | 'bonus_if_better' (CM p.12 15-save, only when it beats 3e by >=2)
    'attack_from_ie': 'bonus_if_better',  # ADJ-6: 'off' | 'bonus_if_better' (CM p.11 20-THAC0 vs 3e BAB, >=3 gap)
    'energy_resistance': 'banded',  # ADJ-7: IE % -> 3.5 energy resistance (see energy_resistance())
    'physical_resistance': 'dr',  # ADJ-8: IE slashing/crushing/piercing % -> DR x/<type>
    'magic_resistance': 'cm',     # ADJ-9: CM p.22 SR = 11 + MR/5; MR>=100 -> immunity to spells
    'morale': 'no_flee_if_unbreakable',  # ADJ-10
    'cr': 'proto_or_level',      # ADJ-11: CR from the ToEE template (+HD advancement) or class level; IE XP only reported
    'commoners': 'monster_hd',    # ADJ-12: 2e 0-level/1st-level "fighter" townsfolk -> 1 HD humanoid, no PC class
    'track_a_stats': 'srd',       # ADJ-13: 'srd' keep ToEE template abilities/AC | 'ie' use IE values | 'max'
    'plot_minimum_hp': 'invulnerable',  # ADJ-14: IE op 208 (minimum HP) on ambient/plot creatures -> 'invulnerable' | 'ignore'
}

# ----------------------------------------------------------------------------------- abilities
def strength_3e(score, pct, table='cm'):
    """CM p.3-4 'Exceptional Strength' table. IE stores 18/00 as pct=100."""
    if table == 'ignore' or score < 18 or (score == 18 and pct <= 0):
        return score if score <= 18 or table == 'ignore' else _str_over_18(score)
    if score > 18:
        return _str_over_18(score)
    if table == 'compressed':
        return 19 if pct <= 50 else (20 if pct < 100 else 21)
    if pct <= 50: return 19
    if pct <= 75: return 20
    if pct <= 90: return 21
    if pct <= 99: return 22
    return 23


def _str_over_18(score):
    # CM p.4: 19-20 -> 24, 21-22 -> 25, "22-23" -> 26 (overlap in the source; we read it as 23 -> 26), 24-25 -> 27
    return {19: 24, 20: 24, 21: 25, 22: 25, 23: 26, 24: 27, 25: 27}.get(score, score)


def mod(score):
    return (score - 10) // 2


# ----------------------------------------------------------------------------------- classes
# IE class names (CLASS.IDS, read from the player's install) are split on '_' into 2e base classes
CLASS_2E_TO_3E = {'FIGHTER': 'fighter', 'MAGE': 'wizard', 'CLERIC': 'cleric', 'THIEF': 'rogue', 'BARD': 'bard',
                  'PALADIN': 'paladin', 'DRUID': 'druid', 'RANGER': 'ranger', 'SORCERER': 'sorcerer', 'MONK': 'monk',
                  'BARBARIAN': 'barbarian', 'SHAMAN': 'druid'}
KEY_ABILITY = {'fighter': 0, 'barbarian': 0, 'paladin': 0, 'ranger': 1, 'rogue': 1, 'monk': 4, 'wizard': 3,
               'cleric': 4, 'druid': 4, 'sorcerer': 5, 'bard': 5}
HIT_DIE = {'fighter': 10, 'paladin': 10, 'barbarian': 12, 'ranger': 8, 'rogue': 6, 'bard': 6, 'monk': 8,
           'cleric': 8, 'druid': 8, 'wizard': 4, 'sorcerer': 4}
BAB_RATE = {'fighter': 1.0, 'paladin': 1.0, 'barbarian': 1.0, 'ranger': 1.0, 'rogue': .75, 'bard': .75, 'monk': .75,
            'cleric': .75, 'druid': .75, 'wizard': .5, 'sorcerer': .5}
GOOD_SAVES = {'fighter': 'F', 'paladin': 'F', 'barbarian': 'F', 'ranger': 'FR', 'rogue': 'R', 'bard': 'RW', 'monk': 'FRW',
              'cleric': 'FW', 'druid': 'FW', 'wizard': 'W', 'sorcerer': 'W'}


def split_class(ids_name):
    """'FIGHTER_MAGE_THIEF' -> ['fighter', 'wizard', 'rogue']; unknown/monster classes -> []"""
    if not ids_name:
        return []
    parts = ids_name.upper().split('_')
    out = [CLASS_2E_TO_3E[p] for p in parts if p in CLASS_2E_TO_3E]
    return out if len(out) == len(parts) else []


def class_levels(classes, ie_levels, rule='cm'):
    """CM p.3: total = highest + sum(max(1, other // 3)); we give the highest class its level and every other class its
    third (min 1), one of the splits CM step 4 allows. Single class: IE fills all three level bytes; use the first."""
    if not classes:
        return []
    lv = [max(1, int(x)) for x in ie_levels[:len(classes)]]
    if len(classes) == 1:
        return [(classes[0], lv[0])]
    if rule == 'sum':
        return list(zip(classes, lv))
    top = max(range(len(classes)), key=lambda i: (lv[i], -i))
    return [(c, lv[i] if i == top else max(1, lv[i] // 3)) for i, c in enumerate(classes)]


def bab_from_classes(levels):
    return sum(int(BAB_RATE[c] * n) for c, n in levels)


def base_saves(levels):
    """SRD class tables: good = 2 + lvl/2, poor = lvl/3 (summed per class, PH multiclass rule)."""
    out = [0, 0, 0]
    for c, n in levels:
        g = GOOD_SAVES[c]
        for k, s in enumerate('FRW'):
            out[k] += (2 + n // 2) if s in g else n // 3
    return out   # fortitude, reflex, will


# ----------------------------------------------------------------------------------- monsters (SRD 3.5 type table)
TYPE_TABLE = {   # hit die, BAB rate, good saves
    'aberration': (8, .75, 'W'), 'animal': (8, .75, 'FR'), 'construct': (10, .75, ''), 'dragon': (12, 1.0, 'FRW'),
    'elemental': (8, .75, ''), 'fey': (6, .5, 'RW'), 'giant': (8, .75, 'F'), 'humanoid': (8, .75, ''),
    'magical_beast': (10, 1.0, 'FR'), 'monstrous_humanoid': (8, 1.0, 'RW'), 'ooze': (10, .75, ''),
    'outsider': (8, 1.0, 'FRW'), 'plant': (8, .75, 'F'), 'undead': (12, .5, 'W'), 'vermin': (8, .75, 'F'),
    'shapechanger': (8, .75, 'FRW')}


def monster_bab(mtype, hd):
    return int(TYPE_TABLE.get(mtype, (8, .75, ''))[1] * hd)


def monster_saves(mtype, hd):
    g = TYPE_TABLE.get(mtype, (8, .75, ''))[2]
    return [(2 + hd // 2) if s in g else hd // 3 for s in 'FRW']


SIZE_AC = {'size_fine': 8, 'size_diminutive': 4, 'size_tiny': 2, 'size_small': 1, 'size_medium': 0, 'size_large': -1,
           'size_huge': -2, 'size_gargantuan': -4, 'size_colossal': -8}


# ----------------------------------------------------------------------------------- combat numbers
def ac_3e(ac_2e):
    """CM p.11 / p.21: 3e AC = 20 - 2e AC (descending -> ascending)."""
    return 20 - ac_2e


def natural_armor(ac_2e, dex, size='size_medium'):
    """CM p.21: natural armor = (20 - old AC) - 10 - Dex modifier - size modifier (never below 0)."""
    return max(0, ac_3e(ac_2e) - 10 - mod(dex) - SIZE_AC.get(size, 0))


def attack_from_thac0(thac0):
    """CM p.11: attack bonus ~ 20 - THAC0."""
    return 20 - thac0


def save_from_2e(save):
    """CM p.12: 3e save bonus ~ 15 - 2e save number (Fort ~ death/paralysation/poison, Ref & Will ~ spell)."""
    return 15 - save


def spell_resistance(mr_pct, rule='cm'):
    """CM p.22: SR = 11 + MR/5. MR 100% is total immunity in IE; we keep SR 31 and flag it."""
    if mr_pct <= 0:
        return 0
    return 11 + mr_pct // 5


def energy_resistance(pct, hd, rule='banded'):
    """ADJ-7 (no CM rule; CM p.22 says 'use a similar MM creature'): 100%+ -> immunity, 50-99 -> 10 (20 at 8+ HD),
    20-49 -> 5 (10 at 8+ HD), <20 ignored. Negative -> vulnerability (3.5: +50% damage). Returns ('immune'|'vuln'|N|0)."""
    if pct >= 100:
        return 'immune'
    if pct < 0:
        return 'vuln' if pct <= -50 else 0
    if pct >= 50:
        return 20 if hd >= 8 else 10
    if pct >= 20:
        return 10 if hd >= 8 else 5
    return 0


def physical_dr(res, weapon_immunity=None):
    """ADJ-8. res = {'slashing':%, 'crushing':%, 'piercing':%, 'missile':%}. If two weapon types are resisted >= 25% and the
    third is not, DR 5 (10 at >= 50%) / <the unresisted type>; IE weapon immunity (opcode 120: magical/silver/enchanted+N)
    -> DR 10/magic, 10/silver, 10/+N-as-magic (CM p.22 'hit only by silver or magical weapons')."""
    if weapon_immunity:
        return (10, weapon_immunity)
    typ = {'slashing': 'slashing', 'crushing': 'bludgeoning', 'piercing': 'piercing'}
    hi = [k for k in typ if res.get(k, 0) >= 25]
    lo = [k for k in typ if res.get(k, 0) <= 0]
    if len(hi) == 2 and len(lo) == 1:
        amt = 10 if min(res[k] for k in hi) >= 50 else 5
        return (amt, typ[lo[0]])
    if len(hi) == 3:
        return (5 if min(res[k] for k in hi) < 50 else 10, '-')
    return None


def apr_ie(v):
    """IE attacks-per-round byte: 0-5 = attacks, 6-10 = 1.5, 2.5, 3.5, 4.5, 5.5 (IESDP CRE notes)."""
    return v if v <= 5 else (v - 5) + 0.5


# ----------------------------------------------------------------------------------- CR / XP
XP_2E_BY_HD = [(0, 7), (1, 15), (2, 35), (3, 65), (4, 120), (5, 175), (6, 270), (7, 420), (8, 650), (9, 975),
               (10, 1400), (11, 2000), (12, 3000), (13, 4000), (14, 5000), (15, 6000)]  # 2e DMG Table 31 (ballpark)


def hd_from_2e_xp(xp):
    """Rough 2e XP -> 'effective HD' (used only as a sanity check / report). Above 15 HD: +1 per 1000 XP."""
    best = 0
    for hd, v in XP_2E_BY_HD:
        if xp >= v:
            best = hd
    if xp > 6000:
        best = 15 + (xp - 6000) // 1000
    return best


def cr_estimate(track, levels=None, template_cr=None, template_hd=None, ie_hd=None):
    """ADJ-11. Track B: CR = total class level (3.5 DMG: PC-class NPC CR = level). Track A: template CR, +1 per 3 HD
    advanced past the template (MM 'Improving Monsters' rule of thumb ~ +1 CR per 4 HD for most types; 3 for bosses)."""
    if track == 'class':
        return max(1, sum(n for _, n in (levels or [])))
    cr = template_cr or 1
    if ie_hd and template_hd and ie_hd > template_hd:
        cr += (ie_hd - template_hd) // 4
    return cr


# ----------------------------------------------------------------------------------- misc
def align_toee(ie_name):
    """ALIGNMEN.IDS names (LAWFUL_GOOD, NEUTRAL, CHAOTIC_EVIL, NONE, ...) -> ToEE alignment bits (lawful 1, chaotic 2,
    good 4, evil 8)."""
    n = (ie_name or '').upper()
    v = 0
    if 'LAWFUL' in n: v |= 1
    if 'CHAOTIC' in n: v |= 2
    if n.endswith('GOOD'): v |= 4
    if n.endswith('EVIL'): v |= 8
    return v


def hostility(ea_value):
    """EA.IDS: <= 30 (GOODCUTOFF) friendly/party side, >= 200 (EVILCUTOFF) hostile, else neutral."""
    if ea_value >= 200:
        return 'hostile'
    if ea_value <= 30 and ea_value != 0:
        return 'friendly'
    return 'neutral'


def thief_skill(pct):
    """CM p.9: skill bonus ~ pct // 5 - 5."""
    return max(0, pct // 5 - 5)


def speed_feet(ie_move):
    """CM p.20: speed = old movement x 2.5 ft, rounded up to 10 (IE movement is not stored in CRE V1/V9; via effects)."""
    import math
    return int(math.ceil(ie_move * 2.5 / 10.0) * 10)

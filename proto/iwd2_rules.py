"""IWD2 (3e) feats and skills -> Temple+ equivalents. Authored tables only (names from IWD2 FEATS.IDS / SKILLS.IDS,
engine constants of Temple+). IWD2's native 3e numbers (BAB, saves, class levels) are kept as they are elsewhere
(iecre.rules3e); this maps only the feat bits (CRE V2.2 0x1c0, 96 bits) and the 16 skill ranks (0x218).
Values: a Temple+ python constant name, a list of them, IMPLIED (granted by the ToEE class / proficiency system
already, nothing to add) or None (no ToEE equivalent: listed in the creature's notes)."""
IMPLIED = 'implied'
FEATS = {
    'AEGIS_OF_RIME': None, 'AMBIDEXTERITY': None,   # ToEE 3.5 folded Ambidexterity into Two-Weapon Fighting
    'AQUA_MORTIS': None, 'ARMOR_PROF': IMPLIED, 'ARMORED_ARCANA': None, 'ARTERIAL_STRIKE': None,
    'BLIND_FIGHT': 'feat_blind_fight', 'BULLHEADED': None, 'CLEAVE': 'feat_cleave', 'COMBAT_CASTING': 'feat_combat_casting',
    'CONUNDRUM': None, 'CRIPPLING_STRIKE': None, 'DASH': None, 'DEFLECT_ARROWS': 'feat_deflect_arrows',
    'DIRTY_FIGHTING': None, 'DISCIPLINE': None, 'DODGE': 'feat_dodge', 'ENVENOM_WEAPON': None,
    'EXOTIC_BASTARD': 'feat_exotic_weapon_proficiency_bastard_sword', 'EXPERTISE': 'feat_combat_expertise',
    'EXTRA_RAGE': None, 'EXTRA_SHAPESHIFTING': None, 'EXTRA_SMITING': None, 'EXTRA_TURNING': 'feat_extra_turning',
    'FIENDSLAYER': None, 'FORESTER': None, 'GREAT_FORTITUDE': 'feat_great_fortitude', 'HAMSTRING': None,
    'HERETICS_BANE': None, 'HEROIC_INSPIRATION': None,
    'IMPROVED_CRITICAL': None,   # ToEE's is per weapon: needs the creature's weapon (TODO: pick from the wielded item)
    'IMPROVED_EVASION': 'feat_improved_evasion', 'IMPROVED_INITIATIVE': 'feat_improved_initiative',
    'IMPROVED_TURNING': 'feat_improved_turning', 'IRON_WILL': 'feat_iron_will', 'LIGHTNING_REFLEXES': 'feat_lightning_reflexes',
    'LINGERING_SONG': None, 'LUCK_OF_HEROES': None,
    'MARTIAL_AXE': IMPLIED, 'MARTIAL_BOW': IMPLIED, 'MARTIAL_FLAIL': IMPLIED, 'MARTIAL_GREATSWORD': IMPLIED,
    'MARTIAL_HAMMER': IMPLIED, 'MARTIAL_LARGESWORD': IMPLIED, 'MARTIAL_POLEARM': IMPLIED,
    'MAXIMIZED_ATTACKS': None, 'MERCANTILE_BACKGROUND': None, 'POWER_ATTACK': 'feat_power_attack',
    'PRECISE_SHOT': ['feat_point_blank_shot', 'feat_precise_shot'], 'RAPID_SHOT': ['feat_point_blank_shot', 'feat_rapid_shot'],
    'RESIST_POISON': None, 'SCION_OF_STORMS': None, 'SHIELD_PROF': IMPLIED,
    'SIMPLE_CROSSBOW': IMPLIED, 'SIMPLE_MACE': IMPLIED, 'SIMPLE_MISSILE': IMPLIED, 'SIMPLE_QUARTERSTAFF': IMPLIED,
    'SIMPLE_SMALLBLADE': IMPLIED, 'SLIPPERY_MIND': None, 'SNAKE_BLOOD': None,
    'SPELL_FOCUS_ENCHANTMENT': 'feat_spell_focus_enchantment', 'SPELL_FOCUS_EVOCATION': 'feat_spell_focus_evocation',
    'SPELL_FOCUS_NECROMANCY': 'feat_spell_focus_necromancy', 'SPELL_FOCUS_TRANSMUTE': 'feat_spell_focus_transmutation',
    'SPELL_PENETRATION': 'feat_spell_penetration', 'SPIRIT_OF_FLAME': None, 'STRONG_BACK': None,
    'STUNNING_FIST': 'feat_stunning_fist', 'SUBVOCAL_CASTING': None, 'TOUGHNESS': 'feat_toughness',
    'TWO_WEAPON_FIGHTING': 'feat_two_weapon_fighting', 'WEAPON_FINESSE': None,   # per weapon in ToEE (TODO as Improved Critical)
    'WILDSHAPE_BOAR': None, 'WILDSHAPE_PANTHER': None, 'WILDSHAPE_SHAMBLER': None,
}
# SKILLS.IDS order = CRE V2.2 rank bytes 0x218..0x227
SKILLS = ['skill_alchemy', 'skill_animal_empathy', 'skill_bluff', 'skill_concentration', 'skill_diplomacy',
          'skill_disable_device', 'skill_hide', 'skill_intimidate', 'skill_knowledge_arcana', 'skill_move_silently',
          'skill_open_lock', 'skill_pick_pocket', 'skill_search', 'skill_spellcraft', 'skill_use_magic_device',
          'skill_wilderness_lore']


def map_3e(r3, feat_names):
    """r3: iecre rules3e; feat_names {bit: FEATS.IDS name} -> (feats [const], skills {const: ranks}, unmapped [name])"""
    m = r3['feats']; bits = m[0] | m[1] << 32 | m[2] << 64
    feats, unmapped = [], []
    for b in range(96):
        if not bits >> b & 1: continue
        n = feat_names.get(b, 'FEAT_%d' % b); t = FEATS.get(n)
        if t == IMPLIED: continue
        if t is None: unmapped.append(n); continue
        for c in (t if isinstance(t, list) else [t]):
            if c not in feats: feats.append(c)
    skills = dict((SKILLS[i], v) for i, v in enumerate(r3['skills'][:16]) if v)
    return feats, skills, unmapped

"""Commissioned (AI-generated, owner's own) NPC portraits -> ToEE portrait TGAs + portraits.mes entries.

Ids are 9900+ in steps of 10 (batches 2-5 run past 9999: 10000-10394, flips 10310+; batch 6 10400-10694, flips 10700-10974) (Co8 uses 9000-9754). Per id: +0 _b 130x150, +1 _m 42x37, +2 _s 53x47, +3 _s_grey, +4 _m_grey,
the vanilla NPC layout (vanilla leaves +0 empty for NPCs; we put the big portrait there like the PC entries do).
Sources: art/portraits/<key>/ie_<key>_{big,m,s}.png (see /workspace/portrait-commission specs).
"""
import os, re, sys
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(os.path.dirname(HERE), 'art', 'portraits')
MASTERS = os.environ.get('IE_PORTRAIT_MASTERS', '/workspace/portrait-art/masters')   # ie_<key>/ie_<key>_master.png
# key -> (portraits.mes base id, display name used in file names)
ART_IDS = {
    'hrothgar': (9900, 'Hrothgar'), 'everard': (9910, 'Everard'), 'arundel': (9920, 'Arundel'),
    'poquelin': (9930, 'Poquelin'), 'belhifet': (9940, 'Belhifet'), 'yxunomei': (9950, 'Yxunomei'),
    'kresselack': (9960, 'Kresselack'), 'conlan': (9970, 'Conlan'),
    # batch 2: IWD2
    'ulbrec': (9980, 'Ulbrec'), 'shawford': (9990, 'Shawford'), 'hedron': (10000, 'Hedron'), 'oswald': (10010, 'Oswald'),
    'nathaniel': (10020, 'Nathaniel'), 'isair': (10030, 'Isair'), 'madae': (10040, 'Madae'), 'ennelia': (10050, 'Ennelia'),
    # batch 3: IWD2 secondary NPCs
    'elytharra': (10060, 'Elytharra'), 'deirdre': (10070, 'Deirdre'), 'koluhm': (10080, 'Koluhm'), 'phaen': (10090, 'Phaen'),
    'reig': (10100, 'Reig'), 'guthewulf': (10110, 'Guthewulf'), 'iselore': (10120, 'Iselore'), 'kickshaw': (10130, 'Kickshaw'),
    # batch 4: children, a squirrel, townsfolk
    'damien': (10140, 'Damien'), 'eboy1': (10150, 'Boy1'), 'eboy2': (10160, 'Boy2'), 'egirl1': (10170, 'Girl1'),
    'egirl2': (10180, 'Girl2'), 'squirrel': (10190, 'Squirrel'), 'fisherwoman': (10200, 'Fisherwoman'),
    'townsman_old': (10210, 'OldTownsman'),
    'merchant_stout': (10220, 'StoutMerchant'),   # first Hedron art (replaced by the revision); generic, unmapped for now
    # batch 5: monsters; *_varB = the upgraded variant (elite/chief/high-level spawns)
    'yeti': (10230, 'Yeti'), 'yeti_varB': (10240, 'YetiB'), 'verbeeg': (10250, 'Verbeeg'),
    'frost_giant': (10260, 'FrostGiant'), 'frost_giant_varB': (10270, 'FrostGiantB'), 'winter_wolf': (10280, 'WinterWolf'),
    'boring_beetle': (10290, 'BoringBeetle'), 'boring_beetle_varB': (10300, 'BoringBeetleB'),
    # batch 6: monsters; *_elite = upgraded variant; matriarch / abominable snowman are bosses (no flip)
    'hook_horror': (10400, 'HookHorror'),
    'hook_horror_elite': (10410, 'HookHorrorB'),
    'hook_horror_matriarch': (10420, 'HookHorrorMatriarch'),
    'snow_troll': (10430, 'SnowTroll'),
    'snow_troll_elite': (10440, 'SnowTrollB'),
    'ice_troll': (10450, 'IceTroll'),
    'ice_troll_elite': (10460, 'IceTrollB'),
    'yuanti': (10470, 'Yuanti'),
    'yuanti_elite': (10480, 'YuantiB'),
    'yuanti_abomination': (10490, 'YuantiAbomination'),
    'lizardman': (10500, 'Lizardman'),
    'lizardman_elite': (10510, 'LizardmanB'),
    'dire_wolf': (10520, 'DireWolf'),
    'dire_wolf_elite': (10530, 'DireWolfB'),
    'malarite': (10540, 'Malarite'),
    'malarite_elite': (10550, 'MalariteB'),
    'umber_hulk': (10560, 'UmberHulk'),
    'bombardier_beetle': (10570, 'BombardierBeetle'),
    'rhino_beetle': (10580, 'RhinoBeetle'),
    'wight': (10590, 'Wight'),
    'wight_elite': (10600, 'WightB'),
    'salamander': (10610, 'Salamander'),
    'salamander_frost': (10620, 'FrostSalamander'),
    'skeleton_elite': (10630, 'ArmoredSkeleton'),
    'abominable_snowman': (10640, 'AbominableSnowman'),
    'winter_wolf_elite': (10650, 'WinterWolfB'),
    'orc_shaman': (10660, 'OrcShaman'),
    'orc_elite': (10670, 'OrcElite'),
    'goblin_elite': (10680, 'GoblinElite'),
    'wyvern': (10690, 'Wyvern'),
    # batch 8 part A: IWD1 Easthaven NPCs, extras, townsfolk pools (flips 12200+)
    'pomab': (11250, 'Pomab'),
    'accalia': (11260, 'Accalia'),
    'erevain': (11280, 'Erevain'),
    'elisia': (11290, 'Elisia'),
    'jhonen': (11300, 'Jhonen'),
    'gaspar': (11310, 'Gaspar'),
    'grisella': (11320, 'Grisella'),
    'apsel': (11340, 'Apsel'),
    'oldjed': (11350, 'OldJed'),
    'churin': (11360, 'Churin'),
    'pomab_tower': (11370, 'PomabTower'),
    'cyclops': (11380, 'Cyclops'),
    'cryshal_sentry': (11390, 'CryshalSentry'),
    'eh_expedition_sellsword': (11400, 'EHSellsword'),
    'eh_survivor_m': (11410, 'EHSurvivorM'),
    'eh_survivor_f': (11420, 'EHSurvivorF'),
    'eh_cradle_regular': (11430, 'CradleRegular'),
    'eh_tempus_acolyte': (11440, 'TempusAcolyte'),
    'pool_fisher_young': (11460, 'FisherYoung'),
    'pool_fisher_old': (11470, 'FisherOld'),
    'pool_fishwife': (11480, 'Fishwife'),
    'pool_dockworker': (11490, 'Dockworker'),
    'pool_dockworker_f': (11510, 'DockhandF'),
    'pool_tempus_priest': (11520, 'TempusPriest'),
    'pool_tempus_priestess': (11530, 'TempusPriestess'),
    'hildreth': (11270, 'Hildreth'),
    'eh_mercenary_veteran': (12800, 'MercenaryVeteran'),   # generic sellsword (2nd sellsword variant), for later pools
    # batch 8 rest (Gemini game-ready 130x150 only, no hi-res master)
    'boss_black_ice_knight': (12130, 'BlackIceKnight'),
    'boss_goblin_marshal': (12030, 'GoblinMarshal'),
    'boss_greater_ice_troll': (12060, 'GreaterIceTroll'),
    'boss_greater_mummy': (12100, 'GreaterMummy'),
    'boss_imbued_wight': (12170, 'ImbuedWight'),
    'boss_joril_bodyguard': (12150, 'JorilBodyguard'),
    'boss_krilag': (12040, 'Krilag'),
    'boss_lizard_king': (12070, 'LizardKing'),
    'boss_myrkul_sending': (12120, 'MyrkulSending'),
    'boss_shadowed_elf_officer': (12160, 'ShadowedElfOfficer'),
    'boss_spectral_knight': (12110, 'SpectralKnight'),
    'boss_talonite_priestess': (12090, 'TalonitePriestess'),
    'boss_umber_hulk_elder': (12180, 'UmberHulkElder'),
    'boss_white_wyrm': (12140, 'WhiteWyrm'),
    'boss_yeti_chieftain': (12050, 'YetiChieftain'),
    'boss_yuanti_elite': (12080, 'YuantiElite'),
    'eh_scrimshaw_apprentice': (11450, 'EhScrimshawApprentice'),
    'mon_beetle_cellar': (11750, 'BeetleCellar'),
    'mon_bombardier_beetle': (11760, 'BombardierBeetle'),
    'mon_cornugon': (12020, 'Cornugon'),
    'mon_frost_giant': (11900, 'FrostGiant'),
    'mon_frost_salamander': (11860, 'FrostSalamander'),
    'mon_ghoul': (11790, 'Ghoul'),
    'mon_goblin_archer_vale': (11700, 'GoblinArcherVale'),
    'mon_goblin_snow': (11690, 'GoblinSnow'),
    'mon_harpy': (11980, 'Harpy'),
    'mon_hook_horror': (11930, 'HookHorror'),
    'mon_ice_troll': (11880, 'IceTroll'),
    'mon_iron_golem': (12010, 'IronGolem'),
    'mon_lizardman': (11830, 'Lizardman'),
    'mon_minotaur': (11990, 'Minotaur'),
    'mon_mummy': (11820, 'Mummy'),
    'mon_ogre': (11960, 'Ogre'),
    'mon_orc': (11710, 'Orc'),
    'mon_orc_shadowed': (11720, 'OrcShadowed'),
    'mon_orog': (11950, 'Orog'),
    'mon_sahuagin': (12000, 'Sahuagin'),
    'mon_salamander': (11850, 'Salamander'),
    'mon_shadow': (11810, 'Shadow'),
    'mon_skeleton_vale': (11770, 'SkeletonVale'),
    'mon_spider': (11940, 'Spider'),
    'mon_troll': (11870, 'Troll'),
    'mon_umber_hulk': (11920, 'UmberHulk'),
    'mon_verbeeg': (11890, 'Verbeeg'),
    'mon_wight': (11800, 'Wight'),
    'mon_winter_wolf_snow': (11740, 'WinterWolfSnow'),
    'mon_wolf_snow': (11730, 'WolfSnow'),
    'mon_wyvern': (11970, 'Wyvern'),
    'mon_yeti': (11910, 'Yeti'),
    'mon_yuanti': (11840, 'Yuanti'),
    'mon_zombie': (11780, 'Zombie'),
    'pool_beggar': (11660, 'Beggar'),
    'pool_captive': (11670, 'Captive'),
    'pool_hunter': (11650, 'Hunter'),
    'pool_innkeeper_f': (11580, 'InnkeeperF'),
    'pool_kul_child': (11620, 'KulChild'),
    'pool_kul_elder_f': (11590, 'KulElderF'),
    'pool_kul_villager_f': (11610, 'KulVillagerF'),
    'pool_kul_villager_m': (11600, 'KulVillagerM'),
    'pool_merchant_m': (11560, 'MerchantM'),
    'pool_militia_m': (11540, 'MilitiaM'),
    'pool_reghed_warrior_f': (11640, 'ReghedWarriorF'),
    'pool_reghed_warrior_m': (11630, 'ReghedWarriorM'),
    'pool_sage': (11680, 'Sage'),
    'quimby': (11330, 'Quimby'),
}
# Generic monsters also get a left/right mirrored copy (own id) for per-instance variety. Named NPCs don't.
FLIPS = {
    'yeti': 10310, 'yeti_varB': 10320, 'verbeeg': 10330, 'frost_giant': 10340, 'frost_giant_varB': 10350,
    'winter_wolf': 10360, 'boring_beetle': 10370, 'boring_beetle_varB': 10380, 'squirrel': 10390,
    'hook_horror': 10700,
    'hook_horror_elite': 10710,
    'snow_troll': 10720,
    'snow_troll_elite': 10730,
    'ice_troll': 10740,
    'ice_troll_elite': 10750,
    'yuanti': 10760,
    'yuanti_elite': 10770,
    'yuanti_abomination': 10780,
    'lizardman': 10790,
    'lizardman_elite': 10800,
    'dire_wolf': 10810,
    'dire_wolf_elite': 10820,
    'malarite': 10830,
    'malarite_elite': 10840,
    'umber_hulk': 10850,
    'bombardier_beetle': 10860,
    'rhino_beetle': 10870,
    'wight': 10880,
    'wight_elite': 10890,
    'salamander': 10900,
    'salamander_frost': 10910,
    'skeleton_elite': 10920,
    'winter_wolf_elite': 10930,
    'orc_shaman': 10940,
    'orc_elite': 10950,
    'goblin_elite': 10960,
    'wyvern': 10970,
    'pool_fisher_young': 12200,
    'pool_fisher_old': 12210,
    'pool_fishwife': 12220,
    'pool_dockworker': 12230,
    'pool_dockworker_f': 12240,
    'pool_tempus_priest': 12250,
    'pool_tempus_priestess': 12260,
    'eh_mercenary_veteran': 12810,
    'mon_beetle_cellar': 12480,
    'mon_bombardier_beetle': 12490,
    'mon_cornugon': 12750,
    'mon_frost_giant': 12630,
    'mon_frost_salamander': 12590,
    'mon_ghoul': 12520,
    'mon_goblin_archer_vale': 12430,
    'mon_goblin_snow': 12420,
    'mon_harpy': 12710,
    'mon_hook_horror': 12660,
    'mon_ice_troll': 12610,
    'mon_iron_golem': 12740,
    'mon_lizardman': 12560,
    'mon_minotaur': 12720,
    'mon_mummy': 12550,
    'mon_ogre': 12690,
    'mon_orc': 12440,
    'mon_orc_shadowed': 12450,
    'mon_orog': 12680,
    'mon_sahuagin': 12730,
    'mon_salamander': 12580,
    'mon_shadow': 12540,
    'mon_skeleton_vale': 12500,
    'mon_spider': 12670,
    'mon_troll': 12600,
    'mon_umber_hulk': 12650,
    'mon_verbeeg': 12620,
    'mon_wight': 12530,
    'mon_winter_wolf_snow': 12470,
    'mon_wolf_snow': 12460,
    'mon_wyvern': 12700,
    'mon_yeti': 12640,
    'mon_yuanti': 12570,
    'mon_zombie': 12510,
    'pool_beggar': 12390,
    'pool_captive': 12400,
    'pool_hunter': 12380,
    'pool_innkeeper_f': 12310,
    'pool_kul_child': 12350,
    'pool_kul_elder_f': 12320,
    'pool_kul_villager_f': 12340,
    'pool_kul_villager_m': 12330,
    'pool_merchant_m': 12290,
    'pool_militia_m': 12270,
    'pool_reghed_warrior_f': 12370,
    'pool_reghed_warrior_m': 12360,
    'pool_sage': 12410,
}
# Face boxes on the 1200x1384 master, set by eye: (centre x, top of head/hair/crown, bottom of chin/beard).
# _m/_s are recropped from these (whole head + margin under the chin, like vanilla NPC_6001_m_Terjon);
# the commissioned _m/_s PNGs are cropped too tight. A key without a box keeps its source _m/_s.
FACE = {
    'hrothgar': (590, 120, 800), 'everard': (630, 120, 820), 'arundel': (530, 90, 770), 'poquelin': (620, 80, 790),
    'belhifet': (420, 170, 860), 'yxunomei': (580, 110, 840), 'kresselack': (620, 50, 880), 'conlan': (650, 170, 850),
    'ulbrec': (520, 150, 730), 'shawford': (560, 180, 830), 'hedron': (580, 95, 800), 'oswald': (620, 120, 800),
    'nathaniel': (500, 200, 880), 'isair': (560, 150, 850), 'madae': (600, 120, 870), 'ennelia': (600, 220, 880),
    'elytharra': (590, 90, 700), 'deirdre': (560, 90, 700), 'koluhm': (650, 150, 870), 'phaen': (600, 100, 810),
    'reig': (565, 120, 820), 'guthewulf': (600, 115, 1000), 'iselore': (625, 120, 900), 'kickshaw': (550, 160, 830),
    'damien': (585, 140, 870), 'eboy1': (605, 170, 940), 'eboy2': (625, 140, 870), 'egirl1': (645, 115, 700),
    'egirl2': (635, 115, 880), 'squirrel': (625, 165, 960), 'fisherwoman': (675, 95, 730), 'townsman_old': (620, 165, 940),
    'merchant_stout': (580, 130, 810),
    'yeti': (600, 165, 960), 'yeti_varB': (645, 130, 1000), 'verbeeg': (610, 115, 915), 'frost_giant': (600, 200, 1050),
    'frost_giant_varB': (620, 150, 1000), 'winter_wolf': (605, 210, 1010), 'boring_beetle': (610, 250, 1050),
    'boring_beetle_varB': (500, 250, 1050),
    'hook_horror': (500, 150, 850),
    'hook_horror_elite': (520, 180, 900),
    'hook_horror_matriarch': (580, 150, 900),
    'snow_troll': (580, 170, 850),
    'snow_troll_elite': (540, 200, 880),
    'ice_troll': (780, 250, 950),
    'ice_troll_elite': (700, 200, 880),
    'yuanti': (560, 180, 750),
    'yuanti_elite': (600, 80, 820),
    'yuanti_abomination': (600, 170, 780),
    'lizardman': (690, 250, 850),
    'lizardman_elite': (620, 150, 900),
    'dire_wolf': (600, 180, 1020),
    'dire_wolf_elite': (720, 180, 1000),
    'malarite': (600, 120, 860),
    'malarite_elite': (560, 80, 900),
    'umber_hulk': (600, 180, 1000),
    'bombardier_beetle': (600, 180, 1100),
    'rhino_beetle': (600, 150, 1100),
    'wight': (600, 130, 860),
    'wight_elite': (600, 70, 850),
    'salamander': (600, 100, 800),
    'salamander_frost': (720, 120, 800),
    'skeleton_elite': (600, 70, 880),
    'abominable_snowman': (620, 100, 1000),
    'winter_wolf_elite': (640, 120, 950),
    'orc_shaman': (570, 130, 830),
    'orc_elite': (610, 130, 830),
    'goblin_elite': (600, 130, 880),
    'wyvern': (520, 250, 750),
    'pomab': (550, 110, 840),
    'accalia': (585, 110, 770),
    'erevain': (600, 75, 730),
    'elisia': (550, 75, 770),
    'jhonen': (550, 110, 770),
    'gaspar': (620, 130, 800),
    'grisella': (585, 180, 800),
    'apsel': (585, 145, 770),
    'oldjed': (585, 110, 760),
    'churin': (585, 145, 770),
    'pomab_tower': (585, 110, 770),
    'cyclops': (585, 110, 800),
    'cryshal_sentry': (585, 110, 730),
    'eh_expedition_sellsword': (555, 90, 790),
    'eh_survivor_m': (585, 120, 730),
    'eh_survivor_f': (585, 120, 730),
    'eh_cradle_regular': (600, 120, 730),
    'eh_tempus_acolyte': (600, 90, 700),
    'pool_fisher_young': (615, 120, 700),
    'pool_fisher_old': (590, 120, 760),
    'pool_fishwife': (585, 120, 670),
    'pool_dockworker': (615, 90, 670),
    'pool_dockworker_f': (585, 120, 700),
    'pool_tempus_priest': (585, 90, 760),
    'pool_tempus_priestess': (585, 90, 690),
    'hildreth': (630, 100, 900),   # chin box includes the braided beard
    'eh_mercenary_veteran': (600, 90, 760),
}
TOP_PAD, CHIN_PAD = 0.06, 0.14   # fraction of head height above the top / below the chin
SIZES = {'b': (130, 150), 'm': (42, 37), 's': (53, 47)}


def face_crop(master, box, size):
    """Crop master to size's aspect around box = (cx, top, chin), whole head in frame, then downscale."""
    cx, top, chin = box; h = chin - top
    y0 = top - TOP_PAD * h; ch = h * (1 + TOP_PAD + CHIN_PAD); cw = ch * size[0] / size[1]
    x0 = min(max(cx - cw / 2, 0), master.width - cw); y0 = min(max(y0, 0), master.height - ch)
    return master.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize(size, Image.LANCZOS)


def recrop(key):
    """Rewrite art/portraits/<key>/ie_<key>_{m,s}.png from the master (masters live outside the repo: MASTERS dir)."""
    src = os.path.join(MASTERS, 'ie_%s' % key, 'ie_%s_master.png' % key)
    m = Image.open(src).convert('RGB')
    for k in ('m', 's'):
        face_crop(m, FACE[key], SIZES[k]).save(os.path.join(ART, key, 'ie_%s_%s.png' % (key, k)))


def grey(im):
    g = im.convert('L').point(lambda v: int(0.65 * v + 33))   # matches vanilla *_grey.tga levels
    out = Image.merge('RGBA', (g, g, g, im.getchannel('A')))
    return out


def files_for(key):
    base, name = ART_IDS[key]
    return {base: 'NPC_%d_b_%s.tga' % (base, name), base + 1: 'NPC_%d_m_%s.tga' % (base + 1, name),
            base + 2: 'NPC_%d_s_%s.tga' % (base + 2, name), base + 3: 'NPC_%d_s_%s_grey.tga' % (base + 3, name),
            base + 4: 'NPC_%d_m_%s_grey.tga' % (base + 4, name)}


def build(out_dir, vanilla_mes=None):
    """Write the TGAs and a portraits.mes (vanilla entries + ours) into out_dir (= data/art/interface/portraits)."""
    os.makedirs(out_dir, exist_ok=True)
    mes = dict(vanilla_mes or {})
    for key, (base, name) in ART_IDS.items():
        src = os.path.join(ART, key, 'ie_%s_%s.png')
        if not os.path.isfile(src % (key, 'big')):
            continue
        ims = {k: Image.open(src % (key, 'big' if k == 'b' else k)).convert('RGBA') for k in SIZES}
        for k, sz in SIZES.items():
            if ims[k].size != sz:
                ims[k] = ims[k].resize(sz, Image.LANCZOS)
        fn = files_for(key)
        imgs = {base: ims['b'], base + 1: ims['m'], base + 2: ims['s'], base + 3: grey(ims['s']), base + 4: grey(ims['m'])}
        for i, f in fn.items():
            if i in mes and mes[i] and mes[i] != f:
                raise SystemExit('portrait id clash %d: %s vs %s' % (i, mes[i], f))
            imgs[i].save(os.path.join(out_dir, f))
            mes[i] = f
        if key in FLIPS:   # mirrored copy, same +0..+4 layout
            fb = FLIPS[key]
            for j, f in enumerate(files_for(key).values()):
                f = f.replace('NPC_%d_' % (base + j), 'NPC_%d_' % (fb + j)).replace('.tga', '_flip.tga')
                if fb + j in mes and mes[fb + j] and mes[fb + j] != f:
                    raise SystemExit('portrait id clash %d: %s vs %s' % (fb + j, mes[fb + j], f))
                imgs[base + j].transpose(Image.FLIP_LEFT_RIGHT).save(os.path.join(out_dir, f))
                mes[fb + j] = f
    with open(os.path.join(out_dir, 'portraits.mes'), 'w', encoding='latin-1') as f:
        f.write(''.join('{%d} {%s}\n' % kv for kv in sorted(mes.items())))
    return mes


def vanilla(toee):
    import toeedata
    return toeedata.ToEEData(toee).mes('art/interface/portraits/portraits.mes')


if __name__ == '__main__':   # ie_portraits.py <out>/data/art/interface/portraits [toee root] | ie_portraits.py recrop [key...]
    if sys.argv[1] == 'recrop':
        for k in sys.argv[2:] or sorted(FACE):
            recrop(k)
        sys.exit()
    build(sys.argv[1], vanilla(sys.argv[2]) if len(sys.argv) > 2 else None)

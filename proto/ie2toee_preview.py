"""Build a Temple+ preview from Easthaven through the Vale of Shadows using the
player's Icewind Dale (classic or Enhanced Edition) installation.

  python ie2toee_preview.py --iwd "C:\\Games\\Icewind Dale" --toee "C:\\GOG Games\\ToEE" [--out iwd_preview_out]
                            [--install]

Pipeline (each step is one of the converter scripts in this folder, run in order):
  map (ie2toee.py) -> spells (ie_spells.py) -> items (ie_items.py) -> creatures (ie_creatures.py)
  -> dialogue (ie_dialogue.py) -> dialog window skin (ie_dialog_skin.py) -> bake into map files (ie_bake.py)
  -> travel exits (ie_exits.py) -> exit icons (ie_exiticons.py) -> path node placement (ie_pathnodes.py)
  [-> with --install --engine-pathnodes: Temple+ recalculates the node links with its own pathfinder and writes
      pathnodenew.pnd/pathnodedist.pnd + clearance.bin for every map (pathnode_bake.sh, the standard for new maps)]
Per-map hand overrides in overrides/iwd/<AREA>/ (overrides/README.md): Temple+ DM tile edits are applied by the map
step; hand-culled pathnodenew.pnd/pathnodedist.pnd/clearance.bin are copied in after the path node step (and after the
engine bake), so they win.
The result is <out>/install: copy its contents into the ToEE folder (or pass --install to do that).
Nothing of the IE game is shipped with the converter: everything is read from the install you point it at.
"""
import argparse, glob, json, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import toeedata
import ie_overrides
import ie_install
from ie_map_alerts import apply_map_alert_distances
from ie_build import preview_build
from ie_movies import movie_tool_check, report_prologue_media
OVERRIDES = os.path.join(HERE, 'overrides', 'iwd')   # per-map hand overrides (ie_overrides.py, overrides/README.md)

AREA, MAP_ID, GROUND_ID, START = 'AR1000', 5012, 900, (482, 424)
# Map ids (the IWD module replaces vanilla's maps, so their ids are reused) must stay <= 5198: temple.dll's town map UI
# keeps 200 per-map slots (map id - 4999) and, the first time it opens, fills one per id up to the highest MapList id,
# so ids >= ~5200 overrun them and crash it (the old 5900.. ids did); its place list reads mes/map_names.mes by LINE
# index (map id - 5000), so that file is written gap-free from 5000 (map_names()). 5012..5030: vanilla's area 1
# (Hommlet = the logbook's Easthaven, ie_dialogue LOGBOOK_AREAS) and clear of the ids the engine special-cases
# (ENGINE_MAP_IDS). Vanilla data keyed by map id that still loads from modules/IWD.dat (= ToEE.dat) is overridden:
# rules/MapLimits.mes (scroll limits; our ids dropped) and rules/daynight.nxd (vanilla NPC day/night moves; emptied).
ENGINE_MAP_IDS = ({5000, 5001, 5067, 5107, 5117, 5118, 5119, 5135, 5189, 5199} | set(range(5070, 5079)) |
                  set(range(5096, 5105)) | {5005, 5011, 5050, 5066, 5078, 5080})
# 5000 no terrain/scroll limits; 5001 Hommlet (worldmap, editor start); 5067 ray spell scripts; 5070-5078 random
# encounters; 5096-5104 vignettes (no town map); 5107 quickstart; 5117/5118 tutorial; 5119 arena; 5135 Temple+ debug
# limit; 5189/5199 Co8 day/night fix; 5005 5011 5050 5066 5078 5080 vanilla town map flags
MODULE = 'IWD'          # Temple+ module: modules\IWD.dat (link to your ToEE.dat) + modules\IWD (maps, art, rules, mes) +
                        # modules\IWD_core (dlg, scr, quest texts); chosen in TemplePlusConfig (defaultModule=IWD)
QUEST_BASE = 1          # IE journal entries -> ToEE quests 1.. (vanilla quests are not kept in the IWD module)
SCRIPT_BASE = 1100      # town actors 1100.., interior n: 1120+10n.. (n <= 14: <= 1269); side rooms n >= 15: 1300+10(n-15)..
GENERIC_BASE = 1280    # interior n's baked-object script (the town's is 1099)
# Easthaven's 14 building interiors + 2 side rooms (AR1015 off AR1006, AR1016 off AR1007): map ids MAP_ID+1..+16,
# ground ids 901..916 (map, doors, baked actors + containers)
INTERIORS = ['AR10%02d' % i for i in range(1, 17)]
# the Orc Cave chain off AR1000's south-east road exit (To1200): AR1200 hill road, AR1201 Orc Cave (map ids MAP_ID+17/+18,
# ground ids 917/918); converted like the interiors (map, exits, actors, containers)
INTERIORS += ['AR1200', 'AR1201']
# Keep the published pass id and the older prologue ids stable for existing saves.
PASS_ROOMS = ['AR200%d' % n for n in range(1, 7)]
KULDAHAR = ['AR21%02d' % n for n in range(17)]
VALE = ['AR3000', 'AR3001', 'AR3101', 'AR3201', 'AR3301', 'AR3401', 'AR3501', 'AR3502', 'AR3503']
FORGOTTEN_TEMPLE = ['AR3600', 'AR3601', 'AR3602', 'AR3603']
CHAPTER_DUNGEONS = VALE + FORGOTTEN_TEMPLE + ['AR4000']  # Dragon's Eye exterior, Chapter 2 arrival
NEW_AREAS = PASS_ROOMS + KULDAHAR + CHAPTER_DUNGEONS
INTERIORS += ['AR2000'] + NEW_AREAS
# 5052..5065, 5068..5069 and 5079 are usable. Leave the engine's special maps alone.
AREA_IDS = {'AR2000': 5051}
chapter_map_ids = [n for n in range(5052, 5199) if n not in ENGINE_MAP_IDS]
AREA_IDS.update(zip(NEW_AREAS, chapter_map_ids))
# the converted areas whose ARE header script runs (ie_cutscene area loop). AR1006 (the new-game start, Winter's Cradle):
# the prologue chapter screen (IncrementChapter CHPTXT0/1) and, in IWD:EE, Hrothgar's opening cutscene EHHROTHT;
# AR2000: the avalanche movie (classic) / journal clean-up (EE)
AREA_SCRIPT_AREAS = (AREA, 'AR1006', 'AR2000', *NEW_AREAS)


def map_id(i, ar):
    return AREA_IDS.get(ar, MAP_ID + i)


def script_base(i):
    """interior n's actor script ids (clear of the baked-object scripts GENERIC_BASE + n = 1281..)"""
    # (n >= 19: 1500.. in steps of 50, clear of the spawnables 1400..1498 and the speech bubbles 1499)
    if i >= 1 and INTERIORS[i - 1] in CHAPTER_DUNGEONS:
        return 5000 + 96 * CHAPTER_DUNGEONS.index(INTERIORS[i - 1])
    if i >= 20:
        return 1800 + 64 * (i - 20)
    return (SCRIPT_BASE + 20 + 10 * i if i <= 14 else 1300 + 10 * (i - 15) if i <= 17 else 1330 if i == 18
            else 1500 + 50 * (i - 19))


def name_base(i):
    """interior n's creature name ids (description .mes): 20 per area, 60 for the cave (AR1201, 45 actors)"""
    if i >= 1 and INTERIORS[i - 1] in CHAPTER_DUNGEONS:
        return 29000 + 96 * CHAPTER_DUNGEONS.index(INTERIORS[i - 1])
    return 27000 + 20 * i + 80 if i <= 18 else 27000 + 20 * 18 + 80 + 60 * (i - 18)
def install_varhooks(scr):
    """IE variable store save/load hook (ie_vars): Temple+ imports scr/tpModifiers/*.py at startup."""
    d = os.path.join(scr, 'tpModifiers'); os.makedirs(d, exist_ok=True)
    for module in ('ie_varhooks.py', 'ie_raider_death.py', 'ie_palisade_defender.py'):
        shutil.copy(os.path.join(HERE, 'runtime', 'tpModifiers', module), d)
    old = os.path.join(scr, 'ie_varslots.py')          # (slot table of older builds: no longer used)
    if os.path.isfile(old):
        os.remove(old)

RUNTIME = ['ie_runtime', 'ie_critters', 'ie_spellrt', 'ie_combat', 'ie_doors', 'ie_bakert', 'ie_itemrt', 'ie_travel', 'ie_atlas', 'ie_movies_rt', 'ie_cutscene', 'map_tick', 'ie_spawn', 'ie_vars']


IWD_START = ('AR1006', 440, 464)   # STARTARE.2DA of IWD:EE; classic IWD's copy is encrypted, so it is used for both


def ie_start(ie, w, interiors):
    """The game's own new-game area and spot -> (ToEE map id, tile). IE pixels -> tiles with the converter's iso
    step (scale 1.0: 1/40 tile per px across, 1/28 down), anchored on an entrance of that area."""
    import json
    ar, x, y = IWD_START
    try:
        import iefs
        t = iefs.IEGame(ie).read('startare', '2da').decode('latin-1')
        if t.startswith('2DA'):
            ar = re.search(r'^\s*START_AREA\s+(\w+)', t, re.M).group(1).upper()
            x, y = (int(re.search(r'^\s*START_%sPOS\s+(\d+)' % k, t, re.M).group(1)) for k in 'XY')
    except Exception:
        pass
    try:
        mid = MAP_ID if ar == AREA else interiors[ar]
        e = next(e for e in json.load(open(os.path.join(w, ar + '_objects.json')))['entrances'] if e.get('toee'))
        dx, dy = x - e['x'], y - e['y']
        return mid, (int(round(e['toee'][0] - dx / 40.0 + dy / 28.0)), int(round(e['toee'][1] + dx / 40.0 + dy / 28.0)))
    except Exception as ex:
        print('warning: start %s not converted (%s); new game starts in the town' % (ar, ex))
        return MAP_ID, START


def area_scripts(ie, areas):
    """[(area, ARE header script resref)] of the AREA_SCRIPT_AREAS among `areas` that have one in the install"""
    import iefs
    from ieformats import Are
    g = iefs.IEGame(ie); out = []
    for ar in areas:
        if ar not in AREA_SCRIPT_AREAS:
            continue
        try:
            sc = (Are(g.read(ar, 'are')).script or '').strip().lower()
            if sc and sc != 'none':
                g.read(sc, 'bcs')
                out.append((ar, sc))
        except Exception as ex:
            print('warning: %s area script: %s' % (ar, ex))
    return out


def flavour(ie):
    """EE installs have a lang/ folder (and a .key next to it); classic ones keep dialog.tlk at the top."""
    if os.path.isdir(os.path.join(ie, 'lang')):
        return 'IWDEE'
    if 'dialog.tlk' in [n.lower() for n in os.listdir(ie)]:
        return 'IWD'
    sys.exit('%s does not look like an Icewind Dale install (no chitin.key / dialog.tlk / lang folder)' % ie)


def run_tool(args):
    cmd = [sys.executable, os.path.join(HERE, args[0])]
    if args[0] == 'ie_dialogue.py':
        # Whole chapters exceed the Windows process command-line length limit.
        return subprocess.run(cmd + ['--args-from-stdin'], input=json.dumps(args[1:]).encode('ascii'), cwd=HERE)
    return subprocess.run(cmd + args[1:], cwd=HERE)


def run(step, args):
    print('== %s' % step, flush=True)
    r = run_tool(args)
    if r.returncode:
        sys.exit('step "%s" failed (exit %d): %s' % (step, r.returncode, args[0]))


def run_soft(step, args):
    """like run(), but a failing step only returns False (one broken interior must not stop the whole preview)"""
    print('== %s' % step, flush=True)
    r = run_tool(args)
    return r.returncode == 0


def copytree(src, dst):
    if os.path.isdir(src):
        shutil.copytree(src, dst, dirs_exist_ok=True)


def mes_with(td, rel, lines, dest):
    """Vanilla .mes from the ToEE data (dat files; an earlier preview install's lines are dropped) + our lines."""
    try:
        txt = td.read(rel).decode('latin-1')
    except FileNotFoundError:
        txt = ''
    keys = {re.match(r'\{(\d+)\}', l).group(1) for l in lines}
    keep = [l for l in txt.splitlines() if not (re.match(r'\s*\{(\d+)\}', l) and re.match(r'\s*\{(\d+)\}', l).group(1) in keys)]
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, 'w', encoding='latin-1', newline='\r\n') as f:
        f.write('\n'.join(keep).rstrip('\n') + '\n' + '\n'.join(lines) + '\n')


def install_module_names(td, core, module):
    """Temple+ uses the module's gamedesc.mes for description IDs from 30000 up."""
    names = {}
    for filename in sorted(glob.glob(os.path.join(core, 'mes', 'description', 'ie2toee_*.mes'))):
        with open(filename, encoding='latin-1') as source:
            for line in source:
                match = re.match(r'\s*\{(\d+)\}\s*\{', line)
                if match and int(match[1]) >= 30000:
                    names[int(match[1])] = line.strip()
    if names:
        mes_with(td, 'mes/gamedesc.mes', [names[k] for k in sorted(names)],
                 os.path.join(module, 'mes', 'gamedesc.mes'))


def area_names(ie, w, specs, shops):
    """Town map place list / map description per converted area, from the IE data: the worldmap's area name
    (WORLDMAP.WMP, e.g. AR1000 'Easthaven'), else the name of the store a resident runs (STO, e.g. 'The Snowdrift
    Inn'), else '<town> - <named resident>' (an NPC with a commissioned portrait), else by the ARE's type and the
    area it is entered from: '<town> - Outskirts' (outdoor), '<town> - Cave' (0x20), '<parent> - Side Room' (off
    an interior), '<town> - House (<resref>)'."""
    import struct, iefs, iescript, iecre, ie_creatures
    from ieformats import Are
    tv = {}
    try:
        exec(open(os.path.join(w, 'ie_travel_data.py'), encoding='latin-1').read(), tv)
    except Exception:
        pass
    parent = {}       # area -> the converted area whose exit leads into it (the town wins)
    for src, a in sorted(tv.get('AREAS', {}).items(), key=lambda kv: kv[0] != AREA):
        for r in a.get('regions', []):
            parent.setdefault(r.get('dest_area'), src)
    g = iefs.IEGame(ie); t = iescript.Tlk.load(iescript.find_tlk(ie))
    wmp = {}
    try:
        b = g.read('worldmap', 'wmp'); off = struct.unpack_from('<I', b, 12)[0]
        cnt, ao = struct.unpack_from('<II', b, off + 0x20)
        for i in range(cnt):
            o = ao + i * 0xf0
            wmp[b[o:o + 8].split(b'\0')[0].decode('latin-1').upper()] = t.get(struct.unpack_from('<i', b, o + 0x40)[0])
    except Exception as ex:
        print('warning: worldmap names: %s' % ex)
    town = wmp.get(AREA) or AREA
    def region_name(area):
        seen = set()
        while area and area not in seen:
            if wmp.get(area):
                return wmp[area]
            seen.add(area)
            area = parent.get(area)
        return town

    out = {}
    for ar, spec in specs.items():
        name = wmp.get(ar)
        for st in sorted(set(shops.get(ar, {}).values())) if not name else ():
            try:
                name = t.get(struct.unpack_from('<I', g.read(st, 'sto'), 0x0c)[0]).strip() or None
            except Exception:
                pass
            if name:
                break
        if not name and spec and os.path.isfile(spec):
            gl = {}; exec(open(spec, encoding='latin-1').read(), gl)
            for c in gl.get('CREATURES', []):
                if c.get('resref') in ie_creatures.PORTRAITS:
                    try:
                        name = '%s - %s' % (region_name(ar), t.get(iecre.Cre(g.read(c['resref'], 'cre'), c['resref']).as_dict()['name_strref']))
                        break
                    except Exception:
                        pass
        out[ar] = name
    for ar in sorted(out, key=lambda a: parent.get(a) not in (None, AREA)):   # parents named first
        if out[ar]:
            continue
        try:
            at = Are(g.read(ar, 'are')).area_type
        except Exception:
            at = 0
        pa = parent.get(ar)
        out[ar] = ('%s - Outskirts' % region_name(ar) if at & 1 else '%s - Cave' % region_name(ar) if at & 0x20 else
                   '%s - Side Room' % out[pa] if pa and pa not in wmp and out.get(pa) else '%s - House (%s)' % (region_name(ar), ar))
    return {ar: n.replace('{', '(').replace('}', ')') for ar, n in out.items()}



# Read before modules\<module> is mounted: Temple+ builds the UI (town map place list: mes/map_names.mes, read once at
# UI startup) and the legacy game systems (scroll limits: rules/MapLimits.mes) with only modules\<module>_core and the
# base archives on the path (temple_main.cpp: UiSystems before gameSystems.LoadModule), so a module-folder copy of these
# is ignored and vanilla's names/limits for the reused ids show through (the town map listed "Church of St. Cuthbert -
# Main Floor" for 5012). Copy the overrides to <module>_core as well.
CORE_EARLY = ('mes/map_names.mes', 'rules/MapLimits.mes', 'rules/daynight.nxd')


def copy_early_to_core(M, C):
    for rel in CORE_EARLY:
        src = os.path.join(M, rel)
        if os.path.isfile(src):
            os.makedirs(os.path.dirname(os.path.join(C, rel)), exist_ok=True)
            shutil.copyfile(src, os.path.join(C, rel))


def map_names(td, names, maplist, dest):
    """mes/map_names.mes, every id from 5000 to the highest map id in key order with a non-empty text: the town
    map's place list takes the line at index (map id - 5000), so a gap or an empty line shifts or blanks the names."""
    try:
        txt = td.read('mes/map_names.mes').decode('latin-1')
    except FileNotFoundError:
        txt = ''
    d = {int(k): v.strip() for k, v in re.findall(r'^\s*\{(\d+)\}\s*\{([^}]*)\}', txt, re.M)}
    ml = {int(k): v.strip() for k, v in re.findall(r'^\{(\d+)\}\{([^,}]*)', maplist, re.M)}
    d.update(names)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, 'w', encoding='latin-1', newline='\r\n') as f:
        for k in range(5000, max(list(d) + list(ml)) + 1):
            f.write('{%d}{%s}\n' % (k, d.get(k) or ml.get(k) or 'Map %d' % k))


def starting_equipment(root, module, rules_dir):
    """Keep custom kits; restore the stock class kit when Co8 expects its shop map."""
    td = toeedata.ToEEData(root, module)
    rel = 'rules/start_equipment.mes'
    try:
        effective = td.read(rel).decode('latin-1')
    except FileNotFoundError:
        return
    source = next((a for a in reversed(td.sources) if rel in a.files and
                   re.fullmatch(r'toee\d*\.dat', os.path.basename(a.path), re.I)), None)
    if source is None:
        return
    entry = re.compile(r'^(\s*\{(\d+)\}\s*\{)([^}\r\n]*)(\})', re.M)
    stock = {int(m[2]): m[3] for m in entry.finditer(source.read(rel).decode('latin-1'))}
    def kit(m):
        key = int(m[2])
        if key < 200 and key % 100 <= 10 and m[3].split() == ['6142'] and key in stock:
            return m[1] + stock[key] + m[4]
        return m[0]
    fixed = entry.sub(kit, effective)
    if fixed != effective or os.path.isfile(os.path.join(root, 'modules', module, rel)):
        with open(os.path.join(rules_dir, 'start_equipment.mes'), 'wb') as out:
            out.write(fixed.encode('latin-1'))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--iwd', required=True, help='your Icewind Dale or Icewind Dale: Enhanced Edition folder')
    ap.add_argument('--toee', required=True, help='your Temple of Elemental Evil folder (GOG or Steam)')
    ap.add_argument('--tp', help='the preview Temple+ folder (default: the folder with TemplePlus.exe next to this one)')
    ap.add_argument('--out', default='iwd_preview_out')
    ap.add_argument('--movies-ee', help='IWD:EE folder to take the movies from (movies/*.wbm) when --iwd is classic IWD '
                    'without its CD movie BIFs; needs RAD Video Tools for the Bink 1 encode (ie_movies.py)')
    ap.add_argument('--no-movies', action='store_true')
    ap.add_argument('--install', action='store_true', help='also copy the result into the ToEE folder')
    ap.add_argument('--engine-pathnodes', action='store_true',
                    help='after --install: let Temple+ itself recalculate every map\'s path node links and write clearance.bin '
                         '(pathnode_bake.sh; needs a Temple+ build with the TP_AUTOLOAD/TP_AUTOEXEC harness and '
                         'debug.recalc_neighbours/flush_nodes/genclearance with the optional args, DudeMcDude/TemplePlus '
                         'feature/pathnode-bake, given as --tp)')
    a = ap.parse_args()
    with preview_build(a.out, (a.iwd, a.toee, a.tp, a.movies_ee, HERE)) as stage:
        if not a.no_movies:
            missing = movie_tool_check('IWD')
            report_prologue_media('IWD', missing)
        convert(a, stage)
        if a.no_movies:
            print('MOVIE SUMMARY - Skipped by request (--no-movies).', flush=True)
        else:
            report_prologue_media('IWD', missing, stage / 'work/movies/ie_movies_data.py')


def convert(a, stage):
    all_ids = [MAP_ID] + [map_id(i, ar) for i, ar in enumerate(INTERIORS, 1)]
    assert max(all_ids) <= 5198, 'map ids above 5198 crash the town map (see MAP_ID)'
    assert not ENGINE_MAP_IDS & set(all_ids), 'map ids hit engine special cases'
    assert len(set(all_ids)) == len(all_ids), 'duplicate map ids'
    ie, toee = os.path.abspath(a.iwd), os.path.abspath(a.toee)
    out = os.path.abspath(a.out)
    tp = a.tp or next((p for p in (os.path.join(HERE, '..', '..', 'TemplePlus'), os.path.join(HERE, '..', 'TemplePlus'))
                       if os.path.isfile(os.path.join(p, 'TemplePlus.exe'))), None)
    if not os.path.isfile(os.path.join(toee, 'temple.dll')):
        sys.exit('%s does not look like a ToEE folder (no temple.dll)' % toee)
    F = flavour(ie); skin = 'iwdee' if F == 'IWDEE' else 'iwd'
    if F == 'IWDEE':
        import iefs
        if not iefs.has_ee_ui(ie):
            sys.exit(iefs.old_iwdee_error(ie))
    print('IE install: %s (%s)\nToEE: %s\nTemple+: %s\nout: %s' % (ie, F, toee, tp, out))
    w = os.path.join(stage, 'work')
    tpa = ['--tp', os.path.abspath(tp)] if tp else []
    a1 = AREA.lower()

    ovr = ['--overrides', OVERRIDES] if os.path.isdir(OVERRIDES) else []
    run('map', ['ie2toee.py', '--game', ie, '--area', AREA, '--out', w, '--map-id', str(MAP_ID), '--ground-id', str(GROUND_ID)] + ovr)
    import json
    interiors = {}      # area -> map id, for the interiors that converted
    for i, ar in enumerate(INTERIORS, 1):
        if run_soft('interior %s' % ar, ['ie2toee.py', '--game', ie, '--area', ar, '--out', w,
                                         '--map-id', str(map_id(i, ar)), '--ground-id', str(GROUND_ID + i)] + ovr):
            interiors[ar] = map_id(i, ar)
        else:
            print('warning: interior %s failed to convert and is skipped (its door stays a dead end)' % ar, flush=True)
    px, py = json.load(open(os.path.join(w, AREA + '_objects.json')))['placement']['canvas_offset']
    run('spells', ['ie_spells.py', 'convert', ie, os.path.join(w, 'spells'), '--toee', toee] + tpa)
    cre = os.path.join(w, 'cre')
    run('creatures', ['ie_creatures.py', 'convert', ie, toee, cre, '--area', AREA, '--script-base', str(SCRIPT_BASE)] + tpa)
    actors = open(os.path.join(cre, 'dialogue_actors.txt')).read().split()
    icre = {}           # interior -> its creature dir (actors baked like the town's: prefab .mob, permanent ids)
    for ar, mid in sorted(interiors.items()):
        i = INTERIORS.index(ar) + 1; d = os.path.join(w, 'cre_' + ar.lower())
        if run_soft('creatures %s' % ar, ['ie_creatures.py', 'convert', ie, toee, d, '--area', ar,
                                         '--script-base', str(script_base(i)),
                                         '--name-base', str(name_base(i))] + tpa):
            icre[ar] = d
            actors += open(os.path.join(d, 'dialogue_actors.txt')).read().split()
    dlg_cmd = (['ie_dialogue.py', ie, os.path.join(cre, 'dialogue'), '--quest-base', str(QUEST_BASE)] + actors +
        sum((['--area-script', '%s:%s' % (ar, sc)] for ar, sc in area_scripts(ie, [AREA] + sorted(interiors))), []) + ['--area-map', '%s:%d:%d,%d' % (AREA, MAP_ID, px, py)] +
        sum((['--area-map', '%s:%d:%d,%d' % ((ar, mid) + tuple(json.load(open(os.path.join(w, ar + '_objects.json')))
                                                              ['placement']['canvas_offset']))]      # (merges the interiors into ie_areas.py)
             for ar, mid in sorted(interiors.items())), []))
    for ar in [AREA] + sorted(interiors):     # ARE trigger regions with a script (e.g. AR1200 CARATRG1 -> Caravan_Quest)
        if ar in FORGOTTEN_TEMPLE:
            dlg_cmd += ['--append-journal-area', ar]
        for r in json.load(open(os.path.join(w, ar + '_objects.json')))['regions']:
            if r['type'] != 'travel' and r.get('script'):
                dlg_cmd += ['--region-script', '%s:%s' % (ar, r['script'].lower())]
    run('dialogue', dlg_cmd)
    spw = os.path.join(w, 'spawnables')   # CreateCreature / ARE spawn-point CREs of the converted areas (ie_spawn.py)
    run_soft('spawnables', ['ie_creatures.py', 'spawnables', ie, toee, spw, '--scr', os.path.join(cre, 'dialogue'),
                            '--script-base', '1400', '--script-max', '1498',     # (1499: speech bubbles)
                            '--area', AREA] + sum((['--append-area' if ar in FORGOTTEN_TEMPLE else '--area', ar]
                                                   for ar in sorted(interiors)), []) + tpa)
    sa = os.path.join(spw, 'dialogue_actors.txt')     # spawned creatures' own scripts/dialogue: second dialogue pass
    if os.path.isfile(sa) and open(sa).read().split():
        run('dialogue + spawnables', dlg_cmd + open(sa).read().split())
    stores, shop_of = set(), {}   # the IE stores the converted dialogues open (StartStore) -> ToEE barter stock
    for root, _, fs in os.walk(os.path.join(cre, 'dialogue')):
        for fn in fs:
            m_ = re.match(r'py(\d{5})ie_\w+\.py$', fn)
            if m_:
                found = re.findall(r'StartStore\(c, "(\w+)"', open(os.path.join(root, fn), encoding='latin-1').read())
                stores |= {x.lower() for x in found}
                if found:
                    shop_of[int(m_.group(1))] = found[0].lower()      # script id -> the store its dialogue opens
    stores = sorted(stores)
    area_shops = {}   # area -> {actor ident: store} (shops(); also names the area: area_names())

    def shops(specs_py, ar):      # bake input: actor ident -> store, for the area's merchants
        g = {}
        if specs_py and os.path.isfile(specs_py):
            exec(open(specs_py, encoding='latin-1').read(), g)
        d = {c['ident']: shop_of[c['script_id']] for c in g.get('CREATURES', []) if c.get('script_id') in shop_of}
        area_shops[ar] = d
        p_ = os.path.join(w, 'shops_%s.json' % ar.lower()); json.dump(d, open(p_, 'w'), indent=1)
        return ['--shops', p_]
    run('items', ['ie_items.py', 'convert', ie, os.path.join(w, 'items'), '--toee', toee] +
        sum((['--area', ar, '--objects', '%s=%s' % (ar, os.path.join(w, ar + '_objects.json'))]
             for ar in [AREA] + sorted(interiors)), []) +
        sum((['--store', st] for st in stores), []) + tpa)
    run('dialog skin', ['ie_dialog_skin.py', ie, os.path.join(w, 'skin'), '--skin', skin, '--default', skin])
    bake = os.path.join(w, 'bake')
    run('bake', ['ie_bake.py', 'bake', '--area', AREA, '--flavour', F, '--specs', os.path.join(cre, 'ie_creatures_%s.py' % a1)] + shops(os.path.join(cre, 'ie_creatures_%s.py' % a1), AREA) + [
                 '--items', os.path.join(w, 'items', 'ie_itemmap.py'), '--doors', os.path.join(w, 'ie_doors_%s.py' % a1),
                 '--maps', os.path.join(w, 'maps', AREA), '--map-id', str(MAP_ID), '--placement', '%d,%d' % (px, py),
                 '--toee', toee, '--ie', ie, '--out', bake])

    for ar, mid in sorted(interiors.items()):
        al = ar.lower(); ox, oy = json.load(open(os.path.join(w, ar + '_objects.json')))['placement']['canvas_offset']
        spec = os.path.join(icre[ar], 'ie_creatures_%s.py' % al) if ar in icre else None
        run('bake %s' % ar, ['ie_bake.py', 'bake', '--area', ar, '--flavour', F] + (['--specs', spec] + shops(spec, ar) if spec else []) +
            ['--items', os.path.join(w, 'items', 'ie_itemmap.py'), '--maps', os.path.join(w, 'maps', ar),
             '--map-id', str(mid), '--placement', '%d,%d' % (ox, oy), '--generic-script', str(4000 + NEW_AREAS.index(ar) if ar in NEW_AREAS else GENERIC_BASE + INTERIORS.index(ar) + 1),
             '--toee', toee, '--ie', ie, '--out', bake])

    run('travel exits', ['ie_exits.py', w, '--out', os.path.join(w, 'ie_travel_data.py'), '--ie', ie, '--area', '%s:%d' % (AREA, MAP_ID),
                          '--info-regions', os.path.join(bake, 'rules', 'info_regions')] +
        sum((['--area', '%s:%d' % kv] for kv in sorted(interiors.items())), []))
    run('exit icons', ['ie_exiticons.py', '--travel', os.path.join(w, 'ie_travel_data.py'), '--maps', os.path.join(bake, 'modules', 'ToEE', 'maps'),
                       '--jumppoints', os.path.join(bake, 'rules', 'jumppoint.tab')])
    run('path nodes', ['ie_pathnodes.py', '--travel', os.path.join(w, 'ie_travel_data.py'), '--maps', os.path.join(bake, 'modules', 'ToEE', 'maps')])

    def path_overrides(maps_dir, label):   # hand-made path node data wins over the generator / engine bake
        for ar in [AREA] + sorted(interiors):
            got = ie_overrides.install_pathnodes(OVERRIDES, ar, os.path.join(maps_dir, ar))
            if got:
                print('%s override %s: %s' % (label, ar, ' '.join(got)), flush=True)
    path_overrides(os.path.join(bake, 'modules', 'ToEE', 'maps'), 'path node')
    print('== assemble', flush=True)
    mov = os.path.join(w, 'movies')
    if not a.no_movies:   # intro + the prologue-end avalanche (long encode); the rest: ie_movies.py convert ... without --only
        run_soft('movies', ['ie_movies.py', 'convert', '--game', ie, '--toee', toee, '--out', mov, '--reuse-from', os.path.join(out, 'work', 'movies'), '--only', 'intro', 'avalanch', 'slides', '--flavour', 'IWD'] +
                 (['--ee', os.path.abspath(a.movies_ee)] if a.movies_ee else []))
    inst = os.path.join(stage, 'install')
    M = os.path.join(inst, 'modules', MODULE); C = os.path.join(inst, 'modules', MODULE + '_core')
    os.makedirs(os.path.join(inst, 'modules'), exist_ok=True)   # modules\IWD.dat: see the install step
    for d in ('maps', 'art/ground', 'art/clip', 'rules', 'mes', 'dlg', 'scr', 'mes/description'):
        os.makedirs(os.path.join(C if d in ('dlg', 'scr', 'mes/description') else M, d), exist_ok=True)
    copytree(os.path.join(bake, 'modules', 'ToEE', 'maps', AREA), os.path.join(M, 'maps', AREA))
    for g in (AREA, AREA + '_doors', AREA + '_night'):
        copytree(os.path.join(w, 'art', 'ground', g), os.path.join(M, 'art', 'ground', g))
    copytree(os.path.join(w, 'art', 'clip', AREA), os.path.join(M, 'art', 'clip', AREA))
    for ar in interiors:
        copytree(os.path.join(bake, 'modules', 'ToEE', 'maps', ar), os.path.join(M, 'maps', ar))
        for g in (ar, ar + '_doors', ar + '_night'):
            copytree(os.path.join(w, 'art', 'ground', g), os.path.join(M, 'art', 'ground', g))
        copytree(os.path.join(w, 'art', 'clip', ar), os.path.join(M, 'art', 'clip', ar))
    copytree(os.path.join(w, 'skin', 'modules', 'ToEE'), M)
    for mid in [MAP_ID] + list(interiors.values()):    # town map tiles (ie2toee.py write_townmap)
        copytree(os.path.join(w, 'townmap', str(mid)), os.path.join(M, 'townmap', str(mid)))
    shutil.copy(os.path.join(bake, 'rules', 'jumppoint.tab'), os.path.join(M, 'rules', 'jumppoint.tab'))   # exit icons
    copytree(os.path.join(bake, 'rules', 'info_regions'), os.path.join(M, 'rules', 'info_regions'))     # clickable info points
    copytree(os.path.join(cre, 'dialogue', 'modules', 'ToEE', 'dlg'), os.path.join(C, 'dlg'))
    copytree(os.path.join(cre, 'dialogue', 'modules', 'ToEE', 'scr'), os.path.join(C, 'scr'))
    if os.path.isdir(os.path.join(cre, 'dialogue', 'modules', 'ToEE', 'sound')):
        copytree(os.path.join(cre, 'dialogue', 'modules', 'ToEE', 'sound'), os.path.join(M, 'sound'))
    copytree(os.path.join(bake, 'modules', 'ToEE', 'scr'), os.path.join(C, 'scr'))
    for d in [cre] + list(icre.values()):
        copytree(os.path.join(d, 'modules', 'ToEE', 'mes', 'description'), os.path.join(C, 'mes', 'description'))
        if os.path.isdir(os.path.join(d, 'modules', 'ToEE', 'rules', 'protos')):   # critter protos on a foreign mesh
            copytree(os.path.join(d, 'modules', 'ToEE', 'rules', 'protos'), os.path.join(C, 'rules', 'protos'))
    if os.path.isfile(os.path.join(spw, 'ie_spawnables.py')):
        shutil.copy(os.path.join(spw, 'ie_spawnables.py'), os.path.join(C, 'scr'))
        copytree(os.path.join(spw, 'modules', 'ToEE', 'mes', 'description'), os.path.join(C, 'mes', 'description'))
        if os.path.isdir(os.path.join(spw, 'modules', 'ToEE', 'rules', 'protos')):   # critter protos on a foreign mesh
            copytree(os.path.join(spw, 'modules', 'ToEE', 'rules', 'protos'), os.path.join(C, 'rules', 'protos'))
    copytree(os.path.join(w, 'items', 'modules', 'ToEE', 'mes', 'description'), os.path.join(C, 'mes', 'description'))
    copytree(os.path.join(w, 'items', 'data'), os.path.join(inst, 'data'))
    import ie_portraits   # commissioned NPC portraits (+ vanilla portraits.mes entries)
    ie_portraits.build(os.path.join(inst, 'data', 'art', 'interface', 'portraits'), ie_portraits.vanilla(toee))
    import ie_ui_art   # cutscene letterbox textures (generated)
    ie_ui_art.write_ui_art(M)
    scr = os.path.join(C, 'scr')
    for f in [os.path.join(HERE, 'runtime', m + '.py') for m in RUNTIME] + [
            os.path.join(w, 'spells', 'ie_spellmap.py'), os.path.join(w, 'items', 'ie_itemmap.py'),
            os.path.join(w, 'ie_doors_%s.py' % a1), os.path.join(bake, 'ie_bake_%s.py' % a1),
            os.path.join(w, 'ie_travel_data.py')] + [os.path.join(w, 'ie_doors_%s.py' % ar.lower()) for ar in interiors] + [
            os.path.join(bake, 'ie_bake_%s.py' % ar.lower()) for ar in interiors]:
        shutil.copy(f, scr)
    import ie_worldmap_art
    ie_worldmap_art.build(ie, os.path.join(w, 'ie_travel_data.py'), M, scr)
    install_varhooks(scr)
    if os.path.isfile(os.path.join(mov, 'ie_movies_data.py')):
        shutil.copy(os.path.join(mov, 'ie_movies_data.py'), scr)
        copytree(os.path.join(mov, 'data'), os.path.join(inst, 'data'))
        copytree(os.path.join(mov, 'modules', 'ToEE'), M)   # movies/, slide/, sound/speech/slide/, mes/subtitles/
    import ie_music
    ie_music.convert(ie, toee, inst, [(ar, ar) for ar in [AREA] + list(interiors)], module=MODULE, scr_dir=scr)
    with open(os.path.join(scr, 'iwd.py'), 'w') as f:      # (optional now: new games start in Easthaven)      # console helper:  import iwd; iwd.go()
        f.write('from toee import *\n\ndef go():\n    """Travel to the converted town (map %d)."""\n'
                '    import ie_travel\n    ie_travel.start()      # walk into a building door / the road exit: the party travels (docs/travel.md)\n'
                '    game.fade_and_teleport(0, 0, 0, %d, %d, %d)\n' % (MAP_ID, MAP_ID, START[0], START[1]))
    sn = {}
    snips = [os.path.join(w, ar + '_snippets.txt') for ar in [AREA] + list(interiors)]   # town + every interior
    snips.append(os.path.join(cre, 'dialogue', 'journal_snippets.txt'))      # IE journal -> logbook quests
    for sp in snips:
        cur = None
        if not os.path.isfile(sp):
            continue
        for l in open(sp, encoding='latin-1'):
            l = l.rstrip('\r\n')
            if l.startswith('# '):
                cur = l[2:].strip(); continue
            if l.strip() and cur:
                sn.setdefault(cur, []).append(l)
    td = toeedata.ToEEData(toee)
    install_module_names(td, C, M)
    starting_equipment(toee, MODULE, os.path.join(M, 'rules'))
    specs = {AREA: os.path.join(cre, 'ie_creatures_%s.py' % a1)}
    specs.update({ar: os.path.join(icre[ar], 'ie_creatures_%s.py' % ar.lower()) if ar in icre else None for ar in interiors})
    # Scripted actors resolve their IE death variables and shared counters through this table.
    for spec in specs.values():
        if spec and os.path.isfile(spec):
            shutil.copy2(spec, os.path.join(C, 'scr'))
    ids = dict(interiors, **{AREA: MAP_ID})
    names = area_names(ie, w, specs, area_shops)
    # vanilla town map files of the reused ids (ToEE*.dat stay loaded) would show through between ours: black them out
    from PIL import Image
    black = None
    for src in td.sources:
        for f in src.files:
            m_ = re.match(r'townmap[\\/](\d+)[\\/](z[48]\d{6}\.jpg)$', f, re.I)
            if m_ and int(m_.group(1)) in ids.values():
                dst = os.path.join(M, 'townmap', m_.group(1), m_.group(2).lower())
                if not os.path.exists(dst):
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    black = black or Image.new('RGB', (256, 256))
                    black.save(dst, quality=90)
    for ar in sorted(names, key=lambda a: ids[a]):
        print('map %d %s: %s' % (ids[ar], ar, names[ar]))
    sn.pop('mes/map_names.mes', None)     # (ie2toee.py's lines carry the resref; map_names() below writes the file)
    for rel, lines in sn.items():
        # the quest texts are only read from <module>_core (a copy in the module folder is ignored: verified in game)
        dst = C if os.path.basename(rel) in ('gamequestlog.mes', 'gamequest.mes', 'gamearea.mes', 'logbook_ui_quests_text.mes') else M
        mes_with(td, rel, lines, os.path.join(dst, rel))
    # new game -> Easthaven: Temple+ MapList flag (module-support build; docs/modding-start-map.md in the Temple+ fork)
    smap, stile = ie_start(ie, w, interiors)   # the game's own new-game spot (IWD:EE STARTARE.2DA: AR1006 at 440,464)
    print('new game start: map %d tile %s' % (smap, stile), flush=True)
    ml = os.path.join(M, 'rules', 'MapList.mes')
    t = open(ml, encoding='latin-1').read().split('\n')
    found = False
    for i, l in enumerate(t):
        if 'NEW_GAME_START' in l:   # one start map only
            t[i] = l = re.sub(r',\s*Flag:\s*NEW_GAME_START(,\s*NewGame[XY]:\s*\d+)*', '', l)
        if l.startswith('{%d}' % smap):
            l = l.rstrip('\r')
            t[i] = l[:l.rindex('}')] + ', Flag: NEW_GAME_START, NewGameX: %d, NewGameY: %d}' % stile
            found = True
    if not found:
        raise SystemExit('MapList.mes: no entry for map %d' % smap)
    with open(os.path.join(HERE, 'guidance', 'map_alerts.json'), encoding='utf-8') as f:
        alert_distances = json.load(f).get(MODULE, {})
    t = apply_map_alert_distances('\n'.join(t), ids, alert_distances).split('\n')
    open(ml, 'w', encoding='latin-1', newline='').write('\n'.join(t))
    map_names(td, {ids[ar]: n for ar, n in names.items()}, '\n'.join(t), os.path.join(M, 'mes', 'map_names.mes'))
    try:      # vanilla scroll limits of the reused ids would clip our maps (no entry = no limit)
        lim = td.read('rules/MapLimits.mes').decode('latin-1').splitlines()
    except FileNotFoundError:
        lim = []
    open(os.path.join(M, 'rules', 'MapLimits.mes'), 'w', encoding='latin-1', newline='\r\n').write(
        '\n'.join(l for l in lim if not (re.match(r'\s*\{(\d+)\}', l) and int(re.match(r'\s*\{(\d+)\}', l).group(1)) in ids.values())) + '\n')
    open(os.path.join(M, 'rules', 'daynight.nxd'), 'wb').close()   # no vanilla NPC day/night moves (they name map ids)
    copy_early_to_core(M, C)   # town map names / scroll limits are read before modules\IWD is mounted
    print('module overlay: %s  (%d areas: %s + %d interiors)' % (os.path.join(out, 'install'), 1 + len(interiors), AREA, len(interiors)))
    if a.install:
        # an earlier convert's dialogue scripts with the same numbers would shadow ours (ie_install.py)
        stale = ie_install.retire_stale(inst, toee, [MODULE, MODULE + '_core'])
        if stale:
            print('moved %d old converted script/dialogue files out of the way to %s' % (
                len(stale), os.path.join(toee, 'ie2toee-stale')), flush=True)
        copytree(inst, toee)
        # The module archive: the player's own modules\ToEE.dat (base module data: rules, protos' scripts, ...),
        # hard-linked (or copied) as modules\IWD.dat. It makes the module selectable in TemplePlusConfig; the IWD
        # folders override it. (An empty .dat makes Temple+ hang at "Module archive".) Never shipped: local data only.
        src, dst = os.path.join(toee, 'modules', 'ToEE.dat'), os.path.join(toee, 'modules', MODULE + '.dat')
        if not os.path.isfile(src):
            raise SystemExit('no modules\\ToEE.dat in %s' % toee)
        if not (os.path.isfile(dst) and os.path.getsize(dst) == os.path.getsize(src)):
            if os.path.exists(dst):
                os.remove(dst)
            try:
                os.link(src, dst)
            except OSError:
                shutil.copyfile(src, dst)
        print('installed into %s' % toee)
        if a.engine_pathnodes:   # engine-side path node links + clearance data for every converted map (pathnode_bake.sh)
            print('== engine path nodes + clearance', flush=True)
            env = dict(os.environ, TOEE_OVERLAY=toee,   # TOEE_DIR (env): a separate ToEE copy whose saves run_ingame.sh restores
                       PNBAKE_MODULE=MODULE,
                       PNBAKE_COPY_TO=os.path.join(M, 'maps'), TP_DIST=os.environ.get('TP_DIST', tp))
            r = subprocess.run(['bash', os.path.join(HERE, 'pathnode_bake.sh'), os.path.join(scr, 'ie_travel_data.py')], cwd=HERE, env=env)
            if r.returncode:
                sys.exit('step "engine path nodes" failed (exit %d)' % r.returncode)
            path_overrides(os.path.join(M, 'maps'), 'path node')                       # the bake rewrote both copies
            path_overrides(os.path.join(toee, 'modules', MODULE, 'maps'), 'installed path node')
    print('done. Run TemplePlusConfig, pick the module "%s", then start a NEW game: it begins in Easthaven.' % MODULE)


if __name__ == '__main__':
    main()

"""IWD2 proof of concept: converts Targos (IE areas AR1000-AR1006, AR1100, AR1200-AR1201) of YOUR OWN Icewind Dale II install
(GOG or retail) into ToEE maps for the preview Temple+ build.

  python ie2toee_preview_iwd2.py --iwd2 "C:\\GOG Games\\Icewind Dale 2" --toee "C:\\GOG Games\\ToEE-IWD2" [--out iwd2_out] [--install]

Same converter steps as ie2toee_preview.py (map, spells, creatures, items, bake, travel exits, exit icons, path nodes),
plus dialogue for the Targos NPCs (ie_dialogue.py; journal/quests not yet) and the IE dialogue window (ie_dialog_skin.py, from your install's GUI). Maps are named I2AR1000.. (map ids from map_id_base in guidance/iwd2.json, currently 5031-5040, immediately after IWD's 5012-5030) so they stay <= 5198 (temple.dll town map) and do not collide with IWD or ENGINE_MAP_IDS.
Install target (use a COPY of ToEE): maps, ground art, rules -> modules\\ToEE; scripts and description .mes ->
modules\\ToEE_core (Temple+ discovers scripts before modules\\ToEE is mounted); item icons -> data\\.
Nothing of IWD2 is shipped: everything is read from the install you point it at.
"""
import argparse, json, os, re, shutil, sys
import iefs

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import toeedata
from ie2toee_preview import (run, run_soft, copytree, mes_with, RUNTIME,
                             ENGINE_MAP_IDS, TOWNMAP_ID_MAX, area_names, map_names, drop_high_maplist_ids,
                             copy_early_to_core)

GUIDE = os.path.join(HERE, 'guidance', 'iwd2.json')
AREAS = ['AR1000', 'AR1001', 'AR1002', 'AR1003', 'AR1004', 'AR1005', 'AR1006', 'AR1100', 'AR1200', 'AR1201']
SPAWN_SCRIPT_BASE = 2600   # runtime-spawned creatures with a dialog/scripts: 2600..2999
# name ids stay below the ~30000 description cap: 28000+250i for the first 8 areas, then the free gap 20800-21999
# (spawn names 20300.., item names 22000..); AR1200 has >100 actors, so its scripts get 150 slots
AREA_BASES = {'AR1200': (21000, 2300), 'AR1201': (21400, 2450)}
SCRIPT_BASE = 1500  # area i's actor scripts 1500+100i.. (vanilla ToEE: <= 1374); dialogue for the actors with a DLG
START = (450, 490)   # fallback: I2AR1000 tile of IWD2's own new-game spot (STARTARE.2DA 2390,860, the docks)


def start_tile(ie, w):
    """IWD2's new-game position (STARTARE.2DA) as a ToEE tile, by an affine fit of the I2AR1000 entrances' IE -> tile."""
    try:
        import iefs
        t = iefs.IEGame(ie).read('startare', '2da').decode('latin-1')
        x, y = (int(re.search(r'START_%sPOS\s+(\d+)' % k, t).group(1)) for k in 'XY')
        P = [(e['x'], e['y'], e['toee'][0], e['toee'][1]) for e in
             json.load(open(os.path.join(w, 'I2AR1000_objects.json')))['entrances'] if e.get('toee')][:3]
        def solve(c):   # 3x3 Cramer
            m = [[p[0], p[1], 1] for p in P]; v = [p[c] for p in P]
            det = lambda a: (a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1]) - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
                             + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0]))
            d = det(m)
            return [det([[v[r] if j == i else m[r][j] for j in range(3)] for r in range(3)]) / d for i in range(3)]
        A, B = solve(2), solve(3)
        return int(round(A[0] * x + A[1] * y + A[2])), int(round(B[0] * x + B[1] * y + B[2]))
    except Exception as e:
        print('warning: IWD2 start position not read (%s); using %s' % (e, START))
        return START


def dialog_skin_for(ie):
    """IE dialogue-window skin for this IWD2 install (ie_dialog_skin.py --skin), the same rule as ie_dialog_skin.py:
    the EE 'iwdee' gamelog skin needs ui.menu and bgee.lua (override/ or chitin.key); an install without them is
    classic (GOG 2.01 / retail: GUIW.CHU message window -> 'iwd'). An Enhanced Edition folder (lang/) that lacks
    them is too old to convert: stop rather than fall back to the classic skin."""
    g = iefs.IEGame(ie)
    if g.exists('ui', 'menu') and g.exists('bgee', 'lua'):
        return 'iwdee'
    if os.path.isdir(os.path.join(ie, 'lang')):
        sys.exit('%s looks like an Enhanced Edition of Icewind Dale II, but it is too old.\n'
                 'It lacks the Enhanced Edition UI files (ui.menu and bgee.lua).\n'
                 'Please update it to a current patch and run convert_iwd2.bat again. Older Enhanced Edition '
                 'versions are not supported.\n'
                 'convert_iwd2.bat needs no special flag - just point it at the updated folder.' % ie)
    return 'iwd'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--iwd2', required=True, help='your Icewind Dale II folder (GOG or retail)')
    ap.add_argument('--toee', required=True, help='your ToEE folder (a copy)')
    ap.add_argument('--tp', help='the preview Temple+ folder')
    ap.add_argument('--out', default='iwd2_preview_out')
    ap.add_argument('--install', action='store_true')
    a = ap.parse_args()
    ie, toee, out = os.path.abspath(a.iwd2), os.path.abspath(a.toee), os.path.abspath(a.out)
    if 'chitin.key' not in [n.lower() for n in os.listdir(ie)]:
        sys.exit('%s does not look like an Icewind Dale II install (no chitin.key)' % ie)
    if not os.path.isfile(os.path.join(toee, 'temple.dll')):
        sys.exit('%s does not look like a ToEE folder (no temple.dll)' % toee)
    skin = dialog_skin_for(ie)   # before any convert: an old IWD2:EE stops here
    print('IWD2 install: %s (dialogue skin "%s")' % (ie, skin), flush=True)
    tp = a.tp or next((p for p in (os.path.join(HERE, '..', '..', 'TemplePlus'), os.path.join(HERE, '..', 'TemplePlus'))
                       if os.path.isfile(os.path.join(p, 'TemplePlus.exe'))), None)
    tpa = ['--tp', os.path.abspath(tp)] if tp else []
    guide = json.load(open(GUIDE))
    G = guide['areas']
    prefix = guide.get('map_name_prefix', 'I2')
    base = int(guide['map_id_base'])
    gbase = int(guide.get('ground_id_base', 950))
    for i, ar in enumerate(AREAS):
        G.setdefault(ar, {})
        G[ar]['map'] = base + i
        G[ar].setdefault('ground', gbase + i)
    ids_used = [G[ar]['map'] for ar in AREAS]
    assert max(ids_used) <= TOWNMAP_ID_MAX, 'map ids above %d crash the town map (see map_id_base)' % TOWNMAP_ID_MAX
    assert not ENGINE_MAP_IDS & set(ids_used), 'map ids hit engine special cases: %s' % sorted(ENGINE_MAP_IDS & set(ids_used))
    w = os.path.join(out, 'work'); os.makedirs(w, exist_ok=True)
    ok = []
    for ar in AREAS:
        if run_soft('map %s' % ar, ['ie2toee.py', '--game', ie, '--area', ar, '--out', w, '--map-id', str(G[ar]['map']),
                                    '--ground-id', str(G[ar]['ground']), '--guidance', GUIDE]):
            ok.append(ar)
        else:
            print('warning: %s failed to convert and is skipped' % ar, flush=True)
    run('spells', ['ie_spells.py', 'convert', ie, os.path.join(w, 'spells'), '--toee', toee] + tpa)
    cre = {}
    for i, ar in enumerate(AREAS):
        if ar in ok:
            d = os.path.join(w, 'cre_' + ar.lower())
            if run_soft('creatures %s' % ar, ['ie_creatures.py', 'convert', ie, toee, d, '--area', ar,
                                              '--name-base', str(AREA_BASES.get(ar, (28000 + 250 * i,))[0]),
                                              '--script-base', str(AREA_BASES.get(ar, (0, SCRIPT_BASE + 100 * i))[1])] + tpa):
                cre[ar] = d
    # dialogue: the actors that have a DLG (IE scripts of dialogue-less actors such as the goblins stay unconverted)
    actors = []
    for d in cre.values():
        for l in open(os.path.join(d, 'dialogue_actors.txt')).read().split('\n'):
            p_ = l.split()[-1].split(':') if l.strip() else []
            if len(p_) > 3 and p_[3]:
                actors += ['--actor', l.split()[-1]]
            elif len(p_) > 2:   # no DLG: a stub script (binds the ident; the .mob names this id, so no "Failed to build script name")
                # plus the actor's area-specific BCS (cutscene/battle scripts, e.g. AR1200's 12caba05 -> 12cSpn1a);
                # the generic 00* combat/AI scripts stay with ToEE's own AI
                own = [x for x in (p_[4].split(',') if len(p_) > 4 else []) if x and not x.lower().startswith('00')]
                actors += ['--actor', '%s:%s:%s::%s' % (tuple(p_[:3]) + (','.join(own),))]
    dlg = os.path.join(w, 'dialogue')
    shutil.rmtree(dlg, ignore_errors=True)   # regenerated each build: no stale scripts from earlier id layouts
    shutil.rmtree(os.path.join(w, 'spawnables'), ignore_errors=True)
    amap = sum((['--area-map', '%s:%d:%d,%d' % ((ar, G[ar]['map']) + tuple(json.load(open(os.path.join(w, 'I2' + ar + '_objects.json')))
                ['placement']['canvas_offset']))] for ar in ok), [])
    ascr = []      # each area's own script (ARE V9.1 header +0xA4)
    gm = iefs.IEGame(ie)
    for ar in ok:
        try:
            d_ = gm.read(ar.lower(), 'are'); r_ = d_[0xa4 if d_[4:8] == b'V9.1' else 0x94:][:8].rstrip(b'\0').decode('latin-1')
            if r_:
                ascr += ['--area-script', '%s:%s' % (ar, r_.lower())]
        except Exception as e:
            print('warning: area script of %s: %s' % (ar, e))
    dlg_cmd = ['ie_dialogue.py', ie, dlg, '--strip-directions', '--quest-base', '150', '--quest-max', '199',
               '--new-game', 'CHAPTER=-1'] + actors + amap + ascr
    run_soft('dialogue', dlg_cmd)
    spw = os.path.join(w, 'spawnables')   # CreateCreature / spawn-point / summon CREs (ie_spawn.py at runtime)
    run_soft('spawnables', ['ie_creatures.py', 'spawnables', ie, toee, spw, '--whole-game', '--scr', dlg,
                            '--script-base', str(SPAWN_SCRIPT_BASE), '--script-max', str(SPAWN_SCRIPT_BASE + 399)] +
             sum((['--area', ar] for ar in ok), []) + tpa)
    sa = os.path.join(spw, 'dialogue_actors.txt')     # spawned creatures' own scripts/dialogue: second dialogue pass
    if os.path.isfile(sa) and open(sa).read().split():
        run_soft('dialogue + spawnables', dlg_cmd + open(sa).read().split())
    run('items', ['ie_items.py', 'convert', ie, os.path.join(w, 'items'), '--toee', toee] +
        sum((['--area', ar, '--objects', '%s=%s' % (ar, os.path.join(w, 'I2' + ar + '_objects.json'))] for ar in ok), []) + tpa)
    bake = os.path.join(w, 'bake')
    for ar in ok:
        md = 'I2' + ar; ox, oy = json.load(open(os.path.join(w, md + '_objects.json')))['placement']['canvas_offset']
        spec = os.path.join(cre[ar], 'ie_creatures_%s.py' % ar.lower()) if ar in cre else None
        run('bake %s' % ar, ['ie_bake.py', 'bake', '--area', ar, '--flavour', 'IWD2', '--map-dir', md] + (['--specs', spec] if spec else []) +
            ['--items', os.path.join(w, 'items', 'ie_itemmap.py'), '--maps', os.path.join(w, 'maps', md),
             '--map-id', str(G[ar]['map']), '--placement', '%d,%d' % (ox, oy), '--toee', toee, '--ie', ie, '--out', bake])
    tr = os.path.join(w, 'ie_travel_data.py')
    run('travel exits', ['ie_exits.py', w, '--out', tr, '--ie', ie, '--info-regions', os.path.join(bake, 'rules', 'info_regions')] +
        sum((['--area', 'I2%s:%d' % (ar, G[ar]['map'])] for ar in ok), []))
    run('exit icons', ['ie_exiticons.py', '--travel', tr, '--maps', os.path.join(bake, 'modules', 'ToEE', 'maps'),
                       '--jumppoints', os.path.join(bake, 'rules', 'jumppoint.tab')])
    run('path nodes', ['ie_pathnodes.py', '--travel', tr, '--maps', os.path.join(bake, 'modules', 'ToEE', 'maps')])

    # IE dialogue window (Temple+ uses it only when art\interface\dialog_ie\skins.json exists): built from YOUR
    # install's GUI (classic: GUIW.CHU message window; EE: ui.menu/bgee.lua gamelog), default for every conversation
    sk = os.path.join(w, 'skin'); shutil.rmtree(sk, ignore_errors=True)
    run('dialog skin', ['ie_dialog_skin.py', ie, sk, '--skin', skin, '--default', skin])
    print('== assemble', flush=True)
    mov = os.path.join(w, 'movies')   # IWD2's .mve are Bink 1 already: a plain copy (ie_movies.py)
    run_soft('movies', ['ie_movies.py', 'convert', '--game', ie, '--toee', toee, '--out', mov, '--flavour', 'IWD2'])
    inst = os.path.join(out, 'install'); shutil.rmtree(inst, ignore_errors=True)
    M = os.path.join(inst, 'modules', 'ToEE'); C = os.path.join(inst, 'modules', 'ToEE_core'); scr = os.path.join(C, 'scr')
    for d in (os.path.join(M, 'rules'), scr, os.path.join(C, 'mes', 'description')):
        os.makedirs(d, exist_ok=True)
    for ar in ok:
        md = 'I2' + ar
        copytree(os.path.join(bake, 'modules', 'ToEE', 'maps', md), os.path.join(M, 'maps', md))
        for g in (md, md + '_doors', md + '_night'):
            copytree(os.path.join(w, 'art', 'ground', g), os.path.join(M, 'art', 'ground', g))
        copytree(os.path.join(w, 'art', 'clip', md), os.path.join(M, 'art', 'clip', md))
        f = os.path.join(w, 'ie_doors_%s.py' % md.lower())
        if os.path.isfile(f): shutil.copy(f, scr)
        f = os.path.join(bake, 'ie_bake_%s.py' % md.lower())
        if os.path.isfile(f): shutil.copy(f, scr)
    for ar in ok:    # town map tiles (ie2toee.py write_townmap)
        copytree(os.path.join(w, 'townmap', str(G[ar]['map'])), os.path.join(M, 'townmap', str(G[ar]['map'])))
    shutil.copy(os.path.join(bake, 'rules', 'jumppoint.tab'), os.path.join(M, 'rules', 'jumppoint.tab'))
    copytree(os.path.join(bake, 'rules', 'info_regions'), os.path.join(M, 'rules', 'info_regions'))
    copytree(os.path.join(sk, 'modules', 'ToEE'), M)   # art/interface/dialog_ie (+ fonts/ie_*.ttf): IE dialogue window
    copytree(os.path.join(bake, 'modules', 'ToEE', 'scr'), scr)
    for d in cre.values():
        copytree(os.path.join(d, 'modules', 'ToEE', 'mes', 'description'), os.path.join(C, 'mes', 'description'))
        if os.path.isdir(os.path.join(d, 'modules', 'ToEE', 'rules', 'protos')):   # critter protos on a foreign mesh
            copytree(os.path.join(d, 'modules', 'ToEE', 'rules', 'protos'), os.path.join(C, 'rules', 'protos'))
        for f in os.listdir(d):
            if re.match(r'ie_creatures_ar\d+\.py$', f): shutil.copy(os.path.join(d, f), scr)
    if os.path.isfile(os.path.join(spw, 'ie_spawnables.py')):
        shutil.copy(os.path.join(spw, 'ie_spawnables.py'), scr)
        copytree(os.path.join(spw, 'modules', 'ToEE', 'mes', 'description'), os.path.join(C, 'mes', 'description'))
        if os.path.isdir(os.path.join(spw, 'modules', 'ToEE', 'rules', 'protos')):   # critter protos on a foreign mesh
            copytree(os.path.join(spw, 'modules', 'ToEE', 'rules', 'protos'), os.path.join(C, 'rules', 'protos'))
    copytree(os.path.join(w, 'items', 'modules', 'ToEE', 'mes', 'description'), os.path.join(C, 'mes', 'description'))
    copytree(os.path.join(w, 'items', 'data'), os.path.join(inst, 'data'))
    import ie_portraits   # commissioned NPC portraits (+ vanilla portraits.mes entries)
    ie_portraits.build(os.path.join(inst, 'data', 'art', 'interface', 'portraits'), ie_portraits.vanilla(toee))
    import ie_ui_art   # cutscene letterbox textures (generated)
    ie_ui_art.write_ui_art(M)
    if os.path.isfile(os.path.join(mov, 'ie_movies_data.py')):
        os.makedirs(scr, exist_ok=True); shutil.copy(os.path.join(mov, 'ie_movies_data.py'), scr)
        copytree(os.path.join(mov, 'data'), os.path.join(inst, 'data'))
        copytree(os.path.join(mov, 'modules', 'ToEE'), M)   # movies/, slide/, sound/speech/slide/, mes/subtitles/
    if os.path.isdir(os.path.join(dlg, 'modules', 'ToEE', 'dlg')):
        copytree(os.path.join(dlg, 'modules', 'ToEE', 'dlg'), os.path.join(C, 'dlg'))
        copytree(os.path.join(dlg, 'modules', 'ToEE', 'scr'), scr)
    for f in [os.path.join(HERE, 'runtime', m + '.py') for m in RUNTIME] + [
            os.path.join(w, 'spells', 'ie_spellmap.py'), os.path.join(w, 'items', 'ie_itemmap.py'), tr]:
        shutil.copy(f, scr)
    sn = {}
    for ar in ok:
        sp = os.path.join(w, 'I2' + ar + '_snippets.txt'); cur = None
        if not os.path.isfile(sp): continue
        for l in open(sp, encoding='latin-1'):
            l = l.rstrip('\r\n')
            if l.startswith('# '): cur = l[2:].strip(); continue
            if l.strip() and cur: sn.setdefault(cur, []).append(l)
    td = toeedata.ToEEData(toee)
    # vanilla town map files of the reused ids (ToEE*.dat stay loaded) would show through between ours: black them out
    from PIL import Image
    black = None
    our_ids = {G[ar]['map'] for ar in ok}
    for src in td.sources:
        for f in src.files:
            m_ = re.match(r'townmap[\\/](\d+)[\\/](z[48]\d{6}\.jpg)$', f, re.I)
            if m_ and int(m_.group(1)) in our_ids:
                dst = os.path.join(M, 'townmap', m_.group(1), m_.group(2).lower())
                if not os.path.exists(dst):
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    black = black or Image.new('RGB', (256, 256))
                    black.save(dst, quality=90)
    # shops from converted dialogues, for area_names() store fallbacks
    shop_of, area_shops = {}, {}
    dlg_dir = os.path.join(w, 'dialogue')
    if os.path.isdir(dlg_dir):
        for root, _, fs in os.walk(dlg_dir):
            for fn in fs:
                m_ = re.match(r'py(\d{5})ie_\w+\.py$', fn)
                if not m_:
                    continue
                found = re.findall(r'StartStore\(c, "(\w+)"', open(os.path.join(root, fn), encoding='latin-1').read())
                if found:
                    shop_of[int(m_.group(1))] = found[0].lower()
    specs = {ar: (os.path.join(cre[ar], 'ie_creatures_%s.py' % ar.lower()) if ar in cre else None) for ar in ok}
    for ar, spec in specs.items():
        gl = {}
        if spec and os.path.isfile(spec):
            exec(open(spec, encoding='latin-1').read(), gl)
        area_shops[ar] = {c['ident']: shop_of[c['script_id']] for c in gl.get('CREATURES', []) if c.get('script_id') in shop_of}
    names = area_names(ie, w, specs, area_shops, start_area='AR1000', prefix=prefix)
    for ar in sorted(names, key=lambda a: G[a]['map']):
        print('map %d %s: %s' % (G[ar]['map'], ar, names[ar]))
    sn.pop('mes/map_names.mes', None)     # (ie2toee.py's lines carry the resref; map_names() below writes the file)
    for rel, lines in sn.items():
        mes_with(td, rel, lines, os.path.join(M, rel))
    st = start_tile(ie, w); print('new game start: I2AR1000 tile %s' % (st,))
    ml = os.path.join(M, 'rules', 'MapList.mes')
    if os.path.isfile(ml):   # new game -> Targos docks (Temple+ MapList flag, module-support build)
        t = open(ml, encoding='latin-1').read().split('\n')
        t = drop_high_maplist_ids(t)   # strip leftover 59xx (and any other id > 5198) from the generated file
        for i, l in enumerate(t):
            if 'NEW_GAME_START' in l:   # one start map only
                t[i] = l = re.sub(r',\s*Flag:\s*NEW_GAME_START(,\s*NewGame[XY]:\s*\d+)*', '', l)
            if l.startswith('{%d}' % G['AR1000']['map']):
                l = re.sub(r',\s*Flag:\s*NEW_GAME_START.*?(?=,\s*\w+:|}\s*$)', '', l.rstrip('\r'))
                t[i] = l[:l.rindex('}')] + ', Flag: NEW_GAME_START, NewGameX: %d, NewGameY: %d}' % st
        open(ml, 'w', encoding='latin-1', newline='').write('\n'.join(t))
        map_names(td, {G[ar]['map']: n for ar, n in names.items()}, '\n'.join(t), os.path.join(M, 'mes', 'map_names.mes'))
    else:
        t = []
        map_names(td, {G[ar]['map']: n for ar, n in names.items()}, '', os.path.join(M, 'mes', 'map_names.mes'))
    try:      # vanilla scroll limits of the reused ids would clip our maps (no entry = no limit)
        lim = td.read('rules/MapLimits.mes').decode('latin-1').splitlines()
    except FileNotFoundError:
        lim = []
    open(os.path.join(M, 'rules', 'MapLimits.mes'), 'w', encoding='latin-1', newline='\r\n').write(
        '\n'.join(l for l in lim if not (re.match(r'\s*\{(\d+)\}', l) and int(re.match(r'\s*\{(\d+)\}', l).group(1)) in our_ids)) + '\n')
    open(os.path.join(M, 'rules', 'daynight.nxd'), 'wb').close()   # no vanilla NPC day/night moves (they name map ids)
    copy_early_to_core(M, C)   # town map names / scroll limits are read before modules\ToEE is mounted
    print('overlay: %s  (%d areas: %s)' % (inst, len(ok), ' '.join('I2' + x for x in ok)))
    if a.install:
        # scripts/dialogs of an earlier install in our id range (1500-2999) that this build no longer has (ids moved):
        # moved aside (out/stale_install), never deleted, so Temple+ sees one file per script id
        for sub in ('scr', 'dlg'):
            d_ = os.path.join(toee, 'modules', 'ToEE_core', sub)
            for f in (os.listdir(d_) if os.path.isdir(d_) else []):
                m_ = re.match(r'(?:py)?(\d{5})ie_', f)
                if m_ and 1500 <= int(m_.group(1)) <= 2999 and not os.path.exists(os.path.join(C, sub, f)):
                    os.makedirs(os.path.join(out, 'stale_install', sub), exist_ok=True)
                    shutil.move(os.path.join(d_, f), os.path.join(out, 'stale_install', sub, f))
        copytree(inst, toee)
        for root, _, fs in os.walk(os.path.join(toee, 'modules', 'ToEE_core', 'scr')):
            for f in fs:
                if f.endswith('.pyc'): os.remove(os.path.join(root, f))
        print('installed into %s' % toee)
    print('done. Start a NEW game in TemplePlus.exe: it begins at the Targos docks.')


if __name__ == '__main__':
    main()

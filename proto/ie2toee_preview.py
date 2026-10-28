"""One-command player preview build: converts the IE town area AR1000 of YOUR OWN Icewind Dale (classic or
Enhanced Edition) install into a ToEE module overlay for the preview Temple+ build.

  python ie2toee_preview.py --iwd "C:\\Games\\Icewind Dale" --toee "C:\\GOG Games\\ToEE" [--out iwd_preview_out]
                            [--install]

Pipeline (each step is one of the converter scripts in this folder, run in order):
  map (ie2toee.py) -> spells (ie_spells.py) -> items (ie_items.py) -> creatures (ie_creatures.py)
  -> dialogue (ie_dialogue.py) -> dialog window skin (ie_dialog_skin.py) -> bake into map files (ie_bake.py)
  -> travel exits (ie_exits.py) -> exit icons (ie_exiticons.py) -> path node placement (ie_pathnodes.py)
  [-> with --install --engine-pathnodes: Temple+ recalculates the node links with its own pathfinder and writes
      pathnodenew.pnd/pathnodedist.pnd + clearance.bin for every map (pathnode_bake.sh, the standard for new maps)]
The result is <out>/install: copy its contents into the ToEE folder (or pass --install to do that).
Nothing of the IE game is shipped with the converter: everything is read from the install you point it at.
"""
import argparse, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import toeedata

AREA, MAP_ID, GROUND_ID, START = 'AR1000', 5900, 900, (482, 424)
MODULE = 'IWD'          # Temple+ module: modules\IWD.dat (link to your ToEE.dat) + modules\IWD (maps, art, rules, mes) +
                        # modules\IWD_core (dlg, scr, quest texts); chosen in TemplePlusConfig (defaultModule=IWD)
QUEST_BASE = 1          # IE journal entries -> ToEE quests 1.. (vanilla quests are not kept in the IWD module)
SCRIPT_BASE = 1100      # town actors 1100.., interior n: 1120+10n.. (n <= 14: <= 1269); side rooms n >= 15: 1300+10(n-15)..
GENERIC_BASE = 1280    # interior n's baked-object script (the town's is 1099)
# Easthaven's 14 building interiors + 2 side rooms (AR1015 off AR1006, AR1016 off AR1007): map ids 5901..5916,
# ground ids 901..916 (map, doors, baked actors + containers)
INTERIORS = ['AR10%02d' % i for i in range(1, 17)]
# the Orc Cave chain off AR1000's south-east road exit (To1200): AR1200 hill road, AR1201 Orc Cave (map ids 5917/5918,
# ground ids 917/918); converted like the interiors (map, exits, actors, containers)
INTERIORS += ['AR1200', 'AR1201']


def script_base(i):
    """interior n's actor script ids (clear of the baked-object scripts GENERIC_BASE + n = 1281..)"""
    return SCRIPT_BASE + 20 + 10 * i if i <= 14 else 1300 + 10 * (i - 15) if i <= 17 else 1330 + 50 * (i - 18)


def name_base(i):
    """interior n's creature name ids (description .mes): 20 per area, 60 for the cave (AR1201, 45 actors)"""
    return 27000 + 20 * i + 80 if i <= 18 else 27000 + 20 * 18 + 80 + 60 * (i - 18)
RUNTIME = ['ie_runtime', 'ie_critters', 'ie_spellrt', 'ie_combat', 'ie_doors', 'ie_bakert', 'ie_itemrt', 'ie_travel']


def flavour(ie):
    """EE installs have a lang/ folder (and a .key next to it); classic ones keep dialog.tlk at the top."""
    if os.path.isdir(os.path.join(ie, 'lang')):
        return 'IWDEE'
    if 'dialog.tlk' in [n.lower() for n in os.listdir(ie)]:
        return 'IWD'
    sys.exit('%s does not look like an Icewind Dale install (no chitin.key / dialog.tlk / lang folder)' % ie)


def run(step, args):
    print('== %s' % step, flush=True)
    cmd = [sys.executable, os.path.join(HERE, args[0])] + args[1:]
    r = subprocess.run(cmd, cwd=HERE)
    if r.returncode:
        sys.exit('step "%s" failed (exit %d): %s' % (step, r.returncode, ' '.join(cmd)))


def run_soft(step, args):
    """like run(), but a failing step only returns False (one broken interior must not stop the whole preview)"""
    print('== %s' % step, flush=True)
    r = subprocess.run([sys.executable, os.path.join(HERE, args[0])] + args[1:], cwd=HERE)
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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--iwd', required=True, help='your Icewind Dale or Icewind Dale: Enhanced Edition folder')
    ap.add_argument('--toee', required=True, help='your Temple of Elemental Evil folder (GOG or Steam)')
    ap.add_argument('--tp', help='the preview Temple+ folder (default: the folder with TemplePlus.exe next to this one)')
    ap.add_argument('--out', default='iwd_preview_out')
    ap.add_argument('--install', action='store_true', help='also copy the result into the ToEE folder')
    ap.add_argument('--engine-pathnodes', action='store_true',
                    help='after --install: let Temple+ itself recalculate every map\'s path node links and write clearance.bin '
                         '(pathnode_bake.sh; needs a Temple+ build with the TP_AUTOLOAD/TP_AUTOEXEC harness and '
                         'debug.recalc_neighbours/flush_nodes/genclearance with the optional args, DudeMcDude/TemplePlus '
                         'feature/pathnode-bake, given as --tp)')
    a = ap.parse_args()
    ie, toee = os.path.abspath(a.iwd), os.path.abspath(a.toee)
    out = os.path.abspath(a.out)
    tp = a.tp or next((p for p in (os.path.join(HERE, '..', '..', 'TemplePlus'), os.path.join(HERE, '..', 'TemplePlus'))
                       if os.path.isfile(os.path.join(p, 'TemplePlus.exe'))), None)
    if not os.path.isfile(os.path.join(toee, 'temple.dll')):
        sys.exit('%s does not look like a ToEE folder (no temple.dll)' % toee)
    F = flavour(ie); skin = 'iwdee' if F == 'IWDEE' else 'iwd'
    print('IE install: %s (%s)\nToEE: %s\nTemple+: %s\nout: %s' % (ie, F, toee, tp, out))
    w = os.path.join(out, 'work'); os.makedirs(w, exist_ok=True)
    tpa = ['--tp', os.path.abspath(tp)] if tp else []
    a1 = AREA.lower()

    run('map', ['ie2toee.py', '--game', ie, '--area', AREA, '--out', w, '--map-id', str(MAP_ID), '--ground-id', str(GROUND_ID)])
    import json
    interiors = {}      # area -> map id, for the interiors that converted
    for i, ar in enumerate(INTERIORS, 1):
        if run_soft('interior %s' % ar, ['ie2toee.py', '--game', ie, '--area', ar, '--out', w,
                                         '--map-id', str(MAP_ID + i), '--ground-id', str(GROUND_ID + i)]):
            interiors[ar] = MAP_ID + i
        else:
            print('warning: interior %s failed to convert and is skipped (its door stays a dead end)' % ar, flush=True)
    px, py = json.load(open(os.path.join(w, AREA + '_objects.json')))['placement']['canvas_offset']
    run('spells', ['ie_spells.py', 'convert', ie, os.path.join(w, 'spells'), '--toee', toee] + tpa)
    cre = os.path.join(w, 'cre')
    run('creatures', ['ie_creatures.py', 'convert', ie, toee, cre, '--area', AREA, '--script-base', str(SCRIPT_BASE)] + tpa)
    actors = open(os.path.join(cre, 'dialogue_actors.txt')).read().split()
    icre = {}           # interior -> its creature dir (actors baked like the town's: prefab .mob, permanent ids)
    for ar, mid in sorted(interiors.items()):
        i = mid - MAP_ID; d = os.path.join(w, 'cre_' + ar.lower())
        if run_soft('creatures %s' % ar, ['ie_creatures.py', 'convert', ie, toee, d, '--area', ar,
                                         '--script-base', str(script_base(i)),
                                         '--name-base', str(name_base(i))] + tpa):
            icre[ar] = d
            actors += open(os.path.join(d, 'dialogue_actors.txt')).read().split()
    run('dialogue', ['ie_dialogue.py', ie, os.path.join(cre, 'dialogue'), '--quest-base', str(QUEST_BASE)] + actors +
        ['--area-script', '%s:%s' % (AREA, a1), '--area-map', '%s:%d:%d,%d' % (AREA, MAP_ID, px, py)] +
        sum((['--area-map', '%s:%d:%d,%d' % ((ar, mid) + tuple(json.load(open(os.path.join(w, ar + '_objects.json')))
                                                              ['placement']['canvas_offset']))]      # (merges the interiors into ie_areas.py)
             for ar, mid in sorted(interiors.items())), []))
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

    def shops(specs_py, ar):      # bake input: actor ident -> store, for the area's merchants
        g = {}
        if specs_py and os.path.isfile(specs_py):
            exec(open(specs_py, encoding='latin-1').read(), g)
        d = {c['ident']: shop_of[c['script_id']] for c in g.get('CREATURES', []) if c.get('script_id') in shop_of}
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
             '--map-id', str(mid), '--placement', '%d,%d' % (ox, oy), '--generic-script', str(GENERIC_BASE + mid - MAP_ID),
             '--toee', toee, '--ie', ie, '--out', bake])

    run('travel exits', ['ie_exits.py', w, '--out', os.path.join(w, 'ie_travel_data.py'), '--ie', ie, '--area', '%s:%d' % (AREA, MAP_ID),
                          '--info-regions', os.path.join(bake, 'rules', 'info_regions')] +
        sum((['--area', '%s:%d' % kv] for kv in sorted(interiors.items())), []))
    run('exit icons', ['ie_exiticons.py', '--travel', os.path.join(w, 'ie_travel_data.py'), '--maps', os.path.join(bake, 'modules', 'ToEE', 'maps'),
                       '--jumppoints', os.path.join(bake, 'rules', 'jumppoint.tab')])
    run('path nodes', ['ie_pathnodes.py', '--travel', os.path.join(w, 'ie_travel_data.py'), '--maps', os.path.join(bake, 'modules', 'ToEE', 'maps')])
    print('== assemble', flush=True)
    inst = os.path.join(out, 'install'); shutil.rmtree(inst, ignore_errors=True)
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
    shutil.copy(os.path.join(bake, 'rules', 'jumppoint.tab'), os.path.join(M, 'rules', 'jumppoint.tab'))   # exit icons
    copytree(os.path.join(bake, 'rules', 'info_regions'), os.path.join(M, 'rules', 'info_regions'))     # clickable info points
    copytree(os.path.join(cre, 'dialogue', 'modules', 'ToEE', 'dlg'), os.path.join(C, 'dlg'))
    copytree(os.path.join(cre, 'dialogue', 'modules', 'ToEE', 'scr'), os.path.join(C, 'scr'))
    copytree(os.path.join(bake, 'modules', 'ToEE', 'scr'), os.path.join(C, 'scr'))
    for d in [cre] + list(icre.values()):
        copytree(os.path.join(d, 'modules', 'ToEE', 'mes', 'description'), os.path.join(C, 'mes', 'description'))
    copytree(os.path.join(w, 'items', 'modules', 'ToEE', 'mes', 'description'), os.path.join(C, 'mes', 'description'))
    copytree(os.path.join(w, 'items', 'data'), os.path.join(inst, 'data'))
    scr = os.path.join(C, 'scr')
    for f in [os.path.join(HERE, 'runtime', m + '.py') for m in RUNTIME] + [
            os.path.join(w, 'spells', 'ie_spellmap.py'), os.path.join(w, 'items', 'ie_itemmap.py'),
            os.path.join(w, 'ie_doors_%s.py' % a1), os.path.join(bake, 'ie_bake_%s.py' % a1),
            os.path.join(w, 'ie_travel_data.py')] + [os.path.join(w, 'ie_doors_%s.py' % ar.lower()) for ar in interiors] + [
            os.path.join(bake, 'ie_bake_%s.py' % ar.lower()) for ar in interiors]:
        shutil.copy(f, scr)
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
    for rel, lines in sn.items():
        # the quest texts are only read from <module>_core (a copy in the module folder is ignored: verified in game)
        dst = C if os.path.basename(rel) in ('gamequestlog.mes', 'gamequest.mes', 'gamearea.mes', 'logbook_ui_quests_text.mes') else M
        mes_with(td, rel, lines, os.path.join(dst, rel))
    # new game -> Easthaven: Temple+ MapList flag (module-support build; docs/modding-start-map.md in the Temple+ fork)
    ml = os.path.join(M, 'rules', 'MapList.mes')
    t = open(ml, encoding='latin-1').read().split('\n')
    for i, l in enumerate(t):
        if l.startswith('{%d}' % MAP_ID):
            l = re.sub(r',\s*Flag:\s*NEW_GAME_START.*?(?=,\s*\w+:|}\s*$)', '', l.rstrip('\r'))
            t[i] = l[:l.rindex('}')] + ', Flag: NEW_GAME_START, NewGameX: %d, NewGameY: %d}' % START
            break
    else:
        raise SystemExit('MapList.mes: no entry for map %d' % MAP_ID)
    open(ml, 'w', encoding='latin-1', newline='').write('\n'.join(t))
    print('module overlay: %s  (%d areas: %s + %d interiors)' % (inst, 1 + len(interiors), AREA, len(interiors)))
    if a.install:
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
    print('done. Run TemplePlusConfig, pick the module "%s", then start a NEW game: it begins in Easthaven.' % MODULE)


if __name__ == '__main__':
    main()

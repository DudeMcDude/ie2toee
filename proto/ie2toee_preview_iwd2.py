"""IWD2 proof of concept: converts Targos (IE areas AR1000-AR1006 + AR1100) of YOUR OWN Icewind Dale II install
(GOG or retail) into ToEE maps for the preview Temple+ build.

  python ie2toee_preview_iwd2.py --iwd2 "C:\\GOG Games\\Icewind Dale 2" --toee "C:\\GOG Games\\ToEE-IWD2" [--out iwd2_out] [--install]

Same converter steps as ie2toee_preview.py (map, spells, creatures, items, bake, travel exits, exit icons, path nodes),
without dialogue. Maps are named I2AR1000.. (map ids 5950-5957, guidance/iwd2.json) so they never clash with IWD's.
Install target (use a COPY of ToEE): maps, ground art, rules -> modules\\ToEE; scripts and description .mes ->
modules\\ToEE_core (Temple+ discovers scripts before modules\\ToEE is mounted); item icons -> data\\.
Nothing of IWD2 is shipped: everything is read from the install you point it at.
"""
import argparse, json, os, re, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import toeedata
from ie2toee_preview import run, run_soft, copytree, mes_with, RUNTIME

GUIDE = os.path.join(HERE, 'guidance', 'iwd2.json')
AREAS = ['AR1000', 'AR1001', 'AR1002', 'AR1003', 'AR1004', 'AR1005', 'AR1006', 'AR1100']
START = (489, 425)   # I2AR1000 (Targos docks) new-game tile


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
    tp = a.tp or next((p for p in (os.path.join(HERE, '..', '..', 'TemplePlus'), os.path.join(HERE, '..', 'TemplePlus'))
                       if os.path.isfile(os.path.join(p, 'TemplePlus.exe'))), None)
    tpa = ['--tp', os.path.abspath(tp)] if tp else []
    G = json.load(open(GUIDE))['areas']
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
                                              '--name-base', str(27000 + 300 * i)] + tpa):
                cre[ar] = d
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

    print('== assemble', flush=True)
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
    shutil.copy(os.path.join(bake, 'rules', 'jumppoint.tab'), os.path.join(M, 'rules', 'jumppoint.tab'))
    copytree(os.path.join(bake, 'rules', 'info_regions'), os.path.join(M, 'rules', 'info_regions'))
    copytree(os.path.join(bake, 'modules', 'ToEE', 'scr'), scr)
    for d in cre.values():
        copytree(os.path.join(d, 'modules', 'ToEE', 'mes', 'description'), os.path.join(C, 'mes', 'description'))
        for f in os.listdir(d):
            if re.match(r'ie_creatures_ar\d+\.py$', f): shutil.copy(os.path.join(d, f), scr)
    copytree(os.path.join(w, 'items', 'modules', 'ToEE', 'mes', 'description'), os.path.join(C, 'mes', 'description'))
    copytree(os.path.join(w, 'items', 'data'), os.path.join(inst, 'data'))
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
    for rel, lines in sn.items():
        mes_with(td, rel, lines, os.path.join(M, rel))
    ml = os.path.join(M, 'rules', 'MapList.mes')
    if os.path.isfile(ml):   # new game -> Targos docks (Temple+ MapList flag, module-support build)
        t = open(ml, encoding='latin-1').read().split('\n')
        for i, l in enumerate(t):
            if 'NEW_GAME_START' in l:   # one start map only
                t[i] = l = re.sub(r',\s*Flag:\s*NEW_GAME_START(,\s*NewGame[XY]:\s*\d+)*', '', l)
            if l.startswith('{%d}' % G['AR1000']['map']):
                l = re.sub(r',\s*Flag:\s*NEW_GAME_START.*?(?=,\s*\w+:|}\s*$)', '', l.rstrip('\r'))
                t[i] = l[:l.rindex('}')] + ', Flag: NEW_GAME_START, NewGameX: %d, NewGameY: %d}' % START
        open(ml, 'w', encoding='latin-1', newline='').write('\n'.join(t))
    print('overlay: %s  (%d areas: %s)' % (inst, len(ok), ' '.join('I2' + x for x in ok)))
    if a.install:
        copytree(inst, toee)
        for root, _, fs in os.walk(os.path.join(toee, 'modules', 'ToEE_core', 'scr')):
            for f in fs:
                if f.endswith('.pyc'): os.remove(os.path.join(root, f))
        print('installed into %s' % toee)
    print('done. Start a NEW game in TemplePlus.exe: it begins at the Targos docks.')


if __name__ == '__main__':
    main()

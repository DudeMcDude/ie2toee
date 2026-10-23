"""One-command player preview build: converts the IE town area AR1000 of YOUR OWN Icewind Dale (classic or
Enhanced Edition) install into a ToEE module overlay for the preview Temple+ build.

  python ie2toee_preview.py --iwd "C:\\Games\\Icewind Dale" --toee "C:\\GOG Games\\ToEE" [--out iwd_preview_out]
                            [--install]

Pipeline (each step is one of the converter scripts in this folder, run in order):
  map (ie2toee.py) -> spells (ie_spells.py) -> items (ie_items.py) -> creatures (ie_creatures.py)
  -> dialogue (ie_dialogue.py) -> dialog window skin (ie_dialog_skin.py) -> bake into map files (ie_bake.py)
The result is <out>/install: copy its contents into the ToEE folder (or pass --install to do that).
Nothing of the IE game is shipped with the converter: everything is read from the install you point it at.
"""
import argparse, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import toeedata

AREA, MAP_ID, GROUND_ID, START = 'AR1000', 5900, 900, (482, 424)
SCRIPT_BASE = 1100
# Easthaven's 14 building interiors: map ids 5901.., ground ids 901.. (map + doors only; no creatures/items yet)
INTERIORS = ['AR10%02d' % i for i in range(1, 15)]
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
    run('items', ['ie_items.py', 'convert', ie, os.path.join(w, 'items'), '--toee', toee, '--area', AREA,
                  '--objects', os.path.join(w, AREA + '_objects.json')] + tpa)
    cre = os.path.join(w, 'cre')
    run('creatures', ['ie_creatures.py', 'convert', ie, toee, cre, '--area', AREA, '--script-base', str(SCRIPT_BASE)] + tpa)
    actors = open(os.path.join(cre, 'dialogue_actors.txt')).read().split()
    run('dialogue', ['ie_dialogue.py', ie, os.path.join(cre, 'dialogue')] + actors +
        ['--area-script', '%s:%s' % (AREA, a1), '--area-map', '%s:%d:%d,%d' % (AREA, MAP_ID, px, py)])
    run('dialog skin', ['ie_dialog_skin.py', ie, os.path.join(w, 'skin'), '--skin', skin, '--default', skin])
    bake = os.path.join(w, 'bake')
    run('bake', ['ie_bake.py', 'bake', '--area', AREA, '--flavour', F, '--specs', os.path.join(cre, 'ie_creatures_%s.py' % a1),
                 '--items', os.path.join(w, 'items', 'ie_itemmap.py'), '--doors', os.path.join(w, 'ie_doors_%s.py' % a1),
                 '--maps', os.path.join(w, 'maps', AREA), '--map-id', str(MAP_ID), '--placement', '%d,%d' % (px, py),
                 '--toee', toee, '--ie', ie, '--out', bake])

    run('travel exits', ['ie_exits.py', w, '--out', os.path.join(w, 'ie_travel_data.py'), '--area', '%s:%d' % (AREA, MAP_ID)] +
        sum((['--area', '%s:%d' % kv] for kv in sorted(interiors.items())), []))
    print('== assemble', flush=True)
    inst = os.path.join(out, 'install'); shutil.rmtree(inst, ignore_errors=True)
    M = os.path.join(inst, 'modules', 'ToEE'); C = os.path.join(inst, 'modules', 'ToEE_core')
    for d in ('maps', 'art/ground', 'art/clip', 'rules', 'mes', 'dlg', 'scr', 'mes/description'):
        os.makedirs(os.path.join(C if d in ('dlg', 'scr', 'mes/description') else M, d), exist_ok=True)
    copytree(os.path.join(bake, 'modules', 'ToEE', 'maps', AREA), os.path.join(M, 'maps', AREA))
    for g in (AREA, AREA + '_doors', AREA + '_night'):
        copytree(os.path.join(w, 'art', 'ground', g), os.path.join(M, 'art', 'ground', g))
    copytree(os.path.join(w, 'art', 'clip', AREA), os.path.join(M, 'art', 'clip', AREA))
    for ar in interiors:
        copytree(os.path.join(w, 'maps', ar), os.path.join(M, 'maps', ar))
        for g in (ar, ar + '_doors', ar + '_night'):
            copytree(os.path.join(w, 'art', 'ground', g), os.path.join(M, 'art', 'ground', g))
        copytree(os.path.join(w, 'art', 'clip', ar), os.path.join(M, 'art', 'clip', ar))
    copytree(os.path.join(w, 'skin', 'modules', 'ToEE'), M)
    copytree(os.path.join(cre, 'dialogue', 'modules', 'ToEE', 'dlg'), os.path.join(C, 'dlg'))
    copytree(os.path.join(cre, 'dialogue', 'modules', 'ToEE', 'scr'), os.path.join(C, 'scr'))
    copytree(os.path.join(bake, 'modules', 'ToEE', 'scr'), os.path.join(C, 'scr'))
    copytree(os.path.join(cre, 'modules', 'ToEE', 'mes', 'description'), os.path.join(C, 'mes', 'description'))
    copytree(os.path.join(w, 'items', 'modules', 'ToEE', 'mes', 'description'), os.path.join(C, 'mes', 'description'))
    copytree(os.path.join(w, 'items', 'data'), os.path.join(inst, 'data'))
    scr = os.path.join(C, 'scr')
    for f in [os.path.join(HERE, 'runtime', m + '.py') for m in RUNTIME] + [
            os.path.join(w, 'spells', 'ie_spellmap.py'), os.path.join(w, 'items', 'ie_itemmap.py'),
            os.path.join(w, 'ie_doors_%s.py' % a1), os.path.join(bake, 'ie_bake_%s.py' % a1),
            os.path.join(w, 'ie_travel_data.py')] + [os.path.join(w, 'ie_doors_%s.py' % ar.lower()) for ar in interiors]:
        shutil.copy(f, scr)
    with open(os.path.join(scr, 'iwd.py'), 'w') as f:      # console helper:  import iwd; iwd.go()
        f.write('from toee import *\n\ndef go():\n    """Travel to the converted town (map %d)."""\n'
                '    import ie_travel\n    ie_travel.start()      # walk into a building door / the road exit: the party travels (docs/travel.md)\n'
                '    game.fade_and_teleport(0, 0, 0, %d, %d, %d)\n' % (MAP_ID, MAP_ID, START[0], START[1]))
    sn = {}
    for ar in [AREA] + list(interiors):          # merge the snippets of the town and every converted interior
        cur = None
        for l in open(os.path.join(w, ar + '_snippets.txt')):
            l = l.rstrip('\r\n')
            if l.startswith('# '):
                cur = l[2:].strip(); continue
            if l.strip() and cur:
                sn.setdefault(cur, []).append(l)
    td = toeedata.ToEEData(toee)
    for rel, lines in sn.items():
        mes_with(td, rel, lines, os.path.join(M, rel))
    print('module overlay: %s  (%d areas: %s + %d interiors)' % (inst, 1 + len(interiors), AREA, len(interiors)))
    if a.install:
        copytree(inst, toee)
        print('installed into %s' % toee)
    print('done. In game: load or start a game, press Shift+~ (console), type   import iwd; iwd.go()')


if __name__ == '__main__':
    main()

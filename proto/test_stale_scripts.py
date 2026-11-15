#!/usr/bin/env python3
"""Offline test (no IE data, no game):   python3 test_stale_scripts.py
Reconverting over an earlier install must not leave two dialogue scripts with one number: Temple+ then skips one
and cannot open the .dlg, so the NPC does not talk (Hrothgar, 2026-11-13: py01187ie_hroth.py from the new convert
next to py01187ie_hrothgar.py from the 11-11 one). ie_install.retire_stale moves the old generated files out of the
module (nothing deleted) and leaves everything else alone."""
import os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ie_install

fails = []
def check(name, ok):
    print('%s %s' % ('PASS' if ok else 'FAIL', name))
    if not ok:
        fails.append(name)

def touch(*p):
    os.makedirs(os.path.dirname(os.path.join(*p)), exist_ok=True)
    open(os.path.join(*p), 'w').write('x')

with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR_TESTS')) as td:
    toee, inst = os.path.join(td, 'toee'), os.path.join(td, 'out', 'install')
    core = os.path.join(toee, 'modules', 'IWD_core')
    # the earlier install (11-11 convert) + files that are not ours
    for f in ('py01187ie_hrothgar.py', 'py01123ie_hrothgar.py', 'py01115ie_ghast.py', 'py01499ie_barks.py',
              'py00475DCALLIAN.py', 'ie_runtime.py', 'ie_bcs_ehhero1.py'):
        touch(core, 'scr', f)
    for f in ('01187ie_hrothgar.dlg', '01123ie_hrothgar.dlg', '00475dcallian.dlg'):
        touch(core, 'dlg', f)
    # the new convert
    for f in ('py01187ie_hroth.py', 'py01160ie_hroth.py', 'py01115ie_goblinarcher1.py', 'py01499ie_barks.py',
              'ie_bcs_ehhero1.py'):
        touch(inst, 'modules', 'IWD_core', 'scr', f)
    for f in ('01187ie_hroth.dlg', '01160ie_hroth.dlg'):
        touch(inst, 'modules', 'IWD_core', 'dlg', f)

    moved = ie_install.retire_stale(inst, toee, ['IWD', 'IWD_core'], stamp='T')
    left = set(os.listdir(os.path.join(core, 'scr'))) | set(os.listdir(os.path.join(core, 'dlg')))
    check('old Hrothgar script + dlg moved out', not {'py01187ie_hrothgar.py', '01187ie_hrothgar.dlg',
                                                       'py01123ie_hrothgar.py', '01123ie_hrothgar.dlg'} & left)
    check('old goblin-id leftover moved out', 'py01115ie_ghast.py' not in left)
    check('file the new convert rewrites stays', 'py01499ie_barks.py' in left)
    check('vanilla / runtime / bcs files untouched', {'py00475DCALLIAN.py', 'ie_runtime.py', 'ie_bcs_ehhero1.py',
                                                      '00475dcallian.dlg'} <= left)
    bk = os.path.join(toee, 'ie2toee-stale', 'T', 'modules', 'IWD_core')
    check('moved, not deleted', os.path.isfile(os.path.join(bk, 'scr', 'py01187ie_hrothgar.py'))
          and os.path.isfile(os.path.join(bk, 'dlg', '01187ie_hrothgar.dlg')) and len(moved) == 5)
    # after the overlay copy: one file per script number
    import shutil, re, collections
    shutil.copytree(inst, toee, dirs_exist_ok=True)
    for sub, rx in (('scr', r'^py(\d{5})'), ('dlg', r'^(\d{5})')):
        n = collections.Counter(re.match(rx, f).group(1) for f in os.listdir(os.path.join(core, sub)) if re.match(rx, f))
        check('one %s file per number after install' % sub, all(v == 1 for v in n.values()))
    check('no install on a fresh folder: nothing moved', ie_install.retire_stale(inst, os.path.join(td, 'none'), ['IWD_core']) == [])

print('%d failed' % len(fails) if fails else 'all passed')
sys.exit(1 if fails else 0)

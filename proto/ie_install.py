"""Install-time housekeeping for a converted module overlay.

Temple+ finds dialogue scripts by number: scr\\pyNNNNN*.py and dlg\\NNNNN*.dlg. Two files with the same number make
it skip one script ("Multiple scripts have the id ...") and fail to open the dialogue ("multiple scriptfiles with
number"), so the NPC never talks. A reconvert can give an actor another id or file name (the ident follows the
CRE death variable: 'hroth' vs 'hrothgar'), and copying the new overlay over an old install left the previous
convert's files next to the new ones: Hrothgar's dialogue did not start (2026-11-13 playtest).

retire_stale() moves our generated files (the 'ie_' names written by ie_dialogue.py / ie_bake.py) that the new
overlay does not contain out of the module, into <toee>\\ie2toee-stale\\<stamp>\\..., before the overlay is copied.
Nothing is deleted; other files (vanilla, other mods) are never touched."""
import os, re, shutil, time

GENERATED = {'scr': re.compile(r'^py\d{5}ie_.+\.py$', re.I), 'dlg': re.compile(r'^\d{5}ie_.+\.dlg$', re.I)}


def retire_stale(inst, toee, modules, stamp=None):
    """inst: the new overlay (has modules/<m>/scr|dlg); toee: the ToEE folder it is copied into.
    Returns the moved paths (relative to toee)."""
    stamp = stamp or time.strftime('%Y%m%d-%H%M%S')
    moved = []
    for mod in modules:
        for sub, pat in GENERATED.items():
            rel = os.path.join('modules', mod, sub)
            have = os.path.join(toee, rel)
            if not os.path.isdir(have):
                continue
            new_dir = os.path.join(inst, rel)
            new = {f.lower() for f in os.listdir(new_dir)} if os.path.isdir(new_dir) else set()
            for f in sorted(os.listdir(have)):
                if pat.match(f) and f.lower() not in new and os.path.isfile(os.path.join(have, f)):
                    dst = os.path.join(toee, 'ie2toee-stale', stamp, rel)
                    os.makedirs(dst, exist_ok=True)
                    shutil.move(os.path.join(have, f), os.path.join(dst, f))
                    moved.append(os.path.join(rel, f))
    return moved

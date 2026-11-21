"""Install the Targos Guard reputation from the player's own reputation tables."""
from copy import copy
from pathlib import Path
import re

from ie2toee_preview import mes_with


def install(td, install_root):
    root = Path(install_root)
    scripts = root / 'modules' / 'ToEE_core' / 'scr'
    # The engine loads its reputation tables at startup, before mounting the module.
    startup = copy(td)
    startup.loose = [str(Path(td.root) / 'data')]
    rules = 'rules/gamerep.mes'
    journal = 'mes/gamereplog.mes'
    title = 'Ally of the Targos Guard'
    background = 'You came to Targos to help defend the town against the goblin horde.'
    effect = 'The palisade defenders recognize your party as allies in battle.'
    reps, entries = startup.mes(rules), startup.mes(journal)
    # Reuse the same IDs when converting over a previous install with saved games.
    for rep, rule in reps.items():
        match = re.fullmatch(r'(\d+) 0 0, 0 0', rule.strip())
        if match and entries.get(rep) == title and entries.get(rep + 1000) == background:
            faction = int(match.group(1))
            break
    else:
        rep = next(i for i in range(23, 1000) if i not in reps
                   and all(i + offset not in entries for offset in (0, 1000, 2000)))
        used = {int(x) for row in td.protos().values() for x in row[154].split() if x.isdigit()}
        for rule in reps.values():
            grants, _, adjustments = rule.partition(',')
            used.update(map(int, re.findall(r'\d+', grants)))
            used.update(map(int, re.findall(r'[+-]?\d+', adjustments)[1::2]))
        faction = next(i for i in range(161, 1000) if i not in used)

    mes_with(startup, rules, ['{%d}{%d 0 0, 0 0}' % (rep, faction)], root / 'data' / rules)
    mes_with(startup, journal, ['{%d}{%s}' % (rep + offset, text) for offset, text in
                           ((0, title), (1000, background), (2000, effect))], root / 'data' / journal)
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / 'ie_targos_reputation.py').write_text(
        'REPUTATION = %d\nFACTION = %d\n' % (rep, faction), encoding='ascii')

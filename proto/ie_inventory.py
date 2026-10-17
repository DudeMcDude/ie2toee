"""Inventory the triggers / actions / object functions used by an IE game's scripts and dialogs, so the shared
runtime (ie_runtime) can be prioritised. Reads the player's install; the report stays local.

usage: python3 ie_inventory.py <IE game dir> <out.json> [--fallback iesdp_opcodes.json] [--md out.md]
"""
import sys, json, argparse, collections
import iefs, iescript as S

def run(game, ids, log=print):
    cnt = {k: collections.Counter() for k in ('bcs_trigger', 'bcs_action', 'dlg_trigger', 'dlg_action', 'object')}
    files = collections.defaultdict(set); errors = []; nfiles = collections.Counter()
    objn = list(ids['object'].by_name)
    def objs(args):
        for a in args:
            if isinstance(a, S.Obj):
                for f in a.chain:
                    cnt['object'][f] += 1
                if a.name:
                    cnt['object']['"<name>"'] += 1
                if a.filt:
                    cnt['object']['[filter]'] += 1
            elif isinstance(a, S.Call):
                objs(a.args)
    for ref in game.list('bcs'):
        try:
            b = S.Bcs(game.read(ref, 'bcs'), ids, ref)
        except FileNotFoundError:
            continue
        except Exception as e:
            errors.append((ref + '.bcs', str(e)[:120])); continue
        nfiles['bcs'] += 1
        for trig, resp in b.blocks:
            for t in trig:
                cnt['bcs_trigger'][t.name] += 1; files['bcs_trigger', t.name].add(ref); objs(t.args)
            for w, acts in resp:
                for a in S.walk_calls(acts):
                    cnt['bcs_action'][a.name] += 1; files['bcs_action', a.name].add(ref); objs(a.args)
    for ref in game.list('dlg'):
        try:
            d = S.Dlg(game.read(ref, 'dlg'), ref)
        except FileNotFoundError:
            continue
        except Exception as e:
            errors.append((ref + '.dlg', str(e)[:120])); continue
        nfiles['dlg'] += 1
        for kind, strings in (('dlg_trigger', d.state_triggers + d.trans_triggers), ('dlg_action', d.actions)):
            for s in strings:
                try:
                    calls = S.parse_script_text(s, objn)
                except SyntaxError as e:
                    errors.append((ref + '.dlg', str(e)[:120])); continue
                for c in S.walk_calls(calls):
                    k = kind if not (kind == 'dlg_action' and c is not calls[0] and False) else kind
                    cnt[k][c.name] += 1; files[k, c.name].add(ref); objs(c.args)
    return cnt, files, errors, nfiles

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('game'); ap.add_argument('out'); ap.add_argument('--fallback'); ap.add_argument('--md')
    a = ap.parse_args()
    g = iefs.IEGame(a.game)
    ids = S.IdsSet(g, json.load(open(a.fallback)) if a.fallback else None)
    cnt, files, errors, nfiles = run(g, ids)
    rep = {'files': dict(nfiles), 'ids_missing_from_install': ids.missing, 'errors': errors,
           'tables': {k: [(n, c, len(files[k, n])) for n, c in v.most_common()] for k, v in cnt.items()}}
    json.dump(rep, open(a.out, 'w'), indent=1)
    if a.md:
        with open(a.md, 'w') as f:
            f.write('# Script inventory\n\nfiles: %s; IDS missing from install (IESDP fallback used): %s; parse errors: %d\n\n'
                    % (dict(nfiles), ', '.join(ids.missing) or 'none', len(errors)))
            for k, rows in rep['tables'].items():
                f.write('## %s (%d distinct, %d uses)\n\n| # | name | uses | files |\n|---|---|---|---|\n'
                        % (k, len(rows), sum(r[1] for r in rows)))
                for i, (n, c, nf) in enumerate(rows, 1):
                    f.write('| %d | %s | %d | %d |\n' % (i, n, c, nf))
                f.write('\n')
    print(dict(nfiles), 'errors', len(errors), errors[:5])

if __name__ == '__main__':
    main()

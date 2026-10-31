"""Movies: the IE games' intro/cut movies -> ToEE Bink 1 (.bik, 'BIKi') + movies.mes entries.

  python ie_movies.py convert --game <IE dir> [--ee <IWD:EE dir>] --toee <ToEE dir> --out <dir> [--only intro]

Sources, all read from YOUR OWN install (nothing is shipped):
  * IWD2: the loose Data/*.mve files are already Bink 1 ('BIKi', the same revision ToEE's binkw32 plays): copied as is.
  * IWD:  classic MVEs live in MVEfile*.bif on the CDs; IWD:EE ships movies/*.wbm (VP8/Vorbis). Either is decoded
          by ffmpeg to a temp AVI and re-encoded to Bink 1 with RAD Video Tools (free from radgametools.com:
          radvideo64.exe binkc <avi> <bik> /v1; on Linux run under Wine). ffmpeg has no Bink encoder.
Output: <out>/data/movies/IE-<GAME>-<name>.bik and <out>/modules/ToEE/movies/movies.mes (vanilla entries + ours,
ids MOVIE_BASE + 5*index + part). Runtime: ie_movies_rt.play_intro() (first heartbeat of a new game).
"""
import argparse, glob, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
MOVIE_BASE = 1100
# (key, IE resref) in id order; key 'intro' is what the runtime plays on a new game
MOVIES = {'IWD': [('intro', 'intro'), ('bislogo', 'bislogo'), ('tsrlogo', 'tsrlogo'), ('avalanch', 'avalanch'),
                  ('tower', 'tower'), ('scry', 'scry'), ('return', 'return'), ('credits', 'credits')],
          'IWD2': [('intro', 'intro'), ('bislogo', 'bislogo'), ('wotc', 'wotc'), ('middle', 'middle'), ('end', 'end'),
                   ('credits', 'credits')]}


def find_loose(root, res, exts):
    for p in glob.glob(os.path.join(root, '**', '*'), recursive=True):
        b, e = os.path.splitext(os.path.basename(p))
        if b.lower() == res and e.lower().lstrip('.') in exts:
            return p
    return None


def radvideo():
    for p in [os.environ.get('RADVIDEO', '')] + glob.glob(os.path.expanduser('~/.wine*/drive_c/Program Files*/RADVideo/radvideo64.exe')) + [
            r'C:\Program Files (x86)\RADVideo\radvideo64.exe', r'C:\Program Files\RADVideo\radvideo64.exe']:
        if p and os.path.isfile(p):
            return p
    return None


CHUNK_S = 100   # RAD binkc stalls on uncompressed AVIs over ~2 GB: long movies are encoded as parts (queued back to back)


def duration(src):
    try:
        return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of',
                                              'csv=p=0', src]).decode().strip())
    except Exception:
        return 0.0


def to_bink1(src, dst, tmp):
    """src -> one or more Bink 1 files dst, dst-2.bik, ...; returns their paths."""
    rv = radvideo()
    if not rv:
        raise RuntimeError('RAD Video Tools (radvideo64.exe) not found: install them (free) or set RADVIDEO')
    n = max(1, int(-(-duration(src) // CHUNK_S)))
    outs = []
    for k in range(n):
        avi = os.path.join(tmp, 'in.avi'); out = os.path.join(tmp, 'out.bik')
        subprocess.check_call(['ffmpeg', '-v', 'error', '-y', '-ss', str(k * CHUNK_S), '-t', str(CHUNK_S), '-i', src,
                               '-c:v', 'rawvideo', '-pix_fmt', 'bgr24', '-c:a', 'pcm_s16le', '-ar', '22050', avi])
        wp = (lambda p: p) if os.name == 'nt' else (lambda p: 'Z:' + p.replace('/', '\\'))   # '/x' would be a switch
        cmd = [rv, 'binkc', wp(avi), wp(out), '/v1', '/o', '/#']
        if os.name != 'nt':
            env = dict(os.environ, WINEDEBUG='-all')
            env.setdefault('WINEPREFIX', rv.split('/drive_c/')[0])
            subprocess.call(['xvfb-run', '-a', 'wine'] + cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.call(cmd)
        os.remove(avi)
        if not os.path.isfile(out) or open(out, 'rb').read(4) != b'BIKi':
            raise RuntimeError('Bink 1 encode failed for %s part %d' % (src, k + 1))
        d = dst if k == 0 else dst[:-4] + '-%d.bik' % (k + 1)
        shutil.move(out, d); outs.append(d)
    return outs


def convert(game, toee, out, ee=None, only=None, flavour=None):
    import iefs, toeedata
    flavour = flavour or ('IWD2' if find_loose(game, 'intro', ('mve',)) and
                          open(find_loose(game, 'intro', ('mve',)), 'rb').read(3) == b'BIK' else 'IWD')
    g = iefs.IEGame(game)
    md = os.path.join(out, 'data', 'movies'); os.makedirs(md, exist_ok=True)
    done = {}
    tmp = tempfile.mkdtemp(prefix='iemov')
    for i, (key, res) in enumerate(MOVIES[flavour]):
        if only and key not in only:
            continue
        name = 'IE-%s-%s.bik' % (flavour, key)
        dst = os.path.join(md, name)
        src = find_loose(game, res, ('mve', 'bik'))
        try:
            parts = [dst]
            if src and open(src, 'rb').read(4) == b'BIKi':
                shutil.copy(src, dst)
            else:
                if not src:
                    try:     # classic MVE inside a BIF (IWD CD install)
                        data = g.read(res, 'mve'); src = os.path.join(tmp, res + '.mve'); open(src, 'wb').write(data)
                    except Exception:
                        src = find_loose(ee or game, res, ('wbm',)) or find_loose(game, res, ('wbm',))
                if not src:
                    print('movie %s: no source (MVE bif missing and no IWD:EE wbm)' % res); continue
                parts = to_bink1(src, dst, tmp)
            for k, pth in enumerate(parts):
                done[MOVIE_BASE + 5 * i + k] = (key, os.path.basename(pth))
            print('movie %s -> %s' % (os.path.basename(src), name), flush=True)
        except Exception as e:
            print('movie %s failed: %s' % (res, e), flush=True)
    shutil.rmtree(tmp, ignore_errors=True)
    van = toeedata.ToEEData(toee).read('movies/movies.mes').decode('latin-1')
    van = '\n'.join(l for l in van.splitlines() if not re.match(r'\{(11\d\d)\}', l))
    mm = os.path.join(out, 'modules', 'ToEE', 'movies'); os.makedirs(mm, exist_ok=True)
    with open(os.path.join(mm, 'movies.mes'), 'w', encoding='latin-1') as f:
        f.write(van.rstrip() + '\n\n// ie2toee movies (converted from your own %s install)\n' % flavour)
        for mid, (key, name) in sorted(done.items()):
            f.write('{%d}{%s;;}\t// %s %s\n' % (mid, name, flavour, key))
    with open(os.path.join(out, 'ie_movies_data.py'), 'w') as f:
        m = {}
        for mid, (k, n) in sorted(done.items()):
            m.setdefault(k, []).append(mid)
        f.write('# generated by ie_movies.py\nMOVIES = %r   # key -> movies.mes ids (parts, played in order)\n' % m)
    return done


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    c = sp.add_parser('convert')
    c.add_argument('--game', required=True); c.add_argument('--ee'); c.add_argument('--toee', required=True)
    c.add_argument('--out', required=True); c.add_argument('--only', nargs='*'); c.add_argument('--flavour')
    a = ap.parse_args()
    convert(a.game, a.toee, a.out, a.ee, a.only, a.flavour)


if __name__ == '__main__':
    main()

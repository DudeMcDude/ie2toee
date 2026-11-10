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
                  ('tower', 'tower'), ('scry', 'scry'), ('return', 'return'), ('credits', 'credits'),
                  ('howseer', 'howseer'), ('howdrag', 'howdrag'), ('ecredit', 'ecredit')],   # (HoW: IWD:EE wbm only)
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
    except Exception:     # Interplay MVE: no container duration -> decode it once
        try:
            err = subprocess.run(['ffmpeg', '-v', 'info', '-i', src, '-f', 'null', '-'], stderr=subprocess.PIPE,
                                 stdout=subprocess.DEVNULL).stderr.decode('latin-1', 'replace')
            t = re.findall(r'time=(\d+):(\d+):([\d.]+)', err)[-1]
            return int(t[0]) * 3600 + int(t[1]) * 60 + float(t[2])
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
        cut = ['-ss', str(k * CHUNK_S), '-t', str(CHUNK_S)]
        mve = src.lower().endswith('.mve')      # Interplay MVE cannot input-seek: cut on the output side
        subprocess.check_call(['ffmpeg', '-v', 'error', '-y'] + ([] if mve else cut) + ['-i', src,
                               ] + (cut + ['-r', '15'] if mve else []) + ['-c:v', 'rawvideo', '-pix_fmt', 'bgr24', '-c:a', 'pcm_s16le', '-ar', '22050', avi])
        if k and os.path.getsize(avi) < 65536:   # duration overestimated: nothing left to encode
            break
        wp = (lambda p: p) if os.name == 'nt' else (lambda p: 'Z:' + p.replace('/', '\\'))   # '/x' would be a switch
        cmd = [rv, 'binkc', wp(avi), wp(out), '/v1', '/o', '/#']
        if os.name != 'nt':
            env = dict(os.environ, WINEDEBUG='-all')
            env.setdefault('WINEPREFIX', rv.split('/drive_c/')[0])
            try:
                subprocess.call(['xvfb-run', '-a', 'wine'] + cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=900)
            except subprocess.TimeoutExpired:
                pass
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
            if os.path.exists(dst) and os.environ.get('IE_MOVIES_REUSE'):
                parts = [dst] + sorted(glob.glob(dst[:-4] + '-[0-9].bik'))
            elif src and open(src, 'rb').read(4) == b'BIKi':
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
            print('movie %s -> %s' % (res, name), flush=True)
        except Exception as e:
            print('movie %s failed: %s' % (res, e), flush=True)
    shutil.rmtree(tmp, ignore_errors=True)
    if not only or 'slides' in only:
        done.update(slides(ee or game, out, flavour) if flavour == 'IWD' else slides(game, out, flavour))
    van = toeedata.ToEEData(toee).read('movies/movies.mes').decode('latin-1')
    van = '\n'.join(l for l in van.splitlines() if not re.match(r'\{(1[12]\d\d)\}', l))
    mm = os.path.join(out, 'modules', 'ToEE', 'movies'); os.makedirs(mm, exist_ok=True)
    with open(os.path.join(mm, 'movies.mes'), 'w', encoding='latin-1') as f:
        f.write(van.rstrip() + '\n\n// ie2toee movies (converted from your own %s install)\n' % flavour)
        for mid, (key, name) in sorted(done.items()):
            f.write('{%d}{%s}\t// %s %s\n' % (mid, name if ';' in name else name + ';;', flavour, key))
    with open(os.path.join(out, 'ie_movies_data.py'), 'w') as f:
        m = {}
        for mid, (k, n) in sorted(done.items()):
            m.setdefault(k, []).append(mid)
        f.write('# generated by ie_movies.py\nMOVIES = %r   # key -> movies.mes ids (parts, played in order)\n' % m)
    return done


# ----------------------------------------------------------------------------- chapter slides
SLIDE_BASE = 1200       # movies.mes ids of the chapter slides: SLIDE_BASE + chapter (0 = prologue)
SLIDE_W, SLIDE_H = 800, 500   # vanilla end slides (slide/ES01a.jpg)


def _tlk(root):
    import struct, iescript as S
    d = open(S.find_tlk(root), 'rb').read()
    n, off = struct.unpack_from('<II', d, 10)
    def e(i):
        if i < 0 or i >= n:
            return '', ''
        f, snd, v, p, o, l = struct.unpack_from('<H8sIIII', d, 18 + i * 26)
        return snd.split(b'\0')[0].decode('latin-1').lower(), d[off + o:off + o + l].decode('latin-1')
    return e


def chapters(g, tlk):
    """[(chapter, title, narration strref)] from CHAPTERS.2DA (IWD2: row = chapter, col 0 title, col 1 narration)
    or CHPTXT<n>.2DA (IWD: the IncrementChapter("CHPTXTn") text: title + narration). IWD2's CHPTXT files are
    unused BG1 leftovers, so CHAPTERS wins."""
    out = []
    try:
        t = g.read('chapters', '2da').decode('latin-1')
        for l in t.splitlines():
            m = re.match(r'\s*(\d+)\s+(\d{3,})\s+(\d{3,})', l)
            if m:
                out.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
        if out:
            return out
    except Exception:
        pass
    for n in range(0, 16):
        try:
            t = g.read('chptxt%d' % n, '2da').decode('latin-1')
        except Exception:
            continue
        refs = [int(x) for x in re.findall(r'\b(\d{3,7})\b', t.split('DEFAULT', 2)[-1])]
        title = next((r for r in refs if not tlk(r)[0]), None)
        narr = next((r for r in refs if tlk(r)[0]), None)
        if narr is not None:
            out.append((n, title, narr))
    return out


def _subtitle_lines(text, maxlen=160):
    """Narration -> subtitle lines like vanilla mes/subtitles/intro.mes ({0}{..} {1}{..}): sentence groups."""
    sents = re.split(r'(?<=[.!?])\s+', re.sub(r'\s+', ' ', text).strip())
    lines, cur = [], ''
    for x in sents:
        if cur and len(cur) + len(x) + 1 > maxlen:
            lines.append(cur); cur = x
        else:
            cur = (cur + ' ' + x).strip()
    if cur:
        lines.append(cur)
    return lines


def _burn_title(jpg, title):
    from PIL import Image, ImageDraw, ImageFont
    im = Image.open(jpg).convert('RGB'); d = ImageDraw.Draw(im)
    try:
        f = ImageFont.truetype('DejaVuSerif-Bold.ttf', 20)
    except Exception:
        f = ImageFont.load_default()
    w = d.textbbox((0, 0), title, font=f)[2]
    x, y = (im.width - w) // 2, 28        # IWD2 guichp*b: top panel ~ y 25..55 of the 800x500 slide
    d.text((x + 1, y + 1), title, font=f, fill=(0, 0, 0)); d.text((x, y), title, font=f, fill=(222, 190, 110))
    im.save(jpg, quality=90)


def slides(game, out, flavour):
    """Chapter screens -> ToEE slides: modules/ToEE/slide/<n>.jpg, sound/speech/slide/<n>.mp3, mes/subtitles/<n>.mes."""
    import iefs
    from PIL import Image
    from iegui import decode_mos, pvrz_loader_for
    g = iefs.IEGame(game); tlk = _tlk(game); pv = pvrz_loader_for(g)
    M = os.path.join(out, 'modules', 'ToEE')
    for d in ('slide', 'sound/speech/slide', 'mes/subtitles', 'rules/subtitles'):
        os.makedirs(os.path.join(M, d), exist_ok=True)
    done = {}
    tmp = tempfile.mkdtemp(prefix='ieslide')
    for ch, title, narr in chapters(g, tlk):
        base = 'IE-%s-chap%d' % (flavour, ch)
        try:
            rgba = decode_mos(g.read('guichp%db' % ch, 'mos'), pv)
            im = Image.fromarray(rgba).convert('RGB')
            im.thumbnail((SLIDE_W, SLIDE_H), Image.LANCZOS)
            bg = Image.new('RGB', (SLIDE_W, SLIDE_H)); bg.paste(im, ((SLIDE_W - im.width) // 2, (SLIDE_H - im.height) // 2))
            bg.save(os.path.join(M, 'slide', base + '.jpg'), quality=90)
            snd, text = tlk(narr)
            wav = os.path.join(tmp, 'n.wav'); open(wav, 'wb').write(g.read(snd, 'wav'))
            src = wav
            if open(wav, 'rb').read(4) == b'WAVC':   # IE WAVC = 28-byte header + Interplay ACM
                src = os.path.join(tmp, 'n.acm'); open(src, 'wb').write(open(wav, 'rb').read()[28:])
            # temple.dll's movies.mes parser only accepts .mp3 in the sound field (anything else is
            # dropped). Miles/ToEE needs MPEG-1 Layer III (vanilla ES01a.mp3: 44100 Hz mono 64k).
            # A 22050 Hz encode is MPEG-2 and fails PlayOnce. After a Bink (BinkOpenMiles) an MP3
            # can still fail under Wine; Temple+ 0.2.91 ends the slide after 3 s and logs the Miles reason.
            subprocess.check_call(['ffmpeg', '-v', 'quiet', '-y', '-i', src,
                                   '-map_metadata', '-1', '-ac', '1', '-ar', '44100',
                                   '-c:a', 'libmp3lame', '-b:a', '64k', '-id3v2_version', '3',
                                   os.path.join(M, 'sound', 'speech', 'slide', base + '.mp3')])
            ttl = tlk(title)[1].strip() if title is not None else ''
            lines = ([ttl] if ttl else []) + _subtitle_lines(text)
            with open(os.path.join(M, 'mes', 'subtitles', base + '.mes'), 'w', encoding='latin-1', errors='replace') as f:
                f.write('\n// %s chapter %d (converted from your own install)\n\n' % (flavour, ch))
                for i, l in enumerate(lines):
                    f.write('{%d}{%s}\n' % (i, l.replace('{', '(').replace('}', ')')))
            # the engine shows subtitles only with a control file rules/subtitles/<n>.mes (vanilla es01a.mes:
            # "start ms;duration ms;font;r;g;b;text line"): title first, then the lines paced by their length
            mp3 = os.path.join(M, 'sound', 'speech', 'slide', base + '.mp3')
            dur = int(float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                                                     '-of', 'csv=p=0', mp3]).decode().strip()) * 1000)
            t0 = 500; tt = 3000 if ttl else 0; rest = max(1000, dur - t0 - tt - 300)
            body = lines[1:] if ttl else lines; tot = float(sum(len(l) for l in body)) or 1.0
            with open(os.path.join(M, 'rules', 'subtitles', base + '.mes'), 'w', encoding='latin-1') as f:
                f.write('\n// start time (milliseconds) ; duration (milliseconds) ; font name ; red ; green ; blue ; text line\n\n')
                t = t0; i = 0
                if ttl:
                    f.write('{0}{%d;%d;arial-12;193;154;62;0}\n' % (t, tt)); t += tt; i = 1
                for k, l in enumerate(body):
                    d_ = int(rest * len(l) / tot)
                    f.write('{%d}{%d;%d;arial-12;255;255;255;%d}\n' % (i + k, t, d_, i + k)); t += d_
            if ttl and flavour == 'IWD2':     # the IE drew the title into the frame's top panel
                _burn_title(os.path.join(M, 'slide', base + '.jpg'), ttl)
            done[SLIDE_BASE + ch] = ('chapter%d' % ch, '%s.jpg;%s.mp3;%s.mes' % (base, base, base))
            print('slide chapter %d: guichp%db + %s (%d subtitle lines)' % (ch, ch, snd, len(lines)), flush=True)
        except Exception as e:
            print('slide chapter %d failed: %s' % (ch, e), flush=True)
    shutil.rmtree(tmp, ignore_errors=True)
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

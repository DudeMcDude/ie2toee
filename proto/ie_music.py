"""On-the-fly IE music (.MUS / .ACM) and area ambient (.ARE WAV/WAVC) -> ToEE soundscheme converter.

Runs on the player's machine against their own IE and ToEE installs. No audio or proprietary game data
is ever stored in the converter repository.

Writes:
  <out>/modules/ToEE/sound/music/ie_<mus>.mp3
  <out>/modules/ToEE/sound/ambient/ie_<wav>.mp3
  <out>/modules/ToEE/sound/schemeindex.mes
  <out>/modules/ToEE/sound/schemelist.mes
  <map_dir>/mapinfo.txt  (SoundScheme: <scheme_id>,0)
"""
import argparse
import os
import re
import shutil
import struct
import subprocess
import tempfile
import iefs
import toeedata

SILENT_STEMS = {'spc', 'spc1', 'mx0000', 'mx0000a', 'blank', 'blanka', 'g3blank'}
SILENT_MUS = {'****', '', 'mx0000.mus', 'blank.mus', 'g3blank.mus'}


def _cstr(b):
    return b.split(b'\0', 1)[0].decode('latin-1').strip()


def find_ffmpeg():
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.environ.get('FFMPEG', ''),
        shutil.which('ffmpeg'),
        os.path.join(os.getcwd(), 'media-tools', 'ffmpeg.exe'),
        os.path.join(os.path.dirname(here), 'media-tools', 'ffmpeg.exe'),
        r'D:\Games\IE2ToEE-MediaTools\ffmpeg.exe',
    ]
    for p in candidates:
        if p and os.path.isfile(p):
            return p
    return None


def parse_songlist(game):
    """Parse SONGLIST.2DA (IWD/BG) or MUSIC.2DA (IWD2) -> {int_id: (name, mus_file)}."""
    txt = None
    for res in ('songlist', 'music'):
        try:
            txt = game.read(res, '2da').decode('latin-1', 'replace')
            break
        except Exception:
            continue
    if not txt:
        return {}
    out = {}
    lines = [l.strip() for l in txt.splitlines() if l.strip()]
    for idx, line in enumerate(lines[3:]):
        parts = line.split()
        if not parts:
            continue
        if parts[0].lstrip('-').isdigit():
            sid = int(parts[0])
            name = parts[1] if len(parts) > 1 else ''
            mus = parts[2] if len(parts) > 2 else ''
        else:
            sid = idx
            name = parts[0]
            mus = parts[1] if len(parts) > 1 else ''
        out[sid] = (name, mus)
    return out


def parse_mus(mus_text, max_stems=8):
    """Parse an IE .MUS playlist into (folder_prefix, [stem_names])."""
    lines = []
    for raw in mus_text.splitlines():
        s = raw.split('#', 1)[0].strip()
        if s:
            lines.append(s)
    if len(lines) < 3:
        return '', []
    prefix = lines[0].split()[0]
    try:
        count = int(lines[1].split()[0])
    except ValueError:
        count = len(lines) - 2
    stems = []
    for entry in lines[2:2 + count]:
        toks = entry.split()
        if not toks:
            continue
        first = toks[0]
        if first.lower() == 'loop' or first.startswith('@'):
            break
        low = first.lower()
        if low in SILENT_STEMS or low.startswith('spc'):
            continue
        stems.append(first)
        if len(stems) >= max_stems:
            break
    return prefix, stems


def parse_are_audio(data):
    """Extract outdoor flag, song indices, and enabled ambient records from ARE V1.0 / V9.1 bytes."""
    sig = data[:8]
    if sig == b'AREAV1.0':
        s = 0
    elif sig == b'AREAV9.1':
        s = 0x10
    else:
        raise ValueError(f'Unsupported ARE signature: {sig!r}')
    area_type = struct.unpack_from('<H', data, 0x48)[0]
    outdoor = bool(area_type & 1)
    amb_cnt, amb_off = struct.unpack_from('<HI', data, 0x82 + s)
    song_off = struct.unpack_from('<I', data, 0xbc + s)[0]
    svals = struct.unpack_from('<10i', data, song_off) if song_off and song_off + 40 <= len(data) else (-1,) * 10

    ambients = []
    for i in range(amb_cnt):
        ao = amb_off + i * 0xd4
        if ao + 0xd4 > len(data):
            break
        name = _cstr(data[ao:ao + 32])
        vol = struct.unpack_from('<H', data, ao + 0x2e)[0]
        raw_snds = [_cstr(data[ao + 0x30 + k * 8:ao + 0x38 + k * 8]) for k in range(10)]
        scnt = struct.unpack_from('<H', data, ao + 0x80)[0]
        snds = [x for x in raw_snds[:min(scnt, 10)] if x]
        interval, deviation, sched, flags = struct.unpack_from('<IIII', data, ao + 0x84)
        if not (flags & 1) or not snds:
            continue
        if outdoor and not (flags & 4):
            continue
        looping = bool((flags & 2) or (interval == 0 and len(snds) == 1))
        ambients.append({
            'name': name,
            'volume': vol,
            'sounds': snds,
            'interval': interval,
            'schedule': sched & 0xffffff,
            'flags': flags,
            'looping': looping,
            'global': bool(flags & 4),
        })
    return {
        'outdoor': outdoor,
        'day_song': svals[0],
        'night_song': svals[1],
        'win_song': svals[2],
        'battle_song': svals[3],
        'lose_song': svals[4],
        'ambients': ambients,
    }


def schedule_times(sched):
    """Map an IE 24-bit hour schedule bitmask to ToEE schemelist /time: ranges."""
    mask = sched & 0xffffff
    if mask == 0 or mask == 0xffffff:
        return [None]
    day_on = bool(mask & (1 << 12))
    night_on = bool((mask & 1) or (mask & (1 << 23)))
    if day_on and not night_on:
        return ['6-17']
    if night_on and not day_on:
        return ['18-23', '0-5']
    return [None]


def _find_mus_file(music_dir, mus_name):
    if not music_dir or not mus_name or mus_name.lower() in SILENT_MUS:
        return None
    base = mus_name if mus_name.lower().endswith('.mus') else (mus_name + '.mus')
    return iefs._ci_find(music_dir, base)


def resolve_stem_paths(music_dir, mus_path):
    """Return existing .acm file paths for a .mus playlist."""
    if not mus_path or not os.path.isfile(mus_path):
        return []
    with open(mus_path, 'r', encoding='latin-1', errors='replace') as f:
        prefix, stems = parse_mus(f.read())
    if not prefix or not stems:
        return []
    sub = iefs._ci_find(music_dir, prefix)
    out = []
    for st in stems:
        candidates = []
        if sub and os.path.isdir(sub):
            candidates.append(os.path.join(sub, f'{prefix}{st}.acm'))
            candidates.append(os.path.join(sub, f'{st}.acm'))
        candidates.append(os.path.join(music_dir, f'{prefix}{st}.acm'))
        for cand in candidates:
            hit = iefs._ci_find(music_dir, os.path.relpath(cand, music_dir))
            if hit and os.path.isfile(hit):
                out.append(hit)
                break
    return out


def resolve_area_music(area_name, are_info, songlist, music_dir, bcs_text=''):
    """Determine (day_mus_path, night_mus_path, battle_mus_path) for an area."""
    def song_mus(sid):
        if sid is None or sid <= 0 or sid not in songlist:
            return None
        _, mus = songlist[sid]
        if not mus or mus.lower() in SILENT_MUS:
            return None
        return _find_mus_file(music_dir, mus)

    day_mus = song_mus(are_info['day_song'])
    night_mus = song_mus(are_info['night_song'])
    m = re.match(r'^AR(\d{4})$', area_name.upper())
    if day_mus is None and m and music_dir:
        day_mus = _find_mus_file(music_dir, f'mx{m.group(1)}.mus')
    if night_mus is None and day_mus is not None:
        night_mus = day_mus

    battle_mus = song_mus(are_info['battle_song'])
    if battle_mus is None and bcs_text:
        for sm in re.finditer(r'SetMusic\([^,]+,\s*\d+\s*,\s*(\d+)\)', bcs_text):
            cand_id = int(sm.group(1))
            if cand_id in songlist and songlist[cand_id][0].upper().startswith('BATTLE'):
                battle_mus = song_mus(cand_id)
                if battle_mus:
                    break
    if battle_mus is None and m and music_dir:
        battle_mus = _find_mus_file(music_dir, f'ba{m.group(1)}.mus')
    if battle_mus is None and music_dir:
        au = area_name.upper()
        if au == 'AR1201' and _find_mus_file(music_dir, 'bc1.mus'):
            battle_mus = _find_mus_file(music_dir, 'bc1.mus')
        elif au in ('AR1200', 'AR2000') and _find_mus_file(music_dir, 'bm1.mus'):
            battle_mus = _find_mus_file(music_dir, 'bm1.mus')
        elif au.startswith('AR12') and _find_mus_file(music_dir, 'b3.mus'):
            battle_mus = _find_mus_file(music_dir, 'b3.mus')
        elif au.startswith('AR11') and _find_mus_file(music_dir, 'b2.mus'):
            battle_mus = _find_mus_file(music_dir, 'b2.mus')
        else:
            battle_mus = _find_mus_file(music_dir, 'b1.mus')
    return day_mus, night_mus, battle_mus


def build_scheme_lines(are_info, day_mp3, night_mp3, battle_mp3, amb_mp3_map, max_lines=60):
    """Build the list of schemelist.mes value strings for one area sound scheme."""
    lines = []
    if day_mp3 and (not night_mp3 or night_mp3 == day_mp3):
        lines.append(f'music\\{day_mp3} /VOL:50 /loop')
    else:
        if day_mp3:
            lines.append(f'music\\{day_mp3} /VOL:50 /loop /time:6-17')
        if night_mp3:
            lines.append(f'music\\{night_mp3} /VOL:50 /loop /time:18-23')
            lines.append(f'music\\{night_mp3} /VOL:50 /loop /time:0-5')
    if battle_mp3:
        lines.append(f'music\\{battle_mp3} /VOL:50 /combatmusic')

    seen_loops = set()
    seen_scatters = set()
    for amb in are_info['ambients']:
        times = schedule_times(amb['schedule'])
        if amb['looping']:
            snd = amb['sounds'][0].lower()
            mp3 = amb_mp3_map.get(snd)
            if not mp3:
                continue
            scale = 0.45 if amb['global'] else 0.30
            cap = 50 if amb['global'] else 35
            vol = max(15, min(cap, int(round(amb['volume'] * scale))))
            for t in times:
                key = (mp3, t)
                if key in seen_loops or len(lines) >= max_lines:
                    continue
                seen_loops.add(key)
                t_opt = f' /time:{t}' if t else ''
                lines.append(f'ambient\\{mp3} /VOL:{vol} /loop{t_opt}')
        else:
            interval = max(3, amb['interval'] or 15)
            freq = max(3, min(35, int(round(100.0 / interval))))
            vol = max(15, min(45, int(round(amb['volume'] * 0.40))))
            for s_res in amb['sounds']:
                mp3 = amb_mp3_map.get(s_res.lower())
                if not mp3:
                    continue
                for t in times:
                    key = (mp3, t)
                    if key in seen_scatters or len(lines) >= max_lines:
                        continue
                    seen_scatters.add(key)
                    t_opt = f' /time:{t}' if t else ''
                    lines.append(f'ambient\\{mp3} /scatter /freq:{freq} /VOL:{vol}{t_opt}')
    return lines


def convert_mus_track(music_dir, mus_path, out_music_dir, ffmpeg_bin, tmp_dir, cache):
    """Transcode a .mus playlist's .acm stem(s) into out_music_dir/ie_<name>.mp3."""
    if not mus_path or not ffmpeg_bin:
        return None
    stem_name = os.path.splitext(os.path.basename(mus_path))[0].lower()
    mp3_name = f'ie_{stem_name}.mp3'
    if stem_name in cache:
        return cache[stem_name]
    dst = os.path.join(out_music_dir, mp3_name)
    if os.path.isfile(dst) and os.path.getsize(dst) > 100:
        cache[stem_name] = mp3_name
        return mp3_name
    stems = resolve_stem_paths(music_dir, mus_path)
    if not stems:
        return None
    os.makedirs(out_music_dir, exist_ok=True)
    try:
        if len(stems) == 1:
            subprocess.check_call([
                ffmpeg_bin, '-v', 'quiet', '-max_error_rate', '1.0', '-y', '-i', stems[0],
                '-map_metadata', '-1', '-ac', '2', '-ar', '44100',
                '-c:a', 'libmp3lame', '-b:a', '128k', '-id3v2_version', '3', dst
            ])
        else:
            wavs = []
            for idx, sp in enumerate(stems):
                w = os.path.join(tmp_dir, f'{stem_name}_{idx}.wav')
                subprocess.check_call([ffmpeg_bin, '-v', 'quiet', '-max_error_rate', '1.0', '-y', '-i', sp, w])
                wavs.append(w)
            lst = os.path.join(tmp_dir, f'{stem_name}_concat.txt')
            with open(lst, 'w', encoding='utf-8') as f:
                for w in wavs:
                    f.write("file '" + w.replace('\\', '/') + "'\n")
            subprocess.check_call([
                ffmpeg_bin, '-v', 'quiet', '-max_error_rate', '1.0', '-y', '-f', 'concat', '-safe', '0', '-i', lst,
                '-map_metadata', '-1', '-ac', '2', '-ar', '44100',
                '-c:a', 'libmp3lame', '-b:a', '128k', '-id3v2_version', '3', dst
            ])
        cache[stem_name] = mp3_name
        return mp3_name
    except Exception as e:
        print(f'warning: music track {mus_path}: {e}')
        return None


def convert_ambient_wav(game, resref, out_amb_dir, ffmpeg_bin, tmp_dir, cache):
    """Transcode an IE ambient WAV/WAVC resource into out_amb_dir/ie_<resref>.mp3."""
    key = resref.lower()
    if key in cache:
        return cache[key]
    mp3_name = f'ie_{key}.mp3'
    dst = os.path.join(out_amb_dir, mp3_name)
    if os.path.isfile(dst) and os.path.getsize(dst) > 100:
        cache[key] = mp3_name
        return mp3_name
    if not ffmpeg_bin:
        return None
    try:
        raw = game.read(resref, 'wav')
    except Exception:
        return None
    os.makedirs(out_amb_dir, exist_ok=True)
    src = os.path.join(tmp_dir, key + ('.acm' if raw[:4] == b'WAVC' else '.wav'))
    try:
        with open(src, 'wb') as f:
            f.write(raw[28:] if raw[:4] == b'WAVC' else raw)
        subprocess.check_call([
            ffmpeg_bin, '-v', 'quiet', '-max_error_rate', '1.0', '-y', '-i', src,
            '-map_metadata', '-1', '-ar', '44100',
            '-c:a', 'libmp3lame', '-b:a', '96k', '-id3v2_version', '3', dst
        ])
        cache[key] = mp3_name
        return mp3_name
    except Exception as e:
        print(f'warning: ambient sound {resref}: {e}')
        return None


def update_mapinfo_soundscheme(mapinfo_path, scheme1, scheme2=0):
    """Write or update 'SoundScheme: s1,s2' in a map's mapinfo.txt."""
    lines = []
    if os.path.isfile(mapinfo_path):
        with open(mapinfo_path, 'r', encoding='latin-1', errors='replace') as f:
            raw_lines = f.read().splitlines()
        for l in raw_lines:
            if not l.strip().lower().startswith('soundscheme:'):
                lines.append(l)
    lines.append(f'SoundScheme: {scheme1},{scheme2}')
    os.makedirs(os.path.dirname(mapinfo_path), exist_ok=True)
    with open(mapinfo_path, 'w', encoding='latin-1', newline='\r\n') as f:
        f.write('\n'.join(lines) + '\n')


def _strip_scheme_range(mes_text, min_key):
    out = []
    for line in mes_text.splitlines():
        m = re.match(r'^\s*\{(\d+)\}', line)
        if m and int(m.group(1)) >= min_key:
            continue
        out.append(line)
    return '\n'.join(out).rstrip() + '\n'


def _replace_mes_line(mes_text, key, new_val):
    pat = re.compile(r'^\s*\{' + str(key) + r'\}\s*\{[^}]*\}.*$', re.M)
    rep = f'{{{key}}}{{{new_val}}}'
    if pat.search(mes_text):
        return pat.sub(lambda _: rep, mes_text, count=1)
    return mes_text.rstrip() + f'\n{rep}\n'


def convert(ie_dir, toee_dir, out_dir, area_maps, module='ToEE', scheme_base=70, scr_dir=None):
    """Convert music and area ambients for [(area_name, map_folder_name_or_path), ...] on the fly.

    Writes sound/music/ie_*.mp3, sound/ambient/ie_*.mp3, sound/schemeindex.mes, sound/schemelist.mes
    under <out_dir>/modules/<module>/sound/, and updates each map's mapinfo.txt with SoundScheme.
    """
    game = iefs.IEGame(ie_dir)
    td = toeedata.ToEEData(toee_dir, module=module)
    songlist = parse_songlist(game)
    music_dir = iefs._ci_find(ie_dir, 'music')
    ffmpeg_bin = find_ffmpeg()
    if not ffmpeg_bin:
        print('warning: ffmpeg not found; skipping music/ambient audio transcoding')

    sound_root = os.path.join(out_dir, 'modules', module, 'sound')
    out_music_dir = os.path.join(sound_root, 'music')
    out_amb_dir = os.path.join(sound_root, 'ambient')
    os.makedirs(sound_root, exist_ok=True)

    try:
        idx_text = td.read('sound/schemeindex.mes').decode('latin-1')
    except Exception:
        idx_text = '{0}{<<NONE>>}\n'
    try:
        lst_text = td.read('sound/schemelist.mes').decode('latin-1')
    except Exception:
        lst_text = '{0}{dummy - none}\n'

    idx_text = _strip_scheme_range(idx_text, scheme_base)
    lst_text = _strip_scheme_range(lst_text, scheme_base * 100)

    mus_cache = {}
    amb_cache = {}
    tmp_dir = tempfile.mkdtemp(prefix='ie_music_')
    report = {'theme': None, 'areas': {}, 'music_files': 0, 'ambient_files': 0}

    try:
        # Main menu / ShopMap theme (schemes 14 -> #1400 and 29 -> #2900)
        theme_mus = _find_mus_file(music_dir, 'theme.mus')
        if theme_mus:
            theme_mp3 = convert_mus_track(music_dir, theme_mus, out_music_dir, ffmpeg_bin, tmp_dir, mus_cache)
            if theme_mp3:
                report['theme'] = theme_mp3
                lst_text = _replace_mes_line(lst_text, 1400, f'music\\{theme_mp3} /VOL:60 /loop')
                lst_text = _replace_mes_line(lst_text, 2900, f'music\\{theme_mp3} /VOL:50 /loop')

        idx_add = ['\n// IE converted area sound schemes (generated on the fly by ie_music.py)']
        lst_add = ['\n// IE converted area sound schemes (generated on the fly by ie_music.py)']

        for i, (area_name, map_dir) in enumerate(area_maps):
            au = area_name.upper()
            scheme_id = scheme_base + i
            base_line = scheme_id * 100
            are_info = parse_are_audio(game.read(au, 'are'))

            bcs_text = ''
            if scr_dir:
                bcs_path = os.path.join(scr_dir, f'ie_bcs_{au.lower()}_area.py')
                if os.path.isfile(bcs_path):
                    with open(bcs_path, 'r', encoding='cp1252', errors='replace') as f:
                        bcs_text = f.read()

            day_mus, night_mus, battle_mus = resolve_area_music(au, are_info, songlist, music_dir, bcs_text)
            day_mp3 = convert_mus_track(music_dir, day_mus, out_music_dir, ffmpeg_bin, tmp_dir, mus_cache) if day_mus else None
            night_mp3 = convert_mus_track(music_dir, night_mus, out_music_dir, ffmpeg_bin, tmp_dir, mus_cache) if night_mus else None
            battle_mp3 = convert_mus_track(music_dir, battle_mus, out_music_dir, ffmpeg_bin, tmp_dir, mus_cache) if battle_mus else None

            amb_mp3_map = {}
            for amb in are_info['ambients']:
                for s_res in amb['sounds']:
                    low = s_res.lower()
                    if low not in amb_mp3_map:
                        mp3 = convert_ambient_wav(game, s_res, out_amb_dir, ffmpeg_bin, tmp_dir, amb_cache)
                        if mp3:
                            amb_mp3_map[low] = mp3

            slines = build_scheme_lines(are_info, day_mp3, night_mp3, battle_mp3, amb_mp3_map)
            idx_add.append(f'{{{scheme_id}}}{{IE {au} #{base_line}}}')
            lst_add.append(f'// {au} (scheme {scheme_id})')
            for k, sl in enumerate(slines):
                lst_add.append(f'{{{base_line + k}}}{{{sl}}}')

            if map_dir:
                if not os.path.isabs(map_dir):
                    map_dir = os.path.join(out_dir, 'modules', module, 'maps', map_dir)
                update_mapinfo_soundscheme(os.path.join(map_dir, 'mapinfo.txt'), scheme_id, 0)

            report['areas'][au] = {
                'scheme_id': scheme_id,
                'day_music': day_mp3,
                'night_music': night_mp3,
                'battle_music': battle_mp3,
                'ambient_count': len(amb_mp3_map),
                'scheme_entries': len(slines),
            }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    with open(os.path.join(sound_root, 'schemeindex.mes'), 'w', encoding='latin-1', newline='\r\n') as f:
        f.write(idx_text.rstrip() + '\n' + '\n'.join(idx_add) + '\n')
    with open(os.path.join(sound_root, 'schemelist.mes'), 'w', encoding='latin-1', newline='\r\n') as f:
        f.write(lst_text.rstrip() + '\n' + '\n'.join(lst_add) + '\n')

    report['music_files'] = len(mus_cache)
    report['ambient_files'] = len(amb_cache)
    return report


def main():
    ap = argparse.ArgumentParser(description='Convert IE music and area ambients into ToEE sound schemes.')
    ap.add_argument('ie_dir', help='Path to IE game installation')
    ap.add_argument('toee_dir', help='Path to base ToEE installation')
    ap.add_argument('out_dir', help='Output directory')
    ap.add_argument('--module', default='ToEE', help='Target module directory name (default: ToEE)')
    ap.add_argument('--scheme-base', type=int, default=70, help='First soundscheme ID to allocate (default: 70)')
    ap.add_argument('--scr-dir', help='Optional converted scr/ directory to inspect area BCS SetMusic calls')
    ap.add_argument('--area', action='append', default=[], help='AREA[:MAP_DIR_NAME] (e.g. AR1000 or AR1000:I2AR1000)')
    a = ap.parse_args()
    area_maps = []
    for spec in a.area:
        if ':' in spec:
            ar, mdir = spec.split(':', 1)
        else:
            ar, mdir = spec, spec
        area_maps.append((ar.upper(), mdir))
    rep = convert(a.ie_dir, a.toee_dir, a.out_dir, area_maps, module=a.module, scheme_base=a.scheme_base, scr_dir=a.scr_dir)
    print(f"Converted {rep['music_files']} music tracks and {rep['ambient_files']} ambient sounds across {len(rep['areas'])} areas.")


if __name__ == '__main__':
    main()

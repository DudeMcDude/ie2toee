"""Unit tests for on-the-fly IE music and area ambient soundscheme conversion (no game data)."""
import os
import shutil
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import ie_music


def _fake_are(outdoor=True, songs=(3, -1, -1, -1, -1), ambients=(), v91=False):
    """Build a minimal ARE V1.0 or V9.1 binary with a song block and ambient table."""
    sig = b'AREAV9.1' if v91 else b'AREAV1.0'
    s = 0x10 if v91 else 0
    hdr_end = 0xd0 + s
    song_off = hdr_end
    amb_off = song_off + 144
    buf = bytearray(amb_off + len(ambients) * 0xd4)
    buf[:8] = sig
    struct.pack_into('<H', buf, 0x48, 1 if outdoor else 0)
    struct.pack_into('<HI', buf, 0x82 + s, len(ambients), amb_off)
    struct.pack_into('<I', buf, 0xbc + s, song_off)
    s10 = list(songs) + [-1] * (10 - len(songs))
    struct.pack_into('<10i', buf, song_off, *s10)
    for i, amb in enumerate(ambients):
        ao = amb_off + i * 0xd4
        name = amb.get('name', f'amb{i}').encode('latin-1')[:31]
        buf[ao:ao + len(name)] = name
        struct.pack_into('<H', buf, ao + 0x2e, amb.get('volume', 80))
        snds = amb.get('sounds', [])
        for k, sr in enumerate(snds[:10]):
            b8 = sr.encode('latin-1')[:8]
            buf[ao + 0x30 + k * 8:ao + 0x30 + k * 8 + len(b8)] = b8
        struct.pack_into('<H', buf, ao + 0x80, len(snds))
        struct.pack_into('<IIII', buf, ao + 0x84,
                         amb.get('interval', 0), 0,
                         amb.get('schedule', 0xffffff),
                         amb.get('flags', 0x7))
    return bytes(buf)


class MusicConverterTests(unittest.TestCase):
    def test_parse_mus_filters_spacers_and_stops_at_loop(self):
        mus = (
            "MX1000\n"
            "6\n"
            "SPC1\n"
            "A   @TAG end\n"
            "SPC1\n"
            "MX0000A\n"
            "B1  @TAG ENDB1\n"
            "Loop MX1000 A\n"
        )
        prefix, stems = ie_music.parse_mus(mus)
        self.assertEqual(prefix, 'MX1000')
        self.assertEqual(stems, ['A', 'B1'])

    def test_parse_are_audio_and_build_scheme_lines(self):
        raw = _fake_are(
            outdoor=True,
            songs=(6, 6, -1, 0, -1),
            ambients=[
                {'name': 'Day loop', 'sounds': ['AM1000'], 'volume': 85, 'interval': 0, 'schedule': 0x01ffe0, 'flags': 0x7},
                {'name': 'Night loop', 'sounds': ['AM1000_N'], 'volume': 85, 'interval': 0, 'schedule': 0xfe001f, 'flags': 0x7},
                {'name': 'Local pier', 'sounds': ['PIER1'], 'volume': 90, 'interval': 0, 'schedule': 0xffffff, 'flags': 0x3},
                {'name': 'Crows', 'sounds': ['CROW1', 'CROW2'], 'volume': 65, 'interval': 15, 'schedule': 0x01ffe0, 'flags': 0xd},
            ],
            v91=True,
        )
        info = ie_music.parse_are_audio(raw)
        self.assertTrue(info['outdoor'])
        self.assertEqual(info['day_song'], 6)
        # Local pier (flags=0x3, non-global) is excluded on outdoor maps
        self.assertEqual([a['name'] for a in info['ambients']], ['Day loop', 'Night loop', 'Crows'])

        amb_map = {
            'am1000': 'ie_am1000.mp3',
            'am1000_n': 'ie_am1000_n.mp3',
            'crow1': 'ie_crow1.mp3',
            'crow2': 'ie_crow2.mp3',
        }
        lines = ie_music.build_scheme_lines(info, 'ie_mx1000.mp3', 'ie_mx1000.mp3', 'ie_b1.mp3', amb_map)
        self.assertIn(r'music\ie_mx1000.mp3 /VOL:50 /loop', lines)
        self.assertIn(r'music\ie_b1.mp3 /VOL:50 /combatmusic', lines)
        self.assertIn(r'ambient\ie_am1000.mp3 /VOL:38 /loop /time:6-17', lines)
        # Night schedule splits into 18-23 and 0-5 for ToEE non-wrapping time ranges
        self.assertIn(r'ambient\ie_am1000_n.mp3 /VOL:38 /loop /time:18-23', lines)
        self.assertIn(r'ambient\ie_am1000_n.mp3 /VOL:38 /loop /time:0-5', lines)
        self.assertIn(r'ambient\ie_crow1.mp3 /scatter /freq:7 /VOL:26 /time:6-17', lines)
        self.assertIn(r'ambient\ie_crow2.mp3 /scatter /freq:7 /VOL:26 /time:6-17', lines)

    def test_startup_and_module_catalogs_keep_their_own_base_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'ie/music').mkdir(parents=True)
            for location, name in [('data', 'Startup'), ('modules/ToEE', 'Module')]:
                sound = root / 'base' / location / 'sound'
                sound.mkdir(parents=True)
                (sound / 'schemeindex.mes').write_text('{231}{' + name + ' #23100}\n')
                (sound / 'schemelist.mes').write_text('{23100}{' + name + '.mp3}\n')
            with patch.object(ie_music.iefs, 'IEGame') as game, patch.object(ie_music, 'parse_songlist', return_value={}):
                game.return_value.read.return_value = _fake_are()
                ie_music.convert(str(root / 'ie'), str(root / 'base'), str(root / 'out'), [('AR1000', 'AR1000')])
            for location, name in [('data', 'Startup'), ('modules/ToEE', 'Module')]:
                sound = root / 'out' / location / 'sound'
                index = (sound / 'schemeindex.mes').read_text()
                self.assertIn('{70}{IE AR1000 #7000}', index)
                self.assertIn('{231}{' + name + ' #23100}', index)
                self.assertIn('{23100}{' + name + '.mp3}', (sound / 'schemelist.mes').read_text())

    def test_update_mapinfo_soundscheme_is_idempotent(self):
        tmp = tempfile.mkdtemp(prefix='test_mapinfo_')
        try:
            p = os.path.join(tmp, 'mapinfo.txt')
            with open(p, 'w') as f:
                f.write('LightScheme: 1\nSoundScheme: 20,28\n')
            ie_music.update_mapinfo_soundscheme(p, 70, 0)
            ie_music.update_mapinfo_soundscheme(p, 75, 0)
            with open(p, 'r') as f:
                lines = f.read().splitlines()
            self.assertEqual(lines, ['LightScheme: 1', 'SoundScheme: 75,0'])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_resolve_area_music_iwd2_blank_song_falls_back_to_area_mus(self):
        tmp = tempfile.mkdtemp(prefix='test_mus_dir_')
        try:
            for fn in ('MX2102.mus', 'BA3101.mus', 'b1.mus'):
                open(os.path.join(tmp, fn), 'w').write('')
            songlist = {0: ('NO_MUSIC', ''), 4: ('BLANK', 'MX0000.mus')}
            d2102, n2102, b2102 = ie_music.resolve_area_music(
                'AR2102', {'day_song': 4, 'night_song': 4, 'battle_song': 0}, songlist, tmp
            )
            self.assertEqual(os.path.basename(d2102), 'MX2102.mus')
            self.assertEqual(os.path.basename(n2102), 'MX2102.mus')
            self.assertEqual(os.path.basename(b2102), 'b1.mus')

            _, _, b3101 = ie_music.resolve_area_music(
                'AR3101', {'day_song': 4, 'night_song': 4, 'battle_song': 4}, songlist, tmp
            )
            self.assertEqual(os.path.basename(b3101), 'BA3101.mus')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()

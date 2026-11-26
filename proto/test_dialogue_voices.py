"""Unit tests for on-the-fly NPC dialogue voice conversion (no game data)."""
import os, shutil, struct, tempfile, unittest
import ie_dialogue, iescript as S


def _fake_tlk(entries):
    """Build a minimal TLK V1 binary from [(text, sound_resref), ...]."""
    blobs = [t.encode('cp1252') for t, _ in entries]
    stroff = 18 + len(entries) * 26
    hdr = bytearray(b'TLK V1  ' + struct.pack('<HII', 0, len(entries), stroff))
    off = 0
    for b, (_, snd) in zip(blobs, entries):
        flags = 7 if snd else 1
        s8 = snd.encode('latin-1')[:8].ljust(8, b'\0')
        hdr += struct.pack('<H8sIIII', flags, s8, 0, 0, off, len(b))
        off += len(b)
    return bytes(hdr) + b''.join(blobs)


def _fake_dlg(state_strrefs):
    """Build a minimal DLG V1.0 binary with 1 end-transition per state."""
    n = len(state_strrefs)
    soff = 52
    toff = soff + n * 16
    hdr = b'DLG V1.0' + struct.pack('<11I', n, soff, n, toff, 0, 0, 0, 0, 0, 0, 0)
    states = b''.join(struct.pack('<iIII', sr, i, 1, 0xffffffff) for i, sr in enumerate(state_strrefs))
    trans = b''.join(struct.pack('<5I8sI', 8, 0xffffffff, 0xffffffff, 0xffffffff, 0, b'\0' * 8, 0) for _ in range(n))
    return hdr + states + trans


class FakeGame(object):
    def __init__(self, dlgs, wavs):
        self.dlgs = dlgs
        self.wavs = {k.lower(): v for k, v in wavs.items()}

    def read(self, res, ext):
        if ext == 'dlg':
            return self.dlgs[res.lower()]
        if ext == 'wav':
            return self.wavs[res.lower()]
        raise KeyError((res, ext))


class DialogueVoiceTests(unittest.TestCase):
    def test_dlg_emits_speech_id_only_for_existing_wavs(self):
        tlk = S.Tlk(_fake_tlk([
            ('Voiced greeting.', 'TESTV01'),
            ('Silent follow-up.', ''),
            ('Missing audio ref.', 'MISSING1'),
        ]))
        dlg_bytes = _fake_dlg([0, 1, 2])
        game = FakeGame({'testdlg': dlg_bytes}, {'testv01': b'RIFF....WAVE'})
        ids = {'object': type('O', (), {'by_name': {}})()}
        dc = ie_dialogue.DlgConv(game, ids, S.StrrefText(tlk), 'tester', 'AR1000', None)
        lines, _, _, _ = dc.convert('testdlg')
        npc_lines = [l for l in lines if l.startswith('{') and '{1}' not in l]
        self.assertEqual(npc_lines[0], '{10}{Voiced greeting.}{Voiced greeting.}{}{10}{}{}')
        self.assertEqual(npc_lines[1], '{20}{Silent follow-up.}{Silent follow-up.}{}{}{}{}')
        self.assertEqual(npc_lines[2], '{30}{Missing audio ref.}{Missing audio ref.}{}{}{}{}')
        self.assertEqual(dc.voices, [(10, 'TESTV01')])

        # Also verify wrapped text callable (such as IWD2 --strip-directions lambda r, _t=_t: ...)
        _t = S.StrrefText(tlk)
        wrapped_text = lambda r, _t=_t: _t(r)
        dc2 = ie_dialogue.DlgConv(game, ids, wrapped_text, 'tester', 'AR1000', None)
        lines2, _, _, _ = dc2.convert('testdlg')
        self.assertEqual(dc2.voices, [(10, 'TESTV01')])
        self.assertIn('{10}{Voiced greeting.}{Voiced greeting.}{}{10}{}{}', lines2)

    def test_convert_voice_clips_caches_and_strips_wavc(self):
        tmp = tempfile.mkdtemp(prefix='test_vox_')
        try:
            game = FakeGame({}, {
                'clip_a': b'WAVC' + (b'\0' * 24) + b'ACM_PAYLOAD_BYTES',
            })
            calls = []
            fake_ff = os.path.join(tmp, 'fake_ffmpeg.cmd' if os.name == 'nt' else 'fake_ffmpeg.sh')
            # Use a tiny wrapper around convert_voice_clips by patching subprocess.check_call
            orig_cc = ie_dialogue.subprocess.check_call
            seen_inputs = []
            def mock_cc(cmd):
                src = cmd[cmd.index('-i') + 1]
                dst = cmd[-1]
                with open(src, 'rb') as f:
                    seen_inputs.append((os.path.basename(src), f.read()))
                with open(dst, 'wb') as f:
                    f.write(b'ID3_FAKE_MP3')
            ie_dialogue.subprocess.check_call = mock_cc
            try:
                cache = {}; warned = [False]
                speech_root = os.path.join(tmp, 'speech')
                n1 = ie_dialogue.convert_voice_clips(
                    game, speech_root, 1187, [(10, 'CLIP_A'), (20, 'CLIP_A')], cache, 'ffmpeg', tmp, warned)
                n2 = ie_dialogue.convert_voice_clips(
                    game, speech_root, 1160, [(10, 'CLIP_A')], cache, 'ffmpeg', tmp, warned)
                self.assertEqual(n1, 2)
                self.assertEqual(n2, 1)
                # ffmpeg should only be called once for CLIP_A; the other 2 copies come from cache
                self.assertEqual(len(seen_inputs), 1)
                self.assertEqual(seen_inputs[0], ('clip_a.acm', b'ACM_PAYLOAD_BYTES'))
                self.assertTrue(os.path.isfile(os.path.join(speech_root, '01187', 'v10_m.mp3')))
                self.assertTrue(os.path.isfile(os.path.join(speech_root, '01187', 'v20_m.mp3')))
                self.assertTrue(os.path.isfile(os.path.join(speech_root, '01160', 'v10_m.mp3')))
            finally:
                ie_dialogue.subprocess.check_call = orig_cc
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()

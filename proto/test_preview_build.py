"""Regression tests for rebuilding a preview into the same output directory."""
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

from ie_build import preview_build
import ie_movies


class PreviewBuildTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.out = Path(tmp.name)

    def test_rebuild(self):
        stale = ['work/cre/dialogue/py01187ie_hrothgar.py', 'work/movies/ie_movies_data.py',
                 'install/maps/old-sector.mob', 'install/scripts/old.py']
        with preview_build(self.out) as stage:
            for name in stale:
                path = stage / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
        note = self.out / 'notes.txt'
        note.touch()
        with preview_build(self.out) as stage:
            self.assertTrue(all((self.out / name).is_file() for name in stale))
            self.assertFalse(any((stage / name).exists() for name in stale))
            (stage / 'install/01187ie_hroth.dlg').touch()
        self.assertFalse(any((self.out / name).exists() for name in stale))
        self.assertTrue((self.out / 'install/01187ie_hroth.dlg').is_file())
        self.assertTrue(note.is_file())

    def test_failure_retry_and_legacy_output(self):
        (self.out / 'work').mkdir()
        legacy = self.out / 'work/old.txt'
        legacy.write_text('legacy')
        with self.assertRaises(RuntimeError):
            with preview_build(self.out) as stage:
                (stage / 'work/partial').touch()
                raise RuntimeError('conversion failed')
        self.assertEqual(legacy.read_text(), 'legacy')
        with preview_build(self.out) as stage:
            self.assertFalse((stage / 'work/partial').exists())
            with self.assertRaises(SystemExit):
                with preview_build(self.out):
                    self.fail('a second writer acquired the same output folder')
        self.assertEqual(next(self.out.glob('previous-output-*/work.previous/old.txt')).read_text(), 'legacy')

    def test_failed_publication_restores_both_directories(self):
        with preview_build(self.out) as stage:
            for name in ('work', 'install'):
                (stage / name / 'original').touch()
        rename = Path.rename
        def fail_last_move(path, dest):
            if path == stage / 'install':
                raise PermissionError('install is locked')
            return rename(path, dest)
        with self.assertRaises(PermissionError):
            with patch.object(Path, 'rename', fail_last_move), preview_build(self.out) as stage:
                (stage / 'work/new').touch()
        self.assertFalse((self.out / 'work/new').exists())
        self.assertTrue(all((self.out / name / 'original').is_file() for name in ('work', 'install')))

    def test_source_inside_output_directory(self):
        source = self.out / 'work/game'
        source.mkdir(parents=True)
        with self.assertRaises(SystemExit):
            with preview_build(self.out, (source,)):
                self.fail('would overwrite an input directory')
        self.assertTrue(source.is_dir())

    def test_movie_reuse_only_copies_requested_movie_and_parts(self):
        cache = self.out / 'old/data/movies'
        cache.mkdir(parents=True)
        for name in ('IE-IWD-intro.bik', 'IE-IWD-intro-2.bik', 'IE-IWD-tower.bik', 'old.txt'):
            (cache / name).write_bytes(name.encode())
        new = self.out / 'new'
        with patch.dict(os.environ, {'IE_MOVIES_REUSE': '1'}), patch('iefs.IEGame'), patch('toeedata.ToEEData') as td:
            td.return_value.read.return_value = b''
            ie_movies.convert(str(self.out), '', str(new), only=['intro'], flavour='IWD', reuse_from=self.out / 'old')
        files = {p.name for p in (new / 'data/movies').iterdir()}
        self.assertEqual(files, {'IE-IWD-intro.bik', 'IE-IWD-intro-2.bik'})
        self.assertIn('IE-IWD-intro-2.bik', (new / 'modules/ToEE/movies/movies.mes').read_text())


if __name__ == '__main__':
    unittest.main()

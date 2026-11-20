import json
import tempfile
import unittest
from pathlib import Path

from ie_container_art import container_art, write_container_art


class ContainerArtTest(unittest.TestCase):
    def setUp(self):
        self.heap = dict(name='Goblin Arrows', type=4, toee=[10, 20], items=[('arrows', 13)])

    def test_heap_limit_counts_item_stacks(self):
        for count in (1, 2, 3):
            with self.subTest(count=count):
                result = container_art(dict(self.heap, items=self.heap['items'] * count), 'I2AR1000')
                self.assertEqual(result, {'pile': [10, 20]} if count <= 2 else None)

    def test_special_heaps_keep_their_interactions(self):
        for key in ('locked', 'key', 'trapped', 'script', 'flags'):
            with self.subTest(key=key):
                self.assertIsNone(container_art(dict(self.heap, **{key: 1}), 'I2AR1000'))
        spear = dict(self.heap, name='Soldier Spear', type=1)
        self.assertEqual(container_art(spear, 'I2AR1000'), {'pile': [10, 20]})
        self.assertIsNone(container_art(spear, 'AR1000'))

    def test_index_distinguishes_names_and_rebake_clears_stale_shapes(self):
        polygon = [[0, 0], [1, 0], [.5, .5], [1, 1], [0, 1]]
        chest = dict(name='Chest', type=2, locked=True, poly=polygon)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            metadata = path / 'container_art.json'
            def guid(i, name):
                return '%s-%s' % (i, name)
            write_container_art(path, [chest, dict(chest, poly=polygon[::-1])], guid)
            self.assertEqual(json.loads(metadata.read_text()), {
                '0-Chest': {'poly': polygon}, '1-Chest': {'poly': polygon[::-1]}})
            write_container_art(path, [dict(chest, poly=[])], guid)
            self.assertFalse(metadata.exists())


if __name__ == '__main__':
    unittest.main()

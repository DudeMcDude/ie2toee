import json
from pathlib import Path
import unittest

from ie_map_alerts import apply_map_alert_distances


class MapAlertsTest(unittest.TestCase):
    def test_remapped_cave_only_and_repeat(self):
        original = '{5100}{Cave, 10, 20, Area: 1}\r\n{5030}{Stock, 1, 2}\r\n'
        expected = original.replace('Area: 1}', 'Area: 1, AlertDistance: 10}')
        result = apply_map_alert_distances(original, {'AR1201': 5100}, {'AR1201': 10})
        self.assertEqual(result, expected)
        self.assertEqual(apply_map_alert_distances(result, {'AR1201': 5100}, {'AR1201': 10}), expected)
        self.assertIn('AlertDistance: 0}', apply_map_alert_distances(result, {'AR1201': 5100}, {'AR1201': 0}))

    def test_no_override_or_area(self):
        original = '{5030}{Stock, 1, 2}\n'
        self.assertEqual(apply_map_alert_distances(original, {'AR1000': 5030}, {}), original)
        self.assertEqual(apply_map_alert_distances(original, {}, {'AR1201': 10}), original)

    def test_bad_settings_and_missing_or_duplicate_entries(self):
        for value in [-1, 1001, True, 1.5, '10']:
            with self.assertRaises(ValueError):
                apply_map_alert_distances('', {}, {'AR1201': value})
        for text in ['', '{5030}{Cave, 1, 2}\n{5030}{Cave, 1, 2}\n']:
            with self.assertRaises(ValueError):
                apply_map_alert_distances(text, {'AR1201': 5030}, {'AR1201': 10})

    def test_guidance_is_scoped_to_cave_and_targos_outdoors(self):
        settings = json.loads((Path(__file__).parent / 'guidance/map_alerts.json').read_text())
        self.assertEqual(settings['IWD'], {'AR1201': 12})
        self.assertEqual(settings['IWD2'], {'AR1000': 18, 'AR1100': 18, 'AR1200': 18})


if __name__ == '__main__':
    unittest.main()

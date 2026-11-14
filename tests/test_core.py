import math
import tempfile
import unittest
from xml.etree import ElementTree
from passo.core import Tracker, calories, to_gpx
from passo.storage import Store


class TrackingTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.t = Tracker(monotonic=lambda: self.now, wall=lambda: 1700000000+self.now)
        self.t.start('walk', 70)

    def fix(self, lat=0, lon=0, elapsed=100, **kwargs):
        return self.t.location(lat, lon, kwargs.pop('accuracy', 5), elapsed, **kwargs)

    def test_corner_is_kept(self):
        self.assertTrue(self.fix())
        self.assertTrue(self.fix(lat=.000027, elapsed=101))
        self.assertTrue(self.fix(lat=.000027, lon=.000027, elapsed=102))
        self.assertEqual(len(self.t.snapshot()['points']), 3)
        self.assertAlmostEqual(self.t.snapshot()['distance'], 6, delta=.1)

    def test_short_walking_corner_is_preserved(self):
        self.assertTrue(self.fix())
        self.assertTrue(self.fix(lat=.000009, elapsed=101, speed=1))
        self.assertTrue(self.fix(lat=.000009, lon=.000009, elapsed=102, speed=1))
        self.assertEqual(len(self.t.snapshot()['points']), 3)
        self.assertAlmostEqual(self.t.snapshot()['distance'], 2, delta=.05)

    def test_cached_fix_before_start_or_resume_is_rejected(self):
        stamp = (1700000000+self.now)*1000
        self.assertFalse(self.fix(timestamp=stamp-1000))
        self.assertTrue(self.fix(timestamp=stamp))
        self.t.pause()
        self.now += 20
        self.t.resume()
        self.assertFalse(self.fix(elapsed=120, timestamp=stamp+19000))
        self.assertTrue(self.fix(elapsed=121, timestamp=stamp+20000))

    def test_stationary_good_signal_does_not_create_a_false_gap(self):
        self.fix()
        for n in range(1, 12):
            self.assertFalse(self.fix(elapsed=100+n, speed=0))
        self.assertEqual(self.t.snapshot()['lastSignal'], 1700000100000)
        self.assertTrue(self.fix(lat=.000027, elapsed=112, speed=1.4))
        points = self.t.snapshot()['points']
        self.assertEqual(points[0]['seg'], points[1]['seg'])

    def test_gap_does_not_add_shortcut_distance(self):
        self.fix()
        self.fix(lat=.01, elapsed=110)
        a = self.t.snapshot()
        self.assertEqual(a['distance'], 0)
        self.assertNotEqual(a['points'][0]['seg'], a['points'][1]['seg'])

    def test_bad_and_stale_fixes_rejected(self):
        for args in [dict(accuracy=35), dict(age=7), dict(age=-1), dict(lat=91), dict(lon=181), dict(lat=math.nan)]:
            self.assertFalse(self.fix(**args))
        self.assertEqual(self.t.snapshot()['points'], [])

    def test_teleport_and_duplicate_time_rejected(self):
        self.fix()
        self.assertFalse(self.fix(lat=.01, elapsed=101))
        self.assertFalse(self.fix(lat=.000027, elapsed=100))
        self.assertEqual(len(self.t.snapshot()['points']), 1)

    def test_stationary_drift_rejected(self):
        self.fix(accuracy=10)
        self.assertFalse(self.fix(lat=.000027, elapsed=102, accuracy=10, speed=0))

    def test_pause_excludes_time_and_breaks_route(self):
        self.fix()
        self.now += 10
        self.t.pause()
        self.now += 50
        self.assertEqual(self.t.snapshot()['duration'], 10000)
        self.assertFalse(self.fix(lat=.01, elapsed=160))
        self.t.resume()
        self.fix(lat=.01, elapsed=161)
        a = self.t.finish()
        self.assertEqual(a['duration'], 10000)
        self.assertEqual(a['distance'], 0)
        self.assertNotEqual(a['points'][0]['seg'], a['points'][1]['seg'])
        self.assertFalse(self.t.snapshot())

    def test_recovery_does_not_count_offline_time(self):
        self.now += 10
        recovered = Tracker(self.t.snapshot(), monotonic=lambda: 500)
        self.assertEqual(recovered.snapshot()['duration'], 10000)
        self.assertEqual(recovered.snapshot()['status'], 'interrupted')
        recovered.resume()
        self.assertEqual(recovered.snapshot()['duration'], 10000)

    def test_calories(self):
        self.assertAlmostEqual(calories('walk', 70, 60000), 4.655)
        self.assertGreater(calories('run', 70, 60000), calories('walk', 70, 60000))

    def test_invalid_setup(self):
        for mode, weight in [('bike', 70), ('walk', math.nan), ('walk', 0)]:
            with self.assertRaises(ValueError):
                Tracker().start(mode, weight)

    def test_export_preserves_gaps(self):
        self.fix()
        self.fix(lat=.01, elapsed=110)
        root = ElementTree.fromstring(to_gpx(self.t.snapshot()))
        ns = {'g': 'http://www.topografix.com/GPX/1/1'}
        self.assertEqual(len(root.findall('.//g:trkseg', ns)), 2)
        self.assertEqual(len(root.findall('.//g:trkpt', ns)), 2)
        with self.assertRaises(ValueError):
            to_gpx({'points': []})


class StorageTests(unittest.TestCase):
    def test_service_and_ui_connections(self):
        with tempfile.TemporaryDirectory() as folder:
            ui, service = Store(folder), Store(folder)
            ui.command('start', mode='walk', weight=70)
            ui.command('pause')
            self.assertEqual([c['action'] for c in service.commands()], ['start', 'pause'])
            self.assertEqual(service.commands(), [])
            service.checkpoint({'id': 'one'})
            self.assertEqual(ui.get('active')['id'], 'one')
            service.archive({'id': 'one', 'date': 1})
            self.assertEqual(ui.get('active'), {})
            self.assertEqual(len(ui.history()), 1)
            ui.delete('one')
            self.assertEqual(service.history(), [])


if __name__ == '__main__':
    unittest.main()

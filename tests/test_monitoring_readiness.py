"""Une API prête ne prouve pas que Prometheus a collecté son état métier prêt."""
import sys
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'observability/tests'))
import stale


class MonitoringReadinessTests(unittest.TestCase):
    def setUp(self):
        self.elapsed = 0
        self.record = {}
        self.status = Mock(return_value={'ready': True, 'stale': False,
                                        'updatedUtc': '2026-10-27T18:01:51Z'})

    def sleep(self, seconds):
        self.elapsed += seconds

    def wait(self, query, timeout=4):
        with patch.object(stale.time, 'monotonic', side_effect=lambda: self.elapsed), \
                patch.object(stale.time, 'sleep', side_effect=self.sleep), \
                patch.object(stale.b, 'utc', return_value='2026-10-27T18:01:52Z'):
            stale.wait_for_nominal(self.status, query, self.record, timeout)

    def sample(self, value):
        return [{'metric': {'job': 'bridge', 'instance': 'relayer:8080'},
                 'value': [1793124112 + self.elapsed, str(value)]}]

    def test_api_ready_waits_for_prometheus_business_ready(self):
        def query(expr):
            return self.sample(0 if expr == 'bridge_ready' and self.elapsed == 0 else 1)

        self.wait(query)
        self.assertTrue(self.record['passed'])
        self.assertEqual(self.status.call_count, 2)
        self.assertEqual(self.elapsed, 2)
        self.assertEqual([o['prometheus']['bridge_ready']['value'] for o in self.record['observations']], [0, 1])
        self.assertTrue(all(o['status_ready'] for o in self.record['observations']))
        self.assertEqual(self.record['observations'][0]['status_updated_utc'], '2026-10-27T18:01:51Z')
        self.assertEqual(self.record['observations'][1]['prometheus']['bridge_ready']['evaluation_timestamp_unix_seconds'], 1793124114)
        self.assertIn('pas celle du scrape', self.record['timestamp_semantics'])

    def test_permanently_unready_scrape_times_out_with_observations(self):
        def query(expr):
            return self.sample(0 if expr == 'bridge_ready' else 1)

        with self.assertRaises(TimeoutError):
            self.wait(query)
        self.assertFalse(self.record['passed'])
        self.assertEqual(self.elapsed, 4)
        self.assertEqual(len(self.record['observations']), 2)
        self.assertTrue(all(o['prometheus']['bridge_ready']['value'] == 0 for o in self.record['observations']))
        self.assertIn('ended_utc', self.record)

    def test_missing_metric_is_not_a_success_and_can_arrive_later(self):
        def query(expr):
            return [] if expr == 'bridge_ready' and self.elapsed == 0 else self.sample(1)

        self.wait(query)
        self.assertTrue(self.record['passed'])
        self.assertEqual(self.elapsed, 2)
        self.assertEqual(self.record['observations'][0]['prometheus']['bridge_ready'],
                         {'value': None, 'evaluation_timestamp_unix_seconds': None})

    def test_ambiguous_metric_is_not_retried_or_masked(self):
        def query(expr):
            return self.sample(1) * (2 if expr == 'bridge_ready' else 1)

        with self.assertRaisesRegex(AssertionError, 'Série ambiguë : bridge_ready'):
            self.wait(query)
        self.assertFalse(self.record['passed'])
        self.assertEqual(self.elapsed, 0)
        self.assertEqual(self.status.call_count, 1)


if __name__ == '__main__':
    unittest.main()

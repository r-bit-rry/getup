import json, os, tempfile, unittest
from tools.getup import manifest, write

class IndexTest(unittest.TestCase):
    def test_the_index_carries_counts_statuses_and_the_two_truths(self):
        counts = {'2026-10-22': 2, '2026-10-23': 1}
        idx = manifest.build_index(generated_at='2026-10-21T04:15:00Z', counts=counts,
                                   coverage={'checked': 3, 'missed': []},
                                   sources={'leaan': {'status': 'partial', 'count': 3, 'failures': ['leaan: https://x: 503']}},
                                   dropped_no_venue=4, unpinned=2)
        self.assertEqual([(d['date'], d['count']) for d in idx['dates']], list(counts.items()))
        self.assertEqual(idx['sources']['leaan']['status'], 'partial')
        self.assertEqual((idx['dropped_no_venue'], idx['unpinned']), (4, 2))

    def test_only_day_files_are_counted_and_a_second_write_is_quiet(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(f'{root}/data')
            write.write_json(write.date_file(root, '2026-10-22'), [{'id': 'a'}])
            write.write_json(write.labels_file(root), {'x': {}})
            self.assertEqual(manifest.day_counts(root), {'2026-10-22': 1})
            idx = manifest.build_index(generated_at='2026-10-21T04:15:00Z', counts={'2026-10-22': 1},
                                       coverage={}, sources={}, dropped_no_venue=0, unpinned=0)
            self.assertTrue(manifest.write_index(root, idx))
            self.assertFalse(manifest.write_index(root, idx))
            self.assertEqual([d['date'] for d in idx['dates']], ['2026-10-22'])

    def test_an_unreadable_day_is_omitted_not_counted_as_zero(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(f'{root}/data')
            write.write_json(write.date_file(root, '2026-10-22'), [])
            open(write.date_file(root, '2026-10-23'), 'w').write('{not json')
            with self.assertLogs('getup', level='WARNING') as logs:
                self.assertEqual(manifest.day_counts(root), {'2026-10-22': 0})
            self.assertIn('2026-10-23', logs.output[0])

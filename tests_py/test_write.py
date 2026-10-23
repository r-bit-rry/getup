import json, os, tempfile, unittest
from tools.getup import write

class CanonicalTest(unittest.TestCase):
    def test_key_order_does_not_change_the_bytes(self):
        a = write.dumps({'start': 1, 'title': 'ערב ג׳אז'})
        b = write.dumps({'title': 'ערב ג׳אז', 'start': 1})
        self.assertEqual(a, b)
        self.assertEqual(a, '{\n "start": 1,\n "title": "ערב ג׳אז"\n}\n')
        self.assertNotIn('\\u', a)  # Hebrew stays Hebrew

    def test_a_second_identical_write_reports_no_change(self):
        with tempfile.TemporaryDirectory() as root:
            path = write.date_file(root, '2026-10-23')
            self.assertTrue(write.write_json(path, [{'id': 'x'}]))
            self.assertFalse(write.write_json(path, [{'id': 'x'}]))
            self.assertEqual(json.loads(open(path, encoding='utf-8').read()), [{'id': 'x'}])

    def test_internal_source_categories_never_reach_the_bytes(self):
        with tempfile.TemporaryDirectory() as root:
            write.write_days(root, {'2026-10-20': [{'id': 'x', 'tags': ['בידור וסטנדאפ']}]})
            self.assertNotIn('tags', open(write.date_file(root, '2026-10-20'), encoding='utf-8').read())

    def test_data_files_sees_day_files_and_nothing_else(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(f'{root}/data')
            write.write_json(write.date_file(root, '2026-10-20'), [])
            write.write_json(write.index_file(root), {})
            write.write_json(write.labels_file(root), {})
            self.assertEqual(write.data_files(f'{root}/data'), ['2026-10-20'])

    def test_pruning_removes_only_future_days_that_are_no_longer_served(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, 'data'))
            for day in ('2026-10-20', '2026-10-23', '2026-11-30'):
                write.write_json(write.date_file(root, day), [])
            write.write_json(write.index_file(root), {'dates': []})
            removed = write.prune_future(root, {'2026-10-23'}, '2026-10-21')
            self.assertEqual(removed, ['2026-11-30'])          # not the past day
            self.assertTrue(os.path.exists(write.date_file(root, '2026-10-20')))
            self.assertTrue(os.path.exists(write.index_file(root)))  # never a date file

    def test_the_strict_reader_raises_where_the_lenient_one_defaults(self):
        with tempfile.TemporaryDirectory() as root:
            good = write.date_file(root, '2026-10-20')
            write.write_json(good, [])
            self.assertEqual(write.read_json(good, 'default'), [])
            open(good, 'w').write('{not json')
            self.assertEqual(write.read_json(good, 'default'), 'default')
            with self.assertRaises(ValueError):
                write.read_json_strict(good)

class ClockTest(unittest.TestCase):
    def test_generated_at_is_utc_rfc3339(self):
        self.assertRegex(write.utc_now(), r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$')

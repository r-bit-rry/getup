import json, os, tempfile, unittest
from datetime import date, timedelta
from tools.getup import archive, write

TODAY = '2026-10-21'
def days_ago(n):
    return (date.fromisoformat(TODAY) - timedelta(days=n)).isoformat()

class CodecTest(unittest.TestCase):
    def test_the_codec_available_here_round_trips(self):
        name, suffix, _, _ = archive.codec()
        self.assertIn(name, ('zstd', 'lzma'))
        self.assertIn(suffix, ('.zst', '.xz'))
        self.assertEqual(archive.decompress(archive.compress('שלום'.encode())), 'שלום'.encode())

class RollTest(unittest.TestCase):
    def test_days_older_than_ninety_roll_and_the_ninety_day_old_one_stays(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(f'{root}/data')
            old1, old2, edge = days_ago(91), days_ago(92), days_ago(90)
            write.write_json(write.date_file(root, old1), [{'id': 'old1'}])
            write.write_json(write.date_file(root, old2), [{'id': 'old2'}])
            write.write_json(write.date_file(root, edge), [{'id': 'edge'}])
            self.assertEqual(archive.roll(root, TODAY), sorted([old1, old2]))
            path = archive.month_file(root, old1[:7])
            self.assertEqual(sorted(json.loads(archive.decompress(open(path, 'rb').read()))), sorted([old1, old2]))
            self.assertFalse(os.path.exists(write.date_file(root, old2)))
            self.assertTrue(os.path.exists(write.date_file(root, edge)))

    def test_a_second_roll_merges_instead_of_overwriting(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(f'{root}/data')
            a, b = days_ago(91), days_ago(92)
            write.write_json(write.date_file(root, a), [{'id': 'a'}])
            archive.roll(root, TODAY)
            write.write_json(write.date_file(root, b), [{'id': 'b'}])
            archive.roll(root, TODAY)
            got = json.loads(archive.decompress(open(archive.month_file(root, b[:7]), 'rb').read()))
            self.assertEqual(sorted(got), sorted([a, b]))
            self.assertEqual(archive.archive_months(root), [b[:7]])

    def test_a_corrupt_day_file_warns_is_left_alone_and_is_never_archived(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(f'{root}/data')
            corrupt = days_ago(91)
            open(write.date_file(root, corrupt), 'w').write('{not json')
            with self.assertLogs('getup', level='WARNING') as logs:
                self.assertEqual(archive.roll(root, TODAY), [])
            self.assertIn(corrupt, logs.output[0])
            self.assertTrue(os.path.exists(write.date_file(root, corrupt)))

import json, lzma, os, tempfile, unittest, zlib
from datetime import date, timedelta
from unittest import mock
from tools.getup import archive, write

TODAY = '2026-10-21'
def days_ago(n):
    return (date.fromisoformat(TODAY) - timedelta(days=n)).isoformat()

def zstd_stand_in():
    """A 3.14 box's codec, faked with zlib: different bytes, so the suffix must be honoured."""
    return 'zstd', '.zst', zlib.compress, zlib.decompress

def lzma_labelled_zst():
    """For reading a .zst member on a box that has no zstd at all."""
    return 'zstd', '.zst', lzma.compress, lzma.decompress

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

    def test_a_corrupt_month_member_warns_and_leaves_its_days_alone(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(f'{root}/data')
            os.makedirs(f'{root}/archive')
            day = days_ago(91)
            write.write_json(write.date_file(root, day), [{'id': 'kept'}])
            member = f'{root}/archive/{day[:7]}.json{archive.suffix()}'
            open(member, 'wb').write(b'not a codec stream')
            with self.assertLogs('getup', level='WARNING') as logs:
                self.assertEqual(archive.roll(root, TODAY), [])
            self.assertIn(day[:7], logs.output[0])
            self.assertEqual(open(member, 'rb').read(), b'not a codec stream')
            self.assertTrue(os.path.exists(write.date_file(root, day)))

class CodecChangeTest(unittest.TestCase):
    def test_an_xz_member_is_read_as_xz_on_a_zstd_box(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(f'{root}/archive')
            member = f'{root}/archive/2026-07.json.xz'
            open(member, 'wb').write(lzma.compress(write.dumps({'2026-07-01': []}).encode()))
            with mock.patch.object(archive, '_zstd', zstd_stand_in):
                self.assertEqual(archive.suffix(), '.zst')
                self.assertEqual(archive.month_file(root, '2026-07'), member)
                got = json.loads(archive.decompress(open(member, 'rb').read(), '.xz'))
            self.assertEqual(got, {'2026-07-01': []})

    def test_a_roll_on_a_later_codec_does_not_split_the_month(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(f'{root}/data')
            a, b = days_ago(91), days_ago(92)
            write.write_json(write.date_file(root, a), [{'id': 'a'}])
            with mock.patch.object(archive, '_zstd', side_effect=ImportError):
                archive.roll(root, TODAY)
            write.write_json(write.date_file(root, b), [{'id': 'b'}])
            with mock.patch.object(archive, '_zstd', lzma_labelled_zst):
                self.assertEqual(archive.roll(root, TODAY), [b])
                self.assertEqual(archive.archive_months(root), [a[:7]])
                self.assertEqual(os.listdir(f'{root}/archive'), [f'{a[:7]}.json.xz'])
                got = json.loads(archive.decompress(open(archive.month_file(root, a[:7]), 'rb').read(),
                                                    '.xz'))
            self.assertEqual(sorted(got), sorted([a, b]))

    def test_a_month_split_across_both_suffixes_is_merged_into_one(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(f'{root}/data')
            os.makedirs(f'{root}/archive')
            a, b, c = days_ago(91), days_ago(92), days_ago(93)
            write.write_json(write.date_file(root, c), [{'id': 'c'}])
            open(f'{root}/archive/{a[:7]}.json.xz', 'wb').write(
                lzma.compress(write.dumps({a: [{'id': 'a'}]}).encode()))
            open(f'{root}/archive/{a[:7]}.json.zst', 'wb').write(
                lzma.compress(write.dumps({b: [{'id': 'b'}]}).encode()))
            with mock.patch.object(archive, '_zstd', lzma_labelled_zst):
                archive.roll(root, TODAY)
                self.assertEqual(archive.archive_months(root), [a[:7]])
                self.assertEqual(os.listdir(f'{root}/archive'), [f'{a[:7]}.json.zst'])
                got = json.loads(archive.decompress(open(archive.month_file(root, a[:7]), 'rb').read()))
            self.assertEqual(sorted(got), sorted([a, b, c]))

import json, os, shutil, tempfile, unittest
from tools.getup import cli

CAPTURE = 'docs/research/2026-10-21'
TODAY = '2026-10-21'

def fresh(root):
    shutil.copytree('venue', f'{root}/venue')
    shutil.copytree('data', f'{root}/data')

class CliTest(unittest.TestCase):
    def test_build_returns_zero_and_a_missing_tz_is_the_only_fatal_import(self):
        with tempfile.TemporaryDirectory() as root:
            fresh(root)
            self.assertEqual(cli.main(['build', '--root', root, '--today', TODAY,
                                       '--from-dir', CAPTURE, '--sources', 'leaan']), 0)

    def test_a_failed_source_exits_two_but_still_writes_what_it_has(self):
        with tempfile.TemporaryDirectory() as root:
            fresh(root)
            os.makedirs(f'{root}/empty')
            with open(f'{root}/empty/popit.xml', 'w') as f:
                f.write('<rss><channel></channel></rss>')
            code = cli.main(['build', '--root', root, '--today', TODAY,
                             '--from-dir', f'{root}/empty', '--sources', 'popit'])
            self.assertEqual(code, 2)
            with open(f'{root}/data/index.json', encoding='utf-8') as f:
                idx = json.load(f)
            self.assertEqual(idx['sources']['popit']['status'], 'failed')

    def test_pending_writes_a_batch_and_labels_merge_it(self):
        with tempfile.TemporaryDirectory() as root:
            fresh(root)
            self.assertEqual(cli.main(['pending', '--root', root, '--today', TODAY,
                                       '--from-dir', CAPTURE, '--sources', 'leaan']), 0)
            with open(f'{root}/build/labels.pending.jsonl', encoding='utf-8') as f:
                batch = [json.loads(line) for line in f]
            self.assertTrue(batch and all(set(p) >= {'key', 'title'} for p in batch))
            with open(f'{root}/build/labels.jsonl', 'w', encoding='utf-8') as f:
                f.write('\n'.join(json.dumps(
                    {'key': p['key'], 'format': 'tribute', 'scene': ['פופ'], 'crowd': []},
                    ensure_ascii=False) for p in batch))
            self.assertEqual(cli.main(['labels', '--root', root, '--labels',
                                       f'{root}/build/labels.jsonl']), 0)
            with open(f'{root}/data/labels.json', encoding='utf-8') as f:
                self.assertEqual(len(json.load(f)), len(batch))

    def test_pending_touches_no_day_file_and_no_registry(self):
        with tempfile.TemporaryDirectory() as root:
            fresh(root)
            with open(f'{root}/data/2026-10-22.json', 'rb') as f:
                day = f.read()
            with open(f'{root}/venue/venues.json', 'rb') as f:
                registry = f.read()
            self.assertEqual(cli.main(['pending', '--root', root, '--today', TODAY,
                                       '--from-dir', CAPTURE, '--sources', 'leaan']), 0)
            with open(f'{root}/data/2026-10-22.json', 'rb') as f:
                self.assertEqual(f.read(), day)
            with open(f'{root}/venue/venues.json', 'rb') as f:
                self.assertEqual(f.read(), registry)

    def test_an_unknown_subcommand_is_an_argument_error(self):
        self.assertEqual(cli.main(['nope']), 1)

    def test_coverage_and_archive_report_the_committed_state(self):
        with tempfile.TemporaryDirectory() as root:
            fresh(root)
            self.assertEqual(cli.main(['coverage', '--root', root, '--today', TODAY]), 0)
            self.assertEqual(cli.main(['archive', '--root', root, '--today', TODAY]), 0)

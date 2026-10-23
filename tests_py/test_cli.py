import contextlib, io, json, os, shutil, tempfile, unittest
from unittest import mock
from tools.getup import cli, github, human, intake, normalize, write
from tests_py.github_fake import Fake, issue
from tests_py.test_intake import fresh as intake_fresh
from tests_py.test_intake_parse import EVENT

CAPTURE = 'docs/research/2026-10-21'
TODAY = '2026-10-21'

def fresh(root):
    shutil.copytree('venue', f'{root}/venue')
    shutil.copytree('data', f'{root}/data')

class CliTest(unittest.TestCase):
    def test_build_returns_zero_and_writes_the_day_files(self):
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
            write.write_json(write.labels_file(root), {})   # the committed cache now covers this capture
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

    def test_a_missing_tz_is_exit_four_with_a_message(self):
        with tempfile.TemporaryDirectory() as root:
            fresh(root)
            saved = normalize.TZ
            normalize.TZ = None
            self.addCleanup(setattr, normalize, 'TZ', saved)
            with mock.patch.object(normalize, 'ZoneInfo', side_effect=RuntimeError('no tzdata')), \
                    contextlib.redirect_stderr(io.StringIO()) as err:
                code = cli.main(['build', '--root', root, '--today', TODAY,
                                 '--from-dir', CAPTURE, '--sources', 'leaan'])
            self.assertEqual(code, 4)
            self.assertIn('tz data', err.getvalue())
            self.assertIn('Asia/Jerusalem', err.getvalue())

    def test_bad_argument_values_exit_two_with_one_line(self):
        with tempfile.TemporaryDirectory() as root:
            fresh(root)
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(cli.main(['build', '--root', root, '--today', TODAY,
                                           '--from-dir', CAPTURE, '--sources', 'nope']), 2)
            self.assertEqual(len(err.getvalue().strip().splitlines()), 1)
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(cli.main(['coverage', '--root', root, '--today', '2026-13-01']), 2)
            self.assertIn('2026-13-01', err.getvalue())

    def test_coverage_exits_three_when_a_major_venue_is_missed(self):
        with tempfile.TemporaryDirectory() as root:
            write.write_json(f'{root}/venue/venues.json',
                             {'v_major': {'id': 'v_major', 'name': 'היכל', 'tier': 'major'}})
            self.assertEqual(cli.main(['coverage', '--root', root, '--today', TODAY]), 3)

    def test_pending_exits_nonzero_when_every_source_failed(self):
        with tempfile.TemporaryDirectory() as root:
            fresh(root)
            os.makedirs(f'{root}/empty')
            with open(f'{root}/empty/popit.xml', 'w') as f:
                f.write('<rss><channel></channel></rss>')
            self.assertEqual(cli.main(['pending', '--root', root, '--today', TODAY,
                                       '--from-dir', f'{root}/empty', '--sources', 'popit']), 2)

    def test_coverage_and_archive_report_the_committed_state(self):
        with tempfile.TemporaryDirectory() as root:
            fresh(root)
            self.assertEqual(cli.main(['coverage', '--root', root, '--today', TODAY]), 0)
            self.assertEqual(cli.main(['archive', '--root', root, '--today', TODAY]), 0)


class IntakeCliTest(unittest.TestCase):
    def test_a_polled_issue_is_written_by_the_command(self):
        with tempfile.TemporaryDirectory() as root:
            intake_fresh(root)
            write.write_json(human.store_file(root), {})
            client = Fake([issue(7, EVENT)])
            with mock.patch('tools.getup.intake.client_from_env', return_value=client):
                self.assertEqual(cli.main(['intake', '--root', root, '--today', TODAY]), 0)
            self.assertEqual(len(human.load(root)), 1)

    def test_a_failed_api_call_is_exit_five(self):
        with mock.patch('tools.getup.intake.client_from_env',
                        side_effect=github.GithubError(401, 'Bad credentials')):
            self.assertEqual(cli.main(['intake']), 5)

    def test_a_per_issue_failure_is_still_exit_zero(self):
        with tempfile.TemporaryDirectory() as root:
            intake_fresh(root)
            client = Fake([issue(7, EVENT), issue(8, EVENT.replace('2026-11-14', '2026-11-15'))])
            real = client.comment

            def broken(n, body):
                if n == 7:
                    raise github.GithubError(500, 'server error')
                real(n, body)

            client.comment = broken
            with mock.patch('tools.getup.intake.client_from_env', return_value=client):
                self.assertEqual(cli.main(['intake', '--root', root, '--today', TODAY]), 0)

    def test_a_corrupt_state_file_is_exit_five_before_any_poll(self):
        with tempfile.TemporaryDirectory() as root:
            intake_fresh(root)
            write.write_bytes(os.path.join(root, 'prefs.json'), b'{')
            client = Fake([issue(7, EVENT)])
            with mock.patch('tools.getup.intake.client_from_env', return_value=client) as made:
                self.assertEqual(cli.main(['intake', '--root', root, '--today', TODAY]), 5)
            self.assertEqual(made.call_count, 0)      # checked before the client is built
            self.assertEqual(client.ensured, 0)

    def test_a_corrupt_registry_or_human_store_is_exit_five_before_any_poll(self):
        for name in ('venue/venues.json', 'data/human.json'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as root:
                intake_fresh(root)
                write.write_bytes(os.path.join(root, name), b'{')
                client = Fake([issue(7, EVENT)])
                with mock.patch('tools.getup.intake.client_from_env', return_value=client) as made:
                    self.assertEqual(cli.main(['intake', '--root', root, '--today', TODAY]), 5)
                self.assertEqual(made.call_count, 0)
                self.assertEqual(client.ensured, 0)

    def test_an_unwritable_state_file_is_exit_five(self):
        from tests_py.test_intake_prefs import PREFS
        with tempfile.TemporaryDirectory() as root:
            intake_fresh(root)
            write.write_json(intake.prefs_file(root), {'never': [], 'always': []})
            client = Fake([issue(21, PREFS)])
            with mock.patch('tools.getup.intake.add_rule',
                            side_effect=OSError(30, 'Read-only file system')), \
                 mock.patch('tools.getup.intake.client_from_env', return_value=client):
                self.assertEqual(cli.main(['intake', '--root', root, '--today', TODAY]), 5)

    def test_a_missing_token_is_exit_five_and_never_network(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(cli.main(['intake']), 5)


if __name__ == '__main__':
    unittest.main()

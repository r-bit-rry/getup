import os, re, shutil, subprocess, tempfile, unittest

SCRIPT = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'daily.sh')
STAMP = re.compile(r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ daily: ')


def run(args, **env):
    clean = {k: v for k, v in os.environ.items() if not k.startswith('GETUP_')}
    clean.update(env)
    return subprocess.run(['sh', SCRIPT, *args], capture_output=True, text=True, env=clean)


def git(root, *args):
    return subprocess.run(['git', '-C', root, *args], capture_output=True, text=True)


class DailyScriptTest(unittest.TestCase):
    def test_help_exits_zero(self):
        done = run(['--help'])
        self.assertEqual(done.returncode, 0)
        self.assertIn('--dry-run', done.stdout)

    def test_missing_credentials_exits_five_and_touches_nothing(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(f'{root}/data')
            with open(f'{root}/prefs.json', 'w') as f:
                f.write('{}')
            before = sorted(os.listdir(root))
            log = f'{root}.log'
            done = run([], GETUP_ROOT=root, GETUP_LOG=log)
            self.assertEqual(done.returncode, 5)
            self.assertIn('GETUP_REPO', done.stderr)
            self.assertEqual(sorted(os.listdir(root)), before)
            self.assertFalse(os.path.exists(log))

    def test_dry_run_prints_only_allowed_paths_and_makes_no_commit(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as tools:
            os.makedirs(f'{root}/data')
            os.makedirs(f'{root}/venue')
            with open(f'{root}/prefs.json', 'w') as f:
                f.write('{}')
            with open(f'{root}/data/index.json', 'w') as f:
                f.write('{}')
            self.assertEqual(git(root, 'init', '-q').returncode, 0)
            subprocess.run(['git', '-C', root, 'config', 'user.email', 't@example.com'], check=True)
            subprocess.run(['git', '-C', root, 'config', 'user.name', 't'], check=True)
            subprocess.run(['git', '-C', root, 'add', 'data', 'venue', 'prefs.json'], check=True)
            subprocess.run(['git', '-C', root, 'commit', '-qm', 'base'], check=True)

            with open(f'{root}/data/2026-10-25.json', 'w') as f:
                f.write('{"date": "2026-10-25"}')
            with open(f'{root}/notes.txt', 'w') as f:
                f.write('outside the staged paths')
            stub = f'{tools}/python-stub'
            with open(stub, 'w') as f:
                f.write(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{tools}/calls"\nexit 0\n')
            os.chmod(stub, 0o755)

            done = run(['--dry-run'], GETUP_ROOT=root, GETUP_PYTHON=stub,
                       GETUP_REPO='owner/name', GETUP_GITHUB_TOKEN='token')

            self.assertEqual(done.returncode, 0, done.stderr)
            paths = [line for line in done.stdout.splitlines() if not STAMP.match(line)]
            self.assertEqual(paths, ['data/2026-10-25.json'])
            self.assertEqual(git(root, 'rev-list', '--count', 'HEAD').stdout.strip(), '1')
            self.assertEqual(git(root, 'diff', '--cached', '--quiet').returncode, 0)
            self.assertIn('notes.txt', git(root, 'status', '--porcelain').stdout)
            with open(f'{tools}/calls') as f:
                calls = f.read().splitlines()
            self.assertEqual([line.split()[2] for line in calls],
                             ['intake', 'build', 'coverage', 'archive'])

    def test_script_parses(self):
        done = subprocess.run(['sh', '-n', SCRIPT], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)

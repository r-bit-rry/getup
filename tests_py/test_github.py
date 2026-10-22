import json
import unittest

from tools.getup import github


def reply(status, payload, headers=None):
    return status, headers or {}, json.dumps(payload) if not isinstance(payload, str) else payload


def client(handler, token='tok'):
    seen = []

    def fetch(request):
        seen.append(request)
        return handler(request)

    return github.Client('roy/getup', token, fetch=fetch), seen


def issue(n, **o):
    return {'number': n, 'state': 'open', 'body': 'b', 'author_association': 'OWNER',
            'labels': [{'name': 'intake'}], **o}


class RequestTest(unittest.TestCase):
    def test_the_request_carries_the_token_the_version_and_the_repo_path(self):
        c, seen = client(lambda r: reply(200, []))
        c.issues()
        req = seen[0]
        self.assertEqual(req.get_method(), 'GET')
        self.assertEqual(req.full_url, 'https://api.github.com/repos/roy/getup/issues'
                                       '?state=open&labels=intake&per_page=100&page=1')
        self.assertEqual(req.get_header('Authorization'), 'Bearer tok')
        self.assertEqual(req.get_header('X-github-api-version'), '2022-11-28')

    def test_pull_requests_and_processed_issues_are_never_returned(self):
        rows = [issue(1), issue(2, pull_request={'url': 'x'}),
                issue(3, labels=[{'name': 'intake'}, {'name': 'processed'}])]
        c, _ = client(lambda r: reply(200, rows))
        self.assertEqual([i['number'] for i in c.issues()], [1])

    def test_a_full_page_asks_for_the_next_one(self):
        def handler(r):
            return reply(200, [issue(n) for n in range(100)] if r.full_url.endswith('page=1')
                         else [issue(101)])
        c, seen = client(handler)
        self.assertEqual(len(c.issues()), 101)
        self.assertTrue(seen[1].full_url.endswith('page=2'))


class ErrorTest(unittest.TestCase):
    def test_a_bad_token_is_a_github_error_with_its_status(self):
        c, _ = client(lambda r: reply(401, {'message': 'Bad credentials'}))
        with self.assertRaises(github.GithubError) as raised:
            c.issues()
        self.assertEqual((raised.exception.status, raised.exception.message),
                         (401, 'Bad credentials'))

    def test_a_missing_label_is_named_and_never_created(self):
        c, seen = client(lambda r: reply(200, [{'name': 'intake'}, {'name': 'processed'}]))
        with self.assertRaises(github.GithubError) as raised:
            c.ensure_labels()
        self.assertEqual(raised.exception.status, 0)
        self.assertIn('needs-info', raised.exception.message)
        self.assertIn('intake:prefs', raised.exception.message)
        self.assertTrue(all(r.get_method() == 'GET' for r in seen))   # no POST /labels

    def test_every_label_present_is_one_quiet_check(self):
        names = [{'name': n} for n in ('intake', 'processed', 'needs-info', 'intake:prefs')]
        c, seen = client(lambda r: reply(200, names))
        c.ensure_labels()
        self.assertEqual(len(seen), 1)

    def test_a_missing_token_or_repo_never_reaches_the_network(self):
        def boom(request):
            raise AssertionError(f'network call: {request.full_url}')

        with self.assertRaises(github.GithubError) as raised:
            github.client_from_env({'GETUP_REPO': 'roy/getup'}, fetch=boom)
        self.assertEqual(raised.exception.status, 0)
        self.assertIn('GETUP_GITHUB_TOKEN', raised.exception.message)
        with self.assertRaises(github.GithubError):
            github.client_from_env({'GETUP_GITHUB_TOKEN': 'tok'}, fetch=boom)


if __name__ == '__main__':
    unittest.main()

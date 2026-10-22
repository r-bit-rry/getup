"""The only HTTP in GetUp: auth headers, issues, comments and the label check.

The transport is injected (``fetch(request) -> (status, headers, body)``) so every test drives
a fake and no test can reach api.github.com.
"""

import http.client
import json
import os
import urllib.error
import urllib.request

VERSION = '2022-11-28'
PER_PAGE = 100


class GithubError(Exception):
    """An HTTP failure, or a local one: ``status`` 0 means no HTTP status (config or transport)."""

    def __init__(self, status: int, message: str):
        super().__init__(f'{status}: {message}' if status else message)
        self.status = status
        self.message = message


def _http(request):
    """The real transport: an HTTP error is a reply, not an exception, so the caller reads its status."""
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, dict(response.headers), response.read().decode('utf-8')
    except urllib.error.HTTPError as exc:
        body = exc.read().decode('utf-8', 'replace') if exc.fp else ''
        return exc.code, dict(exc.headers or {}), body


class Client:
    def __init__(self, repo: str, token: str, *, fetch=None, base: str = 'https://api.github.com'):
        self.repo = repo
        self.token = token
        self.base = base.rstrip('/')
        self._fetch = fetch or _http

    def _request(self, method: str, path: str, body=None):
        data = json.dumps(body).encode('utf-8') if body is not None else None
        request = urllib.request.Request(f'{self.base}{path}', data=data, method=method)
        request.add_header('Authorization', f'Bearer {self.token}')
        request.add_header('Accept', 'application/vnd.github+json')
        request.add_header('X-GitHub-Api-Version', VERSION)
        request.add_header('User-Agent', 'getup-intake/1.0')
        if data is not None:
            request.add_header('Content-Type', 'application/json')
        try:
            status, _, text = self._fetch(request)
        except (OSError, http.client.HTTPException) as exc:   # no reply: status 0, the caller exits 5
            raise GithubError(0, f'{method} {path}: {exc}') from exc
        if status >= 400:
            try:
                message = json.loads(text).get('message')
            except (ValueError, AttributeError):
                message = None
            raise GithubError(status, str(message or f'HTTP {status}'))
        if not text or not text.strip():
            return None
        try:
            return json.loads(text)
        except ValueError as exc:       # a 200 that is not JSON is a transport fault, not a payload
            raise GithubError(0, f'{method} {path}: reply is not JSON: {exc}') from exc

    def _pages(self, path: str, query: str = ''):
        page = 1
        while True:
            rows = self._request(
                'GET', f'{path}?{query}&per_page={PER_PAGE}&page={page}'.replace('?&', '?')) or []
            if not isinstance(rows, list):      # a payload of the wrong shape is a fault, not a row
                raise GithubError(0, f'GET {path}: reply is not a list')
            yield rows
            if len(rows) < PER_PAGE:
                return
            page += 1

    def issues(self) -> list[dict]:
        rows = []
        for page in self._pages(f'/repos/{self.repo}/issues', 'state=open&labels=intake'):
            rows.extend(page)
        return [row for row in rows
                if not row.get('pull_request')
                and 'processed' not in {str(label.get('name') or '').lower()
                                        for label in row.get('labels') or []}]

    def comments(self, number: int) -> list[dict]:
        rows = []
        for page in self._pages(f'/repos/{self.repo}/issues/{number}/comments'):
            rows.extend(page)
        return rows

    def comment(self, number: int, body: str) -> dict:
        return self._request('POST', f'/repos/{self.repo}/issues/{number}/comments',
                             {'body': body})

    def add_label(self, number: int, name: str) -> None:
        self._request('POST', f'/repos/{self.repo}/issues/{number}/labels', {'labels': [name]})

    def remove_label(self, number: int, name: str) -> None:
        try:
            self._request('DELETE', f'/repos/{self.repo}/issues/{number}/labels/{name}')
        except GithubError as exc:
            if exc.status != 404:                 # already gone is the state we wanted
                raise

    def ensure_labels(self, names=('intake', 'processed', 'needs-info', 'intake:prefs')) -> None:
        """Verify, never create: a missing label means a misconfigured repo, and the forms drop it silently."""
        present = set()
        for page in self._pages(f'/repos/{self.repo}/labels'):
            present.update(str(row.get('name') or '').lower() for row in page)
        missing = [name for name in names if name.lower() not in present]
        if missing:
            raise GithubError(0, 'missing labels: ' + ', '.join(missing))


def client_from_env(environ=None, fetch=None) -> Client:
    env = os.environ if environ is None else environ
    repo = str(env.get('GETUP_REPO') or '').strip()
    token = str(env.get('GETUP_GITHUB_TOKEN') or '').strip()
    if not repo:
        raise GithubError(0, 'GETUP_REPO is not set (owner/name)')
    if repo.count('/') != 1:
        raise GithubError(0, f'GETUP_REPO is not owner/name: {repo!r}')
    if not token:
        raise GithubError(0, 'GETUP_GITHUB_TOKEN is not set')
    return Client(repo, token, fetch=fetch)

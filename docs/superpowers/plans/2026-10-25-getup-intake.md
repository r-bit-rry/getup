# GetUp Intake and Ops Implementation Plan

**Status: executed** — intake + ops, in the same merged history `0506b55..d552d02`.
Final: **284** Python tests and **141** client tests, all passing. Task bodies below are
the plan as written, not a report.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn a GitHub issue into one canonical event record (or one preference rule, or one source request) exactly once, with the `author_association` guard, a receipt comment and the `processed`/`needs-info` labels; keep a human record authoritative over every scan; and surface failed sources and coverage misses as one quiet Hebrew footer line.
**Architecture:** Two thin stdlib modules — `github.py` owns HTTP and nothing else, `intake.py` owns the rules — over a committed `data/human.json` that `build.run` merges before dedup. `dedup.RANK` gains `human` above `ticketing`. The client gains one pure `opsLine(manifest)`; it never filters. `prefs.json` is still read in the browser; intake only writes the file.
**Tech Stack:** Python 3.12+ stdlib only (`urllib.request`, `json`, `html`, `zoneinfo`, `unittest`), vanilla ES modules, `node --test`. No pip, no GitHub Actions, no webhooks.
**Spec:** docs/superpowers/specs/2026-10-18-getup-design.md

## Global Constraints

- **Stdlib only in Python.** The single network import is `urllib.request` inside `tools/getup/github.py`. No dependency, no `requirements.txt`.
- **No network in tests.** `Client` takes an injectable `fetch(request) -> (status, headers, body)`; every intake test drives a fake client (`tests_py/github_fake.py`). The client test asserts the request object, never sends it.
- **Guard.** Only `author_association in {'OWNER', 'MEMBER'}` is processed. `COLLABORATOR`, `CONTRIBUTOR`, `FIRST_TIME_CONTRIBUTOR`, `NONE` are skipped with **zero** API writes — no receipt, no label. This is the only defence (ADR-0008).
- **Idempotency.** The `processed` label is the ledger; the receipt comment is the record. Both comment kinds carry a hidden HTML marker (`<!-- getup:record -->`, `<!-- getup:needs-info -->`); a re-run checks existing comments and never posts the same marker twice. `data/human.json` is keyed by issue number, so replaying an issue replaces that issue's entry and nothing else.
- **Never half-ingest.** The whole form is validated before any file is touched. A malformed issue produces one `needs-info` comment naming the exact fields and one label; `data/human.json`, `prefs.json` and `venue/venues.json` are byte-identical afterwards.
- **Human beats machine.** A record with `source.class == 'human'` wins the §7.4 merge against any machine record at the same venue within ±30 min and is never absorbed as `enrichment` into a machine row. `data/human.json` is committed data, not a state store: every build re-reads it (a day file alone would be overwritten by the next scan). Its values are **canonical drafts**, never finished records: venue resolution and `city/lat/lon/drive_min/coords_source` are copied from the registry by `build.place` on every run, exactly like a scanned draft.
- **The alarm never filters.** `index.json`'s `sources` and `coverage.missed` are rendered as text. No event is removed, reordered or hidden because a source failed.
- **`prefs.json` stays a browser preference.** Intake appends a rule and commits the file; `src/prefs.js` is unchanged and takes effect on reload.
- **Issue text is untrusted.** Values are length-capped or rejected; the receipt embeds the record inside `<pre>` with `html.escape`, so a title containing markup or backticks cannot break the comment.
- **Hebrew verbatim.** Every new user-facing string is Hebrew; field names in `needs-info` are the form labels, character for character.
- **Existing suites stay green.** 134 client tests, 205 Python tests. Final acceptance: `python3 -m unittest discover -s tests_py` and `node --test`.
- **`data/human.json` is not a day file.** It does not match `^\d{4}-\d{2}-\d{2}\.json$`, so `write.data_files`, `manifest.day_counts` and the client never see it. Nothing enumerates `data/` to find it; the store is opened by its exact path (`human.store_file`) and excluded from every day-file loop on purpose.

## Review Focus

The spec implies these and no happy path exercises them. Each has a test in the owning task.

1. **An issue by a non-member** — no comment, no label, no file, even when the body is a perfect event. (Task 4)
2. **An issue whose field is empty or invalid** — `_No response_`, a blank heading, `2026-02-30`, `25:00`, a past date, `javascript:`; the comment names each field and nothing is stored. (Tasks 2, 4)
3. **A duplicate issue for an event already ingested** — two issue numbers, one row, and the second receipt says it was merged into the existing event, never `נקלט`. (Tasks 4, 6)
4. **A human record colliding with a scan** — the human title and price survive a rebuild, the machine copy becomes `enrichment`, a second build does not duplicate the row, and a human draft at a venue provisioned after ingestion gains `drive_min` on the next build. (Task 6)
5. **A source that is `failed` in the index** — it is named in the footer and the list is untouched; the all-clear sentence is not printed over a failure. (Task 7)

---

## File Structure

| File | Responsibility |
|---|---|
| `.github/ISSUE_TEMPLATE/event.yml` | `אירוע חדש` form; `labels: ["intake"]`; fixed Hebrew labels the parser matches. |
| `.github/ISSUE_TEMPLATE/source.yml` | `מקור חדש` form; same label contract. |
| `.github/ISSUE_TEMPLATE/prefs.yml` | `העדפה` form; one `never`/`always` rule per issue; labels `intake`, `intake:prefs`. |
| `tools/getup/github.py` | The only HTTP: auth headers, issue list, comments, label existence check, `GithubError`, `client_from_env`. |
| `tools/getup/intake.py` | Form parsing, validation, record/prefs/source canonicalisation, the guard, the poll loop, receipts and labels; stores canonical drafts and re-exports `GithubError`/`client_from_env`. |
| `tools/getup/human.py` | `data/human.json`: strict load, byte-stable save, one canonical draft per issue number, deterministic order. |
| `tools/getup/normalize.py` | Modified: honour `draft['tickets']` / `draft['community']` and always keep the event link in `urls.source`. |
| `tools/getup/venues.py` | Modified: `find()` — alias lookup without provisioning, for prefs; `resolve()` delegates to it. |
| `tools/getup/dedup.py` | Modified: `RANK['human'] = 4`. |
| `tools/getup/build.py` | Modified: merge `human.json` drafts before placement, so every run places them, and never stamp `seen_last` for `human`. |
| `tools/getup/cli.py` | Modified: `intake` subcommand, exit codes `0`/`5`, startup state check and help text. |
| `data/human.json` | Committed store, starts as `{}`; issue number → canonical draft (never a finished record). |
| `src/format.js` | Modified: `opsLine(manifest)` — the single footer sentence. |
| `app.js` | Modified: footer writes `opsLine(manifest)` into `#coverage`. |
| `README.md` | The label bootstrap, the `prefs.json` schema, the three forms, the token env vars, the daily commands, the correction loop. |
| `tests_py/github_fake.py` | `Fake` client and `issue()` builder shared by the intake tests. |
| `tests_py/test_github.py` | Request shape, pagination, PR/processed filtering, HTTP errors, env. |
| `tests_py/test_intake_parse.py` | Form bodies → fields → draft/source record; form↔parser top-level field-id drift for all three forms. |
| `tests_py/test_human.py` | Store round-trip, corrupt store, deterministic order. |
| `tests_py/test_normalize.py` | Modified: human draft URLs; Leaan behaviour unchanged. |
| `tests_py/test_intake.py` | Guard, draft ingestion, source ingestion, merged/correction receipts, `needs-info`, corrupt state, replay. |
| `tests_py/test_intake_prefs.py` | Rule validation, `add_rule`, prefs dispatch, corrupt-prefs continuation, README pin. |
| `tests_py/test_dedup.py` | Modified: human rank and field preservation. |
| `tests_py/test_build.py` | Modified: human drafts survive scans, gain coordinates at build time, dedupe, and never stamp `seen_last`. |
| `tests_py/test_venues.py` | Modified: `find` never provisions. |
| `tests_py/test_cli.py` | Modified: `intake` command, exit 0 on a per-issue failure, exit 5 on API/token or corrupt state. |
| `tests/format.test.js` | Modified: the footer sentence, including a `failed` source. |

---

### Task 1: GitHub API client

**Files:**
- Create: `tools/getup/github.py`, `tests_py/test_github.py`

**Interfaces:**
- Consumes: stdlib only.
- Produces:
  - `GithubError(status: int, message: str)` — `.status`, `.message`; status `0` means local configuration, not HTTP.
  - `Client(repo: str, token: str, *, fetch=None, base='https://api.github.com')`
  - `Client.issues() -> list[dict]` — open issues carrying `intake`, **excluding** any whose labels contain `processed` and any `pull_request`; server-side query `?state=open&labels=intake&per_page=100&page=N`, paging until a short page.
  - `Client.comments(number: int) -> list[dict]`
  - `Client.comment(number: int, body: str) -> dict`
  - `Client.add_label(number: int, name: str) -> None` — `POST /issues/{n}/labels {'labels': [name]}`
  - `Client.remove_label(number: int, name: str) -> None` — `DELETE /issues/{n}/labels/{name}`; a 404 is not an error.
  - `Client.ensure_labels(names=('intake', 'processed', 'needs-info', 'intake:prefs')) -> None` — `GET /repos/{repo}/labels?per_page=100&page=N`; raises `GithubError(0, 'missing labels: …')` naming every absent label. It never creates a label: the forms silently drop a missing label, so a create-on-the-fly path would hide a misconfigured repo behind a working poll.
  - `client_from_env(environ=None, fetch=None) -> Client` — `GETUP_REPO` (`owner/name`) and `GETUP_GITHUB_TOKEN`; missing either raises `GithubError(0, ...)` naming the variable; `fetch` is passed straight to `Client`.
  - Transport contract: `fetch(request) -> (status: int, headers: dict, body: str)`; the default is `_http` using `urllib.request`.

- [ ] **Step 1: Write the failing tests**

```python
# tests_py/test_github.py
import json, unittest
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
```

- [ ] **Step 2: Run it and confirm it fails** — `python3 -m unittest tests_py.test_github -v` → `ModuleNotFoundError: tools.getup.github`

- [ ] **Step 3: Implement** — `Client._request(method, path, body=None)` builds one `urllib.request.Request` with `Authorization: Bearer`, `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28`, `User-Agent: getup-intake/1.0`, JSON body when given; calls `self._fetch`, parses JSON, raises `GithubError(status, payload['message'])` for any status ≥ 400. `issues()` pages by `per_page=100&page=n` while the page is full, then filters `pull_request` and any label named `processed`. `ensure_labels` GETs the label pages, compares lower-cased names, and raises `GithubError(0, ...)` listing the missing ones. `client_from_env` reads the two variables, strips whitespace, raises `GithubError(0, ...)` before constructing `Client`, and forwards `fetch`.

- [ ] **Step 4: Run and confirm it passes** — `python3 -m unittest tests_py.test_github -v`

- [ ] **Step 5: Commit** — `git add tools/getup/github.py tests_py/test_github.py && git commit -m "feat(intake): stdlib GitHub client with injectable transport"`

---

### Task 2: Issue forms, form parsing and event/source validation

**Files:**
- Create: `.github/ISSUE_TEMPLATE/event.yml`, `.github/ISSUE_TEMPLATE/source.yml`, `.github/ISSUE_TEMPLATE/prefs.yml`, `tools/getup/intake.py`, `tests_py/test_intake_parse.py`

**Interfaces:**
- Consumes: `normalize.tz()` (existing), `normalize.desc_cap` (existing).
- Produces:
  - `EVENT_FIELDS = ('שם האירוע', 'שם המקום', 'עיר', 'תאריך', 'שעה', 'מחיר', 'קישור לאירוע', 'קישור לכרטיסים', 'קהילה סגורה (קישור לקבוצה)', 'תיאור')`
  - `EVENT_REQUIRED = EVENT_FIELDS[:5]`
  - `EVENT_IDS = ('event-title', 'event-venue', 'event-city', 'event-date', 'event-time', 'event-price', 'event-url', 'event-tickets', 'event-gated', 'event-desc')`, `SOURCE_IDS = ('source-name', 'source-url', 'source-kind', 'source-gap')`, `PREFS_IDS = ('prefs-kind', 'prefs-venue', 'prefs-city', 'prefs-artist', 'prefs-reason')` — the form `id:` values in the same order as the field tuples; the drift test compares these, never labels.
  - `parse_form(body: str) -> dict[str, str]` — splits `### <label>` sections; a section value that is `_No response_` or blank becomes `''`; a checked `- [X] <label>` line adds `<label>: 'x'`; an unchecked one adds nothing.
  - `event_draft(fields: dict, today: str) -> tuple[dict | None, list[str]]` — `(draft, [])` or `(None, problems)`. Draft keys: `class='human'`, `source='github'`, `title`, `venue`, `city`, `start` (unix int, `Asia/Jerusalem`), `url` (`קישור לאירוע`, always provenance), `tickets` (`קישור לכרטיסים`, optional), `community`, `price_from`, `desc`. Problems are exactly: `'שם האירוע'`, `'שם האירוע (עד 200 תווים)'`, `'שם המקום'`, `'עיר'`, `'תאריך'`, `'תאריך (YYYY-MM-DD)'`, `'תאריך שכבר עבר'`, `'שעה'`, `'שעה (HH:MM)'`, `'מחיר (מספר בשקלים או חינם)'`, `'קישור לאירוע (https://)'`, `'קישור לכרטיסים (https://)'`, listed in field order.
  - `SOURCE_FIELDS = ('שם המקור', 'כתובת המקור', 'סוג המקור', 'מה חסר היום')`
  - `PREFS_FIELDS = ('סוג הכלל', 'שם המקום', 'עיר', 'אמן או שם מופע', 'למה')`
  - `SOURCE_KINDS = {'לוח מכירות': 'ticketing', 'אגרגטור': 'aggregator', 'לילה': 'nightlife', 'אתר של מקום': 'venue', 'רשת חברתית': 'social'}`
  - `source_record(fields: dict) -> tuple[dict | None, list[str]]` — `{'name', 'url', 'kind', 'note'}`, problems `'שם המקור'`, `'כתובת המקור (https://)'`, `'סוג המקור'`.

- [ ] **Step 1: Write the failing tests**

```python
# tests_py/test_intake_parse.py
import re, unittest
from tools.getup import intake

EVENT = '''### שם האירוע

ערב ג׳אז

### שם המקום

בית ציוני אמריקה (מאירהוף), תל אביב

### עיר

תל אביב

### תאריך

2026-11-14

### שעה

22:00

### מחיר

_No response_

### קישור לאירוע

https://example.com/e/1

### קישור לכרטיסים

https://example.com/t/1

### קהילה סגורה (קישור לקבוצה)

- [ ] קהילה סגורה (קישור לקבוצה)

### תיאור

רביעיית ג׳אז
'''

GATED = EVENT.replace('- [ ]', '- [X]').replace(
    'https://example.com/e/1', 'https://facebook.com/groups/x').replace(
    'https://example.com/t/1', '_No response_')
SOURCE = '''### שם המקור

בילום

### כתובת המקור

https://biluim.co.il

### סוג המקור

אגרגטור

### מה חסר היום

חסרים אירועים מחוץ לתל אביב
'''

class FormTest(unittest.TestCase):
    def test_headings_become_fields_and_no_response_is_empty(self):
        fields = intake.parse_form(EVENT)
        self.assertEqual(fields['שם האירוע'], 'ערב ג׳אז')
        self.assertEqual(fields['מחיר'], '')
        self.assertNotIn('קהילה סגורה (קישור לקבוצה)', fields)

    def test_a_checked_box_is_a_key(self):
        self.assertEqual(intake.parse_form(GATED)['קהילה סגורה (קישור לקבוצה)'], 'x')

    def test_every_form_field_id_is_one_the_parser_knows(self):
        # Only top-level `- type:` blocks carry ids; a dropdown option is `- label:` and is skipped.
        for path, known in (('.github/ISSUE_TEMPLATE/event.yml', intake.EVENT_IDS),
                            ('.github/ISSUE_TEMPLATE/source.yml', intake.SOURCE_IDS),
                            ('.github/ISSUE_TEMPLATE/prefs.yml', intake.PREFS_IDS)):
            ids = re.findall(r'^\s*- type: \w+\n\s+id: (\S+)',
                             open(path, encoding='utf-8').read(), re.M)
            self.assertEqual(len(ids), len(set(ids)), path)
            self.assertEqual(set(ids), set(known), path)

class EventTest(unittest.TestCase):
    def test_a_complete_form_is_one_human_draft(self):
        draft, problems = intake.event_draft(intake.parse_form(EVENT), '2026-10-21')
        self.assertEqual(problems, [])
        self.assertEqual(draft['class'], 'human')
        self.assertEqual(draft['source'], 'github')
        self.assertEqual(draft['start'], 1794686400)          # 2026-11-14 22:00 IST
        self.assertEqual((draft['venue'], draft['city']),
                         ('בית ציוני אמריקה (מאירהוף), תל אביב', 'תל אביב'))
        self.assertEqual((draft['url'], draft['tickets'], draft['community']),
                         ('https://example.com/e/1', 'https://example.com/t/1', None))
        self.assertEqual(draft['desc'], 'רביעיית ג׳אז')

    def test_a_gated_link_is_a_community_link_not_a_ticket(self):
        draft, _ = intake.event_draft(intake.parse_form(GATED), '2026-10-21')
        self.assertEqual((draft['url'], draft['tickets'], draft['community']),
                         ('https://facebook.com/groups/x', None, 'https://facebook.com/groups/x'))

    def test_a_free_event_never_borrows_its_event_page_as_a_ticket_link(self):
        fields = {**intake.parse_form(EVENT), 'מחיר': 'חינם', 'קישור לכרטיסים': ''}
        draft, problems = intake.event_draft(fields, '2026-10-21')
        self.assertEqual(problems, [])
        self.assertEqual((draft['price_from'], draft['tickets']), (0, None))

    def test_free_is_zero_and_a_price_may_carry_a_shekel_sign(self):
        fields = intake.parse_form(EVENT)
        self.assertEqual(intake.event_draft({**fields, 'מחיר': 'חינם'}, '2026-10-21')[0]['price_from'], 0)
        self.assertEqual(intake.event_draft({**fields, 'מחיר': '₪80'}, '2026-10-21')[0]['price_from'], 80)

    def test_every_missing_required_field_is_named_in_form_order(self):
        draft, problems = intake.event_draft({'שם האירוע': 'ערב ג׳אז'}, '2026-10-21')
        self.assertIsNone(draft)
        self.assertEqual(problems, ['שם המקום', 'עיר', 'תאריך', 'שעה'])

    def test_a_bad_date_time_price_or_url_names_only_that_field(self):
        fields = intake.parse_form(EVENT)
        self.assertEqual(intake.event_draft({**fields, 'תאריך': '2026-02-30'}, '2026-10-21')[1],
                         ['תאריך (YYYY-MM-DD)'])
        self.assertEqual(intake.event_draft({**fields, 'שעה': '25:00'}, '2026-10-21')[1],
                         ['שעה (HH:MM)'])
        self.assertEqual(intake.event_draft({**fields, 'תאריך': '2026-10-20'}, '2026-10-21')[1],
                         ['תאריך שכבר עבר'])
        self.assertEqual(intake.event_draft({**fields, 'מחיר': 'מאה שקל'}, '2026-10-21')[1],
                         ['מחיר (מספר בשקלים או חינם)'])
        self.assertEqual(intake.event_draft({**fields, 'קישור לאירוע': 'javascript:alert(1)'}, '2026-10-21')[1],
                         ['קישור לאירוע (https://)'])
        self.assertEqual(intake.event_draft({**fields, 'קישור לכרטיסים': 'javascript:alert(1)'}, '2026-10-21')[1],
                         ['קישור לכרטיסים (https://)'])

    def test_a_two_hundred_and_one_character_title_is_refused_not_truncated(self):
        fields = {**intake.parse_form(EVENT), 'שם האירוע': 'א' * 201}
        self.assertEqual(intake.event_draft(fields, '2026-10-21')[1], ['שם האירוע (עד 200 תווים)'])

class SourceTest(unittest.TestCase):
    def test_a_source_form_is_a_canonical_request(self):
        record, problems = intake.source_record(intake.parse_form(SOURCE))
        self.assertEqual(problems, [])
        self.assertEqual(record, {'name': 'בילום', 'url': 'https://biluim.co.il',
                                  'kind': 'aggregator', 'note': 'חסרים אירועים מחוץ לתל אביב'})

    def test_a_missing_url_and_an_unknown_kind_are_named(self):
        fields = intake.parse_form(SOURCE)
        self.assertEqual(intake.source_record({**fields, 'כתובת המקור': 'javascript:x'})[1],
                         ['כתובת המקור (https://)'])
        self.assertEqual(intake.source_record({**fields, 'סוג המקור': 'פודקאסט'})[1],
                         ['סוג המקור'])
```

- [ ] **Step 2: Run it and confirm it fails** — `python3 -m unittest tests_py.test_intake_parse -v`

- [ ] **Step 3: Implement** — write the three YAML forms with `name:`, `description:`, `title: "[אירוע] "` / `"[מקור] "` / `"[העדפה] "`, `labels` (`["intake"]`, or `["intake", "intake:prefs"]` for prefs), `required: true` on the first three/five fields, and the labels above verbatim. Every field puts `id:` on the line directly after `- type:`, so the drift test can find top-level blocks without matching dropdown options. `parse_form` is one regex over `^### (.+)$` with the section text joined, `_No response_` mapped to `''`, and checkbox lines consumed from the section value. `event_draft` validates in `EVENT_REQUIRED` order, then optional price and both links; `url` is the `קישור לאירוע` value and `community` is that same URL only when the gated box is checked, while `tickets` comes only from `קישור לכרטיסים` — a free or gated event therefore never exposes its page as `כרטיס`. The start is `datetime.fromisoformat(f'{date}T{time}').replace(tzinfo=normalize.tz())`, and the past check is `normalize.bucket_day(start) < today`. `source_record` maps the dropdown through `SOURCE_KINDS` and requires an `https?://` URL.

- [ ] **Step 4: Run and confirm it passes** — `python3 -m unittest tests_py.test_intake_parse -v`

- [ ] **Step 5: Commit** — `git add .github tools/getup/intake.py tests_py/test_intake_parse.py && git commit -m "feat(intake): issue forms and the form-to-record trust boundary"`

---

### Task 3: The human draft store

**Files:**
- Create: `tools/getup/human.py`, `data/human.json`, `tests_py/test_human.py`
- Modify: `tools/getup/normalize.py`, `tests_py/test_normalize.py`

**Interfaces:**
- Consumes: `write.read_json_strict`, `write.write_json` (existing).
- Produces:
  - `store_file(root: str) -> str` — `<root>/data/human.json`
  - `load(root: str) -> dict[str, dict]` — missing file → `{}`; a non-object, a non-dict value or a non-numeric key raises `ValueError` naming the file; never a silent drop.
  - `save(root: str, store: dict) -> bool` — canonical bytes through `write.write_json`.
  - `records(store: dict) -> list[dict]` — the canonical **drafts**, ordered by integer issue number, so two builds cannot swap rows. No `venue_id`, `lat`, `lon`, `drive_min` or `id` is stored: `build.place` adds them on every run.
  - `put(store: dict, number: int, record: dict) -> bool` — replace keyed by `str(number)`; `True` only when the value changed. This is also the correction path: removing `processed` and re-polling calls `put` for the same number.
  - `normalize.record` also reads `draft['tickets']` and `draft['community']` (strings, else `None`) and keeps `draft['url']` in `urls.source` for every class; the existing `class == 'ticketing'` fill-in is unchanged when `tickets` is absent.

- [ ] **Step 1: Write the failing tests**

```python
# tests_py/test_human.py
import tempfile, unittest
from tools.getup import human, write

DRAFT = {'class': 'human', 'source': 'github', 'title': 'ערב ג׳אז',
         'venue': 'בית ציוני אמריקה (מאירהוף)', 'city': 'תל אביב',
         'start': 1794686400, 'url': 'https://github.com/roy/getup/issues/7',
         'tickets': None, 'community': None, 'price_from': None, 'desc': ''}

class StoreTest(unittest.TestCase):
    def test_a_missing_store_is_empty_and_a_corrupt_one_raises(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(human.load(root), {})
            write.write_json(human.store_file(root), {'7': 'not a draft'})
            with self.assertRaises(ValueError):
                human.load(root)

    def test_put_is_byte_stable_and_one_issue_has_one_draft(self):
        with tempfile.TemporaryDirectory() as root:
            store = human.load(root)
            self.assertTrue(human.put(store, 7, DRAFT))
            self.assertFalse(human.put(store, 7, dict(DRAFT)))
            self.assertTrue(human.put(store, 7, {**DRAFT, 'title': 'תיקון'}))   # a correction replaces
            self.assertTrue(human.save(root, store))
            self.assertFalse(human.save(root, store))
            self.assertEqual(human.load(root)['7']['title'], 'תיקון')

    def test_records_are_drafts_ordered_by_issue_number_not_by_string(self):
        store = {}
        human.put(store, 10, {**DRAFT, 'title': 'b'})
        human.put(store, 2, {**DRAFT, 'title': 'a'})
        self.assertEqual([r['title'] for r in human.records(store)], ['a', 'b'])
        self.assertNotIn('venue_id', human.records(store)[0])
```

```python
# tests_py/test_normalize.py — added case
class HumanUrlTest(unittest.TestCase):
    def test_the_event_link_is_always_the_source_and_tickets_is_explicit(self):
        rec = normalize.record({**DRAFT, 'class': 'human', 'source': 'github',
                                'url': 'https://facebook.com/events/9',
                                'tickets': 'https://t', 'community': None})
        self.assertEqual(rec['urls'], {'tickets': 'https://t', 'community': None,
                                       'source': 'https://facebook.com/events/9'})
        rec = normalize.record({**DRAFT, 'class': 'human', 'source': 'github',
                                'url': 'https://facebook.com/groups/x',
                                'tickets': None, 'community': 'https://facebook.com/groups/x'})
        self.assertEqual((rec['urls']['tickets'], rec['urls']['community']),
                         (None, 'https://facebook.com/groups/x'))

    def test_the_ticket_seller_rule_is_unchanged(self):
        self.assertEqual(normalize.record(dict(DRAFT))['urls']['tickets'], DRAFT['url'])
```

- [ ] **Step 2: Run it and confirm it fails** — `python3 -m unittest tests_py.test_human tests_py.test_normalize -v`

- [ ] **Step 3: Implement** — `load` validates keys with `str.isdigit()` and values with `isinstance(..., dict)` plus a non-empty string `title` and `venue` and an int `start`, raising one `ValueError` naming the file and the offending key. `records` sorts `store` by `int(key)` and returns the drafts untouched. `put` deep-copies nothing (the draft is already detached) and returns `store.get(key) != record`; writing the same number again is the correction path. In `normalize.record`, compute `tickets = draft.get('tickets') or (url if source_class == 'ticketing' else None)` and `community = draft.get('community')`, keeping both `None` unless they are non-empty strings, and keep `urls['source'] = url` for every class. Commit `data/human.json` as `{}`. The store holds no coordinates and no `id`; `build.place` derives them, and nothing in `write.data_files`, `manifest.day_counts` or `cli pending` may enumerate `data/human.json` as a day file.

- [ ] **Step 4: Run and confirm it passes** — `python3 -m unittest tests_py.test_human tests_py.test_normalize -v`

- [ ] **Step 5: Commit** — `git add tools/getup/human.py data/human.json tools/getup/normalize.py tests_py/test_human.py tests_py/test_normalize.py && git commit -m "feat(intake): committed human draft store and explicit record links"`

---

### Task 4: Event and source ingestion, the guard and the labels

**Files:**
- Create: `tests_py/github_fake.py`, `tests_py/test_intake.py`
- Modify: `tools/getup/intake.py`

**Interfaces:**
- Consumes: `github.Client`/`GithubError`/`client_from_env` (Task 1), `parse_form`/`event_draft`/`source_record` (Task 2), `human.load/save/put/store_file` (Task 3), `venues.load/find/resolve`, `dedup.WINDOW`.
- Produces:
  - `ASSOCIATIONS = frozenset({'OWNER', 'MEMBER'})`
  - `eligible(issue: dict) -> bool`
  - `RECEIPT_MARK = '<!-- getup:record -->'`, `INFO_MARK = '<!-- getup:needs-info -->'`
  - `info(problems: list[str]) -> str` — `INFO_MARK + '\nלא נקלט. נדרש: ' + ' · '.join(problems)`
  - `receipt(payload: dict, lead: str) -> str` — marker, Hebrew lead, and `<pre>` with `html.escape(json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True))`
  - `GithubError` and `client_from_env` — re-exported from `github` so callers (and `cli`'s patch target `tools.getup.intake.client_from_env`) import them here.
  - `same_event(store: dict, number: int, draft: dict, registry: dict) -> bool` — another issue's draft is the same event when their venues resolve to one id (falling back to normalized venue+city for an unprovisioned venue) and `start` is within `dedup.WINDOW`; the issue's own entry never counts, so a correction is an update, not a merge.
  - `ingest(root: str, issue: dict, *, client, today: str) -> dict` — `{'number', 'result', 'problems'}` with result in `{'ingested', 'merged', 'source', 'needs-info', 'skipped', 'failed'}`; never raises for a bad issue. Stores the **canonical draft** (no placement, no coordinates); catches `GithubError` and `ValueError` into `'failed'` and comments the message, so one corrupt state file fails one issue and the poll continues.
  - `poll(root: str, *, client, today: str) -> list[dict]` — `ensure_labels()` once (a missing label raises before any issue is touched), then one `ingest` per issue, sorted by number
  - `KINDS = ('event', 'source')` — which form a body is; `detect(fields) -> str | None`

- [ ] **Step 1: Write the failing tests**

```python
# tests_py/github_fake.py
class Fake:
    def __init__(self, issues=(), comments=None):
        self.pending = list(issues)
        self.comments_ = dict(comments or {})
        self.said, self.labels, self.ensured = [], [], 0
    def ensure_labels(self): self.ensured += 1
    def issues(self): return list(self.pending)
    def comments(self, n): return list(self.comments_.get(n, []))
    def comment(self, n, body):
        self.said.append((n, body))
        self.comments_.setdefault(n, []).append({'body': body})
        return {}
    def add_label(self, n, name): self.labels.append((n, name))
    def remove_label(self, n, name): self.labels.append((n, '-' + name))

def issue(n, body, association='OWNER', labels=()):
    return {'number': n, 'state': 'open', 'body': body, 'author_association': association,
            'labels': [{'name': 'intake'}, *({'name': l} for l in labels)]}
```

```python
# tests_py/test_intake.py
import html, json, os, shutil, tempfile, unittest
from tools.getup import human, intake, venues, write
from tests_py.github_fake import Fake, issue
from tests_py.test_intake_parse import EVENT

TODAY = '2026-10-21'

def fresh(root):
    shutil.copytree('venue', f'{root}/venue')
    os.makedirs(f'{root}/data')
    write.write_json(human.store_file(root), {})

class GuardTest(unittest.TestCase):
    def test_a_non_member_issue_writes_nothing_at_all(self):
        for assoc in ('NONE', 'CONTRIBUTOR', 'COLLABORATOR', 'FIRST_TIME_CONTRIBUTOR'):
            with tempfile.TemporaryDirectory() as root:
                fresh(root)
                client = Fake([issue(7, EVENT, assoc)])
                self.assertEqual(intake.poll(root, client=client, today=TODAY),
                                 [{'number': 7, 'result': 'skipped', 'problems': []}])
                self.assertEqual((client.said, client.labels, human.load(root)), ([], [], {}))

class EventTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        fresh(self.root)
        self.client = Fake([issue(7, EVENT.replace('https://example.com/t/1', 'https://x/t'))])

    def test_a_valid_issue_stores_the_canonical_draft_with_a_receipt_and_processed(self):
        self.assertEqual(intake.poll(self.root, client=self.client, today=TODAY),
                         [{'number': 7, 'result': 'ingested', 'problems': []}])
        stored = human.load(self.root)['7']
        self.assertEqual((stored['venue'], stored['start']),
                         ('בית ציוני אמריקה (מאירהוף), תל אביב', 1794686400))
        self.assertEqual((stored['class'], stored['source']), ('human', 'github'))
        self.assertEqual((stored['url'], stored['tickets']),
                         ('https://example.com/e/1', 'https://x/t'))
        self.assertNotIn('venue_id', stored)        # placement belongs to the build
        self.assertNotIn('drive_min', stored)
        self.assertEqual(self.client.labels, [(7, 'processed')])
        body = self.client.said[0][1]
        self.assertTrue(body.startswith(intake.RECEIPT_MARK))
        self.assertIn('נקלט', body)
        self.assertIn(json.dumps(stored, ensure_ascii=False, indent=1, sort_keys=True),
                      html.unescape(body))

    def test_a_second_issue_for_an_ingested_event_receipts_a_merge_not_an_intake(self):
        client = Fake([issue(7, EVENT), issue(8, EVENT)])
        self.assertEqual([r['result'] for r in intake.poll(self.root, client=client, today=TODAY)],
                         ['ingested', 'merged'])
        self.assertIn('מוזג לאירוע קיים', client.said[1][1])
        self.assertNotIn('נקלט', client.said[1][1])

    def test_replaying_the_same_issue_posts_no_second_comment_and_stores_one_draft(self):
        intake.poll(self.root, client=self.client, today=TODAY)
        intake.poll(self.root, client=self.client, today=TODAY)
        self.assertEqual(len(human.load(self.root)), 1)
        self.assertEqual(len(self.client.said), 1)

    def test_a_correction_replaces_the_record_for_that_issue_number(self):
        intake.poll(self.root, client=self.client, today=TODAY)
        corrected = EVENT.replace('ערב ג׳אז', 'ערב ג׳אז — תיקון')
        client = Fake([issue(7, corrected)])
        self.assertEqual(intake.poll(self.root, client=client, today=TODAY),
                         [{'number': 7, 'result': 'ingested', 'problems': []}])
        self.assertEqual(len(human.load(self.root)), 1)
        self.assertEqual(human.load(self.root)['7']['title'], 'ערב ג׳אז — תיקון')

    def test_a_malformed_issue_names_the_field_and_changes_no_file(self):
        before = open(human.store_file(self.root), 'rb').read()
        client = Fake([issue(8, EVENT.replace('### שעה\n\n22:00', '### שעה\n\n_No response_'))])
        self.assertEqual(intake.poll(self.root, client=client, today=TODAY),
                         [{'number': 8, 'result': 'needs-info', 'problems': ['שעה']}])
        self.assertEqual(human.load(self.root), {})
        self.assertEqual(client.said, [(8, intake.info(['שעה']))])
        self.assertEqual(client.labels, [(8, 'needs-info')])
        self.assertEqual(open(human.store_file(self.root), 'rb').read(), before)

    def test_a_failed_comment_is_a_failed_issue_and_the_poll_continues(self):
        client = Fake([issue(7, EVENT), issue(8, EVENT.replace('2026-11-14', '2026-11-15'))])
        real = client.comment
        def broken(n, body):
            if n == 7:
                raise intake.GithubError(500, 'server error')
            real(n, body)
        client.comment = broken
        results = intake.poll(self.root, client=client, today=TODAY)
        self.assertEqual([r['result'] for r in results], ['failed', 'ingested'])

    def test_a_corrupt_state_file_fails_one_issue_with_a_named_comment_and_continues(self):
        write.write_json(human.store_file(self.root), ['not', 'an', 'object'])
        client = Fake([issue(7, EVENT), issue(8, EVENT)])
        results = intake.poll(self.root, client=client, today=TODAY)
        self.assertEqual([r['result'] for r in results], ['failed', 'failed'])
        self.assertIn('human.json', client.said[0][1])
        self.assertIn('human.json', client.said[1][1])
        self.assertEqual(client.labels, [])             # a failed issue changes no label

    def test_an_unrecognised_body_is_needs_info_not_a_guess(self):
        client = Fake([issue(9, '### מה זה\n\nמשהו אחר')])
        self.assertEqual(intake.poll(self.root, client=client, today=TODAY),
                         [{'number': 9, 'result': 'needs-info', 'problems': ['טופס לא מזוהה']}])

class SourceTest(unittest.TestCase):
    def test_a_source_request_is_receipted_and_processed_without_touching_records(self):
        from tests_py.test_intake_parse import SOURCE
        with tempfile.TemporaryDirectory() as root:
            fresh(root)
            client = Fake([issue(11, SOURCE)])
            self.assertEqual(intake.poll(root, client=client, today=TODAY),
                             [{'number': 11, 'result': 'source', 'problems': []}])
            self.assertIn('"kind": "aggregator"', html.unescape(client.said[0][1]))
            self.assertEqual((client.labels, human.load(root)), [(11, 'processed')], {})
```

- [ ] **Step 2: Run it and confirm it fails** — `python3 -m unittest tests_py.test_intake -v`

- [ ] **Step 3: Implement** — `ingest` first checks `eligible` (return `skipped` before any client call), then `parse_form` → `detect`; `None` is `['טופס לא מזוהה']`. For an event: `event_draft`; on problems post `info(...)` once (guarded by the marker in `client.comments`) and `add_label('needs-info')`. On success load the store and the registry, set `merged = same_event(store, number, draft, registry)`, `human.put` + `human.save`, and receipt the draft with `'מוזג לאירוע קיים. הרשומה הקנונית:'` when merged, else `'נקלט. הרשומה הקנונית:'`; then `add_label('processed')`, and `remove_label('needs-info')` **only when the issue carries that label**. No venue is provisioned here and no coordinate is stored: `build.place` owns that on every run. For a source: `source_record`, `receipt(record, 'נקלט. בקשת המקור:')`, `processed`; no file. Wrap the body in `except GithubError` and `except ValueError`; both return `failed` with the message in `.problems` and no label change, but the `ValueError` branch comments `'{INFO_MARK}\nלא נקלט. קובץ מצב פגום: {exc}'` so the file is named on the issue, and `poll` moves on to the next issue.

- [ ] **Step 4: Run and confirm it passes** — `python3 -m unittest tests_py.test_intake -v`

- [ ] **Step 5: Commit** — `git add tools/getup/intake.py tests_py/github_fake.py tests_py/test_intake.py && git commit -m "feat(intake): guarded issue ingestion with receipts, labels and replay safety"`

---

### Task 5: Preference authoring and its documentation

**Files:**
- Create: `README.md`, `tests_py/test_intake_prefs.py`
- Modify: `tools/getup/venues.py`, `tools/getup/intake.py`, `tests_py/test_venues.py`

**Interfaces:**
- Consumes: `venues.alias_index`, `venues._unique_name` (existing, same module), `write.read_json/write_json`, `parse_form`, `PREFS_FIELDS` (Task 2), `github` (Task 1).
- Produces:
  - `venues.find(registry: dict, venue, city) -> str | None` — the alias lookup `resolve` already does, without provisioning and without mutation; `resolve` becomes `find(...) or _provision(...)` with byte-identical behaviour.
  - `PREFS_KINDS = {'לא להציג': 'never', 'תמיד להציג': 'always'}`
  - `prefs_rule(fields: dict, registry: dict) -> tuple[dict | None, list[str]]` — `{'kind': 'never'|'always', 'rule': {'venue_id': ...} | {'artist': ...}}`; both keys when both fields are filled; problems `'סוג הכלל'`, `'שם המקום או אמן'`, `'שם המקום (לא נמצא במאגר)'`.
  - `prefs_file(root: str) -> str` — `<root>/prefs.json`
  - `add_rule(root: str, kind: str, rule: dict) -> bool` — appends to `never`/`always` unless an equal dict is already there; writes canonical bytes; a corrupt `prefs.json` raises `ValueError` rather than being overwritten.
  - `detect(fields) -> str | None` gains `'prefs'`; `ingest` handles it with `receipt(spec, 'נקלט. ההעדפה נוספה ל־prefs.json ותיכנס לתוקף ברענון הבא.')`.

- [ ] **Step 1: Write the failing tests**

```python
# tests_py/test_venues.py — added case
class FindTest(unittest.TestCase):
    def test_find_answers_without_provisioning(self):
        reg = venues.load('.')
        before = len(reg)
        self.assertEqual(venues.find(reg, 'בית ציוני אמריקה (מאירהוף)', 'תל אביב'),
                         'v_zionist_america_tlv')
        self.assertIsNone(venues.find(reg, 'מועדון שלא קיים', 'חיפה'))
        self.assertEqual(len(reg), before)          # a prefs lookup must never curate the registry
```

```python
# tests_py/test_intake_prefs.py
import json, os, shutil, tempfile, unittest
from tools.getup import intake, venues, write
from tests_py.github_fake import Fake, issue
from tests_py.test_intake_parse import EVENT

TODAY = '2026-10-21'
PREFS = '''### סוג הכלל

לא להציג

### שם המקום

בית ציוני אמריקה (מאירהוף)

### עיר

תל אביב

### אמן או שם מופע

_No response_

### למה

רועש מדי
'''

def fresh(root):
    shutil.copytree('venue', f'{root}/venue')
    os.makedirs(f'{root}/data')

class RuleTest(unittest.TestCase):
    def test_a_venue_rule_resolves_to_an_id_without_touching_the_registry(self):
        reg = venues.load('.')
        spec, problems = intake.prefs_rule(intake.parse_form(PREFS), reg)
        self.assertEqual(problems, [])
        self.assertEqual(spec, {'kind': 'never', 'rule': {'venue_id': 'v_zionist_america_tlv'}})

    def test_an_artist_rule_keeps_the_title_and_both_fields_are_an_and(self):
        fields = intake.parse_form(PREFS)
        self.assertEqual(intake.prefs_rule({**fields, 'שם המקום': '', 'עיר': '',
                                            'אמן או שם מופע': 'The Cure'}, venues.load('.'))[0],
                         {'kind': 'never', 'rule': {'artist': 'The Cure'}})
        both = intake.prefs_rule({**fields, 'אמן או שם מופע': 'The Cure'}, venues.load('.'))
        self.assertEqual(both[0]['rule'], {'venue_id': 'v_zionist_america_tlv', 'artist': 'The Cure'})

    def test_an_unknown_venue_and_an_empty_rule_are_named(self):
        fields = intake.parse_form(PREFS)
        self.assertEqual(intake.prefs_rule({**fields, 'שם המקום': 'מועדון שלא קיים'},
                                           venues.load('.'))[1], ['שם המקום (לא נמצא במאגר)'])
        self.assertEqual(intake.prefs_rule({**fields, 'שם המקום': '', 'עיר': ''},
                                           venues.load('.'))[1], ['שם המקום או אמן'])

    def test_add_rule_appends_once_and_keeps_the_two_lists(self):
        with tempfile.TemporaryDirectory() as root:
            fresh(root)
            write.write_json(intake.prefs_file(root), {'never': [], 'always': []})
            self.assertTrue(intake.add_rule(root, 'never', {'artist': 'The Cure'}))
            self.assertFalse(intake.add_rule(root, 'never', {'artist': 'The Cure'}))
            self.assertTrue(intake.add_rule(root, 'always', {'venue_id': 'v_x'}))
            self.assertEqual(json.load(open(intake.prefs_file(root), encoding='utf-8')),
                             {'never': [{'artist': 'The Cure'}], 'always': [{'venue_id': 'v_x'}]})

    def test_the_prefs_issue_writes_the_file_and_receipts_the_rule(self):
        with tempfile.TemporaryDirectory() as root:
            fresh(root)
            write.write_json(intake.prefs_file(root), {'never': [], 'always': []})
            client = Fake([issue(21, PREFS)])
            self.assertEqual(intake.poll(root, client=client, today=TODAY),
                             [{'number': 21, 'result': 'prefs', 'problems': []}])
            self.assertEqual(json.load(open(intake.prefs_file(root), encoding='utf-8'))['never'],
                             [{'venue_id': 'v_zionist_america_tlv'}])
            self.assertIn('"venue_id": "v_zionist_america_tlv"', client.said[0][1])
            self.assertEqual(client.labels, [(21, 'processed')])

    def test_a_corrupt_prefs_file_fails_only_its_issue_and_the_poll_continues(self):
        with tempfile.TemporaryDirectory() as root:
            fresh(root)
            write.write_bytes(intake.prefs_file(root), b'{')
            client = Fake([issue(20, PREFS), issue(21, EVENT)])
            results = intake.poll(root, client=client, today=TODAY)
            self.assertEqual([r['result'] for r in results], ['failed', 'ingested'])
            self.assertIn('prefs.json', client.said[0][1])
            self.assertEqual(client.labels, [(21, 'processed')])

    def test_the_readme_documents_the_shape_the_writer_writes(self):
        text = open('README.md', encoding='utf-8').read()
        for token in ('"never"', '"always"', '"venue_id"', '"artist"', 'prefs.yml',
                      'gh label create', 'processed'):
            self.assertIn(token, text)
```

- [ ] **Step 2: Run it and confirm it fails** — `python3 -m unittest tests_py.test_intake_prefs tests_py.test_venues -v`

- [ ] **Step 3: Implement** — the prefs form from Task 2 already carries `סוג הכלל` (dropdown `לא להציג`/`תמיד להציג`), the three lookup fields, `למה` (a textarea the parser keeps but the rule ignores) and `intake:prefs`. `venues.find` holds the two lookup passes that `resolve` has today and returns `None` instead of provisioning; `resolve` calls it and provisions on `None`. `prefs_rule` maps the dropdown, requires at least one of venue/artist, resolves a venue only through `find`, and returns the exact dict. `add_rule` validates `kind in {'never', 'always'}` and `rule` non-empty, loads a lenient missing file as `{never: [], always: []}` but raises `ValueError` naming the file on a non-object, appends only when absent, and writes with `write.write_json`. `ingest` adds the `'prefs'` branch: load registry, `prefs_rule`, `add_rule`, receipt, `processed`, remove `needs-info`; the shared `ValueError` catch in `ingest` turns a corrupt `prefs.json` or `venues.json` into one failed issue with a comment naming the file. README gains: what the page is, the one-time label bootstrap (`gh label create intake`, `gh label create processed`, `gh label create needs-info`, `gh label create intake:prefs`) and why a missing label stops the poll, the three issue forms, the daily commands, the correction loop (remove `processed` from a processed issue and the next poll replaces that issue's draft), and this block as the schema example:

```json
{"never": [{"venue_id": "v_zionist_america_tlv"}], "always": [{"artist": "The Cure"}]}
```

  with one table row per field (`venue_id`, `artist`; at least one per rule; both means AND; artist is an exact normalized title match; the file is applied in the browser on reload, no rescan).

- [ ] **Step 4: Run and confirm it passes** — `python3 -m unittest tests_py.test_intake_prefs tests_py.test_venues -v`

- [ ] **Step 5: Commit** — `git add README.md tools/getup/venues.py tools/getup/intake.py tests_py/test_intake_prefs.py tests_py/test_venues.py && git commit -m "feat(intake): author prefs.json from an issue and document the schema"`

---

### Task 6: Human precedence in dedup and in the build

**Files:**
- Modify: `tools/getup/dedup.py`, `tools/getup/build.py`, `tests_py/test_dedup.py`, `tests_py/test_build.py`

**Interfaces:**
- Consumes: records (existing), `human.load/records` (Task 3), `build.place`, `venues.save`, `build.run` internals.
- Produces:
  - `dedup.RANK['human'] = 4` — above `ticketing` (3).
  - `build.run` reads `human.records(human.load(root))` on every run and passes those canonical drafts through `place` **before** `geo.fill`/`geo.seed`, in a second call whose drops do not touch `dropped_no_venue`; the coordinates copied into the normalized record therefore come from the registry of that run, never from ingestion. Scan counts and statuses stay tallied from scan survivors only. A run where every scan source failed still writes nothing (existing rule) and therefore publishes no human row that day.
  - The `seen_last` stamp loop skips `record['source']['class'] == 'human'`: one manual post at a major venue must not mask a broken adapter. A corrupt `human.json` still aborts the build loudly.

- [ ] **Step 1: Write the failing tests**

```python
# tests_py/test_dedup.py — added class
class HumanTest(unittest.TestCase):
    def test_a_human_correction_beats_the_seller_and_keeps_its_fields(self):
        human_rec = rec(id='h1', title='ערב ג׳אז — תיקון', price_from=1,
                        source={'class': 'human', 'name': 'github'},
                        urls={'tickets': 'https://t', 'community': None,
                              'source': 'https://github.com/roy/getup/issues/7'})
        seller = rec(id='t1', price_from=174, soldout=True)
        out = dedup.merge([seller, human_rec])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['id'], 'h1')
        self.assertEqual(out[0]['title'], 'ערב ג׳אז — תיקון')
        self.assertEqual(out[0]['price_from'], 1)
        self.assertEqual(out[0]['source'], {'class': 'human', 'name': 'github'})
        self.assertEqual(out[0]['urls']['source'], 'https://github.com/roy/getup/issues/7')
        self.assertEqual(out[0]['enrichment'], ['leaan: d'])
        self.assertEqual(dedup.merge([human_rec, seller]), out)   # order cannot change the winner

    def test_a_human_record_is_never_absorbed_into_a_machine_row(self):
        human_rec = rec(id='h1', source={'class': 'human', 'name': 'github'})
        out = dedup.merge([rec(id='a1', start=1792780200 + 1200,
                               source={'class': 'aggregator', 'name': 'biluim'}), human_rec])
        self.assertEqual([r['source']['class'] for r in out], ['human'])
        self.assertEqual(out[0]['id'], 'h1')

    def test_thirty_one_minutes_away_is_still_a_second_event(self):
        human_rec = rec(id='h1', source={'class': 'human', 'name': 'github'})
        self.assertEqual(len(dedup.merge([human_rec, rec(id='t2', start=1792780200 + 1861)])), 2)
```

```python
# tests_py/test_build.py — added class
from tools.getup import human, venues

def served(root):
    return {ev['id']: ev for day in write.data_files(f'{root}/data')
            for ev in json.load(open(write.date_file(root, day), encoding='utf-8'))}

def human_draft(root, base, **overrides):
    venue = venues.load(root)[base['venue_id']]['name']
    draft = {'class': 'human', 'source': 'github', 'title': base['title'],
             'venue': venue, 'city': base['city'], 'start': base['start'],
             'url': 'https://github.com/roy/getup/issues/7',
             'tickets': None, 'community': None,
             'price_from': base['price_from'], 'desc': ''}
    return {**draft, **overrides}

class HumanPrecedenceTest(unittest.TestCase):
    def test_a_human_correction_survives_the_next_scan_and_is_not_duplicated(self):
        with tempfile.TemporaryDirectory() as root:
            fresh(root)
            args = dict(sources=('leaan',), from_dir=CAPTURE, fetch=no_network, now=NOW)
            build.run(root, TODAY, **args)
            base = next(ev for ev in served(root).values() if ev['day'] == '2026-10-22')
            correction = human_draft(root, base, title='תיקון אנושי', price_from=7)
            write.write_json(human.store_file(root), {'7': correction})
            build.run(root, TODAY, **args)
            rows = [ev for ev in served(root).values() if ev['id'] == base['id']]
            self.assertEqual(len(rows), 1)
            self.assertEqual((rows[0]['title'], rows[0]['price_from']), ('תיקון אנושי', 7))
            self.assertEqual(rows[0]['source'], {'class': 'human', 'name': 'github'})
            self.assertEqual(rows[0]['urls']['source'], 'https://github.com/roy/getup/issues/7')
            self.assertTrue(any(n.startswith(base['source']['name'])
                                for n in rows[0]['enrichment']))
            build.run(root, TODAY, **args)
            self.assertEqual(len([ev for ev in served(root).values()
                                  if ev['id'] == base['id']]), 1)

    def test_a_human_draft_gets_coordinates_when_its_new_venue_is_seeded(self):
        with tempfile.TemporaryDirectory() as root:
            fresh(root)
            write.write_json(human.store_file(root), {'7': {
                'class': 'human', 'source': 'github', 'title': 'ערב ג׳אז במועדון החדש',
                'venue': 'מועדון חדש לגמרי', 'city': 'חיפה', 'start': 1794686400,
                'url': 'https://github.com/roy/getup/issues/7',
                'tickets': None, 'community': None, 'price_from': None, 'desc': ''}})
            build.run(root, TODAY, sources=('leaan',), from_dir=CAPTURE,
                      fetch=no_network, now=NOW)
            row = next(ev for ev in served(root).values()
                       if ev['title'] == 'ערב ג׳אז במועדון החדש')
            self.assertIsNotNone(row['lat'])          # provisioned, then geo.seed filled it
            self.assertIsNotNone(row['drive_min'])

    def test_a_human_row_never_stamps_seen_last(self):
        with tempfile.TemporaryDirectory() as root:
            fresh(root)
            draft = {'class': 'human', 'source': 'github', 'title': 'ערב ג׳אז',
                     'venue': 'מועדון ללא סריקה', 'city': 'חיפה',
                     'start': 1794686400, 'url': 'https://github.com/roy/getup/issues/7',
                     'tickets': None, 'community': None, 'price_from': None, 'desc': ''}
            write.write_json(human.store_file(root), {'7': draft})
            build.run(root, TODAY, sources=('leaan',), from_dir=CAPTURE,
                      fetch=no_network, now=NOW)
            venue = next(v for v in venues.load(root).values()
                         if v.get('name') == 'מועדון ללא סריקה')
            self.assertNotEqual(venue.get('seen_last'), TODAY)

    def test_two_issues_for_one_event_are_one_row(self):
        with tempfile.TemporaryDirectory() as root:
            fresh(root)
            args = dict(sources=('leaan',), from_dir=CAPTURE, fetch=no_network, now=NOW)
            build.run(root, TODAY, **args)
            base = next(ev for ev in served(root).values() if ev['day'] == '2026-10-22')
            draft = human_draft(root, base)
            write.write_json(human.store_file(root), {'7': draft, '8': dict(draft)})
            build.run(root, TODAY, **args)
            self.assertEqual(len([ev for ev in served(root).values()
                                  if ev['id'] == base['id']]), 1)
```

- [ ] **Step 2: Run it and confirm it fails** — `python3 -m unittest tests_py.test_dedup tests_py.test_build -v`

- [ ] **Step 3: Implement** — one line in `dedup.RANK` with a comment naming ruling 6. In `build.run`, after the scanned `place(...)` and **before** `geo.fill`/`geo.seed`, do `human_kept, _ = place(registry, human.records(human.load(root)))` so a venue the drafts provision is geocoded and seeded in the same run; normalize `human_kept` into their own list, so `_tally` never reports `github` as an unknown source and no source count changes. Then `records = classify.apply(dedup.merge(records + human_records), ...)`. In the `seen_last` loop, `continue` when `(record.get('source') or {}).get('class') == 'human'`; do not touch counts, states, `dropped_no_venue`, `unpinned`, pruning or archiving. `human.load` raising on a corrupt file aborts the run loudly — a corrupted store must not silently drop corrections.

- [ ] **Step 4: Run and confirm it passes** — `python3 -m unittest tests_py.test_dedup tests_py.test_build -v`

- [ ] **Step 5: Commit** — `git add tools/getup/dedup.py tools/getup/build.py tests_py/test_dedup.py tests_py/test_build.py && git commit -m "feat(pipeline): human records win dedup and survive every scan"`

---

### Task 7: The quiet ops line in the footer

**Files:**
- Modify: `src/format.js`, `app.js`, `tests/format.test.js`

**Interfaces:**
- Consumes: `manifest.sources` (`{name: {status, count, failures}}`) and `manifest.coverage` (`{checked, missed: [{venue_id, name}]}`) from `data/index.json`.
- Produces:
  - `opsLine(manifest) -> str` — one Hebrew sentence. Failed sources first (`מקור שנכשל: a`), then partial (`מקור חלקי: b`), each name list sorted and joined by `, `; then the coverage half: misses by `name` → `לא נבדקו ב־14 הימים האחרונים: x · y`; else `checked > 0` → `כל N המקורות נבדקו`; else `אין מידע על כיסוי המקורות`. Parts joined by ` · `. The all-clear sentence is omitted when any source is failed or partial. Statuses other than `failed`/`partial` and non-object entries are ignored.
  - `app.js` writes `opsLine(manifest)` into `#coverage` and keeps the age in `#data-age`; no other render change. Filtering, ordering and the manifest itself are untouched.

- [ ] **Step 1: Write the failing tests**

```javascript
// tests/format.test.js — added import and cases
import { opsLine } from '../src/format.js';
import { readFileSync } from 'node:fs';

test('a failed source is named in the footer', () => {
  assert.equal(
    opsLine({ sources: { leaan: { status: 'failed' } }, coverage: { checked: 3, missed: [] } }),
    'מקור שנכשל: leaan',
  );
});

test('partial and failed sources share one line with the misses', () => {
  assert.equal(
    opsLine({
      sources: { leaan: { status: 'failed' }, biluim: { status: 'partial' }, popit: { status: 'ok' } },
      coverage: { checked: 3, missed: [{ venue_id: 'v', name: 'היכל התרבות' }] },
    }),
    'מקור שנכשל: leaan · מקור חלקי: biluim · לא נבדקו ב־14 הימים האחרונים: היכל התרבות',
  );
});

test('a failure suppresses the all-clear sentence', () => {
  assert.equal(
    opsLine({ sources: { popit: { status: 'failed' } }, coverage: { checked: 3, missed: [] } }),
    'מקור שנכשל: popit',
  );
});

test('an unknown status is not a failure and the all-clear survives', () => {
  assert.equal(
    opsLine({ sources: { x: { status: 'ok-ish' }, y: 'failed' }, coverage: { checked: 3, missed: [] } }),
    'כל 3 המקורות נבדקו',
  );
});

test('an older index without sources still reports coverage', () => {
  assert.equal(opsLine({}), 'אין מידע על כיסוי המקורות');
  assert.equal(opsLine({ coverage: { checked: 3, missed: ['שם'] } }),
    'לא נבדקו ב־14 הימים האחרונים: שם');
});

test('the page still has the footer slot the writer targets', () => {
  assert.match(readFileSync(new URL('../index.html', import.meta.url), 'utf8'), /id="coverage"/);
});
```

- [ ] **Step 2: Run it and confirm it fails** — `node --test tests/format.test.js`

- [ ] **Step 3: Implement** — `opsLine` in `src/format.js`: a `names(map, status)` helper, `Array.isArray(manifest?.coverage?.missed)` with the same string/`.name`/`.venue_id` fallback the footer has today, then `parts.join(' · ')`. Replace the `missed`/`checked` block in `app.js` with the import and `$('#coverage').textContent = opsLine(manifest);`. No filtering, no sorting, no event mutation.

- [ ] **Step 4: Run and confirm it passes** — `node --test` (all client tests, 134 + new)

- [ ] **Step 5: Commit** — `git add src/format.js app.js tests/format.test.js && git commit -m "feat(client): footer names failed sources and coverage misses on one line"`

---

### Task 8: The `intake` command

**Files:**
- Modify: `tools/getup/cli.py`, `tools/getup/intake.py`, `tests_py/test_cli.py`

**Interfaces:**
- Consumes: `intake.poll`, `intake.client_from_env` (Task 4), `github.GithubError` (Task 1).
- Produces:
  - `intake.check_state(root) -> None` — strictly loads `prefs.json`, `venue/venues.json` and `data/human.json` through their own loaders (`write.read_json_strict` for prefs), raising `ValueError` naming the file and the fault; called before any network or poll.
  - `cli.main(['intake', '--root', R, '--today', D]) -> int` — prints one line per issue (`#7: ingested`, `#8: failed — …`, `#9: needs-info — שעה`); **`0` when the poll ran, even if an issue failed** (the receipt comment and the log carry the failure), `5` when the GitHub API or token failed or a state file is corrupt at startup (one line on stderr, no polling), `1` for bad arguments.
  - `EXIT_CODES` gains `5 intake: GitHub API or token failure, or a corrupt prefs.json/venues.json/human.json`; its help text also states that a per-issue failure still exits `0`. The command resolves the token and repo from the environment at call time, so tests patch `tools.getup.intake.client_from_env`.

- [ ] **Step 1: Write the failing tests**

```python
# tests_py/test_cli.py — added class
from tools.getup import github, human, write
from tests_py.github_fake import Fake, issue
from tests_py.test_intake import fresh
from tests_py.test_intake_parse import EVENT

class IntakeCliTest(unittest.TestCase):
    def test_a_polled_issue_is_written_by_the_command(self):
        with tempfile.TemporaryDirectory() as root:
            fresh(root)
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
            fresh(root)
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
            fresh(root)
            write.write_bytes(os.path.join(root, 'prefs.json'), b'{')
            client = Fake([issue(7, EVENT)])
            with mock.patch('tools.getup.intake.client_from_env', return_value=client) as made:
                self.assertEqual(cli.main(['intake', '--root', root, '--today', TODAY]), 5)
            self.assertEqual(made.call_count, 0)      # checked before the client is built
            self.assertEqual(client.ensured, 0)

    def test_a_missing_token_is_exit_five_and_never_network(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(cli.main(['intake']), 5)
```

- [ ] **Step 2: Run it and confirm it fails** — `python3 -m unittest tests_py.test_cli -v` (`unrecognized arguments: intake`)

- [ ] **Step 3: Implement** — `check_state` lives in `intake.py`: it calls `human.load(root)`, `venues.load(root)` and, when `prefs_file(root)` exists, `write.read_json_strict` plus an object check; any fault is one `ValueError` naming the file. Add `subs.add_parser('intake')` with `--root`/`--today` only, a `check_state(root)` call **before** `client_from_env`, and `_intake(args)` that catches `github.GithubError` and the `check_state` `ValueError` into one stderr line and returns `5`; both happen before polling. Per-issue results print one line each and the command returns `0` regardless of `failed` rows. Extend `EXIT_CODES` with the `5` clause and the "a per-issue failure is still 0" sentence, so `getup intake --help` documents it. `cli.main` dispatches it like the existing commands; no new import-time network, no token read at import.

- [ ] **Step 4: Run and confirm it passes** — `python3 -m unittest discover -s tests_py`

- [ ] **Step 5: Commit** — `git add tools/getup/cli.py tools/getup/intake.py tests_py/test_cli.py && git commit -m "feat(intake): daily poll command with its own exit code"`

---

## Final Check

- [ ] `python3 -m unittest discover -s tests_py` — 205 + new, all green.
- [ ] `node --test` — 134 + new, all green.
- [ ] `git status` clean apart from the intended files; `data/human.json` is `{}` unless a real issue was ingested.
- [ ] No test touches `api.github.com` (`grep -rn "api.github.com" tests_py` only shows the assertion in `test_github.py`).

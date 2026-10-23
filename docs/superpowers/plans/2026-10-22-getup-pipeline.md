# GetUp Pipeline Implementation Plan

**Status: executed** — the pipeline, in the same merged history `0506b55..d552d02`.
Final: **284** Python tests (`python3 -m unittest discover -s tests_py`), 2 live-gated,
all passing. Task bodies below are the plan as written, not a report.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A stdlib-only Python pipeline that scans the first three sources, normalizes, dedups, derives every signal the client reads, and writes `data/YYYY-MM-DD.json`, `data/index.json` and `venue/venues.json` byte-identically on every re-run — on an Android phone with no pip and no state store. A broken adapter is reported, never fatal: the portal must not go dark because one source changed shape.

**Architecture:** One package, `tools/getup/`, one responsibility per module. Sources enter as `Draft` dicts through a one-function adapter table; everything after that is pure functions over lists of dicts until `write.py`, which owns the only bytes-related code. `build.py` is the single impure orchestrator and knows the order; `cli.py` is argv only. All network calls take an injectable `fetch`, and cassette mode (`--from-dir`) makes no network call at all, so every test runs offline.

**Tech Stack:** Python 3.14 on the phone (stdlib only: `json`, `zoneinfo`, `urllib.request`, `xml.etree.ElementTree`, `html.parser`, `hashlib`, `logging`, `compression.zstd`/`compression.lzma`, `lzma`), Python 3.12 on the dev box, `unittest`. No pip, no venv, no requirements file.

**Spec:** docs/superpowers/specs/2026-10-18-getup-design.md

## Global Constraints

- **Stdlib only.** No third-party import anywhere, including tests. No `requirements.txt`, no `pip install` in any step.
- **The client is the contract.** `src/` reads exactly these event fields: `id, day, start, end, title, venue_id, city, price_from, soldout, free, free_until, format, expensive, commitment, notable, desc, urls{tickets,community,source}, notes[], scene[], crowd[], enrichment[], lat, lon, drive_min, drive_approx`. `price_max` is emitted for spec §7.2 and read by nothing. `seen` is emitted, read by nothing, and is the only way `seen.first` survives a re-run. **`daypart` is not emitted at all** — no client code reads it, and a derived field nobody reads is a lie you maintain. `lat`, `lon` and `drive_min` are nullable: an event whose venue has no geocode is still published with all three `null`. `drive_approx` is always a boolean: `true` exactly when `drive_min` came from the city-centroid shortcut (`coords_source` is `geo.SHORTCUT`), `false` for a real venue geocode or for no minutes at all; the client prints the minutes with a `~` when it is true.
- **Record shape.** `normalizeEvent` (`src/data.js`) spreads unknown keys and then coerces: every numeric field must be a finite number or absent, `free` must be exactly `true`, `scene/crowd/notes/enrichment` must be arrays of strings. A record that violates this is a bug here, not a bug there. Source categories (`tags`) are internal and never reach a date file.
- **Byte rules.** Every JSON file: `json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True)` plus one trailing `\n`. No event field may hold a generation time; `generated_at` (`%Y-%m-%dT%H:%M:%SZ`) exists only in `data/index.json`.
- **Time.** `Asia/Jerusalem` via `zoneinfo.ZoneInfo`; never a fixed offset. `import zoneinfo` failing must abort the run with one clear line, never fall back to UTC. An event buckets to its start's local date, except a start at 00:00–05:59 which buckets to the previous day.
- **Windows.** Read the full source payload (Leaan reaches +303 days) for touring only. `SERVE_DAYS = 30`; the served horizon is exactly the 30 consecutive dates `today … today + SERVE_DAYS - 1` and nothing outside it is stored. Raw retention 90 days. Coverage lookback 14 days.
- **Trust boundary, and failure.** Every source field is untrusted. A record that fails validation is dropped with exactly one `logging.getLogger('getup').warning(...)` naming source and source_id. Nothing half-formed is ever written. A source that fails, returns zero events or returns a scalar where a list belongs is recorded in `data/index.json` under `sources` with status `partial`/`failed`; the run still writes the other sources' data and exits non-zero. **A run with any non-ok source prunes nothing and archives nothing** — it can never delete a future day or an old one. The build still writes the sources that did answer, and a run where every requested source failed writes no day file at all and only refreshes the index with the failures, so a total outage cannot blank the portal.
- **Coordinates belong to the registry.** `venue/venues.json` owns `lat`, `lon` and a cached `drive_min` (venue point → Netanya). The build copies those three values **and the entry's `coords_source`**, so `normalize.record` can set `drive_approx: true` for a city-centroid minute. A venue whose city is in the committed capture gets that city's centroid and minutes, with `coords_source` naming the shortcut; a venue the capture cannot place, or one with no cached minutes, publishes `drive_min: null` (plus `lat: null`, `lon: null` when it has no point) — never an invented drive time — and each served record it produces is counted under `unpinned` in `data/index.json`.
- **Every reader enumerates `data/` through `write.data_files`.** One regex, one place; `labels.json` and `index.json` are never day files.
- **Hebrew.** Source Hebrew text is stored verbatim (never translated, never transliterated). The only new Hebrew strings are the notes prefixes in Task 12.
- **`node --test` stays green.** The existing 128 client tests plus the two this plan adds (Task 9) are the acceptance suite for this pipeline's output.
- **Cassette mode.** With `--from-dir` no network call is made at all: no geocoding, no router, and the registry is used exactly as committed. `pending` never geocodes either.
- Dev box runs Python 3.12; `compression.*` (PEP 784) exists only on 3.14. Every 3.14-only path is behind an import guard with a 3.12 fallback, so `python3 -m unittest` passes on both.

## Review Focus

The spec implies these and no task's happy path exercises them. Each has a test pinned to the owning task.

1. **A source returns a scalar, drops a path, or returns zero because its page shape changed** — detection is a warning plus a `failed`/`partial` status in the index, never an empty day and never a crash. (Tasks 2, 3, 4, 5, 15)
2. **An event with no venue** — Popit publishes `מיקום לא ידוע` and bare streets. A record with no resolvable venue is dropped with a warning and counted as `dropped_no_venue`, because the client requires a `venue_id` that exists. (Tasks 4, 8, 15)
3. **Two spellings of one city** — `קרית`/`קריית`, `מודיעין`/`מודיעין מכבים רעות`, `תל אביב`/`תל אביב-יפו`, `נתב"ג`/`איירפורט סיטי`/`קרית שדה התעופה`, plus `היכל התרבות` in 17 cities. One spelling must not become two venues or two cities. (Task 6)
4. **An event with no coordinates** — it publishes with null minutes, is counted under `unpinned`, no longer poisons the client's `/table` batch, and still renders `זמן נסיעה לא ידוע`. (Tasks 7, 8, 9, 15)
5. **A re-run that must be byte-identical** — cassette mode, a pre-seeded registry, `seen.first` read back from the committed files, and records nobody classified yet. (Task 15)
6. **A half-formed record** — a missing start, an absurd start (`1e16`), an end 145 days after the start, a 1200-character description. (Task 8)
7. **A Popit item with no place clause** — the title suffix is the only clue, its URL is a slug rather than `/event/<id>`, and `מיקום לא ידוע` means drop, not guess. (Task 4)

---

## File Structure

| File | Responsibility |
|---|---|
| `tools/getup/__init__.py` | Package marker. No code. |
| `tools/getup/write.py` | Canonical JSON bytes, atomic write, change detection, day/index/labels paths, day-file enumeration, internal-key stripping, stale-future pruning. The only module that touches `json.dumps`. |
| `tools/getup/scan.py` | Adapter table, payload fetching, per-source counts, statuses and failures. |
| `tools/getup/adapters/__init__.py` | `ADAPTERS` — the one line a fourth source adds. |
| `tools/getup/adapters/leaan.py` | `__NEXT_DATA__` extraction, ticket-seller drafts. |
| `tools/getup/adapters/popit.py` | RSS items, Hebrew prose date and clock, place hint, title-suffix place. |
| `tools/getup/adapters/biluim.py` | HTML listing cards, aggregator drafts. |
| `tools/getup/venues.py` | Registry load/save, alias index, city collapse, `resolve`, provisional entries. |
| `tools/getup/geo.py` | Nominatim geocode (1 req/s, cached in the registry), OSRM minutes from Netanya, city-capture seed. |
| `tools/getup/normalize.py` | `Draft` → record: `norm_title`, id, bucket day, end-span, desc cap, validation, drop warning. |
| `tools/getup/dedup.py` | §7.4 merge by venue and ±30 min, seller ownership, enrichment. |
| `tools/getup/classify.py` | Closed vocabulary, label cache in `data/labels.json`, pending batch, sanitizing, deterministic fallback. |
| `tools/getup/derive.py` | `expensive`, `commitment`, `notable`, `free_until`, touring, venue-fact projection into `notes`. |
| `tools/getup/coverage.py` | 14-day major-venue alarm from `seen.last`, over committed day files and archive members. |
| `tools/getup/manifest.py` | The one owner of `data/index.json`: dates, counts, source statuses, `unpinned`, `dropped_no_venue`, coverage. |
| `tools/getup/archive.py` | 90-day roll into `archive/YYYY-MM.json.zst` (zstd, else lzma). |
| `tools/getup/build.py` | The order: scan → venues → geo → normalize → dedup → classify → trim → derive → seen → write → coverage → archive. |
| `tools/getup/cli.py` | `build`, `pending`, `labels`, `archive`, `coverage` subcommands and exit codes. |
| `tools/getup/__main__.py` | `sys.exit(cli.main(sys.argv[1:]))`, so the daily command is `python3 -m tools.getup build`. |
| `src/distance.js` | `/table` batching; skips events without coordinates instead of refusing the batch. |
| `tests_py/__init__.py` | Package marker so `python3 -m unittest tests_py.test_x` works. |
| `tests_py/test_*.py` | One module per unit, plus `test_build.py` for the end-to-end run on the committed research capture. |
| `tests/distance.test.js`, `tests/format.test.js` | Client tests for the unpinned path and the unknown-drive label. |
| `data/labels.json` | Classification cache, committed. Read by `build`, written only by the `labels` command. Not in the manifest, so the client never fetches it. |
| `build/` | Gitignored scratch: fetched payloads, pending batch, model replies. |

---

### Task 1: Package skeleton, the canonical writer and the day-file helper

**Files:**
- Create: `tools/getup/__init__.py`, `tools/getup/write.py`, `tests_py/__init__.py`, `tests_py/test_write.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces:
  - `dumps(obj) -> str` — canonical text, one trailing `\n`
  - `write_json(path: str, obj) -> bool` — atomic; `True` only when the bytes changed
  - `write_bytes(path: str, data: bytes) -> bool` — the same atomic path for compressed archives
  - `read_json(path: str, default=None)` — returns `default` on a missing or unreadable file, never raises
  - `read_json_strict(path: str)` — raises on a missing or corrupt file; the archive and history readers use it
  - `date_file(root, day) -> str`, `index_file(root) -> str`, `labels_file(root) -> str`
  - `data_files(dirpath: str) -> list[str]` — **the only** day-file enumerator: sorted dates matching `^\d{4}-\d{2}-\d{2}\.json$`
  - `write_days(root: str, by_day: dict[str, list]) -> list[str]` — strips `INTERNAL_KEYS` from every record before serialising
  - `INTERNAL_KEYS = frozenset({'tags'})`
  - `prune_future(root: str, keep: set[str], today: str) -> list[str]` — deletes day files dated after `today` that are not in `keep`, enumerated through `data_files`
  - `utc_now() -> str` — `'2026-10-22T04:15:00Z'`

- [ ] **Step 1: Write the failing tests**

```python
# tests_py/test_write.py
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
```

- [ ] **Step 2: Run it and confirm it fails** — `python3 -m unittest tests_py.test_write -v` → `ModuleNotFoundError: tools`

- [ ] **Step 3: Implement the writer** — `os.makedirs(os.path.dirname(path), exist_ok=True)`, write to `path + '.tmp'` in the same directory, `os.replace`; compare the new text against the file's current text and skip the write when equal. `data_files` is one `os.listdir` plus the day regex; `prune_future` and every later reader call it rather than repeating the regex. `write_days` copies each record minus `INTERNAL_KEYS`. Add `build/` to `.gitignore`.

- [ ] **Step 4: Run and confirm it passes** — `python3 -m unittest tests_py.test_write -v`

- [ ] **Step 5: Commit** — `git add tools tests_py .gitignore && git commit -m "feat(pipeline): canonical byte-stable JSON writer"`

---

### Task 2: Transport and per-source failure handling

**Files:**
- Create: `tools/getup/scan.py`, `tools/getup/adapters/__init__.py`, `tests_py/test_scan.py`

**Interfaces:**
- Produces:
  - **`Draft`** — `{source, class, source_id, title, venue, city, street, start, end, price_from, price_max, soldout, desc, url, tags, venue_id, lat, lon, drive_min}`. `class` is `'ticketing'|'nightlife'|'aggregator'`; `tags` is a list of raw source category strings; any field may be `None`. Adapters fill the source-side keys only; `venue_id`, `lat`, `lon`, `drive_min` are filled by the orchestration (Tasks 6, 7, 15).
  - **Adapter module contract** (what a fourth source must provide): `NAME: str`, `CLASS: str`, `CASSETTE: str`, `URLS: list[str]`, `parse(payload) -> list[Draft]`.
  - `ADAPTERS: dict[str, module]` in `adapters/__init__.py`
  - `fetch_text(url: str) -> str` — `urllib.request`, UA `getup/1.0 (+repo url)`, 20 s timeout, raises `FetchError`
  - `scan(names: list[str], *, fetch=fetch_text, adapters=ADAPTERS) -> tuple[list[Draft], dict[str, int], list[str], dict[str, str]]` — drafts, per-source counts, failure messages, per-source status in `{'ok', 'partial', 'failed'}`. `ok` means every URL fetched and at least one draft; `partial` means one URL failed but drafts exist; `failed` means every URL failed, zero drafts, or the parser raised. A broken source never raises out of `scan`; an unknown name raises `ValueError`.
  - `scan_from_dir(names: list[str], path: str, *, adapters=ADAPTERS) -> tuple[...]` — the same four values, reading `ADAPTERS[n].CASSETTE`; never calls `fetch`.

- [ ] **Step 1: Write the failing tests**

```python
# tests_py/test_scan.py
import os, tempfile, unittest
from tools.getup import scan

class Stub:
    NAME = 'stub'; CLASS = 'aggregator'; CASSETTE = 'stub.html'
    URLS = ['https://a', 'https://b']
    @staticmethod
    def parse(payload):
        if payload == 'boom':
            raise ValueError('page shape changed')
        return [{'source': 'stub', 'class': 'aggregator', 'source_id': payload,
                 'title': 't', 'venue': 'v', 'city': 'c', 'start': 1792780200}] if payload == 'ok' else []

def stub_scan(fetch, names=('stub',)):
    return scan.scan(list(names), fetch=fetch, adapters={'stub': Stub})

class StatusTest(unittest.TestCase):
    def test_every_url_answering_is_ok(self):
        drafts, counts, failures, status = stub_scan(lambda url, **k: 'ok')
        self.assertEqual((len(drafts), counts, failures, status),
                         (2, {'stub': 2}, [], {'stub': 'ok'}))

    def test_one_dead_url_is_partial_and_the_other_urls_still_produce_drafts(self):
        def fetch(url, **kw):
            if url.endswith('/a'):
                raise scan.FetchError('503')
            return 'ok'
        drafts, counts, failures, status = stub_scan(fetch)
        self.assertEqual(len(drafts), 1)
        self.assertEqual(status, {'stub': 'partial'})
        self.assertEqual(len(failures), 1)
        self.assertIn('stub', failures[0])

    def test_every_url_dead_is_failed_and_nothing_raises(self):
        def fetch(url, **kw):
            raise scan.FetchError('offline')
        drafts, counts, failures, status = stub_scan(fetch)
        self.assertEqual((drafts, counts, status), ([], {'stub': 0}, {'stub': 'failed'}))

    def test_a_parser_that_raises_is_a_failed_source_not_a_crash(self):
        drafts, counts, failures, status = stub_scan(lambda url, **k: 'boom')
        self.assertEqual((drafts, status), ([], {'stub': 'failed'}))
        self.assertIn('page shape changed', failures[0])

    def test_zero_events_from_working_urls_is_failed(self):
        drafts, counts, failures, status = stub_scan(lambda url, **k: 'empty')
        self.assertEqual(status, {'stub': 'failed'})

    def test_an_unknown_source_name_is_an_argument_error(self):
        with self.assertRaises(ValueError):
            scan.scan(['nope'])

class CassetteTest(unittest.TestCase):
    def test_cassette_mode_reads_the_file_and_never_touches_the_network(self):
        with tempfile.TemporaryDirectory() as root:
            open(os.path.join(root, 'stub.html'), 'w').write('ok')
            def boom(url, **kw):
                raise AssertionError(f'network call in cassette mode: {url}')
            drafts, counts, failures, status = scan.scan_from_dir(['stub'], root, adapters={'stub': Stub})
            self.assertEqual((len(drafts), status), (2, {'stub': 'ok'}))
```

- [ ] **Step 2: Run and confirm it fails** — `python3 -m unittest tests_py.test_scan -v`

- [ ] **Step 3: Implement** — `scan` iterates `names`, resolves the adapter, loops `URLS`, accumulates drafts, and catches `Exception` per source into `failures` with `f'{name}: {url}: {exc}'`. Status is computed from the URL tally and the draft count. `scan_from_dir` calls `parse` on the cassette text and reports `failed` when the file is missing. Neither function logs a warning of its own: parse ownership of shape warnings stays in the adapter, so each bad payload warns exactly once.

- [ ] **Step 4: Run and confirm it passes** — `python3 -m unittest tests_py.test_scan -v`

- [ ] **Step 5: Commit** — `git commit -m "feat(pipeline): adapter table and per-source failure handling"`

---

### Task 3: The Leaan parser

**Files:**
- Create: `tools/getup/adapters/leaan.py`, `tests_py/test_scan_leaan.py`
- Modify: `tools/getup/adapters/__init__.py`

**Interfaces:**
- Consumes: `Draft`, the adapter contract and `scan` from Task 2.
- Produces:
  - `leaan.extract_next_data(html: str) -> dict`
  - `leaan.parse(payload) -> list[Draft]` — accepts a bare event list, the raw `__NEXT_DATA__` dict (`{"props": ...}`), or an HTML string containing the script tag
  - `leaan.NAME/CLASS/CASSETTE/URLS`; registered in `ADAPTERS`

- [ ] **Step 1: Write the failing tests**

```python
# tests_py/test_scan_leaan.py
import json, os, unittest
from tools.getup import scan
from tools.getup.adapters import leaan

CAPTURE = 'docs/research/2026-10-21/leaan-events.json'

def events():
    return json.load(open(CAPTURE, encoding='utf-8'))

class ShapeTest(unittest.TestCase):
    def test_the_capture_is_a_bare_event_list(self):
        drafts = leaan.parse(events())
        self.assertEqual(len(drafts), 215)

    def test_the_raw_next_data_dict_is_accepted(self):
        payload = {'props': {'pageProps': {'initialState': {'pageData': {'events': events()}}}}}
        self.assertEqual(len(leaan.parse(payload)), 215)

    def test_an_html_page_is_read_through_the_script_tag(self):
        payload = ('<html><body><script id="__NEXT_DATA__" type="application/json">'
                   + json.dumps({'props': {'pageProps': {'initialState': {'pageData': {'events': events()}}}}}))
        payload += '</script></body></html>'
        self.assertEqual(len(leaan.parse(payload)), 215)

    def test_an_empty_event_list_is_a_quiet_zero(self):
        html = ('<html><body><script id="__NEXT_DATA__" type="application/json">'
                '{"props":{"pageProps":{"initialState":{"pageData":{"events":[]}}}}}'
                '</script></body></html>')
        with self.assertNoLogs('getup', level='WARNING'):
            self.assertEqual(leaan.parse(html), [])

    def test_a_changed_shape_warns_once_and_yields_no_events(self):
        with self.assertLogs('getup', level='WARNING') as logs:
            drafts = leaan.parse({'props': {'pageProps': {}}})
        self.assertEqual(drafts, [])
        self.assertEqual(len(logs.output), 1)
        self.assertIn('leaan', logs.output[0])
        self.assertIn('pageData.events', logs.output[0])

    def test_a_scalar_where_the_event_list_belongs_is_not_iterated_as_characters(self):
        payload = {'props': {'pageProps': {'initialState': {'pageData': {'events': 'nope'}}}}}
        with self.assertLogs('getup', level='WARNING'):
            self.assertEqual(leaan.parse(payload), [])

    def test_a_non_object_record_is_skipped_with_its_index(self):
        events_ = [{'event_id': 'a', 'title': 't', 'venue': 'v', 'city': 'c', 'start': 1792780200}, 7]
        payload = {'props': {'pageProps': {'initialState': {'pageData': {'events': events_}}}}}
        with self.assertLogs('getup', level='WARNING') as logs:
            drafts = leaan.parse(payload)
        self.assertEqual([d['source_id'] for d in drafts], ['a'])
        self.assertIn('leaan[1]', logs.output[0])

class DraftTest(unittest.TestCase):
    def test_the_real_capture_yields_215_ticket_seller_drafts(self):
        first = leaan.parse(events())[0]
        self.assertEqual((first['class'], first['source']), ('ticketing', 'leaan'))
        self.assertEqual(first['source_id'], '6a1be86c43116ffad6fea591')
        self.assertEqual(first['venue'], 'מרכז עזריאלי')
        self.assertEqual(first['city'], 'תל אביב')
        self.assertEqual(first['start'], 1780988400)
        self.assertEqual(first['tags'], ['הצגות והרצאות'])
        self.assertEqual(first['url'], 'https://www.leaan.co.il/event/6a1be86c43116ffad6fea591')

@unittest.skipUnless(os.environ.get('GETUP_LIVE') == '1', 'live source; set GETUP_LIVE=1')
class LeaanLiveTest(unittest.TestCase):
    def test_the_category_pages_still_answer_with_events(self):
        drafts, counts, failures, status = scan.scan(['leaan'])
        self.assertEqual((failures, status), ([], {'leaan': 'ok'}))
        self.assertGreater(counts['leaan'], 0)
```

- [ ] **Step 2: Run and confirm it fails** — `python3 -m unittest tests_py.test_scan_leaan -v`

- [ ] **Step 3: Implement** — dispatch on the payload type: `list` → events; `dict` → walk `props.pageProps.initialState.pageData.events`; `str` starting with `<` → one regex for `<script id="__NEXT_DATA__" ...>` then `json.loads`, else `json.loads` the string. A missing path, a non-list `events`, a non-object element (warn `leaan[<index>]`) and unparseable JSON each produce `[]` plus exactly one warning naming `leaan` and `pageData.events`; nothing below the list raises. `URLS` holds the three genre page URLs from the `israeli-events` skill; the source field names are `event_id,title,venue,city,street,start,end,price,multi_price,soldout,categories,desc,url`.

- [ ] **Step 4: Run and confirm it passes** — `python3 -m unittest tests_py.test_scan_leaan -v`

- [ ] **Step 5: Commit** — `git commit -m "feat(pipeline): Leaan drafts from three payload shapes"`

---

### Task 4: The Popit adapter

**Files:**
- Create: `tools/getup/adapters/popit.py`, `tests_py/test_popit.py`
- Modify: `tools/getup/adapters/__init__.py`

**Interfaces:**
- Consumes: `Draft` and the adapter contract from Task 2.
- Produces:
  - `popit.parse(payload: str) -> list[Draft]` — `CASSETTE = 'popit.xml'`, `CLASS = 'nightlife'`
  - `popit.parse_hebrew_when(text: str, published: datetime) -> int | None` — local unix seconds or `None`
  - `popit.place_from_title(title: str) -> tuple[str | None, str | None]` — `(venue, city)` from a ` — <place>` suffix
  - `PLACE_FIX: dict[str, tuple[str | None, str | None]]` — the observed English suffixes: `'Tel Aviv Port' → ('נמל תל אביב', 'תל אביב')`, `'Tel Aviv-Yafo' → (None, 'תל אביב')`, `'Petah Tikva' → (None, 'פתח תקווה')`, `'Rishon LeZion' → (None, 'ראשון לציון')`, `'Israel' → (None, None)`, `'HaSharon' → (None, None)`
  - `popit.NAME/CLASS/CASSETTE/URLS`; registered in `ADAPTERS`

- [ ] **Step 1: Write the failing tests**

```python
# tests_py/test_popit.py
import unittest
from datetime import datetime, timezone
from tools.getup.adapters import popit

XML = open('docs/research/2026-10-21/popit.xml', encoding='utf-8').read()

def drafts():
    return {d['source_id']: d for d in popit.parse(XML)}

class PopitTest(unittest.TestCase):
    def test_a_real_item_carries_venue_city_clock_and_its_slug_url(self):
        d = drafts()['2315']                              # "…ב-14 בנובמבר בשעה 14:00"
        self.assertEqual(d['class'], 'nightlife')
        self.assertEqual((d['venue'], d['city']), ('Altalena St 8', 'ראשון לציון'))
        self.assertEqual(d['start'], 1794657600)          # 2026-11-14 14:00 Asia/Jerusalem
        self.assertEqual(d['url'], 'https://popit.events/event/urban-music-14-11-2315')
        self.assertNotEqual(d['url'], 'https://popit.events/event/2315')

    def test_the_publication_date_is_never_used_as_the_start(self):
        # 2303 was published 2026-10-19 and starts 2026-10-24 22:00, five days later
        published = 1792426896                               # 2026-10-19T16:21:36Z
        self.assertGreater(drafts()['2303']['start'], published + 86400)

    def test_an_item_with_no_clock_has_no_start_rather_than_a_guess(self):
        self.assertIsNone(drafts()['2309']['start'])       # "ב-21 באוקטובר" with no שעה

    def test_a_street_suffix_is_the_venue(self):
        d = drafts()['2303']                              # no place clause, "— ברוך קטינקא 2"
        self.assertEqual(d['venue'], 'ברוך קטינקא 2')
        self.assertEqual(d['start'], 1792868400)          # 2026-10-24 22:00

    def test_an_english_place_suffix_is_mapped_to_hebrew(self):
        self.assertEqual(popit.place_from_title('DARWISH — Tel Aviv Port'),
                         ('נמל תל אביב', 'תל אביב'))

    def test_a_city_suffix_gives_a_city_and_never_invents_a_venue(self):
        self.assertEqual(popit.place_from_title('FUEGO — Tel Aviv-Yafo'), (None, 'תל אביב'))

    def test_an_unknown_location_keeps_the_title_and_names_no_venue(self):
        d = drafts()['2263']                              # "— Israel (מיקום לא ידוע)"
        self.assertIsNone(d['venue'])
        self.assertIsNone(d['city'])

    def test_a_month_that_wraps_into_january_belongs_to_the_next_year(self):
        published = datetime(2026, 12, 30, 12, tzinfo=timezone.utc)
        self.assertEqual(popit.parse_hebrew_when('מסיבה ב-2 בינואר בשעה 23:00', published),
                         1798923600)                    # 2027-01-02 23:00 Asia/Jerusalem

    def test_a_feed_with_no_items_warns_instead_of_reporting_a_quiet_night(self):
        with self.assertLogs('getup', level='WARNING') as logs:
            self.assertEqual(popit.parse('<rss><channel></channel></rss>'), [])
        self.assertIn('popit', logs.output[0])
```

- [ ] **Step 2: Run and confirm it fails** — `python3 -m unittest tests_py.test_popit -v`

- [ ] **Step 3: Implement** — `xml.etree.ElementTree.fromstring`, one `Draft` per `<item>`; `source_id` is `<guid>` (`'2315'`), `url` is `<link>` byte-for-byte (it is already a slug), `entry` href is the same link. Venue and city come from the description's `ב<venue>, <city>,` clause, with a leading `-` stripped from the capture (`ב-Altalena St 8` → `Altalena St 8`). The venue begins at the first word-initial `ב` **after** the `היא מסיבת …` phrase, so `במרכז ביאליק` keeps its `מ` instead of truncating to `יאליק`; the last-`ב` rule is dead. When the clause is absent, `place_from_title` takes the text after the last `—`, drops a trailing `(מיקום לא ידוע)`, maps it through `PLACE_FIX`, and falls back to `(suffix, None)` — a bare Hebrew street stays a venue. A `(מיקום לא ידוע)` marker always means `venue: None`, and the build drops that draft. A title suffix that `place_from_title` consumes is also stripped from the title, or every served record shows the venue twice. A city containing a digit is not a city (`2254` writes the street into the city slot): the adapter emits `city: None`, and Task 6 owns the identity rule for unknown cities. `parse_hebrew_when` combines the `ב-DD ב<month>` date, the first `HH:MM` clock, and the year from `pubDate` with a +1 roll when the parsed month precedes it by **six or more** months. `בחצות` is not a clock: `2229`'s New Year prose would otherwise publish a 31 December party at midnight (~21 h early), so a date with no `HH:MM` keeps `start: None` and `normalize.record` drops it. The adapter looks `Asia/Jerusalem` up lazily inside the parse helpers (`_tz()`), so importing the package never needs tzdata; Task 8 owns the `RuntimeError` contract.

- [ ] **Step 4: Run and confirm it passes** — `python3 -m unittest tests_py.test_popit -v`

- [ ] **Step 5: Commit** — `git commit -m "feat(pipeline): Popit RSS adapter with place fallback and slug URLs"`

---

### Task 5: The Biluim adapter

**Files:**
- Create: `tools/getup/adapters/biluim.py`, `tests_py/test_biluim.py`
- Modify: `tools/getup/adapters/__init__.py`

**Interfaces:**
- Consumes: `Draft`, the adapter contract and `scan` from Task 2.
- Produces:
  - `biluim.parse(payload: str) -> list[Draft]` — `CASSETTE = 'biluim.html'`, `CLASS = 'aggregator'`
  - `URLS = ['https://biluim.co.il/events/tel-aviv']` — the listing proven to carry these cards; `/events` returned none of this shape
  - `biluim.CardParser` — `html.parser.HTMLParser` subclass
  - `biluim.NAME/CLASS/CASSETTE/URLS`; registered in `ADAPTERS`

- [ ] **Step 1: Write the failing tests**

```python
# tests_py/test_biluim.py
import os, unittest
from tools.getup import scan
from tools.getup.adapters import biluim

# A synthetic card in the shape the skill's recipe documents; the real markup is not in the
# capture, so the live test below is what proves the recipe still holds.
HTML = '''<ul class="events"><li class="event">
  <a href="/event/123" class="title">ערב ג׳אז בבית יד לבנים</a>
  <span class="venue">בית יד לבנים</span><span class="city">רעננה</span>
  <time datetime="2026-10-29T20:30">29.10</time>
  <span class="price">₪80</span><p class="desc">רביעיית ג׳אז</p></li></ul>'''

class BiluimTest(unittest.TestCase):
    def test_a_card_becomes_an_aggregator_draft(self):
        [d] = biluim.parse(HTML)
        self.assertEqual(d['class'], 'aggregator')
        self.assertEqual(d['source_id'], '/event/123')
        self.assertEqual((d['venue'], d['city']), ('בית יד לבנים', 'רעננה'))
        self.assertEqual(d['start'], 1793298600)          # 2026-10-29 20:30 Asia/Jerusalem
        self.assertEqual(d['price_from'], 80)
        self.assertEqual(d['desc'], 'רביעיית ג׳אז')

    def test_markup_that_no_longer_matches_warns_and_yields_nothing(self):
        with self.assertLogs('getup', level='WARNING') as logs:
            self.assertEqual(biluim.parse('<html><body><div>new site</div></body></html>'), [])
        self.assertIn('biluim', logs.output[0])

@unittest.skipUnless(os.environ.get('GETUP_LIVE') == '1', 'live source; set GETUP_LIVE=1')
class BiluimLiveTest(unittest.TestCase):
    def test_the_listing_still_answers_with_cards(self):
        drafts, counts, failures, status = scan.scan(['biluim'])
        self.assertEqual((failures, status), ([], {'biluim': 'ok'}))
        self.assertGreater(counts['biluim'], 0)
```

- [ ] **Step 2: Run and confirm it fails** — `python3 -m unittest tests_py.test_biluim -v`

- [ ] **Step 3: Implement** — the skill's `li.event` recipe is dead: the live `/events/tel-aviv` page has zero `<li>` and 66 Tailwind cards, and the committed 3-card capture (`docs/research/2026-10-22/biluim-tlv-excerpt.html`, installed as the cassette `biluim.html`) is the shape to parse. `CardParser` opens on an `article` whose class tokens contain `group` and closes on its matching `</article>` (not a bare depth counter); the card's `a[href^="/events/e/"]` is `source_id` (raw href) and `url` (`urljoin('https://biluim.co.il', href)`). Title is `h3.font-extrabold` text, falling back to that link's `aria-label`; start is the card's `time[datetime]` through `datetime.fromisoformat` (aware values converted, naive values attached to `Asia/Jerusalem` lazily via `_tz()`); venue is the first `a[href^="/events/venues/"]` text, else the map-pin `span.truncate` (the clock-row span has no `truncate`); price is `span.glass.tabular-nums` (`חינם` → 0, first integer → `price_from`, the integer after `עד` → `price_max`, absent → both `None`); tags is the first `span.glass.rounded-full` without `tabular-nums`; `city`/`street`/`desc` stay `None` — the TLV listing carries a Golan venue, so the listing path is never a city. Void tags (`br`, `img`, `input`, `hr`, `wbr`, `meta`, `link`, `source`) are excluded from depth accounting because `HTMLParser` never emits their end tag; one `<br>` used to swallow every later card. Zero cards plus a non-empty page is one warning naming `biluim`. The test asserts the three real cards field by field, keeps the old `li.event` shape as a shape-change negative, and pins the `<br>` case.

- [ ] **Step 4: Run and confirm it passes** — `python3 -m unittest tests_py.test_biluim -v`

- [ ] **Step 5: Commit** — `git commit -m "feat(pipeline): Biluim HTML adapter"`

---

### Task 6: Venue registry and identity

**Files:**
- Create: `tools/getup/venues.py`, `tests_py/test_venues.py`

**Interfaces:**
- Consumes: `write.read_json`, `write.write_json` (Task 1).
- Produces:
  - `CITY_FIX: dict[str, str]` — a data-driven dict seeded with the variants this capture actually contains: `'מודיעין': 'מודיעין מכבים רעות'`, `'תל אביב-יפו': 'תל אביב'`, `'איירפורט סיטי': 'נתב"ג'`, `'קרית שדה התעופה': 'נתב"ג'`, `'פתח תקוה': 'פתח תקווה'`
  - `norm_city(city: str) -> str` — collapse whitespace, strip niqqud, unify quotes, then `CITY_FIX`; a leading `קרית ` becomes `קריית ` so that whole family collapses without one dict entry per city
  - `norm_name(name: str) -> str`, `norm_name_loose(name: str) -> str` — collapse whitespace, `־`/`-`→space, straight/curly quotes unified, geresh unified, niqqud stripped; the loose form also drops punctuation and any `(...)`
  - `strip_city_suffix(venue: str, city: str | None) -> str` — removes a trailing `, <city>` before normalising
  - `load(root) -> dict[str, dict]`, `save(root, registry) -> bool`
  - `alias_index(registry) -> dict[tuple[str, str], str]`
  - `resolve(registry, venue, city) -> str | None` — the registry id; mutates `registry` when it must provision; `None` when there is no usable name, because a city alone cannot identify a hall (that draft is dropped and counted)
  - Unknown cities: a city string containing a digit is a street that leaked into the city slot (`2254`'s `שדרות שאול המלך 2 בתל אביב`), and the adapter already nulls it. `norm_city` must leave any other unrecognised city unrecognised — never provision a city from it — and `resolve` must fall back to name-only identity for a venue whose city is unknown rather than inventing one.
  - `provisional_id(name, city) -> str` — `'v_' + sha1(f'{norm_name(name)}|{norm_city(city)}')[:10]`

- [ ] **Step 1: Write the failing tests**

```python
# tests_py/test_venues.py
import unittest
from tools.getup import venues

ROOT = '.'

class CityTest(unittest.TestCase):
    def test_the_observed_spellings_collapse_to_one_city(self):
        self.assertEqual(venues.norm_city('קרית ביאליק'), venues.norm_city('קריית ביאליק'))
        self.assertEqual(venues.norm_city('מודיעין'), venues.norm_city('מודיעין מכבים רעות'))
        self.assertEqual(venues.norm_city('תל אביב-יפו'), venues.norm_city('תל אביב'))
        self.assertEqual(venues.norm_city('איירפורט סיטי'), venues.norm_city('נתב"ג'))
        self.assertEqual(venues.norm_city('קרית שדה התעופה'), venues.norm_city('נתב"ג'))
        self.assertEqual(venues.norm_city('פתח תקוה'), venues.norm_city('פתח תקווה'))

class ResolveTest(unittest.TestCase):
    def setUp(self):
        self.reg = venues.load(ROOT)

    def test_one_hall_name_resolves_per_city(self):
        rishon = venues.resolve(self.reg, 'היכל התרבות', 'ראשון לציון')
        petah = venues.resolve(self.reg, 'היכל התרבות', 'פתח תקוה')
        self.assertEqual(rishon, 'v_heichal_tarbut_rishon')
        self.assertEqual(petah, 'v_heichal_tarbut_petah_tikva')   # spelling collapse
        self.assertNotEqual(rishon, petah)

    def test_an_alias_resolves_to_its_venue(self):
        self.assertEqual(venues.resolve(self.reg, 'Zionist America House', 'תל אביב'),
                         'v_zionist_america_tlv')
        self.assertEqual(venues.resolve(self.reg, 'היכל התרבות ספי ריבלין, קריית השרון', 'נתניה'),
                         'v_heichal_spi_rivlin_netanya')

    def test_a_city_suffix_on_the_source_venue_does_not_create_a_second_venue(self):
        with_suffix = venues.resolve(self.reg, 'בית ציוני אמריקה (מאירהוף), תל אביב', 'תל אביב')
        bare = venues.resolve(self.reg, 'בית ציוני אמריקה (מאירהוף)', 'תל אביב')
        self.assertEqual(with_suffix, bare)
        self.assertTrue(with_suffix.startswith('v_'))

    def test_punctuation_and_parentheses_are_only_a_second_try(self):
        first = venues.resolve(self.reg, 'מועדון ״הבימה״', 'תל אביב')
        second = venues.resolve(self.reg, 'מועדון הבימה', 'תל אביב')
        self.assertEqual(first, second)

    def test_an_unseen_venue_gets_one_stable_provisional_entry(self):
        a = venues.resolve(self.reg, 'מועדון חדש לגמרי', 'חיפה')
        b = venues.resolve(self.reg, 'מועדון חדש לגמרי', 'חיפה')
        self.assertEqual(a, b)
        self.assertTrue(a.startswith('v_'))
        self.assertEqual(self.reg[a]['tier'], 'room')       # never major: no alarm noise
        self.assertIsNone(self.reg[a]['lat'])               # flagged, not silently pinned

    def test_a_bare_street_with_a_city_still_has_identity(self):
        self.assertIsNotNone(venues.resolve(self.reg, 'Nisim Elkayam St 10', 'באר שבע'))

    def test_no_name_and_no_city_is_no_venue(self):
        self.assertIsNone(venues.resolve(self.reg, None, None))
        self.assertIsNone(venues.resolve(self.reg, '   ', ''))
```

- [ ] **Step 2: Run and confirm it fails** — `python3 -m unittest tests_py.test_venues -v`

- [ ] **Step 3: Implement** — `resolve` first strips a trailing `, <city>` from the source venue, then looks `(norm_name, norm_city)` up in a fresh alias index; on a miss it retries with `(norm_name_loose, norm_city)`; on a second miss it retries `(norm_name, '')` for registry entries whose aliases omit the city; only then does it provision. A provisional entry is `{id, name, aliases: [], city, lat: None, lon: None, drive_min: None, coords_source: 'unresolved', tier: 'room', parking: None, access: None, transport: None, social: {instagram: None, facebook: None}}` — that is the record the capture is expected to produce about ninety of, and `tier: 'room'` keeps them out of the coverage alarm. `save` sorts through `write.write_json`.

- [ ] **Step 4: Run and confirm it passes** — `python3 -m unittest tests_py.test_venues -v`

- [ ] **Step 5: Commit** — `git commit -m "feat(pipeline): venue registry, city collapse and provisional identity"`

---

### Task 7: Geocoding and cached drive minutes

**Files:**
- Create: `tools/getup/geo.py`, `tests_py/test_geo.py`

**Interfaces:**
- Consumes: `venues.load/save/norm_city` (Task 6), `scan.fetch_text` (Task 2).
- Produces:
  - `RateLimiter(min_interval: float = 1.0, *, clock=time.monotonic, sleep=time.sleep)`, `.wait() -> None`
  - `geocode(venue: str, city: str, *, fetch, limiter=None) -> tuple[float, float] | None` — Nominatim `q="venue, city"`, `countrycodes=il`, `format=json`, `limit=1`
  - `drive_minutes(dest: tuple[float, float], origin=(32.3286, 34.8566), *, fetch) -> int | None` — OSRM route, `round(duration/60)`; `None` on any failure, never raises
  - `fill(registry: dict, *, fetch=scan.fetch_text, limiter=None, warn=None) -> tuple[dict, int, int]` — mutates coords and `drive_min` only where they are `None`; returns `(registry, geocoded, failed)`. It never writes a city centroid: no geocode means the entry stays `lat: None, lon: None, drive_min: None, coords_source: 'unresolved'`.
  - `CITY_CAPTURE = 'docs/research/2026-10-21/geo-drive.json'` — the committed capture: 29 city geocodes plus OSRM minutes from Netanya, `{'geo': {city: [lat, lon]}, 'drive': {city: {km, min}}}`
  - `seed(registry: dict, path: str = CITY_CAPTURE) -> int` — fills `lat`/`lon`/`drive_min` from the venue's city only where each is missing; sets `coords_source` to `SHORTCUT` when it supplies the point; returns the number of entries it pinned. A Nominatim point and a cached duration are never replaced.
  - `SHORTCUT = 'shortcut: city centroid, upgrade when venue geocodes exist'` — the `coords_source` every seeded entry carries
  - Cache note on the venue: `shortcut: minutes are from Netanya and cached at the venue; upgrade when a second origin is needed`

- [ ] **Step 1: Write the failing tests**

```python
# tests_py/test_geo.py
import unittest
from tools.getup import geo, venues

NOMINATIM = '[{"lat":"32.0771","lon":"34.7753"}]'
OSRM = '{"code":"Ok","routes":[{"duration":1740}]}'

def fake(responses, counter=None):
    def fetch(url, **kw):
        if counter is not None:
            counter.append(url)
        return responses.get('nominatim' if 'nominatim' in url else 'osrm')
    return fetch

def reg(**o):
    return {'v_x': {'id': 'v_x', 'name': 'מועדון', 'aliases': [], 'city': 'חיפה',
                    'lat': None, 'lon': None, 'drive_min': None, 'tier': 'room',
                    'coords_source': 'unresolved', 'parking': None,
                    'access': None, 'transport': None, 'social': {}, **o}}

class GeoTest(unittest.TestCase):
    def test_a_venue_with_coordinates_is_never_geocoded_again(self):
        calls = []
        geo.fill(venues.load('.'), fetch=fake({'nominatim': NOMINATIM, 'osrm': OSRM}, calls))
        self.assertFalse([u for u in calls if 'nominatim' in u])   # every fixture venue has a point

    def test_a_missing_point_is_geocoded_once_and_a_missing_duration_is_cached(self):
        registry, geocoded, failed = geo.fill(reg(), fetch=fake({'nominatim': NOMINATIM, 'osrm': OSRM}))
        self.assertEqual((geocoded, failed), (1, 0))
        self.assertEqual((registry['v_x']['lat'], registry['v_x']['lon']), (32.0771, 34.7753))
        self.assertEqual(registry['v_x']['drive_min'], 29)

    def test_a_venue_that_does_not_geocode_stays_null_and_carries_no_centroid(self):
        warnings = []
        registry, geocoded, failed = geo.fill(reg(), fetch=fake({'nominatim': '[]'}),
                                              warn=warnings.append)
        self.assertEqual((geocoded, failed), (0, 1))
        self.assertEqual((registry['v_x']['lat'], registry['v_x']['drive_min']), (None, None))
        self.assertEqual(registry['v_x']['coords_source'], 'unresolved')
        self.assertEqual(len(warnings), 1)
        self.assertIn('מועדון', warnings[0])

    def test_an_unreachable_router_is_none_not_zero_minutes(self):
        self.assertIsNone(geo.drive_minutes((32.1, 34.8), fetch=lambda url, **k: '{"code":"NoRoute"}'))
        def boom(url, **kw): raise OSError('offline')
        self.assertIsNone(geo.drive_minutes((32.1, 34.8), fetch=boom))
        self.assertIsNone(geo.geocode('x', 'y', fetch=boom))

    def test_nominatim_is_called_at_most_once_per_second(self):
        sleeps, now = [], [0.0]
        lim = geo.RateLimiter(1.0, clock=lambda: now[0], sleep=lambda s: (sleeps.append(s), now.__setitem__(0, now[0] + s)))
        lim.wait(); lim.wait()
        self.assertEqual(len(sleeps), 1)
        self.assertAlmostEqual(sleeps[0], 1.0)

class SeedTest(unittest.TestCase):
    def test_the_city_capture_supplies_the_point_and_the_minutes(self):
        registry = reg(city='ראשון לציון')
        self.assertEqual(geo.seed(registry), 1)
        self.assertEqual((registry['v_x']['lat'], registry['v_x']['lon']), (31.9635712, 34.8101149))
        self.assertEqual(registry['v_x']['drive_min'], 42)
        self.assertEqual(registry['v_x']['coords_source'],
                         'shortcut: city centroid, upgrade when venue geocodes exist')

    def test_a_geocoded_point_and_its_minutes_are_never_replaced(self):
        registry = reg(city='חיפה', lat=32.8, lon=34.9, drive_min=61, coords_source='nominatim')
        self.assertEqual(geo.seed(registry), 0)
        self.assertEqual((registry['v_x']['lat'], registry['v_x']['drive_min']), (32.8, 61))

    def test_a_city_the_capture_does_not_know_stays_unpinned(self):
        registry = reg(city='גבעת ברנר')
        self.assertEqual(geo.seed(registry), 0)
        self.assertEqual((registry['v_x']['lat'], registry['v_x']['drive_min']), (None, None))
```

- [ ] **Step 2: Run and confirm it fails** — `python3 -m unittest tests_py.test_geo -v`

- [ ] **Step 3: Implement** — `fill` walks the registry once, geocodes only `lat is None` entries through the limiter, sets `coords_source` truthfully (`'nominatim'` on success, `'unresolved'` plus one warning naming the venue on failure), caches `drive_min` once per venue, and never re-requests a value it has. `seed` reads `CITY_CAPTURE` once, indexes both its maps by `venues.norm_city`, and copies `lat`/`lon`/`drive_min` into each registry entry whose city is known and whose value is still `None` — `coords_source: SHORTCUT` when the point comes from the capture, untouched otherwise. Then seed the committed registry in place, so `venue/venues.json` gains a `drive_min` for every city the capture knows before the first cassette run: `python3 -c "from tools.getup import geo, venues; r = venues.load('.'); geo.seed(r); venues.save('.', r)"`. Every network call is a single `fetch` callable. Cassette mode never calls `fetch`, but it still runs `seed`, which is what gives a served record a finite `drive_min` with no network at all (Task 15).

- [ ] **Step 4: Run and confirm it passes** — `python3 -m unittest tests_py.test_geo -v`

- [ ] **Step 5: Commit** — `git commit -m "feat(pipeline): Nominatim geocode cache and OSRM minutes"`

---

### Task 8: Normalization, titles and time bucketing

**Files:**
- Create: `tools/getup/normalize.py`, `tests_py/test_normalize.py`

**Interfaces:**
- Consumes: `Draft` (Task 2), `venues.resolve` (Task 6) for the `venue_id` the build puts on the draft, `venues.norm_city` (Task 6).
- Produces:
  - `TZ = zoneinfo.ZoneInfo('Asia/Jerusalem')` — import failure raises `RuntimeError('getup: no tz data for Asia/Jerusalem')`
  - `norm_title(text: str) -> str` — the single title normaliser: lowercase, niqqud and punctuation stripped, geresh/gershayim unified, emoji dropped, whitespace collapsed. `classify.key`, `derive.touring` and `dedup` all import this one.
  - `bucket_day(start: int) -> str` — `'YYYY-MM-DD'`; starts at 00:00–05:59 local bucket to the previous day
  - `record(draft: dict) -> dict | None` — the client-shaped record, or `None` (one warning naming source and source_id)
  - `id_for(venue_id: str, day: str, start: int) -> str` — `f'{venue_id}|{day}|{HH:MM}'`, the same id the client synthesizes
  - `desc_cap(text, limit: int = 600) -> str` — whitespace-collapsed, cut on a word boundary, `…` appended
  - `MIN_START = 946684800`, `MAX_START = 4102444800`, `MAX_SPAN = 12 * 3600`
  - **Counting contract:** `normalize.record` is the only filter between a raw `Draft` and a served record. Task 15 computes every per-source `count` and `status` from the records that survive `venues.resolve` + `normalize.record`, never from raw drafts. A source may legitimately return drafts the build will drop: Popit's `2309` test requires a start-less draft to survive `parse`, and 42 of the capture's 78 drafts have no start (36 have a start, 19 also have a venue). Reporting `popit: ok, count 78` while the build writes 19 records would call a feed healthy after it lost every clock, so a source with zero survivors is `failed` and its published count is 0.

- [ ] **Step 1: Write the failing tests**

```python
# tests_py/test_normalize.py
import unittest
from tools.getup import normalize

DRAFT = {'source': 'leaan', 'class': 'ticketing', 'source_id': 'a1', 'title': 'ערב ג׳אז',
         'venue': 'אוזן בר', 'venue_id': 'v_ozen_tlv', 'city': 'תל אביב', 'street': '',
         'start': 1792780200, 'end': 1792787400, 'price_from': 129, 'price_max': None,
         'soldout': False, 'desc': 'ג׳אז  חופשי', 'url': 'https://x', 'tags': ['ג׳אז'],
         'lat': 32.0771, 'lon': 34.7753, 'drive_min': 29}

class TitleTest(unittest.TestCase):
    def test_punctuation_and_emoji_do_not_make_two_titles(self):
        self.assertEqual(normalize.norm_title('סוף סיפור- סוף מסלול כפיר 🦁'),
                         normalize.norm_title('סוף סיפור סוף מסלול כפיר'))
        self.assertEqual(normalize.norm_title('  ערב   ג׳אז '), normalize.norm_title('ערב ג׳אז'))

class BucketTest(unittest.TestCase):
    def test_after_midnight_belongs_to_the_previous_day(self):
        self.assertEqual(normalize.bucket_day(1792780200), '2026-10-23')  # 21:30
        self.assertEqual(normalize.bucket_day(1792796400), '2026-10-23')  # 02:00 next day
        self.assertEqual(normalize.bucket_day(1792810740), '2026-10-23')  # 05:59
        self.assertEqual(normalize.bucket_day(1792810800), '2026-10-24')  # 06:00

    def test_winter_time_is_not_a_fixed_offset(self):
        # 2026-11-05 05:30 IST; a +03:00 shortcut would read 06:30 and keep it on the 5th
        self.assertEqual(normalize.bucket_day(1793849400), '2026-11-04')

class RecordTest(unittest.TestCase):
    def test_the_id_is_what_the_client_would_have_synthesized(self):
        rec = normalize.record(dict(DRAFT))
        self.assertEqual(rec['id'], 'v_ozen_tlv|2026-10-23|21:30')
        self.assertEqual(normalize.id_for('v_ozen_tlv', '2026-10-23', 1792780200), rec['id'])

    def test_source_categories_stay_internal_and_coordinates_pass_through(self):
        rec = normalize.record(dict(DRAFT))
        self.assertEqual(rec['tags'], ['ג׳אז'])          # stripped by write, used by classify
        self.assertEqual((rec['lat'], rec['lon'], rec['drive_min']), (32.0771, 34.7753, 29))

    def test_an_event_whose_venue_has_no_point_keeps_null_coordinates(self):
        rec = normalize.record({**DRAFT, 'venue_id': 'v_new', 'lat': None, 'lon': None,
                                'drive_min': None})
        self.assertEqual((rec['lat'], rec['lon'], rec['drive_min']), (None, None, None))

    def test_an_absent_venue_id_is_dropped_with_one_warning(self):
        for bad in (None, '', '   '):
            with self.assertLogs('getup', level='WARNING') as logs:
                self.assertIsNone(normalize.record({**DRAFT, 'venue_id': bad}))
            self.assertEqual(len(logs.output), 1)
            self.assertIn('a1', logs.output[0])

    def test_an_absurd_or_missing_start_is_dropped_with_one_warning(self):
        for bad in (None, 0, 1e16, '1792780200', -1, 4102444801):
            with self.assertLogs('getup', level='WARNING') as logs:
                self.assertIsNone(normalize.record({**DRAFT, 'start': bad}), str(bad))
            self.assertEqual(len(logs.output), 1)
            self.assertIn('a1', logs.output[0])

    def test_an_empty_title_is_dropped(self):
        with self.assertLogs('getup', level='WARNING'):
            self.assertIsNone(normalize.record({**DRAFT, 'title': '   '}))

    def test_an_end_five_months_later_is_not_a_show_end(self):
        # the real capture's first record ends on 2026-11-01 for a June start
        rec = normalize.record({**DRAFT, 'start': 1780988400, 'end': 1793469600})
        self.assertIsNone(rec['end'])
        self.assertEqual(rec['start'], 1780988400)

    def test_a_long_description_is_capped_at_600_and_loses_no_whole_word(self):
        text = ('מילה ' * 400).strip()
        out = normalize.desc_cap(text)
        self.assertLessEqual(len(out), 601)
        self.assertTrue(out.endswith('…'))
        self.assertEqual(normalize.desc_cap('  א  ב \n ג '), 'א ב ג')

    def test_a_zero_price_is_free_and_an_unknown_price_is_not(self):
        self.assertTrue(normalize.record({**DRAFT, 'price_from': 0})['free'])
        self.assertFalse(normalize.record({**DRAFT, 'price_from': None})['free'])
        self.assertIsNone(normalize.record({**DRAFT, 'price_from': None})['price_from'])
```

- [ ] **Step 2: Run and confirm it fails** — `python3 -m unittest tests_py.test_normalize -v`

- [ ] **Step 3: Implement `record`** — validate `title` after collapse, `start` as an int inside `[MIN_START, MAX_START]`, `venue_id` non-empty; coerce `price_from/price_max` to `int | None` and `soldout` to `bool`; `end = end if start < end <= start + MAX_SPAN else None`; set `day = bucket_day(start)`, `id`, `source = {'class': …, 'name': …}`, `urls = {'tickets': url if class == 'ticketing' else None, 'community': None, 'source': url}`, `free_until = None`, `notes = []`, `enrichment = []`, `seen = {}`, keep `tags`, and copy `lat/lon/drive_min` as given (nullable). `record` never emits `format/scene/crowd/daypart/expensive/commitment/notable` — derive owns those.

- [ ] **Step 4: Run and confirm it passes** — `python3 -m unittest tests_py.test_normalize -v`

- [ ] **Step 5: Commit** — `git commit -m "feat(pipeline): normalization, title form, bucketing and the record trust boundary"`

---

### Task 9: Client tolerance for unpinned events

**Files:**
- Modify: `src/distance.js`, `tests/distance.test.js`, `tests/format.test.js`

**Interfaces:**
- Consumes: the record shape from `normalize.record` (Task 8) — `lat`/`lon`/`drive_min` may be `null`.
- Produces: `recomputeDistances(events, centre, opts)` returns **one entry per input event**, `null` where the event has no finite `lat`/`lon`; only pinned events are sent in the `/table` URL. An all-unpinned list makes no request. Task 17 runs the suite.

- [ ] **Step 1: Write the failing tests**

```javascript
// tests/distance.test.js — added cases
test('an event without coordinates is skipped, not fatal for the batch', async () => {
  let called;
  const r = await recomputeDistances(
    [{ lat: 32.1, lon: 34.8 }, { lat: null, lon: null }, { lat: 32.2, lon: 34.9 }],
    { lat: 32, lon: 34.7 },
    { fetchImpl: async url => { called = url; return { ok: true, json: async () => ({ code: 'Ok', durations: [[0, 600, 1200]] }) }; } },
  );
  assert.deepEqual(r, [10, null, 20]);
  assert.doesNotMatch(called, /null/);
  assert.equal((called.match(/;/g) || []).length, 2);   // origin + two pinned destinations
});

test('a list with no pinned event asks the router nothing', async () => {
  let calls = 0;
  const r = await recomputeDistances([{ lat: null, lon: null }], { lat: 32, lon: 34 },
    { fetchImpl: async () => { calls += 1; return { ok: true, json: async () => ({}) }; } });
  assert.deepEqual(r, [null]);
  assert.equal(calls, 0);
});
```

```javascript
// tests/format.test.js — added case
test('an unpinned event says the drive time is unknown instead of inventing one', () => {
  const later = Math.floor(Date.now() / 1000) + 7200;
  assert.equal(leaveText({ start: later, end: null, drive_min: null }, Date.now()), 'זמן נסיעה לא ידוע');
});
```

- [ ] **Step 2: Run and confirm it fails** — `node --test tests/distance.test.js tests/format.test.js`

- [ ] **Step 3: Implement** — partition the list, keep the input index, request only pinned destinations, and scatter the returned minutes back into an array of input length with `null` for the skipped events. `MAX_DESTS` counts pinned events. Failure of the whole call still returns `null` (unchanged). Replace the comment that justified refusing the batch with the new rule: one unpinned event costs its own label, not everyone's.

- [ ] **Step 4: Run and confirm it passes** — `node --test`

- [ ] **Step 5: Commit** — `git commit -m "fix(client): an unpinned event no longer voids the drive-time batch"`

---

### Task 10: Dedup and seller ownership

**Files:**
- Create: `tools/getup/dedup.py`, `tests_py/test_dedup.py`

**Interfaces:**
- Consumes: records from `normalize.record` (Task 8), `normalize.norm_title` (Task 8).
- Produces:
  - `WINDOW = 1800`
  - `RANK = {'ticketing': 3, 'aggregator': 2, 'nightlife': 1}`
  - `merge(records: list[dict]) -> list[dict]` — stable, deterministic order, tie-broken on `(norm_title, id)`
  - `enrichment_note(loser: dict) -> str` — `'<source>: <desc or url>'`, cap 200

- [ ] **Step 1: Write the failing tests**

```python
# tests_py/test_dedup.py
import unittest
from tools.getup import dedup

def rec(**o):
    base = {'id': 'a', 'venue_id': 'v', 'start': 1792780200, 'end': 1792787400, 'title': 't',
            'price_from': 100, 'soldout': False, 'source': {'class': 'ticketing', 'name': 'leaan'},
            'urls': {'tickets': 'https://t', 'community': None, 'source': 'https://s'},
            'notes': [], 'desc': 'd', 'enrichment': []}
    return {**base, **o}

class MergeTest(unittest.TestCase):
    def test_the_seller_owns_the_row_and_the_aggregator_becomes_enrichment(self):
        seller = rec(id='t1', price_from=174, soldout=True)
        aggr = rec(id='a1', start=1792780200 + 1200, price_from=120,
                   source={'class': 'aggregator', 'name': 'biluim'}, desc='חניה חופשית')
        out = dedup.merge([aggr, seller])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['id'], 't1')
        self.assertEqual(out[0]['price_from'], 174)          # seller wins on price
        self.assertTrue(out[0]['soldout'])
        self.assertEqual(out[0]['enrichment'], ['biluim: חניה חופשית'])

    def test_thirty_minutes_merges_and_thirty_one_does_not(self):
        self.assertEqual(len(dedup.merge([rec(id='a'), rec(id='b', start=1792780200 + 1800)])), 1)
        self.assertEqual(len(dedup.merge([rec(id='a'), rec(id='b', start=1792780200 + 1801)])), 2)

    def test_overlapping_windows_at_one_venue_stay_two_rows(self):
        club = rec(id='club', start=1792780200, end=1792780200 + 6 * 3600)
        dj = rec(id='dj', start=1792780200 + 3600, end=1792780200 + 2 * 3600)
        self.assertEqual(len(dedup.merge([club, dj])), 2)

    def test_an_aggregator_with_no_seller_stands_and_says_so(self):
        [out] = dedup.merge([rec(id='a1', source={'class': 'aggregator', 'name': 'biluim'})])
        self.assertEqual(out['source']['class'], 'aggregator')

    def test_two_venues_at_the_same_hour_are_two_events(self):
        self.assertEqual(len(dedup.merge([rec(id='a'), rec(id='b', venue_id='v2')])), 2)

    def test_equal_rank_is_broken_by_the_normalized_title_then_the_id(self):
        a = rec(id='b', title='ערב-ג׳אז', source={'class': 'nightlife', 'name': 'popit'})
        b = rec(id='a', title='ערב ג׳אז', source={'class': 'nightlife', 'name': 'popit'})
        self.assertEqual(dedup.merge([a, b])[0]['id'], 'a')
        self.assertEqual(dedup.merge([b, a])[0]['id'], 'a')
```

- [ ] **Step 2: Run and confirm it fails** — `python3 -m unittest tests_py.test_dedup -v`

- [ ] **Step 3: Implement** — group by `venue_id`, sort each group by `(start, norm_title(title), id)`, fold a record into the group's last kept row when `abs(start_diff) <= WINDOW` and the kept row wins on `RANK` (equal rank: the smaller `(norm_title, id)` wins, so input order cannot change output); the loser contributes `enrichment_note`, plus `urls.community` and any `notes` the winner lacks. Return sorted by `(start, id)`.

- [ ] **Step 4: Run and confirm it passes** — `python3 -m unittest tests_py.test_dedup -v`

- [ ] **Step 5: Commit** — `git commit -m "feat(pipeline): venue-and-time dedup with seller ownership"`

---

### Task 11: Classification vocabulary and label cache

**Files:**
- Create: `tools/getup/classify.py`, `data/labels.json` (committed as `{}`), `tests_py/test_classify.py`

**Interfaces:**
- Consumes: records (Task 8), `normalize.norm_title` (Task 8), `write.read_json/write_json`, `write.labels_file` (Task 1).
- Produces:
  - `VOCAB = {'scene': [...15], 'crowd': [...8], 'format': [...8]}` — exact §7.7 strings
  - `key(rec: dict) -> str` — `sha1(norm_title(rec['title']))[:16]`; one key per title, so a tour classifies once and punctuation cannot fork the cache
  - `load(root) -> dict[str, dict]`, `save(root, labels) -> bool`
  - `pending(records, labels) -> list[dict]` — `{key, title, desc, tags}`, `desc` capped at 200
  - `merge(labels, replies: list[dict]) -> dict` — sanitized, sorted by key
  - `apply(records, labels) -> list[dict]` — sets `format`, `scene`, `crowd`
  - `rules(rec: dict) -> dict` — deterministic fallback from the source's own categories (`tags`)
  - `sanitize(label: dict) -> dict` — drops anything outside `VOCAB`; `format` falls back to `'unknown'`

- [ ] **Step 1: Write the failing tests**

```python
# tests_py/test_classify.py
import json, re, tempfile, unittest
from tools.getup import classify

def rec(title='ערב ג׳אז', tags=()):
    return {'id': 'x', 'title': title, 'desc': 'ערב ג׳אז אינטימי', 'tags': list(tags),
            'source': {'class': 'ticketing', 'name': 'leaan'}, 'venue_id': 'v'}

class VocabTest(unittest.TestCase):
    def test_the_vocabulary_matches_the_client_character_for_character(self):
        js = open('src/chips.js', encoding='utf-8').read()
        for axis in ('scene', 'crowd', 'format'):
            block = re.search(rf"{axis}: \[(.*?)\]", js, re.S).group(1)
            self.assertEqual(set(re.findall(r"'([^']+)'", block)), set(classify.VOCAB[axis]), axis)
        self.assertIn('מופע מחווה', classify.VOCAB['scene'])
        self.assertIn('להט״ב', classify.VOCAB['crowd'])
        self.assertIn('dj_set', classify.VOCAB['format'])

class LabelTest(unittest.TestCase):
    def test_an_unlisted_label_is_dropped_not_invented(self):
        out = classify.sanitize({'format': 'opera', 'scene': ['אופרה', 'ג׳אז'],
                                 'crowd': ['VIP', '30+', '30+']})
        self.assertEqual(out, {'format': 'unknown', 'scene': ['ג׳אז'], 'crowd': ['30+']})

    def test_only_uncached_titles_are_pending_and_a_cached_one_is_reused(self):
        first = rec('MADONNA THE TRIBUTE SHOW')
        self.assertEqual([p['key'] for p in classify.pending([first], {})], [classify.key(first)])
        labels = classify.merge({}, [{'key': classify.key(first), 'format': 'tribute',
                                      'scene': ['פופ'], 'crowd': []}])
        self.assertEqual(classify.pending([first], labels), [])
        [applied] = classify.apply([first], labels)
        self.assertEqual((applied['format'], applied['scene']), ('tribute', ['פופ']))

    def test_punctuation_does_not_fork_the_cache(self):
        self.assertEqual(classify.key(rec('ערב-ג׳אז')), classify.key(rec('ערב ג׳אז')))

    def test_without_a_label_the_source_categories_decide(self):
        [applied] = classify.apply([rec(tags=['בידור וסטנדאפ'])], {})
        self.assertEqual((applied['format'], applied['scene']), ('standup', ['סטנדאפ']))
        [applied] = classify.apply([rec(tags=['הצגות והרצאות'])], {})
        self.assertEqual((applied['format'], applied['scene']), ('theatre', ['תיאטרון']))
        [applied] = classify.apply([rec(tags=[])], {})
        self.assertEqual((applied['format'], applied['scene'], applied['crowd']), ('unknown', [], []))

    def test_the_cache_round_trips_sorted(self):
        with tempfile.TemporaryDirectory() as root:
            labels = {'b' * 16: {'format': 'unknown', 'scene': [], 'crowd': []},
                      'a' * 16: {'format': 'dj_set', 'scene': ['אלקטרונית/טכנו'], 'crowd': []}}
            self.assertTrue(classify.save(root, labels))
            self.assertFalse(classify.save(root, labels))
            self.assertEqual(list(json.load(open(f'{root}/data/labels.json', encoding='utf-8'))),
                             ['a' * 16, 'b' * 16])
```

- [ ] **Step 2: Run and confirm it fails** — `python3 -m unittest tests_py.test_classify -v`

- [ ] **Step 3: Implement** — `key` calls `normalize.norm_title`; `merge` sanitizes every reply and appends to the existing cache; `apply` reads `labels[key(rec)]` or `rules(rec)`; `rules` maps Leaan's five categories onto `format`/`scene` and leaves `crowd` empty. `pending` is the batch the agent feeds to its model; its replies are merged with `--labels`. Nothing in this module makes a network call and no key is stored anywhere.

- [ ] **Step 4: Run and confirm it passes** — `python3 -m unittest tests_py.test_classify -v`

- [ ] **Step 5: Commit** — `git commit -m "feat(pipeline): closed-vocabulary classification cache"`

---

### Task 12: Derived signals

**Files:**
- Create: `tools/getup/derive.py`, `tests_py/test_derive.py`

**Interfaces:**
- Consumes: `normalize.norm_title` (Task 8), records after `classify.apply` (Task 11), registry (Task 6).
- Produces:
  - `p90(prices: list[float]) -> float | None` — nearest rank: `sorted(prices)[min(n - 1, floor(0.9 * n))]`
  - `touring(records: list[dict]) -> dict[str, int]` — `norm_title` → distinct `city` count, over the **full** payload
  - `signals(records, *, touring: dict[str, int], registry: dict) -> list[dict]` — sets `expensive`, `commitment`, `free_until`, `notable`, `notes`
  - `commitment(rec: dict) -> str` — `'plan_ahead'` if `format in {'festival', 'theatre', 'orchestra'}` or `drive_min >= 60`; else `'jump_in'`. An unknown drive (`drive_min is None`) is never a reason to plan ahead.
  - `notable(rec: dict, cities: int, registry: dict) -> bool` — ticketing AND (`cities >= 2` OR tier `major` OR `price_from >= 200`)
  - `free_until(text: str | None) -> str | None`
  - `venue_notes(rec: dict, venue: dict | None) -> list[str]` — `חניה: …`, `נגישות: …`, `תחבורה: …`, max 5, no duplicates

- [ ] **Step 1: Write the failing tests**

```python
# tests_py/test_derive.py
import json, unittest
from tools.getup import derive

def rec(**o):
    base = {'id': 'x', 'title': 'ערב', 'venue_id': 'v', 'city': 'תל אביב', 'price_from': 100,
            'format': 'tribute', 'drive_min': 30, 'free_until': None, 'notes': [], 'desc': '',
            'source': {'class': 'ticketing', 'name': 'leaan'}}
    return {**base, **o}

MAJOR = {'v': {'tier': 'major', 'parking': 'חניון מאירהוף, ₪30/שעה',
               'access': 'נגיש לכיסא גלגלים', 'transport': 'קו 5'}}
MID = {'v': {'tier': 'mid', 'parking': None, 'access': None, 'transport': None}}

class P90Test(unittest.TestCase):
    def test_the_real_capture_p90_is_199(self):
        prices = [e['price'] for e in json.load(open('docs/research/2026-10-21/leaan-events.json',
                                                     encoding='utf-8'))]
        self.assertEqual(derive.p90(prices), 199)

    def test_a_ten_price_set_uses_the_nearest_rank(self):
        self.assertEqual(derive.p90([10, 20, 30, 40, 50, 60, 70, 80, 90, 100]), 100)
        self.assertEqual(derive.p90([39]), 39)
        self.assertIsNone(derive.p90([]))

class SignalTest(unittest.TestCase):
    def test_expensive_is_the_run_threshold_or_two_hundred(self):
        set_ = [rec(id=f'r{i}', price_from=p) for i, p in enumerate([39, 49, 59, 69, 79, 89, 99, 129, 149, 199])]
        out = {r['id']: r['expensive'] for r in derive.signals(set_, touring={}, registry=MID)}
        self.assertTrue(out['r9'])       # 199 == p90
        self.assertFalse(out['r7'])      # 129 < 199
        over = derive.signals([rec(price_from=250)], touring={}, registry=MID)
        self.assertTrue(over[0]['expensive'])   # >= 200, even alone
        self.assertFalse(derive.signals([rec(price_from=None)], touring={}, registry=MID)[0]['expensive'])

    def test_commitment_ignores_an_unknown_drive_and_has_no_ticketed_and_48h_clause(self):
        # ticketed, ten days out, 30 minute drive: the amended rule says jump_in
        self.assertEqual(derive.commitment(rec(format='tribute', drive_min=30)), 'jump_in')
        self.assertEqual(derive.commitment(rec(format='tribute', drive_min=None)), 'jump_in')
        self.assertEqual(derive.commitment(rec(format='theatre')), 'plan_ahead')
        self.assertEqual(derive.commitment(rec(format='orchestra')), 'plan_ahead')
        self.assertEqual(derive.commitment(rec(format='festival')), 'plan_ahead')
        self.assertEqual(derive.commitment(rec(format='live_band', drive_min=60)), 'plan_ahead')
        self.assertEqual(derive.commitment(rec(format='live_band', drive_min=59)), 'jump_in')

    def test_notable_needs_a_ticket_seller(self):
        self.assertTrue(derive.notable(rec(), 2, MID))          # touring two cities
        self.assertTrue(derive.notable(rec(price_from=200), 1, MID))
        self.assertFalse(derive.notable(rec(price_from=199), 1, MID))
        self.assertTrue(derive.notable(rec(), 1, MAJOR))         # major venue
        self.assertFalse(derive.notable(rec(source={'class': 'aggregator', 'name': 'biluim'}), 5, MAJOR))

    def test_touring_counts_cities_and_punctuation_does_not_split_a_title(self):
        records = [{'title': e['title'], 'city': e['city']}
                   for e in json.load(open('docs/research/2026-10-21/leaan-events.json', encoding='utf-8'))]
        records.append({'title': 'אסף מור יוסף במופע סטנדאפ!', 'city': 'באר שבע'})
        counts = derive.touring(records)
        self.assertEqual(counts['אסף מור יוסף במופע סטנדאפ'], 15)
        self.assertEqual(sum(1 for n in counts.values() if n >= 2), 30)

    def test_free_until_is_read_from_prose_in_both_languages(self):
        self.assertEqual(derive.free_until('כניסה חינם עד 22:00'), '22:00')
        self.assertEqual(derive.free_until('free before 11pm'), '23:00')
        self.assertIsNone(derive.free_until('כניסה חופשית'))

    def test_venue_facts_reach_the_event_notes_once(self):
        notes = derive.venue_notes(rec(notes=['חניה: חניון מאירהוף, ₪30/שעה']), MAJOR['v'])
        self.assertEqual(notes, ['חניה: חניון מאירהוף, ₪30/שעה', 'נגישות: נגיש לכיסא גלגלים', 'תחבורה: קו 5'])
        self.assertEqual(derive.venue_notes(rec(), None), [])
```

- [ ] **Step 2: Run and confirm it fails** — `python3 -m unittest tests_py.test_derive -v`

- [ ] **Step 3: Implement** — `signals` computes one threshold from the records it is given (that is the retained 30-day set by the time `build` calls it), then fills the four signals per record plus `notes = venue_notes(...)`. `free_until` scans `rec['desc']` for `חינם עד HH:MM` and `free before Npm/am`. No `daypart` is ever produced.

- [ ] **Step 4: Run and confirm it passes** — `python3 -m unittest tests_py.test_derive -v`

- [ ] **Step 5: Commit** — `git commit -m "feat(pipeline): p90, commitment, notability and venue facts on the record"`

---

### Task 13: Monthly archive

**Files:**
- Create: `tools/getup/archive.py`, `tests_py/test_archive.py`

**Interfaces:**
- Consumes: `write.data_files`, `write.read_json_strict`, `write.write_bytes` (Task 1).
- Produces:
  - `RETENTION_DAYS = 90`
  - `codec() -> tuple[str, str, Callable[[bytes], bytes], Callable[[bytes], bytes]]` — `('zstd', '.zst', …)` when `compression.zstd` imports, else `('lzma', '.xz', …)`
  - `compress(data: bytes) -> bytes`, `decompress(data: bytes) -> bytes`, `suffix() -> str`
  - `month_file(root, month) -> str` — `archive/2026-08.json.zst` or `.json.xz`
  - `archive_months(root: str) -> list[str]` — sorted `YYYY-MM` for every member present under `archive/`; the one reader `coverage.report` uses to enumerate them
  - `roll(root, today, *, codec_override=None) -> list[str]` — returns archived day names

- [ ] **Step 1: Write the failing tests**

```python
# tests_py/test_archive.py
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
```

- [ ] **Step 2: Run and confirm it fails** — `python3 -m unittest tests_py.test_archive -v`

- [ ] **Step 3: Implement** — `today - 90 days` as a local `date`, day names from `write.data_files(f'{root}/data')`, strict read per day: a raise is warned once naming the day and the file is skipped, never moved and never deleted. Read the existing month payload when present, `update` the newly expired days, write through `write.write_bytes(month_file, compress(...))`, then delete the day file. `codec()` guards `from compression import zstd` and `from compression import lzma`, falling back to the long-standing `import lzma` — three lines, because libzstd is an optional CPython build dependency and the phone may lack it (ADR-0002). The suffix always matches the codec, so a reader never has to guess. `archive_months` is one `os.listdir(f'{root}/archive')` plus `^\d{4}-\d{2}\.json\.(zst|xz)$`, sorted, returning `[]` when the directory does not exist; it never decompresses anything itself.

- [ ] **Step 4: Run and confirm it passes** — `python3 -m unittest tests_py.test_archive -v`

- [ ] **Step 5: Commit** — `git commit -m "feat(pipeline): ninety-day monthly archive"`

---

### Task 14: Coverage alarm and the index manifest

**Files:**
- Create: `tools/getup/coverage.py`, `tools/getup/manifest.py`, `tests_py/test_coverage.py`, `tests_py/test_manifest.py`

**Interfaces:**
- Consumes: `venues.load` (Task 6), `write.read_json`, `write.data_files`, `write.index_file`, `write.write_json` (Task 1), `archive.archive_months/month_file/decompress` (Task 13).
- Produces:
  - `LOOKBACK_DAYS = 14`
  - `last_seen_by_venue(records) -> dict[str, str]` — venue id → max `seen.last` across its records
  - `check(registry, records, today) -> {'checked': int, 'missed': [{'venue_id', 'name'}]}` — a venue is **seen** when its registry `seen_last` (stamped by the last build that scanned it) is `today - LOOKBACK_DAYS` or later; only a venue with no `seen_last` falls back to the latest `seen.last` in the files. The event `day` is irrelevant, so a future season still counts when the venue was scanned this week, and a major hall read today with nothing in the next 30 days is not a false alarm
  - `report(root, today) -> dict` — reads **every** committed day file through `write.data_files(data_dir)` plus every archive member through `archive.archive_months` and calls `check`. It runs against files, not in-memory records and not a date window, so the 14-day lookback is a lookback on sightings, never on event dates; the `coverage` command therefore always reports the committed state.
  - `manifest.day_counts(root) -> dict[str, int]` — date → record count for every readable day file on disk, through `write.data_files`; an unreadable file is warned about and omitted, never counted as zero
  - `manifest.build_index(*, generated_at, counts, coverage, sources, dropped_no_venue, unpinned) -> dict` and `manifest.write_index(root, index) -> bool` — **the only owner of `data/index.json`**; `unpinned` is the served-set count the build hands in, never recomputed here

- [ ] **Step 1: Write the failing tests**

```python
# tests_py/test_coverage.py
import unittest
from tools.getup import coverage

REG = {'v_major': {'id': 'v_major', 'name': 'היכל גדול', 'tier': 'major'},
       'v_quiet': {'id': 'v_quiet', 'name': 'אולם שקט', 'tier': 'major'},
       'v_room': {'id': 'v_room', 'name': 'מועדון', 'tier': 'room'}}

def rec(venue_id, day, last):
    return {'venue_id': venue_id, 'day': day, 'seen': {'first': last, 'last': last}}

class CoverageTest(unittest.TestCase):
    def test_a_major_venue_with_no_recent_sighting_is_missed(self):
        recs = [rec('v_major', '2026-10-21', '2026-10-20'), rec('v_room', '2026-10-21', '2026-10-21')]
        out = coverage.check(REG, recs, '2026-10-21')
        self.assertEqual(out['checked'], 2)                       # only major venues are checked
        self.assertEqual(out['missed'], [{'venue_id': 'v_quiet', 'name': 'אולם שקט'}])

    def test_a_future_event_with_a_stale_last_seen_is_still_missed(self):
        # the event is on sale for November, but nothing has been seen here for twenty days
        stale = [rec('v_quiet', '2026-11-10', '2026-10-01')]
        missed = [m['venue_id'] for m in coverage.check(REG, stale, '2026-10-21')['missed']]
        self.assertEqual(missed, ['v_quiet'])

    def test_a_fresh_sighting_keeps_a_venue_alive_when_every_event_is_far_out(self):
        # seen three days ago, and its only events are twenty days away: the date window must not hide it
        fresh = [rec('v_quiet', '2026-11-10', '2026-10-18')]
        self.assertEqual(coverage.check(REG, fresh, '2026-10-21')['missed'], [])

    def test_the_window_is_fourteen_days_ending_today(self):
        inside = [rec('v_quiet', '2026-10-08', '2026-10-08')]    # 13 days back
        self.assertEqual(coverage.check(REG, inside, '2026-10-21')['missed'], [])
        outside = [rec('v_quiet', '2026-10-06', '2026-10-06')]   # 15 days back
        self.assertEqual([m['venue_id'] for m in coverage.check(REG, outside, '2026-10-21')['missed']],
                         ['v_quiet'])

    def test_the_fixture_registry_checks_three_major_venues(self):
        # the committed fixtures predate `seen`, so all three read as missed until Task 17 rewrites them
        out = coverage.report('.', '2026-10-21')
        self.assertEqual(out['checked'], 3)
        self.assertEqual({m['venue_id'] for m in out['missed']},
                         {'v_heichal_tarbut_rishon', 'v_zionist_america_tlv', 'v_heichal_tarbut_petah_tikva'})
```

```python
# tests_py/test_manifest.py
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
```

- [ ] **Step 2: Run and confirm it fails** — `python3 -m unittest tests_py.test_coverage tests_py.test_manifest -v`

- [ ] **Step 3: Implement** — `last_seen_by_venue` takes the max of `seen.last` and ignores records without it. `check` computes the `today - LOOKBACK_DAYS` cutoff in local dates, compares it against the latest `seen.last` of every `tier == 'major'` entry, and sorts misses by `name` so the footer line never reshuffles. `report` concatenates every day file on disk (no date filter: the served days start today and run forward, so a 14-day window on event dates would miss every one of them and alert on all three majors every night) and every archived day's records from `archive.archive_months`, decompressed and merged; day files are read with `write.read_json`, so one unreadable file is skipped rather than aborting the alarm. `day_counts` reads each day file once through `write.data_files`; `build_index` sorts dates and passes every field through untouched, so a partial source's failures and the `unpinned`/`dropped_no_venue` counts reach the client verbatim, and a run that wrote nothing still lists the days already on disk.

- [ ] **Step 4: Run and confirm it passes** — `python3 -m unittest tests_py.test_coverage tests_py.test_manifest -v`

- [ ] **Step 5: Commit** — `git commit -m "feat(pipeline): seen-based coverage alarm and the index owner"`

---

### Task 15: History, seen and build orchestration

**Files:**
- Create: `tools/getup/build.py`, `tests_py/test_build.py`
- Modify: `.gitignore` (`build/`)

**Interfaces:**
- Consumes: `write.*` (Task 1), `scan.*` (Task 2), `venues.resolve` (Task 6), `geo.fill/seed` (Task 7), `normalize.*` (Task 8), `dedup.merge` (Task 10), `classify.*` (Task 11), `derive.*` (Task 12), `archive.roll/decompress/archive_months` (Task 13), `coverage.report` + `manifest.day_counts/build_index/write_index` (Task 14).
- Produces:
  - `SERVE_DAYS = 30`
  - `history(root) -> {'seen': {event_id: {'first': str, 'last': str}}}` — `seen` read from day files and archive members, so `seen.first` survives both the horizon and the 90-day roll. Reads day files only through `write.data_files`, and archive members through `archive.decompress`.
  - `window(records, today) -> list[dict]` — keeps `today <= day < today + SERVE_DAYS`, the same 30 dates the write covers
  - `run(root, today, *, sources=('leaan', 'popit', 'biluim'), from_dir=None, labels_path=None, fetch=scan.fetch_text, now=None) -> dict` → `{'written': list[str], 'pruned': list[str] | None, 'counts': dict, 'sources': dict, 'coverage': dict, 'dropped_no_venue': int, 'unpinned': int}` — `unpinned` counts served-set records only; `counts` and `sources.<name>.count` count records that survived `venues.resolve` + `normalize.record`, never raw drafts (Task 8's counting contract)

- [ ] **Step 1: Write the failing tests**

```python
# tests_py/test_build.py
import json, os, shutil, tempfile, unittest
from tools.getup import build, write

CAPTURE = 'docs/research/2026-10-21'
TODAY = '2026-10-21'
NOW = '2026-10-21T04:15:00Z'

def fresh(root):
    shutil.copytree('venue', f'{root}/venue')
    shutil.copytree('data', f'{root}/data')

def snapshot(root):
    return {day: open(write.date_file(root, day), 'rb').read()
            for day in write.data_files(f'{root}/data')}

def no_network(url, **kw):
    raise AssertionError(f'network call in cassette mode: {url}')

class BuildTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        fresh(self.root)

    def test_two_runs_on_unchanged_cassettes_are_byte_identical(self):
        build.run(self.root, TODAY, sources=('leaan', 'popit'), from_dir=CAPTURE,
                  fetch=no_network, now=NOW)
        first = snapshot(self.root)
        first_venues = open(f'{self.root}/venue/venues.json', 'rb').read()
        first_index = open(write.index_file(self.root), 'rb').read()
        build.run(self.root, TODAY, sources=('leaan', 'popit'), from_dir=CAPTURE,
                  fetch=no_network, now=NOW)
        self.assertEqual(snapshot(self.root), first)
        self.assertEqual(open(f'{self.root}/venue/venues.json', 'rb').read(), first_venues)
        self.assertEqual(open(write.index_file(self.root), 'rb').read(), first_index)

    def test_the_index_counts_match_the_files_it_lists(self):
        out = build.run(self.root, TODAY, sources=('leaan',), from_dir=CAPTURE,
                        fetch=no_network, now=NOW)
        idx = json.load(open(write.index_file(self.root), encoding='utf-8'))
        self.assertEqual({d['date'] for d in idx['dates']}, set(snapshot(self.root)))
        for d in idx['dates']:
            self.assertEqual(len(json.loads(snapshot(self.root)[d['date']])), d['count'])
        self.assertEqual(idx['sources']['leaan']['status'], 'ok')
        self.assertEqual(out['counts']['leaan'], idx['sources']['leaan']['count'])

    def test_nothing_outside_the_thirty_day_horizon_is_stored(self):
        build.run(self.root, TODAY, sources=('leaan',), from_dir=CAPTURE, fetch=no_network, now=NOW)
        days = write.data_files(f'{self.root}/data')
        self.assertEqual((days[0], days[-1]), ('2026-10-21', '2026-11-19'))
        self.assertEqual(len(days), build.SERVE_DAYS)   # every horizon day exists, empty ones included

    def test_seen_first_survives_the_next_run(self):
        build.run(self.root, TODAY, sources=('leaan',), from_dir=CAPTURE, fetch=no_network, now=NOW)
        [first_event] = json.loads(snapshot(self.root)['2026-10-22'])
        self.assertEqual(first_event['seen']['first'], TODAY)
        self.assertEqual(build.history(self.root)['seen'][first_event['id']]['first'], TODAY)
        build.run(self.root, '2026-10-22', sources=('leaan',), from_dir=CAPTURE,
                  fetch=no_network, now='2026-10-22T04:15:00Z')
        again = {ev['id']: ev for ev in json.loads(snapshot(self.root)['2026-10-22'])}
        self.assertEqual(again[first_event['id']]['seen'], {'first': TODAY, 'last': '2026-10-22'})

    def test_the_build_never_writes_the_label_cache(self):
        before = open(f'{self.root}/data/labels.json', 'rb').read()
        build.run(self.root, TODAY, sources=('leaan',), from_dir=CAPTURE, fetch=no_network, now=NOW)
        self.assertEqual(open(f'{self.root}/data/labels.json', 'rb').read(), before)

    def test_a_source_that_returns_nothing_is_reported_and_deletes_nothing(self):
        os.makedirs(f'{self.root}/empty')
        open(f'{self.root}/empty/popit.xml', 'w').write('<rss><channel></channel></rss>')
        write.write_json(write.date_file(self.root, '2026-11-30'), [{'id': 'stale'}])
        before = snapshot(self.root)
        out = build.run(self.root, TODAY, sources=('popit',), from_dir=f'{self.root}/empty',
                        fetch=no_network, now=NOW)
        self.assertEqual(out['sources']['popit']['status'], 'failed')
        self.assertIsNone(out['pruned'])
        self.assertEqual(snapshot(self.root), before)              # nothing written, nothing deleted
        idx = json.load(open(write.index_file(self.root), encoding='utf-8'))
        self.assertEqual(idx['sources']['popit']['status'], 'failed')
        self.assertEqual({d['date'] for d in idx['dates']}, set(snapshot(self.root)))  # still listed

    def test_a_fully_ok_run_prunes_a_stale_future_day(self):
        write.write_json(write.date_file(self.root, '2026-11-30'), [{'id': 'stale'}])
        out = build.run(self.root, TODAY, sources=('leaan',), from_dir=CAPTURE, fetch=no_network, now=NOW)
        self.assertEqual(out['pruned'], ['2026-11-30'])
        self.assertNotIn('2026-11-30', snapshot(self.root))

    def test_unpinned_and_venueless_events_are_counted_not_invented(self):
        out = build.run(self.root, TODAY, sources=('leaan', 'popit'), from_dir=CAPTURE,
                        fetch=no_network, now=NOW)
        idx = json.load(open(write.index_file(self.root), encoding='utf-8'))
        self.assertGreater(idx['unpinned'], 0)                     # cities the capture does not geocode stay unpinned
        self.assertGreater(idx['dropped_no_venue'], 0)             # Popit's "מיקום לא ידוע" items
        self.assertEqual(idx['unpinned'], out['unpinned'])
        for blob in snapshot(self.root).values():
            for ev in json.loads(blob):
                if ev['lat'] is None:
                    self.assertIsNone(ev['lon'])
                    self.assertIsNone(ev['drive_min'])

    def test_every_served_venue_from_the_capture_has_finite_drive_minutes(self):
        build.run(self.root, TODAY, sources=('leaan', 'popit'), from_dir=CAPTURE,
                  fetch=no_network, now=NOW)
        reg = json.load(open(f'{self.root}/venue/venues.json', encoding='utf-8'))
        known = json.load(open(f'{CAPTURE}/geo-drive.json', encoding='utf-8'))['drive']
        served = [ev for blob in snapshot(self.root).values() for ev in json.loads(blob)]
        placed = [ev for ev in served if reg[ev['venue_id']]['city'] in known]
        self.assertTrue(placed)                                    # the capture covers most of the served set
        for ev in placed:
            self.assertIsInstance(ev['drive_min'], int)             # a placed city never yields null minutes

    def test_every_written_event_satisfies_the_client_contract(self):
        build.run(self.root, TODAY, sources=('leaan', 'popit'), from_dir=CAPTURE,
                  fetch=no_network, now=NOW)
        reg = json.load(open(f'{self.root}/venue/venues.json', encoding='utf-8'))
        for path, blob in snapshot(self.root).items():
            for ev in json.loads(blob):
                self.assertIn(ev['venue_id'], reg, path)
                self.assertNotIn('daypart', ev)
                self.assertNotIn('tags', ev)
                self.assertLessEqual(len(ev['desc']), 601)
                self.assertIn(ev['format'], ['live_band', 'tribute', 'dj_set', 'orchestra',
                                             'standup', 'theatre', 'festival', 'unknown'])
                self.assertIsInstance(ev['notes'], list)
                self.assertTrue(all(isinstance(n, str) for n in ev['notes']))
```

- [ ] **Step 2: Run and confirm it fails** — `python3 -m unittest tests_py.test_build -v`

- [ ] **Step 3: Implement `build.run` in this order** — scan (`from_dir` uses `scan_from_dir`; otherwise `scan`) → `venues.resolve` per draft, dropping drafts whose venue is `None` with one warning and incrementing `dropped_no_venue` → `geo.fill` **only when `from_dir is None`** (cassette mode never calls the network, and a geocode failure is not fatal) → `geo.seed` **always**, so every venue in a captured city carries a point and cached minutes even when the network is never touched → `normalize.record` → tally each source's survivors and demote a source with none to `failed` **before** dedup, so a row absorbed into a ticketing record still counts for its own source → `dedup.merge` → set `seen_last = today` on every registry venue referenced by a surviving record (before the horizon trims the list) → `venues.save` (a no-op when nothing changed) → `classify.apply` reading `data/labels.json` (never writing it) → `derive.touring` over the **untrimmed** records → `window` → `derive.signals` over the trimmed ones → merge `history(root)['seen']` into each record (`first = min(prior, today)`, `last = today`) → `write_days` over the whole horizon `today … today + SERVE_DAYS - 1` (30 dates, empty lists included), so no stale fixture day can survive inside it — skipped entirely when every requested source's tallied state is `failed`, so a total outage cannot blank the portal → `prune_future` and `archive.roll` **only when every tallied state is `ok`** → `manifest.day_counts` → `coverage.report(root, today)` from the files as they now stand (so a same-day re-run reports the same alarm and the index stays byte-identical) → `manifest.write_index` with the source statuses, `dropped_no_venue`, `unpinned` (served-set records whose venue has no point **or** no cached `drive_min`) and the coverage block. `generated_at` comes from `now or write.utc_now()` and is written only to `data/index.json`. The per-source `count` and `status` passed to the index are tallied from the records that survived `venues.resolve` + `normalize.record`, keyed back to their source — not from the raw drafts `scan` returned. A source whose every draft drops (a feed that lost its clocks) is `failed` with `count: 0` and one failure line naming it, even when `scan` said `ok`; a source with some survivors keeps `ok`/`partial` from the transport, with the survivor count. A failed or partial source still writes the day files it has, still lists every day already on disk in the index, returns its status, and leaves every future day and every archive untouched.

- [ ] **Step 4: Run and confirm it passes** — `python3 -m unittest tests_py.test_build -v`

- [ ] **Step 5: Commit** — `git commit -m "feat(pipeline): seen history, failure-tolerant orchestration and the idempotency proof"`

---

### Task 16: CLI

**Files:**
- Create: `tools/getup/cli.py`, `tools/getup/__main__.py`, `tests_py/test_cli.py`

**Interfaces:**
- Consumes: `build.run`, `build.history` (Task 15), `classify.pending/merge/save` (Task 11), `normalize.*` (Task 8), `dedup.merge` (Task 10), `scan.*` (Task 2), `archive.roll` (Task 13), `coverage.report` (Task 14).
- Produces:
  - `cli.main(argv: list[str]) -> int` — `build`, `pending`, `labels`, `coverage`, `archive`; `0` ok, `1` argparse error, `2` a source failed/partial/returned nothing or a bad `--sources`/`--today` value (the write still happened; `pending` returns it only when every source failed), `3` `coverage` found a missed major venue, `4` tz data missing. The codes are printed in `getup --help`
  - `python3 -m tools.getup build` is the daily command
  - `pending` scans and writes `build/labels.pending.jsonl` only: it never geocodes and never writes `data/`

- [ ] **Step 1: Write the failing tests**

```python
# tests_py/test_cli.py
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
            open(f'{root}/empty/popit.xml', 'w').write('<rss><channel></channel></rss>')
            code = cli.main(['build', '--root', root, '--today', TODAY,
                             '--from-dir', f'{root}/empty', '--sources', 'popit'])
            self.assertEqual(code, 2)
            idx = json.load(open(f'{root}/data/index.json', encoding='utf-8'))
            self.assertEqual(idx['sources']['popit']['status'], 'failed')

    def test_pending_writes_a_batch_and_labels_merge_it(self):
        with tempfile.TemporaryDirectory() as root:
            fresh(root)
            self.assertEqual(cli.main(['pending', '--root', root, '--today', TODAY,
                                       '--from-dir', CAPTURE, '--sources', 'leaan']), 0)
            batch = [json.loads(l) for l in open(f'{root}/build/labels.pending.jsonl', encoding='utf-8')]
            self.assertTrue(batch and all(set(p) >= {'key', 'title'} for p in batch))
            open(f'{root}/build/labels.jsonl', 'w').write('\n'.join(json.dumps(
                {'key': p['key'], 'format': 'tribute', 'scene': ['פופ'], 'crowd': []},
                ensure_ascii=False) for p in batch))
            self.assertEqual(cli.main(['labels', '--root', root, '--labels',
                                       f'{root}/build/labels.jsonl']), 0)
            self.assertEqual(len(json.load(open(f'{root}/data/labels.json', encoding='utf-8'))), len(batch))

    def test_an_unknown_subcommand_is_an_argument_error(self):
        self.assertEqual(cli.main(['nope']), 1)
```

- [ ] **Step 2: Run and confirm it fails** — `python3 -m unittest tests_py.test_cli -v`

- [ ] **Step 3: Implement** — argparse per subcommand; `--root`, `--today`, `--sources`, `--from-dir` shared. `build` prints the counts and one line per failed source to stderr, returns `2` whenever any status is not `ok`, and `4` when `build.run` raises the tz `RuntimeError`. `pending` calls `scan`/`scan_from_dir`, `normalize`, `dedup`, `classify.pending` and writes the JSONL batch; it takes no geo path and touches no `data/` file. `labels` reads the reply JSONL, folds it in with `classify.merge` and commits it with `classify.save`.

- [ ] **Step 4: Run and confirm it passes** — `python3 -m unittest tests_py.test_cli -v`

- [ ] **Step 5: Commit** — `git commit -m "feat(pipeline): CLI subcommands, exit codes and the pending batch"`

---

### Task 17: Accept the first real run

**Files:**
- Modify: `data/*.json`, `data/index.json`, `data/labels.json`, `venue/venues.json`
- Modify: `docs/superpowers/plans/2026-10-22-getup-pipeline.md` (tick the boxes)

**Interfaces:**
- Consumes: `python3 -m tools.getup build` and the client suite as the acceptance suite.
- Produces: committed data that the finished client renders.

- [x] **Step 1: Run the pipeline over the committed capture**

`python3 -m tools.getup build --today 2026-10-21 --from-dir docs/research/2026-10-21 --sources leaan popit`
Expected: exit 0; `git status` shows the seven fixture days rewritten, new days through `2026-11-19` (30 dates from `2026-10-21`), `venue/venues.json` grown by about 89 provisional venues — the ones whose city the capture knows also gain a city centroid and cached `drive_min` — and `data/index.json` reporting `unpinned` above zero with `dropped_no_venue` equal to the Popit items whose title says `מיקום לא ידוע`.

- [x] **Step 2: Run the client suite against the new data** — `node --test` → all green, including the two unpinned tests from Task 9. This is the bucketing assertion from `tests/data.test.js` proving §7.4.1 on real output.

- [x] **Step 3: Classify what is pending and rebuild**

`python3 -m tools.getup pending --today 2026-10-21 --from-dir docs/research/2026-10-21 --sources leaan popit` → the agent answers `build/labels.pending.jsonl` with its own model access → `python3 -m tools.getup labels --labels build/labels.jsonl` → rebuild. Expected: `data/2026-10-2*.json` now carry real `scene` chips in the portal; `git status` shows only intended changes.

- [x] **Step 4: Confirm the second build changed nothing**

`git diff --stat data/ venue/` after an identical `build` with the same `--today` → empty. A different `--today` legitimately moves `seen.last` inside the day files, every venue's `seen_last` in `venue/venues.json`, and `generated_at`; nothing else.

- [x] **Step 5: Prove the live adapters once, by hand**

`GETUP_LIVE=1 python3 -m unittest tests_py.test_scan_leaan tests_py.test_biluim -v` on the phone host. Expected: the Leaan category pages still answer and yield >0 drafts; the Biluim listing still yields cards. If they do not, fix the adapter before the scheduler exists — this is the hidden cost §10 names.

- [x] **Step 6: Commit** — `git add data venue && git commit -m "data: first pipeline run over the research capture"`

---


**Accepted 2026-10-22, live.** No `--from-dir`: the run fetched all five URLs from
`leaan.co.il`, `popit.events` and `biluim.co.il` (see
`.superpowers/sdd/2026-10-22-getup-pipeline/acceptance-report.md`). `--today 2026-10-22`,
30 dates through `2026-11-20`. `--sources leaan,popit` above was a typo: argparse takes
`--sources leaan popit`. Ticking the boxes means the acceptance happened, not that the
commands ran byte-for-byte as written.

## Notes the reader will want

- **`daypart` is deliberately absent.** The client reads `format`, `expensive` and `commitment` as chips and never reads a time-of-day bucket; emitting one would be a maintained lie. The old fixtures still carry the field, and the client ignores it, so nothing breaks while they are replaced.
- **`seen.last` is the only per-run field inside a date file.** It is scan history mandated by §7.2, not a generation timestamp; a same-day re-run therefore stays byte-identical while a next-day run legitimately differs. `venue/venues.json` carries the same truth as `seen_last` on each venue — a hall whose feed was read today but whose next event is 40 days out has no record anywhere, so the registry is the only place the alarm can learn it. **Consequence: `venues.json` may change daily**, so byte-identity holds for same-day re-runs, not across days.
- **`tags` is internal.** It exists so `classify.rules` can fall back on the source's own categories; `write.write_days` strips it, so the client never sees a key it does not read.
- **A broken source is loud, not fatal.** `data/index.json` carries `sources[name] = {status, count, failures}`, so the client footer can say "Popit failed last night" while the rest of the portal stays up. A `partial` or `failed` run prunes and archives nothing.
- **`unpinned` is the honest count.** A venue the capture cannot place, or one whose minutes were never cached, publishes null minutes instead of a guessed number, and every served record it produces is counted; the count tells you how many, and the client already has the `זמן נסיעה לא ידוע` label for them. City-centroid minutes are a shortcut, and `coords_source` says so on the venue.
- **`price_max` is emitted as `null`** because no current source states a maximum: Leaan's `multi_price` is a boolean, not a range.
- **Classification is a committed cache (`data/labels.json`), not a network call in the build.** `build` only reads it. A missing or broken model never blocks the daily write, never breaks byte-identity, and is repaired by running `pending`/`labels` when the agent has time.

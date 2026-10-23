# GetUp Site Implementation Plan

**Status: executed** — the client, completed in branch `feat/getup-site` and merged as
PR #1 (`748f08e`); history `0506b55..d552d02`. Final: **141** client tests
(`node --test`), all passing. Task bodies below are the plan as written, not a report.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the GetUp portal as a dependency-free static site that renders real event data from committed JSON — table + map on desktop, one card per event on mobile.

**Architecture:** Vanilla ES modules, no bundler. Every decision lives in a pure module that returns data or HTML strings, so `node --test` can prove it with zero packages; `app.js` is the only file that touches the DOM and stays thin. Event data is fetched per date through a manifest and never derived in the browser.

**Tech Stack:** HTML5, CSS custom properties, ES2022 modules, `node --test` (dev only, no dependencies), MapLibre GL 6 + OpenFreeMap, Rubik + Secular One self-hosted.

**Spec:** `docs/superpowers/specs/2026-10-18-getup-design.md` (read §7 and §9 before starting; the ADRs in `docs/adr/` override where they disagree).

## Global Constraints

- **No build step.** No bundler, no transpiler, no runtime npm dependency. `package.json` exists only to set `"type": "module"` and `"test": "node --test"`; its `dependencies` must stay empty.
- ES modules only, loaded with `<script type="module">`.
- `<html lang="he" dir="rtl">` on every page. No i18n layer, no English strings.
- Type: **Rubik** variable for everything; **Secular One** only for the wordmark. Self-hosted under `assets/fonts/`, `font-display: swap`.
- Colours: `#EA580C` events, `#2563EB` map/cool, `#FFF7ED` day base, `#0B1120` night base, `#0F172A` day text, `#F1F5F9` night text. **Dark text on orange only** (white-on-orange fails contrast).
- Density: 40px table rows, 13px body, 11px chips, 8px spacing base.
- **No `text-transform: uppercase`** — the language has no uppercase.
- Chips always carry **icon + Hebrew label**. Never icon-only.
- Unknown never hides an event. No field may render as `undefined`, `null`, `NaN`, or `"₪null"`.
- Timezone is `Asia/Jerusalem`. Dates are ISO `YYYY-MM-DD`; timestamps are unix seconds.
- MapLibre pinned **≥ 6.15.0** (4.x renders Hebrew reversed). The tile style URL lives in one config constant, never inline in logic.
- Serve horizon is 30 days; the default date filter is **7 days**.
- Data age (`generated_at` from the manifest) is always visible in the footer.
- Every task ends green: `node --test` passes and the changed files are committed.

## Review Focus

The spec implies these and no task's happy path exercises them. Each has a test pinned to the
owning task.

1. **Mixed Hebrew/Latin titles** — `MADONNA THE TRIBUTE SHOW - מופע מחווה למדונה`. Bidi reordering must not scramble the Latin run or move its punctuation. (Task 5)
2. **Sparse records** — every optional field missing at once. Must render placeholders, survive filters, and never leak `undefined`/`null`/`NaN`. (Task 5)
3. **Empty result set** — e.g. "today" on a quiet Sunday. Must show a real empty state with counts, not a blank list. (Task 5)
4. **Distances that cannot be recomputed** — geolocation denied, or OSRM unreachable. Must fall back to cached minutes **and say so**, never show silently wrong numbers. (Task 8)
5. **Long Hebrew titles** — must truncate visually without losing the string and without breaking the fixed table layout. (Task 5)

---

## File Structure

| File | Responsibility |
|---|---|
| `package.json` | module marker + `test` script. No dependencies. |
| `src/format.js` | Pure formatting: relative days, day labels, time ranges, leave-by, prices, data age. |
| `src/data.js` | Manifest + per-date fetch, in-memory cache, graceful missing-date handling. |
| `src/filters.js` | Filter state, defaults, localStorage round-trip, predicate, ordering. |
| `src/chips.js` | Closed vocabulary → chip HTML. The only place tags become markup. |
| `src/render.js` | Table HTML, card HTML, empty state HTML. Strings only, no DOM. |
| `src/prefs.js` | never/always rules from `prefs.json`. |
| `src/distance.js` | OSRM `/table` recompute for a non-default centre, with fallback signal. |
| `src/map.js` | MapLibre init, Hebrew label forcing, markers. |
| `app.js` | Bootstrap + DOM wiring only. The single impure file. |
| `index.html` | Markup shell. |
| `styles.css` | Design tokens, day/night themes, table + cards, RTL via logical properties. |
| `data/*.json`, `venue/venues.json`, `prefs.json` | Committed fixtures in this plan; live data later. |
| `tests/*.test.js` | `node --test` suites, one per source module. |

---

### Task 1: Skeleton and `src/format.js`

**Files:**
- Create: `package.json`, `.gitignore`, `src/format.js`, `tests/format.test.js`

**Interfaces:**
- Produces:
  - `relDay(isoDate: string, today: string): string | null` → `'היום' | 'מחר' | 'מחרתיים' | 'בעוד N ימים' | null`
  - `dayLabel(isoDate: string): string` → `'יום שישי, 23 באוקטובר'`
  - `timeRange(startUnix: number, endUnix: number): string` → `'21:30–23:30'`
  - `leaveBy(startUnix: number, driveMin: number): string` → `'HH:MM'`, computed as start − drive − 30, in `Asia/Jerusalem`
  - `priceLabel(ev: {price_from?: number|null, free?: boolean}): {text: string, kind: 'free'|'paid'|'unknown'}`
  - `dataAge(generatedAt: string, now: Date): string` → `'עודכן לפני 3 שעות'`

- [ ] **Step 1: Create the project skeleton**

`package.json`:
```json
{ "name": "getup", "private": true, "type": "module", "scripts": { "test": "node --test" } }
```
`.gitignore`: `node_modules/`, `.DS_Store`, `*.log`.
Run `git init` if the directory is not yet a repository.

- [ ] **Step 2: Write the failing tests**

```js
// tests/format.test.js
import test from 'node:test';
import assert from 'node:assert/strict';
import { relDay, dayLabel, timeRange, leaveBy, priceLabel, dataAge } from '../src/format.js';

const T0 = Date.UTC(2026, 9, 18, 21, 0); // 2026-10-18 21:00Z

test('relDay names the near days and counts the rest', () => {
  assert.equal(relDay('2026-10-18', '2026-10-18'), 'היום');
  assert.equal(relDay('2026-10-19', '2026-10-18'), 'מחר');
  assert.equal(relDay('2026-10-20', '2026-10-18'), 'מחרתיים');
  assert.equal(relDay('2026-10-23', '2026-10-18'), 'בעוד 5 ימים');
  assert.equal(relDay('2026-11-30', '2026-10-18'), null);
});

test('leaveBy subtracts drive time and a 30 minute buffer', () => {
  // 21:30 Asia/Jerusalem on 2026-10-23 = 18:30Z; 29 min drive + 30 buffer => 20:31 local
  const start = Math.floor(new Date('2026-10-23T18:30:00Z').getTime() / 1000);
  assert.equal(leaveBy(start, 29), '20:31');
});

test('timeRange never renders a negative span', () => {
  assert.equal(timeRange(T0 / 1000, T0 / 1000 + 7200), '00:00–02:00');
  assert.equal(timeRange(T0 / 1000, T0 / 1000), '00:00–00:00');
});

test('priceLabel distinguishes free, paid and unknown', () => {
  assert.deepEqual(priceLabel({ free: true, price_from: 0 }), { text: 'חינם', kind: 'free' });
  assert.deepEqual(priceLabel({ price_from: 174 }), { text: '₪174', kind: 'paid' });
  assert.deepEqual(priceLabel({}), { text: 'מחיר לא ידוע', kind: 'unknown' });
  assert.deepEqual(priceLabel({ price_from: null }), { text: 'מחיר לא ידוע', kind: 'unknown' });
});

test('dayLabel is Hebrew and date-stable', () => {
  assert.equal(dayLabel('2026-10-23'), 'יום שישי, 23 באוקטובר');
});
```

- [ ] **Step 3: Run the tests and confirm they fail**

Run: `node --test tests/format.test.js`
Expected: FAIL — `Cannot find module '../src/format.js'`.

- [ ] **Step 4: Implement `src/format.js`**

Use `Intl.DateTimeFormat('he-IL', { timeZone: 'Asia/Jerusalem', … })` for every rendered time; never `Date#getHours()`, which follows the host zone. Day arithmetic operates on `YYYY-MM-DD` strings via `Date.UTC` to avoid DST drift. `priceLabel` returns `kind: 'unknown'` for `undefined`, `null`, and non-finite values.

- [ ] **Step 5: Run the tests and confirm they pass**

Run: `node --test`
Expected: PASS, 5 tests.

- [ ] **Step 6: Commit**

```bash
git add package.json .gitignore src/format.js tests/format.test.js
git commit -m "feat: project skeleton and pure formatting module"
```

---

### Task 2: Fixtures, manifest and loader

**Files:**
- Create: `src/data.js`, `tests/data.test.js`
- Create: `venue/venues.json`, `prefs.json`, `data/index.json`, `data/2026-10-23.json` … one file per fixture date

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `loadManifest(base = '.'): Promise<Manifest>` where `Manifest = { generated_at: string, dates: {date: string, count: number}[], coverage: {checked: number, missed: {venue_id: string, name: string}[]} }`
  - `loadDate(base, isoDate): Promise<Event[]>` — resolves `[]` (never rejects) when the file is absent; every returned event carries `day: isoDate`, so downstream modules never need the filename
  - `loadVenues(base): Promise<Record<string, Venue>>`
  - `clearCache(): void`
  - `Event` shape exactly as spec §7.2 plus `day`; `Venue` as spec §7.3 but stored as an object map keyed by id.

- [ ] **Step 1: Generate fixtures from the research capture**

Source: `docs/research/2026-10-21/leaan-events.json` and `geo-drive.json`. Select 13 records with distinct titles across ≥8 cities, preserving real titles, venues, prices and drive minutes. Add one Popit event from `popit.xml`.

**Do not invent data** (controller rulings R-A/R-B): no record may set `free: true` unless the source states it — the capture never does, so the Popit record carries `free: false` and `price_from: null`. Do not manufacture a sparse record by nulling real fields; Task 5 builds its own sparse object inside its test. `expensive` is p90 of the fixture set at `Math.floor(0.9 * n)`, or ≥ ₪200.

Write them into `data/<date>.json` grouped by **the date the event belongs to** — its start date in `Asia/Jerusalem`, except a start between 00:00 and 05:59, which belongs to the previous day (spec §7.4.1). Then write `data/index.json` listing those dates with counts and `generated_at`. Venue identity comes from `venue/venues.json`; do not invent a venue that is not in it.

- [ ] **Step 2: Write the failing tests**

```js
// tests/data.test.js
import test from 'node:test';
import assert from 'node:assert/strict';
import { loadManifest, loadDate, loadVenues } from '../src/data.js';

const BASE = new URL('..', import.meta.url).pathname;

test('manifest lists dates and counts', async () => {
  const m = await loadManifest(BASE);
  assert.ok(m.generated_at);
  assert.ok(m.dates.length > 0);
  assert.ok(m.dates.every(d => /^\d{4}-\d{2}-\d{2}$/.test(d.date)));
});

test('every manifest date has a file with the promised count', async () => {
  const m = await loadManifest(BASE);
  for (const d of m.dates) {
    const evs = await loadDate(BASE, d.date);
    assert.equal(evs.length, d.count, `${d.date} count mismatch`);
  }
});

test('a missing date resolves to an empty list, never throws', async () => {
  assert.deepEqual(await loadDate(BASE, '1999-01-01'), []);
});

test('venues are keyed by id and every fixture event resolves its venue', async () => {
  const venues = await loadVenues(BASE);
  const m = await loadManifest(BASE);
  for (const d of m.dates) {
    for (const ev of await loadDate(BASE, d.date)) {
      assert.ok(venues[ev.venue_id], `missing venue ${ev.venue_id} in ${d.date}`);
    }
  }
});
```

- [ ] **Step 3: Run the tests and confirm they fail**

Run: `node --test tests/data.test.js`
Expected: FAIL — `Cannot find module '../src/data.js'`.

- [ ] **Step 4: Implement `src/data.js`**

`loadDate` catches fetch/parse errors and returns `[]`, logging one `console.warn`; a missing file must never blank the UI (Review Focus 3). Cache parsed dates in a `Map` keyed by date.

The same module must read files in the browser (`fetch`) and in Node tests (`fs`), with no build step. Resolve it with one environment branch, not two code paths:

```js
const defaultRead = async (path) => {
  if (typeof window !== 'undefined') return (await fetch(path)).json();
  const { readFile } = await import('node:fs/promises');
  return JSON.parse(await readFile(path, 'utf8'));
};
```

`base` is a directory path: `'.'` in the browser, the repo root in tests. `import('node:fs/promises')` is never reached in the browser and, with no bundler, is never even requested.

- [ ] **Step 5: Run the tests and confirm they pass**

Run: `node --test`
Expected: PASS, including the fixture integrity tests.

- [ ] **Step 6: Commit**

```bash
git add src/data.js tests/data.test.js data venue prefs.json
git commit -m "feat: committed fixtures, manifest and data loader"
```

---

### Task 3: `src/filters.js`

**Files:**
- Create: `src/filters.js`, `tests/filters.test.js`

**Interfaces:**
- Consumes: `Event` from Task 2.
- Produces:
  - `defaultState(): State` = `{ centre: {lat: 32.3286, lon: 34.8566, label: 'נתניה'}, dateWindow: 'week', range: null, maxDriveMin: 45, maxPrice: null, freeOnly: false, age: null, hasTickets: false, includeGated: true, scenes: [], crowds: [] }`
  - `applyFilters(events: Event[], state: State, today: string): Event[]`
  - `sortEvents(events: Event[]): Event[]` — ascending `day`, then `notable` first, then ascending `drive_min`
  - `serializeState(state): string` / `deserializeState(json: string | null): State` — round-trips, ignores unknown keys, falls back to `defaultState()` on garbage

  Date filtering compares `ev.day` (a `YYYY-MM-DD` string attached by Task 2) against `today`, so no unix/timezone arithmetic happens in the browser. `applyFilters` therefore takes `today` explicitly rather than reading the clock.

- [ ] **Step 1: Write the failing tests**

```js
// tests/filters.test.js
import test from 'node:test';
import assert from 'node:assert/strict';
import { defaultState, applyFilters, sortEvents, serializeState, deserializeState } from '../src/filters.js';

const TODAY = '2026-10-18';
const ev = (o = {}) => ({ id: 'x', title: 't', venue_id: 'v', city: 'c', day: '2026-10-20',
  start: 0, end: 0, drive_min: 20, price_from: 100, free: false, soldout: false,
  notable: false, scene: [], crowd: [], urls: {}, ...o });

test('defaults match the spec', () => {
  const s = defaultState();
  assert.equal(s.dateWindow, 'week');
  assert.equal(s.maxDriveMin, 45);
  assert.equal(s.centre.label, 'נתניה');
});

test('the week window keeps days 0..7 and drops the rest', () => {
  const soon = ev({ id: 'soon', day: '2026-10-20' });
  const late = ev({ id: 'late', day: '2026-11-15' });
  const r = applyFilters([soon, late], defaultState(), TODAY);
  assert.deepEqual(r.map(e => e.id), ['soon']);
});

test('unknown age never hides an event; a stated exclusion does', () => {
  const unknown = ev({ crowd: [] });
  const minorOnly = ev({ crowd: ['18+'] });
  const s = { ...defaultState(), age: 16 };
  assert.deepEqual(applyFilters([unknown], s, TODAY).map(e => e.id), ['x']);
  assert.deepEqual(applyFilters([minorOnly], s, TODAY), []);
});

test('unknown price survives a max-price filter', () => {
  assert.equal(applyFilters([ev({ price_from: null })], { ...defaultState(), maxPrice: 100 }, TODAY).length, 1);
});

test('free-only keeps free events and drops priced ones', () => {
  const r = applyFilters([ev({ id: 'free', free: true, price_from: 0 }), ev({ price_from: 50 })],
    { ...defaultState(), freeOnly: true }, TODAY);
  assert.deepEqual(r.map(e => e.id), ['free']);
});

test('gated-community events follow the include toggle', () => {
  const gated = ev({ id: 'g', urls: { community: 'https://facebook.com/groups/x' } });
  assert.equal(applyFilters([gated], { ...defaultState(), includeGated: false }, TODAY).length, 0);
  assert.equal(applyFilters([gated], { ...defaultState(), includeGated: true }, TODAY).length, 1);
});

test('scene and crowd filters match any selected tag', () => {
  const rock = ev({ id: 'rock', scene: ['רוק'], crowd: ['30+'] });
  const jazz = ev({ id: 'jazz', scene: ['ג׳אז'], crowd: [] });
  assert.deepEqual(applyFilters([rock, jazz], { ...defaultState(), scenes: ['רוק'] }, TODAY).map(e => e.id), ['rock']);
  assert.deepEqual(applyFilters([rock, jazz], { ...defaultState(), crowds: ['30+'] }, TODAY).map(e => e.id), ['rock']);
});

test('drive filter excludes only known-too-far events', () => {
  const r = applyFilters([ev({ drive_min: 90 })], { ...defaultState(), maxDriveMin: 30 }, TODAY);
  assert.deepEqual(r, []);
  const missing = applyFilters([ev({ drive_min: null })], { ...defaultState(), maxDriveMin: 30 }, TODAY);
  assert.equal(missing.length, 1, 'missing drive data is not "too far" — it must pass');
});

test('sort puts notable first within a day, then nearest', () => {
  const a = ev({ id: 'a', day: '2026-10-20', drive_min: 10 });
  const b = ev({ id: 'b', day: '2026-10-20', drive_min: 40, notable: true });
  const c = ev({ id: 'c', day: '2026-10-20', drive_min: 5 });
  const d = ev({ id: 'd', day: '2026-10-19', drive_min: 90 });
  assert.deepEqual(sortEvents([a, b, c, d]).map(e => e.id), ['d', 'b', 'c', 'a']);
});

test('state round-trips and survives garbage', () => {
  const s = { ...defaultState(), maxPrice: 120, scenes: ['רוק'] };
  assert.deepEqual(deserializeState(serializeState(s)), s);
  assert.deepEqual(deserializeState('{not json'), defaultState());
  assert.equal(deserializeState('{"nonsense":1}').dateWindow, 'week');
});
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `node --test tests/filters.test.js`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/filters.js`**

The age predicate removes an event only when `crowd` contains an explicit `'18+'` and the user's age is below 18 — nothing else. `null` drive/price values are missing data and must pass every filter (ADR-0006). Date windows compare `ev.day` against `today` as `YYYY-MM-DD` strings; `range` uses `{from, to}` inclusive.

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `node --test`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/filters.js tests/filters.test.js
git commit -m "feat: filter state, predicates and ordering"
```

---

### Task 4: `src/chips.js`

**Files:**
- Create: `src/chips.js`, `tests/chips.test.js`

**Interfaces:**
- Produces:
  - `VOCAB = { scene: string[], crowd: string[], format: string[] }` — exact lists from spec §7.7
  - `chipsHTML(ev: Event, max?: number): string`
  - `chip(kind: 'scene'|'crowd', label: string): string` — one chip

- [ ] **Step 1: Write the failing tests**

```js
// tests/chips.test.js
import test from 'node:test';
import assert from 'node:assert/strict';
import { chipsHTML, chip, VOCAB } from '../src/chips.js';

test('vocabulary is the closed list from the spec', () => {
  assert.ok(VOCAB.scene.includes('מופע מחווה'));
  assert.ok(VOCAB.crowd.includes('להט״ב'));
  assert.ok(VOCAB.format.includes('dj_set'));
});

test('a chip always carries an icon and a Hebrew label', () => {
  const html = chip('scene', 'רוק');
  assert.match(html, /<svg/);
  assert.match(html, />רוק</);
  assert.match(html, /title="רוק"/);
});

test('scene and crowd render in different colours', () => {
  assert.match(chip('scene', 'רוק'), /chip s/);
  assert.match(chip('crowd', '30+'), /chip c/);
});

test('the cap collapses the remainder into +N with a hover title', () => {
  const ev = { scene: ['רוק', 'פופ', 'ג׳אז'], crowd: ['30+', 'להט״ב'] };
  const html = chipsHTML(ev, 3);
  assert.equal((html.match(/class="chip [sc]"/g) || []).length, 3);
  assert.match(html, /\+2/);
  assert.match(html, /title="30\+ · להט״ב"/);
});

test('an event with no tags yields an empty strip, not a placeholder chip', () => {
  assert.equal(chipsHTML({ scene: [], crowd: [] }), '');
});
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `node --test tests/chips.test.js`

- [ ] **Step 3: Implement `src/chips.js`**

One inline `<svg>` per axis (music note for scene, two-people glyph for crowd), `aria-hidden="true"`, 12×12. Labels are escaped. Tags not in `VOCAB` are dropped, never rendered.

- [ ] **Step 4: Run and confirm pass** — `node --test`

- [ ] **Step 5: Commit**

```bash
git add src/chips.js tests/chips.test.js
git commit -m "feat: closed-vocabulary chip rendering"
```

---

### Task 5: `src/render.js`

**Files:**
- Create: `src/render.js`, `tests/render.test.js`

**Interfaces:**
- Consumes: `relDay`, `dayLabel`, `timeRange`, `startTime`, `leaveBy`, `priceLabel` (Task 1); `chipsHTML` (Task 4).
- Produces:
  - `tableHTML(events: Event[], today: string, venues: Record<string, Venue>): string`
  - `cardsHTML(events: Event[], today: string, venues: Record<string, Venue>): string`
  - `emptyHTML(manifest: Manifest, today: string): string`

  **Amended after review (R-D/R-E/R-F):** the location slot renders venue + city + distance from the registry (never `source.name`), each part in `<bdi>`; an unknown `end` renders the start clock alone via `startTime`; cards emit a real `<p class="note">` and the info affordance is a focusable `<button aria-label="מידע נוסף">`; every `href` goes through `safeUrl` (http/https or in-site only).

- [ ] **Step 1: Write the failing tests**

```js
// tests/render.test.js
import test from 'node:test';
import assert from 'node:assert/strict';
import { tableHTML, cardsHTML, emptyHTML } from '../src/render.js';

const base = { venue_id: 'v', city: 'תל אביב', start: 1792780200, end: 1792787400,
  drive_min: 29, price_from: 174, free: false, soldout: false, notable: false,
  scene: ['פופ'], crowd: ['30+'], notes: [], urls: { tickets: 'https://x' }, seen: {} };
const two = [
  { ...base, id: '1', title: 'MADONNA THE TRIBUTE SHOW - מופע מחווה למדונה', day: '2026-10-23' },
  { ...base, id: '2', title: 'ערב ג׳אז', day: '2026-10-23', notable: true },
];

test('one table only — headers and bodies cannot drift apart', () => {
  const html = tableHTML(two, '2026-10-18');
  assert.equal((html.match(/<table/g) || []).length, 1);
  assert.equal((html.match(/<col /g) || []).length, 5);
});

test('mixed Hebrew and Latin title survives verbatim, isolated for bidi', () => {
  const html = tableHTML(two, '2026-10-18');
  assert.ok(html.includes('MADONNA THE TRIBUTE SHOW - מופע מחווה למדונה'));
  assert.match(html, /<bdi>MADONNA THE TRIBUTE SHOW - מופע מחווה למדונה<\/bdi>/);
});

test('sparse record renders placeholders and no undefined or null', () => {
  const sparse = { id: '9', title: 'אירוע', day: '2026-10-23', venue_id: 'v', city: null,
    start: 1792780200, end: null, drive_min: null, price_from: null, free: false,
    soldout: false, notable: false, scene: [], crowd: [], notes: [], urls: {}, seen: {} };
  const html = tableHTML([sparse], '2026-10-18');
  assert.doesNotMatch(html, /undefined|null|NaN|₪null/);
});

test('long titles are kept whole and left to CSS to truncate', () => {
  const long = { ...base, id: '3', day: '2026-10-23', title: 'מסיבת '.repeat(40) };
  assert.ok(tableHTML([long], '2026-10-18').includes(long.title));
});

test('cards cap the strip and carry the leave-by line', () => {
  const html = cardsHTML([{ ...two[0], scene: ['רוק', 'פופ', 'ג׳אז'], crowd: ['30+', 'להט״ב'] }], '2026-10-18');
  assert.match(html, /<article class="card"/);
  assert.match(html, /\+2/);
  assert.match(html, /צא /);
});

test('empty state reports real counts from the manifest', () => {
  const m = { generated_at: '2026-10-18T16:00:00Z', dates: [{ date: '2026-10-22', count: 6 }], coverage: { checked: 0, missed: [] } };
  const html = emptyHTML(m, '2026-10-18');
  assert.match(html, /אין/);
  assert.match(html, /6/);
});
```

- [ ] **Step 2: Run the tests and confirm they fail** — `node --test tests/render.test.js`

- [ ] **Step 3: Implement `src/render.js`**

Wrap every title in `<bdi>` (Review Focus 1). Day separators are `<tr class="dayrow"><td colspan="5">`. Emit `<colgroup>` with widths `122px`, auto, `30%`, `104px`, `132px`. Escape all interpolated text. Missing values go through Task 1's formatters, which return Hebrew placeholders.

- [ ] **Step 4: Run and confirm pass** — `node --test`

- [ ] **Step 5: Commit**

```bash
git add src/render.js tests/render.test.js
git commit -m "feat: table, card and empty-state renderers"
```

---

### Task 6: `src/prefs.js`

**Files:**
- Create: `src/prefs.js`, `tests/prefs.test.js`

**Interfaces:**
- Produces:
  - `loadPrefs(base = '.'): Promise<Prefs>` where `Prefs = { never: Rule[], always: Rule[] }`, `Rule = { venue_id?: string, artist?: string }`
  - `applyPrefs(events: Event[], prefs: Prefs): Event[]` — `never` removes, `always` forces `notable = true`

- [ ] **Step 1: Write the failing tests**

```js
// tests/prefs.test.js
import test from 'node:test';
import assert from 'node:assert/strict';
import { applyPrefs } from '../src/prefs.js';

const ev = (o) => ({ id: '1', title: 't', venue_id: 'v1', notable: false, ...o });

test('never removes by venue id', () => {
  const p = { never: [{ venue_id: 'v1' }], always: [] };
  assert.deepEqual(applyPrefs([ev({})], p), []);
});

test('always promotes to notable without removing anything', () => {
  const p = { never: [], always: [{ venue_id: 'v1' }] };
  const r = applyPrefs([ev({}), ev({ id: '2', venue_id: 'v2' })], p);
  assert.equal(r.length, 2);
  assert.equal(r[0].notable, true);
  assert.equal(r[1].notable, false);
});

test('an empty prefs file changes nothing', () => {
  const e = ev({});
  assert.deepEqual(applyPrefs([e], { never: [], always: [] }), [e]);
});
```

- [ ] **Step 2: Run the tests and confirm they fail** — `node --test tests/prefs.test.js`

- [ ] **Step 3: Implement `src/prefs.js`**

`loadPrefs` resolves `{never: [], always: []}` when the file is missing or malformed. Rules match on `venue_id` first, then on an exact normalized title match for `artist`.

- [ ] **Step 4: Run and confirm pass** — `node --test`

- [ ] **Step 5: Commit**

```bash
git add src/prefs.js tests/prefs.test.js
git commit -m "feat: never/always preferences"
```

---

### Task 7: Shell — `index.html`, `styles.css`, `app.js`

**Files:**
- Create: `index.html`, `styles.css`, `app.js`

**Interfaces:**
- Consumes: everything from Tasks 1–6.
- Produces: a page at `index.html` that boots with no console errors.

- [ ] **Step 1: Vendor the assets**

Download Rubik variable (`wght 300..800`, latin + hebrew subsets) and Secular One as `woff2` into `assets/fonts/`; download `maplibre-gl.js` and `maplibre-gl.css` version **6.15.0 or later** into `assets/maplibre/`. Declare `@font-face` in `styles.css` with `font-display: swap`. Nothing loads from a CDN at runtime.

- [ ] **Step 2: Write `index.html`**

`<html lang="he" dir="rtl">`. Sticky header: wordmark (`GetUp`, Secular One), centre label, view toggle (מחשב/נייד), theme toggle (יום/לילה). Filter bar with the controls from spec §7.10. `<main>` with `#list` and `#map`. Footer with `#data-age` and a coverage line. `<script type="module" src="./app.js">`.

- [ ] **Step 3: Write `styles.css`**

Tokens as CSS custom properties on `:root` and `[data-theme="night"]`, exact values from Global Constraints. `table-layout: fixed`. Logical properties only (`margin-inline-start`, `padding-inline`), never `left`/`right`. Day/night map treatment is a CSS filter, labelled as a v1 shortcut in a comment. Respect `prefers-reduced-motion`.

- [ ] **Step 4: Write `app.js`**

Boot: `loadManifest` → `loadDate` for every manifest date → `loadVenues`, `loadPrefs` → `applyPrefs` → `applyFilters` → `sortEvents` → render into `#list`, **passing the venues map as the third argument to `tableHTML`/`cardsHTML`**; paint the footer from `dataAge`.

Build filter state only from `defaultState()` (a partial state silently hides gated events — see the Task 3 ledger note), and wire the info `<button>` so tapping a card reveals its `.note`. Every filter control writes state through `serializeState` to `localStorage` and re-renders. View toggle flips `document.body.dataset.view`; theme flips `data-theme`.

- [ ] **Step 5: Verify by hand**

Run: `python3 -m http.server 8080` in the repo root, open `http://localhost:8080`.
Expected: 13 events across the fixture dates; the table renders with aligned columns; toggling נייד switches to cards; toggling לילה switches palette; no console errors.

- [ ] **Step 6: Commit**

```bash
git add index.html styles.css app.js
git commit -m "feat: page shell, design tokens and app wiring"
```

---

### Task 8: `src/distance.js` and `src/map.js`

**Files:**
- Create: `src/distance.js`, `src/map.js`, `tests/distance.test.js`
- Modify: `app.js`

**Interfaces:**
- Produces:
  - `recomputeDistances(events: {lat:number, lon:number}[], centre: {lat:number, lon:number}): Promise<number[] | null>` — one OSRM `/table` request; `null` on any failure
  - `initMap(el: HTMLElement, opts: {styleUrl: string}): Map`
  - `drawMarkers(map, events: Event[]): void`
  - `MAP_STYLE_URL` constant — the only place the tile URL appears

- [ ] **Step 1: Write the failing test**

```js
// tests/distance.test.js
import test from 'node:test';
import assert from 'node:assert/strict';
import { recomputeDistances } from '../src/distance.js';

test('an unreachable router returns null instead of throwing', async () => {
  const r = await recomputeDistances([{ lat: 32.1, lon: 34.8 }], { lat: 0, lon: 0 },
    { fetchImpl: async () => { throw new Error('offline'); } });
  assert.equal(r, null);
});

test('a malformed router response returns null', async () => {
  const r = await recomputeDistances([{ lat: 32.1, lon: 34.8 }], { lat: 0, lon: 0 },
    { fetchImpl: async () => ({ ok: true, json: async () => ({ code: 'NoTable' }) }) });
  assert.equal(r, null);
});
```

- [ ] **Step 2: Run and confirm it fails** — `node --test tests/distance.test.js`

- [ ] **Step 3: Implement `src/distance.js`**

`fetchImpl` is injectable so tests never hit the network. One `/table` call: origin first, destinations after; minutes are `durations[0][i+1] / 60`, rounded. Reject more than 99 destinations by chunking or returning `null` (record which in a comment).

- [ ] **Step 4: Run and confirm pass** — `node --test`

- [ ] **Step 5: Implement `src/map.js`**

`new maplibregl.Map({ style: MAP_STYLE_URL, ... })`; on `load`, rewrite every symbol layer's `text-field` to `["coalesce", ["get","name:he"], ["get","name:en"], ["get","name"]]` inside `try/catch`. Markers are DOM elements coloured per event (paid / free / sold out), with popups naming the city and leave-by. Call `map.resize()` after a view toggle.

- [ ] **Step 6: Wire centre changes in `app.js`**

On geolocation or an explicit centre change, call `recomputeDistances` for the visible set and re-render sorting and leave-by. On `null`, keep the cached `drive_min` **and** set a visible note that distances are relative to Netanya (Review Focus 4).

- [ ] **Step 7: Verify by hand** — map shows Hebrew labels in correct order; markers sit in the right cities; denying geolocation leaves the page usable.

- [ ] **Step 8: Commit**

```bash
git add src/distance.js src/map.js tests/distance.test.js app.js
git commit -m "feat: map, Hebrew labels and centre-aware drive times"
```

---

### Task 9: Accessibility and motion pass

**Files:**
- Modify: `index.html`, `styles.css`, `app.js`

**Interfaces:** none new.

- [ ] **Step 1: Add a keyboard and focus test**

```js
// tests/a11y.test.js
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');

test('document declares Hebrew and RTL', () => {
  assert.match(html, /<html[^>]+lang="he"/);
  assert.match(html, /<html[^>]+dir="rtl"/);
});

test('every control has an accessible name', () => {
  const buttons = html.match(/<button[^>]*>/g) || [];
  for (const b of buttons) assert.match(b, /aria-label=|aria-pressed=/, b);
});

test('no uppercase transform survives into the stylesheet', () => {
  const css = readFileSync(new URL('../styles.css', import.meta.url), 'utf8');
  assert.doesNotMatch(css, /text-transform:\s*uppercase/i);
});
```

- [ ] **Step 2: Run and confirm it fails, then fix each failure**

Run: `node --test tests/a11y.test.js`

- [ ] **Step 3: Add focus and toggle state**

Visible focus ring on every interactive element; `aria-pressed` on the three toggles; `aria-hidden="true"` on every decorative SVG.

- [ ] **Step 4: Make the info affordance keyboard-reachable**

The `i` note must be focusable, expose its text as `aria-label`, and open on focus as well as hover.

- [ ] **Step 5: Honour reduced motion**

Wrap every transition in `@media (prefers-reduced-motion: no-preference)`.

- [ ] **Step 6: Check contrast in both themes**

Body text ≥ 4.5:1; chips and the orange price pill ≥ 3:1. Fix by changing the token, never by adding a one-off colour.

- [ ] **Step 7: Verify on a 375px viewport**

One card per event, no horizontal scroll, tap-to-expand reveals the note.

- [ ] **Step 8: Run the whole suite**

Run: `node --test`
Expected: PASS, all suites.

- [ ] **Step 9: Commit**

```bash
git add index.html styles.css app.js tests/a11y.test.js
git commit -m "feat: accessibility, focus and reduced-motion pass"
```

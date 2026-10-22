import test from 'node:test';
import assert from 'node:assert/strict';
import { loadManifest, loadDate, loadVenues, normalizeEvent, validDates } from '../src/data.js';
import { applyFilters, defaultState } from '../src/filters.js';

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

test('every loaded event carries the day it was loaded from', async () => {
  const m = await loadManifest(BASE);
  for (const d of m.dates) {
    const evs = await loadDate(BASE, d.date);
    assert.ok(evs.every(ev => ev.day === d.date), `${d.date} lost its day`);
  }
});

const TZ = 'Asia/Jerusalem';
const ymd = new Intl.DateTimeFormat('en-CA', { timeZone: TZ, year: 'numeric', month: '2-digit', day: '2-digit' });
const hour = new Intl.DateTimeFormat('en-GB', { timeZone: TZ, hour: '2-digit', hourCycle: 'h23' });

const dayBefore = (isoDate) => {
  const [y, m, d] = isoDate.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d - 1)).toISOString().slice(0, 10);
};

test('every fixture file is the §7.4.1 bucket of its start', async () => {
  const m = await loadManifest(BASE);
  for (const d of m.dates) {
    for (const ev of await loadDate(BASE, d.date)) {
      const at = new Date(ev.start * 1000);
      const date = ymd.format(at);
      const bucket = Number(hour.format(at)) < 6 ? dayBefore(date) : date;
      assert.equal(bucket, d.date, `${ev.id} belongs to ${bucket}, not ${d.date}`);
    }
  }
});

test('generated_at is an RFC 3339 UTC timestamp', async () => {
  const m = await loadManifest(BASE);
  assert.match(m.generated_at, /Z$/);
  assert.ok(!Number.isNaN(Date.parse(m.generated_at)), 'generated_at does not parse');
});

// ── fix wave A: one normalizer at the data boundary ──────────────────────

test('a scalar scene, crowd or note becomes a one-item list instead of deleting the event', () => {
  const ev = normalizeEvent(
    { venue_id: 'v', start: 1792780200, scene: 'תיאטרון', crowd: '30+', notes: 'חניה חופשית', enrichment: 'x' },
    '2026-10-23',
  );
  assert.deepEqual(ev.scene, ['תיאטרון']);
  assert.deepEqual(ev.crowd, ['30+']);
  assert.deepEqual(ev.notes, ['חניה חופשית']);
  assert.deepEqual(ev.enrichment, ['x']);
  // the persisted scene filter must not throw on it
  assert.equal(applyFilters([ev], { ...defaultState(), scenes: ['תיאטרון'] }, '2026-10-23').length, 1);
});

test('free is strictly true and every numeric field is a finite number or null', () => {
  const ev = normalizeEvent({
    venue_id: 'v', free: 'false', price_from: '80', price_max: NaN, drive_min: '20',
    lat: '32.1', lon: undefined, start: '1792780200', end: Infinity,
  }, '2026-10-23');
  assert.equal(ev.free, false);
  for (const k of ['price_from', 'price_max', 'drive_min', 'lat', 'lon', 'start', 'end']) {
    assert.equal(ev[k], null, k);
  }
  assert.equal(normalizeEvent({ free: true }, '2026-10-23').free, true);
  assert.equal(normalizeEvent({ price_from: 80 }, '2026-10-23').price_from, 80);
});

test('a missing id is synthesized per venue, day and clock; a real id survives', () => {
  const a = normalizeEvent({ venue_id: 'v', start: 1792780200 }, '2026-10-23');
  const b = normalizeEvent({ venue_id: 'v', start: 1792780200 }, '2026-10-24');
  assert.match(a.id, /^v\|2026-10-23\|\d{2}:\d{2}$/);
  assert.notEqual(a.id, b.id, 'two days must not collapse into one distance key');
  assert.equal(normalizeEvent({ id: 'keep|me' }, '2026-10-23').id, 'keep|me');
  assert.equal(normalizeEvent({ id: '' }, '2026-10-23').id, '|2026-10-23|00:00');
});

test('a non-object record normalizes instead of throwing', () => {
  for (const v of [null, 7, 'x', ['a']]) {
    const ev = normalizeEvent(v, '2026-10-23');
    assert.equal(ev.day, '2026-10-23');
    assert.ok(ev.id.length > 0);
  }
});

test('fixture events all come back with a usable id and array-shaped tags', async () => {
  for (const ev of await loadDate(BASE, '2026-10-22')) {
    assert.ok(typeof ev.id === 'string' && ev.id.length > 0);
    for (const k of ['scene', 'crowd', 'notes']) assert.ok(Array.isArray(ev[k]), `${k} of ${ev.id}`);
  }
});

test('a manifest date that is not an ISO day is filtered out, not rendered', () => {
  const dates = validDates({ dates: [
    { date: '2026-10-22' }, { date: '2026-10-23' },
    { date: 'nope' }, { date: '2026-10-2' }, { date: 20261022 }, {}, null,
  ] });
  assert.deepEqual(dates.map(d => d.date), ['2026-10-22', '2026-10-23']);
  assert.deepEqual(validDates({}), []);
  assert.deepEqual(validDates(null), []);
});

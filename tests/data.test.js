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

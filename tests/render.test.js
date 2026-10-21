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

test('title, note and city are escaped in text and attribute contexts', () => {
  const ev = { ...base, id: '4', day: '2026-10-23', title: '<img src=x onerror=1>', city: 'א"ב',
    notes: ['חניה "חופשית" & ₪30'] };
  const html = tableHTML([ev], '2026-10-18');
  assert.doesNotMatch(html, /<img/);
  assert.match(html, /&#60;img src=x onerror=1&#62;/);
  assert.match(html, /title="חניה &#34;חופשית&#34; &#38; ₪30"/);
});

test('a sold-out event carries the badge and no live ticket link', () => {
  const ev = { ...base, id: '5', day: '2026-10-23', title: 'אזל', soldout: true };
  const html = tableHTML([ev], '2026-10-18');
  assert.match(html, /אזלו הכרטיסים/);
  assert.doesNotMatch(html, /href=/);
});

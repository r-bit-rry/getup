import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { tableHTML, cardsHTML } from '../src/render.js';

const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const css = readFileSync(new URL('../styles.css', import.meta.url), 'utf8');

// A name is visible text or an explicit label. aria-pressed is state, not a name.
const buttons = markup => [...markup.matchAll(/<button\b([^>]*)>([\s\S]*?)<\/button>/g)];
const textOf = markup => markup.replace(/<[^>]*>/g, '').replace(/&#?\w+;/g, 'x').trim();
const named = ([, attrs, inner]) => textOf(inner).length > 0 || /aria-label="[^"]+"/.test(attrs);

const base = { venue_id: 'v', city: 'תל אביב', start: 1792780200, end: 1792787400,
  drive_min: 29, price_from: 174, free: false, soldout: false, notable: false,
  scene: ['פופ'], crowd: ['30+'], notes: [], urls: { tickets: 'https://x' }, seen: {} };
const withNotes = { ...base, id: '1', title: 'ערב ג׳אז', day: '2026-10-23',
  notes: ['לא פורסם מחיר או קישור לכרטיסים'] };

test('document declares Hebrew and RTL', () => {
  assert.match(html, /<html[^>]+lang="he"/);
  assert.match(html, /<html[^>]+dir="rtl"/);
});

test('every button in the page shell has an accessible name', () => {
  const all = buttons(html);
  assert.ok(all.length > 0, 'no buttons found');
  for (const b of all) assert.ok(named(b), b[0]);
});

test('every button the renderer emits has an accessible name', () => {
  for (const out of [tableHTML([withNotes], '2026-10-18'), cardsHTML([withNotes], '2026-10-18'),
    tableHTML([{ ...base, id: '2', title: 'בלי הערות', day: '2026-10-23' }], '2026-10-18')]) {
    const all = buttons(out);
    for (const b of all) assert.ok(named(b), b[0]);
  }
  // the icon-only control is the reason this test exists
  assert.match(tableHTML([withNotes], '2026-10-18'), /<button[^>]+aria-label="מידע נוסף"/);
});

test('the toggles expose pressed state', () => {
  for (const id of ['t-day', 't-night', 'f-free', 'f-tickets', 'f-minor', 'f-gated']) {
    assert.match(html, new RegExp(`<button[^>]+id="${id}"[^>]+aria-pressed="(true|false)"`), id);
  }
});

test('no uppercase transform survives into the stylesheet', () => {
  assert.doesNotMatch(css, /text-transform:\s*uppercase/i);
});

test('the stylesheet keeps the sticky-header offset and a reduced-motion block', () => {
  assert.match(css, /scroll-padding-block-start:\s*var\(--bar-h/);
  assert.match(css, /@media\s*\(prefers-reduced-motion/);
});

test('the page declares a referrer policy and a named location control', () => {
  assert.match(html, /<meta name="referrer" content="strict-origin-when-cross-origin">/);
  const geo = buttons(html).find(([, attrs]) => /id="where-geo"/.test(attrs));
  assert.ok(geo, 'no location button');
  assert.match(geo[1], /aria-label="[^"]+"/);
  // the button finds you; the centre label marks where you are — they must not share a glyph
  assert.doesNotMatch(geo[1], /📍/);
  assert.match(geo[2], /<svg/);
});

test('the view breakpoint is the one the stylesheet uses', () => {
  const app = readFileSync(new URL('../app.js', import.meta.url), 'utf8');
  assert.match(app, /matchMedia\('\(max-width: 900px\)'\)/);
  assert.match(css, /@media \(max-width: 900px\)/);
  // and the bulk load cannot reject outside fatal()
  assert.match(app, /try \{\n\s*days = ok\n\s*\? await Promise\.all\(dates/);
});

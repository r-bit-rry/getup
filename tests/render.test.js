import test from 'node:test';
import assert from 'node:assert/strict';
import { tableHTML, cardsHTML, emptyHTML, listHTML } from '../src/render.js';

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

const venues = { v: { id: 'v', name: 'בית ציוני אמריקה (מאירהוף)' } };
const sourced = { ...base, source: { class: 'ticketing', name: 'leaan' } };

test('the location slot names the venue and city, never the ticket seller', () => {
  const ev = { ...sourced, id: '6', day: '2026-10-23', title: 'אירוע' };
  const html = tableHTML([ev], '2026-10-18', venues);
  assert.match(html, /<bdi>בית ציוני אמריקה \(מאירהוף\)<\/bdi>/);
  assert.match(html, /<bdi>תל אביב<\/bdi>/);
  assert.match(html, /<bdi>29 דק׳ נסיעה<\/bdi>/);
  assert.doesNotMatch(html, /leaan/);
  const card = cardsHTML([ev], '2026-10-18', venues);
  assert.match(card, /בית ציוני אמריקה \(מאירהוף\)/);
  assert.doesNotMatch(card, /leaan/);
});

test('an unknown venue falls back to the city alone', () => {
  const html = tableHTML([two[0]], '2026-10-18', {});
  assert.match(html, /<span class="v"><bdi>תל אביב<\/bdi>/);
  assert.doesNotMatch(html, /<i>\|<\/i><bdi>תל אביב/);
});

test('an unknown end renders a single start time, not a zero-length span', () => {
  const ev = { ...base, id: '7', day: '2026-10-23', title: 'אירוע', end: null };
  const html = tableHTML([ev], '2026-10-18');
  assert.match(html, />21:30</);
  assert.doesNotMatch(html, /21:30–21:30/);
  const card = cardsHTML([ev], '2026-10-18');
  assert.match(card, />21:30</);
  assert.doesNotMatch(card, /21:30–21:30/);
});

test('a card reveals its notes and the info affordance is a real button', () => {
  const ev = { ...base, id: '8', day: '2026-10-23', title: 'אירוע', notes: ['חניה חופשית', 'שער פתיחה 20:30'] };
  const card = cardsHTML([ev], '2026-10-18');
  assert.match(card, /<p class="note">חניה חופשית<br>שער פתיחה 20:30<\/p>/);
  assert.match(card, /<button type="button" class="ico" aria-label="מידע נוסף"/);
  // the table row carries the same note, collapsed until its own button opens it
  const table = tableHTML([ev], '2026-10-18');
  assert.match(table, /<p class="note">חניה חופשית<br>שער פתיחה 20:30<\/p>/);
  assert.match(table, /aria-expanded="false"/);
});

test('an event without notes emits no note block and no info button', () => {
  const card = cardsHTML([{ ...base, id: '9', day: '2026-10-23', title: 'אירוע' }], '2026-10-18');
  assert.doesNotMatch(card, /class="note"/);
  assert.doesNotMatch(card, /class="ico"/);
});

test('a javascript: ticket URL never reaches href', () => {
  const ev = { ...base, id: '10', day: '2026-10-23', title: 'אירוע', urls: { tickets: 'javascript:alert(1)' } };
  const html = tableHTML([ev], '2026-10-18');
  assert.doesNotMatch(html, /javascript:/);
  assert.match(html, /href="#"/);
});

test('format, expensive and plan-ahead reach the table cell and the card strip', () => {
  const ev = { ...base, id: '11', day: '2026-10-23', title: 'עפרה', scene: ['תיאטרון'],
    format: 'theatre', expensive: true, commitment: 'plan_ahead' };
  for (const html of [tableHTML([ev], '2026-10-18'), cardsHTML([ev], '2026-10-18')]) {
    assert.match(html, />תיאטרון</);
    assert.match(html, />יקר</);
    assert.match(html, />תכנון מראש</);
  }
});

test('a record without the signals renders no signal chip', () => {
  const ev = { ...base, id: '12', day: '2026-10-23', title: 'אירוע', scene: [], crowd: [],
    format: 'unknown', expensive: false, commitment: 'jump_in' };
  for (const html of [tableHTML([ev], '2026-10-18'), cardsHTML([ev], '2026-10-18')]) {
    assert.doesNotMatch(html, /יקר|תכנון מראש|הופעה חיה|מופע מחווה|תזמורת|סטנדאפ|תיאטרון|פסטיבל/);
  }
});

test('one malformed record is skipped by name; the rest still render', () => {
  const warn = console.warn;
  const calls = [];
  console.warn = (...args) => calls.push(args.join(' '));
  try {
    const bad = { ...base, id: 'bad', title: 'רשומה שבורה', day: '2026-10-23', start: undefined };
    const good = { ...base, id: 'good', title: 'רשומה תקינה', day: '2026-10-23' };
    const table = tableHTML([bad, good], '2026-10-18');
    assert.doesNotMatch(table, /רשומה שבורה/);
    assert.match(table, /רשומה תקינה/);
    assert.match(table, /אירוע אחד/);
    const cards = cardsHTML([bad, good], '2026-10-18');
    assert.doesNotMatch(cards, /רשומה שבורה/);
    assert.match(cards, /רשומה תקינה/);
  } finally {
    console.warn = warn;
  }
  assert.ok(calls.some(line => line.includes('bad')), calls.join('\n'));
});

test('a record with no ticket and no community links to its source', () => {
  const ev = { ...base, id: '13', day: '2026-10-23', title: '04 Haifa',
    urls: { tickets: null, community: null, source: 'https://popit.events/event/04-haifa' } };
  for (const html of [tableHTML([ev], '2026-10-18'), cardsHTML([ev], '2026-10-18')]) {
    assert.match(html, /href="https:\/\/popit\.events\/event\/04-haifa"[^>]*>מקור</);
  }
  const bad = { ...ev, urls: { source: 'javascript:alert(1)' } };
  assert.match(tableHTML([bad], '2026-10-18'), /href="#"/);
});

// ── fix wave A: escaping, URLs, painted count ────────────────────────────

test('control and bidi-override characters are stripped before escaping', () => {
  const ev = { ...base, id: 'b1', day: '2026-10-23', title: 'שלום\u202Eworld\u2066!\u0000\u009b' };
  const html = tableHTML([ev], '2026-10-18');
  assert.ok(html.includes('שלוםworld!'));
  assert.doesNotMatch(html, /[\u0000\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069]/);
});

test('the empty-state count is a number, not markup', () => {
  const m = { dates: [{ date: '2026-10-22', count: '0<img src=x onerror=alert(1)>' }] };
  const html = emptyHTML(m, '2026-10-18');
  assert.doesNotMatch(html, /<img|onerror/);
  assert.match(html, /0 אירועים/);
  // a numeric string is still a count
  assert.match(emptyHTML({ dates: [{ date: '2026-10-22', count: '6' }] }, '2026-10-18'), /6 אירועים/);
});

test('only http(s), a single-slash path and a fragment may reach an href', () => {
  const hrefs = ['//evil.example/x', '/\\evil.example/x', '\\\\evil.example', 'javascript:alert(1)',
    ' data:text/html,x', 'https:/evil.example'];
  for (const u of hrefs) {
    const ev = { ...base, id: 'u', day: '2026-10-23', title: 'אירוע', urls: { tickets: u } };
    assert.match(tableHTML([ev], '2026-10-18'), /href="#"/, u);
  }
  for (const u of ['https://ok.example/p?a=1&b=2', '/local/page', '#frag']) {
    const ev = { ...base, id: 'u', day: '2026-10-23', title: 'אירוע', urls: { tickets: u } };
    const html = tableHTML([ev], '2026-10-18');
    assert.ok(html.includes(`href="${u.replace(/&/g, '&#38;')}"`), u);
  }
});

test('every outbound anchor carries noopener noreferrer', () => {
  const ev = { ...base, id: 'r', day: '2026-10-23', title: 'אירוע',
    urls: { tickets: 'https://t.example', community: 'https://c.example' } };
  const out = tableHTML([ev], '2026-10-18') + cardsHTML([ev], '2026-10-18')
    + tableHTML([{ ...ev, urls: { source: 'https://s.example' } }], '2026-10-18');
  const anchors = out.match(/<a\b[^>]*>/g) ?? [];
  assert.ok(anchors.length > 0);
  for (const a of anchors) assert.match(a, /rel="noopener noreferrer"/, a);
});

test('a list whose every record fails paints an error, not an empty table, and counts zero', () => {
  const warn = console.warn;
  console.warn = () => {};
  try {
    const bad = { ...base, id: 'bad', day: '2026-10-23', title: 'שבור', start: null };
    for (const view of ['desktop', 'mobile']) {
      const r = listHTML([bad], '2026-10-18', {}, view);
      assert.equal(r.count, 0);
      assert.match(r.html, /לא הצלחנו להציג את האירועים/);
      assert.doesNotMatch(r.html, /<table|<article/);
    }
  } finally {
    console.warn = warn;
  }
});

test('the painted count counts only records that reached the list', () => {
  const warn = console.warn;
  console.warn = () => {};
  try {
    const bad = { ...base, id: 'bad', day: '2026-10-23', title: 'שבור', start: null };
    const good = { ...base, id: 'good', day: '2026-10-23', title: 'תקין' };
    for (const view of ['desktop', 'mobile']) {
      const r = listHTML([bad, good], '2026-10-18', {}, view);
      assert.equal(r.count, 1, view);
      assert.doesNotMatch(r.html, /שבור/);
    }
  } finally {
    console.warn = warn;
  }
});

test('an empty list builds nothing, so the caller can paint its own empty state', () => {
  assert.deepEqual(listHTML([], '2026-10-18'), { html: '', count: 0 });
});

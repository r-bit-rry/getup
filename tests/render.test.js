import test from 'node:test';
import assert from 'node:assert/strict';
import { tableHTML, cardsHTML, emptyHTML, listHTML, hiddenHTML, capFor } from '../src/render.js';

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
  assert.equal((html.match(/<col\b/g) || []).length, 5);
  assert.equal((html.match(/<th /g) || []).length, 5);
  // the widths are one stylesheet rule per column class, shared by the narrow shell
  assert.match(css, /\.tbl col\.c-vibe \{ width: 18% \}/);
});

test('the narrow shell drops the vibe column from the markup, never from CSS alone', () => {
  const html = tableHTML(two, '2026-10-18', {}, true);
  // a hidden cell with a surviving <col> hands the price column a zero width: both go together
  assert.equal((html.match(/<col\b/g) || []).length, 4);
  assert.equal((html.match(/<th /g) || []).length, 4);
  assert.doesNotMatch(html, /וייב/);
  assert.equal((html.match(/<td>/g) || []).length, 4 * 2); // two rows, four cells each
  assert.match(html, /colspan="4"/);
  assert.doesNotMatch(css, /col:nth-child\(3\)/);
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
  assert.doesNotMatch(html, /href="https:\/\/x"/);
  assert.doesNotMatch(html, />כרטיס</);
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
  assert.match(html, /אין אירועים בתקופה הקרובה/);
  // a numeric string is still a count
  assert.match(emptyHTML({ dates: [{ date: '2026-10-22', count: '6' }] }, '2026-10-18'), /6 אירועים/);
});

test('only http(s), a single-slash path and a fragment may reach an href', () => {
  const hrefs = ['//evil.example/x', '/\\evil.example/x', '\\\\evil.example', 'javascript:alert(1)',
    ' data:text/html,x', 'https:/evil.example', '/\t/evil.example/x', '/\u202E/evil.example/x',
    '/\u009b/evil.example'];
  for (const u of hrefs) {
    const ev = { ...base, id: 'u', day: '2026-10-23', title: 'אירוע', urls: { tickets: u } };
    assert.match(tableHTML([ev], '2026-10-18'), /href="#"/, JSON.stringify(u));
  }
  for (const u of ['https://ok.example/p?a=1&b=2', '/local/page', '#frag']) {
    const ev = { ...base, id: 'u', day: '2026-10-23', title: 'אירוע', urls: { tickets: u } };
    const html = tableHTML([ev], '2026-10-18');
    assert.ok(html.includes(`href="${u.replace(/&/g, '&#38;')}"`), u);
  }
  // the controls are stripped before the value is emitted, not after it was validated
  const dirty = { ...base, id: 'u', day: '2026-10-23', title: 'אירוע',
    urls: { tickets: 'https://ok.example/a\u0000b\u202Ec' } };
  assert.match(tableHTML([dirty], '2026-10-18'), /href="https:\/\/ok\.example\/abc"/);
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

// ── fix wave B: the subtitle, one city, the cap, the empty way out ───────

import { readFileSync } from 'node:fs';
const css = readFileSync(new URL('../styles.css', import.meta.url), 'utf8');
const desc = 'עופרה מחזמר מרגש בעקבות חייה ושיריה של כוכבת העל הישראלית שכבשה את העולם – עופרה חזה. מילדותה בשכונת התקווה ועד הבמות הגדולות.';

test('the description answers "what is this?" under the title, escaped', () => {
  const ev = { ...base, id: 'd', day: '2026-10-23', title: 'עפרה', desc };
  const table = tableHTML([ev], '2026-10-18');
  // the first clause only, not the whole description
  assert.match(table, /<span class="desc">עופרה מחזמר[^<]*עופרה חזה\.<\/span>/);
  assert.doesNotMatch(table, /מילדותה/);
  const card = cardsHTML([ev], '2026-10-18');
  assert.match(card, /<p class="desc">עופרה מחזמר/);

  const nasty = { ...ev, id: 'e', desc: '<img src=x onerror=1> מחזמר' };
  for (const html of [tableHTML([nasty], '2026-10-18'), cardsHTML([nasty], '2026-10-18')]) {
    assert.doesNotMatch(html, /<img/);
    assert.match(html, /&#60;img src=x onerror=1&#62;/);
  }
});

test('a description longer than the line is cut at a word boundary with an ellipsis', () => {
  const long = 'מילה '.repeat(60).trim();
  const html = tableHTML([{ ...base, id: 'l', day: '2026-10-23', title: 'אירוע', desc: long }], '2026-10-18');
  const text = html.match(/<span class="desc">([^<]*)<\/span>/)[1];
  assert.ok(text.length <= 121, String(text.length));
  assert.ok(text.endsWith('…'));
  assert.ok(!/מילו…/.test(text), 'a word must not be cut in half');
});

test('an empty or missing description renders no subtitle line', () => {
  for (const d of [undefined, null, '', '   ', 42]) {
    const ev = { ...base, id: 'n', day: '2026-10-23', title: 'אירוע', desc: d };
    for (const html of [tableHTML([ev], '2026-10-18'), cardsHTML([ev], '2026-10-18')]) {
      assert.doesNotMatch(html, /class="desc"/, String(d));
    }
  }
});

test('a city already inside the venue name is not printed twice', () => {
  const v = { v: { id: 'v', name: 'היכל התרבות, ראשון לציון' } };
  const ev = { ...base, id: 'c', day: '2026-10-23', title: 'עפרה', city: 'ראשון לציון',
    venue_id: 'v', drive_min: 42 };
  for (const html of [tableHTML([ev], '2026-10-18', v), cardsHTML([ev], '2026-10-18', v)]) {
    assert.equal((html.match(/ראשון לציון/g) || []).length, 1);
    // the separator between the parts that remain is kept
    assert.match(html, /<bdi>היכל התרבות, ראשון לציון<\/bdi><i aria-hidden="true">\|<\/i><bdi>42 דק׳ נסיעה<\/bdi>/);
  }
  // a venue that does not name the city still gets it
  const other = { ...ev, venue_id: 'x' };
  const html = tableHTML([other], '2026-10-18', { x: { name: 'אולם' } });
  assert.match(html, /<bdi>אולם<\/bdi><i aria-hidden="true">\|<\/i><bdi>ראשון לציון<\/bdi>/);
});

test('a long title wraps to two lines instead of truncating from the start', () => {
  // the renderer keeps the whole title; CSS is what clamps it
  const title = 'MADONNA THE TRIBUTE SHOW - מופע מחווה למדונה';
  assert.ok(tableHTML([{ ...base, id: 't', day: '2026-10-23', title }], '2026-10-18').includes(title));
  assert.match(css, /\.what \.t \{[^}]*-webkit-line-clamp:\s*2/);
  assert.doesNotMatch(css, /\.what \.t \{[^}]*(white-space:\s*nowrap|max-inline-size:\s*46ch)/);
  assert.match(css, /\.card \.t2 \{[^}]*-webkit-line-clamp:\s*2/);
});

test('the drive cap reports what it hid, and says nothing when it hid nothing', () => {
  assert.equal(hiddenHTML([]), '');
  const far = [{ drive_min: 49 }, { drive_min: 57 }, { drive_min: 49 }];
  const html = hiddenHTML(far);
  // a button, not a footnote: it can raise the cap itself
  assert.match(html, /<button[^>]+class="f hiddenbtn"[^>]+id="f-far"/);
  assert.match(html, /עוד 3 אירועים בין 49 ל־57 דק׳/);
  assert.match(html, /הצג עד 60 דק׳ נסיעה/);
  assert.match(hiddenHTML([{ drive_min: 57 }]), /עוד אירוע אחד ב־57 דק׳/);
  assert.equal(hiddenHTML([{ drive_min: null }]), '');
});

test('the cap rises to the furthest hidden event, so one press always reveals it', () => {
  // 69–80 was hidden by a 60-minute cap: a 60-minute button would change nothing
  const far = [{ drive_min: 69 }, { drive_min: 74 }, { drive_min: 80 }];
  const html = hiddenHTML(far);
  assert.match(html, /data-cap="80"/);
  assert.match(html, /הצג עד 80 דק׳ נסיעה/);
  assert.equal(capFor(far), 80);
  // a fraction is rounded up, never down onto the event it is meant to reveal
  assert.equal(capFor([{ drive_min: 74.2 }]), 75);
  assert.equal(capFor([]), null);
});

test('the empty state offers one way to widen instead of a database count', () => {
  const html = emptyHTML({ dates: [{ date: '2026-10-22', count: 14 }] }, '2026-10-18');
  assert.match(html, /יש 14 אירועים בתקופה הקרובה/);
  assert.doesNotMatch(html, /במאגר/);
  assert.match(html, /<button[^>]+id="f-widen"[^>]*>הצג את החודש הקרוב<\/button>/);
  // public Hebrew is plural, as fatal() already is
  assert.match(html, /נסו טווח רחב יותר/);
  assert.doesNotMatch(html, /נסה טווח/);
});

test('an empty page says the cap emptied it, not that nothing exists', () => {
  const m = { dates: [{ date: '2026-10-22', count: 3 }] };
  const html = emptyHTML(m, '2026-10-18', { capHidden: 2 });
  assert.doesNotMatch(html, /אין אירועים בטווח שבחרת/);
  assert.match(html, /מגבלת הנסיעה הסתירה/);
  assert.match(html, /2 אירועים/);
  assert.match(html, /הכפתור שמעל לרשימה/);
  // the plain empty state still exists when nothing was hidden
  assert.match(emptyHTML(m, '2026-10-18'), /אין אירועים בטווח שבחרת/);
});

test('an empty page caused by filters names them and offers to clear them', () => {
  const m = { dates: [{ date: '2026-10-22', count: 3 }] };
  const html = emptyHTML(m, '2026-10-18', { filters: 2 });
  assert.match(html, /הסינון שבחרת הסתיר/);
  assert.match(html, /<button[^>]+data-reset>ניקוי הסינון<\/button>/);
  assert.doesNotMatch(html, /אין אירועים בטווח שבחרת/);
});

// ── fix wave C: a running show, a repeated title, a real card separator ──

test('a show that has started shows until when exactly once', () => {
  const now = Math.floor(Date.now() / 1000);
  const ev = { ...base, id: 'live', day: '2026-10-23', title: 'עפרה',
    start: now - 1800, end: now + 1800 };
  const html = tableHTML([ev], '2026-10-18');
  assert.match(html, /<span class="h num">עד \d{2}:\d{2}<\/span>/);
  assert.doesNotMatch(html, /צא /);
  // the when-cell carries the end; the leave line must not print the same clock again
  assert.match(html, /<span class="r"><\/span>/);
  assert.equal((html.match(/עד \d{2}:\d{2}/g) || []).length, 1);
  const card = cardsHTML([ev], '2026-10-18');
  assert.match(card, /<span class="time2 num">עד \d{2}:\d{2}<\/span>/);
  assert.match(card, /<span class="leave"><\/span>/);
  assert.equal((card.match(/עד \d{2}:\d{2}/g) || []).length, 1);
  // a future event still carries the leave-by line
  assert.match(tableHTML([{ ...ev, start: now + 3600, end: now + 7200 }], '2026-10-18'), /צא /);
});

test('an event with no published end never states one, and no-end still runs', () => {
  const now = Math.floor(Date.now() / 1000);
  const open = { ...base, id: 'open', day: '2026-10-23', title: 'מסיבה', end: null,
    start: now - 900 }; // started 15 minutes ago
  for (const html of [tableHTML([open], '2026-10-18'), cardsHTML([open], '2026-10-18')]) {
    assert.doesNotMatch(html, /עד /, 'a guessed end is a fact we do not have');
    assert.match(html, /מתקיים כעת/);
  }
});

test('a subtitle that opens with the title does not repeat it', () => {
  const title = 'אורי ברויר';
  for (const desc of [
    'אורי ברויר אורי ברויר במופע סטנדאפ',
    'אורי ברויר - מופע סטנדאפ',
    'אורי ברויר – מופע סטנדאפ',
    'אורי ברויר — מופע סטנדאפ',
    'אורי ברויר: מופע סטנדאפ',
    'אורי ברויר | מופע סטנדאפ',
  ]) {
    const html = tableHTML([{ ...base, id: 'r', day: '2026-10-23', title, desc }], '2026-10-18');
    const text = html.match(/<span class="desc">([^<]*)<\/span>/)[1];
    assert.ok(!text.includes(title), `${desc} → ${text}`);
    assert.ok(text.length > 0, desc);
  }
  // a description that is only the title prints no subtitle at all
  const only = tableHTML([{ ...base, id: 'o', day: '2026-10-23', title, desc: title }], '2026-10-18');
  assert.doesNotMatch(only, /class="desc"/);
});

test('the card location line keeps its flex rule and a visible divider', () => {
  assert.match(css, /\.card \.v2 \{[^}]*display:\s*flex/);
  assert.match(css, /\.card \.v2 i \{[^}]*margin-inline/);
  // a template literal leaked into the stylesheet once and silently dropped the next rule
  assert.doesNotMatch(css, /`/);
});

// ── fix wave E: navigation, the cap that reveals, one time per row ───────

const HAIFA = { v_bar_shtenfeld_haifa: { id: 'v_bar_shtenfeld_haifa', name: 'בר שטיינפלד, חיפה' } };

test('a row and a card carry a navigation link built from venue and city', () => {
  const ev = { ...base, id: 'nav', day: '2026-10-23', title: '04 Haifa',
    venue_id: 'v_bar_shtenfeld_haifa', city: 'חיפה',
    urls: { tickets: null, community: null, source: 'https://popit.events/x' } };
  for (const html of [tableHTML([ev], '2026-10-18', HAIFA), cardsHTML([ev], '2026-10-18', HAIFA)]) {
    const href = html.match(/href="([^"]*google\.com\/maps\/dir[^"]*)"/)?.[1] ?? '';
    assert.ok(href, 'no navigation link');
    // the two address halves are one comma-separated text query, encoded once
    assert.match(href, /destination=%D7%91%D7%A8%20%D7%A9%D7%98%D7%99%D7%99%D7%A0%D7%A4%D7%9C%D7%93/);
    assert.match(href, /%2C%20%D7%97%D7%99%D7%A4%D7%94/);
    assert.match(html, />ניווט</);
    assert.match(html, /rel="noopener noreferrer"[^>]*>ניווט</);
  }
});

test('no venue and no city means no navigation link', () => {
  const orphan = { ...base, id: 'x', day: '2026-10-23', title: 'אירוע', city: '', venue_id: 'gone' };
  for (const html of [tableHTML([orphan], '2026-10-18', {}), cardsHTML([orphan], '2026-10-18', {})]) {
    assert.doesNotMatch(html, /ניווט|google\.com\/maps/);
  }
  // either half of the address is enough
  assert.match(tableHTML([{ ...orphan, city: 'חיפה' }], '2026-10-18', {}), />ניווט</);
  const venueOnly = { ...orphan, city: null, venue_id: 'v' };
  assert.match(tableHTML([venueOnly], '2026-10-18', { v: { name: 'אולם' } }), />ניווט</);
});

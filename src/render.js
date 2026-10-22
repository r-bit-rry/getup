import { relDay, dayLabel, timeRange, startTime, priceLabel, leaveText } from './format.js';
import { chipsHTML } from './chips.js';

// Control and bidi-override characters would let a title reverse its neighbours in the RTL line.
const STRIP = /[\u0000-\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069]/g;
const esc = s => String(s ?? '').replace(STRIP, '').replace(/[&<>"']/g, c => `&#${c.charCodeAt(0)};`);

// Only http(s) and same-site paths may reach an href; a scraped scheme, `//host` or `/\host` is not trusted.
// Strip the controls BEFORE validating: `/\t/evil` and `/\u202E/evil` would otherwise pass the
// allow-list as single-slash paths and reach the browser as `//evil`.
const SAFE_URL = /^(?:https?:\/\/|\/(?![/\\])|#)/i;
const safeUrl = u => {
  const clean = typeof u === 'string' ? u.replace(STRIP, '') : '';
  return SAFE_URL.test(clean) ? clean : '#';
};

const countLabel = n => (n === 1 ? 'אירוע אחד' : `${n} אירועים`);

const timeLabel = (ev, nowMs = Date.now()) => {
  // An event with no start has no honest "when": refuse the row rather than print 02:00.
  if (!Number.isFinite(ev.start)) throw new TypeError('missing start');
  const ended = Number.isFinite(ev.end) && ev.end > ev.start;
  // A running show has one clock left to print: when it ends. Its start is no longer a plan.
  if (ev.start * 1000 <= nowMs) return ended ? `עד ${startTime(ev.end)}` : startTime(ev.start);
  return ended ? timeRange(ev.start, ev.end) : startTime(ev.start);
};

const driveLabel = ev => (Number.isFinite(ev.drive_min) ? `${ev.drive_min} דק׳ נסיעה` : '');

const venueName = (ev, venues) => (venues ?? {})[ev.venue_id]?.name ?? '';

// "היכל התרבות, ראשון לציון | ראשון לציון" says the city twice for no new fact.
export const cityIn = (venue, city) => {
  const c = String(city ?? '').trim();
  return !c || String(venue ?? '').trim().endsWith(c);
};

// The phone has no map and the car may lack room: the destination is a text query, so a bad
// venue coordinate cannot break it. Omitted when neither half of the address is known.
const navLink = (ev, venues) => {
  const venue = venueName(ev, venues);
  const city = String(ev.city ?? '').trim();
  const query = [venue, cityIn(venue, city) ? '' : city].filter(Boolean).join(', ');
  if (!query) return '';
  const href = `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(query)}`;
  return `<a class="act nav" href="${esc(safeUrl(href))}" target="_blank" rel="noopener noreferrer">ניווט</a>`;
};

const location = (ev, venues) => {
  const venue = venueName(ev, venues);
  const city = String(ev.city ?? '').trim();
  const parts = [venue, cityIn(venue, city) ? '' : city, driveLabel(ev)].filter(Boolean);
  return parts.map(part => `<bdi>${esc(part)}</bdi>`).join('<i aria-hidden="true">|</i>');
};

// The record's own description is what answers "what is this?"; the first clause is enough.
const DESC_MAX = 120;
const squish = s => String(s ?? '').replace(/\s+/g, ' ').trim();

// Scrapers repeat the title at the start of the subtitle: "אורי ברויר - אורי ברויר במופע…".
const withoutTitle = (text, title) => {
  const t = squish(title);
  let out = text;
  for (let i = 0; t && i < 3 && out.startsWith(t); i++) {
    out = out.slice(t.length).replace(/^[\s\-–—:|]+/, '').trim();
    if (!out) break;
  }
  return out;
};

const descText = ev => {
  const text = typeof ev.desc === 'string' ? withoutTitle(squish(ev.desc), ev.title) : '';
  if (!text) return '';
  const clause = (text.match(/^[^.!?…]*[.!?…]?/)?.[0] ?? text).trim() || text;
  if (clause.length <= DESC_MAX) return esc(clause);
  const cut = clause.slice(0, DESC_MAX);
  const at = cut.search(/\s+\S*$/); // never cut a word in half
  return esc(`${at > 0 ? cut.slice(0, at) : cut}…`);
};

const descLine = (ev, tag = 'span') => (descText(ev) ? `<${tag} class="desc">${descText(ev)}</${tag}>` : '');

const notes = ev => (ev.notes ?? []).filter(Boolean);

const noteBlock = ev => (notes(ev).length
  ? `<p class="note">${notes(ev).map(esc).join('<br>')}</p>`
  : '');

const infoButton = ev => (notes(ev).length
  ? `<button type="button" class="ico" aria-label="מידע נוסף" aria-expanded="false" title="${esc(notes(ev).join(' · '))}">i</button>`
  : '');

const priceCell = ev => {
  const { text, kind } = priceLabel(ev);
  const until = ev.free_until ? `<span class="s">חינם עד ${esc(ev.free_until)}</span>` : '';
  const sold = ev.soldout ? '<span class="sold">אזלו הכרטיסים</span>' : '';
  return `<span class="price ${kind}">${esc(text)}</span>${until}${sold}`;
};

const links = (ev, venues) => {
  const ticket = ev.soldout
    ? '<span class="act gone">אזל</span>'
    : ev.urls?.tickets
      ? `<a class="act" href="${esc(safeUrl(ev.urls.tickets))}" target="_blank" rel="noopener noreferrer">כרטיס</a>`
      : '';
  const comm = ev.urls?.community
    ? `<a class="act comm" href="${esc(safeUrl(ev.urls.community))}" target="_blank" rel="noopener noreferrer">קבוצה</a>`
    : '';
  // A nightlife feed has no ticket and no community: its source page is the only way in.
  const source = !ev.urls?.tickets && !ev.urls?.community && ev.urls?.source
    ? `<a class="act" href="${esc(safeUrl(ev.urls.source))}" target="_blank" rel="noopener noreferrer">מקור</a>`
    : '';
  return ticket + comm + source + navLink(ev, venues);
};

const acts = (ev, venues) => `<span class="acts">${links(ev, venues)}${infoButton(ev)}</span>`;

const rowHTML = (ev, venues, compact) => `<tr class="row">
<td><span class="when"><span class="h num">${timeLabel(ev)}</span><span class="r">${leaveText(ev)}</span></span></td>
<td><span class="what"><span class="t"><bdi>${esc(ev.title)}</bdi></span>${descLine(ev)}<span class="v">${location(ev, venues)}</span></span></td>
${compact ? '' : `<td><span class="vibe">${chipsHTML(ev)}</span></td>`}
<td>${priceCell(ev)}</td>
<td>${acts(ev, venues)}${noteBlock(ev)}</td>
</tr>`;

// One <tr class="dayrow"> per calendar day; grouping is by day so an unsorted input cannot duplicate a header.
const groupByDay = events => {
  const days = new Map();
  for (const ev of events) {
    if (!days.has(ev.day)) days.set(ev.day, []);
    days.get(ev.day).push(ev);
  }
  return days;
};

const dayRowHTML = (day, count, today, compact) => {
  const rel = relDay(day, today);
  return `<tr class="dayrow"><td colspan="${compact ? 4 : 5}"><div class="dayhead">`
    + `<h2>${esc(dayLabel(day))}</h2>`
    + (rel ? `<span class="rel">${esc(rel)}</span>` : '')
    + `<span class="n">${countLabel(count)}</span></div></td></tr>`;
};

// One malformed record must not blank the whole list: build what can be built, name what was dropped once.
const warned = new Set();
const guarded = (build, ev) => {
  try { return build(ev); } catch (err) {
    if (!warned.has(ev?.id)) {
      warned.add(ev?.id);
      console.warn(`getup: skipped event ${ev?.id ?? '?'}`, err?.message ?? err);
    }
    return '';
  }
};

export function tableHTML(events, today, venues, compact = false) {
  return tableShell(tableBody(events, today, venues, compact).body, compact);
}

// Column widths live in the stylesheet by class, so the shell and the rules cannot drift:
// the narrow shell carries no vibe column at all, rather than an empty one holding its width.
const tableShell = (body, compact) => `<div class="tbl"><table>
<colgroup><col class="c-when"><col>${compact ? '' : '<col class="c-vibe">'}<col class="c-price"><col class="c-acts"></colgroup>
<thead><tr><th scope="col">מתי</th><th scope="col">מה ואיפה</th>${compact ? '' : '<th scope="col">וייב</th>'}<th scope="col">מחיר</th><th scope="col">פעולות</th></tr></thead>
<tbody>${body}</tbody></table></div>`;

// painted is what actually reached the DOM: a dropped row must not be counted as shown.
const tableBody = (events, today, venues, compact = false) => {
  let painted = 0;
  const body = [...groupByDay(events ?? [])]
    .map(([day, list]) => {
      const rows = list.map(ev => guarded(e => rowHTML(e, venues, compact), ev)).filter(Boolean);
      painted += rows.length;
      return rows.length ? dayRowHTML(day, rows.length, today, compact) + rows.join('') : '';
    })
    .join('');
  return { body, painted };
};

const cardHTML = (ev, today, venues) => {
  const { text, kind } = priceLabel(ev);
  return `<article class="card">
<div class="c1"><span class="rel2">${esc(relDay(ev.day, today) ?? dayLabel(ev.day))}</span><span class="time2 num">${timeLabel(ev)}</span><span class="p2 ${kind}">${esc(text)}</span></div>
<h3 class="t2"><bdi>${esc(ev.title)}</bdi></h3>
${descLine(ev, 'p')}
<div class="v2"><span>${location(ev, venues)}</span><span class="leave">${leaveText(ev)}</span></div>
<div class="strip">${chipsHTML(ev, 3)}${infoButton(ev)}</div>
${ev.soldout ? '<div class="sold">אזלו הכרטיסים</div>' : ''}
${noteBlock(ev)}
<div class="cta"><span class="acts">${links(ev, venues)}</span></div></article>`;
};

const cardsBody = (events, today, venues) => {
  const cards = (events ?? [])
    .map(ev => guarded(e => cardHTML(e, today, venues), ev))
    .filter(Boolean);
  return { body: `<div class="cards">${cards.join('')}</div>`, painted: cards.length };
};

export function cardsHTML(events, today, venues) {
  return cardsBody(events, today, venues).body;
}

const brokenHTML = () => `<div class="empty"><h3>לא הצלחנו להציג את האירועים</h3>
<p>נתוני האירועים חלקיים כרגע. נסו לרענן את הדף.</p></div>`;

// Only the visible view is built, and the caller learns how many records actually painted.
export function listHTML(events, today, venues, view = 'desktop') {
  const list = events ?? [];
  if (!list.length) return { html: '', count: 0 };
  if (view === 'mobile') {
    const { body, painted } = cardsBody(list, today, venues);
    return painted ? { html: body, count: painted } : { html: brokenHTML(), count: 0 };
  }
  // 901–1200px keeps the map beside the list: four columns there, five when the vibe fits.
  const compact = view === 'narrow';
  const { body, painted } = tableBody(list, today, venues, compact);
  return painted ? { html: tableShell(body, compact), count: painted } : { html: brokenHTML(), count: 0 };
}

// The cap is a button, not a footnote, and it raises itself to the furthest hidden event: one
// press must always reveal something, never leave the same button on screen.
export function capFor(hidden) {
  const drives = (hidden ?? []).map(ev => ev.drive_min).filter(Number.isFinite);
  return drives.length ? Math.ceil(Math.max(...drives) / 5) * 5 : null;
}

export function hiddenHTML(hidden) {
  const list = hidden ?? [];
  if (!list.length) return '';
  const drives = list.map(ev => ev.drive_min).filter(Number.isFinite);
  if (!drives.length) return '';
  const lo = Math.min(...drives);
  const hi = Math.max(...drives);
  const cap = capFor(list);
  const span = lo === hi ? `ב־${lo} דק׳` : `בין ${lo} ל־${hi} דק׳`;
  return `<button type="button" class="f hiddenbtn" id="f-far" data-cap="${cap}">עוד ${countLabel(list.length)} ${span} · הצג עד ${cap} דק׳ נסיעה</button>`;
}

// When the cap is what emptied the page, saying "there is nothing" contradicts the button above it.
export function emptyHTML(manifest, today, { capHidden = 0, filters = 0 } = {}) {
  const upcoming = (manifest.dates ?? []).filter(d => d.date >= today);
  const total = upcoming.reduce((n, d) => n + (Number(d.count) || 0), 0);
  const rel = `<p class="rel">${total ? `יש ${countLabel(total)} בתקופה הקרובה` : 'אין אירועים בתקופה הקרובה'}</p>`;
  const clear = filters
    ? '<button type="button" class="f" data-reset>ניקוי הסינון</button>'
    : '';
  if (capHidden) {
    return `<div class="empty"><h3>מגבלת הנסיעה הסתירה את כל האירועים</h3>
<p>יש ${countLabel(capHidden)} בטווח מעבר למגבלת הנסיעה. הכפתור שמעל לרשימה מרחיב אותה.</p>
${rel}${clear}</div>`;
  }
  if (filters) {
    return `<div class="empty"><h3>הסינון שבחרת הסתיר את כל האירועים</h3>
<p>יש אירועים בטווח. נקו את הסינון כדי לראות אותם.</p>
${rel}${clear}
<button type="button" class="f" id="f-widen">הצג את החודש הקרוב</button></div>`;
  }
  return `<div class="empty"><h3>אין אירועים בטווח שבחרת</h3>
<p>נסו טווח רחב יותר או נקו חלק מהסינונים.</p>
${rel}
<button type="button" class="f" id="f-widen">הצג את החודש הקרוב</button></div>`;
}

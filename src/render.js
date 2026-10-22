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

const timeLabel = ev => {
  // An event with no start has no honest "when": refuse the row rather than print 02:00.
  if (!Number.isFinite(ev.start)) throw new TypeError('missing start');
  return Number.isFinite(ev.end) && ev.end > ev.start
    ? timeRange(ev.start, ev.end)
    : startTime(ev.start);
};

const driveLabel = ev => (Number.isFinite(ev.drive_min) ? `${ev.drive_min} דק׳ נסיעה` : '');

const venueName = (ev, venues) => (venues ?? {})[ev.venue_id]?.name ?? '';

// "היכל התרבות, ראשון לציון | ראשון לציון" says the city twice for no new fact.
export const cityIn = (venue, city) => {
  const c = String(city ?? '').trim();
  return !c || String(venue ?? '').trim().endsWith(c);
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

const links = ev => {
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
  return ticket + comm + source;
};

const acts = ev => `<span class="acts">${links(ev)}${infoButton(ev)}</span>`;

const rowHTML = (ev, venues) => `<tr class="row">
<td><span class="when"><span class="h num">${timeLabel(ev)}</span><span class="r">${leaveText(ev)}</span></span></td>
<td><span class="what"><span class="t"><bdi>${esc(ev.title)}</bdi></span>${descLine(ev)}<span class="v">${location(ev, venues)}</span></span></td>
<td><span class="vibe">${chipsHTML(ev)}</span></td>
<td>${priceCell(ev)}</td>
<td>${acts(ev)}${noteBlock(ev)}</td>
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

const dayRowHTML = (day, count, today) => {
  const rel = relDay(day, today);
  return `<tr class="dayrow"><td colspan="5"><div class="dayhead">`
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

export function tableHTML(events, today, venues) {
  return tableShell(tableBody(events, today, venues).body);
}

// Column widths live in the stylesheet: one place that can also drop a column on a narrow screen.
const tableShell = body => `<div class="tbl"><table>
<colgroup><col><col><col><col><col></colgroup>
<thead><tr><th scope="col">מתי</th><th scope="col">מה ואיפה</th><th scope="col">וייב</th><th scope="col">מחיר</th><th scope="col">פעולות</th></tr></thead>
<tbody>${body}</tbody></table></div>`;

// painted is what actually reached the DOM: a dropped row must not be counted as shown.
const tableBody = (events, today, venues) => {
  let painted = 0;
  const body = [...groupByDay(events ?? [])]
    .map(([day, list]) => {
      const rows = list.map(ev => guarded(e => rowHTML(e, venues), ev)).filter(Boolean);
      painted += rows.length;
      return rows.length ? dayRowHTML(day, rows.length, today) + rows.join('') : '';
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
<div class="cta"><span class="acts">${links(ev)}</span></div></article>`;
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
  const { body, painted } = tableBody(list, today, venues);
  return painted ? { html: tableShell(body), count: painted } : { html: brokenHTML(), count: 0 };
}

// The drive cap is the default that hides most events; it is a button, not a footnote.
export function hiddenHTML(hidden) {
  const list = hidden ?? [];
  if (!list.length) return '';
  const drives = list.map(ev => ev.drive_min).filter(Number.isFinite);
  if (!drives.length) return '';
  const lo = Math.min(...drives);
  const hi = Math.max(...drives);
  const span = lo === hi ? `ב־${lo} דק׳` : `בין ${lo} ל־${hi} דק׳`;
  return `<button type="button" class="f hiddenbtn" id="f-far">עוד ${countLabel(list.length)} ${span} · הצג עד 60 דק׳ נסיעה</button>`;
}

export function emptyHTML(manifest, today) {
  const upcoming = (manifest.dates ?? []).filter(d => d.date >= today);
  const total = upcoming.reduce((n, d) => n + (Number(d.count) || 0), 0);
  return `<div class="empty"><h3>אין אירועים בטווח שבחרת</h3>
<p>נסו טווח רחב יותר או נקו חלק מהסינונים.</p>
<p class="rel">${total ? `יש ${countLabel(total)} בתקופה הקרובה` : 'אין אירועים בתקופה הקרובה'}</p>
<button type="button" class="f" id="f-widen">הצג את החודש הקרוב</button></div>`;
}

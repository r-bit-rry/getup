import { relDay, dayLabel, timeRange, startTime, leaveBy, priceLabel } from './format.js';
import { chipsHTML } from './chips.js';

// Control and bidi-override characters would let a title reverse its neighbours in the RTL line.
const UNSAFE = /[\u0000-\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069]/g;
const esc = s => String(s ?? '').replace(UNSAFE, '').replace(/[&<>"']/g, c => `&#${c.charCodeAt(0)};`);

// Only http(s) and same-site paths may reach an href; a scraped scheme, `//host` or `/\host` is not trusted.
const SAFE_URL = /^(?:https?:\/\/|\/(?![/\\])|#)/i;
const safeUrl = u => (typeof u === 'string' && SAFE_URL.test(u) ? u : '#');

const countLabel = n => (n === 1 ? 'אירוע אחד' : `${n} אירועים`);

const timeLabel = ev => {
  // An event with no start has no honest "when": refuse the row rather than print 02:00.
  if (!Number.isFinite(ev.start)) throw new TypeError('missing start');
  return Number.isFinite(ev.end) && ev.end > ev.start
    ? timeRange(ev.start, ev.end)
    : startTime(ev.start);
};

const driveLabel = ev => (Number.isFinite(ev.drive_min) ? `${ev.drive_min} דק׳ נסיעה` : '');

const leaveLine = ev => (Number.isFinite(ev.drive_min)
  ? `צא ${leaveBy(ev.start, ev.drive_min)}`
  : 'זמן נסיעה לא ידוע');

const venueName = (ev, venues) => (venues ?? {})[ev.venue_id]?.name ?? '';

const location = (ev, venues) => [venueName(ev, venues), ev.city, driveLabel(ev)]
  .filter(Boolean).map(part => `<bdi>${esc(part)}</bdi>`).join('<i aria-hidden="true">|</i>');

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
<td><span class="when"><span class="h num">${timeLabel(ev)}</span><span class="r">${leaveLine(ev)}</span></span></td>
<td><span class="what"><span class="t"><bdi>${esc(ev.title)}</bdi></span><span class="v">${location(ev, venues)}</span></span></td>
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

const tableShell = body => `<div class="tbl"><table>
<colgroup><col style="width:122px"><col style="width:auto"><col style="width:30%"><col style="width:104px"><col style="width:132px"></colgroup>
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
<div class="v2"><span>${location(ev, venues)}</span><span class="leave">${leaveLine(ev)}</span></div>
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

export function emptyHTML(manifest, today) {
  const upcoming = (manifest.dates ?? []).filter(d => d.date >= today);
  const total = upcoming.reduce((n, d) => n + (Number(d.count) || 0), 0);
  return `<div class="empty"><h3>אין אירועים בטווח שבחרת</h3>
<p>נסה טווח רחב יותר או נקה חלק מהסינונים.</p>
<p class="rel">במאגר יש ${countLabel(total)} בטווח הקרוב</p></div>`;
}

import { relDay, dayLabel, timeRange, startTime, leaveBy, priceLabel } from './format.js';
import { chipsHTML } from './chips.js';

const esc = s => String(s ?? '').replace(/[&<>"']/g, c => `&#${c.charCodeAt(0)};`);

// Only http(s) and in-site links may reach an href; a scraped scheme is not trusted.
const safeUrl = u => {
  if (typeof u !== 'string') return '#';
  try {
    const { protocol } = new URL(u);
    if (protocol === 'http:' || protocol === 'https:') return u;
  } catch { /* relative or fragment, checked below */ }
  return u.startsWith('/') || u.startsWith('#') ? u : '#';
};

const countLabel = n => (n === 1 ? 'אירוע אחד' : `${n} אירועים`);

const timeLabel = ev => (Number.isFinite(ev.end) && ev.end > ev.start
  ? timeRange(ev.start, ev.end)
  : startTime(ev.start));

const driveLabel = ev => (Number.isFinite(ev.drive_min) ? `${ev.drive_min} דק׳ נסיעה` : '');

const leaveLine = ev => (Number.isFinite(ev.drive_min)
  ? `צא ${leaveBy(ev.start, ev.drive_min)}`
  : 'זמן נסיעה לא ידוע');

const venueName = (ev, venues) => (venues ?? {})[ev.venue_id]?.name ?? '';

const location = (ev, venues) => [venueName(ev, venues), ev.city, driveLabel(ev)]
  .filter(Boolean).map(part => `<bdi>${esc(part)}</bdi>`).join('<i>|</i>');

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
      ? `<a class="act" href="${esc(safeUrl(ev.urls.tickets))}" target="_blank" rel="noopener">כרטיס</a>`
      : '';
  const comm = ev.urls?.community
    ? `<a class="act comm" href="${esc(safeUrl(ev.urls.community))}" target="_blank" rel="noopener">קבוצה</a>`
    : '';
  return ticket + comm;
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

export function tableHTML(events, today, venues) {
  const body = [...groupByDay(events ?? [])]
    .map(([day, list]) => dayRowHTML(day, list.length, today) + list.map(ev => rowHTML(ev, venues)).join(''))
    .join('');
  return `<div class="tbl"><table>
<colgroup><col style="width:122px"><col style="width:auto"><col style="width:30%"><col style="width:104px"><col style="width:132px"></colgroup>
<thead><tr><th scope="col">מתי</th><th scope="col">מה ואיפה</th><th scope="col">וייב</th><th scope="col">מחיר</th><th scope="col">פעולות</th></tr></thead>
<tbody>${body}</tbody></table></div>`;
}

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

export function cardsHTML(events, today, venues) {
  return `<div class="cards">${(events ?? []).map(ev => cardHTML(ev, today, venues)).join('')}</div>`;
}

export function emptyHTML(manifest, today) {
  const upcoming = (manifest.dates ?? []).filter(d => d.date >= today);
  const total = upcoming.reduce((n, d) => n + (d.count ?? 0), 0);
  return `<div class="empty"><h3>אין אירועים בטווח שבחרת</h3>
<p>נסה טווח רחב יותר או נקה חלק מהסינונים.</p>
<p class="rel">במאגר יש ${countLabel(total)} בטווח הקרוב</p></div>`;
}

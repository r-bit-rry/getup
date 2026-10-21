import { relDay, dayLabel, timeRange, leaveBy, priceLabel } from './format.js';
import { chipsHTML } from './chips.js';

const esc = s => String(s ?? '').replace(/[&<>"']/g, c => `&#${c.charCodeAt(0)};`);

const countLabel = n => (n === 1 ? 'אירוע אחד' : `${n} אירועים`);

const driveLine = ev => (Number.isFinite(ev.drive_min)
  ? `${ev.drive_min} דק׳ נסיעה · צא ${leaveBy(ev.start, ev.drive_min)}`
  : 'זמן נסיעה לא ידוע');

const noteText = ev => (ev.notes ?? []).filter(Boolean).join(' · ');

const priceCell = ev => {
  const { text, kind } = priceLabel(ev);
  const until = ev.free_until ? `<span class="s">חינם עד ${esc(ev.free_until)}</span>` : '';
  const sold = ev.soldout ? '<span class="sold">אזלו הכרטיסים</span>' : '';
  return `<span class="price ${kind}">${esc(text)}</span>${until}${sold}`;
};

const acts = ev => {
  const note = noteText(ev);
  const ticket = ev.soldout
    ? '<span class="act gone">אזל</span>'
    : ev.urls?.tickets
      ? `<a class="act" href="${esc(ev.urls.tickets)}" target="_blank" rel="noopener">כרטיס</a>`
      : '';
  const comm = ev.urls?.community
    ? `<a class="act comm" href="${esc(ev.urls.community)}" target="_blank" rel="noopener">קבוצה</a>`
    : '';
  const info = note ? `<span class="ico" title="${esc(note)}">i</span>` : '';
  return `<span class="acts">${ticket}${comm}${info}</span>`;
};

const where = ev => [ev.city, ev.source?.name].filter(Boolean).map(esc).join('<i>|</i>');

const rowHTML = ev => `<tr class="row">
<td><span class="when"><span class="h num">${timeRange(ev.start, ev.end ?? ev.start)}</span><span class="r">${driveLine(ev)}</span></span></td>
<td><span class="what"><span class="t"><bdi>${esc(ev.title)}</bdi></span><span class="v">${where(ev)}</span></span></td>
<td><span class="vibe">${chipsHTML(ev)}</span></td>
<td>${priceCell(ev)}</td>
<td>${acts(ev)}</td>
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

export function tableHTML(events, today) {
  const body = [...groupByDay(events ?? [])]
    .map(([day, list]) => dayRowHTML(day, list.length, today) + list.map(rowHTML).join(''))
    .join('');
  return `<div class="tbl"><table>
<colgroup><col style="width:122px"><col style="width:auto"><col style="width:30%"><col style="width:104px"><col style="width:132px"></colgroup>
<thead><tr><th scope="col">מתי</th><th scope="col">מה ואיפה</th><th scope="col">וייב</th><th scope="col">מחיר</th><th scope="col">פעולות</th></tr></thead>
<tbody>${body}</tbody></table></div>`;
}

const cardHTML = (ev, today) => {
  const { text, kind } = priceLabel(ev);
  return `<article class="card">
<div class="c1"><span class="rel2">${esc(relDay(ev.day, today) ?? dayLabel(ev.day))}</span><span class="time2 num">${timeRange(ev.start, ev.end ?? ev.start)}</span><span class="p2 ${kind}">${esc(text)}</span></div>
<h3 class="t2"><bdi>${esc(ev.title)}</bdi></h3>
<div class="v2"><span>${where(ev)}</span><span class="leave">${driveLine(ev)}</span></div>
<div class="strip">${chipsHTML(ev, 3)}</div>
${ev.soldout ? '<div class="sold">אזלו הכרטיסים</div>' : ''}
<div class="cta">${acts(ev)}</div></article>`;
};

export function cardsHTML(events, today) {
  return `<div class="cards">${(events ?? []).map(ev => cardHTML(ev, today)).join('')}</div>`;
}

export function emptyHTML(manifest, today) {
  const upcoming = (manifest.dates ?? []).filter(d => d.date >= today);
  const total = upcoming.reduce((n, d) => n + (d.count ?? 0), 0);
  return `<div class="empty"><h3>אין אירועים בטווח שבחרת</h3>
<p>נסה טווח רחב יותר או נקה חלק מהסינונים.</p>
<p class="rel">במאגר יש ${countLabel(total)} בטווח הקרוב</p></div>`;
}

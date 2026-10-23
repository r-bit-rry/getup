const TZ = 'Asia/Jerusalem';
const DAY_MS = 86400000;

const clock = new Intl.DateTimeFormat('he-IL', { timeZone: TZ, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
const dayName = new Intl.DateTimeFormat('he-IL', { timeZone: TZ, weekday: 'long', day: 'numeric', month: 'long' });

const dayNum = (isoDate) => {
  const [y, m, d] = isoDate.split('-').map(Number);
  return Date.UTC(y, m - 1, d) / DAY_MS;
};

export function relDay(isoDate, today) {
  const diff = dayNum(isoDate) - dayNum(today);
  if (diff === 0) return 'היום';
  if (diff === 1) return 'מחר';
  if (diff === 2) return 'מחרתיים';
  if (diff > 2 && diff <= 14) return `בעוד ${diff} ימים`;
  return null;
}

export function dayLabel(isoDate) {
  const [y, m, d] = isoDate.split('-').map(Number);
  return dayName.format(new Date(Date.UTC(y, m - 1, d, 12)));
}

export function timeRange(startUnix, endUnix) {
  const end = Math.max(endUnix, startUnix);
  return `${clock.format(new Date(startUnix * 1000))}–${clock.format(new Date(end * 1000))}`;
}

export function startTime(startUnix) {
  return clock.format(new Date(startUnix * 1000));
}

// A source that published no end has published no end: six hours is only how long the row stays
// on the list, never a time we print. A guessed 03:00 must not be stated as a fact.
export const EXPIRY_HOURS = 6;
export const endOf = ev => (Number.isFinite(ev.end) && ev.end > ev.start
  ? ev.end
  : ev.start + EXPIRY_HOURS * 3600);

// Once the start has passed, "leave by" is meaningless. The when-cell carries the end time for a
// running show, so this line stays empty rather than printing the same clock twice.
export const leaveText = (ev, nowMs = Date.now()) => {
  if (ev.start * 1000 <= nowMs) {
    return Number.isFinite(ev.end) && ev.end > ev.start ? '' : 'מתקיים כעת';
  }
  return Number.isFinite(ev.drive_min) ? `צא ${leaveBy(ev.start, ev.drive_min)}` : 'זמן נסיעה לא ידוע';
};

export function leaveBy(startUnix, driveMin) {
  return clock.format(new Date(startUnix * 1000 - (driveMin + 30) * 60000));
}

export function priceLabel(ev) {
  if (ev.free) return { text: 'חינם', kind: 'free' };
  if (Number.isFinite(ev.price_from)) return { text: `₪${ev.price_from}`, kind: 'paid' };
  return { text: 'מחיר לא ידוע', kind: 'unknown' };
}

export function dataAge(generatedAt, now) {
  // a missing or unparseable timestamp has no age; never let NaN reach the footer
  const generated = generatedAt == null ? NaN : new Date(generatedAt).getTime();
  if (!Number.isFinite(generated)) return '';
  const hours = Math.floor((now - generated) / 3600000);
  if (hours < 1) return 'עודכן עכשיו';
  if (hours === 1) return 'עודכן לפני שעה';
  if (hours === 2) return 'עודכן לפני שעתיים';
  return `עודכן לפני ${hours} שעות`;
}

// One quiet sentence for the footer: what broke and what went unread, never a filter or an order.
export function opsLine(manifest) {
  const sources = manifest?.sources ?? {};
  const names = status => Object.entries(sources)
    .filter(([, s]) => s !== null && typeof s === 'object' && s.status === status)
    .map(([name]) => name)
    .sort()
    .join(', ');
  const failed = names('failed');
  const partial = names('partial');
  const parts = [];
  if (failed) parts.push(`מקור שנכשל: ${failed}`);
  if (partial) parts.push(`מקור חלקי: ${partial}`);
  const missed = (Array.isArray(manifest?.coverage?.missed) ? manifest.coverage.missed : [])
    .map(m => (typeof m === 'string' ? m : m?.name ?? m?.venue_id ?? m?.id))
    .filter(Boolean);
  const checked = manifest?.coverage?.checked ?? 0;
  const allOk = Object.keys(sources).length > 0
    && Object.values(sources).every(s => s !== null && typeof s === 'object' && s.status === 'ok');
  if (missed.length) {
    parts.push(`לא נבדקו ב־14 הימים האחרונים: ${missed.join(' · ')}`);
  } else if (!failed && !partial) {
    if (checked && allOk) parts.push(`כל ${checked} המקומות נבדקו`);
    else if (!checked) parts.push('אין מידע על כיסוי המקורות');
  }
  return parts.join(' · ');
}

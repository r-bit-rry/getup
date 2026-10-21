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

export function leaveBy(startUnix, driveMin) {
  return clock.format(new Date(startUnix * 1000 - (driveMin + 30) * 60000));
}

export function priceLabel(ev) {
  if (ev.free) return { text: 'חינם', kind: 'free' };
  if (Number.isFinite(ev.price_from)) return { text: `₪${ev.price_from}`, kind: 'paid' };
  return { text: 'מחיר לא ידוע', kind: 'unknown' };
}

export function dataAge(generatedAt, now) {
  const hours = Math.floor((now - new Date(generatedAt)) / 3600000);
  if (hours < 1) return 'עודכן עכשיו';
  if (hours === 1) return 'עודכן לפני שעה';
  if (hours === 2) return 'עודכן לפני שעתיים';
  return `עודכן לפני ${hours} שעות`;
}

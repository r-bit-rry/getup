import test from 'node:test';
import assert from 'node:assert/strict';
import { relDay, dayLabel, timeRange, leaveBy, priceLabel, dataAge } from '../src/format.js';

const T0 = Date.UTC(2026, 9, 18, 21, 0); // 2026-10-18 21:00Z

test('relDay names the near days and counts the rest', () => {
  assert.equal(relDay('2026-10-18', '2026-10-18'), 'היום');
  assert.equal(relDay('2026-10-19', '2026-10-18'), 'מחר');
  assert.equal(relDay('2026-10-20', '2026-10-18'), 'מחרתיים');
  assert.equal(relDay('2026-10-23', '2026-10-18'), 'בעוד 5 ימים');
  assert.equal(relDay('2026-11-30', '2026-10-18'), null);
});

test('leaveBy subtracts drive time and a 30 minute buffer', () => {
  // 21:30 Asia/Jerusalem on 2026-10-23 = 18:30Z; 29 min drive + 30 buffer => 20:31 local
  const start = Math.floor(new Date('2026-10-23T18:30:00Z').getTime() / 1000);
  assert.equal(leaveBy(start, 29), '20:31');
});

test('timeRange never renders a negative span', () => {
  assert.equal(timeRange(T0 / 1000, T0 / 1000 + 7200), '00:00–02:00');
  assert.equal(timeRange(T0 / 1000, T0 / 1000), '00:00–00:00');
});

test('priceLabel distinguishes free, paid and unknown', () => {
  assert.deepEqual(priceLabel({ free: true, price_from: 0 }), { text: 'חינם', kind: 'free' });
  assert.deepEqual(priceLabel({ price_from: 174 }), { text: '₪174', kind: 'paid' });
  assert.deepEqual(priceLabel({}), { text: 'מחיר לא ידוע', kind: 'unknown' });
  assert.deepEqual(priceLabel({ price_from: null }), { text: 'מחיר לא ידוע', kind: 'unknown' });
});

test('dayLabel is Hebrew and date-stable', () => {
  assert.equal(dayLabel('2026-10-23'), 'יום שישי, 23 באוקטובר');
});

test('dataAge speaks Hebrew and never goes negative', () => {
  const now = new Date('2026-10-18T18:00:00Z');
  assert.equal(dataAge('2026-10-18T15:00:00Z', now), 'עודכן לפני 3 שעות');
  assert.equal(dataAge('2026-10-18T19:00:00Z', now), 'עודכן עכשיו');
  assert.equal(dataAge('2026-10-18T17:00:00Z', now), 'עודכן לפני שעה');
  assert.equal(dataAge('2026-10-18T16:00:00Z', now), 'עודכן לפני שעתיים');
});

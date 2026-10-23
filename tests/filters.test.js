// tests/filters.test.js
import test from 'node:test';
import assert from 'node:assert/strict';
import { defaultState, applyFilters, sortEvents, serializeState, deserializeState, clampStaleRange, dropStarted, excludedByDrive } from '../src/filters.js';
import { relDay } from '../src/format.js';

const TODAY = '2026-10-18';
const ev = (o = {}) => ({ id: 'x', title: 't', venue_id: 'v', city: 'c', day: '2026-10-20',
  start: 0, end: 0, drive_min: 20, price_from: 100, free: false, soldout: false,
  notable: false, scene: [], crowd: [], urls: {}, ...o });

test('defaults match the spec', () => {
  const s = defaultState();
  assert.equal(s.dateWindow, 'week');
  assert.equal(s.maxDriveMin, 45);
  assert.equal(s.centre.label, 'נתניה');
});

test('the week window keeps days 0..7 and drops the rest', () => {
  const soon = ev({ id: 'soon', day: '2026-10-20' });
  const late = ev({ id: 'late', day: '2026-11-15' });
  const r = applyFilters([soon, late], defaultState(), TODAY);
  assert.deepEqual(r.map(e => e.id), ['soon']);
});

test('unknown age never hides an event; a stated exclusion does', () => {
  const unknown = ev({ crowd: [] });
  const minorOnly = ev({ crowd: ['18+'] });
  const s = { ...defaultState(), age: 16 };
  assert.deepEqual(applyFilters([unknown], s, TODAY).map(e => e.id), ['x']);
  assert.deepEqual(applyFilters([minorOnly], s, TODAY), []);
});

test('unknown price survives a max-price filter', () => {
  assert.equal(applyFilters([ev({ price_from: null })], { ...defaultState(), maxPrice: 100 }, TODAY).length, 1);
});

test('free-only requires the fact; an unknown price does not pass it', () => {
  const r = applyFilters([
    ev({ id: 'free', free: true, price_from: 0 }),
    ev({ id: 'priced', price_from: 50 }),
    ev({ id: 'unknown', price_from: null, free: false }),
  ], { ...defaultState(), freeOnly: true }, TODAY);
  assert.deepEqual(r.map(e => e.id), ['free']);
});

test('gated-community events follow the include toggle', () => {
  const gated = ev({ id: 'g', urls: { community: 'https://facebook.com/groups/x' } });
  assert.equal(applyFilters([gated], { ...defaultState(), includeGated: false }, TODAY).length, 0);
  assert.equal(applyFilters([gated], { ...defaultState(), includeGated: true }, TODAY).length, 1);
});

test('scene and crowd filters match any selected tag', () => {
  const rock = ev({ id: 'rock', scene: ['רוק'], crowd: ['30+'] });
  const jazz = ev({ id: 'jazz', scene: ['ג׳אז'], crowd: [] });
  assert.deepEqual(applyFilters([rock, jazz], { ...defaultState(), scenes: ['רוק'] }, TODAY).map(e => e.id), ['rock']);
  assert.deepEqual(applyFilters([rock, jazz], { ...defaultState(), crowds: ['30+'] }, TODAY).map(e => e.id), ['rock']);
});

test('drive filter excludes only known-too-far events', () => {
  const r = applyFilters([ev({ drive_min: 90 })], { ...defaultState(), maxDriveMin: 30 }, TODAY);
  assert.deepEqual(r, []);
  const missing = applyFilters([ev({ drive_min: null })], { ...defaultState(), maxDriveMin: 30 }, TODAY);
  assert.equal(missing.length, 1, 'missing drive data is not "too far" — it must pass');
});

test('sort puts notable first within a day, then nearest', () => {
  const a = ev({ id: 'a', day: '2026-10-20', drive_min: 10 });
  const b = ev({ id: 'b', day: '2026-10-20', drive_min: 40, notable: true });
  const c = ev({ id: 'c', day: '2026-10-20', drive_min: 5 });
  const d = ev({ id: 'd', day: '2026-10-19', drive_min: 90 });
  assert.deepEqual(sortEvents([a, b, c, d]).map(e => e.id), ['d', 'b', 'c', 'a']);
});

test('state round-trips and survives garbage', () => {
  const s = { ...defaultState(), maxPrice: 120, scenes: ['רוק'] };
  assert.deepEqual(deserializeState(serializeState(s)), s);
  assert.deepEqual(deserializeState('{not json'), defaultState());
  assert.equal(deserializeState('{"nonsense":1}').dateWindow, 'week');
});

// ── fix wave A: stable order and a stale stored range ────────────────────

test('equal day, notability and drive fall back to id so a re-run cannot reorder the page', () => {
  const rows = [
    ev({ id: 'c', day: '2026-10-20', drive_min: 10, notable: false }),
    ev({ id: 'a', day: '2026-10-20', drive_min: 10, notable: false }),
    ev({ id: 'b', day: '2026-10-20', drive_min: 10, notable: false }),
  ];
  assert.deepEqual(sortEvents(rows).map(e => e.id), ['a', 'b', 'c']);
  assert.deepEqual(sortEvents([...rows].reverse()).map(e => e.id), ['a', 'b', 'c']);
});

test('a stored range that ended before today resets to the week window', () => {
  const stale = { ...defaultState(), dateWindow: 'range', range: { from: '2026-10-01', to: '2026-10-10' } };
  const out = clampStaleRange(stale, '2026-10-18');
  assert.equal(out.dateWindow, 'week');
  assert.equal(out.range, null);
  // a live range and a range ending today are left alone
  const live = { ...defaultState(), dateWindow: 'range', range: { from: '2026-10-18', to: '2026-10-25' } };
  assert.deepEqual(clampStaleRange(live, '2026-10-18'), live);
  const endsToday = { ...defaultState(), dateWindow: 'range', range: { from: '2026-10-01', to: '2026-10-18' } };
  assert.deepEqual(clampStaleRange(endsToday, '2026-10-18'), endsToday);
  assert.deepEqual(clampStaleRange(defaultState(), '2026-10-18'), defaultState());
});

// ── fix wave C: a running show stays; the cut-off is the end ─────────────

const NOW_MS = Date.UTC(2026, 9, 22, 18, 0, 0);
const startedMinAgo = min => (NOW_MS - min * 60000) / 1000;
const endsInMin = min => (NOW_MS + min * 60000) / 1000;

test('a show running 30 minutes is still on offer', () => {
  const running = ev({ id: 'running', start: startedMinAgo(30), end: endsInMin(90) });
  assert.deepEqual(dropStarted([running], NOW_MS).map(e => e.id), ['running']);
});

test('an event is dropped once it has ended', () => {
  const gone = ev({ id: 'gone', start: startedMinAgo(120), end: startedMinAgo(1) });
  assert.deepEqual(dropStarted([gone], NOW_MS), []);
});

test('a night 22:00–04:00 survives to 03:59 and drops at 04:00', () => {
  const start = Date.UTC(2026, 9, 22, 22) / 1000;
  const end = Date.UTC(2026, 9, 23, 4) / 1000;
  const club = ev({ id: 'club', start, end });
  assert.deepEqual(dropStarted([club], (end - 60) * 1000).map(e => e.id), ['club']);
  assert.deepEqual(dropStarted([club], end * 1000), []);
});

test('a record with no end is dropped six hours after it began, not four', () => {
  const open = ev({ id: 'open', start: startedMinAgo(60) });
  assert.deepEqual(dropStarted([open], NOW_MS).map(e => e.id), ['open']);
  // the party that never published an end is still real at 04:30 of its own six hours
  const late = ev({ id: 'late', start: startedMinAgo(270) });
  assert.deepEqual(dropStarted([late], NOW_MS).map(e => e.id), ['late']);
  const stale = ev({ id: 'stale', start: startedMinAgo(361) });
  assert.deepEqual(dropStarted([stale], NOW_MS), []);
});

test('a future event is kept', () => {
  const future = ev({ id: 'future', start: startedMinAgo(-180) });
  assert.deepEqual(dropStarted([future], NOW_MS).map(e => e.id), ['future']);
});

test('a record with no finite start is dropped', () => {
  const none = ev({ id: 'none', start: undefined });
  const nan = ev({ id: 'nan', start: NaN });
  assert.deepEqual(dropStarted([none, nan], NOW_MS), []);
});

test('the drive diff counts only what the cap removed and spans its minutes', () => {
  const rows = [
    ev({ id: 'near', drive_min: 20 }),
    ev({ id: 'far50', drive_min: 50 }),
    ev({ id: 'far60', drive_min: 60 }),
    ev({ id: 'unknown', drive_min: null }),
  ];
  const hidden = excludedByDrive(rows, defaultState(), TODAY);
  assert.deepEqual(hidden.map(e => e.id), ['far50', 'far60']);
  assert.equal(hidden.length, 2);
  // no cap, nothing is hidden
  assert.deepEqual(excludedByDrive(rows, { ...defaultState(), maxDriveMin: null }, TODAY), []);
  // a row another filter already removed is not attributed to the drive cap
  const priced = {...defaultState(), maxPrice: 50};
  const pricedRows = [ev({ id: 'far-pricy', drive_min: 90, price_from: 200 })];
  assert.deepEqual(excludedByDrive(pricedRows, priced, TODAY), []);
});

// ── fix wave D: the window opens at windowStart, the labels stay on today ─

const YESTERDAY = '2026-10-17';

test('at 00:30 the window opens on yesterday, so last night is not lost', () => {
  const rows = [
    ev({ id: 'club', day: YESTERDAY }),
    ev({ id: 'older', day: '2026-10-16' }),
    ev({ id: 'today', day: TODAY }),
    ev({ id: 'edge', day: '2026-10-25' }),
    ev({ id: 'past-edge', day: '2026-10-26' }),
  ];
  // yesterday and two days back are added here only to prove which one survives
  assert.deepEqual(applyFilters(rows, defaultState(), TODAY, YESTERDAY).map(e => e.id),
    ['club', 'today', 'edge'], 'yesterday is in, two days back is out, both edges of the week hold');
});

test('with the default windowStart yesterday stays out', () => {
  assert.deepEqual(applyFilters([ev({ day: YESTERDAY })], defaultState(), TODAY), []);
});

test('the היום window keeps today and last night, not the day before', () => {
  const s = { ...defaultState(), dateWindow: 'today' };
  const rows = [ev({ id: 'club', day: YESTERDAY }), ev({ id: 'today', day: TODAY }),
    ev({ id: 'older', day: '2026-10-16' }), ev({ id: 'tomorrow', day: '2026-10-19' })];
  assert.deepEqual(applyFilters(rows, s, TODAY, YESTERDAY).map(e => e.id), ['club', 'today']);
  assert.deepEqual(applyFilters(rows, s, TODAY).map(e => e.id), ['today']);
});

test('a range opening today and the drive cap follow the same window', () => {
  const s = { ...defaultState(), dateWindow: 'range', range: { from: TODAY, to: '2026-10-25' } };
  const club = ev({ id: 'club', day: YESTERDAY });
  assert.deepEqual(applyFilters([club], s, TODAY, YESTERDAY).map(e => e.id), ['club']);
  assert.deepEqual(applyFilters([club], s, TODAY), []);
  const far = ev({ id: 'far', day: YESTERDAY, drive_min: 60 });
  assert.deepEqual(excludedByDrive([far], defaultState(), TODAY, YESTERDAY).map(e => e.id), ['far']);
  assert.deepEqual(excludedByDrive([far], defaultState(), TODAY), []);
});

test('relative labels stay keyed to today, not to windowStart', () => {
  assert.equal(relDay(TODAY, TODAY), 'היום');
  assert.equal(relDay(YESTERDAY, TODAY), null, 'yesterday is not היום');
});

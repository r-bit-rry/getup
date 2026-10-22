import { endOf } from './format.js';

const DAY_MS = 86400000;

const dayIndex = (iso) => {
  const [y, m, d] = iso.split('-').map(Number);
  return Date.UTC(y, m - 1, d) / DAY_MS;
};

const WINDOW_DAYS = { today: [0, 0], tomorrow: [1, 1], week: [0, 7] };

export function defaultState() {
  return {
    centre: { lat: 32.3286, lon: 34.8566, label: 'נתניה' },
    dateWindow: 'week',
    range: null,
    maxDriveMin: 45,
    maxPrice: null,
    freeOnly: false,
    age: null,
    hasTickets: false,
    includeGated: true,
    scenes: [],
    crowds: [],
  };
}

export function applyFilters(events, state, today) {
  const t = dayIndex(today);
  const [lo, hi] = WINDOW_DAYS[state.dateWindow] ?? [];
  return events.filter(ev => {
    if (state.dateWindow === 'range' && state.range) {
      if (ev.day < state.range.from || ev.day > state.range.to) return false;
    } else if (lo !== undefined) {
      const n = dayIndex(ev.day) - t;
      if (n < lo || n > hi) return false;
    }
    if (state.maxDriveMin != null && ev.drive_min != null && ev.drive_min > state.maxDriveMin) return false;
    if (state.maxPrice != null && ev.price_from != null && ev.price_from > state.maxPrice) return false;
    if (state.freeOnly && !(ev.free || ev.price_from == null || ev.price_from === 0)) return false;
    if (state.hasTickets && ev.soldout === true) return false;
    if (!state.includeGated && ev.urls?.community) return false;
    if (state.age != null && state.age < 18 && (ev.crowd ?? []).includes('18+')) return false;
    if (state.scenes.length && !(ev.scene ?? []).some(tag => state.scenes.includes(tag))) return false;
    if (state.crowds.length && !(ev.crowd ?? []).some(tag => state.crowds.includes(tag))) return false;
    return true;
  });
}

// A running show is still something to go to: drop a record only once it is over. `start`
// and `end` are Unix seconds; the caller passes milliseconds. A record with no start has
// no honest row at all.
export const dropStarted = (events, nowMs) => (events ?? []).filter(ev =>
  Number.isFinite(ev.start) && nowMs < endOf(ev) * 1000);

// What the drive cap alone removed, so the page can say so instead of hiding it.
export const excludedByDrive = (events, state, today) => (state.maxDriveMin == null
  ? []
  : applyFilters(events, { ...state, maxDriveMin: null }, today)
    .filter(ev => ev.drive_min != null && ev.drive_min > state.maxDriveMin));

export function sortEvents(events) {
  const drive = ev => ev.drive_min ?? Infinity;
  return [...events].sort((a, b) =>
    (a.day < b.day ? -1 : a.day > b.day ? 1 : 0)
    || (b.notable - a.notable)
    || (drive(a) - drive(b))
    // equal rows must keep a stable, re-run-safe order
    || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
}

// A range that ended before today would paint an empty page while the footer claims events exist.
export const clampStaleRange = (state, today) => (state.range?.to < today
  ? { ...state, dateWindow: 'week', range: null }
  : state);

export function serializeState(state) {
  return JSON.stringify(state);
}

const isNum = v => v === null || typeof v === 'number';
const isBool = v => typeof v === 'boolean';
const isArr = v => Array.isArray(v) && v.every(x => typeof x === 'string');
const VALID = {
  centre: v => v && typeof v.lat === 'number' && typeof v.lon === 'number' && typeof v.label === 'string',
  dateWindow: v => ['today', 'tomorrow', 'week', 'range'].includes(v),
  range: v => v === null || (v && typeof v.from === 'string' && typeof v.to === 'string'),
  maxDriveMin: isNum,
  maxPrice: isNum,
  freeOnly: isBool,
  age: isNum,
  hasTickets: isBool,
  includeGated: isBool,
  scenes: isArr,
  crowds: isArr,
};

export function deserializeState(json) {
  const base = defaultState();
  let parsed;
  try { parsed = JSON.parse(json); } catch { return base; }
  if (!parsed || typeof parsed !== 'object') return base;
  for (const key of Object.keys(base)) {
    if (VALID[key](parsed[key])) base[key] = parsed[key];
  }
  return base;
}

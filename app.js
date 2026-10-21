// Page shell: reads state, calls the pure modules, renders. No logic lives here.
import { loadManifest, loadDate, loadVenues } from './src/data.js';
import { loadPrefs, applyPrefs } from './src/prefs.js';
import { applyFilters, sortEvents, defaultState, serializeState, deserializeState } from './src/filters.js';
import { tableHTML, cardsHTML, emptyHTML } from './src/render.js';
import { dataAge } from './src/format.js';
import { VOCAB } from './src/chips.js';
import { recomputeDistances } from './src/distance.js';

const TZ = 'Asia/Jerusalem';
const KEY = { state: 'getup:state', view: 'getup:view', theme: 'getup:theme' };
const $ = (sel, root = document) => root.querySelector(sel);

const read = k => { try { return localStorage.getItem(k); } catch { return null; } };
const write = (k, v) => { try { localStorage.setItem(k, v); } catch { /* storage blocked: session-only state */ } };

const dateFmt = new Intl.DateTimeFormat('en-CA', { timeZone: TZ, year: 'numeric', month: '2-digit', day: '2-digit' });
const today = dateFmt.format(new Date()); // Asia/Jerusalem calendar date, computed once
const addDays = (iso, n) => {
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d + n)).toISOString().slice(0, 10);
};
const monthEnd = addDays(today, 30); // served horizon: 30 days

// A manifest that cannot be fetched must not leave a blank page: keep the shell and say so.
let manifest = { generated_at: null, dates: [], coverage: { checked: 0, missed: [] } };
let venues = {};
let prefs = { never: [], always: [] };
let ok = true;
try {
  manifest = await loadManifest('.');
  venues = await loadVenues('.');
  prefs = await loadPrefs('.');
} catch {
  ok = false;
}
const days = await Promise.all((manifest.dates ?? []).map(d => loadDate('.', d.date)));
const all = applyPrefs(days.flat(), prefs);

const DEFAULT_CENTRE = defaultState().centre;
const isDefaultCentre = c => c.lat === DEFAULT_CENTRE.lat && c.lon === DEFAULT_CENTRE.lon;
const drive = new Map(); // event id → minutes from a centre other than Netanya
let map = null;
let drawMap = () => {};

function fatal() {
  const p = document.createElement('p');
  p.className = 'empty';
  p.textContent = 'לא ניתן לטעון את נתוני האירועים כרגע. נסו לרענן את הדף.';
  $('#list').append(p);
  $('#status').textContent = p.textContent;
}

let state = deserializeState(read(KEY.state) ?? 'null');
if (state.dateWindow === 'range' && !state.range) state.dateWindow = 'week'; // a cleared range must not hide the window

const currentPreset = () => (state.dateWindow !== 'range'
  ? state.dateWindow
  : (state.range?.from === today && state.range?.to === monthEnd ? 'month' : null));

// ── render ───────────────────────────────────────────────────────────────
// Recomputed minutes override the cached ones; everything else still reads the record.
const withDrive = list => (drive.size
  ? list.map(ev => (drive.has(ev.id) ? { ...ev, drive_min: drive.get(ev.id) } : ev))
  : list);
const visible = () => sortEvents(applyFilters(withDrive(all), state, today));
// The drive limit must not hide an event whose real drive is short: recompute over
// everything the other filters allow, then let render() apply maxDriveMin.
const forDistances = () => sortEvents(applyFilters(withDrive(all), { ...state, maxDriveMin: null }, today));

const NOTE = 'זמני הנסיעה יחסית לנתניה';
const distEl = document.createElement('p');
distEl.id = 'dist-note';
distEl.className = 'distnote';
distEl.setAttribute('role', 'status');
distEl.hidden = true;
$('#list').before(distEl);
// The note follows the data, not a flag: it is up whenever a shown minute is still Netanya's.
const syncNote = show => {
  distEl.hidden = !show;
  distEl.textContent = show ? NOTE : '';
};

function render() {
  if (!ok) return;
  const events = visible();
  $('#list').innerHTML = events.length
    ? tableHTML(events, today, venues) + cardsHTML(events, today, venues)
    : emptyHTML(manifest, today);
  $('#status').textContent = `${events.length} אירועים בתצוגה`;
  syncNote(!isDefaultCentre(state.centre) && events.some(ev => !drive.has(ev.id)));
  syncControls();
  write(KEY.state, serializeState(state));
  drawMap(map, events.map(ev => ({ ...ev, venue: venues[ev.venue_id]?.name })));
}

// Cached drive_min already comes from Netanya: only a different centre needs the router.
let centreSeq = 0;
async function refreshDistances() {
  const seq = ++centreSeq;
  if (isDefaultCentre(state.centre)) {
    drive.clear();
    render();
    return;
  }
  // Only ids without minutes for this centre cost a request: a filter change that
  // adds events fetches just those, and one that removes them fetches nothing.
  const events = forDistances().filter(ev => !drive.has(ev.id));
  if (!events.length) {
    render();
    return;
  }
  render(); // the note is up while these minutes are still Netanya's
  const mins = await recomputeDistances(events, state.centre);
  if (seq !== centreSeq) return; // a newer centre/filter made this answer stale
  if (mins) events.forEach((ev, i) => { if (Number.isFinite(mins[i])) drive.set(ev.id, mins[i]); });
  // null keeps the cached Netanya minutes; render leaves the note up for them
  render();
}

// A filter change can add events the last recompute never saw.
const refilter = () => (isDefaultCentre(state.centre) ? render() : refreshDistances());

const recentre = centre => {
  state.centre = centre;
  drive.clear();
  render();
  return refreshDistances();
};

function syncControls() {
  const preset = currentPreset();
  for (const b of document.querySelectorAll('[data-window]')) {
    b.setAttribute('aria-pressed', String(b.dataset.window === preset));
  }
  $('#f-free').setAttribute('aria-pressed', String(state.freeOnly));
  $('#f-tickets').setAttribute('aria-pressed', String(state.hasTickets));
  $('#f-minor').setAttribute('aria-pressed', String(state.age != null));
  $('#f-gated').setAttribute('aria-pressed', String(state.includeGated));

  const price = $('#f-price');
  price.value = state.maxPrice == null ? price.max : String(state.maxPrice);
  $('#price-out').textContent = state.maxPrice == null ? 'ללא הגבלה' : `₪${state.maxPrice}`;
  $('#f-drive').value = state.maxDriveMin == null ? '' : String(state.maxDriveMin);

  const ranged = state.dateWindow === 'range' && state.range;
  $('#f-from').value = ranged ? state.range.from : '';
  $('#f-to').value = ranged ? state.range.to : '';
  $('#f-to').min = $('#f-from').value || today;

  const chosen = state.scenes.length + state.crowds.length;
  for (const b of document.querySelectorAll('#facets button[data-facet]')) {
    const picked = (b.dataset.facet === 'scene' ? state.scenes : state.crowds).includes(b.dataset.value);
    b.setAttribute('aria-pressed', String(picked));
  }
  $('#facet-count').textContent = chosen ? `(${chosen})` : '';
  $('#where-centre').textContent = state.centre.label;
  $('#where-drive').textContent = state.maxDriveMin == null
    ? 'ללא הגבלת נסיעה'
    : `עד ${state.maxDriveMin} דק׳ נסיעה`;
  for (const b of document.querySelectorAll('.card .ico')) {
    b.setAttribute('aria-expanded', String(document.body.dataset.full === '1'));
  }
}

// ── filters ──────────────────────────────────────────────────────────────
for (const b of document.querySelectorAll('[data-window]')) {
  b.addEventListener('click', () => {
    const w = b.dataset.window;
    if (w === 'month') {
      state.dateWindow = 'range';
      state.range = { from: today, to: monthEnd };
    } else {
      state.dateWindow = w;
      state.range = null;
    }
    refilter();
  });
}

for (const id of ['#f-from', '#f-to']) {
  $(id).min = today;
  $(id).max = monthEnd;
  $(id).addEventListener('change', () => {
    const from = $('#f-from').value;
    const to = $('#f-to').value;
    if (!from || !to) return; // a half-filled range keeps the last window
    state.dateWindow = 'range';
    state.range = from <= to ? { from, to } : { from: to, to: from };
    refilter();
  });
}

$('#f-free').addEventListener('click', () => { state.freeOnly = !state.freeOnly; refilter(); });
$('#f-tickets').addEventListener('click', () => { state.hasTickets = !state.hasTickets; refilter(); });
$('#f-gated').addEventListener('click', () => { state.includeGated = !state.includeGated; refilter(); });
// The age rule only ever removes: an explicit 18+ restriction is hidden for a minor-safe view.
$('#f-minor').addEventListener('click', () => { state.age = state.age == null ? 17 : null; refilter(); });

// The slider's top value means "no limit" — the real price range tops out at ₪250.
$('#f-price').addEventListener('input', e => {
  const max = Number(e.currentTarget.max);
  const v = Number(e.currentTarget.value);
  state.maxPrice = v >= max ? null : v;
  refilter();
});

$('#f-drive').addEventListener('change', e => {
  state.maxDriveMin = e.currentTarget.value === '' ? null : Number(e.currentTarget.value);
  refilter();
});

$('#f-clear').addEventListener('click', () => {
  state = defaultState();
  // The default-centre branch clears every recomputed minute and the note atomically.
  refreshDistances();
});

const facetButton = (kind, label) => {
  const b = document.createElement('button');
  b.type = 'button';
  b.className = 'f chip-f';
  b.dataset.facet = kind;
  b.dataset.value = label;
  b.textContent = label;
  return b;
};
for (const [kind, title] of [['scene', 'סצנה'], ['crowd', 'קהל']]) {
  const fs = document.createElement('fieldset');
  const legend = document.createElement('legend');
  legend.textContent = title;
  fs.append(legend, ...VOCAB[kind].map(label => facetButton(kind, label)));
  $('#facets').append(fs);
}
$('#facets').addEventListener('click', e => {
  const b = e.target.closest('button[data-facet]');
  if (!b) return;
  const key = b.dataset.facet === 'scene' ? 'scenes' : 'crowds';
  const v = b.dataset.value;
  state[key] = state[key].includes(v) ? state[key].filter(x => x !== v) : [...state[key], v];
  refilter();
});

// ── chrome toggles ───────────────────────────────────────────────────────
function applyView(view) {
  document.body.dataset.view = view;
  $('#v-desktop').setAttribute('aria-pressed', String(view === 'desktop'));
  $('#v-mobile').setAttribute('aria-pressed', String(view === 'mobile'));
}
function setView(view) {
  applyView(view);
  write(KEY.view, view);
  // the map container was display:none in mobile view; measure it again once layout settles
  requestAnimationFrame(() => map?.resize());
}
function setTheme(theme) {
  document.body.dataset.theme = theme;
  $('#t-day').setAttribute('aria-pressed', String(theme === 'day'));
  $('#t-night').setAttribute('aria-pressed', String(theme === 'night'));
  write(KEY.theme, theme);
}
$('#v-desktop').addEventListener('click', () => setView('desktop'));
$('#v-mobile').addEventListener('click', () => setView('mobile'));
$('#t-day').addEventListener('click', () => setTheme('day'));
$('#t-night').addEventListener('click', () => setTheme('night'));

// An info button opens its own note; a card's opens the notes for the whole card view.
$('#list').addEventListener('click', e => {
  const b = e.target.closest('.ico');
  if (!b) return;
  const open = b.getAttribute('aria-expanded') !== 'true';
  b.setAttribute('aria-expanded', String(open));
  b.closest('td, .card')?.querySelector('.note')?.classList.toggle('open', open);
  if (!b.closest('.card')) return;
  document.body.dataset.full = document.body.dataset.full === '1' ? '0' : '1';
  syncControls();
});

// A phone gets cards until the user says otherwise; an explicit choice is remembered.
const savedView = read(KEY.view);
applyView(savedView ?? (matchMedia('(max-width: 900px)').matches ? 'mobile' : 'desktop'));
setTheme(read(KEY.theme) === 'night' ? 'night' : 'day');

// The sticky map pane starts below the sticky header, whose height wraps.
const syncBar = () => document.documentElement.style.setProperty('--bar-h', `${$('.bar').offsetHeight}px`);
new ResizeObserver(syncBar).observe($('.bar'));
syncBar();

// Mount the map after the bar is measured; a MapLibre failure must leave the list intact.
try {
  const { initMap, drawMarkers } = await import('./src/map.js');
  map = initMap($('#map'));
  drawMap = (m, evs) => {
    try { drawMarkers(m, evs); } catch (err) { console.warn('getup: map draw failed', err?.message ?? err); }
  };
  map.resize();
} catch (err) {
  console.warn('getup: map unavailable', err?.message ?? err);
}

// ── footer ───────────────────────────────────────────────────────────────
$('#data-age').textContent = dataAge(manifest.generated_at, new Date()) || 'מועד העדכון לא ידוע';
const missed = (manifest.coverage?.missed ?? [])
  .map(m => (typeof m === 'string' ? m : m?.name ?? m?.venue_id ?? m?.id))
  .filter(Boolean);
const checked = manifest.coverage?.checked ?? 0;
$('#coverage').textContent = missed.length
  ? `לא נבדקו ב־14 הימים האחרונים: ${missed.join(' · ')}`
  : checked ? `כל ${checked} המקורות נבדקו` : 'אין מידע על כיסוי המקורות';

if (ok) {
  render();
  // A centre restored from localStorage was not computed by this page load.
  if (!isDefaultCentre(state.centre)) refreshDistances();
  // Geolocation overrides Netanya only when granted; denial leaves the correct cached minutes.
  navigator.geolocation?.getCurrentPosition(
    p => recentre({ lat: p.coords.latitude, lon: p.coords.longitude, label: 'המיקום שלי' }),
    () => {},
  );
} else fatal();

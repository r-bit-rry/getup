// Page shell: reads state, calls the pure modules, renders. No logic lives here.
import { loadManifest, loadDate, loadVenues, validDates } from './src/data.js';
import { loadPrefs, applyPrefs } from './src/prefs.js';
import { applyFilters, sortEvents, defaultState, serializeState, deserializeState, clampStaleRange, dropStarted, excludedByDrive } from './src/filters.js';
import { listHTML, emptyHTML, hiddenHTML, noDriveHTML } from './src/render.js';
import { dataAge } from './src/format.js';
import { VOCAB } from './src/chips.js';
import { recomputeDistances } from './src/distance.js';

const TZ = 'Asia/Jerusalem';
const KEY = { state: 'getup:state', theme: 'getup:theme', centre: 'getup:centre' };
const $ = (sel, root = document) => root.querySelector(sel);

const read = k => { try { return localStorage.getItem(k); } catch { return null; } };
const write = (k, v) => { try { localStorage.setItem(k, v); } catch { /* storage blocked: session-only state */ } };
// A geolocated centre lives in the tab, not in localStorage.
const session = {
  get: k => { try { return sessionStorage.getItem(k); } catch { return null; } },
  set: (k, v) => { try { sessionStorage.setItem(k, v); } catch { /* storage blocked */ } },
  del: k => { try { sessionStorage.removeItem(k); } catch { /* storage blocked */ } },
};

const GEO_LABEL = 'המיקום שלי';
const round3 = n => Math.round(n * 1000) / 1000;

const dateFmt = new Intl.DateTimeFormat('en-CA', { timeZone: TZ, year: 'numeric', month: '2-digit', day: '2-digit' });
const hourFmt = new Intl.DateTimeFormat('en-GB', { timeZone: TZ, hour: 'numeric', hourCycle: 'h23' });
let today = dateFmt.format(new Date()); // Asia/Jerusalem calendar date, refreshed when the tab comes back
const addDays = (iso, n) => {
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d + n)).toISOString().slice(0, 10);
};
// Before 06:00 last night is still running: an event bucketed to yesterday (§7.4.1) must be
// served and shown, or the portal is empty at the hour it is used.
const windowStartFor = iso => (Number(hourFmt.format(new Date())) < 6 ? addDays(iso, -1) : iso);
let windowStart = windowStartFor(today);
let monthEnd = addDays(today, 30); // served horizon: 30 days

// A manifest that cannot be fetched must not leave a blank page: keep the shell and say so.
let manifest = { generated_at: null, dates: [], coverage: { checked: 0, missed: [] } };
let venues = {};
let prefs = { never: [], always: [] };
let ok = true;
try {
  const loaded = await loadManifest('.');
  // A null/array/primitive manifest is a failed load, not a page with no events.
  if (!loaded || typeof loaded !== 'object' || Array.isArray(loaded)) throw new TypeError('manifest is not an object');
  manifest = loaded;
} catch {
  ok = false;
}
// venues.json is decoration: the renderer already falls back to the city alone.
try {
  venues = await loadVenues('.');
} catch {
  venues = {};
}
prefs = await loadPrefs('.');
// One bogus date must not blank the list; an all-bogus list is a failed load.
const dates = validDates(manifest);
if (ok && manifest.dates?.length && !dates.length) ok = false;
// Past dates are not shown and are not worth a request. One rejection here must reach fatal(),
// not reject the module and leave an empty shell.
let days = [];
try {
  days = ok
    ? await Promise.all(dates.filter(d => d.date >= windowStart).map(d => loadDate('.', d.date)))
    : [];
} catch (err) {
  console.warn('getup: bulk load failed', err?.message ?? err);
  ok = false;
}
const all = ok ? applyPrefs(days.flat(), prefs) : [];

const DEFAULT_CENTRE = defaultState().centre;
const DEFAULT = defaultState();
const isDefaultCentre = c => c.lat === DEFAULT_CENTRE.lat && c.lon === DEFAULT_CENTRE.lon;

// Filters that differ from the default hide rows while the סינון pill looks idle on a phone.
const activeFilters = () => [
  state.freeOnly, state.hasTickets, state.age != null, !state.includeGated,
  state.maxPrice != null, state.maxDriveMin !== DEFAULT.maxDriveMin,
  ...state.scenes, ...state.crowds,
].filter(Boolean).length;
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

let state = clampStaleRange(deserializeState(read(KEY.state) ?? 'null'), today);
if (state.dateWindow === 'range' && !state.range) state.dateWindow = 'week'; // a cleared range must not hide the window
// An older build may have persisted a precise position; it is not ours to keep.
if (state.centre.label === GEO_LABEL) state.centre = defaultState().centre;
// A position granted in this tab only; it must not survive the tab.
try {
  const geo = JSON.parse(session.get(KEY.centre) ?? 'null');
  if (geo && Number.isFinite(geo.lat) && Number.isFinite(geo.lon)) state.centre = geo;
} catch { /* a corrupt session entry is simply no position */ }

const currentPreset = () => (state.dateWindow !== 'range'
  ? state.dateWindow
  : (state.range?.from === today && state.range?.to === monthEnd ? 'month' : null));

// ── render ───────────────────────────────────────────────────────────────
// Recomputed minutes override the cached ones; everything else still reads the record.
const withDrive = list => (drive.size
  ? list.map(ev => (drive.has(ev.id) ? { ...ev, drive_min: drive.get(ev.id) } : ev))
  : list);
// A running show is still on offer; the cut-off is its end, not its start.
const live = now => dropStarted(withDrive(all), now);
const visible = now => sortEvents(applyFilters(live(now), state, today, windowStart));
// The drive limit must not hide an event whose real drive is short: recompute over
// everything the other filters allow, then let render() apply maxDriveMin.
const forDistances = () => sortEvents(applyFilters(live(Date.now()), { ...state, maxDriveMin: null }, today, windowStart));

const NOTE = 'זמני הנסיעה יחסית לנתניה';
const distEl = document.createElement('p');
distEl.id = 'dist-note';
distEl.className = 'distnote';
distEl.setAttribute('role', 'status');
distEl.hidden = true;
$('#list').before(distEl);

// Sending a position to a public router is a fact the user is told next to the note, not buried.
const geoEl = document.createElement('p');
geoEl.id = 'geo-note';
geoEl.className = 'distnote';
geoEl.hidden = true;
geoEl.textContent = 'המיקום נשלח לשירות ניתוב ציבורי (OSRM)';
distEl.after(geoEl);

// Half of Thursday sits behind the 45-minute cap: the count is a button above the list, not a footnote.
const farEl = document.createElement('div');
farEl.id = 'hidden-events';
geoEl.after(farEl);

// The note follows the data, not a flag: it is up whenever a shown minute is still Netanya's.
// role="status": writing textContent replaces the node and re-announces, so only change what differs.
const syncNote = show => {
  const hide = !show;
  if (distEl.hidden !== hide) distEl.hidden = hide;
  const text = show ? NOTE : '';
  if (distEl.textContent !== text) distEl.textContent = text;
  const geo = state.centre.label === GEO_LABEL;
  if (geoEl.hidden !== !geo) geoEl.hidden = !geo;
};

// Writing the same state on every paint is a synchronous localStorage write per filter click.
let lastPersisted = null;
const persist = () => {
  const s = serializeState(state.centre.label === GEO_LABEL
    ? { ...state, centre: defaultState().centre }
    : state);
  if (s === lastPersisted) return;
  lastPersisted = s;
  write(KEY.state, s);
};

function render() {
  if (!ok) return;
  const now = Date.now();
  const events = visible(now);
  const hidden = excludedByDrive(live(now), state, today, windowStart);
  const { html, count } = listHTML(events, today, venues, viewName());
  farEl.innerHTML = hiddenHTML(hidden) + noDriveHTML(events, state.maxDriveMin);
  // the empty state must name what emptied it: the cap first, then the filters
  $('#list').innerHTML = events.length
    ? html
    : emptyHTML(manifest, windowStart, { capHidden: hidden.length, filters: activeFilters() });
  $('#status').textContent = `${count} אירועים בתצוגה`;
  syncNote(!isDefaultCentre(state.centre) && events.some(ev => !drive.has(ev.id)));
  syncControls();
  persist();
  drawMap(map, events.map(ev => ({ ...ev, venue: venues[ev.venue_id]?.name })));
}

// Cached drive_min already comes from Netanya: only a different centre needs the router.
let centreSeq = 0;
let inFlight = false; // one batch at a time; the slider can fire once per release
let rerun = false; // a centre/filter change landed mid-flight: cover it once the request settles

// /table takes 100 coordinates including the origin: a long list is sliced and merged.
const CHUNK = 99;
async function distancesFor(events, centre) {
  const out = [];
  for (let i = 0; i < events.length; i += CHUNK) {
    const mins = await recomputeDistances(events.slice(i, i + CHUNK), centre);
    if (!mins) return null; // one failed slice keeps every cached minute, and the note, standing
    out.push(...mins);
  }
  return out;
}

async function refreshDistances() {
  const seq = ++centreSeq;
  if (isDefaultCentre(state.centre)) {
    drive.clear();
    render();
    return;
  }
  if (inFlight) {
    // Paint now with the cached minutes; the new centre's request covers this change when it lands.
    rerun = true;
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
  inFlight = true;
  let mins = null;
  try {
    mins = await distancesFor(events, state.centre);
  } finally {
    inFlight = false;
  }
  if (seq === centreSeq) { // a newer centre/filter made this answer stale
    if (mins) events.forEach((ev, i) => { if (Number.isFinite(mins[i])) drive.set(ev.id, mins[i]); });
    // null keeps the cached Netanya minutes; render leaves the note up for them
    render();
  }
  if (rerun) { rerun = false; await refreshDistances(); }
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
  // The cap button can raise the limit past the fixed list: give the select an option for it
  // rather than let it fall back to "no limit" and contradict the label.
  const driveSel = $('#f-drive');
  driveSel.querySelector('option[data-cap-opt]')?.remove();
  const wantDrive = state.maxDriveMin == null ? '' : String(state.maxDriveMin);
  if (wantDrive && ![...driveSel.options].some(o => o.value === wantDrive)) {
    const opt = document.createElement('option');
    opt.value = wantDrive;
    opt.textContent = `עד ${wantDrive} דק׳`;
    opt.dataset.capOpt = '1';
    driveSel.append(opt);
  }
  driveSel.value = wantDrive;

  const active = activeFilters();
  $('#filter-count').textContent = active ? `· ${active}` : '';

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
// change, not input: every paint rebuilds the list, so one drag must not repaint 22 times.
$('#f-price').addEventListener('change', e => {
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
  session.del(KEY.centre); // a reset also forgets the position granted in this tab
  // The default-centre branch clears every recomputed minute and the note atomically.
  refreshDistances();
});

// The empty state offers one way out: widen to the whole served month, then paint it.
// Widening alone is not enough when another filter caused the emptiness: reset those too.
$('#list').addEventListener('click', e => {
  if (e.target.closest('[data-reset]')) {
    // defaults for the filters, the window the user chose stays
    state = { ...defaultState(), centre: state.centre, dateWindow: state.dateWindow, range: state.range };
    refilter();
    return;
  }
  if (!e.target.closest('#f-widen')) return;
  state = { ...defaultState(), dateWindow: 'range', range: { from: today, to: monthEnd } };
  session.del(KEY.centre);
  refilter();
});

// One press must reveal what the button counted: raise the cap to the furthest hidden event.
const raiseCap = el => {
  const cap = Number(el?.dataset.cap);
  state.maxDriveMin = Number.isFinite(cap) && cap > 0 ? cap : state.maxDriveMin;
  refilter();
};

// The hidden-by-cap count raises the cap itself instead of asking the user to find the slider.
$('#hidden-events').addEventListener('click', e => {
  const b = e.target.closest('#f-far');
  if (b) raiseCap(b);
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
// The view follows the screen: cards up to 900px, four columns with the map to 1200px, five
// above it. Both breakpoints are the ones the stylesheet declares.
const mobileMQ = matchMedia('(max-width: 900px)');
const compactMQ = matchMedia('(max-width: 1200px)');
const viewName = () => (mobileMQ.matches ? 'mobile' : compactMQ.matches ? 'narrow' : 'desktop');
function applyView() {
  const mobile = mobileMQ.matches;
  document.body.dataset.view = mobile ? 'mobile' : 'desktop';
  $('#f-more').open = !mobile; // desktop needs the filters laid out in the row
}
function setTheme(theme) {
  document.body.dataset.theme = theme;
  $('#t-day').setAttribute('aria-pressed', String(theme === 'day'));
  $('#t-night').setAttribute('aria-pressed', String(theme === 'night'));
  write(KEY.theme, theme);
}
const onViewChange = () => {
  applyView();
  render(); // only the visible view is built, so the switch must rebuild the list
  // the map container was display:none in mobile view; measure it again once layout settles
  requestAnimationFrame(() => map?.resize());
};
mobileMQ.addEventListener('change', onViewChange);
compactMQ.addEventListener('change', onViewChange);
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

// A phone gets cards; the breakpoint is the 900px media query the stylesheet uses.
applyView();
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

// A position is only ever requested by this button: load must not ask for GPS.
$('#where-geo').addEventListener('click', () => {
  navigator.geolocation?.getCurrentPosition(
    p => {
      const centre = {
        lat: round3(p.coords.latitude),
        lon: round3(p.coords.longitude),
        label: GEO_LABEL,
      };
      session.set(KEY.centre, JSON.stringify(centre));
      recentre(centre);
    },
    () => {}, // denial leaves the cached Netanya minutes in place
  );
});

// A tab resumed the next morning must not keep yesterday under היום.
const refreshToday = () => {
  const now = dateFmt.format(new Date());
  const start = windowStartFor(now); // 06:00 crosses out of last night without a new date
  if (now === today && start === windowStart) return;
  today = now;
  windowStart = start;
  monthEnd = addDays(today, 30);
  render();
};
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') refreshToday();
});
addEventListener('pageshow', refreshToday);

if (ok) {
  render();
  // A centre restored from this tab was not computed by this page load.
  if (!isDefaultCentre(state.centre)) refreshDistances();
} else fatal();

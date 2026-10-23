// Reads the committed JSON in the browser (fetch) and in Node tests (fs).
export const readJSON = async (path) => {
  if (typeof window !== 'undefined') return (await fetch(path)).json();
  const { readFile } = await import('node:fs/promises');
  return JSON.parse(await readFile(path, 'utf8'));
};

export const join = (base, path) => `${base.replace(/\/+$/, '')}/${path}`;

export const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

// A manifest may name anything; only a real ISO day can be fetched and grouped.
export const validDates = manifest => (Array.isArray(manifest?.dates) ? manifest.dates : [])
  .filter(d => d && typeof d.date === 'string' && DATE_RE.test(d.date));

const clock = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Asia/Jerusalem', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
});

// Untyped scraper output must not decide what the page shows: one shape per field here.
const list = v => (Array.isArray(v) ? v : v == null ? [] : [String(v)]);
const num = v => (typeof v === 'number' && Number.isFinite(v) ? v : null);

// A finite number can still be absurd: 1e16 is a RangeError inside Intl, not a date.
const MIN_START = 946684800; // 2000-01-01T00:00:00Z
const MAX_START = 4102444800; // 2100-01-01T00:00:00Z
const when = v => (v !== null && v >= MIN_START && v <= MAX_START ? v : null);

export function normalizeEvent(ev, isoDate) {
  const src = ev !== null && typeof ev === 'object' && !Array.isArray(ev) ? ev : {};
  const start = when(num(src.start));
  const id = typeof src.id === 'string' && src.id
    ? src.id
    // Without an id every event collapses to one key in the distance map. An unformattable
    // start must not throw here — the record is skipped, but the id still has to exist.
    : `${src.venue_id ?? ''}|${isoDate}|${start === null ? '00:00' : clock.format(new Date(start * 1000))}`;
  return {
    ...src,
    id,
    day: isoDate,
    start,
    end: num(src.end),
    price_from: num(src.price_from),
    price_max: num(src.price_max),
    drive_min: num(src.drive_min),
    // true only when the minute is a city-centroid estimate, never for anything truthy
    drive_approx: src.drive_approx === true,
    lat: num(src.lat),
    lon: num(src.lon),
    free: src.free === true,
    scene: list(src.scene),
    crowd: list(src.crowd),
    notes: list(src.notes),
    enrichment: list(src.enrichment),
  };
}

// keyed by resolved path, so two bases cannot hand each other stale data
const cache = new Map();

export async function loadManifest(base = '.') {
  return readJSON(join(base, 'data/index.json'));
}

export async function loadDate(base, isoDate) {
  const path = join(base, `data/${isoDate}.json`);
  const cached = cache.get(path);
  if (cached) return cached;

  let events;
  try {
    events = await readJSON(path);
  } catch (err) {
    // a missing or malformed day must never blank the page
    console.warn(`getup: no data for ${isoDate}`, err.message);
    return [];
  }

  // A record with no usable start has no row: skip it here, where one bad record costs one line.
  const withDay = (Array.isArray(events) ? events : [])
    .map(ev => normalizeEvent(ev, isoDate))
    .filter(ev => ev.start !== null);
  cache.set(path, withDay);
  return withDay;
}

export async function loadVenues(base) {
  return readJSON(join(base, 'venue/venues.json'));
}

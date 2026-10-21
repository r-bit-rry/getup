// Reads the committed JSON in the browser (fetch) and in Node tests (fs).
export const readJSON = async (path) => {
  if (typeof window !== 'undefined') return (await fetch(path)).json();
  const { readFile } = await import('node:fs/promises');
  return JSON.parse(await readFile(path, 'utf8'));
};

export const join = (base, path) => `${base.replace(/\/+$/, '')}/${path}`;

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

  const withDay = (Array.isArray(events) ? events : []).map((ev) => ({ ...ev, day: isoDate }));
  cache.set(path, withDay);
  return withDay;
}

export async function loadVenues(base) {
  return readJSON(join(base, 'venue/venues.json'));
}

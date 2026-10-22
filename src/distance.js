// One keyless OSRM /table request for a non-default centre; null on any failure.
const OSRM = 'https://router.project-osrm.org/table/v1/driving';

// /table accepts 100 coordinates in total, origin included. Over the limit we
// return null rather than truncate: the caller keeps cached minutes and says so.
const MAX_DESTS = 99;

// A public router may hang; past this the caller keeps its cached minutes and says so.
const TIMEOUT_MS = 6000;

export async function recomputeDistances(events, centre, { fetchImpl, timeoutMs = TIMEOUT_MS } = {}) {
  const list = Array.isArray(events) ? events : [];
  if (!list.length) return [];
  if (!Number.isFinite(centre?.lat) || !Number.isFinite(centre?.lon)) return null;
  // An unpinned event costs its own label, not everyone's: it stays out of the
  // request and gets null back in its place.
  const pinned = [];
  list.forEach((ev, i) => { if (Number.isFinite(ev?.lat) && Number.isFinite(ev?.lon)) pinned.push(i); });
  if (!pinned.length) return list.map(() => null);
  if (pinned.length > MAX_DESTS) return null;

  // ~110 m is enough for a drive minute; the exact position never leaves the browser.
  const round3 = n => Math.round(n * 1000) / 1000;
  const coords = [[centre.lon, centre.lat], ...pinned.map(i => [list[i].lon, list[i].lat])]
    .map(([lon, lat]) => `${round3(lon)},${round3(lat)}`)
    .join(';');
  const url = `${OSRM}/${coords}?annotations=duration`;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await (fetchImpl ?? globalThis.fetch)(url, { signal: controller.signal });
    if (!res?.ok) return null;
    const body = await res.json();
    const row = body?.durations?.[0];
    if (body?.code !== 'Ok' || !Array.isArray(row) || row.length !== pinned.length + 1) return null;
    // OSRM puts null in an unreachable cell; rounding it would turn "unknown" into a 0-minute drive.
    const secs = row.slice(1);
    if (!secs.every(Number.isFinite)) return null;
    // One entry per input event, so callers can index the result by their own list.
    const out = list.map(() => null);
    pinned.forEach((index, k) => { out[index] = Math.round(secs[k] / 60); });
    return out;
  } catch {
    return null; // offline, malformed, or aborted by the timeout
  } finally {
    clearTimeout(timer);
  }
}

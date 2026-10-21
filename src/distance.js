// One keyless OSRM /table request for a non-default centre; null on any failure.
const OSRM = 'https://router.project-osrm.org/table/v1/driving';

// /table accepts 100 coordinates in total, origin included. Over the limit we
// return null rather than truncate: the caller keeps cached minutes and says so.
const MAX_DESTS = 99;

export async function recomputeDistances(events, centre, { fetchImpl } = {}) {
  const list = Array.isArray(events) ? events : [];
  if (!list.length) return [];
  if (!Number.isFinite(centre?.lat) || !Number.isFinite(centre?.lon)) return null;
  if (list.length > MAX_DESTS) return null;
  // One bad coordinate would shift every later index; refuse the whole batch.
  if (list.some(ev => !Number.isFinite(ev?.lat) || !Number.isFinite(ev?.lon))) return null;

  const coords = [[centre.lon, centre.lat], ...list.map(ev => [ev.lon, ev.lat])]
    .map(([lon, lat]) => `${lon},${lat}`)
    .join(';');
  const url = `${OSRM}/${coords}?annotations=duration`;

  try {
    const res = await (fetchImpl ?? globalThis.fetch)(url);
    if (!res?.ok) return null;
    const body = await res.json();
    const row = body?.durations?.[0];
    if (body?.code !== 'Ok' || !Array.isArray(row) || row.length !== list.length + 1) return null;
    // OSRM puts null in an unreachable cell; rounding it would turn "unknown" into a 0-minute drive.
    const secs = row.slice(1);
    if (!secs.every(Number.isFinite)) return null;
    return secs.map(sec => Math.round(sec / 60));
  } catch {
    return null;
  }
}

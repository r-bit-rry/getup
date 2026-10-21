// User never/always rules. A preference applied at read time, not derived data.
import { readJSON, join } from './data.js';

const EMPTY = () => ({ never: [], always: [] });

const isObject = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);

const rules = (list) => (Array.isArray(list) ? list.filter(isObject) : []);

const normalize = (p) => (isObject(p) ? { never: rules(p.never), always: rules(p.always) } : EMPTY());

const norm = (s) => String(s).trim().replace(/\s+/g, ' ').toLowerCase();

// shortcut: artist is matched against the event title, exact after normalization, no fuzzy match
const matches = (ev, rule) => {
  if (typeof rule.venue_id === 'string' && rule.venue_id) return ev.venue_id === rule.venue_id;
  if (typeof rule.artist === 'string' && norm(rule.artist)) return norm(ev.title ?? '') === norm(rule.artist);
  return false;
};

export async function loadPrefs(base = '.') {
  try {
    return normalize(await readJSON(join(base, 'prefs.json')));
  } catch {
    return EMPTY();
  }
}

export function applyPrefs(events, prefs) {
  const { never, always } = normalize(prefs);
  return events
    .filter((ev) => !never.some((rule) => matches(ev, rule)))
    .map((ev) => (always.some((rule) => matches(ev, rule)) ? { ...ev, notable: true } : ev));
}

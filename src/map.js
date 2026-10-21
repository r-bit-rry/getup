import * as maplibregl from '../assets/maplibre/maplibre-gl.mjs';
import { dayLabel, timeRange, startTime, leaveBy } from './format.js';

// The only place the tile style is named; swapping providers is this one line.
export const MAP_STYLE_URL = 'https://tiles.openfreemap.org/styles/positron';

const HEBREW = ['coalesce', ['get', 'name:he'], ['get', 'name:en'], ['get', 'name']];
const NETANYA = [34.8566, 32.3286];
const pins = new WeakMap();
const shown = new WeakMap();

const colour = ev => (ev.soldout ? 'var(--warn)' : ev.free ? 'var(--free)' : 'var(--primary)');

const timeText = ev => {
  if (!Number.isFinite(ev.start)) return '';
  return Number.isFinite(ev.end) && ev.end > ev.start ? timeRange(ev.start, ev.end) : startTime(ev.start);
};

const popupNode = ev => {
  const box = document.createElement('div');
  box.className = 'pinpop';
  const line = (tag, text, cls) => {
    if (!text) return;
    const p = document.createElement(tag);
    if (cls) p.className = cls;
    p.textContent = text;
    box.append(p);
  };
  line('strong', ev.title);
  line('span', ev.venue, 'sub');
  line('span', ev.city, 'sub');
  // day and time on separate lines: a combined Hebrew+range line lets bidi flip the range
  line('span', typeof ev.day === 'string' ? dayLabel(ev.day) : '');
  line('span', timeText(ev), 'time');
  line('span', Number.isFinite(ev.start) && Number.isFinite(ev.drive_min)
    ? `צא ${leaveBy(ev.start, ev.drive_min)}`
    : 'זמן נסיעה לא ידוע', 'sub');
  return box;
};

export function initMap(el, { styleUrl = MAP_STYLE_URL } = {}) {
  const map = new maplibregl.Map({
    container: el,
    style: styleUrl,
    center: NETANYA,
    zoom: 8.6, // the whole served region fits: Ashdod to Haifa, Netanya to the coast
    attributionControl: false,
  });
  // The static credit sits bottom-right; the legal links go bottom-left so they do not overlap.
  map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-left');

  // Close the open popup on a background click; a marker owns its own popup.
  map.on('click', e => {
    if (e.originalEvent?.target?.closest?.('.pin')) return;
    shown.get(map)?.remove();
    shown.delete(map);
  });

  map.on('load', () => {
    for (const layer of map.getStyle().layers ?? []) {
      if (layer.type !== 'symbol' || layer.layout?.['text-field'] === undefined) continue;
      try {
        map.setLayoutProperty(layer.id, 'text-field', HEBREW);
      } catch { /* one unlucky layer must not abort the rest */ }
    }
  });
  return map;
}

export function drawMarkers(map, events) {
  shown.get(map)?.remove();
  shown.delete(map);
  for (const old of pins.get(map) ?? []) old.remove();
  const placed = [];
  for (const ev of events ?? []) {
    if (!Number.isFinite(ev?.lat) || !Number.isFinite(ev?.lon)) continue; // no coordinates, no pin, no error
    try {
      const el = document.createElement('button');
      el.type = 'button';
      el.className = 'pin';
      el.style.setProperty('--pin', colour(ev));
      el.setAttribute('aria-label', [ev.title, ev.city].filter(Boolean).join(' — ') || 'אירוע');
      const marker = new maplibregl.Marker({ element: el }).setLngLat([ev.lon, ev.lat]).addTo(map);
      placed.push(marker); // recorded before the popup, so a bad popup cannot leak it
      const popup = new maplibregl.Popup({ offset: 12, closeOnClick: false }).setDOMContent(popupNode(ev));
      el.addEventListener('click', () => {
        shown.get(map)?.remove();
        popup.setLngLat(marker.getLngLat()).addTo(map);
        shown.set(map, popup);
      });
    } catch { /* one bad event must not stop the rest or leak a marker */ }
  }
  pins.set(map, placed);
}

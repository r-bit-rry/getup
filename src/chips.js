export const VOCAB = {
  scene: ['רוק', 'פופ', 'מזרחית', 'אלקטרונית/טכנו', 'היפ הופ', 'ג׳אז', 'בלוז', 'קלאסי', 'אינדי',
    'מופע מחווה', 'סטנדאפ', 'תיאטרון', 'מחול', 'ילדים', 'ספורט'],
  crowd: ['להט״ב', '18+', '30+', '40+', 'סטודנטים', 'משפחות', 'הורים', 'חיילים'],
  format: ['live_band', 'tribute', 'dj_set', 'orchestra', 'standup', 'theatre', 'festival', 'unknown'],
};

const ICON = {
  scene: '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
  crowd: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>'
    + '<path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
};

const esc = s => String(s).replace(/[&<>"']/g, c => `&#${c.charCodeAt(0)};`);

export function chip(kind, label) {
  const svg = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" `
    + `stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICON[kind] ?? ''}</svg>`;
  return `<span class="chip ${kind === 'scene' ? 's' : 'c'}" title="${esc(label)}">${svg}${esc(label)}</span>`;
}

// §7.5 signals the page promised: format, price pressure and plan-ahead. Absent values emit nothing.
const FORMAT_LABEL = {
  live_band: 'הופעה חיה', tribute: 'מופע מחווה', dj_set: 'DJ', orchestra: 'תזמורת',
  standup: 'סטנדאפ', theatre: 'תיאטרון', festival: 'פסטיבל',
};

const signalItems = ev => [
  ['scene', FORMAT_LABEL[ev.format]],
  ['crowd', ev.expensive === true ? 'יקר' : null],
  ['crowd', ev.commitment === 'plan_ahead' ? 'תכנון מראש' : null],
].filter(([, label]) => label);

export function chipsHTML(ev, max = 3) {
  const seen = new Set();
  const items = [
    ...signalItems(ev),
    ...(ev.scene ?? []).filter(t => VOCAB.scene.includes(t)).map(l => ['scene', l]),
    ...(ev.crowd ?? []).filter(t => VOCAB.crowd.includes(t)).map(l => ['crowd', l]),
  ].filter(([, label]) => {
    if (seen.has(label)) return false;
    seen.add(label);
    return true;
  });
  if (!items.length) return '';
  const shown = items.slice(0, max).map(([kind, label]) => chip(kind, label)).join('');
  const rest = items.slice(max).map(([, label]) => label);
  return rest.length
    ? `${shown}<span class="chip more" title="${esc(rest.join(' · '))}">+${rest.length}</span>`
    : shown;
}

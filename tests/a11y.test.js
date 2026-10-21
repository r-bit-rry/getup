import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');

test('document declares Hebrew and RTL', () => {
  assert.match(html, /<html[^>]+lang="he"/);
  assert.match(html, /<html[^>]+dir="rtl"/);
});

test('every control has an accessible name', () => {
  const buttons = html.match(/<button[^>]*>/g) || [];
  for (const b of buttons) assert.match(b, /aria-label=|aria-pressed=/, b);
});

test('no uppercase transform survives into the stylesheet', () => {
  const css = readFileSync(new URL('../styles.css', import.meta.url), 'utf8');
  assert.doesNotMatch(css, /text-transform:\s*uppercase/i);
});

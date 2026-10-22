import test from 'node:test';
import assert from 'node:assert/strict';
import { chipsHTML, chip, VOCAB } from '../src/chips.js';

test('vocabulary is the closed list from the spec', () => {
  assert.ok(VOCAB.scene.includes('מופע מחווה'));
  assert.ok(VOCAB.crowd.includes('להט״ב'));
  assert.ok(VOCAB.format.includes('dj_set'));
});

test('a chip always carries an icon and a Hebrew label', () => {
  const html = chip('scene', 'רוק');
  assert.match(html, /<svg/);
  assert.match(html, />רוק</);
  assert.match(html, /title="רוק"/);
});

test('scene and crowd render in different colours', () => {
  assert.match(chip('scene', 'רוק'), /chip s/);
  assert.match(chip('crowd', '30+'), /chip c/);
});

test('the cap collapses the remainder into +N with a hover title', () => {
  const ev = { scene: ['רוק', 'פופ', 'ג׳אז'], crowd: ['30+', 'להט״ב'] };
  const html = chipsHTML(ev, 3);
  assert.equal((html.match(/class="chip [sc]"/g) || []).length, 3);
  assert.match(html, /\+2/);
  assert.match(html, /title="30\+ · להט״ב"/);
});

test('an event with no tags yields an empty strip, not a placeholder chip', () => {
  assert.equal(chipsHTML({ scene: [], crowd: [] }), '');
});

test('tags outside the vocabulary are dropped, valid ones still render', () => {
  assert.equal(chipsHTML({ scene: ['סלסה'], crowd: [] }), '');
  const html = chipsHTML({ scene: ['סלסה', 'רוק'], crowd: [] });
  assert.equal((html.match(/class="chip [sc]"/g) || []).length, 1);
  assert.match(html, /title="רוק"/);
  assert.doesNotMatch(html, /סלסה/);
});

test('the three derived signals each reach the strip and lead it', () => {
  for (const [field, value, label] of [
    ['format', 'live_band', 'הופעה חיה'],
    ['format', 'tribute', 'מופע מחווה'],
    ['format', 'dj_set', 'DJ'],
    ['format', 'orchestra', 'תזמורת'],
    ['format', 'standup', 'סטנדאפ'],
    ['format', 'theatre', 'תיאטרון'],
    ['format', 'festival', 'פסטיבל'],
    ['expensive', true, 'יקר'],
    ['commitment', 'plan_ahead', 'תכנון מראש'],
  ]) {
    const html = chipsHTML({ scene: [], crowd: [], [field]: value });
    assert.match(html, new RegExp(`>${label}<`), `${field}=${value}`);
  }
});

test('a bare record emits no signal chip', () => {
  const html = chipsHTML({ format: 'unknown', expensive: false, commitment: 'jump_in', scene: [], crowd: [] });
  assert.equal(html, '');
  assert.doesNotMatch(chipsHTML({ scene: ['רוק'] }), /יקר|תכנון מראש|הופעה חיה/);
});

test('price pressure and plan-ahead do not share the crowd glyph', () => {
  const icon = kind => chip(kind, 'x').match(/<svg[^>]*>([\s\S]*?)<\/svg>/)[1];
  assert.notEqual(icon('expense'), icon('plan'));
  assert.notEqual(icon('expense'), icon('crowd'));
  assert.notEqual(icon('plan'), icon('crowd'));
});

test('the expensive chip is a shekel product, not a dollar one', () => {
  const icon = chip('expense', 'יקר').match(/<svg[^>]*>([\s\S]*?)<\/svg>/)[1];
  assert.match(icon, /₪/);
  // the dollar-sign path the glyph replaced must not come back
  assert.doesNotMatch(icon, /M12 2v20/);
});

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

// tests/prefs.test.js
import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdir, mkdtemp, writeFile } from 'node:fs/promises';
import { applyPrefs, loadPrefs } from '../src/prefs.js';

const ev = (o) => ({ id: '1', title: 't', venue_id: 'v1', notable: false, ...o });

const tmpDir = async () => {
  await mkdir('/tmp/opencode', { recursive: true });
  return mkdtemp('/tmp/opencode/prefs-');
};

test('never removes by venue id', () => {
  const p = { never: [{ venue_id: 'v1' }], always: [] };
  assert.deepEqual(applyPrefs([ev({})], p), []);
});

test('always promotes to notable without removing anything', () => {
  const p = { never: [], always: [{ venue_id: 'v1' }] };
  const r = applyPrefs([ev({}), ev({ id: '2', venue_id: 'v2' })], p);
  assert.equal(r.length, 2);
  assert.equal(r[0].notable, true);
  assert.equal(r[1].notable, false);
});

test('an empty prefs file changes nothing', () => {
  const e = ev({});
  assert.deepEqual(applyPrefs([e], { never: [], always: [] }), [e]);
});

test('artist rule matches title after trim, whitespace collapse and case-fold', () => {
  const p = { never: [{ artist: '  The   Cure ' }], always: [] };
  const r = applyPrefs([ev({ title: 'the cure' }), ev({ id: '2', title: 'The Cure Tribute' })], p);
  assert.deepEqual(r.map((e) => e.id), ['2']);
});

test('artist rule does not fuzzy-match', () => {
  const p = { never: [{ artist: 'Cure' }], always: [] };
  assert.equal(applyPrefs([ev({ title: 'The Cure' })], p).length, 1);
});

test('a rule with neither venue_id nor artist is ignored', () => {
  const p = { never: [{}], always: [{}] };
  const e = ev({});
  assert.deepEqual(applyPrefs([e], p), [e]);
});

test('applyPrefs does not mutate its input', () => {
  const events = [ev({})];
  const snapshot = structuredClone(events);
  applyPrefs(events, { never: [], always: [{ venue_id: 'v1' }] });
  assert.deepEqual(events, snapshot);
});

test('loadPrefs reads a valid prefs.json', async () => {
  const dir = await tmpDir();
  await writeFile(`${dir}/prefs.json`, JSON.stringify({ never: [{ venue_id: 'v9' }], always: [] }));
  assert.deepEqual(await loadPrefs(dir), { never: [{ venue_id: 'v9' }], always: [] });
});

test('loadPrefs resolves the empty shape when the file is missing', async () => {
  const dir = await tmpDir();
  assert.deepEqual(await loadPrefs(dir), { never: [], always: [] });
});

test('loadPrefs resolves the empty shape when the JSON is malformed', async () => {
  const dir = await tmpDir();
  await writeFile(`${dir}/prefs.json`, '{not json');
  assert.deepEqual(await loadPrefs(dir), { never: [], always: [] });
});

test('loadPrefs resolves the empty shape for non-object config', async () => {
  const dir = await tmpDir();
  for (const garbage of ['null', '[]', '"oops"', '{"never":"x","always":{}}']) {
    await writeFile(`${dir}/prefs.json`, garbage);
    assert.deepEqual(await loadPrefs(dir), { never: [], always: [] }, garbage);
  }
});

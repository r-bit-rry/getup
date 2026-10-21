import test from 'node:test';
import assert from 'node:assert/strict';
import { recomputeDistances } from '../src/distance.js';

test('an unreachable router returns null instead of throwing', async () => {
  const r = await recomputeDistances([{ lat: 32.1, lon: 34.8 }], { lat: 0, lon: 0 },
    { fetchImpl: async () => { throw new Error('offline'); } });
  assert.equal(r, null);
});

test('a malformed router response returns null', async () => {
  const r = await recomputeDistances([{ lat: 32.1, lon: 34.8 }], { lat: 0, lon: 0 },
    { fetchImpl: async () => ({ ok: true, json: async () => ({ code: 'NoTable' }) }) });
  assert.equal(r, null);
});

test('one /table call puts the origin first and rounds minutes', async () => {
  let called;
  const r = await recomputeDistances(
    [{ lat: 32.1, lon: 34.8 }, { lat: 32.2, lon: 34.9 }],
    { lat: 32, lon: 34.7 },
    { fetchImpl: async url => { called = url; return { ok: true, json: async () => ({ code: 'Ok', durations: [[0, 600.4, 1200.6]] }) }; } },
  );
  assert.deepEqual(r, [10, 20]);
  assert.match(called, /34\.7,32;34\.8,32\.1;34\.9,32\.2/);
});

test('more than 99 destinations is refused, not truncated or requested', async () => {
  let calls = 0;
  const events = Array.from({ length: 100 }, (_, i) => ({ lat: 32 + i / 1000, lon: 34 }));
  const r = await recomputeDistances(events, { lat: 32, lon: 34 },
    { fetchImpl: async () => { calls += 1; return { ok: true, json: async () => ({ code: 'Ok', durations: [] }) }; } });
  assert.equal(r, null);
  assert.equal(calls, 0);
});

test('an unreachable destination is null, never a zero-minute drive', async () => {
  const r = await recomputeDistances([{ lat: 32.1, lon: 34.8 }], { lat: 32, lon: 34.7 },
    { fetchImpl: async () => ({ ok: true, json: async () => ({ code: 'Ok', durations: [[0, null]] }) }) });
  assert.equal(r, null);
});

test('a durations row that does not match the destinations is rejected', async () => {
  const r = await recomputeDistances([{ lat: 32.1, lon: 34.8 }], { lat: 32, lon: 34.7 },
    { fetchImpl: async () => ({ ok: true, json: async () => ({ code: 'Ok', durations: [[0]] }) }) });
  assert.equal(r, null);
});

test('an empty event list returns [] without touching the network', async () => {
  let calls = 0;
  const r = await recomputeDistances([], { lat: 32, lon: 34 },
    { fetchImpl: async () => { calls += 1; return { ok: true, json: async () => ({ code: 'Ok', durations: [[]] }) }; } });
  assert.deepEqual(r, []);
  assert.equal(calls, 0);
});

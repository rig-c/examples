import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createOutfitTransaction, releaseCandidate } from './outfit-transaction.mjs';

function harness() {
  const requests = [], committed = [], errors = [], pending = [];
  let active = true;
  const transaction = createOutfitTransaction({
    load: () => new Promise((resolve, reject) => requests.push({ resolve, reject })),
    current: () => active,
    commit: (request, candidate) => { if (candidate.failCommit) throw Error('commit failed'); committed.push(request); },
    pending: value => pending.push(value), failed: error => errors.push(error),
  });
  return { transaction, requests, committed, errors, pending, leave: () => { active = false; transaction.invalidate(); } };
}
function candidate() {
  const calls = [];
  return { calls, player: { dispose() { calls.push('player'); } }, assets: { dispose() { calls.push('assets'); } }, sub: { remove() { calls.push('sub'); } } };
}
test('latest outfit wins and stale success releases its detached candidate', async () => {
  const h = harness(), a = candidate(), b = candidate();
  const first = h.transaction.open('homewear'), last = h.transaction.open('office');
  h.requests[1].resolve(b); assert.equal(await last, true);
  h.requests[0].resolve(a); assert.equal(await first, false);
  assert.deepEqual(h.committed, ['office']); assert.deepEqual(a.calls, ['player', 'assets', 'sub']); assert.deepEqual(b.calls, []);
});
test('scene invalidation suppresses late errors and releases late success', async () => {
  const h = harness(), a = candidate();
  const first = h.transaction.open('homewear'); h.leave(); h.requests[0].resolve(a); await first;
  assert.deepEqual(h.committed, []); assert.deepEqual(a.calls, ['player', 'assets', 'sub']); assert.equal(h.pending.at(-1), false);
  const late = h.transaction.open('office'); h.leave(); h.requests[1].reject(Error('late 404')); await late;
  assert.deepEqual(h.errors, []);
});
test('load failure and pre-commit refusal preserve active ownership and report failure', async () => {
  const h = harness(), a = candidate();
  const first = h.transaction.open('homewear'); h.requests[0].reject(Error('404')); assert.equal(await first, false);
  const second = h.transaction.open('homewear'); a.failCommit = true; h.requests[1].resolve(a); assert.equal(await second, false);
  assert.deepEqual(h.committed, []); assert.equal(h.errors.length, 2); assert.deepEqual(a.calls, ['player', 'assets', 'sub']);
});
test('candidate cleanup still releases assets and DOM when player disposal throws', () => {
  const a = candidate();
  a.player.dispose = () => { a.calls.push('player'); throw Error('dispose failed'); };
  assert.throws(() => releaseCandidate(a), AggregateError);
  assert.deepEqual(a.calls, ['player', 'assets', 'sub']);
});

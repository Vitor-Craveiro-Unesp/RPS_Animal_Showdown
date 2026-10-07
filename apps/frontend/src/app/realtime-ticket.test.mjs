import test from 'node:test';
import assert from 'node:assert/strict';
import { RealtimeTicketRenewal } from './realtime-ticket.mjs';

function fixture(fetchTicket = async () => 'fresh-ticket') {
  let nextId = 0;
  const timers = new Map(), sent = [], failures = [];
  const host = { setTimeout(fn, ms) { const id = ++nextId; timers.set(id, { fn, ms }); return id; }, clearTimeout(id) { timers.delete(id); } };
  const renewal = new RealtimeTicketRenewal({ fetchTicket, send: frame => sent.push(frame), onFailure: () => failures.push(true), host, random: () => 0.5 });
  async function runNext() { const [id, timer] = timers.entries().next().value; timers.delete(id); await timer.fn(); }
  return { renewal, timers, sent, failures, runNext };
}

test('renews early on the same socket and reschedules only after server acknowledgement', async () => {
  const f = fixture();
  f.renewal.start(300_000);
  assert.equal([...f.timers.values()][0].ms, 232_500);
  await f.runNext();
  assert.deepEqual(f.sent, [{ type: 'renew', ticket: 'fresh-ticket' }]);
  assert.equal([...f.timers.values()][0].ms, 10_000);
  f.renewal.acknowledge(299_000);
  assert.equal(f.timers.size, 1);
  assert.equal([...f.timers.values()][0].ms, 231_500);
  assert.equal(f.failures.length, 0);
});

test('a stopped connection cannot send the result of an in-flight renewal', async () => {
  let resolve;
  const f = fixture(() => new Promise(done => { resolve = done; }));
  f.renewal.start(300_000);
  const pending = f.runNext();
  f.renewal.stop();
  resolve('late-ticket');
  await pending;
  assert.equal(f.sent.length, 0);
  assert.equal(f.timers.size, 0);
});

test('failed issuance or missing acknowledgement triggers connection recovery', async () => {
  const denied = fixture(async () => { throw new Error('revoked'); });
  denied.renewal.start(300_000);
  await denied.runNext();
  assert.equal(denied.failures.length, 1);
  const silent = fixture();
  silent.renewal.start(300_000);
  await silent.runNext();
  await silent.runNext();
  assert.equal(silent.failures.length, 1);
});

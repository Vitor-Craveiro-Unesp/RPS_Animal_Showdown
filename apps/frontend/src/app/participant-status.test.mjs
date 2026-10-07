import test from 'node:test';
import assert from 'node:assert/strict';
import { participantStatusCounts } from './participant-status.mjs';

test('organizer separates draft strategy from confirmed participants', () => {
  assert.deepEqual(participantStatusCounts([
    { membership_status: 'configuring_strategy', ready: false },
    { membership_status: 'ready', ready: true },
    { membership_status: 'joined', ready: false },
    { membership_status: 'removed', ready: false, removed: true },
  ]), { configuring: 1, ready: 1 });
});

import test from 'node:test';
import assert from 'node:assert/strict';
import { PresentationQueue, eventSteps, scheduledSteps, duration, stateForPresentation } from './presentation.mjs';
import { AUDIO_ASSETS, AudioManager } from './audio-manager.mjs';

const event = (sequence, eventType = 'round_resolved', stateVersion = sequence) => ({ eventId: `id-${sequence}`, sequence, eventType, payload: { stateVersion } });

function host() {
  const created = [], spoken = [];
  class Media {
    constructor(source) { this.src = source; this.currentTime = 0; this.paused = true; created.push(this); }
    play() { this.paused = false; return Promise.resolve(); }
    pause() { this.paused = true; }
  }
  return { Audio: Media, created, spoken, SpeechSynthesisUtterance: class { constructor(text) { this.text = text; } }, speechSynthesis: { cancel() {}, getVoices() { return []; }, speak(value) { spoken.push(value); } } };
}

test('all configured animal IDs resolve to a local MP3 in the official animals directory', () => {
  assert.equal(Object.keys(AUDIO_ASSETS.animals).length, 27);
  for (const source of Object.values(AUDIO_ASSETS.animals)) assert.match(source, /^\/audio\/animals\/A[-_][\w-]+\.mp3$/);
  assert.match(AUDIO_ASSETS.background, /^\/audio\/background\//);
  assert.deepEqual(Object.keys(AUDIO_ASSETS.effects).sort(), ['champion', 'countdown', 'heart_lost', 'podium', 'tie']);
});

test('normal selection replaces the prior animal sound and supports every configured animal', () => {
  const h = host(), audio = new AudioManager(h); audio.configure(true, false);
  for (const animal of Object.keys(AUDIO_ASSETS.animals).filter(id => id !== 'zombie')) assert.equal(audio.animal(animal), true);
  assert.equal(audio.channels.get('animal').src, AUDIO_ASSETS.animals.shark);
  assert.equal(h.created.at(-2).paused, true);
});

test('zombie always replaces the original animal sound until the run is reset', () => {
  const h = host(), audio = new AudioManager(h); audio.configure(true, false);
  audio.animal('otter'); assert.equal(audio.channels.get('animal').src, AUDIO_ASSETS.animals.otter);
  audio.winner('otter', true); assert.equal(audio.channels.get('animal').src, AUDIO_ASSETS.animals.zombie);
  audio.winner('otter', true); assert.equal(audio.channels.get('animal').src, AUDIO_ASSETS.animals.zombie);
  audio.resetRun(); audio.animal('otter'); assert.equal(audio.channels.get('animal').src, AUDIO_ASSETS.animals.otter);
});

test('winner uses its animal normally and zombie MP3 when its official status is zombie', () => {
  const h = host(), audio = new AudioManager(h); audio.configure(true, false);
  audio.winner('tiger', false); assert.equal(audio.channels.get('animal').src, AUDIO_ASSETS.animals.tiger);
  audio.winner('tiger', true); assert.equal(audio.channels.get('animal').src, AUDIO_ASSETS.animals.zombie);
});

for (const effects of [false, true]) for (const music of [false, true]) test(`music/effects independent ${effects}/${music}`, () => {
  const h = host(), audio = new AudioManager(h); audio.configure(effects, music);
  assert.equal(audio.channels.has('background'), music);
  assert.equal(audio.effect('heart_lost'), effects);
  assert.equal(audio.channels.has('effect'), effects);
  assert.equal(audio.animal('lion'), effects);
  audio.dispose(); assert.equal(audio.channels.size, 0);
});

test('background music uses the elevated but bounded presentation volume', () => {
  const h = host(), audio = new AudioManager(h); audio.configure(false, true);
  assert.equal(audio.channels.get('background').volume, .24);
});

test('only selected local effects are used; elimination and generic victory remain silent', () => {
  const h = host(), audio = new AudioManager(h); audio.configure(true, false);
  for (const [eventType, phase, sound] of [['heart_lost', 'heart', 'heart_lost'], ['player_eliminated', 'elimination', null], ['match_completed', 'victory', null]]) {
    const step = eventSteps(event(1, eventType))[0]; assert.equal(step.phase, phase); assert.equal(step.sound, sound);
  }
  assert.equal(audio.effect('player_eliminated'), false); assert.equal(audio.effect('victory'), false);
  audio.effect('countdown'); assert.equal(audio.channels.get('effect').src, AUDIO_ASSETS.effects.countdown);
  audio.effect('heart_lost'); assert.equal(audio.channels.get('effect').src, AUDIO_ASSETS.effects.heart_lost);
});

test('a tie uses the local tie cue only when the authoritative outcome is tie', () => {
  const tied = eventSteps({ ...event(4), payload: { stateVersion: 4, outcome: 'tie' } });
  const resolved = eventSteps({ ...event(5), payload: { stateVersion: 5, outcome: 'player_one_win' } });
  assert.equal(tied.at(-1).sound, 'tie');
  assert.equal(resolved.at(-1).sound, null);
  const h = host(), audio = new AudioManager(h); audio.configure(true, false);
  audio.effect(tied.at(-1).sound); assert.equal(audio.channels.get('effect').src, AUDIO_ASSETS.effects.tie);
});

test('the winner appears alone before silver, bronze and the looping podium music', async () => {
  const h = host(), audio = new AudioManager(h); audio.configure(true, false);
  const steps = eventSteps(event(9, 'champion'));
  assert.deepEqual(steps.map(step => [step.phase, step.sound]), [
    ['champion', 'champion'], ['podium_second', null], ['podium_third', null], ['podium', 'podium'],
  ]);
  assert.deepEqual(steps.map(step => step.ms), [7500, 900, 900, 0]);
  audio.effect(steps[0].sound);
  const champion = audio.channels.get('effect');
  let finished = false;
  const completion = audio.whenFinished('effect').then(() => { finished = true; });
  assert.equal(finished, false);
  champion.onended();
  await completion;
  assert.equal(finished, true);
  audio.effect(steps.at(-1).sound);
  assert.equal(audio.channels.get('effect').src, AUDIO_ASSETS.effects.podium);
  assert.equal(audio.channels.get('effect').loop, true);
  assert.equal(eventSteps(event(8, 'podium_decided')).length, 0);
});

test('the live bracket uses prior server state until the loss and victory are shown', () => {
  const priorMatch = { match_id: 'm1', player_one_hearts: 2, player_two_hearts: 2, winner_id: null, loser_id: null };
  const nextMatch = { ...priorMatch, player_one_hearts: 1, winner_id: 'p2', loser_id: 'p1' };
  const previous = { completed_rounds: [], current_round: { number: 1, matches: [priorMatch] }, champion_id: null };
  const next = { completed_rounds: [{ number: 1, matches: [nextMatch] }], current_round: null, champion_id: 'p2' };
  for (const phase of ['countdown', 'reveal', 'result']) assert.equal(stateForPresentation(previous, next, phase, 'm1'), previous);
  const heart = stateForPresentation(previous, next, 'heart', 'm1');
  assert.equal(heart.current_round.matches[0].player_one_hearts, 1);
  assert.equal(heart.current_round.matches[0].winner_id, null);
  assert.equal(heart.champion_id, null);
  assert.equal(stateForPresentation(previous, next, 'victory', 'm1'), next);
});

test('effects and animal cues share the foreground without overlap', async () => {
  const h = host(), audio = new AudioManager(h);
  audio.configure(true, true);
  audio.effect('tie');
  const tie = audio.channels.get('effect');
  audio.effect('heart_lost');
  assert.equal(tie.paused, true);
  const heart = audio.channels.get('effect');
  const completed = audio.whenFinished('effect');
  audio.winner('tiger');
  await completed;
  assert.equal(heart.paused, true);
  assert.equal(audio.channels.get('animal').src, AUDIO_ASSETS.animals.tiger);
  audio.effect('champion');
  assert.equal(audio.channels.has('animal'), false);
  assert.equal(audio.channels.has('background'), false);
  audio.effect('podium');
  assert.equal(audio.channels.get('effect').loop, true);
  assert.equal(audio.channels.has('background'), false);
});

test('narration is independent from effects and contains canonical scientific name in every supported locale', () => {
  const h = host(), audio = new AudioManager(h); audio.configure(false, false);
  for (const locale of ['pt-BR', 'en', 'zh-CN', 'ar']) assert.equal(audio.narrate('Animal', 'Panthera tigris', locale), true);
  assert.equal(h.spoken.length, 4); assert.equal(h.spoken.at(-1).lang, 'ar-SA'); assert.ok(h.spoken.every(item => item.text.includes('Panthera tigris')));
});

test('queue preserves official ordering, deduplicates reconnect replay and resets for a new run', () => {
  const queue = new PresentationQueue();
  assert.equal(queue.accept(event(1)), true); assert.equal(queue.accept(event(1)), false);
  queue.reconcile(8); assert.equal(queue.accept(event(3)), false); assert.equal(queue.accept(event(9)), true);
  queue.reset(); assert.equal(queue.accept(event(1)), true);
});

for (const speed of [.5, 1, 2, 4, 8]) test(`countdown stays ordered at ${speed}x`, () => {
  const steps = eventSteps(event(1), speed, speed);
  assert.deepEqual(steps.slice(0, 3).map(step => step.number), [3, 2, 1]);
  assert.equal(steps[3].phase, 'reveal'); assert.equal(steps[0].ms, 650 / speed); assert.equal(duration(100, speed), 100 / speed);
});

test('every viewer uses the same authoritative phase times instead of arrival time', () => {
  const official = { ...event(12), payload: { stateVersion: 12, clientPresentationAtMs: 10_000 } };
  const early = scheduledSteps(official, 1, 1, 8_000);
  const late = scheduledSteps(official, 1, 1, 9_500);
  assert.deepEqual(early.map(step => step.startsAtMs), late.map(step => step.startsAtMs));
  assert.deepEqual(early.slice(0, 3).map(step => step.startsAtMs), [10_000, 10_650, 11_300]);
  assert.equal(early.at(-1).startsAtMs, 12_600);
  assert.equal(scheduledSteps(event(13), 1, 1, 20_000)[0].startsAtMs, 20_000);
});

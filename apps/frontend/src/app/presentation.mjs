// Pure presentation queue. No RNG, results, hearts or bracket decisions live here.
export function duration(ms, speed = 1) {
  return ms / ([0.5, 1, 2, 4, 8].includes(Number(speed)) ? Number(speed) : 1);
}
// The bundled champion.mp3 is about seven seconds. Leave a short tail before
// revealing the other places, using the same duration as the backend clock.
export const CHAMPION_CUE_MS = 7500;
export function eventSteps(event, movement = 1, countdown = 1) {
  const step = (phase, ms, sound = null) => ({ phase, ms: duration(ms, movement), sound, event });
  switch (event.eventType) {
    case 'player_waiting': return [step('waiting', 900)];
    case 'second_chance_selected': return [step('secondChance', 1400)];
    case 'match_started': return [step('entrance', 900)];
    case 'round_resolved': return [3, 2, 1].map(number => ({ ...step('countdown', 0, 'countdown'), number, ms: duration(650, countdown) })).concat([step('reveal', 650), step('result', 500, event.payload?.outcome === 'tie' ? 'tie' : null)]);
    case 'heart_lost': return [step('heart', 650, 'heart_lost')];
    case 'player_eliminated': return [step('elimination', 700)];
    case 'match_completed': return [step('victory', 750)];
    case 'player_advanced': return [step('advance', 900)];
    case 'bye': return [step('bye', 900)];
    // podium_decided arrives before champion in the official event log. Reveal
    // the winner first, then the other places, then start the looping podium cue.
    case 'champion': return [
      { ...step('champion', 0, 'champion'), ms: CHAMPION_CUE_MS },
      { ...step('podium_second', 0), ms: 900 },
      { ...step('podium_third', 0), ms: 900 },
      step('podium', 0, 'podium'),
    ];
    default: return [];
  }
}

// Each event carries a server-owned UTC slot. The receive time is never used
// as the start of a competitive reveal unless talking to a legacy backend.
export function scheduledSteps(event, movement = 1, countdown = 1, now = Date.now()) {
  const serverSlot = event.payload?.clientPresentationAtMs;
  let startsAtMs = Number.isFinite(serverSlot) ? serverSlot : now;
  return eventSteps(event, movement, countdown).map(step => {
    const scheduled = { ...step, startsAtMs };
    startsAtMs += step.ms;
    return scheduled;
  });
}

// These are server snapshots. The presentation only controls when each part of
// an already-authoritative transition becomes visible to the audience.
export function stateForPresentation(previous, next, phase, matchId) {
  if (!previous) return next ?? null;
  if (!next || !matchId) return previous;
  if (phase === 'victory') return next;
  if (phase !== 'heart') return previous;
  const nextMatch = [...next.completed_rounds, ...(next.current_round ? [next.current_round] : [])]
    .flatMap(round => round.matches).find(match => match.match_id === matchId);
  if (!nextMatch) return previous;
  const updateRound = round => round && ({ ...round, matches: round.matches.map(match =>
    match.match_id === matchId ? { ...match,
      player_one_hearts: nextMatch.player_one_hearts,
      player_two_hearts: nextMatch.player_two_hearts,
    } : match) });
  return { ...previous,
    completed_rounds: previous.completed_rounds.map(updateRound),
    current_round: updateRound(previous.current_round),
  };
}
export class PresentationQueue {
  constructor() { this.pending = []; this.sequence = 0; this.ids = new Set(); this.floorVersion = -1; this.generation = 0; }
  accept(event) {
    if (!event || !Number.isInteger(event.sequence) || event.sequence <= this.sequence || this.ids.has(event.eventId)) return false;
    this.sequence = event.sequence;
    this.ids.add(event.eventId);
    if (this.ids.size > 512) this.ids.delete(this.ids.values().next().value);
    if ((event.payload?.stateVersion ?? 0) <= this.floorVersion) return false;
    this.pending.push(event);
    return true;
  }
  next() { return this.pending.shift(); }
  reconcile(version) {
    if (version < this.floorVersion) return false;
    this.floorVersion = version;
    this.pending = this.pending.filter(event => (event.payload?.stateVersion ?? 0) > version);
    this.generation++;
    return true;
  }
  clear() { this.pending = []; this.generation++; }
  reset() { this.clear(); this.sequence = 0; this.ids.clear(); this.floorVersion = -1; }
}

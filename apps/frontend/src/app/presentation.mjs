// Pure presentation queue. No RNG, results, hearts or bracket decisions live here.
export function duration(ms, speed = 1) {
  return ms / ([0.5, 1, 2, 4, 8].includes(Number(speed)) ? Number(speed) : 1);
}
export function eventSteps(event, movement = 1, countdown = 1) {
  const step = (phase, ms, sound = null) => ({ phase, ms: duration(ms, movement), sound, event });
  switch (event.eventType) {
    case 'player_waiting': return [step('waiting', 900)];
    case 'second_chance_selected': return [step('secondChance', 1400)];
    case 'match_started': return [step('entrance', 900)];
    case 'round_resolved': return [3, 2, 1].map(number => ({ ...step('countdown', 0, 'countdown'), number, ms: duration(650, countdown) })).concat([step('reveal', 650), step('result', 500)]);
    case 'heart_lost': return [step('heart', 650, 'heart_lost')];
    case 'player_eliminated': return [step('elimination', 700)];
    case 'match_completed': return [step('victory', 750)];
    case 'player_advanced': return [step('advance', 900)];
    case 'bye': return [step('bye', 900)];
    // podium_decided arrives before champion in the official event log. The visual
    // timeline intentionally delays the podium until after the champion cue.
    case 'champion': return [step('champion', 1600, 'champion'), step('podium', 900, 'podium')];
    default: return [];
  }
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

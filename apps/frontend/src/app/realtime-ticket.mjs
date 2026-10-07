// Renew a short-lived grant on the existing connection. Relative lifetimes
// avoid depending on a spectator's wall clock; jitter spreads a venue's load.
export class RealtimeTicketRenewal {
  constructor({ fetchTicket, send, onFailure, host = globalThis, random = Math.random }) {
    Object.assign(this, { fetchTicket, send, onFailure, host, random });
    this.generation = 0;
    this.timer = null;
    this.ackTimer = null;
  }
  start(lifetimeMs) {
    this.stop();
    if (!Number.isFinite(lifetimeMs) || lifetimeMs <= 0) { this.onFailure(); return; }
    const generation = this.generation;
    const delay = Math.max(1000, lifetimeMs - 60_000 - this.random() * 15_000);
    this.timer = this.host.setTimeout(async () => {
      try {
        const ticket = await this.fetchTicket();
        if (generation !== this.generation) return;
        this.ackTimer = this.host.setTimeout(() => {
          if (generation === this.generation) this.onFailure();
        }, 10_000);
        this.send({ type: 'renew', ticket });
      } catch {
        if (generation === this.generation) this.onFailure();
      }
    }, delay);
  }
  acknowledge(lifetimeMs) { this.start(lifetimeMs); }
  stop() {
    this.generation++;
    if (this.timer !== null) this.host.clearTimeout(this.timer);
    if (this.ackTimer !== null) this.host.clearTimeout(this.ackTimer);
    this.timer = this.ackTimer = null;
  }
}

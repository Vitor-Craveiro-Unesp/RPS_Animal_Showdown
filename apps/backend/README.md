# Backend

FastAPI is the authoritative HTTP boundary for official tournaments. It accepts
only validated intents and must invoke the isolated Game Engine for official
outcomes. Browser-supplied results, lives, BYEs, brackets, advances, winners or
locked strategies are rejected as unknown fields and are never authoritative.

## Current HTTP boundary

- `POST /v1/tournaments` creates a room with a canonical internal UUID and an
  80-bit opaque access code. The UUID identifies every server-side aggregate;
  the code is only a public entry mechanism. It returns a one-time organizer
  bearer capability and
  the server keeps only a SHA-256 digest of that credential.
- `POST /v1/tournaments/join` creates a room-scoped participant capability. An
  unavailable, closed, full or unknown code always yields the same neutral 404.
- Participant routes allow strategy save, ready and isolated training intent.
  A strategy contains all ten distributions from the product core and every one
  must total exactly 100. The canonical tie conditions are `tied_with_*`.
- Organizer routes require that room's organizer capability; participant or
  organizer credentials from another room receive `403`.
- `POST /admin/start` accepts only `{}`, requires at least two ready players,
  invokes the Game Engine with server-held strategy snapshots, locks those
  snapshots and stores an Engine-derived official state snapshot. It never
  accepts a competitive state in the body.
- Training creates a server-held Engine `TrainingState` per player. It is kept
  outside the official aggregate and is cleared when the tournament starts.

## Security and deployment boundary

The in-memory repository is available only when an isolated unit test injects
it explicitly into `create_app`. The service fails at process start when
`DATABASE_URL` is absent; it never silently falls back to process-local state.
The durable service uses PostgreSQL shared fixed-window counters, so every API
instance consumes the same atomic operation/subject budget. The table retains
only a SHA-256 subject key and an expiry, never a raw IP address or bearer
credential. If PostgreSQL is unavailable, protected HTTP routes return a
neutral `503` and WebSocket handshakes close with `1013`; there is no fallback
to per-process memory. Durable adapters keep credential digests,
expiry/revocation, room authorization and atomic state changes. Do not trust
`X-Forwarded-For` or `Forwarded` at the application layer; configure the
production proxy boundary to strip them and provide a verified peer address.

Operation limits apply to creation, joining, strategy/ready updates, training,
administrative requests, realtime-ticket issuance and every WebSocket
connection/reconnection before `accept`. Every protected action consumes an
`ip:<ASGI peer>` key; actions carrying a bearer also consume a separate
`credential:<SHA-256>` key. Administrative and participant-capability limits
run before bearer validation, so invalid credentials also consume a budget.

The HTTP boundary permits only the explicit local development origin and uses
bearer headers rather than cookies (`allow_credentials=False`). Production must
set an exact origin allowlist and preserve the no-cookie posture unless Security
approves a CSRF design.

See [the integration contract](../../docs/contracts.md), [security gate](../../docs/security-checklist.md), and [backend security boundary](docs/security-boundary.md).

## PostgreSQL authoritative path

`DATABASE_URL` is mandatory for the application service, which selects the
durable `PostgresTournamentStore`. It requires migrations and
`REALTIME_TICKET_SIGNING_KEY`. Tournament start commits the canonical Engine
snapshot, transition, public event and outbox atomically; see
[the PostgreSQL flow](docs/postgres-authoritative-flow.md).

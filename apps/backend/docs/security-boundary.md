# Backend security boundary

This document describes the backend increment for **SEC-001**, **SEC-002**,
**SEC-004** and the initial HTTP posture for **SEC-006**. Product rules remain in
[`PROJECT_CORE.md`](../../../PROJECT_CORE.md); Engine rules remain owned by
`packages/game-engine`.

## Intent-only API

The HTTP DTOs use strict schemas (`extra="forbid"`). They permit creation,
joining, player strategy, ready, training choice, and administrative commands.
No route model contains client-supplied result, remaining hearts, BYE, bracket,
advance, winner, random value or official event. `start` accepts only `{}` and
calls a `GameEngineGateway` with server-held snapshots.

The in-process adapter builds immutable Engine `Strategy` and `Competitor`
values exclusively from server-held records and executes `start_tournament`.
It persists a JSON-compatible state snapshot only after a successful Engine
transition. Start requires at least two confirmed participants, closes
registration, freezes their strategies and clears independent training states.
The local adapter is intentionally not transaction-safe across processes. With
`DATABASE_URL`, `PostgresTournamentStore` makes Engine execution, canonical
snapshot restoration, snapshot/version persistence, outbox insertion and
idempotency validation one PostgreSQL transaction. PostgreSQL integration tests
are required before public deployment.

## Room capabilities (SEC-001)

Creation issues a random organizer bearer capability exactly once. The store
retains its SHA-256 digest, an expiry and revocation flag—not the bearer value.
Every organizer route checks that credential against the requested room. A known
participant credential or another room's organizer credential receives `403`.
Missing, malformed, expired, revoked or unknown credentials receive `401`.

The local 12-hour TTL is an implementation policy for this development adapter,
not a recovery/authentication product decision. A durable identity and recovery
policy still require Security and Database + Realtime review before public use.

## Opaque codes and abuse controls (SEC-004)

Codes have the form `RPS-` plus 16 characters selected using `secrets` from a
32-character alphabet: 80 bits of entropy. Codes are non-sequential and never
derived from a database identifier. Invalid, closed, started and full rooms have
the same `404 Tournament is not available.` response on join.

The durable path uses `shared_rate_limit_buckets`, a PostgreSQL fixed-window
counter. Its `INSERT … ON CONFLICT` atomically increments an operation plus
SHA-256 subject key, resetting it only after its database TTL has expired. This
is shared by all API instances and avoids an additional V0.1 service. Local
`SlidingWindowRateLimiter` is limited to isolated unit-test injection.

Tournament creation has no application-level request quota. Anonymous creation
still writes a room and organizer capability to PostgreSQL, so automated abuse
can increase storage and hosting costs. Monitor creation volume in production.

Limits are operation-specific: join 12/10 minutes;
strategy/ready 20/minute; training 30/minute; administration 20/minute;
participant-authentication 20/minute; and realtime ticket/handshake 30/minute.
Every request consumes a key based on `ip:<ASGI peer>`; bearer-bearing actions
also consume `credential:<SHA-256>`. Raw addresses and bearer values are not
persisted. `X-Forwarded-For` and `Forwarded` are never trusted by the app: the
edge proxy must remove user-provided variants and arrange for the ASGI peer to
be the verified client address. Administrative and participant limits run
before bearer validation, so rejected guesses cannot avoid rate limiting.

If the shared limiter is unavailable or an increment fails, routes that use it
return a neutral `503` with a short retry hint and WebSocket handshakes close
before `accept` with `1013`. Tournament creation uses the durable store but
does not call the limiter. There is no local fail-open fallback for protected
routes.

## Durable authorization and realtime handoff (SEC-001 / SEC-003)

The local bearer capabilities are a development reference only. The durable
repository stores the canonical `tournament_id` UUID, capability digest,
role (`organizer` or `player`), subject/player ID, expiry and revocation state.
Every administrative action must query that record scoped by `tournament_id`.

Realtime tickets must be short-lived, opaque credentials stored by digest and
bound to: `ticket_id`, `tournament_id`, subject ID, allowed role/channel,
issued/expiry timestamps and revocation/one-time-use state. The backend may
issue a ticket only after room authorization. Realtime validates the ticket and
Origin before subscription, while only the server publishes official GameEvent
records. In the PostgreSQL path, ticket issuance is recorded after durable room
authorization; the registered socket checks ticket and source capability, and
an outbox worker publishes only committed events.

## CORS / CSRF posture (SEC-006)

The current API accepts only an explicit local origin and does not enable CORS
credentials. Authentication uses the `Authorization: Bearer` header, not a
cookie, so browser CSRF is not an accepted authentication path. Production must
replace the local origin with the exact frontend origin(s); wildcard origins and
credentialed CORS are prohibited. A future cookie-based identity design needs a
separate CSRF review before implementation.

## Release blockers still open

- Run the PostgreSQL shared-limiter and full integration checks in the release
  environment; do not replace its fail-closed behavior with process memory.
- Select organizer identity/recovery and persist credential revocation/expiry.
- Replace the in-memory snapshot with a reconstruction-tested, transactionally
  persisted Engine state under an idempotency scheme (SEC-002/SEC-005).
- Implement authenticated, scoped realtime publication (SEC-003).
- Configure production CORS/session/CSRF and proxy identity policy (SEC-006).

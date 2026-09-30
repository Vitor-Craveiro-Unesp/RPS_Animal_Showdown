# Game Engine

Pure Python domain engine for official Rock/Paper/Scissors matches and single-elimination brackets. It has no HTTP, database, socket, browser, or third-party runtime dependency.

## Public boundary

- `ProbabilityDistribution` accepts integer percentages from 0 to 100 and requires an exact total of 100.
- `Strategy` requires the initial distribution plus all nine conditional distributions and copies them into an immutable snapshot.
- `start_match` and `play_round` implement RPS, hearts, ties without a rule cap, conditional strategies and elimination.
- `start_training` and `play_training_round` provide a structurally separate manual-vs-character simulation with the same rules.
- `start_tournament` and `play_active_match_round` implement random BYEs, one active battle at a time, advancement and champion selection.
- All state and transition records are frozen dataclasses. A transition returns a new state and never mutates its input.
- Errors have stable technical `code` values; UI translation belongs outside the Engine.

## Backend adapter boundary

The public API exposes strict conversion functions for the real backend adapter:

- `strategy_from_payload` accepts exactly the ten canonical condition names and validated integer distributions. Legacy `tied_on_*` aliases, missing conditions and extra fields are rejected.
- `strategy_to_payload` returns a fresh JSON-compatible object and never exposes the immutable mapping held by the Engine.
- `tournament_state_to_snapshot` emits the complete official bracket, immutable competitor strategy snapshots and round history under schema version `1` and kind `tournament_state`.
- `tournament_state_from_snapshot` reconstructs a new object graph and performs full history validation before returning trusted state.

The mandatory durable round-trip is `TournamentState` →
`tournament_state_to_snapshot()` → JSON/JSONB persistence → load →
`tournament_state_from_snapshot()` → `TournamentState`. Adapters must not use a
generic dataclass serializer: such output lacks the versioned envelope and does
not constitute a supported Engine snapshot. Match identifiers are also unique
across the complete bracket history, not merely within one round.

The persistence boundary requires canonical hyphenated UUID strings for tournament and player IDs. The public room code is not an Engine identity. Snapshot objects are strict: missing/extra fields, unsupported versions, unknown enum values, non-integer numeric fields, unknown players and altered official histories fail with stable `snapshot.*` or domain error codes.

Snapshots contain state only. RNG internals, access codes, credentials, idempotency keys, database versions and public realtime events remain Backend/Database responsibilities. The backend must store the snapshot and its concurrency envelope atomically; deserialization does not replace SEC-005 locking or idempotency.

Import from `rps_game_engine`, not from internal modules.

## Randomness and server authority

Every operation that can make a random decision requires a `RandomSource`; there is no implicit or client-provided default. Tests inject deterministic sources. Trusted backend code should create `SystemRandomSource`, which uses Python's `secrets.SystemRandom`, and must never expose its state or accept a draw, seed, BYE, move, result, heart count, winner, or bracket advancement from a client.

The Engine validates random draws as finite values in `[0, 1)`. A persistence adapter must call `validate_match_state` or `validate_tournament_state` after reconstructing a stored snapshot. Normal in-memory transitions use shallow invariant checks to avoid replaying an unbounded tie history on every round.

## Bracket rule used in V0.1

Entrant order is supplied by the trusted backend. In every odd round, the Engine uniformly selects one BYE recipient using the injected random source. Remaining entrants are paired in order. Match winners advance in match order and the BYE recipient occupies the last advancement slot. Completed rounds retain the losing match state for bracket rendering.

The Engine requires at least two unique competitors, matching the recorded product decision. Entrant seeding beyond random BYEs remains deferred.

## Tests

From the repository root:

```powershell
python -m unittest discover -s packages/game-engine/tests -t packages/game-engine -v
```

The suite covers strategy validation, canonical adapter conversion, UUID persistence boundaries, versioned snapshot round-trips, forged snapshot rejection, RNG validation, the complete RPS matrix, initial and conditional selection, wins, losses, hearts, 2,000 consecutive ties, elimination, manual training and isolation, BYEs in initial and later rounds, sequential match activation, bracket history and champion selection.

# Game Engine rules and implementation boundary

The product rules are canonical in [PROJECT_CORE.md](../PROJECT_CORE.md), especially sections 13–20 and 32–35. This document records the V0.1 implementation contract; it does not replace those rules.

## Implemented domain contract

The Engine lives in [`packages/game-engine`](../packages/game-engine/) and exports immutable Python contracts from `rps_game_engine`:

| Contract | Purpose |
| --- | --- |
| `ProbabilityDistribution` | Integer percentages for rock, paper and scissors; each value is `0..100` and the exact total is `100`. |
| `Strategy` | Immutable snapshot containing `initial` and every loss, win and tie condition for the three moves. Missing, extra or unvalidated distributions are rejected. |
| `Competitor` | Stable `player_id` plus the strategy snapshot. Display/profile data stays outside the Engine. |
| `MatchState` / `MatchRound` | Hearts, applied conditions, choices, outcome, history, winner and loser. |
| `TrainingState` / `TrainingRound` | Isolated manual-vs-character simulation using the character's official strategy rules. |
| `TournamentState` / `BracketRoundState` | Current round, archived completed rounds, BYE, sequential matches and champion. |
| `MatchTransition` / `TournamentTransition` | New state plus the round and advancement metadata needed by server orchestration. |

## Versioned persistence boundary

The Engine owns a strict, JSON-compatible adapter contract in `rps_game_engine.snapshots`:

- `strategy_from_payload` / `strategy_to_payload` convert backend DTO data without accepting aliases or sharing mutable mappings;
- `tournament_state_to_snapshot` emits schema version `1`, kind `tournament_state`, frozen competitor strategies, bracket state and complete round history;
- `tournament_state_from_snapshot` creates a new object graph and runs `validate_tournament_state` with full history verification before the state may enter a transition;
- tournament and player identities in snapshots are canonical hyphenated UUID strings. Access codes never occupy these fields;
- snapshot objects reject missing/extra fields, unknown enums, non-integer numeric fields, unknown player references and unsupported versions.

The snapshot does not contain RNG state, credentials, access codes, database versions, command keys or realtime events. Backend/Database must persist the snapshot together with the expected/resulting state version inside the SEC-005 transaction. A restored snapshot is trusted only after the conversion function returns successfully.

Training remains a separate domain type and is deliberately not accepted by the official tournament snapshot converter. Its identifier, storage scope, RNG and lifecycle must remain separate from official state.

Domain errors contain stable, non-localized codes. The frontend must translate public feedback and must not receive Python exception messages as an API contract.

## Match transitions

1. The first round uses `initial` for both players.
2. Each later round derives each player's condition independently from that player's previous result and the opponent's previous move.
3. Both moves are sampled from the applicable categorical distributions through the injected RNG.
4. RPS determines the result. A loss removes exactly one heart; a tie removes none.
5. Ties have no Game Engine cap. When a player reaches zero hearts, the match is completed and identifies one winner and one loser.
6. The input state remains unchanged; the function returns a new frozen state.

Deep validation replays stored round history and rejects inconsistent conditions, impossible zero-probability moves, outcomes, heart changes, rounds after elimination, and final results. Persistence adapters must perform this validation when rebuilding official state.

## Bracket transitions

V0.1 uses a round-based single-elimination bracket:

- trusted input order is preserved;
- an odd round receives exactly one uniformly random BYE;
- the organizer cannot select the BYE through the Engine API;
- non-BYE entrants are paired in order;
- exactly one match is marked active;
- only `play_active_match_round` progresses the official bracket;
- after a match ends, the next pending match becomes active;
- after the round ends, winners advance in match order and the BYE recipient is appended to the advancement list;
- completed rounds retain their final battles, including eliminated players;
- one remaining player becomes champion.

This algorithm supports non-power-of-two participant counts without constructing placeholder slots. It intentionally does not shuffle entrants or implement seeded ranking.

## Randomness boundary

Randomness is an explicit dependency. There is no default RNG in transition functions.

- Tests inject deterministic `RandomSource` implementations.
- Production backend code must instantiate `SystemRandomSource`, backed by `secrets.SystemRandom`, or an equivalently reviewed server-only implementation.
- Values must be finite and in `[0, 1)`.
- Client seeds, random draws, chosen moves, BYEs, results and RNG state are never authoritative.
- The current contract does not expose or retain RNG internals.

Random audit retention is still a Backend/Security decision. If replayable deterministic seeds are later introduced, they must remain server-only and require a new security review.

## Training isolation

Training uses `start_training` and `play_training_round`. The user supplies a manual `Move`; the character samples its initial or conditional strategy, and both sides use the same RPS, heart, tie and elimination rules. `TrainingState` is a different type from `MatchState` and `TournamentState`, and every transition returns a new object. It has no bracket, ranking, official winner or advancement field.

The integration must use a separate training identifier, persistence scope and RNG instance. A manual move is valid input only for `play_training_round`; official match and tournament transitions never accept client-selected moves.

## SEC-002 status

The Game Engine portion is implemented and tested: validated/frozen strategies, canonical `tied_with_*` conversion, canonical UUID persistence identities, server-injected randomness, RPS, hearts, ties, elimination, BYEs, sequential brackets, immutable transitions and versioned/reconstructible snapshots with deep validation.

SEC-002 remains **open as an overall deploy blocker** until the Backend:

- accepts only authenticated/authorized intentions rather than official outcomes;
- freezes and persists the strategy snapshot atomically when the tournament starts;
- invokes Engine transitions only on server-held state with server-held RNG;
- persists/reconstructs state through the Engine's versioned snapshot functions and treats conversion failures as rejected state, without rebuilding dataclasses directly;
- installs/imports `rps_game_engine` from its `pyproject.toml` in the backend runtime (the current backend container only copies the directory);
- isolates Training from official persistence and RNG;
- integrates transaction/idempotency controls from SEC-005;
- passes manipulated-payload tests and Security/QA review with no related high finding.

## Pending decisions and risks

- `PROJECT_CORE.md` requires at least 2 confirmed participants to start. The Engine enforces two competitors; Backend and persistence must enforce two confirmed participants before snapshot creation.
- Integer percentages are the V0.1 contract. Supporting fractional percentages would require a versioned contract and an exact numeric representation.
- Entrant seeding/shuffling beyond random BYEs is not specified and remains deferred.
- Unlimited ties are a product rule. Their history can grow without bound, so Backend persistence, pacing and operational protections need Security/QA review without silently changing the game rule.
- Snapshot schema `1` is now canonical inside the Python Engine. Cross-language promotion to `packages/shared-types` remains deferred until Backend integration proves the contract.
- CI currently compiles the package but does not execute its `unittest` suite; QA/DevOps must add the documented test command to the validation workflow.
- RNG audit retention and deterministic replay policy remain pending Security review.

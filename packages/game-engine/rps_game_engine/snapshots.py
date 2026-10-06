"""Strict, versioned JSON-compatible boundaries for persisted Engine state."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from .errors import EngineValidationError
from .models import (
    ALL_STRATEGY_CONDITIONS,
    BracketMatch,
    BracketMatchStatus,
    BracketRoundState,
    Competitor,
    MatchRound,
    MatchState,
    MatchStatus,
    Move,
    ProbabilityDistribution,
    RoundOutcome,
    Strategy,
    StrategyCondition,
    TournamentState,
    TournamentStatus,
)
from .tournament import validate_tournament_state


SNAPSHOT_SCHEMA_VERSION = 3
TOURNAMENT_SNAPSHOT_KIND = "tournament_state"


def canonical_uuid(value: object, *, field: str) -> str:
    """Return the canonical UUID string used by persistence and realtime."""

    if not isinstance(value, str):
        raise EngineValidationError(
            "snapshot.invalid_uuid",
            f"{field} must be a UUID string.",
        )
    try:
        return str(UUID(value))
    except (ValueError, AttributeError) as exc:
        raise EngineValidationError(
            "snapshot.invalid_uuid",
            f"{field} must be a UUID string.",
        ) from exc


def strategy_to_payload(strategy: Strategy) -> dict[str, dict[str, int]]:
    """Convert an immutable strategy into the canonical adapter payload."""

    if not isinstance(strategy, Strategy):
        raise EngineValidationError(
            "snapshot.invalid_strategy",
            "Expected a validated Strategy.",
        )
    return {
        condition.value: {
            "rock": distribution.rock,
            "paper": distribution.paper,
            "scissors": distribution.scissors,
        }
        for condition in StrategyCondition
        for distribution in (strategy.for_condition(condition),)
    }


def strategy_from_payload(payload: object) -> Strategy:
    """Build a frozen Strategy from a strict backend payload.

    Aliases are intentionally unsupported. In particular, ``tied_on_*`` is
    rejected instead of being silently converted to the canonical
    ``tied_with_*`` conditions.
    """

    source = _object(payload, "strategy")
    _fields(source, {condition.value for condition in ALL_STRATEGY_CONDITIONS}, "strategy")
    distributions: dict[StrategyCondition, ProbabilityDistribution] = {}
    for condition in StrategyCondition:
        distribution = _object(source[condition.value], f"strategy.{condition.value}")
        _fields(distribution, {"rock", "paper", "scissors"}, f"strategy.{condition.value}")
        distributions[condition] = ProbabilityDistribution(
            rock=distribution["rock"],  # type: ignore[arg-type]
            paper=distribution["paper"],  # type: ignore[arg-type]
            scissors=distribution["scissors"],  # type: ignore[arg-type]
        )
    return Strategy(distributions)


def tournament_state_to_snapshot(state: TournamentState) -> dict[str, object]:
    """Deep-validate and serialize an official tournament state."""

    validate_tournament_state(state)
    tournament_id = canonical_uuid(state.tournament_id, field="tournament_id")
    if tournament_id != state.tournament_id:
        raise EngineValidationError(
            "snapshot.noncanonical_uuid",
            "Tournament and player IDs must already use canonical UUID strings.",
        )
    competitors = tuple(_canonical_competitor(competitor) for competitor in state.competitors)
    if tuple(competitors) != state.competitors:
        raise EngineValidationError(
            "snapshot.noncanonical_uuid",
            "Tournament and player IDs must already use canonical UUID strings.",
        )
    first_round = state.completed_rounds[0] if state.completed_rounds else state.current_round
    legacy = first_round is not None and first_round.bye_player_id is not None
    def round_payload(round_: BracketRoundState) -> dict[str, object]:
        payload = _bracket_round_to_payload(round_)
        if legacy:
            payload.pop("waiting_player_id")
            payload.pop("second_chance_player_id")
        return payload
    result = {
        "schema_version": 3 if state.podium_enabled else 1 if legacy else 2,
        "kind": TOURNAMENT_SNAPSHOT_KIND,
        "tournament_id": tournament_id,
        "competitors": [_competitor_to_payload(competitor) for competitor in state.competitors],
        "hearts_per_match": state.hearts_per_match,
        "current_round": (
            round_payload(state.current_round)
            if state.current_round is not None
            else None
        ),
        "completed_rounds": [
            round_payload(round_) for round_ in state.completed_rounds
        ],
        "status": state.status.value,
        "champion_id": state.champion_id,
    }
    if state.podium_enabled:
        result.update(run_id=state.run_id, first_place=state.first_place,
            second_place=state.second_place, third_place=state.third_place)
    return result


def tournament_state_from_snapshot(snapshot: object) -> TournamentState:
    """Reconstruct and deep-validate a persisted official snapshot."""

    source = _object(snapshot, "snapshot")
    if "schema_version" in source and source["schema_version"] not in (1, 2, SNAPSHOT_SCHEMA_VERSION):
        raise EngineValidationError("snapshot.unsupported_version", "The snapshot schema version is not supported.")
    extras = {"run_id", "first_place", "second_place", "third_place"} if source.get("schema_version") == 3 else set()
    _fields(
        source,
        {
            "schema_version",
            "kind",
            "tournament_id",
            "competitors",
            "hearts_per_match",
            "current_round",
            "completed_rounds",
            "status",
            "champion_id",
        } | extras,
        "snapshot",
    )
    schema_version = _integer(source["schema_version"], "schema_version")
    if schema_version not in (1, 2, SNAPSHOT_SCHEMA_VERSION):
        raise EngineValidationError(
            "snapshot.unsupported_version",
            "The snapshot schema version is not supported.",
        )
    if source["kind"] != TOURNAMENT_SNAPSHOT_KIND:
        raise EngineValidationError(
            "snapshot.invalid_kind",
            "Expected an official tournament state snapshot.",
        )

    tournament_id = canonical_uuid(source["tournament_id"], field="tournament_id")
    if source["tournament_id"] != tournament_id:
        raise EngineValidationError(
            "snapshot.noncanonical_uuid",
            "tournament_id must use the canonical UUID representation.",
        )
    competitor_payloads = _array(source["competitors"], "competitors")
    competitors = tuple(_competitor_from_payload(item) for item in competitor_payloads)
    competitor_by_id = {competitor.player_id: competitor for competitor in competitors}
    if len(competitor_by_id) != len(competitors):
        raise EngineValidationError(
            "snapshot.duplicate_competitor",
            "Snapshot competitor IDs must be unique.",
        )

    current_payload = source["current_round"]
    current_round = (
        None
        if current_payload is None
        else _bracket_round_from_payload(current_payload, competitor_by_id, schema_version)
    )
    completed_rounds = tuple(
        _bracket_round_from_payload(item, competitor_by_id, schema_version)
        for item in _array(source["completed_rounds"], "completed_rounds")
    )
    state = TournamentState(
        tournament_id=tournament_id,
        run_id=_optional_uuid(source.get("run_id"), "run_id"),
        podium_enabled=schema_version == 3,
        competitors=competitors,
        hearts_per_match=_integer(source["hearts_per_match"], "hearts_per_match"),
        current_round=current_round,
        completed_rounds=completed_rounds,
        status=_enum(TournamentStatus, source["status"], "status"),
        champion_id=_optional_uuid(source["champion_id"], "champion_id"),
    )
    validate_tournament_state(state)
    first_round = completed_rounds[0] if completed_rounds else current_round
    if schema_version >= 2 and len(competitors) % 2 and first_round.waiting_player_id is None:
        raise EngineValidationError("snapshot.invalid_ruleset", "Version 2 odd tournaments require Second Chance.")
    if schema_version == 3 and any(source[k] != getattr(state, k) for k in ("first_place", "second_place", "third_place")):
        raise EngineValidationError("snapshot.invalid_podium", "Podium must agree with official matches.")
    return state


def _canonical_competitor(competitor: Competitor) -> Competitor:
    player_id = canonical_uuid(competitor.player_id, field="player_id")
    return Competitor(player_id=player_id, strategy=competitor.strategy)


def _competitor_to_payload(competitor: Competitor) -> dict[str, object]:
    return {
        "player_id": competitor.player_id,
        "strategy": strategy_to_payload(competitor.strategy),
    }


def _competitor_from_payload(payload: object) -> Competitor:
    source = _object(payload, "competitor")
    _fields(source, {"player_id", "strategy"}, "competitor")
    player_id = canonical_uuid(source["player_id"], field="player_id")
    if source["player_id"] != player_id:
        raise EngineValidationError(
            "snapshot.noncanonical_uuid",
            "player_id must use the canonical UUID representation.",
        )
    return Competitor(
        player_id=player_id,
        strategy=strategy_from_payload(source["strategy"]),
    )


def _match_round_to_payload(round_: MatchRound) -> dict[str, object]:
    return {
        "number": round_.number,
        "player_one_move": round_.player_one_move.value,
        "player_two_move": round_.player_two_move.value,
        "player_one_condition": round_.player_one_condition.value,
        "player_two_condition": round_.player_two_condition.value,
        "outcome": round_.outcome.value,
        "player_one_hearts": round_.player_one_hearts,
        "player_two_hearts": round_.player_two_hearts,
        "lost_heart_player_id": round_.lost_heart_player_id,
    }


def _match_round_from_payload(payload: object) -> MatchRound:
    source = _object(payload, "match_round")
    _fields(
        source,
        {
            "number",
            "player_one_move",
            "player_two_move",
            "player_one_condition",
            "player_two_condition",
            "outcome",
            "player_one_hearts",
            "player_two_hearts",
            "lost_heart_player_id",
        },
        "match_round",
    )
    return MatchRound(
        number=_integer(source["number"], "round.number"),
        player_one_move=_enum(Move, source["player_one_move"], "player_one_move"),
        player_two_move=_enum(Move, source["player_two_move"], "player_two_move"),
        player_one_condition=_enum(
            StrategyCondition,
            source["player_one_condition"],
            "player_one_condition",
        ),
        player_two_condition=_enum(
            StrategyCondition,
            source["player_two_condition"],
            "player_two_condition",
        ),
        outcome=_enum(RoundOutcome, source["outcome"], "outcome"),
        player_one_hearts=_integer(source["player_one_hearts"], "player_one_hearts"),
        player_two_hearts=_integer(source["player_two_hearts"], "player_two_hearts"),
        lost_heart_player_id=_optional_uuid(
            source["lost_heart_player_id"],
            "lost_heart_player_id",
        ),
    )


def _match_to_payload(state: MatchState) -> dict[str, object]:
    return {
        "match_id": state.match_id,
        "player_one_id": state.player_one.player_id,
        "player_two_id": state.player_two.player_id,
        "initial_hearts": state.initial_hearts,
        "player_one_hearts": state.player_one_hearts,
        "player_two_hearts": state.player_two_hearts,
        "rounds": [_match_round_to_payload(round_) for round_ in state.rounds],
        "status": state.status.value,
        "winner_id": state.winner_id,
        "loser_id": state.loser_id,
    }


def _match_from_payload(
    payload: object,
    competitor_by_id: dict[str, Competitor],
) -> MatchState:
    source = _object(payload, "match")
    _fields(
        source,
        {
            "match_id",
            "player_one_id",
            "player_two_id",
            "initial_hearts",
            "player_one_hearts",
            "player_two_hearts",
            "rounds",
            "status",
            "winner_id",
            "loser_id",
        },
        "match",
    )
    player_one_id = _known_player_id(source["player_one_id"], competitor_by_id, "player_one_id")
    player_two_id = _known_player_id(source["player_two_id"], competitor_by_id, "player_two_id")
    return MatchState(
        match_id=_text(source["match_id"], "match_id"),
        player_one=competitor_by_id[player_one_id],
        player_two=competitor_by_id[player_two_id],
        initial_hearts=_integer(source["initial_hearts"], "initial_hearts"),
        player_one_hearts=_integer(source["player_one_hearts"], "player_one_hearts"),
        player_two_hearts=_integer(source["player_two_hearts"], "player_two_hearts"),
        rounds=tuple(
            _match_round_from_payload(item)
            for item in _array(source["rounds"], "rounds")
        ),
        status=_enum(MatchStatus, source["status"], "status"),
        winner_id=_optional_uuid(source["winner_id"], "winner_id"),
        loser_id=_optional_uuid(source["loser_id"], "loser_id"),
    )


def _bracket_round_to_payload(round_: BracketRoundState) -> dict[str, object]:
    return {
        "waiting_player_id": round_.waiting_player_id,
        "second_chance_player_id": round_.second_chance_player_id,
        "number": round_.number,
        "entrant_ids": list(round_.entrant_ids),
        "bye_player_id": round_.bye_player_id,
        "matches": [
            {
                "match_id": match.match_id,
                "status": match.status.value,
                "battle": _match_to_payload(match.battle),
            }
            for match in round_.matches
        ],
    }


def _bracket_round_from_payload(
    payload: object,
    competitor_by_id: dict[str, Competitor],
    schema_version: int,
) -> BracketRoundState:
    source = _object(payload, "bracket_round")
    expected = {"number", "entrant_ids", "bye_player_id", "matches"}
    if schema_version >= 2:
        expected |= {"waiting_player_id", "second_chance_player_id"}
    _fields(source, expected, "bracket_round")
    matches: list[BracketMatch] = []
    for item in _array(source["matches"], "matches"):
        match_source = _object(item, "bracket_match")
        _fields(match_source, {"match_id", "status", "battle"}, "bracket_match")
        matches.append(
            BracketMatch(
                match_id=_text(match_source["match_id"], "match_id"),
                status=_enum(BracketMatchStatus, match_source["status"], "match_status"),
                battle=_match_from_payload(match_source["battle"], competitor_by_id),
            )
        )
    return BracketRoundState(
        waiting_player_id=_optional_uuid(source.get("waiting_player_id"), "waiting_player_id"),
        second_chance_player_id=_optional_uuid(source.get("second_chance_player_id"), "second_chance_player_id"),
        number=_integer(source["number"], "bracket_round.number"),
        entrant_ids=tuple(
            _known_player_id(item, competitor_by_id, "entrant_id")
            for item in _array(source["entrant_ids"], "entrant_ids")
        ),
        bye_player_id=(
            None
            if source["bye_player_id"] is None
            else _known_player_id(source["bye_player_id"], competitor_by_id, "bye_player_id")
        ),
        matches=tuple(matches),
    )


def _object(value: object, path: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise EngineValidationError(
            "snapshot.invalid_object",
            f"{path} must be an object with string keys.",
        )
    return value


def _array(value: object, path: str) -> list[object]:
    if not isinstance(value, list):
        raise EngineValidationError("snapshot.invalid_array", f"{path} must be an array.")
    return value


def _fields(source: dict[str, object], expected: set[str], path: str) -> None:
    actual = set(source)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise EngineValidationError(
            "snapshot.invalid_fields",
            f"{path} has invalid fields; missing={missing}, extra={extra}.",
        )


def _enum(enum_type: type[Any], value: object, field: str) -> Any:
    if not isinstance(value, str):
        raise EngineValidationError("snapshot.invalid_enum", f"{field} is invalid.")
    try:
        return enum_type(value)
    except ValueError as exc:
        raise EngineValidationError("snapshot.invalid_enum", f"{field} is invalid.") from exc


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EngineValidationError("snapshot.invalid_text", f"{field} must be non-empty text.")
    return value


def _integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise EngineValidationError("snapshot.invalid_integer", f"{field} must be an integer.")
    return value


def _optional_uuid(value: object, field: str) -> str | None:
    if value is None:
        return None
    canonical = canonical_uuid(value, field=field)
    if value != canonical:
        raise EngineValidationError(
            "snapshot.noncanonical_uuid",
            f"{field} must use the canonical UUID representation.",
        )
    return canonical


def _known_player_id(
    value: object,
    competitor_by_id: dict[str, Competitor],
    field: str,
) -> str:
    player_id = canonical_uuid(value, field=field)
    if value != player_id:
        raise EngineValidationError(
            "snapshot.noncanonical_uuid",
            f"{field} must use the canonical UUID representation.",
        )
    if player_id not in competitor_by_id:
        raise EngineValidationError(
            "snapshot.unknown_player",
            f"{field} must reference a snapshot competitor.",
        )
    return player_id

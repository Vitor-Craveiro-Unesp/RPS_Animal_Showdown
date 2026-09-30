"""Translation boundary between HTTP records and the pure Game Engine.

This module deliberately owns the conversion of validated server snapshots to
Engine values. It does not accept browser-supplied competitive state.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from typing import Protocol

from rps_game_engine import (
    Competitor,
    Move,
    ProbabilityDistribution,
    Strategy,
    StrategyCondition,
    SystemRandomSource,
    TournamentState,
    TrainingState,
    play_training_round,
    start_tournament,
    start_training,
    tournament_state_from_snapshot,
    tournament_state_to_snapshot,
)
from rps_game_engine.errors import EngineError


@dataclass(frozen=True)
class EnginePlayerSnapshot:
    player_id: str
    strategy: dict[str, object]


@dataclass(frozen=True)
class StartTournamentCommand:
    tournament_id: str
    hearts_required: int
    players: tuple[EnginePlayerSnapshot, ...]


@dataclass(frozen=True)
class TrainingChoiceCommand:
    training_id: str
    player_id: str
    hearts_required: int
    strategy: dict[str, object]
    move: str
    state: object | None


@dataclass(frozen=True)
class EngineStartResult:
    state_reference: str
    state: TournamentState
    snapshot: dict[str, object]


@dataclass(frozen=True)
class TrainingChoiceResult:
    training_id: str
    state: TrainingState
    snapshot: dict[str, object]


class EngineUnavailable(Exception):
    pass


class GameEngineGateway(Protocol):
    def start_tournament(self, command: StartTournamentCommand) -> EngineStartResult: ...

    def run_training_choice(self, command: TrainingChoiceCommand) -> TrainingChoiceResult: ...


class GameEngineAdapter:
    """Concrete in-process adapter for the development repository.

    A durable repository must persist ``snapshot`` and execute this adapter
    inside its transaction/idempotency boundary (SEC-005).
    """

    def start_tournament(self, command: StartTournamentCommand) -> EngineStartResult:
        try:
            competitors = tuple(
                Competitor(player_id=player.player_id, strategy=_strategy_from_snapshot(player.strategy))
                for player in command.players
            )
            state = start_tournament(
                tournament_id=command.tournament_id,
                competitors=competitors,
                hearts_per_match=command.hearts_required,
                random_source=SystemRandomSource(),
            )
        except (EngineError, EngineUnavailable) as error:
            raise EngineUnavailable("The official Game Engine rejected the server snapshot.") from error
        return EngineStartResult(
            state_reference=f"{command.tournament_id}:v1",
            state=state,
            # This is the only persistence boundary for official state.  The
            # Engine owns both the schema and semantic validation; backend
            # dataclass serialization is deliberately not an alternative.
            snapshot=tournament_state_to_snapshot(state),
        )

    def restore_tournament_state(self, snapshot: object) -> TournamentState:
        """Restore a persisted official snapshot through the Engine only."""
        try:
            return tournament_state_from_snapshot(snapshot)
        except EngineError as error:
            raise EngineUnavailable("The persisted official snapshot is invalid.") from error

    def run_training_choice(self, command: TrainingChoiceCommand) -> TrainingChoiceResult:
        try:
            if command.state is None:
                state = start_training(
                    training_id=command.training_id,
                    character=Competitor(
                        player_id=command.player_id,
                        strategy=_strategy_from_snapshot(command.strategy),
                    ),
                    initial_hearts=command.hearts_required,
                )
            elif isinstance(command.state, TrainingState):
                state = command.state
            else:
                raise EngineUnavailable("The saved training state has an invalid type.")
            transition = play_training_round(state, Move(command.move), SystemRandomSource())
        except (EngineError, EngineUnavailable, ValueError) as error:
            raise EngineUnavailable("The training Engine rejected the server snapshot.") from error
        return TrainingChoiceResult(
            training_id=command.training_id,
            state=transition.state,
            snapshot=_json_snapshot(transition.state),
        )


def _strategy_from_snapshot(snapshot: dict[str, object]) -> Strategy:
    """Construct the Engine immutable Strategy with canonical condition names."""
    distributions: dict[StrategyCondition, ProbabilityDistribution] = {}
    for condition in StrategyCondition:
        raw_distribution = snapshot.get(condition.value)
        if not isinstance(raw_distribution, dict):
            raise EngineUnavailable(f"Missing server strategy condition: {condition.value}.")
        try:
            distributions[condition] = ProbabilityDistribution(
                rock=raw_distribution["rock"],
                paper=raw_distribution["paper"],
                scissors=raw_distribution["scissors"],
            )
        except (KeyError, TypeError) as error:
            raise EngineUnavailable(f"Invalid server strategy condition: {condition.value}.") from error
    return Strategy(distributions=distributions)


def _json_snapshot(value: object) -> dict[str, object]:
    """Produce a JSON-compatible snapshot for the persistence/outbox boundary."""
    serialized = _serialize(value)
    if not isinstance(serialized, dict):
        raise EngineUnavailable("The Engine returned an invalid root state.")
    return serialized


def _serialize(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {field.name: _serialize(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key.value if isinstance(key, Enum) else key): _serialize(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_serialize(item) for item in value]
    return value

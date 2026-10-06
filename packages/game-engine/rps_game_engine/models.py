"""Immutable public contracts for the RPS domain."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping

from .errors import EngineValidationError


class Move(StrEnum):
    ROCK = "rock"
    PAPER = "paper"
    SCISSORS = "scissors"


class RoundOutcome(StrEnum):
    PLAYER_ONE_WIN = "player_one_win"
    PLAYER_TWO_WIN = "player_two_win"
    TIE = "tie"


class StrategyCondition(StrEnum):
    INITIAL = "initial"
    LOST_TO_ROCK = "lost_to_rock"
    LOST_TO_PAPER = "lost_to_paper"
    LOST_TO_SCISSORS = "lost_to_scissors"
    WON_AGAINST_ROCK = "won_against_rock"
    WON_AGAINST_PAPER = "won_against_paper"
    WON_AGAINST_SCISSORS = "won_against_scissors"
    TIED_WITH_ROCK = "tied_with_rock"
    TIED_WITH_PAPER = "tied_with_paper"
    TIED_WITH_SCISSORS = "tied_with_scissors"


ALL_STRATEGY_CONDITIONS = frozenset(StrategyCondition)


@dataclass(frozen=True, slots=True)
class ProbabilityDistribution:
    rock: int
    paper: int
    scissors: int

    def __post_init__(self) -> None:
        values = (self.rock, self.paper, self.scissors)
        if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
            raise EngineValidationError(
                "distribution.non_integer",
                "Probabilities must be integer percentages.",
            )
        if any(value < 0 or value > 100 for value in values):
            raise EngineValidationError(
                "distribution.out_of_range",
                "Each probability must be between 0 and 100.",
            )
        if sum(values) != 100:
            raise EngineValidationError(
                "distribution.total",
                "Probabilities must total exactly 100.",
            )


@dataclass(frozen=True, slots=True)
class Strategy:
    """A complete, immutable snapshot of initial and conditional behavior."""

    distributions: Mapping[StrategyCondition, ProbabilityDistribution]

    def __post_init__(self) -> None:
        try:
            source = dict(self.distributions)
        except (TypeError, ValueError) as exc:
            raise EngineValidationError(
                "strategy.invalid_mapping",
                "Strategy distributions must be a mapping.",
            ) from exc

        normalized: dict[StrategyCondition, ProbabilityDistribution] = {}
        invalid_keys: set[object] = set()
        for key, value in source.items():
            try:
                condition = StrategyCondition(key)
            except (TypeError, ValueError):
                invalid_keys.add(key)
                continue
            normalized[condition] = value
        missing_keys = ALL_STRATEGY_CONDITIONS - set(normalized)
        if invalid_keys:
            raise EngineValidationError(
                "strategy.unknown_condition",
                f"Unknown strategy conditions: {sorted(map(str, invalid_keys))}.",
            )
        if missing_keys:
            raise EngineValidationError(
                "strategy.missing_condition",
                f"Missing strategy conditions: {sorted(map(str, missing_keys))}.",
            )
        if any(not isinstance(value, ProbabilityDistribution) for value in normalized.values()):
            raise EngineValidationError(
                "strategy.invalid_distribution",
                "Every strategy condition must contain a ProbabilityDistribution.",
            )

        object.__setattr__(self, "distributions", MappingProxyType(normalized))

    def for_condition(self, condition: StrategyCondition) -> ProbabilityDistribution:
        return self.distributions[condition]


@dataclass(frozen=True, slots=True)
class Competitor:
    player_id: str
    strategy: Strategy

    def __post_init__(self) -> None:
        if not isinstance(self.player_id, str) or not self.player_id.strip():
            raise EngineValidationError(
                "competitor.invalid_id",
                "A competitor must have a non-empty player_id.",
            )
        if not isinstance(self.strategy, Strategy):
            raise EngineValidationError(
                "competitor.invalid_strategy",
                "A competitor must have a validated Strategy snapshot.",
            )


class MatchStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class MatchRound:
    number: int
    player_one_move: Move
    player_two_move: Move
    player_one_condition: StrategyCondition
    player_two_condition: StrategyCondition
    outcome: RoundOutcome
    player_one_hearts: int
    player_two_hearts: int
    lost_heart_player_id: str | None


@dataclass(frozen=True, slots=True)
class MatchState:
    match_id: str
    player_one: Competitor
    player_two: Competitor
    initial_hearts: int
    player_one_hearts: int
    player_two_hearts: int
    rounds: tuple[MatchRound, ...] = ()
    status: MatchStatus = MatchStatus.ACTIVE
    winner_id: str | None = None
    loser_id: str | None = None


@dataclass(frozen=True, slots=True)
class MatchTransition:
    state: MatchState
    round: MatchRound


class TrainingWinner(StrEnum):
    MANUAL_PLAYER = "manual_player"
    CHARACTER = "character"


@dataclass(frozen=True, slots=True)
class TrainingRound:
    number: int
    manual_move: Move
    character_move: Move
    character_condition: StrategyCondition
    outcome: RoundOutcome
    manual_hearts: int
    character_hearts: int


@dataclass(frozen=True, slots=True)
class TrainingState:
    training_id: str
    character: Competitor
    initial_hearts: int
    manual_hearts: int
    character_hearts: int
    rounds: tuple[TrainingRound, ...] = ()
    status: MatchStatus = MatchStatus.ACTIVE
    winner: TrainingWinner | None = None


@dataclass(frozen=True, slots=True)
class TrainingTransition:
    state: TrainingState
    round: TrainingRound


class BracketMatchStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class BracketMatch:
    match_id: str
    status: BracketMatchStatus
    battle: MatchState


@dataclass(frozen=True, slots=True)
class BracketRoundState:
    number: int
    entrant_ids: tuple[str, ...]
    bye_player_id: str | None
    matches: tuple[BracketMatch, ...]
    waiting_player_id: str | None = None
    second_chance_player_id: str | None = None


class TournamentStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class TournamentState:
    tournament_id: str
    competitors: tuple[Competitor, ...]
    hearts_per_match: int
    current_round: BracketRoundState | None
    completed_rounds: tuple[BracketRoundState, ...] = ()
    status: TournamentStatus = TournamentStatus.ACTIVE
    champion_id: str | None = None
    run_id: str | None = None
    podium_enabled: bool = False

    @property
    def first_place(self) -> str | None:
        return self.champion_id

    @property
    def second_place(self) -> str | None:
        return self.completed_rounds[-1].matches[-1].battle.loser_id if self.champion_id else None

    @property
    def third_place(self) -> str | None:
        if not self.podium_enabled:
            return None
        rounds = (*self.completed_rounds, *((self.current_round,) if self.current_round else ()))
        bronze = next((m for r in rounds for m in r.matches if m.match_id.endswith(':third-place')), None)
        if bronze:
            return bronze.battle.winner_id
        if not self.champion_id or len(self.competitors) == 2:
            return None
        if len(self.competitors) == 3:
            return next(p.player_id for p in self.competitors if p.player_id not in (self.first_place, self.second_place))
        # A three-entrant semifinal phase has one actual loser and one BYE.
        previous = self.completed_rounds[-2]
        return previous.matches[0].battle.loser_id if len(previous.entrant_ids) == 3 else None


@dataclass(frozen=True, slots=True)
class TournamentTransition:
    state: TournamentState
    match_round: MatchRound
    completed_match_id: str | None = None
    started_match_id: str | None = None
    assigned_bye_player_id: str | None = None
    champion_id: str | None = None

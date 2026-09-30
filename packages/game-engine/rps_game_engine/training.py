"""Isolated manual-vs-character training transitions."""

from __future__ import annotations

from dataclasses import replace

from .errors import EngineValidationError, InvalidTransitionError
from .match import resolve_round
from .models import (
    Competitor,
    MatchStatus,
    Move,
    RoundOutcome,
    StrategyCondition,
    TrainingRound,
    TrainingState,
    TrainingTransition,
    TrainingWinner,
)
from .randomness import RandomSource
from .strategy import sample_move


def start_training(
    training_id: str,
    character: Competitor,
    initial_hearts: int,
) -> TrainingState:
    if not isinstance(training_id, str) or not training_id.strip():
        raise EngineValidationError(
            "training.invalid_id",
            "A training session must have a non-empty training_id.",
        )
    if not isinstance(character, Competitor):
        raise EngineValidationError(
            "training.invalid_character",
            "Training requires a validated character Competitor.",
        )
    if isinstance(initial_hearts, bool) or not isinstance(initial_hearts, int) or initial_hearts <= 0:
        raise EngineValidationError(
            "training.invalid_initial_hearts",
            "initial_hearts must be a positive integer.",
        )
    return TrainingState(
        training_id=training_id,
        character=character,
        initial_hearts=initial_hearts,
        manual_hearts=initial_hearts,
        character_hearts=initial_hearts,
    )


def play_training_round(
    state: TrainingState,
    manual_move: Move,
    random_source: RandomSource,
) -> TrainingTransition:
    _validate_training_state(state)
    if state.status is MatchStatus.COMPLETED:
        raise InvalidTransitionError(
            "training.already_completed",
            "A completed training session cannot play another round.",
        )
    if not isinstance(manual_move, Move):
        raise EngineValidationError(
            "training.invalid_manual_move",
            "The manual training choice must be a Move value.",
        )

    previous_round = state.rounds[-1] if state.rounds else None
    condition = _character_condition(previous_round)
    character_move = sample_move(
        state.character.strategy.for_condition(condition),
        random_source,
    )
    outcome = resolve_round(manual_move, character_move)
    manual_hearts = state.manual_hearts
    character_hearts = state.character_hearts
    if outcome is RoundOutcome.PLAYER_ONE_WIN:
        character_hearts -= 1
    elif outcome is RoundOutcome.PLAYER_TWO_WIN:
        manual_hearts -= 1

    status = MatchStatus.ACTIVE
    winner: TrainingWinner | None = None
    if manual_hearts == 0:
        status = MatchStatus.COMPLETED
        winner = TrainingWinner.CHARACTER
    elif character_hearts == 0:
        status = MatchStatus.COMPLETED
        winner = TrainingWinner.MANUAL_PLAYER

    training_round = TrainingRound(
        number=len(state.rounds) + 1,
        manual_move=manual_move,
        character_move=character_move,
        character_condition=condition,
        outcome=outcome,
        manual_hearts=manual_hearts,
        character_hearts=character_hearts,
    )
    next_state = replace(
        state,
        manual_hearts=manual_hearts,
        character_hearts=character_hearts,
        rounds=(*state.rounds, training_round),
        status=status,
        winner=winner,
    )
    return TrainingTransition(next_state, training_round)


def _character_condition(previous_round: TrainingRound | None) -> StrategyCondition:
    if previous_round is None:
        return StrategyCondition.INITIAL
    if previous_round.outcome is RoundOutcome.TIE:
        return {
            Move.ROCK: StrategyCondition.TIED_WITH_ROCK,
            Move.PAPER: StrategyCondition.TIED_WITH_PAPER,
            Move.SCISSORS: StrategyCondition.TIED_WITH_SCISSORS,
        }[previous_round.manual_move]
    if previous_round.outcome is RoundOutcome.PLAYER_TWO_WIN:
        return {
            Move.ROCK: StrategyCondition.WON_AGAINST_ROCK,
            Move.PAPER: StrategyCondition.WON_AGAINST_PAPER,
            Move.SCISSORS: StrategyCondition.WON_AGAINST_SCISSORS,
        }[previous_round.manual_move]
    return {
        Move.ROCK: StrategyCondition.LOST_TO_ROCK,
        Move.PAPER: StrategyCondition.LOST_TO_PAPER,
        Move.SCISSORS: StrategyCondition.LOST_TO_SCISSORS,
    }[previous_round.manual_move]


def _validate_training_state(state: TrainingState) -> None:
    if not isinstance(state, TrainingState):
        raise EngineValidationError(
            "training.invalid_state",
            "Expected a TrainingState.",
        )
    for hearts in (state.manual_hearts, state.character_hearts):
        if (
            isinstance(hearts, bool)
            or not isinstance(hearts, int)
            or hearts < 0
            or hearts > state.initial_hearts
        ):
            raise EngineValidationError(
                "training.invalid_hearts",
                "Training hearts must remain between zero and initial_hearts.",
            )
    if state.status is MatchStatus.ACTIVE:
        if state.manual_hearts == 0 or state.character_hearts == 0 or state.winner is not None:
            raise EngineValidationError(
                "training.invalid_active_state",
                "An active training session cannot have an eliminated side or winner.",
            )
    elif state.status is MatchStatus.COMPLETED:
        expected_winner = (
            TrainingWinner.CHARACTER
            if state.manual_hearts == 0 < state.character_hearts
            else TrainingWinner.MANUAL_PLAYER
            if state.character_hearts == 0 < state.manual_hearts
            else None
        )
        if state.winner is not expected_winner:
            raise EngineValidationError(
                "training.invalid_result",
                "A completed training session must identify its surviving winner.",
            )
    else:
        raise EngineValidationError(
            "training.invalid_status",
            "Training status is invalid.",
        )

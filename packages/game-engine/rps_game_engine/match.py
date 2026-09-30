"""Pure Rock/Paper/Scissors match transitions."""

from __future__ import annotations

from dataclasses import replace

from .errors import EngineValidationError, InvalidTransitionError
from .models import (
    Competitor,
    MatchRound,
    MatchState,
    MatchStatus,
    MatchTransition,
    Move,
    ProbabilityDistribution,
    RoundOutcome,
)
from .randomness import RandomSource
from .strategy import condition_for_player, sample_move


def resolve_round(player_one_move: Move, player_two_move: Move) -> RoundOutcome:
    if not isinstance(player_one_move, Move) or not isinstance(player_two_move, Move):
        raise EngineValidationError(
            "round.invalid_move",
            "Both round choices must be Move values.",
        )
    if player_one_move is player_two_move:
        return RoundOutcome.TIE
    player_one_wins = (
        (player_one_move is Move.ROCK and player_two_move is Move.SCISSORS)
        or (player_one_move is Move.PAPER and player_two_move is Move.ROCK)
        or (player_one_move is Move.SCISSORS and player_two_move is Move.PAPER)
    )
    return RoundOutcome.PLAYER_ONE_WIN if player_one_wins else RoundOutcome.PLAYER_TWO_WIN


def start_match(
    match_id: str,
    player_one: Competitor,
    player_two: Competitor,
    initial_hearts: int,
) -> MatchState:
    if not isinstance(match_id, str) or not match_id.strip():
        raise EngineValidationError("match.invalid_id", "A match must have a non-empty match_id.")
    if not isinstance(player_one, Competitor) or not isinstance(player_two, Competitor):
        raise EngineValidationError(
            "match.invalid_competitor",
            "Both match participants must be validated Competitor values.",
        )
    if player_one.player_id == player_two.player_id:
        raise EngineValidationError(
            "match.duplicate_competitor",
            "A player cannot occupy both sides of a match.",
        )
    _validate_hearts(initial_hearts)
    return MatchState(
        match_id=match_id,
        player_one=player_one,
        player_two=player_two,
        initial_hearts=initial_hearts,
        player_one_hearts=initial_hearts,
        player_two_hearts=initial_hearts,
    )


def play_round(state: MatchState, random_source: RandomSource) -> MatchTransition:
    # States produced by this module are already deep-validated. Persistence
    # adapters must call validate_match_state() after reconstructing a snapshot.
    validate_match_state(state, verify_history=False)
    if state.status is MatchStatus.COMPLETED:
        raise InvalidTransitionError(
            "match.already_completed",
            "A completed match cannot play another round.",
        )

    previous_round = state.rounds[-1] if state.rounds else None
    condition_one = condition_for_player(previous_round, 1)
    condition_two = condition_for_player(previous_round, 2)
    move_one = sample_move(state.player_one.strategy.for_condition(condition_one), random_source)
    move_two = sample_move(state.player_two.strategy.for_condition(condition_two), random_source)
    outcome = resolve_round(move_one, move_two)

    hearts_one = state.player_one_hearts
    hearts_two = state.player_two_hearts
    lost_heart_player_id: str | None = None
    if outcome is RoundOutcome.PLAYER_ONE_WIN:
        hearts_two -= 1
        lost_heart_player_id = state.player_two.player_id
    elif outcome is RoundOutcome.PLAYER_TWO_WIN:
        hearts_one -= 1
        lost_heart_player_id = state.player_one.player_id

    winner_id: str | None = None
    loser_id: str | None = None
    status = MatchStatus.ACTIVE
    if hearts_one == 0:
        status = MatchStatus.COMPLETED
        winner_id = state.player_two.player_id
        loser_id = state.player_one.player_id
    elif hearts_two == 0:
        status = MatchStatus.COMPLETED
        winner_id = state.player_one.player_id
        loser_id = state.player_two.player_id

    match_round = MatchRound(
        number=len(state.rounds) + 1,
        player_one_move=move_one,
        player_two_move=move_two,
        player_one_condition=condition_one,
        player_two_condition=condition_two,
        outcome=outcome,
        player_one_hearts=hearts_one,
        player_two_hearts=hearts_two,
        lost_heart_player_id=lost_heart_player_id,
    )
    next_state = replace(
        state,
        player_one_hearts=hearts_one,
        player_two_hearts=hearts_two,
        rounds=(*state.rounds, match_round),
        status=status,
        winner_id=winner_id,
        loser_id=loser_id,
    )
    return MatchTransition(state=next_state, round=match_round)


def validate_match_state(state: MatchState, *, verify_history: bool = True) -> None:
    if not isinstance(state, MatchState):
        raise EngineValidationError("match.invalid_state", "Expected a MatchState.")
    _validate_hearts(state.initial_hearts)
    if state.player_one.player_id == state.player_two.player_id:
        raise EngineValidationError(
            "match.duplicate_competitor",
            "A player cannot occupy both sides of a match.",
        )
    for hearts in (state.player_one_hearts, state.player_two_hearts):
        if isinstance(hearts, bool) or not isinstance(hearts, int):
            raise EngineValidationError("match.invalid_hearts", "Heart counts must be integers.")
        if hearts < 0 or hearts > state.initial_hearts:
            raise EngineValidationError(
                "match.invalid_hearts",
                "Heart counts must remain between zero and initial_hearts.",
            )
    if not isinstance(state.status, MatchStatus):
        raise EngineValidationError("match.invalid_status", "Match status is invalid.")

    if not verify_history:
        _validate_current_result(state)
        return

    expected_hearts_one = state.initial_hearts
    expected_hearts_two = state.initial_hearts
    previous_round: MatchRound | None = None
    for index, round_ in enumerate(state.rounds, start=1):
        if not isinstance(round_, MatchRound) or round_.number != index:
            raise EngineValidationError(
                "match.invalid_round_sequence",
                "Round numbers must be contiguous and one-based.",
            )
        expected_condition_one = condition_for_player(previous_round, 1)
        expected_condition_two = condition_for_player(previous_round, 2)
        if (
            round_.player_one_condition is not expected_condition_one
            or round_.player_two_condition is not expected_condition_two
        ):
            raise EngineValidationError(
                "match.invalid_round_condition",
                "Round conditions must follow the previous result for each player.",
            )
        expected_outcome = resolve_round(round_.player_one_move, round_.player_two_move)
        if round_.outcome is not expected_outcome:
            raise EngineValidationError(
                "match.invalid_round_outcome",
                "Stored round outcome does not match the RPS choices.",
            )
        if _probability_for_move(
            state.player_one.strategy.for_condition(expected_condition_one),
            round_.player_one_move,
        ) == 0 or _probability_for_move(
            state.player_two.strategy.for_condition(expected_condition_two),
            round_.player_two_move,
        ) == 0:
            raise EngineValidationError(
                "match.impossible_strategy_move",
                "A stored move has zero probability in its applied strategy condition.",
            )

        expected_lost_player_id: str | None = None
        if expected_outcome is RoundOutcome.PLAYER_ONE_WIN:
            expected_hearts_two -= 1
            expected_lost_player_id = state.player_two.player_id
        elif expected_outcome is RoundOutcome.PLAYER_TWO_WIN:
            expected_hearts_one -= 1
            expected_lost_player_id = state.player_one.player_id
        if expected_hearts_one < 0 or expected_hearts_two < 0:
            raise EngineValidationError(
                "match.round_after_elimination",
                "A match cannot contain rounds after a player is eliminated.",
            )
        if (
            round_.player_one_hearts != expected_hearts_one
            or round_.player_two_hearts != expected_hearts_two
            or round_.lost_heart_player_id != expected_lost_player_id
        ):
            raise EngineValidationError(
                "match.invalid_round_hearts",
                "Stored round hearts do not match the round outcome.",
            )
        if (expected_hearts_one == 0 or expected_hearts_two == 0) and index != len(state.rounds):
            raise EngineValidationError(
                "match.round_after_elimination",
                "A match cannot contain rounds after a player is eliminated.",
            )
        previous_round = round_

    if (
        state.player_one_hearts != expected_hearts_one
        or state.player_two_hearts != expected_hearts_two
    ):
        raise EngineValidationError(
            "match.state_hearts_mismatch",
            "Current hearts must equal the result of the stored round history.",
        )

    _validate_current_result(state)


def _validate_current_result(state: MatchState) -> None:
    if state.status is MatchStatus.ACTIVE:
        if state.player_one_hearts == 0 or state.player_two_hearts == 0:
            raise EngineValidationError(
                "match.active_eliminated_player",
                "An active match cannot contain an eliminated player.",
            )
        if state.winner_id is not None or state.loser_id is not None:
            raise EngineValidationError(
                "match.active_with_result",
                "An active match cannot have a winner or loser.",
            )
        return

    if state.player_one_hearts == 0 and state.player_two_hearts > 0:
        expected_winner = state.player_two.player_id
        expected_loser = state.player_one.player_id
    elif state.player_two_hearts == 0 and state.player_one_hearts > 0:
        expected_winner = state.player_one.player_id
        expected_loser = state.player_two.player_id
    else:
        expected_winner = None
        expected_loser = None
    if state.winner_id != expected_winner or state.loser_id != expected_loser:
        raise EngineValidationError(
            "match.invalid_result",
            "A completed match must identify its surviving winner and eliminated loser.",
        )


def _validate_hearts(initial_hearts: int) -> None:
    if isinstance(initial_hearts, bool) or not isinstance(initial_hearts, int) or initial_hearts <= 0:
        raise EngineValidationError(
            "match.invalid_initial_hearts",
            "initial_hearts must be a positive integer.",
        )


def _probability_for_move(distribution: ProbabilityDistribution, move: Move) -> int:
    if move is Move.ROCK:
        return distribution.rock
    if move is Move.PAPER:
        return distribution.paper
    return distribution.scissors

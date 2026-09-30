"""Probability sampling and conditional-strategy selection."""

from __future__ import annotations

from .models import (
    MatchRound,
    Move,
    ProbabilityDistribution,
    RoundOutcome,
    StrategyCondition,
)
from .randomness import RandomSource, draw_unit_interval


def sample_move(
    distribution: ProbabilityDistribution,
    random_source: RandomSource,
) -> Move:
    draw = draw_unit_interval(random_source) * 100
    if draw < distribution.rock:
        return Move.ROCK
    if draw < distribution.rock + distribution.paper:
        return Move.PAPER
    return Move.SCISSORS


def condition_for_player(previous_round: MatchRound | None, player_number: int) -> StrategyCondition:
    if player_number not in (1, 2):
        raise ValueError("player_number must be 1 or 2")
    if previous_round is None:
        return StrategyCondition.INITIAL

    own_move = previous_round.player_one_move if player_number == 1 else previous_round.player_two_move
    opponent_move = previous_round.player_two_move if player_number == 1 else previous_round.player_one_move

    if previous_round.outcome is RoundOutcome.TIE:
        return _tie_condition(own_move)

    player_won = (
        previous_round.outcome is RoundOutcome.PLAYER_ONE_WIN and player_number == 1
    ) or (
        previous_round.outcome is RoundOutcome.PLAYER_TWO_WIN and player_number == 2
    )
    return _win_condition(opponent_move) if player_won else _loss_condition(opponent_move)


def _loss_condition(move: Move) -> StrategyCondition:
    return {
        Move.ROCK: StrategyCondition.LOST_TO_ROCK,
        Move.PAPER: StrategyCondition.LOST_TO_PAPER,
        Move.SCISSORS: StrategyCondition.LOST_TO_SCISSORS,
    }[move]


def _win_condition(move: Move) -> StrategyCondition:
    return {
        Move.ROCK: StrategyCondition.WON_AGAINST_ROCK,
        Move.PAPER: StrategyCondition.WON_AGAINST_PAPER,
        Move.SCISSORS: StrategyCondition.WON_AGAINST_SCISSORS,
    }[move]


def _tie_condition(move: Move) -> StrategyCondition:
    return {
        Move.ROCK: StrategyCondition.TIED_WITH_ROCK,
        Move.PAPER: StrategyCondition.TIED_WITH_PAPER,
        Move.SCISSORS: StrategyCondition.TIED_WITH_SCISSORS,
    }[move]

from __future__ import annotations

from collections.abc import Iterable

from rps_game_engine import (
    ALL_STRATEGY_CONDITIONS,
    Competitor,
    Move,
    ProbabilityDistribution,
    Strategy,
    StrategyCondition,
)


class SequenceRandom:
    def __init__(self, values: Iterable[float]) -> None:
        self._values = iter(values)

    def random(self) -> float:
        try:
            return next(self._values)
        except StopIteration as exc:
            raise AssertionError("The deterministic random sequence was exhausted.") from exc


class ConstantRandom:
    def __init__(self, value: float = 0.0) -> None:
        self.value = value

    def random(self) -> float:
        return self.value


def distribution_for(move: Move) -> ProbabilityDistribution:
    if move is Move.ROCK:
        return ProbabilityDistribution(rock=100, paper=0, scissors=0)
    if move is Move.PAPER:
        return ProbabilityDistribution(rock=0, paper=100, scissors=0)
    return ProbabilityDistribution(rock=0, paper=0, scissors=100)


def strategy_for(
    default_move: Move,
    overrides: dict[StrategyCondition, Move] | None = None,
) -> Strategy:
    moves = {condition: default_move for condition in ALL_STRATEGY_CONDITIONS}
    moves.update(overrides or {})
    return Strategy(
        {condition: distribution_for(move) for condition, move in moves.items()}
    )


def competitor(
    player_id: str,
    move: Move,
    overrides: dict[StrategyCondition, Move] | None = None,
) -> Competitor:
    return Competitor(player_id, strategy_for(move, overrides))

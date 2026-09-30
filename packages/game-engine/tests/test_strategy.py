from __future__ import annotations

import unittest

from rps_game_engine import (
    ALL_STRATEGY_CONDITIONS,
    EngineValidationError,
    Move,
    ProbabilityDistribution,
    Strategy,
    StrategyCondition,
    sample_move,
)

from .helpers import SequenceRandom, distribution_for


class ProbabilityDistributionTests(unittest.TestCase):
    def test_accepts_exact_integer_percentages_totaling_one_hundred(self) -> None:
        distribution = ProbabilityDistribution(rock=50, paper=20, scissors=30)
        self.assertEqual((distribution.rock, distribution.paper, distribution.scissors), (50, 20, 30))

    def test_rejects_non_integer_negative_out_of_range_and_wrong_total(self) -> None:
        invalid = (
            ((50.0, 20, 30), "distribution.non_integer"),
            ((True, 0, 99), "distribution.non_integer"),
            ((-1, 51, 50), "distribution.out_of_range"),
            ((101, 0, -1), "distribution.out_of_range"),
            ((40, 20, 30), "distribution.total"),
        )
        for values, expected_code in invalid:
            with self.subTest(values=values), self.assertRaises(EngineValidationError) as raised:
                ProbabilityDistribution(*values)
            self.assertEqual(raised.exception.code, expected_code)

    def test_sampling_uses_half_open_cumulative_intervals(self) -> None:
        distribution = ProbabilityDistribution(rock=50, paper=20, scissors=30)
        source = SequenceRandom((0.0, 0.4999, 0.5, 0.6999, 0.7, 0.999999))
        actual = tuple(sample_move(distribution, source) for _ in range(6))
        self.assertEqual(
            actual,
            (Move.ROCK, Move.ROCK, Move.PAPER, Move.PAPER, Move.SCISSORS, Move.SCISSORS),
        )

    def test_sampling_rejects_untrusted_random_source_values(self) -> None:
        distribution = ProbabilityDistribution(rock=100, paper=0, scissors=0)
        for value in (-0.01, 1.0, float("nan"), float("inf"), True, "0.5"):
            with self.subTest(value=value), self.assertRaises(EngineValidationError):
                sample_move(distribution, SequenceRandom((value,)))


class StrategyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.distribution = distribution_for(Move.ROCK)
        self.complete = {
            condition: self.distribution for condition in ALL_STRATEGY_CONDITIONS
        }

    def test_requires_initial_and_all_nine_conditional_distributions(self) -> None:
        for missing in StrategyCondition:
            incomplete = dict(self.complete)
            incomplete.pop(missing)
            with self.subTest(missing=missing), self.assertRaises(EngineValidationError) as raised:
                Strategy(incomplete)
            self.assertEqual(raised.exception.code, "strategy.missing_condition")

    def test_rejects_unknown_condition_and_unvalidated_distribution(self) -> None:
        with self.assertRaises(EngineValidationError) as unknown:
            Strategy({**self.complete, "client_result": self.distribution})  # type: ignore[dict-item]
        self.assertEqual(unknown.exception.code, "strategy.unknown_condition")

        invalid_value = dict(self.complete)
        invalid_value[StrategyCondition.INITIAL] = {"rock": 100}  # type: ignore[assignment]
        with self.assertRaises(EngineValidationError) as invalid:
            Strategy(invalid_value)
        self.assertEqual(invalid.exception.code, "strategy.invalid_distribution")

    def test_copies_and_freezes_the_official_snapshot(self) -> None:
        source = dict(self.complete)
        strategy = Strategy(source)
        source[StrategyCondition.INITIAL] = distribution_for(Move.PAPER)

        self.assertIs(strategy.for_condition(StrategyCondition.INITIAL), self.distribution)
        with self.assertRaises(TypeError):
            strategy.distributions[StrategyCondition.INITIAL] = distribution_for(Move.SCISSORS)  # type: ignore[index]


if __name__ == "__main__":
    unittest.main()

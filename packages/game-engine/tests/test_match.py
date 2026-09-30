from __future__ import annotations

import unittest
from dataclasses import replace

from rps_game_engine import (
    EngineValidationError,
    InvalidTransitionError,
    MatchRound,
    MatchStatus,
    Move,
    RoundOutcome,
    StrategyCondition,
    condition_for_player,
    play_round,
    resolve_round,
    start_match,
    validate_match_state,
)

from .helpers import ConstantRandom, competitor


class RpsRuleTests(unittest.TestCase):
    def test_resolves_complete_rps_matrix(self) -> None:
        expected = {
            (Move.ROCK, Move.ROCK): RoundOutcome.TIE,
            (Move.ROCK, Move.PAPER): RoundOutcome.PLAYER_TWO_WIN,
            (Move.ROCK, Move.SCISSORS): RoundOutcome.PLAYER_ONE_WIN,
            (Move.PAPER, Move.ROCK): RoundOutcome.PLAYER_ONE_WIN,
            (Move.PAPER, Move.PAPER): RoundOutcome.TIE,
            (Move.PAPER, Move.SCISSORS): RoundOutcome.PLAYER_TWO_WIN,
            (Move.SCISSORS, Move.ROCK): RoundOutcome.PLAYER_TWO_WIN,
            (Move.SCISSORS, Move.PAPER): RoundOutcome.PLAYER_ONE_WIN,
            (Move.SCISSORS, Move.SCISSORS): RoundOutcome.TIE,
        }
        for moves, outcome in expected.items():
            with self.subTest(moves=moves):
                self.assertIs(resolve_round(*moves), outcome)

    def test_maps_every_previous_result_to_each_players_condition(self) -> None:
        win_expected = {
            Move.ROCK: StrategyCondition.WON_AGAINST_ROCK,
            Move.PAPER: StrategyCondition.WON_AGAINST_PAPER,
            Move.SCISSORS: StrategyCondition.WON_AGAINST_SCISSORS,
        }
        loss_expected = {
            Move.ROCK: StrategyCondition.LOST_TO_ROCK,
            Move.PAPER: StrategyCondition.LOST_TO_PAPER,
            Move.SCISSORS: StrategyCondition.LOST_TO_SCISSORS,
        }
        tie_expected = {
            Move.ROCK: StrategyCondition.TIED_WITH_ROCK,
            Move.PAPER: StrategyCondition.TIED_WITH_PAPER,
            Move.SCISSORS: StrategyCondition.TIED_WITH_SCISSORS,
        }
        self.assertIs(condition_for_player(None, 1), StrategyCondition.INITIAL)
        for opponent_move in Move:
            player_one_move = {
                Move.ROCK: Move.PAPER,
                Move.PAPER: Move.SCISSORS,
                Move.SCISSORS: Move.ROCK,
            }[opponent_move]
            winning_round = _round(player_one_move, opponent_move, RoundOutcome.PLAYER_ONE_WIN)
            self.assertIs(condition_for_player(winning_round, 1), win_expected[opponent_move])
            self.assertIs(condition_for_player(winning_round, 2), loss_expected[player_one_move])

            tied_round = _round(opponent_move, opponent_move, RoundOutcome.TIE)
            self.assertIs(condition_for_player(tied_round, 1), tie_expected[opponent_move])
            self.assertIs(condition_for_player(tied_round, 2), tie_expected[opponent_move])


class MatchTransitionTests(unittest.TestCase):
    def test_win_removes_one_heart_and_does_not_mutate_previous_state(self) -> None:
        original = start_match(
            "m1",
            competitor("a", Move.ROCK),
            competitor("b", Move.SCISSORS),
            2,
        )
        transition = play_round(original, ConstantRandom())

        self.assertEqual((original.player_one_hearts, original.player_two_hearts), (2, 2))
        self.assertEqual((transition.state.player_one_hearts, transition.state.player_two_hearts), (2, 1))
        self.assertEqual(transition.round.lost_heart_player_id, "b")
        self.assertIs(transition.state.status, MatchStatus.ACTIVE)

    def test_loss_and_elimination_produce_an_explicit_winner(self) -> None:
        state = start_match(
            "m2",
            competitor("a", Move.ROCK),
            competitor("b", Move.PAPER),
            2,
        )
        state = play_round(state, ConstantRandom()).state
        transition = play_round(state, ConstantRandom())

        self.assertEqual(transition.state.player_one_hearts, 0)
        self.assertIs(transition.state.status, MatchStatus.COMPLETED)
        self.assertEqual(transition.state.winner_id, "b")
        self.assertEqual(transition.state.loser_id, "a")
        with self.assertRaises(InvalidTransitionError):
            play_round(transition.state, ConstantRandom())

    def test_tie_removes_no_heart_and_has_no_engine_cap(self) -> None:
        state = start_match(
            "ties",
            competitor("a", Move.ROCK),
            competitor("b", Move.ROCK),
            1,
        )
        for _ in range(2_000):
            state = play_round(state, ConstantRandom()).state

        self.assertEqual((state.player_one_hearts, state.player_two_hearts), (1, 1))
        self.assertEqual(len(state.rounds), 2_000)
        self.assertIs(state.status, MatchStatus.ACTIVE)
        self.assertTrue(all(round_.outcome is RoundOutcome.TIE for round_ in state.rounds))

    def test_next_round_uses_each_players_own_conditional_strategy(self) -> None:
        player_one = competitor(
            "a",
            Move.ROCK,
            {StrategyCondition.WON_AGAINST_SCISSORS: Move.PAPER},
        )
        player_two = competitor(
            "b",
            Move.SCISSORS,
            {StrategyCondition.LOST_TO_ROCK: Move.ROCK},
        )
        state = start_match("conditional", player_one, player_two, 2)
        first = play_round(state, ConstantRandom()).state
        second = play_round(first, ConstantRandom())

        self.assertIs(second.round.player_one_condition, StrategyCondition.WON_AGAINST_SCISSORS)
        self.assertIs(second.round.player_two_condition, StrategyCondition.LOST_TO_ROCK)
        self.assertEqual((second.round.player_one_move, second.round.player_two_move), (Move.PAPER, Move.ROCK))
        self.assertEqual(second.state.winner_id, "a")

    def test_training_copy_is_isolated_by_immutable_transitions(self) -> None:
        official = start_match(
            "official",
            competitor("a", Move.ROCK),
            competitor("b", Move.SCISSORS),
            1,
        )
        training = play_round(official, ConstantRandom()).state

        self.assertIs(official.status, MatchStatus.ACTIVE)
        self.assertEqual(official.rounds, ())
        self.assertIs(training.status, MatchStatus.COMPLETED)

    def test_deep_validation_rejects_manipulated_official_hearts(self) -> None:
        original = start_match(
            "official",
            competitor("a", Move.ROCK),
            competitor("b", Move.SCISSORS),
            2,
        )
        legitimate = play_round(original, ConstantRandom()).state
        manipulated = replace(legitimate, player_two_hearts=2)

        with self.assertRaisesRegex(EngineValidationError, "round history"):
            validate_match_state(manipulated)


def _round(player_one_move: Move, player_two_move: Move, outcome: RoundOutcome) -> MatchRound:
    return MatchRound(
        number=1,
        player_one_move=player_one_move,
        player_two_move=player_two_move,
        player_one_condition=StrategyCondition.INITIAL,
        player_two_condition=StrategyCondition.INITIAL,
        outcome=outcome,
        player_one_hearts=1,
        player_two_hearts=1,
        lost_heart_player_id=None,
    )


if __name__ == "__main__":
    unittest.main()

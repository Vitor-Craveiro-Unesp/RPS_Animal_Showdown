from __future__ import annotations

import unittest

from rps_game_engine import (
    InvalidTransitionError,
    MatchStatus,
    Move,
    StrategyCondition,
    TrainingWinner,
    play_training_round,
    start_training,
)

from .helpers import ConstantRandom, competitor


class TrainingTests(unittest.TestCase):
    def test_manual_choice_uses_same_hearts_tie_and_elimination_rules(self) -> None:
        official_character = competitor("character", Move.ROCK)
        state = start_training("training", official_character, 2)

        tie = play_training_round(state, Move.ROCK, ConstantRandom())
        self.assertEqual((tie.state.manual_hearts, tie.state.character_hearts), (2, 2))
        self.assertIs(tie.state.status, MatchStatus.ACTIVE)

        loss = play_training_round(tie.state, Move.SCISSORS, ConstantRandom())
        completed = play_training_round(loss.state, Move.SCISSORS, ConstantRandom())
        self.assertEqual(completed.state.manual_hearts, 0)
        self.assertIs(completed.state.winner, TrainingWinner.CHARACTER)
        with self.assertRaises(InvalidTransitionError):
            play_training_round(completed.state, Move.PAPER, ConstantRandom())

    def test_character_uses_its_own_conditional_strategy(self) -> None:
        character = competitor(
            "character",
            Move.ROCK,
            {StrategyCondition.LOST_TO_PAPER: Move.SCISSORS},
        )
        state = start_training("training", character, 2)
        manual_win = play_training_round(state, Move.PAPER, ConstantRandom())
        character_win = play_training_round(manual_win.state, Move.PAPER, ConstantRandom())

        self.assertIs(
            character_win.round.character_condition,
            StrategyCondition.LOST_TO_PAPER,
        )
        self.assertIs(character_win.round.character_move, Move.SCISSORS)
        self.assertEqual(
            (character_win.state.manual_hearts, character_win.state.character_hearts),
            (1, 1),
        )

    def test_training_state_cannot_mutate_official_competitor_or_state(self) -> None:
        character = competitor("character", Move.ROCK)
        original = start_training("training", character, 1)
        completed = play_training_round(original, Move.PAPER, ConstantRandom()).state

        self.assertEqual(original.rounds, ())
        self.assertEqual(original.character_hearts, 1)
        self.assertEqual(completed.character_hearts, 0)
        self.assertIs(completed.character, character)


if __name__ == "__main__":
    unittest.main()

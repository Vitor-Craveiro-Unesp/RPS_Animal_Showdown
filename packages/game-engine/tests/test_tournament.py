from __future__ import annotations

import unittest
from dataclasses import replace

from rps_game_engine import (
    BracketMatchStatus,
    EngineValidationError,
    InvalidTransitionError,
    Move,
    TournamentStatus,
    play_active_match_round,
    start_tournament,
    validate_tournament_state,
)

from .helpers import ConstantRandom, SequenceRandom, competitor


class TournamentTests(unittest.TestCase):
    def test_odd_round_assigns_exactly_one_random_bye(self) -> None:
        competitors = (
            competitor("a", Move.ROCK),
            competitor("b", Move.SCISSORS),
            competitor("c", Move.SCISSORS),
        )
        state = start_tournament("t1", competitors, 1, SequenceRandom((0.5,)))

        self.assertEqual(state.current_round.bye_player_id, "b")  # type: ignore[union-attr]
        self.assertEqual(len(state.current_round.matches), 1)  # type: ignore[union-attr]
        battle = state.current_round.matches[0].battle  # type: ignore[union-attr]
        self.assertEqual((battle.player_one.player_id, battle.player_two.player_id), ("a", "c"))

    def test_bye_player_and_match_winner_advance_to_a_champion(self) -> None:
        competitors = (
            competitor("a", Move.ROCK),
            competitor("b", Move.SCISSORS),
            competitor("c", Move.SCISSORS),
        )
        random_source = SequenceRandom((0.5, 0.0, 0.0, 0.0, 0.0))
        state = start_tournament("t2", competitors, 1, random_source)

        semifinal = play_active_match_round(state, random_source)
        self.assertEqual(semifinal.completed_match_id, "t2:r1:m1")
        self.assertEqual(semifinal.started_match_id, "t2:r2:m1")
        self.assertEqual(semifinal.state.current_round.entrant_ids, ("a", "b"))  # type: ignore[union-attr]

        final = play_active_match_round(semifinal.state, random_source)
        self.assertIs(final.state.status, TournamentStatus.COMPLETED)
        self.assertEqual(final.champion_id, "a")
        self.assertEqual(final.state.champion_id, "a")
        self.assertEqual(len(final.state.completed_rounds), 2)
        with self.assertRaises(InvalidTransitionError):
            play_active_match_round(final.state, ConstantRandom())

    def test_only_one_match_is_active_and_losers_remain_in_completed_rounds(self) -> None:
        competitors = (
            competitor("a", Move.ROCK),
            competitor("b", Move.SCISSORS),
            competitor("c", Move.PAPER),
            competitor("d", Move.ROCK),
        )
        state = start_tournament("t3", competitors, 1, ConstantRandom())
        statuses = tuple(match.status for match in state.current_round.matches)  # type: ignore[union-attr]
        self.assertEqual(statuses, (BracketMatchStatus.ACTIVE, BracketMatchStatus.PENDING))

        first = play_active_match_round(state, ConstantRandom())
        statuses = tuple(match.status for match in first.state.current_round.matches)  # type: ignore[union-attr]
        self.assertEqual(statuses, (BracketMatchStatus.COMPLETED, BracketMatchStatus.ACTIVE))
        self.assertEqual(first.state.current_round.matches[0].battle.loser_id, "b")  # type: ignore[union-attr]

        second = play_active_match_round(first.state, ConstantRandom())
        self.assertEqual(len(second.state.completed_rounds), 1)
        completed_losers = tuple(
            match.battle.loser_id for match in second.state.completed_rounds[0].matches
        )
        self.assertEqual(completed_losers, ("b", "d"))
        self.assertEqual(second.state.current_round.entrant_ids, ("a", "c"))  # type: ignore[union-attr]

        final = play_active_match_round(second.state, ConstantRandom())
        self.assertEqual(final.state.champion_id, "c")

    def test_rejects_duplicate_or_insufficient_competitors(self) -> None:
        player = competitor("a", Move.ROCK)
        with self.assertRaises(EngineValidationError) as insufficient:
            start_tournament("t", (player,), 1, ConstantRandom())
        self.assertEqual(insufficient.exception.code, "tournament.not_enough_competitors")

        with self.assertRaises(EngineValidationError) as duplicate:
            start_tournament("t", (player, player), 1, ConstantRandom())
        self.assertEqual(duplicate.exception.code, "tournament.duplicate_competitor")

    def test_assigns_a_new_random_bye_when_a_later_round_is_odd(self) -> None:
        competitors = (
            competitor("a", Move.ROCK),
            competitor("b", Move.SCISSORS),
            competitor("c", Move.PAPER),
            competitor("d", Move.ROCK),
            competitor("e", Move.SCISSORS),
            competitor("f", Move.PAPER),
        )
        random_source = SequenceRandom((*([0.0] * 6), 0.5, *([0.0] * 4)))
        state = start_tournament("t4", competitors, 1, random_source)

        first = play_active_match_round(state, random_source)
        second = play_active_match_round(first.state, random_source)
        third = play_active_match_round(second.state, random_source)

        self.assertEqual(third.assigned_bye_player_id, "c")
        self.assertEqual(third.state.current_round.entrant_ids, ("a", "c", "e"))  # type: ignore[union-attr]
        semifinal = play_active_match_round(third.state, random_source)
        final = play_active_match_round(semifinal.state, random_source)
        self.assertEqual(final.state.champion_id, "c")

    def test_rejects_a_bracket_with_a_replaced_strategy_snapshot(self) -> None:
        competitors = (
            competitor("a", Move.ROCK),
            competitor("b", Move.SCISSORS),
        )
        state = start_tournament("t5", competitors, 1, ConstantRandom())
        current_round = state.current_round
        self.assertIsNotNone(current_round)
        assert current_round is not None
        bracket_match = current_round.matches[0]
        replaced_player = competitor("a", Move.PAPER)
        forged_battle = replace(bracket_match.battle, player_one=replaced_player)
        forged_match = replace(bracket_match, battle=forged_battle)
        forged_state = replace(
            state,
            current_round=replace(current_round, matches=(forged_match,)),
        )

        with self.assertRaises(EngineValidationError) as raised:
            validate_tournament_state(forged_state)
        self.assertEqual(raised.exception.code, "tournament.strategy_snapshot_mismatch")


if __name__ == "__main__":
    unittest.main()

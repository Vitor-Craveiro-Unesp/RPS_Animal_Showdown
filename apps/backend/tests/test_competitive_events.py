"""Official event contract over deterministic canonical Engine transitions."""

from __future__ import annotations

import pytest

from app.competitive_events import events_for_round
from rps_game_engine import (
    Competitor, Move, ProbabilityDistribution, Strategy, StrategyCondition,
    TournamentStatus, play_active_match_round, start_tournament,
)


class FirstDraw:
    def random(self) -> float:
        return 0.0


def player(player_id: str, move: Move) -> Competitor:
    distribution = ProbabilityDistribution(
        rock=100 if move is Move.ROCK else 0,
        paper=100 if move is Move.PAPER else 0,
        scissors=100 if move is Move.SCISSORS else 0,
    )
    return Competitor(player_id, Strategy({condition: distribution for condition in StrategyCondition}))


@pytest.mark.parametrize("hearts", [1, 2, 3, 4])
def test_each_approved_format_loses_exactly_one_heart_until_champion(hearts: int) -> None:
    state = start_tournament("room", (player("rock", Move.ROCK), player("scissors", Move.SCISSORS)), hearts, FirstDraw())
    for number in range(1, hearts + 1):
        transition = play_active_match_round(state, FirstDraw())
        names = [name for name, _ in events_for_round(state, transition, state_version=number + 1, public_state={"safe": True})]
        assert transition.match_round.player_two_hearts == hearts - number
        assert "round_resolved" in names and "heart_lost" in names
        assert ("player_eliminated" in names) == (number == hearts)
        assert ("champion" in names) == (number == hearts)
        state = transition.state
    assert state.status is TournamentStatus.COMPLETED
    assert state.champion_id == "rock"


def test_tie_has_no_heart_loss_and_event_payload_has_no_private_conditions() -> None:
    state = start_tournament("room", (player("a", Move.ROCK), player("b", Move.ROCK)), 2, FirstDraw())
    transition = play_active_match_round(state, FirstDraw())
    events = events_for_round(state, transition, state_version=2, public_state={"players": []})
    assert [name for name, _ in events] == ["match_started", "final_started", "round_resolved"]
    assert transition.match_round.lost_heart_player_id is None
    assert transition.match_round.player_one_hearts == 2
    assert transition.match_round.player_two_hearts == 2
    assert "condition" not in repr(events) and "strategy" not in repr(events)


def test_bye_advance_next_match_and_champion_events_follow_engine_bracket() -> None:
    state = start_tournament("room", (
        player("a", Move.ROCK), player("b", Move.PAPER), player("c", Move.SCISSORS)
    ), 1, FirstDraw())
    first = play_active_match_round(state, FirstDraw())
    first_events = events_for_round(state, first, state_version=2, public_state={})
    names = [name for name, _ in first_events]
    assert names[:3] == ["player_waiting", "match_started", "round_resolved"]
    assert names.count("second_chance_selected") == 1
    assert "player_advanced" in names
    assert names[-1] == "match_started"
    special = play_active_match_round(first.state, FirstDraw())
    special_events = events_for_round(first.state, special, state_version=3, public_state={})
    assert "second_chance_completed" in [name for name, _ in special_events]
    final = play_active_match_round(special.state, FirstDraw())
    final_events = events_for_round(special.state, final, state_version=4, public_state={})
    assert final_events[-1][0] == "champion"
    assert final.state.champion_id is not None

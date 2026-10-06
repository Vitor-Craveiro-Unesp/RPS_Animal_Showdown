"""Official placements, independent executions and bronze recovery."""
from copy import deepcopy
from dataclasses import replace
from random import Random
from uuid import UUID

import pytest
from rps_game_engine import (
    Competitor, EngineValidationError, ProbabilityDistribution, Strategy,
    StrategyCondition, start_tournament, play_active_match_round,
    tournament_state_from_snapshot, tournament_state_to_snapshot,
)


def run(count, hearts, seed):
    rng = Random(seed)
    strategy = Strategy({c: ProbabilityDistribution(33, 33, 34) for c in StrategyCondition})
    state = start_tournament(str(UUID(int=900)), tuple(
        Competitor(str(UUID(int=i+1)), strategy) for i in range(count)
    ), hearts, rng, run_id=str(UUID(int=1000+seed)))
    initial = state
    order = []
    for _ in range(3000):
        state = tournament_state_from_snapshot(tournament_state_to_snapshot(state))
        if state.champion_id:
            return initial, state, order
        match = next(m for m in state.current_round.matches if m.status.value == "active")
        if not match.battle.rounds:
            order.append(match.match_id)
            assert match.battle.player_one_hearts == match.battle.player_two_hearts == hearts
        state = play_active_match_round(state, rng).state
    pytest.fail("Unfinished tournament")


@pytest.mark.parametrize("count", [2, 3, 4, 5, 6, 7, 8, 9, 15])
@pytest.mark.parametrize("hearts", [1, 2, 3, 4])
def test_official_podium_and_order(count, hearts):
    initial, state, order = run(count, hearts, count * 10 + hearts)
    assert state.competitors == initial.competitors
    final = state.completed_rounds[-1].matches[-1]
    assert state.first_place == state.champion_id == final.battle.winner_id
    assert state.second_place == final.battle.loser_id
    placements = [p for p in (state.first_place, state.second_place, state.third_place) if p]
    assert len(set(placements)) == (2 if count == 2 else 3)
    bronze = [m for r in state.completed_rounds for m in r.matches if m.match_id.endswith(":third-place")]
    if bronze:
        assert len(bronze) == 1
        semifinals = state.completed_rounds[-2].matches
        assert len(semifinals) == 2
        assert {m.battle.winner_id for m in semifinals} == {final.battle.player_one.player_id, final.battle.player_two.player_id}
        assert {m.battle.loser_id for m in semifinals} == {bronze[0].battle.player_one.player_id, bronze[0].battle.player_two.player_id}
        assert order[-2:] == [bronze[0].match_id, final.match_id]
        assert state.third_place == bronze[0].battle.winner_id
    elif count == 3:
        assert state.third_place == next(c.player_id for c in state.competitors if c.player_id not in (state.first_place, state.second_place))
    elif count > 3:
        assert len(state.completed_rounds[-2].entrant_ids) == 3
        assert state.third_place == state.completed_rounds[-2].matches[0].battle.loser_id
    assert sum(m.endswith(":second-chance") for m in order) == count % 2
    forged = deepcopy(tournament_state_to_snapshot(state))
    forged["second_place"] = state.first_place
    with pytest.raises(EngineValidationError):
        tournament_state_from_snapshot(forged)


def test_new_run_resets_podium_and_zombie_and_uses_new_randomness():
    runs = [run(7, 1, seed) for seed in range(8)]
    assert len({initial.run_id for initial, _, _ in runs}) == 8
    assert len({initial.current_round.waiting_player_id for initial, _, _ in runs}) > 1
    assert len({final.completed_rounds[0].second_chance_player_id for _, final, _ in runs}) > 1
    for initial, _, _ in runs:
        assert initial.first_place is initial.second_place is initial.third_place is None
        assert not initial.completed_rounds
        assert initial.current_round.second_chance_player_id is None


def test_snapshot_cannot_move_matches_to_another_run():
    initial, _, _ = run(4, 1, 1)
    snapshot = tournament_state_to_snapshot(initial)
    snapshot["run_id"] = str(UUID(int=9999))
    with pytest.raises(EngineValidationError):
        tournament_state_from_snapshot(snapshot)

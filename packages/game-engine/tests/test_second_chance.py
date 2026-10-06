"""Second Chance invariants, recovery and cardinalities; seeded RNG stays in Engine."""
from copy import deepcopy
from dataclasses import replace
from random import Random
from uuid import UUID

import pytest

from rps_game_engine import (
    Competitor, EngineValidationError, ProbabilityDistribution, Strategy,
    StrategyCondition, play_active_match_round, start_tournament,
    tournament_state_from_snapshot, tournament_state_to_snapshot, validate_tournament_state,
)


def initial(count, hearts, rng):
    strategy = Strategy({c: ProbabilityDistribution(33, 33, 34) for c in StrategyCondition})
    return start_tournament(str(UUID(int=900)), tuple(
        Competitor(str(UUID(int=i+1)), strategy) for i in range(count)
    ), hearts, rng)


@pytest.mark.parametrize("count", [3, 5, 7, 9, 2, 4, 6, 8])
@pytest.mark.parametrize("hearts", [1, 2, 3, 4])
def test_full_bracket_recovery_identity_history_and_full_hearts(count, hearts):
    rng = Random(count * 100 + hearts)
    state = initial(count, hearts, rng)
    original = state.competitors
    first = state.current_round
    waiting = first.waiting_player_id
    assert bool(waiting) == bool(count % 2)
    assert first.bye_player_id is None
    paired = {p.player_id for m in first.matches for p in (m.battle.player_one, m.battle.player_two)}
    assert paired == {p.player_id for p in original} - ({waiting} if waiting else set())
    seen_special = set()
    for _ in range(2000):
        # Reconstruct at every transition, including just before/after selection,
        # every exchange of the special match and every later phase.
        restored = tournament_state_from_snapshot(tournament_state_to_snapshot(state))
        assert restored == state
        assert restored.competitors == original
        if state.champion_id:
            break
        state = play_active_match_round(restored, rng).state
        rounds = (*state.completed_rounds, *((state.current_round,) if state.current_round else ()))
        for round_ in rounds:
            if round_.number > 1:
                assert round_.second_chance_player_id is None
                assert round_.waiting_player_id is None
            if not round_.second_chance_player_id:
                continue
            zombie = round_.second_chance_player_id
            ordinary, special = round_.matches[:-1], round_.matches[-1]
            assert zombie in {m.battle.loser_id for m in ordinary}
            assert zombie not in {m.battle.winner_id for m in ordinary}
            assert special.battle.player_one == next(p for p in original if p.player_id == zombie)
            assert special.battle.player_two.player_id == waiting
            assert all(m.battle.loser_id is not None for m in ordinary)
            if special.match_id not in seen_special:
                assert special.battle.player_one_hearts == special.battle.player_two_hearts == hearts
                assert special.battle.rounds == ()
            seen_special.add(special.match_id)
    else:
        pytest.fail("Bracket did not terminate")
    assert len(seen_special) == count % 2
    assert state.current_round is None
    assert len({state.champion_id}) == 1
    assert state.champion_id in {p.player_id for p in original}
    assert sum(len(r.matches) for r in state.completed_rounds) == count - 1 + count % 2 + int(count in (4, 7, 8))


def test_server_draw_can_select_different_waiting_players():
    assert len({initial(7, 1, Random(seed)).current_round.waiting_player_id for seed in range(30)}) == 7


def test_rejects_a_winner_as_zombie_and_a_second_resurrection():
    rng = Random(30)
    state = initial(7, 2, rng)
    while not state.current_round.second_chance_player_id:
        state = play_active_match_round(state, rng).state
    first = state.current_round
    forged = replace(state, current_round=replace(first,
        second_chance_player_id=first.matches[0].battle.winner_id))
    with pytest.raises(EngineValidationError):
        validate_tournament_state(forged)
    while state.current_round.number == 1:
        state = play_active_match_round(state, rng).state
    forged = replace(state, current_round=replace(state.current_round,
        waiting_player_id=state.current_round.entrant_ids[0],
        second_chance_player_id=first.second_chance_player_id))
    with pytest.raises(EngineValidationError):
        validate_tournament_state(forged)


def test_special_ties_and_both_possible_winners_preserve_first_defeat():
    outcomes, ties = set(), 0
    for seed in range(40):
        rng = Random(seed)
        state = initial(3, 1, rng)
        while not state.champion_id:
            transition = play_active_match_round(state, rng)
            active = next(m for m in state.current_round.matches if m.status.value == "active")
            if active.match_id.endswith(":second-chance"):
                if transition.match_round.lost_heart_player_id is None:
                    ties += 1
                    assert transition.match_round.player_one_hearts == active.battle.player_one_hearts
                    assert transition.match_round.player_two_hearts == active.battle.player_two_hearts
                if transition.completed_match_id:
                    finished = transition.state.completed_rounds[0]
                    battle = finished.matches[-1].battle
                    outcomes.add(battle.winner_id == finished.second_chance_player_id)
                    assert battle.winner_id in transition.state.current_round.entrant_ids
                    assert battle.loser_id not in transition.state.current_round.entrant_ids
                    assert finished.matches[0].battle.loser_id == finished.second_chance_player_id
            state = transition.state
    assert outcomes == {True, False}
    assert ties > 0


def test_version_two_rejects_rule_downgrade_and_legacy_roundtrips():
    state = initial(3, 1, Random(1))
    payload = tournament_state_to_snapshot(state)
    forged = deepcopy(payload)
    round_ = forged["current_round"]
    round_["bye_player_id"] = round_.pop("waiting_player_id")
    round_.pop("second_chance_player_id")
    with pytest.raises(EngineValidationError):
        tournament_state_from_snapshot(forged)
    forged["schema_version"] = 1
    for key in ("run_id", "first_place", "second_place", "third_place"):
        forged.pop(key)
    legacy = tournament_state_from_snapshot(forged)
    assert tournament_state_to_snapshot(legacy) == forged
    for _ in range(100):
        legacy = tournament_state_from_snapshot(tournament_state_to_snapshot(legacy))
        if legacy.champion_id:
            break
        legacy = play_active_match_round(legacy, Random(_)).state
    assert legacy.champion_id
    assert tournament_state_to_snapshot(legacy)["schema_version"] == 1
    forged = deepcopy(payload)
    forged["current_round"]["bye_player_id"] = forged["current_round"]["waiting_player_id"]
    forged["current_round"]["waiting_player_id"] = None
    with pytest.raises(EngineValidationError):
        tournament_state_from_snapshot(forged)

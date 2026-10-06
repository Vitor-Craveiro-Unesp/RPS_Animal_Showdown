"""Public event descriptions derived exclusively from an Engine transition."""

from __future__ import annotations

from rps_game_engine import TournamentState, TournamentTransition


def events_for_round(
    previous: TournamentState,
    transition: TournamentTransition,
    *,
    state_version: int,
    public_state: dict[str, object],
) -> list[tuple[str, dict[str, object]]]:
    """Order one round's public events without disclosing strategy conditions."""
    current = previous.current_round
    if current is None:
        raise ValueError("A completed tournament has no active match.")
    active = next(match for match in current.matches if match.status.value == "active")
    battle = active.battle
    round_ = transition.match_round
    base = {"tournamentId": previous.tournament_id, "stateVersion": state_version, "runId": previous.run_id or previous.tournament_id}
    events: list[tuple[str, dict[str, object]]] = []

    if current.number == 1 and active == current.matches[0] and not battle.rounds:
        if current.waiting_player_id is not None:
            events.append(("player_waiting", {**base, "playerId": current.waiting_player_id, "round": 1}))
        if current.bye_player_id is not None:
            events.append(("bye", {**base, "playerId": current.bye_player_id, "round": current.number}))
        events.append(("match_started", {
            **base, "matchId": active.match_id, "round": current.number,
            "playerOneId": battle.player_one.player_id,
            "playerTwoId": battle.player_two.player_id,
        }))
        if len(previous.competitors) == 2:
            events.append(("final_started", {**base, "matchId": active.match_id}))

    events.append(("round_resolved", {
        **base, "matchId": active.match_id, "round": round_.number,
        "playerOneMove": round_.player_one_move.value,
        "playerTwoMove": round_.player_two_move.value,
        "outcome": round_.outcome.value,
        "playerOneHearts": round_.player_one_hearts,
        "playerTwoHearts": round_.player_two_hearts,
        "lostHeartPlayerId": round_.lost_heart_player_id,
        "state": public_state,
    }))
    if round_.lost_heart_player_id is not None:
        remaining = (
            round_.player_one_hearts
            if round_.lost_heart_player_id == battle.player_one.player_id
            else round_.player_two_hearts
        )
        events.append(("heart_lost", {**base, "matchId": active.match_id,
            "playerId": round_.lost_heart_player_id, "heartsRemaining": remaining}))

    if transition.completed_match_id is not None:
        loser = round_.lost_heart_player_id
        winner = (
            battle.player_two.player_id if loser == battle.player_one.player_id
            else battle.player_one.player_id
        )
        events.extend([
            ("player_eliminated", {**base, "matchId": active.match_id, "playerId": loser}),
            ("match_completed", {**base, "matchId": active.match_id,
                "winnerId": winner, "loserId": loser}),
        ])
        if not active.match_id.endswith(":third-place"):
            events.append(("player_advanced", {**base, "matchId": active.match_id, "playerId": winner}))
        if active.match_id.endswith(":second-chance"):
            events.extend([
                ("second_chance_completed", {**base, "matchId": active.match_id, "winnerId": winner, "loserId": loser}),
                ("player_eliminated_definitively", {**base, "matchId": active.match_id, "playerId": loser}),
            ])
        if active.match_id.endswith(":third-place"):
            events.append(("third_place_decided", {**base, "winnerId": winner, "loserId": loser, "matchId": active.match_id}))
    if transition.assigned_bye_player_id is not None:
        events.append(("bye", {**base, "playerId": transition.assigned_bye_player_id,
            "round": transition.state.current_round.number if transition.state.current_round else None}))
    if transition.started_match_id is not None:
        next_round = transition.state.current_round
        if next_round is None:
            raise ValueError("Started match must exist in the next state.")
        next_match = next(match for match in next_round.matches if match.match_id == transition.started_match_id)
        if next_match.match_id.endswith(":third-place"):
            events.append(("third_place_match_started", {**base, "matchId": next_match.match_id,
                "playerOneId": next_match.battle.player_one.player_id, "playerTwoId": next_match.battle.player_two.player_id}))
        elif len(next_round.entrant_ids) == 2:
            events.append(("final_started", {**base, "matchId": next_match.match_id}))
        if next_match.match_id.endswith(":second-chance"):
            events.extend([
                ("second_chance_selected", {**base, "playerId": next_round.second_chance_player_id,
                    "waitingPlayerId": next_round.waiting_player_id}),
                ("second_chance_match_started", {**base, "matchId": next_match.match_id,
                    "playerOneId": next_match.battle.player_one.player_id,
                    "playerTwoId": next_match.battle.player_two.player_id}),
            ])
        events.append(("match_started", {**base, "matchId": next_match.match_id,
            "round": next_round.number,
            "playerOneId": next_match.battle.player_one.player_id,
            "playerTwoId": next_match.battle.player_two.player_id}))
    if transition.champion_id is not None:
        events.append(("podium_decided", {**base, "firstPlace": transition.state.first_place,
            "secondPlace": transition.state.second_place, "thirdPlace": transition.state.third_place}))
        events.append(("champion", {**base, "playerId": transition.champion_id}))
    return events

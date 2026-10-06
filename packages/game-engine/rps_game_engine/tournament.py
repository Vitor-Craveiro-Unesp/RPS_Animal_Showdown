"""Single-elimination bracket construction and official transitions."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

from .errors import EngineValidationError, InvalidTransitionError
from .match import play_round, start_match, validate_match_state
from .models import (
    BracketMatch,
    BracketMatchStatus,
    BracketRoundState,
    Competitor,
    MatchStatus,
    TournamentState,
    TournamentStatus,
    TournamentTransition,
)
from .randomness import RandomSource, draw_index


def start_tournament(
    tournament_id: str,
    competitors: tuple[Competitor, ...] | list[Competitor],
    hearts_per_match: int,
    random_source: RandomSource,
    *, run_id: str | None = None,
) -> TournamentState:
    if not isinstance(tournament_id, str) or not tournament_id.strip():
        raise EngineValidationError(
            "tournament.invalid_id",
            "A tournament must have a non-empty tournament_id.",
        )
    normalized = tuple(competitors)
    if len(normalized) < 2:
        raise EngineValidationError(
            "tournament.not_enough_competitors",
            "A tournament requires at least two competitors.",
        )
    if any(not isinstance(competitor, Competitor) for competitor in normalized):
        raise EngineValidationError(
            "tournament.invalid_competitor",
            "Every tournament entrant must be a validated Competitor value.",
        )
    player_ids = [competitor.player_id for competitor in normalized]
    if len(player_ids) != len(set(player_ids)):
        raise EngineValidationError(
            "tournament.duplicate_competitor",
            "Competitor player_id values must be unique in a tournament.",
        )
    if isinstance(hearts_per_match, bool) or not isinstance(hearts_per_match, int) or hearts_per_match <= 0:
        raise EngineValidationError(
            "tournament.invalid_hearts",
            "hearts_per_match must be a positive integer.",
        )

    current_round = _build_round(
        tournament_id=run_id or tournament_id,
        number=1,
        entrant_ids=tuple(player_ids),
        competitors=normalized,
        hearts_per_match=hearts_per_match,
        random_source=random_source,
    )
    if current_round.bye_player_id is not None:
        current_round = replace(current_round, waiting_player_id=current_round.bye_player_id, bye_player_id=None)
    state = TournamentState(
        tournament_id=tournament_id,
        run_id=run_id,
        podium_enabled=True,
        competitors=normalized,
        hearts_per_match=hearts_per_match,
        current_round=current_round,
    )
    validate_tournament_state(state)
    return state


def play_active_match_round(
    state: TournamentState,
    random_source: RandomSource,
) -> TournamentTransition:
    # Persistence adapters must deep-validate reconstructed snapshots before
    # entering the trusted in-memory transition loop.
    validate_tournament_state(state, verify_match_history=False)
    if state.status is TournamentStatus.COMPLETED or state.current_round is None:
        raise InvalidTransitionError(
            "tournament.already_completed",
            "A completed tournament cannot advance.",
        )

    current_round = state.current_round
    active_index = next(
        index
        for index, bracket_match in enumerate(current_round.matches)
        if bracket_match.status is BracketMatchStatus.ACTIVE
    )
    active_match = current_round.matches[active_index]
    match_transition = play_round(active_match.battle, random_source)
    updated_match = replace(active_match, battle=match_transition.state)
    matches = list(current_round.matches)
    matches[active_index] = updated_match

    completed_match_id: str | None = None
    started_match_id: str | None = None
    assigned_bye_player_id: str | None = None
    champion_id: str | None = None

    if match_transition.state.status is MatchStatus.ACTIVE:
        next_round_state = replace(current_round, matches=tuple(matches))
        next_state = replace(state, current_round=next_round_state)
    else:
        completed_match_id = active_match.match_id
        matches[active_index] = replace(updated_match, status=BracketMatchStatus.COMPLETED)
        # Selection and creation are one immutable transition, persisted atomically.
        # No restart can observe a chosen zombie without its official match.
        if (current_round.waiting_player_id is not None
                and current_round.second_chance_player_id is None
                and all(match.status is BracketMatchStatus.COMPLETED for match in matches)):
            losers = tuple(match.battle.loser_id for match in matches)
            selected = losers[draw_index(len(losers), random_source)]
            competitors = {competitor.player_id: competitor for competitor in state.competitors}
            special_id = f"{state.run_id or state.tournament_id}:r1:second-chance"
            matches.append(BracketMatch(
                match_id=special_id, status=BracketMatchStatus.PENDING,
                battle=start_match(special_id, competitors[selected],
                    competitors[current_round.waiting_player_id], state.hearts_per_match),
            ))
            current_round = replace(current_round, second_chance_player_id=selected)
        pending_index = next(
            (
                index
                for index, bracket_match in enumerate(matches)
                if bracket_match.status is BracketMatchStatus.PENDING
            ),
            None,
        )
        if pending_index is not None:
            matches[pending_index] = replace(matches[pending_index], status=BracketMatchStatus.ACTIVE)
            started_match_id = matches[pending_index].match_id
            next_state = replace(
                state,
                current_round=replace(current_round, matches=tuple(matches)),
            )
        else:
            finished_round = replace(current_round, matches=tuple(matches))
            advancing_ids = tuple(
                bracket_match.battle.winner_id for bracket_match in matches
                if not bracket_match.match_id.endswith(':third-place')
            )
            if any(player_id is None for player_id in advancing_ids):
                raise EngineValidationError(
                    "tournament.missing_match_winner",
                    "Every completed bracket match must have a winner.",
                )
            if finished_round.bye_player_id is not None:
                advancing_ids = (*advancing_ids, finished_round.bye_player_id)

            if len(advancing_ids) == 1:
                champion_id = advancing_ids[0]
                next_state = replace(
                    state,
                    current_round=None,
                    completed_rounds=(*state.completed_rounds, finished_round),
                    status=TournamentStatus.COMPLETED,
                    champion_id=champion_id,
                )
            else:
                new_round = _build_round(
                    tournament_id=state.run_id or state.tournament_id,
                    number=finished_round.number + 1,
                    entrant_ids=advancing_ids,
                    competitors=state.competitors,
                    hearts_per_match=state.hearts_per_match,
                    random_source=random_source,
                )
                if (state.podium_enabled and len(advancing_ids) == 2
                        and len(finished_round.entrant_ids) == 4 and len(matches) == 2):
                    loser_ids = tuple(m.battle.loser_id for m in matches)
                    canonical = {c.player_id: c for c in state.competitors}
                    bronze_id = f"{state.run_id or state.tournament_id}:r{new_round.number}:third-place"
                    bronze = BracketMatch(bronze_id, BracketMatchStatus.ACTIVE,
                        start_match(bronze_id, canonical[loser_ids[0]], canonical[loser_ids[1]], state.hearts_per_match))
                    new_round = replace(new_round, matches=(bronze, replace(new_round.matches[0], status=BracketMatchStatus.PENDING)))
                assigned_bye_player_id = new_round.bye_player_id
                started_match_id = next(
                    bracket_match.match_id
                    for bracket_match in new_round.matches
                    if bracket_match.status is BracketMatchStatus.ACTIVE
                )
                next_state = replace(
                    state,
                    current_round=new_round,
                    completed_rounds=(*state.completed_rounds, finished_round),
                )

    validate_tournament_state(next_state, verify_match_history=False)
    return TournamentTransition(
        state=next_state,
        match_round=match_transition.round,
        completed_match_id=completed_match_id,
        started_match_id=started_match_id,
        assigned_bye_player_id=assigned_bye_player_id,
        champion_id=champion_id,
    )


def validate_tournament_state(
    state: TournamentState,
    *,
    verify_match_history: bool = True,
) -> None:
    if not isinstance(state, TournamentState):
        raise EngineValidationError("tournament.invalid_state", "Expected a TournamentState.")
    if any(not isinstance(competitor, Competitor) for competitor in state.competitors):
        raise EngineValidationError(
            "tournament.invalid_competitor",
            "Every tournament entrant must be a validated Competitor value.",
        )
    competitor_ids = [competitor.player_id for competitor in state.competitors]
    if len(competitor_ids) < 2 or len(competitor_ids) != len(set(competitor_ids)):
        raise EngineValidationError(
            "tournament.invalid_competitors",
            "Tournament competitors must contain at least two unique player IDs.",
        )
    if (
        isinstance(state.hearts_per_match, bool)
        or not isinstance(state.hearts_per_match, int)
        or state.hearts_per_match <= 0
    ):
        raise EngineValidationError(
            "tournament.invalid_hearts",
            "hearts_per_match must be a positive integer.",
        )
    if not isinstance(state.status, TournamentStatus):
        raise EngineValidationError(
            "tournament.invalid_status",
            "Tournament status is invalid.",
        )

    known_ids = set(competitor_ids)
    previous_advancing_ids: tuple[str, ...] | None = None
    seen_match_ids: set[str] = set()
    for expected_number, completed_round in enumerate(state.completed_rounds, start=1):
        _validate_bracket_round(
            completed_round,
            state,
            expected_number=expected_number,
            require_completed=True,
            verify_match_history=verify_match_history,
            seen_match_ids=seen_match_ids,
        )
        if previous_advancing_ids is not None and completed_round.entrant_ids != previous_advancing_ids:
            raise EngineValidationError(
                "tournament.invalid_round_progression",
                "A round's entrants must be the previous round's advancing players.",
            )
        previous_advancing_ids = _advancing_ids(completed_round)

    if state.status is TournamentStatus.COMPLETED:
        if (
            state.current_round is not None
            or state.champion_id not in known_ids
            or previous_advancing_ids != (state.champion_id,)
        ):
            raise EngineValidationError(
                "tournament.invalid_champion",
                "A completed tournament must have one known champion and no current round.",
            )
        return

    if state.current_round is None or state.champion_id is not None:
        raise EngineValidationError(
            "tournament.invalid_active_state",
            "An active tournament must have a current round and no champion.",
        )
    expected_current_number = len(state.completed_rounds) + 1
    _validate_bracket_round(
        state.current_round,
        state,
        expected_number=expected_current_number,
        require_completed=False,
        verify_match_history=verify_match_history,
        seen_match_ids=seen_match_ids,
    )
    if previous_advancing_ids is not None and state.current_round.entrant_ids != previous_advancing_ids:
        raise EngineValidationError(
            "tournament.invalid_round_progression",
            "A round's entrants must be the previous round's advancing players.",
        )


def _validate_bracket_round(
    bracket_round: BracketRoundState,
    state: TournamentState,
    *,
    expected_number: int,
    require_completed: bool,
    verify_match_history: bool,
    seen_match_ids: set[str],
) -> None:
    if not isinstance(bracket_round, BracketRoundState) or bracket_round.number != expected_number:
        raise EngineValidationError(
            "tournament.invalid_round_number",
            "Bracket round numbers must be contiguous and one-based.",
        )
    entrant_ids = bracket_round.entrant_ids
    if len(entrant_ids) < 2 or len(entrant_ids) != len(set(entrant_ids)):
        raise EngineValidationError(
            "tournament.invalid_round_entrants",
            "Each bracket round must have at least two unique entrants.",
        )
    if not set(entrant_ids).issubset({competitor.player_id for competitor in state.competitors}):
        raise EngineValidationError(
            "tournament.unknown_entrant",
            "Every round entrant must belong to the tournament.",
        )

    waiting = bracket_round.waiting_player_id
    zombie = bracket_round.second_chance_player_id
    bronze_expected = (state.podium_enabled and expected_number > 1 and len(entrant_ids) == 2
        and len(state.completed_rounds[expected_number - 2].entrant_ids) == 4
        and len(state.completed_rounds[expected_number - 2].matches) == 2)
    if waiting is not None and (expected_number != 1 or len(entrant_ids) % 2 != 1
            or waiting not in entrant_ids or bracket_round.bye_player_id is not None):
        raise EngineValidationError("tournament.invalid_waiting", "Waiting is only valid in the initial odd round.")
    if zombie is not None and waiting is None:
        raise EngineValidationError("tournament.invalid_second_chance", "Second Chance requires a waiting participant.")
    if expected_number == 1 and set(entrant_ids) != {c.player_id for c in state.competitors}:
        raise EngineValidationError("tournament.invalid_initial_entrants", "Initial round must include every competitor.")
    expected_has_bye = len(entrant_ids) % 2 == 1 and waiting is None
    if expected_has_bye != (bracket_round.bye_player_id is not None):
        raise EngineValidationError(
            "tournament.invalid_bye",
            "An odd round must have exactly one BYE and an even round must have none.",
        )
    if bracket_round.bye_player_id is not None and bracket_round.bye_player_id not in entrant_ids:
        raise EngineValidationError(
            "tournament.invalid_bye",
            "The BYE recipient must be an entrant in the round.",
        )
    if len(bracket_round.matches) != len(entrant_ids) // 2 + (1 if zombie is not None else 0) + int(bronze_expected):
        raise EngineValidationError(
            "tournament.invalid_match_count",
            "The bracket match count does not cover the round entrants.",
        )

    canonical_competitors = {
        competitor.player_id: competitor for competitor in state.competitors
    }
    paired_ids: list[str] = []
    for bracket_match in bracket_round.matches:
        if state.run_id and not bracket_match.match_id.startswith(f"{state.run_id}:r{expected_number}:"):
            raise EngineValidationError("tournament.invalid_match_id", "Match does not belong to this execution and bracket round.")
        if bracket_match.match_id.endswith(":third-place") and (not bronze_expected or bracket_match != bracket_round.matches[0]):
            raise EngineValidationError("tournament.invalid_bronze", "Unexpected bronze match.")
        if not isinstance(bracket_match.status, BracketMatchStatus):
            raise EngineValidationError(
                "tournament.invalid_match_status",
                "Bracket match status is invalid.",
            )
        validate_match_state(
            bracket_match.battle,
            verify_history=verify_match_history,
        )
        if (
            bracket_match.match_id != bracket_match.battle.match_id
            or bracket_match.match_id in seen_match_ids
        ):
            raise EngineValidationError(
                "tournament.invalid_match_id",
                "Bracket match IDs must be unique across the tournament and match their battle IDs.",
            )
        seen_match_ids.add(bracket_match.match_id)
        if bracket_match.battle.initial_hearts != state.hearts_per_match:
            raise EngineValidationError(
                "tournament.match_hearts_mismatch",
                "Every bracket battle must use the tournament heart configuration.",
            )
        paired_ids.extend(
            (
                bracket_match.battle.player_one.player_id,
                bracket_match.battle.player_two.player_id,
            )
        )
        if (
            bracket_match.battle.player_one
            != canonical_competitors.get(bracket_match.battle.player_one.player_id)
            or bracket_match.battle.player_two
            != canonical_competitors.get(bracket_match.battle.player_two.player_id)
        ):
            raise EngineValidationError(
                "tournament.strategy_snapshot_mismatch",
                "Bracket battles must use the tournament's frozen competitor snapshots.",
            )
        if bracket_match.status is BracketMatchStatus.COMPLETED:
            if bracket_match.battle.status is not MatchStatus.COMPLETED:
                raise EngineValidationError(
                    "tournament.incomplete_battle",
                    "A completed bracket match must contain a completed battle.",
                )
        elif bracket_match.battle.status is MatchStatus.COMPLETED:
            raise EngineValidationError(
                "tournament.completed_battle_not_advanced",
                "A completed battle must be applied to its bracket match atomically.",
            )

    expected_paired_ids = set(entrant_ids)
    if bronze_expected:
        bronze = bracket_round.matches[0]
        semifinal = state.completed_rounds[expected_number - 2]
        losers = tuple(m.battle.loser_id for m in semifinal.matches)
        if (bronze.match_id != f"{state.run_id or state.tournament_id}:r{expected_number}:third-place"
                or tuple(paired_ids[:2]) != losers):
            raise EngineValidationError("tournament.invalid_bronze", "Bronze requires exactly the two semifinal losers.")
        paired_ids = paired_ids[2:]
    if waiting is not None:
        expected_paired_ids.remove(waiting)
    if zombie is not None:
        ordinary = bracket_round.matches[:-1]
        special = bracket_round.matches[-1]
        if (any(m.status is not BracketMatchStatus.COMPLETED for m in ordinary)
                or zombie not in tuple(m.battle.loser_id for m in ordinary)
                or special.match_id != f"{state.run_id or state.tournament_id}:r1:second-chance"
                or (special.battle.player_one.player_id, special.battle.player_two.player_id) != (zombie, waiting)):
            raise EngineValidationError("tournament.invalid_second_chance", "Only one initial loser can return against the waiting participant.")
        paired_ids = paired_ids[:-2]
    elif waiting is not None and require_completed:
        raise EngineValidationError("tournament.missing_second_chance", "The initial round must include Second Chance before advancing.")
    if bracket_round.bye_player_id is not None:
        expected_paired_ids.remove(bracket_round.bye_player_id)
    if len(paired_ids) != len(set(paired_ids)) or set(paired_ids) != expected_paired_ids:
        raise EngineValidationError(
            "tournament.invalid_match_entrants",
            "Every non-BYE entrant must appear in exactly one bracket match.",
        )

    statuses = tuple(bracket_match.status for bracket_match in bracket_round.matches)
    if require_completed:
        if any(status is not BracketMatchStatus.COMPLETED for status in statuses):
            raise EngineValidationError(
                "tournament.unfinished_completed_round",
                "A completed bracket round cannot contain active or pending matches.",
            )
        return

    if statuses.count(BracketMatchStatus.ACTIVE) != 1:
        raise EngineValidationError(
            "tournament.active_match_count",
            "Exactly one bracket match must be active.",
        )
    active_index = statuses.index(BracketMatchStatus.ACTIVE)
    if any(status is not BracketMatchStatus.COMPLETED for status in statuses[:active_index]) or any(
        status is not BracketMatchStatus.PENDING for status in statuses[active_index + 1 :]
    ):
        raise EngineValidationError(
            "tournament.invalid_match_order",
            "Matches before the active match must be completed and later matches pending.",
        )


def _advancing_ids(bracket_round: BracketRoundState) -> tuple[str, ...]:
    winner_ids = tuple(match.battle.winner_id for match in bracket_round.matches if not match.match_id.endswith(':third-place'))
    if any(winner_id is None for winner_id in winner_ids):
        raise EngineValidationError(
            "tournament.missing_match_winner",
            "Every completed bracket match must have a winner.",
        )
    advancing_ids = cast(tuple[str, ...], winner_ids)
    if bracket_round.bye_player_id is not None:
        advancing_ids = (*advancing_ids, bracket_round.bye_player_id)
    return advancing_ids


def _build_round(
    *,
    tournament_id: str,
    number: int,
    entrant_ids: tuple[str, ...],
    competitors: tuple[Competitor, ...],
    hearts_per_match: int,
    random_source: RandomSource,
) -> BracketRoundState:
    bye_player_id: str | None = None
    paired_ids = list(entrant_ids)
    if len(paired_ids) % 2 == 1:
        bye_index = draw_index(len(paired_ids), random_source)
        bye_player_id = paired_ids.pop(bye_index)

    competitor_by_id = {competitor.player_id: competitor for competitor in competitors}
    matches: list[BracketMatch] = []
    for offset in range(0, len(paired_ids), 2):
        match_number = offset // 2 + 1
        match_id = f"{tournament_id}:r{number}:m{match_number}"
        battle = start_match(
            match_id,
            competitor_by_id[paired_ids[offset]],
            competitor_by_id[paired_ids[offset + 1]],
            hearts_per_match,
        )
        matches.append(
            BracketMatch(
                match_id=match_id,
                status=(
                    BracketMatchStatus.ACTIVE
                    if match_number == 1
                    else BracketMatchStatus.PENDING
                ),
                battle=battle,
            )
        )

    return BracketRoundState(
        number=number,
        entrant_ids=entrant_ids,
        bye_player_id=bye_player_id,
        matches=tuple(matches),
    )

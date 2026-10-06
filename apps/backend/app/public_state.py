"""Whitelisted tournament state views safe for browser consumers.

The Engine snapshot is deliberately richer than a spectator view: it contains
each competitor's frozen strategy.  Keep this projection narrow and explicit
so adding fields to the Engine snapshot can never accidentally disclose a
strategy through the HTTP or realtime boundary.
"""

from __future__ import annotations

from typing import Any

from .store import TournamentRecord


def official_state_view(
    tournament: TournamentRecord,
    snapshot: dict[str, object],
    *,
    state_version: int | None = None,
) -> dict[str, object]:
    """Return the public, server-derived projection of an official snapshot."""

    players = {
        player.id: {
            "player_id": player.id,
            "display_name": player.display_name,
            "animal_id": player.animal_id,
        }
        for player in tournament.players.values()
        if not player.removed
    }
    rounds = [*_list(snapshot.get("completed_rounds")), snapshot.get("current_round")]
    first = next((r for r in rounds if isinstance(r, dict) and r.get("number") == 1), {})
    zombie = first.get("second_chance_player_id")
    for player in players.values():
        player["second_chance"] = player["player_id"] == zombie
    public_rounds = [view for item in rounds if (view := _round_view(item)) is not None]
    semifinals = next((r for r in public_rounds if len(r["entrant_ids"]) == 4 and len(r["matches"]) == 2), None)
    final_round = next((r for r in public_rounds if len(r["entrant_ids"]) == 2), None)
    bronze = next((m for r in public_rounds for m in r["matches"] if str(m["match_id"]).endswith(":third-place")), None)
    return {
        "tournament_id": tournament.id,
        "run_id": _optional_text(snapshot.get("run_id")) or tournament.id,
        "first_place": _optional_text(snapshot.get("first_place")) or _optional_text(snapshot.get("champion_id")),
        "second_place": _optional_text(snapshot.get("second_place")),
        "third_place": _optional_text(snapshot.get("third_place")),
        "semifinalist_ids": semifinals["entrant_ids"] if semifinals else [],
        "semifinal_loser_ids": [m["loser_id"] for m in semifinals["matches"] if m["loser_id"]] if semifinals else [],
        "third_place_match": bronze,
        "final_match": final_round["matches"][-1] if final_round else None,
        "sound_effects_enabled": tournament.sound_effects_enabled,
        "background_music_enabled": tournament.background_music_enabled,
        "movement_speed": tournament.movement_speed,
        "countdown_speed": tournament.countdown_speed,
        "state_version": state_version,
        "status": _text(snapshot.get("status")),
        "hearts_per_match": _integer(snapshot.get("hearts_per_match")),
        "champion_id": _optional_text(snapshot.get("champion_id")),
        "players": [players[player_id] for player_id in _competitor_ids(snapshot) if player_id in players],
        "current_round": _round_view(snapshot.get("current_round")),
        "completed_rounds": [
            view for item in _list(snapshot.get("completed_rounds")) if (view := _round_view(item)) is not None
        ],
    }


def _round_view(value: object) -> dict[str, object] | None:
    source = _object(value)
    if source is None:
        return None
    return {
        "number": _integer(source.get("number")),
        "waiting_player_id": _optional_text(source.get("waiting_player_id")),
        "second_chance_player_id": _optional_text(source.get("second_chance_player_id")),
        "eligible_loser_ids": [
            loser for item in _list(source.get("matches"))
            if isinstance(item, dict) and not str(item.get("match_id", "")).endswith(":second-chance")
            and isinstance(item.get("battle"), dict)
            and (loser := _optional_text(item["battle"].get("loser_id"))) is not None
        ] if source.get("waiting_player_id") else [],
        "entrant_ids": [item for item in _list(source.get("entrant_ids")) if isinstance(item, str)],
        "bye_player_id": _optional_text(source.get("bye_player_id")),
        "matches": [view for item in _list(source.get("matches")) if (view := _match_view(item)) is not None],
    }


def _match_view(value: object) -> dict[str, object] | None:
    source = _object(value)
    if source is None:
        return None
    battle = _object(source.get("battle"))
    if battle is None:
        return None
    # Conditions are intentionally excluded: they reveal how a private
    # conditional strategy was selected. Moves and outcomes are game results.
    rounds: list[dict[str, object]] = []
    # The browser renders the latest exchange; the durable official round
    # ledger retains the full history. Sending every past exchange in every
    # realtime event would make a long tie streak quadratic on the wire.
    for round_value in _list(battle.get("rounds"))[-1:]:
        round_source = _object(round_value)
        if round_source is None:
            continue
        rounds.append({
            "number": _integer(round_source.get("number")),
            "player_one_move": _text(round_source.get("player_one_move")),
            "player_two_move": _text(round_source.get("player_two_move")),
            "outcome": _text(round_source.get("outcome")),
            "player_one_hearts": _integer(round_source.get("player_one_hearts")),
            "player_two_hearts": _integer(round_source.get("player_two_hearts")),
            "lost_heart_player_id": _optional_text(round_source.get("lost_heart_player_id")),
        })
    return {
        "match_id": _text(source.get("match_id")),
        "status": _text(source.get("status")),
        "player_one_id": _text(battle.get("player_one_id")),
        "player_two_id": _text(battle.get("player_two_id")),
        "initial_hearts": _integer(battle.get("initial_hearts")),
        "player_one_hearts": _integer(battle.get("player_one_hearts")),
        "player_two_hearts": _integer(battle.get("player_two_hearts")),
        "winner_id": _optional_text(battle.get("winner_id")),
        "loser_id": _optional_text(battle.get("loser_id")),
        "rounds": rounds,
    }


def _competitor_ids(snapshot: dict[str, object]) -> list[str]:
    ids: list[str] = []
    for value in _list(snapshot.get("competitors")):
        source = _object(value)
        player_id = source.get("player_id") if source else None
        if isinstance(player_id, str):
            ids.append(player_id)
    return ids


def _object(value: object) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _text(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _optional_text(value: object) -> str | None:
    return _text(value)


def _integer(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None

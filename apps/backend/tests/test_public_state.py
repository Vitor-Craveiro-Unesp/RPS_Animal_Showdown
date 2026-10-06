from app.public_state import official_state_view
from app.store import PlayerRecord, TournamentRecord


def test_public_state_never_serializes_private_strategy_or_conditions() -> None:
    organizer_token = "raw-organizer-capability-must-never-be-public"
    organizer_digest = "digest-of-organizer-capability-must-never-be-public"
    tournament = TournamentRecord(
        id="tournament", code="ROOM", capacity=2, hearts_required=2,
        organizer_token_digest=organizer_digest, organizer_token_expires_at=__import__("datetime").datetime.max,
        players={"p1": PlayerRecord("p1", "Ana", "panda", "token")},
    )
    snapshot = {
        "status": "running", "hearts_per_match": 2, "champion_id": None,
        "competitors": [{"player_id": "p1", "strategy": {"initial": {"rock": 100}}}],
        "current_round": {"number": 1, "entrant_ids": ["p1"], "bye_player_id": None, "matches": [{
            "match_id": "m1", "status": "in_progress", "battle": {
                "player_one_id": "p1", "player_two_id": "p2", "initial_hearts": 2,
                "player_one_hearts": 2, "player_two_hearts": 1, "winner_id": None, "loser_id": None,
                "rounds": [{"number": 1, "player_one_move": "rock", "player_two_move": "scissors", "outcome": "player_one_won", "player_one_hearts": 2, "player_two_hearts": 1, "lost_heart_player_id": "p2", "player_one_condition": "initial"}],
            },
        }]},
        "completed_rounds": [],
    }

    snapshot["current_round"]["matches"][0]["battle"]["rounds"].append({
        "number": 2, "player_one_move": "paper", "player_two_move": "rock",
        "outcome": "player_one_won", "player_one_hearts": 2,
        "player_two_hearts": 0, "lost_heart_player_id": "p2",
    })
    view = official_state_view(tournament, snapshot, state_version=3)

    assert view["state_version"] == 3
    assert view["players"] == [{"player_id": "p1", "display_name": "Ana", "animal_id": "panda", "second_chance": False}]
    assert [round_["number"] for round_ in view["current_round"]["matches"][0]["rounds"]] == [2]
    rendered = repr(view)
    assert "strategy" not in rendered
    assert "condition" not in rendered
    assert organizer_token not in rendered
    assert organizer_digest not in rendered


def test_public_audio_configuration_preserves_all_independent_combinations() -> None:
    from datetime import datetime
    for effects in (True, False):
        for music in (True, False):
            room = TournamentRecord(id="room", code="ROOM", capacity=2, hearts_required=2,
                organizer_token_digest="digest", organizer_token_expires_at=datetime.max,
                sound_effects_enabled=effects, background_music_enabled=music,
                movement_speed="8", countdown_speed="0.5")
            view = official_state_view(room, {})
            assert view["sound_effects_enabled"] is effects
            assert view["background_music_enabled"] is music
            assert view["movement_speed"] == "8"
            assert view["countdown_speed"] == "0.5"

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.postgres_store import PostgresTournamentStore
from app.security import (
    PostgresFixedWindowRateLimiter,
    RateLimit,
    RateLimitExceeded,
    RateLimiterUnavailable,
    SlidingWindowRateLimiter,
    generate_tournament_code,
)
from app.store import InMemoryTournamentStore, TournamentRecord
from rps_game_engine import tournament_state_from_snapshot


def strategy_payload() -> dict[str, object]:
    distribution = {"rock": 100, "paper": 0, "scissors": 0}
    return {
        "initial": distribution,
        "lost_to_rock": distribution,
        "lost_to_paper": distribution,
        "lost_to_scissors": distribution,
        "won_against_rock": distribution,
        "won_against_paper": distribution,
        "won_against_scissors": distribution,
        "tied_with_rock": distribution,
        "tied_with_paper": distribution,
        "tied_with_scissors": distribution,
    }


def create_tournament(client: TestClient) -> dict[str, object]:
    response = client.post("/v1/tournaments", json={"capacity": 8, "hearts_required": 2})
    assert response.status_code == 201
    return response.json()


def join_tournament(client: TestClient, code: str, name: str) -> dict[str, object]:
    response = client.post(
        "/v1/tournaments/join",
        json={"tournament_code": code, "display_name": name, "animal_id": "tiger"},
    )
    assert response.status_code == 201
    return response.json()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def ready_player(client: TestClient, code: str, name: str) -> dict[str, object]:
    player = join_tournament(client, code, name)
    headers = bearer(str(player["player_access_token"]))
    assert client.put(f"/v1/tournaments/{code}/players/me/strategy", json=strategy_payload(), headers=headers).status_code == 204
    assert client.post(f"/v1/tournaments/{code}/players/me/ready", json={}, headers=headers).status_code == 204
    return player


class ScriptedPlayerCursor:
    """Small DB-API double that rejects reading a superseded result set."""

    def __init__(self, member_rows: list[tuple[object, ...]], rules: dict[str, object]) -> None:
        self.member_rows = member_rows
        self.rules = rules
        self.active_result: str | None = None
        self.parameters: list[tuple[object, ...]] = []

    def execute(self, statement: str, parameters: tuple[object, ...]) -> None:
        self.parameters.append(parameters)
        self.active_result = "members" if "FROM tournament_members member" in statement else "rules"

    def fetchall(self) -> list[tuple[object, ...]]:
        assert self.active_result == "members", "member rows must be materialized before a second SELECT"
        return self.member_rows

    def fetchone(self) -> tuple[object, ...]:
        assert self.active_result == "rules"
        return (self.rules,)


def _durable_record(tournament_id: str) -> TournamentRecord:
    return TournamentRecord(
        id=tournament_id,
        code="RPS-TESTPLAYERLOAD",
        capacity=8,
        hearts_required=2,
        organizer_token_digest="",
        organizer_token_expires_at=datetime.max.replace(tzinfo=UTC),
    )


@pytest.mark.parametrize("member_count", (0, 1, 2, 6))
def test_postgres_player_loader_materializes_zero_one_two_and_many_rows(member_count: int) -> None:
    tournament_id = str(uuid4())
    player_ids = [uuid4() for _ in range(member_count)]
    rows = [
        (player_id, f"Player {index}", "ready", {"initial": {"rock": 100}}, None)
        for index, player_id in enumerate(player_ids, start=1)
    ]
    cursor = ScriptedPlayerCursor(rows, {"hearts_required": 2, "animals": {str(player_id): "tiger" for player_id in player_ids}})

    players = PostgresTournamentStore("postgresql://unit-test.invalid/rps_unit")._load_players(
        cursor, _durable_record(tournament_id)
    )

    assert list(players) == [str(player_id) for player_id in player_ids]
    assert all(player.animal_id == "tiger" and player.ready for player in players.values())
    assert cursor.parameters == [(tournament_id,), (tournament_id,)]


def test_postgres_player_loader_keeps_uuid_tournament_scope_isolated() -> None:
    tournament_id, other_tournament_id = str(uuid4()), str(uuid4())
    player_id, foreign_player_id = uuid4(), uuid4()
    cursor = ScriptedPlayerCursor(
        [(player_id, "Scoped", "ready", {"initial": {"rock": 100}}, None)],
        {
            "hearts_required": 2,
            "animals": {str(player_id): "tiger", str(foreign_player_id): "panda"},
        },
    )

    players = PostgresTournamentStore("postgresql://unit-test.invalid/rps_unit")._load_players(
        cursor, _durable_record(tournament_id)
    )

    assert set(players) == {str(player_id)}
    assert str(foreign_player_id) not in players
    assert all(other_tournament_id not in parameters for parameters in cursor.parameters)


def test_service_requires_durable_database_without_an_explicit_unit_store(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL is required"):
        create_app()


def test_production_requires_explicit_cors_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    with pytest.raises(RuntimeError, match="ALLOWED_ORIGINS is required"):
        create_app(store=InMemoryTournamentStore())


def test_cors_origin_must_be_an_exact_http_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://rps.example/with-a-path")
    with pytest.raises(RuntimeError, match="absolute HTTP"):
        create_app(store=InMemoryTournamentStore())


def test_codes_are_opaque_and_nonsequential() -> None:
    codes = {generate_tournament_code() for _ in range(100)}
    assert len(codes) == 100
    assert all(code.startswith("RPS-") and len(code) == 20 for code in codes)


def test_tournament_uses_uuid_internally_and_code_only_as_public_access() -> None:
    client = TestClient(create_app(store=InMemoryTournamentStore()))
    tournament = create_tournament(client)
    assert len(str(tournament["tournament_id"])) == 36
    assert tournament["tournament_code"].startswith("RPS-")
    assert tournament["hearts_required"] == 2
    player = join_tournament(client, str(tournament["tournament_code"]), "Vitor")
    assert player["tournament_id"] == tournament["tournament_id"]
    assert player["hearts_required"] == 2
    current = client.get(
        f"/v1/tournaments/{tournament['tournament_code']}/players/me",
        headers=bearer(str(player["player_access_token"])),
    )
    assert current.status_code == 200
    assert current.json()["hearts_required"] == 2
    assert "strategy" not in current.json()["player"]


def test_anonymous_creation_issues_a_room_scoped_organizer_capability_without_leaking_it(caplog: pytest.LogCaptureFixture) -> None:
    """No account is needed, but the public room code never becomes admin auth."""
    store = InMemoryTournamentStore()
    client = TestClient(create_app(store=store))
    caplog.set_level("INFO", logger="app.main")

    created = client.post("/v1/tournaments", json={"capacity": 8, "hearts_required": 2})
    assert created.status_code == 201
    room = created.json()
    code = str(room["tournament_code"])
    token = str(room["organizer_access_token"])
    assert token and token != code
    assert len(token) >= 32
    assert token not in repr(store.get_tournament(code))
    assert token not in caplog.text

    # Missing, random, and public-code credentials all fail identically enough
    # to avoid creating an administrative oracle.
    admin_path = f"/v1/tournaments/{code}/admin/participants"
    assert client.get(admin_path).status_code == 401
    assert client.get(admin_path, headers=bearer("not-an-organizer-token")).status_code == 401
    assert client.get(admin_path, headers=bearer(code)).status_code == 401

    participant = join_tournament(client, code, "Participant")
    player_headers = bearer(str(participant["player_access_token"]))
    assert client.get(admin_path, headers=player_headers).status_code == 403
    assert client.patch(
        f"/v1/tournaments/{code}/admin/configuration",
        json={"capacity": 8, "hearts_required": 2}, headers=player_headers,
    ).status_code == 403
    assert client.post(
        f"/v1/tournaments/{code}/admin/start", json={}, headers=player_headers,
    ).status_code == 403
    assert client.get(admin_path, headers=bearer(token)).status_code == 200


@pytest.mark.parametrize("hearts_required", [0, 5, 1_000_000])
def test_only_approved_one_to_four_heart_formats_are_accepted(hearts_required: int) -> None:
    client = TestClient(create_app(store=InMemoryTournamentStore()))
    assert client.post(
        "/v1/tournaments", json={"capacity": 8, "hearts_required": hearts_required},
    ).status_code == 422
    room = create_tournament(client)
    assert client.patch(
        f"/v1/tournaments/{room['tournament_code']}/admin/configuration",
        json={"capacity": 8, "hearts_required": hearts_required},
        headers=bearer(str(room["organizer_access_token"])),
    ).status_code == 422


@pytest.mark.parametrize(
    ("sound_effects_enabled", "background_music_enabled"),
    ((True, True), (True, False), (False, True), (False, False)),
)
def test_organizer_audio_preferences_are_independent_and_server_persisted(
    sound_effects_enabled: bool,
    background_music_enabled: bool,
) -> None:
    store = InMemoryTournamentStore()
    client = TestClient(create_app(store=store))
    created = client.post(
        "/v1/tournaments",
        json={
            "capacity": 8,
            "hearts_required": 2,
            "sound_effects_enabled": sound_effects_enabled,
            "background_music_enabled": background_music_enabled,
        },
    )
    assert created.status_code == 201
    tournament = created.json()
    assert tournament["sound_effects_enabled"] is sound_effects_enabled
    assert tournament["background_music_enabled"] is background_music_enabled

    updated = client.patch(
        f"/v1/tournaments/{tournament['tournament_code']}/admin/configuration",
        json={
            "capacity": 8,
            "hearts_required": 2,
            "sound_effects_enabled": not sound_effects_enabled,
            "background_music_enabled": not background_music_enabled,
        },
        headers=bearer(str(tournament["organizer_access_token"])),
    )
    assert updated.status_code == 200
    assert updated.json() == {
        "capacity": 8,
        "hearts_required": 2,
        "sound_effects_enabled": not sound_effects_enabled,
        "background_music_enabled": not background_music_enabled,
        "movement_speed": "1",
        "countdown_speed": "1",
    }
    persisted = store.get_tournament(str(tournament["tournament_code"]))
    assert persisted.sound_effects_enabled is (not sound_effects_enabled)
    assert persisted.background_music_enabled is (not background_music_enabled)


def test_audio_preferences_reject_non_boolean_values() -> None:
    client = TestClient(create_app(store=InMemoryTournamentStore()))
    response = client.post(
        "/v1/tournaments",
        json={
            "capacity": 8,
            "hearts_required": 2,
            "sound_effects_enabled": "true",
            "background_music_enabled": False,
        },
    )
    assert response.status_code == 422


def test_postgres_rule_document_round_trips_independent_audio_preferences() -> None:
    rules = PostgresTournamentStore._rules(
        2,
        sound_effects_enabled=False,
        background_music_enabled=True,
    )
    tournament = PostgresTournamentStore._record((uuid4(), "RPS-AUDIO", "lobby", 8, rules))
    assert tournament.sound_effects_enabled is False
    assert tournament.background_music_enabled is True


def test_admin_authorization_is_room_scoped_and_limits_invalid_credentials_before_authentication() -> None:
    client = TestClient(create_app(store=InMemoryTournamentStore()))
    first = create_tournament(client)
    second = create_tournament(client)
    player = join_tournament(client, str(first["tournament_code"]), "Vitor")
    first_code = str(first["tournament_code"])

    assert client.get(f"/v1/tournaments/{first_code}/admin/participants", headers=bearer(str(player["player_access_token"]))).status_code == 403
    assert client.get(f"/v1/tournaments/{first_code}/admin/participants", headers=bearer(str(second["organizer_access_token"]))).status_code == 403
    assert client.get(f"/v1/tournaments/{first_code}/admin/participants", headers=bearer(str(first["organizer_access_token"]))).status_code == 200

    for _ in range(17):  # Three administrative requests above consumed the IP budget.
        response = client.get(f"/v1/tournaments/{first_code}/admin/participants", headers=bearer("invalid"))
        assert response.status_code == 401
    assert client.get(f"/v1/tournaments/{first_code}/admin/participants", headers=bearer("invalid")).status_code == 429


def test_organizer_participant_list_exposes_membership_status_and_removal_history() -> None:
    client = TestClient(create_app(store=InMemoryTournamentStore()))
    tournament = create_tournament(client)
    code = str(tournament["tournament_code"])
    organizer_headers = bearer(str(tournament["organizer_access_token"]))

    player = join_tournament(client, code, "Status player")
    player_headers = bearer(str(player["player_access_token"]))
    initial = client.get(f"/v1/tournaments/{code}/admin/participants", headers=organizer_headers)
    assert initial.status_code == 200
    assert initial.json()["participants"] == [
        {
            "player_id": player["player"]["player_id"],
            "display_name": "Status player",
            "animal_id": "tiger",
            "ready": False,
            "strategy_locked": False,
            "membership_status": "joined",
            "removed": False,
        }
    ]

    assert client.put(f"/v1/tournaments/{code}/players/me/strategy", json=strategy_payload(), headers=player_headers).status_code == 204
    configuring = client.get(f"/v1/tournaments/{code}/admin/participants", headers=organizer_headers).json()["participants"][0]
    assert configuring["membership_status"] == "configuring_strategy"

    assert client.post(f"/v1/tournaments/{code}/players/me/ready", json={}, headers=player_headers).status_code == 204
    ready = client.get(f"/v1/tournaments/{code}/admin/participants", headers=organizer_headers).json()["participants"][0]
    assert ready["membership_status"] == "ready"

    assert client.delete(f"/v1/tournaments/{code}/admin/players/{player['player']['player_id']}", headers=organizer_headers).status_code == 204
    removed = client.get(f"/v1/tournaments/{code}/admin/participants", headers=organizer_headers).json()["participants"][0]
    assert removed["membership_status"] == "removed"
    assert removed["removed"] is True


def test_join_errors_are_neutral_for_invalid_and_closed_codes() -> None:
    client = TestClient(create_app(store=InMemoryTournamentStore()))
    unavailable = client.post(
        "/v1/tournaments/join",
        json={"tournament_code": "RPS-AAAAAAAAAAAAAAAA", "display_name": "A", "animal_id": "tiger"},
    )
    tournament = create_tournament(client)
    code = str(tournament["tournament_code"])
    closed = client.post(
        f"/v1/tournaments/{code}/admin/close-registration",
        json={},
        headers=bearer(str(tournament["organizer_access_token"])),
    )
    assert closed.status_code == 204
    unavailable_after_close = client.post(
        "/v1/tournaments/join",
        json={"tournament_code": code, "display_name": "A", "animal_id": "tiger"},
    )
    assert (unavailable.status_code, unavailable.json()) == (unavailable_after_close.status_code, unavailable_after_close.json())


def test_strategy_requires_canonical_tied_with_conditions_and_rejects_forged_official_state() -> None:
    client = TestClient(create_app(store=InMemoryTournamentStore()))
    tournament = create_tournament(client)
    code = str(tournament["tournament_code"])
    player = join_tournament(client, code, "Vitor")
    headers = bearer(str(player["player_access_token"]))

    legacy = strategy_payload()
    legacy["tied_on_rock"] = legacy.pop("tied_with_rock")
    assert client.put(f"/v1/tournaments/{code}/players/me/strategy", json=legacy, headers=headers).status_code == 422
    assert client.put(f"/v1/tournaments/{code}/players/me/strategy", json=strategy_payload(), headers=headers).status_code == 204

    forged_start = client.post(
        f"/v1/tournaments/{code}/admin/start",
        json={"winner": "attacker", "hearts_remaining": 99, "bracket": []},
        headers=bearer(str(tournament["organizer_access_token"])),
    )
    assert forged_start.status_code == 422


def test_official_start_invokes_engine_from_server_snapshot_locks_strategies_and_persists_snapshot() -> None:
    store = InMemoryTournamentStore()
    client = TestClient(create_app(store=store))
    tournament = create_tournament(client)
    code = str(tournament["tournament_code"])
    first = ready_player(client, code, "Vitor")
    second = ready_player(client, code, "Benjamin")

    started = client.post(f"/v1/tournaments/{code}/admin/start", json={}, headers=bearer(str(tournament["organizer_access_token"])))
    assert started.status_code == 200
    body = started.json()
    assert body["tournament_id"] == tournament["tournament_id"]
    assert body["state_reference"] == f"{tournament['tournament_id']}:v1"

    record = store.get_tournament(code)
    assert record.started and not record.registration_open
    assert record.official_state_reference == body["state_reference"]
    assert record.official_state_snapshot is not None
    assert record.official_state_snapshot["schema_version"] == 3
    assert record.official_state_snapshot["kind"] == "tournament_state"
    assert record.official_state_snapshot["tournament_id"] == tournament["tournament_id"]
    assert {player["player"]["player_id"] for player in (first, second)} == {
        competitor["player_id"] for competitor in record.official_state_snapshot["competitors"]
    }
    assert tournament_state_from_snapshot(record.official_state_snapshot).tournament_id == tournament["tournament_id"]
    assert client.put(
        f"/v1/tournaments/{code}/players/me/strategy",
        json=strategy_payload(),
        headers=bearer(str(first["player_access_token"])),
    ).status_code == 409


def test_start_requires_two_confirmed_players_before_engine_invocation() -> None:
    client = TestClient(create_app(store=InMemoryTournamentStore()))
    tournament = create_tournament(client)
    code = str(tournament["tournament_code"])
    ready_player(client, code, "Vitor")
    response = client.post(f"/v1/tournaments/{code}/admin/start", json={}, headers=bearer(str(tournament["organizer_access_token"])))
    assert response.status_code == 409
    assert response.json()["detail"] == "At least two confirmed participants are required."


def test_training_uses_engine_state_isolated_from_the_official_tournament_and_ends_at_start() -> None:
    store = InMemoryTournamentStore()
    client = TestClient(create_app(store=store))
    tournament = create_tournament(client)
    code = str(tournament["tournament_code"])
    first = ready_player(client, code, "Vitor")
    ready_player(client, code, "Benjamin")
    headers = bearer(str(first["player_access_token"]))

    first_turn = client.post(f"/v1/tournaments/{code}/training/choice", json={"move": "rock"}, headers=headers)
    assert first_turn.status_code == 200
    second_turn = client.post(f"/v1/tournaments/{code}/training/choice", json={"move": "rock"}, headers=headers)
    assert second_turn.status_code == 200
    assert first_turn.json()["training_id"] == second_turn.json()["training_id"]
    assert len(second_turn.json()["state"]["rounds"]) == 2
    record = store.get_tournament(code)
    assert record.official_state_snapshot is None
    assert first["player"]["player_id"] in record.training_sessions

    assert client.post(f"/v1/tournaments/{code}/training/reset", headers=headers).status_code == 204
    assert first["player"]["player_id"] not in record.training_sessions
    fresh_turn = client.post(f"/v1/tournaments/{code}/training/choice", json={"move": "paper"}, headers=headers)
    assert fresh_turn.status_code == 200
    assert fresh_turn.json()["training_id"] != first_turn.json()["training_id"]
    assert len(fresh_turn.json()["state"]["rounds"]) == 1

    assert client.post(f"/v1/tournaments/{code}/admin/start", json={}, headers=bearer(str(tournament["organizer_access_token"]))).status_code == 200
    assert not record.training_sessions
    assert client.post(f"/v1/tournaments/{code}/training/choice", json={"move": "rock"}, headers=headers).status_code == 409


def test_guest_training_is_server_calculated_without_creating_a_tournament() -> None:
    store = InMemoryTournamentStore()
    client = TestClient(create_app(store=store))
    intent = {"move": "rock", "hearts_required": 5, "strategy": strategy_payload()}
    first = client.post("/v1/training/guest/choice", json=intent)
    assert first.status_code == 200
    assert first.json()["state"]["initial_hearts"] == 5
    assert first.json()["state"]["manual_hearts"] in {4, 5}
    assert first.json()["state"]["character_hearts"] in {4, 5}
    assert 5 in {
        first.json()["state"]["manual_hearts"],
        first.json()["state"]["character_hearts"],
    }
    second = client.post(
        "/v1/training/guest/choice",
        json={**intent, "move": "paper"},
        headers={"X-Training-Session": first.json()["training_id"]},
    )
    assert second.status_code == 200
    assert second.json()["training_id"] == first.json()["training_id"]
    assert len(second.json()["state"]["rounds"]) == 2
    assert not store._tournaments

    assert client.post("/v1/training/guest/choice", json={**intent, "hearts_required": 0}).status_code == 422
    assert client.post("/v1/training/guest/choice", json={**intent, "hearts_required": 6}).status_code == 422
    assert client.post("/v1/training/guest/choice", json={"move": "rock", "hearts_required": 2}).status_code == 422


def test_cors_allows_only_the_explicit_local_origin() -> None:
    client = TestClient(create_app(store=InMemoryTournamentStore()))
    allowed = client.options(
        "/v1/tournaments",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
    )
    denied = client.options(
        "/v1/tournaments",
        headers={"Origin": "https://attacker.invalid", "Access-Control-Request-Method": "POST"},
    )
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-origin" not in denied.headers


def test_api_security_headers_prevent_caching_of_capability_responses() -> None:
    client = TestClient(create_app(store=InMemoryTournamentStore()))
    response = client.post("/v1/tournaments", json={"capacity": 8, "hearts_required": 2})

    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store, private, max-age=0"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_api_rejects_declared_bodies_over_the_public_boundary_limit() -> None:
    client = TestClient(create_app(store=InMemoryTournamentStore()))

    response = client.post(
        "/v1/tournaments",
        content=b"{}",
        headers={"Content-Length": str(64 * 1024 + 1), "Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert response.headers["cache-control"] == "no-store, private, max-age=0"


def test_production_disables_interactive_api_docs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://rps.example")
    client = TestClient(create_app(store=InMemoryTournamentStore()))

    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_every_admin_mutation_rejects_missing_and_cross_tournament_capabilities() -> None:
    client = TestClient(create_app(store=InMemoryTournamentStore()))
    first, second = create_tournament(client), create_tournament(client)
    code = str(first["tournament_code"])
    cross_headers = bearer(str(second["organizer_access_token"]))
    requests = (
        ("patch", f"/v1/tournaments/{code}/admin/configuration", {"capacity": 8, "hearts_required": 2}),
        ("post", f"/v1/tournaments/{code}/admin/close-registration", {}),
        ("delete", f"/v1/tournaments/{code}/admin/players/{uuid4()}", None),
        ("post", f"/v1/tournaments/{code}/admin/start", {}),
        ("post", f"/v1/tournaments/{code}/admin/access/revoke", {}),
    )

    for method, path, payload in requests:
        invoke = getattr(client, method)
        missing = invoke(path, **({"json": payload} if payload is not None else {}))
        foreign = invoke(path, headers=cross_headers, **({"json": payload} if payload is not None else {}))
        assert missing.status_code == 401
        assert foreign.status_code == 403


@pytest.mark.parametrize("display_name", ("<script>alert(1)</script>", "<img src=x onerror=alert(1)>", "مرحبا 🐼 中文"))
def test_participant_names_are_preserved_as_plain_validated_text(display_name: str) -> None:
    client = TestClient(create_app(store=InMemoryTournamentStore()))
    tournament = create_tournament(client)
    joined = join_tournament(client, str(tournament["tournament_code"]), display_name)

    assert joined["player"]["display_name"] == display_name


def test_rate_limits_are_operation_specific_and_recover_after_the_window() -> None:
    now = [0.0]
    limiter = SlidingWindowRateLimiter(clock=lambda: now[0])
    limit = RateLimit(max_requests=2, window_seconds=10)
    limiter.check("join", "client-a", limit)
    limiter.check("join", "client-a", limit)
    try:
        limiter.check("join", "client-a", limit)
    except RateLimitExceeded as error:
        assert error.retry_after_seconds == 11
    else:
        raise AssertionError("Expected the third request to be limited")
    now[0] = 10.0
    limiter.check("join", "client-a", limit)
    limiter.check("admin", "client-a", limit)


def test_shared_limiter_failure_is_explicit_and_never_downgrades_to_local_memory() -> None:
    def unavailable_connection():
        raise OSError("database unavailable")

    limiter = PostgresFixedWindowRateLimiter(
        "postgresql://unit-test.invalid/rps_unit", connect=unavailable_connection
    )
    with pytest.raises(RateLimiterUnavailable):
        limiter.check("join", "ip:127.0.0.1", RateLimit(max_requests=1, window_seconds=60))


def test_http_fails_closed_when_an_injected_shared_limiter_is_unavailable() -> None:
    class UnavailableLimiter:
        def check(self, operation: str, subject: str, limit: RateLimit) -> None:
            raise RateLimiterUnavailable("database unavailable")

    client = TestClient(create_app(store=InMemoryTournamentStore(), limiter=UnavailableLimiter()))
    response = client.post("/v1/tournaments", json={"capacity": 8, "hearts_required": 2})
    assert response.status_code == 503
    assert response.json()["detail"] == "Request protection is temporarily unavailable."
    assert response.headers["retry-after"] == "5"


def test_organizer_expiry_and_revocation_are_enforced() -> None:
    now = [datetime(2026, 1, 1, tzinfo=UTC)]
    store = InMemoryTournamentStore(now=lambda: now[0], organizer_token_ttl=timedelta(minutes=1))
    tournament, token = store.create_tournament(8, 2)
    assert store.authorize_organizer(tournament.code, token) is tournament
    now[0] += timedelta(minutes=1)
    try:
        store.authorize_organizer(tournament.code, token)
    except Exception as error:
        assert getattr(error, "status_code") == 401
    else:
        raise AssertionError("Expected expired organizer credential to fail")

    fresh_tournament, fresh_token = store.create_tournament(8, 2)
    store.revoke_organizer_access(fresh_tournament)
    try:
        store.authorize_organizer(fresh_tournament.code, fresh_token)
    except Exception as error:
        assert getattr(error, "status_code") == 401
    else:
        raise AssertionError("Expected revoked organizer credential to fail")

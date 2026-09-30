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


def test_codes_are_opaque_and_nonsequential() -> None:
    codes = {generate_tournament_code() for _ in range(100)}
    assert len(codes) == 100
    assert all(code.startswith("RPS-") and len(code) == 20 for code in codes)


def test_tournament_uses_uuid_internally_and_code_only_as_public_access() -> None:
    client = TestClient(create_app(store=InMemoryTournamentStore()))
    tournament = create_tournament(client)
    assert len(str(tournament["tournament_id"])) == 36
    assert tournament["tournament_code"].startswith("RPS-")
    player = join_tournament(client, str(tournament["tournament_code"]), "Vitor")
    assert player["tournament_id"] == tournament["tournament_id"]


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
    assert record.official_state_snapshot["schema_version"] == 1
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

    assert client.post(f"/v1/tournaments/{code}/admin/start", json={}, headers=bearer(str(tournament["organizer_access_token"]))).status_code == 200
    assert not record.training_sessions
    assert client.post(f"/v1/tournaments/{code}/training/choice", json={"move": "rock"}, headers=headers).status_code == 409


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

"""Opt-in PostgreSQL proof for the authoritative HTTP start path.

Set ``RPS_TEST_DATABASE_URL`` to an isolated libpq URL.  This suite creates
only random UUID/code aggregates and never truncates shared tables.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import create_app
from app.security import PostgresFixedWindowRateLimiter, RateLimit, RateLimitExceeded
from rps_game_engine import tournament_state_from_snapshot
from realtime.dsn import to_psycopg_dsn, to_sqlalchemy_url
from realtime.protocol import official_channel


ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS = ROOT / "database" / "migrations"
TEST_DATABASE_URL = os.environ.get("RPS_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="RPS_TEST_DATABASE_URL is not configured",
)


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


@pytest.fixture(scope="module", autouse=True)
def migrated_postgres() -> None:
    pytest.importorskip("psycopg")
    environment = dict(os.environ, DATABASE_URL=to_sqlalchemy_url(str(TEST_DATABASE_URL)))
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=MIGRATIONS,
        env=environment,
        check=True,
    )


@pytest.fixture
def durable_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DATABASE_URL", str(TEST_DATABASE_URL))
    monkeypatch.setenv("REALTIME_TICKET_SIGNING_KEY", "postgres-e2e-test-signing-key-not-for-production")
    # This suite requires an isolated RPS_TEST_DATABASE_URL.  Clearing only
    # the aggregate root makes outbox-worker assertions deterministic and
    # prevents an old event from a prior integration case being claimed first.
    with connection() as database, database.cursor() as cursor:
        cursor.execute("TRUNCATE TABLE tournaments CASCADE; TRUNCATE TABLE shared_rate_limit_buckets")
    return TestClient(create_app())


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_room(client: TestClient) -> dict[str, object]:
    response = client.post("/v1/tournaments", json={"capacity": 8, "hearts_required": 2})
    assert response.status_code == 201, response.text
    return response.json()


def ready_player(client: TestClient, room: dict[str, object], display_name: str) -> dict[str, object]:
    joined = client.post(
        "/v1/tournaments/join",
        json={"tournament_code": room["tournament_code"], "display_name": display_name, "animal_id": "tiger"},
    )
    assert joined.status_code == 201, joined.text
    player = joined.json()
    headers = bearer(str(player["player_access_token"]))
    code = str(room["tournament_code"])
    assert client.put(f"/v1/tournaments/{code}/players/me/strategy", json=strategy_payload(), headers=headers).status_code == 204
    assert client.post(f"/v1/tournaments/{code}/players/me/ready", json={}, headers=headers).status_code == 204
    return player


def connection():
    import psycopg

    return psycopg.connect(to_psycopg_dsn(str(TEST_DATABASE_URL)))


def test_shared_postgres_limiter_is_atomic_across_instances_and_recovers_after_expiry() -> None:
    """Two API instances must consume one shared counter, not two local ones."""
    first = PostgresFixedWindowRateLimiter(str(TEST_DATABASE_URL))
    second = PostgresFixedWindowRateLimiter(str(TEST_DATABASE_URL))
    limit = RateLimit(max_requests=2, window_seconds=60)
    subject = f"ip:rate-limit-e2e-{uuid4()}"

    first.check("join", subject, limit)  # below the limit
    second.check("join", subject, limit)  # exactly at the limit, across instance two
    with pytest.raises(RateLimitExceeded) as limited:
        first.check("join", subject, limit)
    assert limited.value.retry_after_seconds >= 1

    with connection() as database, database.cursor() as cursor:
        cursor.execute(
            "UPDATE shared_rate_limit_buckets SET expires_at = CURRENT_TIMESTAMP - INTERVAL '1 second' "
            "WHERE operation = 'join' AND subject_hash = %s",
            (first._subject_key(subject),),
        )
    second.check("join", subject, limit)  # expired buckets receive a fresh budget
    with connection() as database, database.cursor() as cursor:
        cursor.execute(
            "SELECT request_count, expires_at > CURRENT_TIMESTAMP FROM shared_rate_limit_buckets "
            "WHERE operation = 'join' AND subject_hash = %s",
            (first._subject_key(subject),),
        )
        assert cursor.fetchone() == (1, True)


def test_http_engine_snapshot_transition_event_and_outbox_are_one_durable_chain(durable_client: TestClient) -> None:
    room = create_room(durable_client)
    first = ready_player(durable_client, room, "Vitor")
    second = ready_player(durable_client, room, "Benjamin")
    code = str(room["tournament_code"])
    started = durable_client.post(
        f"/v1/tournaments/{code}/admin/start",
        json={},
        headers={**bearer(str(room["organizer_access_token"])), "Idempotency-Key": str(uuid4())},
    )
    assert started.status_code == 200, started.text
    body = started.json()
    assert body["status"] == "started"
    assert body["tournament_id"] == room["tournament_id"]
    assert body["state_version"] == 1

    with connection() as database, database.cursor() as cursor:
        cursor.execute(
            "SELECT status, state_version, next_event_sequence FROM tournaments WHERE id = %s",
            (room["tournament_id"],),
        )
        assert cursor.fetchone() == ("running", 1, 1)
        cursor.execute(
            "SELECT state_document FROM official_state_snapshots WHERE tournament_id = %s AND state_version = 1",
            (room["tournament_id"],),
        )
        snapshot = cursor.fetchone()[0]
        restored = tournament_state_from_snapshot(snapshot)
        assert restored.tournament_id == room["tournament_id"]
        cursor.execute("SELECT count(*) FROM official_player_snapshots WHERE tournament_id = %s", (room["tournament_id"],))
        assert cursor.fetchone()[0] == 2
        cursor.execute("SELECT count(*) FROM official_transitions WHERE tournament_id = %s", (room["tournament_id"],))
        assert cursor.fetchone()[0] == 1
        cursor.execute("SELECT count(*) FROM official_game_events WHERE tournament_id = %s", (room["tournament_id"],))
        assert cursor.fetchone()[0] == 1
        cursor.execute("SELECT count(*) FROM realtime_outbox WHERE tournament_id = %s AND published_at IS NULL", (room["tournament_id"],))
        assert cursor.fetchone()[0] == 1
    assert {first["player"]["player_id"], second["player"]["player_id"]} == {
        competitor["player_id"] for competitor in snapshot["competitors"]
    }


def test_persistent_capabilities_are_hashed_expire_revoke_and_stay_room_scoped(durable_client: TestClient) -> None:
    first_room, second_room = create_room(durable_client), create_room(durable_client)
    first_player = ready_player(durable_client, first_room, "Scoped")
    second_player = ready_player(durable_client, second_room, "Other room")
    first_code = str(first_room["tournament_code"])
    second_code = str(second_room["tournament_code"])

    assert durable_client.get(f"/v1/tournaments/{first_code}/players/me", headers=bearer(str(first_player["player_access_token"]))).status_code == 200
    assert durable_client.get(f"/v1/tournaments/{first_code}/players/me", headers=bearer(str(second_player["player_access_token"]))).status_code == 403
    assert durable_client.get(f"/v1/tournaments/{second_code}/admin/participants", headers=bearer(str(first_room["organizer_access_token"]))).status_code == 403

    with connection() as database, database.cursor() as cursor:
        cursor.execute(
            "SELECT secret_hash FROM tournament_access_capabilities WHERE tournament_id = %s AND subject_id = %s",
            (first_room["tournament_id"], first_player["player"]["player_id"]),
        )
        persisted_hash = cursor.fetchone()[0]
        assert len(persisted_hash) == 64
        assert persisted_hash != first_player["player_access_token"]
        cursor.execute(
            "UPDATE tournament_access_capabilities "
            "SET issued_at = CURRENT_TIMESTAMP - INTERVAL '2 seconds', "
            "expires_at = CURRENT_TIMESTAMP - INTERVAL '1 second' "
            "WHERE tournament_id = %s AND subject_id = %s",
            (first_room["tournament_id"], first_player["player"]["player_id"]),
        )
    assert durable_client.get(f"/v1/tournaments/{first_code}/players/me", headers=bearer(str(first_player["player_access_token"]))).status_code == 401

    revoke = durable_client.post(
        f"/v1/tournaments/{second_code}/admin/access/revoke",
        json={},
        headers=bearer(str(second_room["organizer_access_token"])),
    )
    assert revoke.status_code == 204
    assert durable_client.get(
        f"/v1/tournaments/{second_code}/admin/participants",
        headers=bearer(str(second_room["organizer_access_token"])),
    ).status_code == 401


def test_duplicate_start_is_idempotent_under_real_postgres_concurrency(durable_client: TestClient) -> None:
    room = create_room(durable_client)
    ready_player(durable_client, room, "First")
    ready_player(durable_client, room, "Second")
    code, command_key = str(room["tournament_code"]), str(uuid4())
    headers = {**bearer(str(room["organizer_access_token"])), "Idempotency-Key": command_key}

    def start_once() -> tuple[int, dict[str, object]]:
        response = TestClient(durable_client.app).post(f"/v1/tournaments/{code}/admin/start", json={}, headers=headers)
        return response.status_code, response.json()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(lambda _: start_once(), range(2)))
    assert [status_code for status_code, _ in results] == [200, 200]
    assert results[0][1] == results[1][1]

    with connection() as database, database.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM idempotency_commands WHERE tournament_id = %s", (room["tournament_id"],))
        assert cursor.fetchone()[0] == 1
        cursor.execute("SELECT count(*) FROM official_transitions WHERE tournament_id = %s", (room["tournament_id"],))
        assert cursor.fetchone()[0] == 1
        cursor.execute("SELECT count(*) FROM realtime_outbox WHERE tournament_id = %s", (room["tournament_id"],))
        assert cursor.fetchone()[0] == 1


def test_engine_rejection_rolls_back_start_command_and_official_rows(durable_client: TestClient) -> None:
    room = create_room(durable_client)
    ready_player(durable_client, room, "Valid")
    invalid_player = ready_player(durable_client, room, "Invalid")
    with connection() as database, database.cursor() as cursor:
        cursor.execute(
            "UPDATE player_strategies SET strategy_document = '{\"not\": \"an engine strategy\"}'::jsonb WHERE tournament_id = %s AND member_id = %s",
            (room["tournament_id"], invalid_player["player"]["player_id"]),
        )
    response = durable_client.post(
        f"/v1/tournaments/{room['tournament_code']}/admin/start",
        json={},
        headers={**bearer(str(room["organizer_access_token"])), "Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 503
    with connection() as database, database.cursor() as cursor:
        cursor.execute("SELECT status, state_version FROM tournaments WHERE id = %s", (room["tournament_id"],))
        assert cursor.fetchone() == ("lobby", 0)
        for table in ("idempotency_commands", "official_transitions", "official_state_snapshots", "official_game_events", "realtime_outbox"):
            cursor.execute(f"SELECT count(*) FROM {table} WHERE tournament_id = %s", (room["tournament_id"],))
            assert cursor.fetchone()[0] == 0


def test_committed_outbox_is_published_then_replayed_to_authenticated_websocket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise Backend → PostgreSQL → outbox worker → WebSocket → client."""
    monkeypatch.setenv("DATABASE_URL", str(TEST_DATABASE_URL))
    monkeypatch.setenv("REALTIME_TICKET_SIGNING_KEY", "postgres-e2e-test-signing-key-not-for-production")
    with connection() as database, database.cursor() as cursor:
        cursor.execute("TRUNCATE TABLE tournaments CASCADE")
    with TestClient(create_app()) as client:
        room = create_room(client)
        ready_player(client, room, "Live one")
        ready_player(client, room, "Live two")
        code = str(room["tournament_code"])
        ticket_response = client.post(
            f"/v1/tournaments/{code}/realtime/ticket",
            headers=bearer(str(room["organizer_access_token"])),
        )
        assert ticket_response.status_code == 200, ticket_response.text

        started = client.post(
            f"/v1/tournaments/{code}/admin/start",
            json={},
            headers={**bearer(str(room["organizer_access_token"])), "Idempotency-Key": str(uuid4())},
        )
        assert started.status_code == 200, started.text

        deadline = time.monotonic() + 3
        published_at = None
        while time.monotonic() < deadline:
            with connection() as database, database.cursor() as cursor:
                cursor.execute(
                    "SELECT published_at FROM realtime_outbox WHERE tournament_id = %s",
                    (room["tournament_id"],),
                )
                row = cursor.fetchone()
            published_at = row[0] if row else None
            if published_at is not None:
                break
            time.sleep(0.05)
        assert published_at is not None, "the committed outbox event was not consumed by the worker"

        channel = official_channel(str(room["tournament_id"]))
        with client.websocket_connect("/v1/realtime", headers={"origin": "http://localhost:3000"}) as socket:
            socket.send_json({"type": "authenticate", "ticket": ticket_response.json()["ticket"], "channel": channel})
            assert socket.receive_json() == {"type": "subscribed", "channel": channel}
            socket.send_json({"type": "resume", "afterSequence": 0})
            event = socket.receive_json()
        assert event["type"] == "official-event"
        assert event["tournamentId"] == room["tournament_id"]
        assert event["sequence"] == 1
        assert event["eventType"] == "tournament_started"


def test_persisted_ticket_rejects_cross_room_expiry_and_capability_revocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", str(TEST_DATABASE_URL))
    monkeypatch.setenv("REALTIME_TICKET_SIGNING_KEY", "postgres-e2e-test-signing-key-not-for-production")
    with connection() as database, database.cursor() as cursor:
        cursor.execute("TRUNCATE TABLE tournaments CASCADE")
    with TestClient(create_app()) as client:
        first, second = create_room(client), create_room(client)
        first_code = str(first["tournament_code"])
        ticket = client.post(
            f"/v1/tournaments/{first_code}/realtime/ticket",
            headers=bearer(str(first["organizer_access_token"])),
        ).json()["ticket"]

        def expect_close(channel: str) -> None:
            with client.websocket_connect("/v1/realtime", headers={"origin": "http://localhost:3000"}) as socket:
                socket.send_json({"type": "authenticate", "ticket": ticket, "channel": channel})
                with pytest.raises(WebSocketDisconnect) as closed:
                    socket.receive_json()
            assert closed.value.code == 1008

        # A valid signed token cannot subscribe to a different UUID channel.
        expect_close(official_channel(str(second["tournament_id"])))

        with connection() as database, database.cursor() as cursor:
            cursor.execute(
                """UPDATE realtime_access_tickets
                      SET issued_at = CURRENT_TIMESTAMP - INTERVAL '10 minutes',
                          not_before = CURRENT_TIMESTAMP - INTERVAL '5 minutes',
                          expires_at = CURRENT_TIMESTAMP - INTERVAL '1 minute'
                    WHERE tournament_id = %s""",
                (first["tournament_id"],),
            )
        expect_close(official_channel(str(first["tournament_id"])))

        # Issue a fresh ticket then revoke its source capability; the DB join
        # in PostgresRealtimeStore must invalidate it immediately.
        fresh_ticket_response = client.post(
            f"/v1/tournaments/{first_code}/realtime/ticket",
            headers=bearer(str(first["organizer_access_token"])),
        )
        assert fresh_ticket_response.status_code == 200
        ticket = fresh_ticket_response.json()["ticket"]
        revoked = client.post(
            f"/v1/tournaments/{first_code}/admin/access/revoke",
            json={},
            headers=bearer(str(first["organizer_access_token"])),
        )
        assert revoked.status_code == 204
        expect_close(official_channel(str(first["tournament_id"])))

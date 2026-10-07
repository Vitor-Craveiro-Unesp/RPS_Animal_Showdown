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
from app.engine_gateway import GameEngineAdapter
from app.postgres_store import PostgresTournamentStore
from app.security import PostgresFixedWindowRateLimiter, RateLimit, RateLimitExceeded
from rps_game_engine import tournament_state_from_snapshot
from realtime.dsn import to_psycopg_dsn, to_sqlalchemy_url
from realtime.protocol import official_channel
from realtime.postgres import PostgresOutboxWorker, PostgresRealtimeStore


ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS = ROOT / "database" / "migrations"
TEST_DATABASE_URL = os.environ.get("RPS_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="RPS_TEST_DATABASE_URL is not configured",
)


def strategy_payload(move: str = "rock") -> dict[str, object]:
    distribution = {"rock": 0, "paper": 0, "scissors": 0}
    if move == "uniform":
        distribution = {"rock": 33, "paper": 33, "scissors": 34}
    else:
        distribution[move] = 100
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


def ready_player(client: TestClient, room: dict[str, object], display_name: str, move: str = "rock") -> dict[str, object]:
    joined = client.post(
        "/v1/tournaments/join",
        json={"tournament_code": room["tournament_code"], "display_name": display_name, "animal_id": "tiger"},
    )
    assert joined.status_code == 201, joined.text
    player = joined.json()
    headers = bearer(str(player["player_access_token"]))
    code = str(room["tournament_code"])
    assert client.put(f"/v1/tournaments/{code}/players/me/strategy", json=strategy_payload(move), headers=headers).status_code == 204
    assert client.post(f"/v1/tournaments/{code}/players/me/ready", json={}, headers=headers).status_code == 204
    return player


def test_organizer_sees_strategy_draft_separately_from_ready(durable_client: TestClient) -> None:
    room = create_room(durable_client)
    code = str(room["tournament_code"])
    joined = durable_client.post(
        "/v1/tournaments/join",
        json={"tournament_code": code, "display_name": "Draft player", "animal_id": "tiger"},
    )
    assert joined.status_code == 201, joined.text
    player = joined.json()
    player_headers = bearer(str(player["player_access_token"]))
    organizer_headers = bearer(str(room["organizer_access_token"]))
    path = f"/v1/tournaments/{code}/admin/participants"
    assert durable_client.put(
        f"/v1/tournaments/{code}/players/me/strategy",
        json=strategy_payload("uniform"), headers=player_headers,
    ).status_code == 204
    draft = durable_client.get(path, headers=organizer_headers).json()["participants"]
    assert draft[0]["membership_status"] == "configuring_strategy"
    assert draft[0]["ready"] is False
    assert durable_client.post(
        f"/v1/tournaments/{code}/players/me/ready", json={}, headers=player_headers,
    ).status_code == 204
    confirmed = durable_client.get(path, headers=organizer_headers).json()["participants"]
    assert confirmed[0]["membership_status"] == "ready"
    assert confirmed[0]["ready"] is True


def test_practice_can_restart_without_mutating_the_durable_tournament(durable_client: TestClient) -> None:
    room = create_room(durable_client)
    first = ready_player(durable_client, room, "Practice player")
    ready_player(durable_client, room, "Official opponent")
    code = str(room["tournament_code"])
    headers = bearer(str(first["player_access_token"]))

    initial = durable_client.post(f"/v1/tournaments/{code}/training/choice", json={"move": "rock"}, headers=headers)
    assert initial.status_code == 200, initial.text
    assert len(initial.json()["state"]["rounds"]) == 1
    assert durable_client.post(f"/v1/tournaments/{code}/training/reset", headers=headers).status_code == 204
    restarted = durable_client.post(f"/v1/tournaments/{code}/training/choice", json={"move": "paper"}, headers=headers)
    assert restarted.status_code == 200, restarted.text
    assert restarted.json()["training_id"] != initial.json()["training_id"]
    assert len(restarted.json()["state"]["rounds"]) == 1

    with connection() as database, database.cursor() as cursor:
        cursor.execute("SELECT status, state_version FROM tournaments WHERE id = %s", (room["tournament_id"],))
        assert cursor.fetchone() == ("lobby", 0)


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
            "SELECT EXTRACT(EPOCH FROM (next_transition_at - updated_at)) "
            "FROM tournaments WHERE id = %s", (room["tournament_id"],),
        )
        assert cursor.fetchone()[0] >= 3
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


def test_durable_competition_reaches_champion_with_bye_ordered_events_and_replay(durable_client: TestClient) -> None:
    room = create_room(durable_client)
    ready_player(durable_client, room, "Rock", "rock")
    ready_player(durable_client, room, "Paper", "paper")
    ready_player(durable_client, room, "Scissors", "scissors")
    code = str(room["tournament_code"])
    started = durable_client.post(
        f"/v1/tournaments/{code}/admin/start", json={},
        headers={**bearer(str(room["organizer_access_token"])), "Idempotency-Key": str(uuid4())},
    )
    assert started.status_code == 200, started.text
    store = PostgresTournamentStore(str(TEST_DATABASE_URL))
    engine = GameEngineAdapter()
    # Three distinct strategies yield six decisive exchanges, including Second Chance.
    for exchange in range(6):
        with connection() as database, database.cursor() as cursor:
            cursor.execute(
                "UPDATE tournaments SET updated_at = CURRENT_TIMESTAMP - INTERVAL '2 seconds', next_transition_at = CURRENT_TIMESTAMP - INTERVAL '2 seconds' WHERE id = %s",
                (room["tournament_id"],),
            )
        assert store.advance_one_running_tournament(engine)
        if exchange == 0:
            live = durable_client.get(
                f"/v1/tournaments/{code}/official-state",
                headers=bearer(str(room["organizer_access_token"])),
            ).json()
            assert live["presentation_state"]["state_version"] == 1
            assert live["presentation_events"]
            assert all("presentationAtMs" in event["payload"] for event in live["presentation_events"])
            assert all("strategy" not in repr(event["payload"]) for event in live["presentation_events"])
        with connection() as database, database.cursor() as cursor:
            cursor.execute("SELECT status FROM tournaments WHERE id = %s", (room["tournament_id"],))
            if cursor.fetchone()[0] == "completed":
                break
    else:
        pytest.fail("Six deterministic rounds did not produce a champion")

    snapshot_response = durable_client.get(
        f"/v1/tournaments/{code}/official-state",
        headers=bearer(str(room["organizer_access_token"])),
    )
    assert snapshot_response.status_code == 200
    public = snapshot_response.json()
    assert public["status"] == "completed" and public["champion_id"] is not None
    assert len(public["completed_rounds"]) == 2  # bracket stages, not RPS exchanges
    assert "strategy" not in snapshot_response.text and "condition" not in snapshot_response.text
    with connection() as database, database.cursor() as cursor:
        cursor.execute(
            "SELECT state_version, next_event_sequence FROM tournaments WHERE id = %s",
            (room["tournament_id"],),
        )
        version, sequence = cursor.fetchone()
        cursor.execute("SELECT count(*) FROM official_state_snapshots WHERE tournament_id = %s", (room["tournament_id"],))
        assert cursor.fetchone()[0] == 1
        cursor.execute(
            "SELECT sequence, event_type FROM official_game_events WHERE tournament_id = %s ORDER BY sequence",
            (room["tournament_id"],),
        )
        rows = cursor.fetchall()
        cursor.execute("SELECT count(*) FROM official_match_rounds WHERE tournament_id = %s", (room["tournament_id"],))
        assert cursor.fetchone()[0] == version - 1
        cursor.execute("SELECT count(*) FROM realtime_outbox WHERE tournament_id = %s", (room["tournament_id"],))
        assert cursor.fetchone()[0] == len(rows)
    assert [row[0] for row in rows] == list(range(1, sequence + 1))
    event_types = [row[1] for row in rows]
    assert {"tournament_started", "player_waiting", "second_chance_selected", "second_chance_completed", "match_started", "round_resolved", "heart_lost",
            "player_eliminated", "match_completed", "player_advanced", "champion"} <= set(event_types)
    assert event_types[-1] == "champion"
    import asyncio
    replayed = asyncio.run(PostgresRealtimeStore(str(TEST_DATABASE_URL)).events_after(str(room["tournament_id"]), 1))
    assert [(event.sequence, event.event_type) for event in replayed] == rows[1:]
    publisher = PostgresOutboxWorker(str(TEST_DATABASE_URL), worker_id=f"integration-{uuid4()}")
    claimed_sequences = []
    for _ in rows:
        event = publisher._claim_one()
        assert event is not None
        claimed_sequences.append(event.sequence)
        publisher._mark_published(event.event_id)
    assert claimed_sequences == list(range(1, sequence + 1))
    assert not store.advance_one_running_tournament(engine)


@pytest.mark.parametrize("count", [3, 5, 7, 9, 4])
def test_second_chance_durable_restart_concurrency_and_replay(durable_client: TestClient, count: int) -> None:
    response = durable_client.post("/v1/tournaments", json={"capacity": 16, "hearts_required": 2})
    assert response.status_code == 201
    room = response.json()
    players = [ready_player(durable_client, room, f"Player {i}", "uniform") for i in range(count)]
    code = room["tournament_code"]
    headers = bearer(room["organizer_access_token"])
    assert durable_client.post(f"/v1/tournaments/{code}/admin/start", json={},
        headers={**headers, "Idempotency-Key": str(uuid4())}).status_code == 200
    for _ in range(250):
        with connection() as database, database.cursor() as cursor:
            cursor.execute("UPDATE tournaments SET updated_at = CURRENT_TIMESTAMP - INTERVAL '2 seconds', next_transition_at = CURRENT_TIMESTAMP - INTERVAL '2 seconds' WHERE id = %s", (room["tournament_id"],))
        # Fresh worker/repository/engine at every exchange: restart from DB only.
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: PostgresTournamentStore(str(TEST_DATABASE_URL)).advance_one_running_tournament(GameEngineAdapter()), range(2)))
        assert sorted(results) == [False, True]
        from app.public_state import official_state_view
        with connection() as database, database.cursor() as cursor:
            cursor.execute("SELECT state_document FROM official_state_snapshots WHERE tournament_id = %s", (room["tournament_id"],))
            saved = cursor.fetchone()[0]
        public = official_state_view(PostgresTournamentStore(str(TEST_DATABASE_URL)).get_tournament(code), saved)
        assert all(word not in repr(public) for word in ("strategy", "probabilities", "token"))
        assert all(p["animal_id"] == "tiger" for p in public["players"])
        assert {p["player_id"] for p in public["players"]} == {p["player"]["player_id"] for p in players}
        if public["status"] == "completed":
            break
    else:
        pytest.fail("Tournament did not finish")
    assert sum(p["second_chance"] for p in public["players"]) == count % 2
    assert durable_client.get(f"/v1/tournaments/{code}/official-state", headers=headers).json()["champion_id"] == public["champion_id"]
    rounds = public["completed_rounds"]
    assert sum(len(r["matches"]) for r in rounds) == count - 1 + count % 2 + int(count in (4, 7, 8))
    with connection() as database, database.cursor() as cursor:
        cursor.execute("SELECT sequence, event_type FROM official_game_events WHERE tournament_id = %s ORDER BY sequence", (room["tournament_id"],))
        events = cursor.fetchall()
        cursor.execute("SELECT count(*) FROM official_matches WHERE tournament_id = %s", (room["tournament_id"],))
        assert cursor.fetchone()[0] == count - 1 + count % 2 + int(count in (4, 7, 8))
    assert [s for s, _ in events] == list(range(1, len(events) + 1))
    for name in ("second_chance_selected", "second_chance_match_started", "second_chance_completed"):
        assert sum(t == name for _, t in events) == count % 2
    import asyncio
    cut = next((s for s, t in events if t == "second_chance_selected"), 1)
    replay = asyncio.run(PostgresRealtimeStore(str(TEST_DATABASE_URL)).events_after(room["tournament_id"], cut))
    assert [(e.sequence, e.event_type) for e in replay] == events[cut:]
    # Actual authenticated WebSocket reconnect resumes from the selection cursor.
    with TestClient(create_app()) as reconnected:
        ticket = reconnected.post(f"/v1/tournaments/{code}/realtime/ticket", headers=headers).json()["ticket"]
        channel = official_channel(room["tournament_id"])
        with reconnected.websocket_connect("/v1/realtime", headers={"origin": "http://localhost:3000"}) as socket:
            socket.send_json({"type": "authenticate", "ticket": ticket, "channel": channel})
            assert socket.receive_json()["type"] == "subscribed"
            socket.send_json({"type": "resume", "afterSequence": cut})
            received = socket.receive_json()
            assert received["sequence"] == cut + 1
            assert received["eventType"] == events[cut][1]


def test_long_tie_streak_backs_off_without_losing_round_history(durable_client: TestClient) -> None:
    room = create_room(durable_client)
    ready_player(durable_client, room, "Rock One", "rock")
    ready_player(durable_client, room, "Rock Two", "rock")
    code = str(room["tournament_code"])
    assert durable_client.post(
        f"/v1/tournaments/{code}/admin/start", json={},
        headers={**bearer(str(room["organizer_access_token"])), "Idempotency-Key": str(uuid4())},
    ).status_code == 200
    store = PostgresTournamentStore(str(TEST_DATABASE_URL))
    for _ in range(10):
        with connection() as database, database.cursor() as cursor:
            cursor.execute(
                "UPDATE tournaments SET updated_at = CURRENT_TIMESTAMP - INTERVAL '2 seconds', next_transition_at = CURRENT_TIMESTAMP - INTERVAL '2 seconds' WHERE id = %s",
                (room["tournament_id"],),
            )
        assert store.advance_one_running_tournament(GameEngineAdapter())
    with connection() as database, database.cursor() as cursor:
        cursor.execute(
            "SELECT state_version, EXTRACT(EPOCH FROM (next_transition_at - updated_at)) "
            "FROM tournaments WHERE id = %s", (room["tournament_id"],),
        )
        version, delay = cursor.fetchone()
        assert version == 11 and delay >= 4
        cursor.execute("SELECT count(*) FROM official_state_snapshots WHERE tournament_id = %s", (room["tournament_id"],))
        assert cursor.fetchone()[0] == 1
        cursor.execute("SELECT count(*) FROM official_match_rounds WHERE tournament_id = %s", (room["tournament_id"],))
        assert cursor.fetchone()[0] == 10
        cursor.execute(
            "SELECT public_payload FROM official_game_events WHERE tournament_id = %s "
            "AND event_type = 'round_resolved' ORDER BY sequence DESC LIMIT 1", (room["tournament_id"],),
        )
        event_payload = cursor.fetchone()[0]
        assert len(event_payload["state"]["current_round"]["matches"][0]["rounds"]) == 1
    assert not store.advance_one_running_tournament(GameEngineAdapter())


def test_four_player_bracket_activates_pending_match_then_final(durable_client: TestClient) -> None:
    room = create_room(durable_client)
    ready_player(durable_client, room, "Rock One", "rock")
    ready_player(durable_client, room, "Scissors", "scissors")
    paper = ready_player(durable_client, room, "Paper", "paper")
    ready_player(durable_client, room, "Rock Two", "rock")
    code = str(room["tournament_code"])
    assert durable_client.post(
        f"/v1/tournaments/{code}/admin/start", json={},
        headers={**bearer(str(room["organizer_access_token"])), "Idempotency-Key": str(uuid4())},
    ).status_code == 200
    initial = durable_client.get(
        f"/v1/tournaments/{code}/official-state",
        headers=bearer(str(room["organizer_access_token"])),
    ).json()
    assert [match["status"] for match in initial["current_round"]["matches"]] == ["active", "pending"]

    store = PostgresTournamentStore(str(TEST_DATABASE_URL))
    engine = GameEngineAdapter()
    for _ in range(8):
        with connection() as database, database.cursor() as cursor:
            cursor.execute(
                "UPDATE tournaments SET updated_at = CURRENT_TIMESTAMP - INTERVAL '2 seconds', next_transition_at = CURRENT_TIMESTAMP - INTERVAL '2 seconds' WHERE id = %s",
                (room["tournament_id"],),
            )
        assert store.advance_one_running_tournament(engine)
    final = durable_client.get(
        f"/v1/tournaments/{code}/official-state",
        headers=bearer(str(room["organizer_access_token"])),
    ).json()
    assert final["status"] == "completed"
    assert final["champion_id"] == paper["player"]["player_id"]
    assert len(final["completed_rounds"]) == 2
    assert [len(stage["matches"]) for stage in final["completed_rounds"]] == [2, 2]
    with connection() as database, database.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM official_matches WHERE tournament_id = %s", (room["tournament_id"],))
        assert cursor.fetchone()[0] == 4
        cursor.execute("SELECT count(*) FROM official_match_rounds WHERE tournament_id = %s", (room["tournament_id"],))
        assert cursor.fetchone()[0] == 8


def test_concurrent_workers_commit_only_one_round_then_resume_after_restart(durable_client: TestClient) -> None:
    room = create_room(durable_client)
    ready_player(durable_client, room, "Rock", "rock")
    ready_player(durable_client, room, "Scissors", "scissors")
    code = str(room["tournament_code"])
    assert durable_client.post(
        f"/v1/tournaments/{code}/admin/start", json={},
        headers={**bearer(str(room["organizer_access_token"])), "Idempotency-Key": str(uuid4())},
    ).status_code == 200
    with connection() as database, database.cursor() as cursor:
        cursor.execute(
            "UPDATE tournaments SET updated_at = CURRENT_TIMESTAMP - INTERVAL '2 seconds', next_transition_at = CURRENT_TIMESTAMP - INTERVAL '2 seconds' WHERE id = %s",
            (room["tournament_id"],),
        )
    def advance_once() -> bool:
        return PostgresTournamentStore(str(TEST_DATABASE_URL)).advance_one_running_tournament(GameEngineAdapter())
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(lambda _: advance_once(), range(2))) == [False, True]
    with connection() as database, database.cursor() as cursor:
        cursor.execute("SELECT state_version FROM tournaments WHERE id = %s", (room["tournament_id"],))
        assert cursor.fetchone()[0] == 2
        cursor.execute("SELECT count(*) FROM official_match_rounds WHERE tournament_id = %s", (room["tournament_id"],))
        assert cursor.fetchone()[0] == 1
        cursor.execute(
            "SELECT state_document->'current_round'->'matches'->0->'battle'->>'player_two_hearts' FROM official_state_snapshots WHERE tournament_id = %s AND state_version = 2",
            (room["tournament_id"],),
        )
        assert cursor.fetchone()[0] == "1"
    # A new repository instance continues solely from the committed snapshot.
    with connection() as database, database.cursor() as cursor:
        cursor.execute(
            "UPDATE tournaments SET updated_at = CURRENT_TIMESTAMP - INTERVAL '2 seconds', next_transition_at = CURRENT_TIMESTAMP - INTERVAL '2 seconds' WHERE id = %s",
            (room["tournament_id"],),
        )
    assert advance_once()
    with connection() as database, database.cursor() as cursor:
        cursor.execute("SELECT state_version FROM tournaments WHERE id = %s", (room["tournament_id"],))
        assert cursor.fetchone()[0] == 3


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
def test_repeat_runs_preserve_history_security_idempotency_and_replay(durable_client: TestClient) -> None:
    import asyncio
    from copy import deepcopy
    room = create_room(durable_client)
    players = [ready_player(durable_client, room, f"Repeat {i}", "uniform") for i in range(7)]
    code, room_id = room["tournament_code"], room["tournament_id"]
    headers = bearer(room["organizer_access_token"])
    path = f"/v1/tournaments/{code}/admin/repeat"
    start = durable_client.post(f"/v1/tournaments/{code}/admin/start", json={},
        headers={**headers, "Idempotency-Key": str(uuid4())})
    assert start.status_code == 200
    old_run = start.json()["run_id"]
    intent = {"expected_run_id": old_run}
    assert durable_client.post(path, json=intent, headers={**headers, "Idempotency-Key": str(uuid4())}).status_code == 409
    assert durable_client.post(path, json=intent, headers={"Idempotency-Key": str(uuid4())}).status_code == 401
    assert durable_client.post(path, json=intent, headers={**bearer(players[0]["player_access_token"]), "Idempotency-Key": str(uuid4())}).status_code == 403
    other = create_room(durable_client)
    assert durable_client.post(path, json=intent, headers={**bearer(other["organizer_access_token"]), "Idempotency-Key": str(uuid4())}).status_code == 403

    def finish():
        for _ in range(500):
            with connection() as db, db.cursor() as cursor:
                cursor.execute("UPDATE tournaments SET updated_at=now()-interval '2 seconds',next_transition_at=now()-interval '2 seconds' WHERE id=%s", (room_id,))
            PostgresTournamentStore(str(TEST_DATABASE_URL)).advance_one_running_tournament(GameEngineAdapter())
            from app.public_state import official_state_view
            store = PostgresTournamentStore(str(TEST_DATABASE_URL))
            state = official_state_view(store.get_tournament(code), store.official_state_snapshot_for(store.get_tournament(code))[0])
            if state["status"] == "completed":
                return state
        pytest.fail("Run did not complete")

    first = finish()
    assert len({first[k] for k in ("first_place","second_place","third_place")}) == 3
    with connection() as db, db.cursor() as cursor:
        cursor.execute("SELECT state_document,finished_at,first_place,second_place,third_place FROM tournament_runs WHERE id=%s", (old_run,))
        saved = deepcopy(cursor.fetchone())
        cursor.execute("SELECT count(*) FROM official_game_events WHERE tournament_id=%s", (room_id,))
        first_events = cursor.fetchone()[0]
    key = str(uuid4())
    def repeat(_):
        return PostgresTournamentStore(str(TEST_DATABASE_URL)).repeat_tournament_atomic(
            code=code,credential=room["organizer_access_token"],idempotency_key=key,
            expected_run_id=old_run,engine=GameEngineAdapter())
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(pool.map(repeat, range(2)))
    assert replies[0] == replies[1]
    new_run = replies[0]["run_id"]
    assert new_run != old_run
    assert durable_client.post(path,json=intent,headers={**headers,"Idempotency-Key":key}).json() == replies[0]
    # A second tab with another key cannot repeat the already-replaced run.
    assert durable_client.post(path,json=intent,headers={**headers,"Idempotency-Key":str(uuid4())}).status_code == 409
    reset = durable_client.get(f"/v1/tournaments/{code}/official-state",headers=headers).json()
    assert reset["run_id"] == new_run
    assert reset["run_start_sequence"] == first_events + 1
    assert all(reset[k] is None for k in ("first_place","second_place","third_place","champion_id"))
    assert not reset["completed_rounds"]
    assert not any(p["second_chance"] for p in reset["players"])
    assert {p["player_id"] for p in reset["players"]} == {p["player_id"] for p in first["players"]}
    for match in reset["current_round"]["matches"]:
        assert match["player_one_hearts"] == match["player_two_hearts"] == 2
    for setting in ("hearts_per_match","sound_effects_enabled","background_music_enabled","movement_speed","countdown_speed"):
        assert reset[setting] == first[setting]
    assert "strategy" not in repr(reset)
    replay = asyncio.run(PostgresRealtimeStore(str(TEST_DATABASE_URL)).events_after(room_id,0))
    assert len(replay) == 1
    assert replay[0].sequence == first_events + 1
    assert replay[0].payload["runId"] == new_run
    second = finish()
    assert len({second[k] for k in ("first_place","second_place","third_place")}) == 3
    with connection() as db, db.cursor() as cursor:
        cursor.execute("SELECT state_document,finished_at,first_place,second_place,third_place FROM tournament_runs WHERE id=%s", (old_run,))
        assert cursor.fetchone() == saved
        cursor.execute("SELECT state_document FROM tournament_runs WHERE id=%s", (new_run,))
        new_saved = cursor.fetchone()[0]
        assert {c["player_id"]:c["strategy"] for c in new_saved["competitors"]} == {c["player_id"]:c["strategy"] for c in saved[0]["competitors"]}
        cursor.execute("SELECT public_payload->>'runId',count(*) FROM official_game_events WHERE tournament_id=%s AND event_type='second_chance_selected' GROUP BY public_payload->>'runId'", (room_id,))
        assert dict(cursor.fetchall()) == {old_run:1,new_run:1}
        cursor.execute("SELECT count(*) FROM tournament_runs WHERE tournament_id=%s", (room_id,))
        assert cursor.fetchone()[0] == 2
        for run_id in (old_run,new_run):
            cursor.execute("SELECT event_type FROM official_game_events WHERE tournament_id=%s AND public_payload->>'runId'=%s AND event_type IN ('third_place_match_started','third_place_decided','final_started','podium_decided','champion') ORDER BY sequence",(room_id,run_id))
            assert [r[0] for r in cursor.fetchall()] == ["third_place_match_started","third_place_decided","final_started","podium_decided","champion"]
        cursor.execute("SELECT count(*) FROM official_game_events WHERE tournament_id=%s AND event_type='player_advanced' AND public_payload->>'matchId' LIKE %s",(room_id,"%:third-place"))
        assert cursor.fetchone()[0] == 0
    # Retrying run #1 after run #2 finishes still returns #2, never creates #3.
    assert repeat(None) == replies[0]
    # A stale participant cursor receives only run #2, with an explicit baseline.
    with TestClient(create_app()) as reconnected:
        participant_headers = bearer(players[0]["player_access_token"])
        ticket = reconnected.post(f"/v1/tournaments/{code}/realtime/ticket",headers=participant_headers).json()["ticket"]
        with reconnected.websocket_connect("/v1/realtime",headers={"origin":"http://localhost:3000"}) as socket:
            socket.send_json({"type":"authenticate","ticket":ticket,"channel":official_channel(room_id)})
            assert socket.receive_json()["type"] == "subscribed"
            socket.send_json({"type":"resume","afterSequence":0})
            assert socket.receive_json() == {"type":"replay-reset","afterSequence":first_events}
            current = socket.receive_json()
            assert current["sequence"] == first_events + 1
            assert current["payload"]["runId"] == new_run
            assert current["payload"]["state"]["run_id"] == new_run
    assert durable_client.post(f"/v1/tournaments/{code}/admin/access/revoke",json={},headers=headers).status_code == 204
    from app.store import InvalidCredential
    with pytest.raises(InvalidCredential):
        repeat(None)


def test_worker_rejects_coherent_snapshot_from_another_run_atomically(durable_client: TestClient):
    import json
    from dataclasses import replace
    from app.engine_gateway import EngineAdvanceResult, EngineUnavailable
    room = create_room(durable_client)
    ready_player(durable_client,room,"One","rock")
    ready_player(durable_client,room,"Two","scissors")
    code = room["tournament_code"]
    started = durable_client.post(f"/v1/tournaments/{code}/admin/start",json={},
        headers={**bearer(room["organizer_access_token"]),"Idempotency-Key":str(uuid4())}).json()
    class WrongRunEngine(GameEngineAdapter):
        def advance_tournament(self, snapshot):
            result = super().advance_tournament(snapshot)
            forged = json.loads(json.dumps(result.snapshot).replace(started["run_id"],str(uuid4())))
            state = tournament_state_from_snapshot(forged)
            return EngineAdvanceResult(replace(result.transition,state=state),forged)
    with connection() as db, db.cursor() as cursor:
        cursor.execute("UPDATE tournaments SET updated_at=now()-interval '2 seconds',next_transition_at=now()-interval '2 seconds' WHERE id=%s",(room["tournament_id"],))
    with pytest.raises(EngineUnavailable):
        PostgresTournamentStore(str(TEST_DATABASE_URL)).advance_one_running_tournament(WrongRunEngine())
    with connection() as db, db.cursor() as cursor:
        cursor.execute("SELECT state_version,current_run_id FROM tournaments WHERE id=%s",(room["tournament_id"],))
        assert cursor.fetchone() == (1, __import__("uuid").UUID(started["run_id"]))
        cursor.execute("SELECT count(*) FROM official_match_rounds WHERE tournament_id=%s",(room["tournament_id"],))
        assert cursor.fetchone()[0] == 0

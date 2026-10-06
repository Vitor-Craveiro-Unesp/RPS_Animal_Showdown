"""Optional integration checks; opt in with an isolated RPS_TEST_DATABASE_URL."""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

from realtime.dsn import to_psycopg_dsn, to_sqlalchemy_url

ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS = ROOT / "database" / "migrations"
TEST_DATABASE_URL = os.environ.get("RPS_TEST_DATABASE_URL")


@unittest.skipUnless(TEST_DATABASE_URL, "RPS_TEST_DATABASE_URL is not configured")
class PostgresMigrationIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            import psycopg  # noqa: F401
        except ImportError as error:
            raise unittest.SkipTest("psycopg is not installed") from error
        # RPS_TEST_DATABASE_URL is intentionally the libpq form used by
        # psycopg. Alembic receives its SQLAlchemy-only equivalent.
        environment = dict(os.environ, DATABASE_URL=to_sqlalchemy_url(str(TEST_DATABASE_URL)))
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=MIGRATIONS, env=environment, check=True)

    def connection(self):
        import psycopg

        return psycopg.connect(to_psycopg_dsn(str(TEST_DATABASE_URL)))

    def setUp(self) -> None:
        # The test database is explicitly isolated by RPS_TEST_DATABASE_URL.
        # Reset the aggregate root so outbox claims from a preceding integration
        # test cannot affect concurrency/retry assertions.
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute("TRUNCATE TABLE tournaments CASCADE")

    def insert_tournament(self, cursor, tournament_id) -> None:
        cursor.execute(
            "INSERT INTO tournaments (id, access_code, organizer_subject_id, capacity) VALUES (%s, %s, 'organizer', 2)",
            (tournament_id, f"test-{tournament_id}"),
        )

    def insert_event_with_outbox(self, cursor, tournament_id, sequence: int, *, enqueue: bool = True):
        transition_id, event_id = uuid4(), uuid4()
        cursor.execute(
            """INSERT INTO official_transitions
               (id, tournament_id, transition_key, expected_state_version, resulting_state_version, state_digest)
               VALUES (%s, %s, %s, 0, 1, %s)""",
            (transition_id, tournament_id, uuid4(), "d" * 64),
        )
        cursor.execute(
            """INSERT INTO official_game_events
               (id, tournament_id, transition_id, sequence, event_type, public_payload)
               VALUES (%s, %s, %s, %s, 'tournament.started', '{}'::jsonb)""",
            (event_id, tournament_id, transition_id, sequence),
        )
        if enqueue:
            cursor.execute(
                "INSERT INTO realtime_outbox (event_id, tournament_id) VALUES (%s, %s)",
                (event_id, tournament_id),
            )
        return event_id

    def test_cross_tournament_command_and_ticket_references_are_rejected(self) -> None:
        tournament_a, tournament_b, command_id, capability_id = (uuid4() for _ in range(4))
        with self.connection() as connection, connection.cursor() as cursor:
            for tournament_id in (tournament_a, tournament_b):
                self.insert_tournament(cursor, tournament_id)
            cursor.execute(
                """INSERT INTO idempotency_commands
                   (id, tournament_id, actor_subject_id, operation, idempotency_key, request_fingerprint)
                   VALUES (%s, %s, 'organizer', 'start', %s, %s)""",
                (command_id, tournament_a, uuid4(), "a" * 64),
            )
            cursor.execute("SAVEPOINT cross_tournament_command")
            with self.assertRaises(Exception):
                cursor.execute(
                    """INSERT INTO official_transitions
                       (id, tournament_id, command_id, transition_key, expected_state_version, resulting_state_version, state_digest)
                       VALUES (%s, %s, %s, %s, 0, 1, %s)""",
                    (uuid4(), tournament_b, command_id, uuid4(), "b" * 64),
                )
            cursor.execute("ROLLBACK TO SAVEPOINT cross_tournament_command")
            cursor.execute(
                """INSERT INTO tournament_access_capabilities
                   (id, tournament_id, subject_id, role, secret_hash, expires_at)
                   VALUES (%s, %s, 'organizer', 'organizer', %s, CURRENT_TIMESTAMP + INTERVAL '1 hour')""",
                (capability_id, tournament_a, "c" * 64),
            )
            cursor.execute("SAVEPOINT cross_tournament_ticket")
            with self.assertRaises(Exception):
                cursor.execute(
                    """INSERT INTO realtime_access_tickets
                       (id, tournament_id, capability_id, subject_id, role, expires_at)
                       VALUES (%s, %s, %s, 'organizer', 'organizer', CURRENT_TIMESTAMP + INTERVAL '5 minutes')""",
                    (uuid4(), tournament_b, capability_id),
                )
            cursor.execute("ROLLBACK TO SAVEPOINT cross_tournament_ticket")

            # A ticket must also carry the exact subject and role of its
            # persisted source capability, not merely an ID in the same room.
            cursor.execute("SAVEPOINT mismatched_ticket_grant")
            with self.assertRaises(Exception):
                cursor.execute(
                    """INSERT INTO realtime_access_tickets
                       (id, tournament_id, capability_id, subject_id, role, expires_at)
                       VALUES (%s, %s, %s, 'different-subject', 'participant', CURRENT_TIMESTAMP + INTERVAL '5 minutes')""",
                    (uuid4(), tournament_a, capability_id),
                )
            cursor.execute("ROLLBACK TO SAVEPOINT mismatched_ticket_grant")

    def test_replay_is_ordered_and_scoped_to_the_tournament(self) -> None:
        from realtime.postgres import PostgresRealtimeStore

        tournament_a, tournament_b = uuid4(), uuid4()
        with self.connection() as connection, connection.cursor() as cursor:
            self.insert_tournament(cursor, tournament_a)
            self.insert_tournament(cursor, tournament_b)
            event_a = self.insert_event_with_outbox(cursor, tournament_a, 1, enqueue=False)
            self.insert_event_with_outbox(cursor, tournament_b, 1, enqueue=False)
        store = PostgresRealtimeStore(str(TEST_DATABASE_URL))
        import asyncio

        events = asyncio.run(store.events_after(str(tournament_a), 0))
        self.assertEqual([(event.event_id, event.tournament_id, event.sequence) for event in events], [(str(event_a), str(tournament_a), 1)])
        self.assertEqual(asyncio.run(store.events_after(str(tournament_a), 1)), ())

    def test_outbox_workers_claim_distinct_events_with_skip_locked(self) -> None:
        from realtime.postgres import PostgresOutboxWorker

        tournament_a, tournament_b = uuid4(), uuid4()
        with self.connection() as connection, connection.cursor() as cursor:
            self.insert_tournament(cursor, tournament_a)
            self.insert_tournament(cursor, tournament_b)
            event_a = self.insert_event_with_outbox(cursor, tournament_a, 1)
            event_b = self.insert_event_with_outbox(cursor, tournament_b, 1)
        worker_a = PostgresOutboxWorker(str(TEST_DATABASE_URL), "test-worker-a")
        worker_b = PostgresOutboxWorker(str(TEST_DATABASE_URL), "test-worker-b")
        with ThreadPoolExecutor(max_workers=2) as executor:
            claimed = tuple(executor.map(lambda worker: worker._claim_one(), (worker_a, worker_b)))
        self.assertEqual({event.event_id for event in claimed if event is not None}, {str(event_a), str(event_b)})

    def test_failed_publish_releases_lease_and_retry_marks_event(self) -> None:
        from realtime.postgres import PostgresOutboxWorker

        class FailingPublisher:
            async def publish(self, event) -> None:
                raise RuntimeError("transport unavailable")

        class RecordingPublisher:
            def __init__(self) -> None:
                self.event_ids: list[str] = []

            async def publish(self, event) -> None:
                self.event_ids.append(event.event_id)

        tournament = uuid4()
        with self.connection() as connection, connection.cursor() as cursor:
            self.insert_tournament(cursor, tournament)
            event_id = self.insert_event_with_outbox(cursor, tournament, 1)
        worker = PostgresOutboxWorker(str(TEST_DATABASE_URL), "test-worker-retry")
        with self.assertRaisesRegex(RuntimeError, "transport unavailable"):
            asyncio.run(worker.publish_one(FailingPublisher()))
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT lease_owner, lease_expires_at, published_at, publish_attempts, last_error_code FROM realtime_outbox WHERE event_id = %s",
                (event_id,),
            )
            lease_owner, lease_expires_at, published_at, attempts, error_code = cursor.fetchone()
        self.assertIsNone(lease_owner)
        self.assertIsNone(lease_expires_at)
        self.assertIsNone(published_at)
        self.assertEqual(attempts, 1)
        self.assertEqual(error_code, "RuntimeError")

        # The worker intentionally applies a one-second retry backoff.  Make
        # the item eligible immediately here so the test proves the next
        # lease/publish cycle without relying on wall-clock sleeps.
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute("UPDATE realtime_outbox SET available_at = CURRENT_TIMESTAMP WHERE event_id = %s", (event_id,))

        publisher = RecordingPublisher()
        self.assertTrue(asyncio.run(worker.publish_one(publisher)))
        self.assertEqual(publisher.event_ids, [str(event_id)])
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT published_at, publish_attempts FROM realtime_outbox WHERE event_id = %s", (event_id,))
            published_at, attempts = cursor.fetchone()
        self.assertIsNotNone(published_at)
        self.assertEqual(attempts, 2)

    def test_downgrade_and_reupgrade_preserve_migration_chain(self) -> None:
        environment = dict(os.environ, DATABASE_URL=to_sqlalchemy_url(str(TEST_DATABASE_URL)))
        subprocess.run([sys.executable, "-m", "alembic", "downgrade", "0001_realtime_event_ledger"], cwd=MIGRATIONS, env=environment, check=True)
        try:
            with self.connection() as connection, connection.cursor() as cursor:
                cursor.execute("SELECT to_regclass('public.tournament_access_capabilities')")
                self.assertIsNone(cursor.fetchone()[0])
        finally:
            subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=MIGRATIONS, env=environment, check=True)
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('public.realtime_access_tickets')")
            self.assertEqual(cursor.fetchone()[0], "realtime_access_tickets")
            cursor.execute("SELECT to_regclass('public.shared_rate_limit_buckets')")
            self.assertEqual(cursor.fetchone()[0], "shared_rate_limit_buckets")
    def test_run_history_blocks_downgrade_and_cross_room_pointer(self) -> None:
        room_a, room_b, run_id = uuid4(), uuid4(), uuid4()
        with self.connection() as connection, connection.cursor() as cursor:
            self.insert_tournament(cursor, room_a)
            self.insert_tournament(cursor, room_b)
            cursor.execute("INSERT INTO tournament_runs(id,tournament_id,number,start_sequence,state_document) VALUES(%s,%s,1,1,'{}')", (run_id,room_a))
            cursor.execute("SAVEPOINT invalid_run_pointer")
            with self.assertRaises(Exception):
                cursor.execute("UPDATE tournaments SET current_run_id=%s WHERE id=%s", (run_id,room_b))
            cursor.execute("ROLLBACK TO SAVEPOINT invalid_run_pointer")
        environment = dict(os.environ, DATABASE_URL=to_sqlalchemy_url(str(TEST_DATABASE_URL)))
        result = subprocess.run([sys.executable,"-m","alembic","downgrade","0005_competition_schedule"], cwd=MIGRATIONS,env=environment,capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn("Run history is not safely downgradeable",result.stderr)
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM tournament_runs WHERE id=%s",(run_id,))
            self.assertEqual(cursor.fetchone()[0],1)

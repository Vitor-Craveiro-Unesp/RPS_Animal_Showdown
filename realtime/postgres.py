"""PostgreSQL adapters for ticket checks, durable replay, and the outbox worker.

The Backend constructs these adapters with its validated DATABASE_URL. Importing
this module does not require psycopg, so protocol/unit tests remain dependency
free; production startup fails closed if the database driver is unavailable.
"""
from __future__ import annotations

import asyncio
from typing import Protocol

from .dsn import to_psycopg_dsn
from .protocol import REPLAY_PAGE_SIZE, OfficialEvent
from .tickets import TicketClaims


class OfficialEventPublisher(Protocol):
    async def publish(self, event: OfficialEvent) -> None:
        ...


class PostgresRealtimeStore:
    """Read-only socket adapters backed by the authoritative event ledger."""

    def __init__(self, database_url: str) -> None:
        self._database_url = to_psycopg_dsn(database_url)

    def _connect(self):
        try:
            import psycopg
        except ImportError as error:  # pragma: no cover - exercised in deployment
            raise RuntimeError("psycopg is required for the PostgreSQL realtime adapter") from error
        return psycopg.connect(self._database_url)

    def is_active(self, claims: TicketClaims, now: int) -> bool:
        # Claim values are compared to persistence, not merely trusted from HMAC.
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT 1
                  FROM realtime_access_tickets ticket
                  JOIN tournament_access_capabilities capability
                    ON capability.id = ticket.capability_id
                   AND capability.tournament_id = ticket.tournament_id
                 WHERE ticket.id = %s
                   AND ticket.tournament_id = %s
                   AND ticket.subject_id = %s
                   AND ticket.role = %s
                   AND ticket.revoked_at IS NULL
                   AND ticket.not_before <= to_timestamp(%s)
                   AND ticket.expires_at > to_timestamp(%s)
                   AND capability.subject_id = ticket.subject_id
                   AND capability.role = ticket.role
                   AND capability.revoked_at IS NULL
                   AND capability.expires_at > to_timestamp(%s)
                """,
                (claims.ticket_id, claims.tournament_id, claims.subject_id, claims.role, now, now, now),
            )
            return cursor.fetchone() is not None

    async def events_after(self, tournament_id: str, sequence: int) -> tuple[OfficialEvent, ...]:
        return await asyncio.to_thread(self._events_after, tournament_id, sequence)

    def _events_after(self, tournament_id: str, sequence: int) -> tuple[OfficialEvent, ...]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, tournament_id, sequence, event_type, public_payload
                  FROM official_game_events
                   WHERE tournament_id = %s AND sequence > %s
                     AND sequence >= COALESCE((SELECT r.start_sequence FROM tournament_runs r
                         JOIN tournaments t ON t.id=r.tournament_id AND t.current_run_id=r.id
                         WHERE t.id=official_game_events.tournament_id), 1)
                 ORDER BY sequence ASC
                 LIMIT %s
                """,
                (tournament_id, sequence, REPLAY_PAGE_SIZE),
            )
            return tuple(
                OfficialEvent(str(event_id), str(room_id), event_sequence, event_type, payload)
                for event_id, room_id, event_sequence, event_type, payload in cursor.fetchall()
            )


class PostgresOutboxWorker:
    """Claims one event at a time with SKIP LOCKED, then marks it after publish."""

    def __init__(self, database_url: str, worker_id: str, lease_seconds: int = 30) -> None:
        if not worker_id:
            raise ValueError("outbox worker id is required")
        self._database_url = database_url
        self._worker_id = worker_id
        self._lease_seconds = lease_seconds

    def _connect(self):
        return PostgresRealtimeStore(self._database_url)._connect()

    async def publish_one(self, publisher: OfficialEventPublisher) -> bool:
        event = await asyncio.to_thread(self._claim_one)
        if event is None:
            return False
        try:
            await publisher.publish(event)
        except Exception as error:
            await asyncio.to_thread(self._release, event.event_id, type(error).__name__[:120])
            raise
        await asyncio.to_thread(self._mark_published, event.event_id)
        return True

    def _claim_one(self) -> OfficialEvent | None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                WITH candidate AS (
                    SELECT outbox.event_id
                      FROM realtime_outbox outbox
                      JOIN official_game_events event
                        ON event.id = outbox.event_id
                       AND event.tournament_id = outbox.tournament_id
                     WHERE outbox.published_at IS NULL
                       AND outbox.available_at <= CURRENT_TIMESTAMP
                       AND (outbox.lease_expires_at IS NULL OR outbox.lease_expires_at < CURRENT_TIMESTAMP)
                       AND NOT EXISTS (
                           SELECT 1
                             FROM official_game_events earlier
                             JOIN realtime_outbox earlier_outbox
                               ON earlier_outbox.event_id = earlier.id
                              AND earlier_outbox.tournament_id = earlier.tournament_id
                            WHERE earlier.tournament_id = event.tournament_id
                              AND earlier.sequence < event.sequence
                              AND earlier_outbox.published_at IS NULL
                       )
                     ORDER BY outbox.available_at, event.tournament_id, event.sequence
                     FOR UPDATE OF outbox SKIP LOCKED
                     LIMIT 1
                )
                UPDATE realtime_outbox outbox
                   SET lease_owner = %s,
                       lease_expires_at = CURRENT_TIMESTAMP + (%s * INTERVAL '1 second'),
                       publish_attempts = outbox.publish_attempts + 1,
                       last_error_code = NULL
                  FROM candidate
                 WHERE outbox.event_id = candidate.event_id
                RETURNING outbox.event_id, outbox.tournament_id
                """,
                (self._worker_id, self._lease_seconds),
            )
            claimed = cursor.fetchone()
            if claimed is None:
                return None
            event_id, tournament_id = claimed
            cursor.execute(
                """
                SELECT id, tournament_id, sequence, event_type, public_payload
                  FROM official_game_events
                 WHERE id = %s AND tournament_id = %s
                """,
                (event_id, tournament_id),
            )
            row = cursor.fetchone()
            if row is None:  # Composite FK makes this an invariant, retain fail-safe.
                raise RuntimeError("outbox event is missing")
            connection.commit()
            return OfficialEvent(str(row[0]), str(row[1]), row[2], row[3], row[4])

    def _mark_published(self, event_id: str) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE realtime_outbox
                   SET published_at = CURRENT_TIMESTAMP, lease_expires_at = NULL
                 WHERE event_id = %s AND lease_owner = %s AND published_at IS NULL
                """,
                (event_id, self._worker_id),
            )
            connection.commit()

    def _release(self, event_id: str, error_code: str) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE realtime_outbox
                   SET lease_owner = NULL,
                       lease_expires_at = NULL,
                       available_at = CURRENT_TIMESTAMP + INTERVAL '1 second',
                       last_error_code = %s
                 WHERE event_id = %s AND lease_owner = %s AND published_at IS NULL
                """,
                (error_code, event_id, self._worker_id),
            )
            connection.commit()

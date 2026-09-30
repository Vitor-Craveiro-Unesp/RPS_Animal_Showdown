"""Security primitives for the HTTP boundary.

The local limiter is deliberately restricted to isolated unit tests.  The
durable API selects the PostgreSQL limiter, whose single-statement upsert makes
each operation/subject counter shared by every API instance.
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from secrets import choice, token_urlsafe
from time import monotonic
from typing import Any, Callable, Final, Protocol


_CODE_ALPHABET: Final = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_CODE_LENGTH: Final = 16  # 32^16 = 80 bits of entropy (prefix excluded).


def generate_tournament_code() -> str:
    """Return a human-enterable, non-sequential code with 80 bits of entropy."""
    suffix = "".join(choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))
    return f"RPS-{suffix}"


def generate_access_token() -> str:
    """Return an opaque bearer credential; callers must store only its digest."""
    return token_urlsafe(32)


@dataclass(frozen=True)
class RateLimit:
    max_requests: int
    window_seconds: float


class RateLimitExceeded(Exception):
    """Raised when an operation-specific limit has no remaining capacity."""

    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = max(1, retry_after_seconds)
        super().__init__("Rate limit exceeded")


class RateLimiterUnavailable(Exception):
    """Raised when the shared abuse-control dependency cannot be reached.

    Callers must fail closed; accepting a request when the shared counter is
    unavailable would let an attacker bypass the public-release control.
    """


class RateLimiter(Protocol):
    def check(self, operation: str, subject: str, limit: RateLimit) -> None: ...


class SlidingWindowRateLimiter:
    """A local sliding-window limiter with an injectable clock for tests."""

    def __init__(self, clock: Callable[[], float] = monotonic) -> None:
        self._clock = clock
        self._requests: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def check(self, operation: str, subject: str, limit: RateLimit) -> None:
        now = self._clock()
        key = (operation, subject)
        requests = self._requests[key]
        cutoff = now - limit.window_seconds
        while requests and requests[0] <= cutoff:
            requests.popleft()
        if len(requests) >= limit.max_requests:
            retry_after = int(requests[0] + limit.window_seconds - now) + 1
            raise RateLimitExceeded(retry_after)
        requests.append(now)


class PostgresFixedWindowRateLimiter:
    """Shared fixed-window limiter backed by PostgreSQL.

    A compact fixed window is intentional for V0.1: it provides atomic shared
    counters and TTL without adding a second operational service.  The row is
    keyed by an operation namespace plus a hashed subject; raw IP addresses or
    bearer credentials are never stored in the database.
    """

    def __init__(self, database_url: str, connect: Callable[[], Any] | None = None) -> None:
        self._database_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        self._connect_override = connect

    def _connect(self) -> Any:
        if self._connect_override is not None:
            return self._connect_override()
        try:
            import psycopg
        except ImportError as error:  # pragma: no cover - deployment configuration
            raise RateLimiterUnavailable("psycopg is required for shared rate limiting") from error
        try:
            return psycopg.connect(self._database_url)
        except Exception as error:
            raise RateLimiterUnavailable("shared rate limiter is unavailable") from error

    @staticmethod
    def _subject_key(subject: str) -> str:
        # The caller's subject includes a type prefix (for example ``ip:`` or
        # ``credential:``), so hash the complete value and retain no raw
        # network address or capability-derived value in durable storage.
        return sha256(subject.encode("utf-8")).hexdigest()

    def check(self, operation: str, subject: str, limit: RateLimit) -> None:
        if not operation or limit.max_requests < 1 or limit.window_seconds <= 0:
            raise ValueError("rate-limit operation and window must be valid")
        try:
            with self._connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO shared_rate_limit_buckets
                        (operation, subject_hash, expires_at, request_count)
                    VALUES
                        (%s, %s, CURRENT_TIMESTAMP + (%s * INTERVAL '1 second'), 1)
                    ON CONFLICT (operation, subject_hash) DO UPDATE
                    SET request_count = CASE
                            WHEN shared_rate_limit_buckets.expires_at <= CURRENT_TIMESTAMP THEN 1
                            ELSE shared_rate_limit_buckets.request_count + 1
                        END,
                        expires_at = CASE
                            WHEN shared_rate_limit_buckets.expires_at <= CURRENT_TIMESTAMP
                                THEN CURRENT_TIMESTAMP + (%s * INTERVAL '1 second')
                            ELSE shared_rate_limit_buckets.expires_at
                        END
                    RETURNING request_count,
                        GREATEST(1, CEIL(EXTRACT(EPOCH FROM expires_at - CURRENT_TIMESTAMP))::integer)
                    """,
                    (operation, self._subject_key(subject), limit.window_seconds, limit.window_seconds),
                )
                request_count, retry_after = cursor.fetchone()
        except RateLimiterUnavailable:
            raise
        except Exception as error:
            raise RateLimiterUnavailable("shared rate limiter is unavailable") from error
        if request_count > limit.max_requests:
            raise RateLimitExceeded(int(retry_after))

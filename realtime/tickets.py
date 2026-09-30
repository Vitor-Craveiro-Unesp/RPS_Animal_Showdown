"""Short-lived, signed realtime tickets and the durable-validation boundary."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Callable, Protocol
from uuid import UUID

from .protocol import AccessGrant, ProtocolError, canonical_tournament_id

_ISSUER = "rps-realtime-v1"


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


@dataclass(frozen=True)
class TicketClaims:
    ticket_id: str
    subject_id: str
    tournament_id: str
    role: str
    expires_at: int
    not_before: int

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "ticket_id", str(UUID(self.ticket_id)))
        except (TypeError, ValueError, AttributeError) as error:
            raise ProtocolError("ticket id must be a UUID") from error
        if not isinstance(self.subject_id, str) or not self.subject_id:
            raise ProtocolError("ticket subject is required")
        object.__setattr__(self, "tournament_id", canonical_tournament_id(self.tournament_id))
        if self.role not in {"organizer", "participant", "spectator"}:
            raise ProtocolError("unsupported tournament role")
        if any(isinstance(value, bool) or not isinstance(value, int) for value in (self.expires_at, self.not_before)):
            raise ProtocolError("ticket timestamps must be integers")
        if self.expires_at <= self.not_before:
            raise ProtocolError("ticket expiration must follow not-before")

    @property
    def grant(self) -> AccessGrant:
        return AccessGrant(self.subject_id, self.tournament_id, self.role)

    def payload(self) -> dict[str, object]:
        return {
            "iss": _ISSUER,
            "jti": self.ticket_id,
            "sub": self.subject_id,
            "tid": self.tournament_id,
            "role": self.role,
            "nbf": self.not_before,
            "exp": self.expires_at,
        }


class TicketStatusStore(Protocol):
    """Durable implementation checks persistence/revocation on every handshake."""

    def is_active(self, claims: TicketClaims, now: int) -> bool:
        ...


class SignedTicketCodec:
    """HMAC codec; ticket storage remains authoritative for revocation and TTL."""

    def __init__(self, signing_key: bytes, now: Callable[[], int] | None = None) -> None:
        if len(signing_key) < 32:
            raise ValueError("realtime ticket signing key must be at least 32 bytes")
        self._signing_key = signing_key
        self._now = now or (lambda: int(time.time()))

    def issue(self, claims: TicketClaims) -> str:
        encoded = _b64encode(json.dumps(claims.payload(), separators=(",", ":"), sort_keys=True).encode("utf-8"))
        signature = hmac.new(self._signing_key, encoded.encode("ascii"), hashlib.sha256).digest()
        return f"{encoded}.{_b64encode(signature)}"

    def verify(self, ticket: str) -> TicketClaims:
        try:
            encoded, supplied_signature = ticket.split(".")
            expected_signature = hmac.new(self._signing_key, encoded.encode("ascii"), hashlib.sha256).digest()
            if not hmac.compare_digest(expected_signature, _b64decode(supplied_signature)):
                raise ProtocolError("invalid realtime ticket")
            payload = json.loads(_b64decode(encoded))
            if not isinstance(payload, dict) or set(payload) != {"iss", "jti", "sub", "tid", "role", "nbf", "exp"}:
                raise ProtocolError("invalid realtime ticket")
            if payload["iss"] != _ISSUER:
                raise ProtocolError("invalid realtime ticket")
            claims = TicketClaims(
                ticket_id=payload["jti"], subject_id=payload["sub"], tournament_id=payload["tid"],
                role=payload["role"], not_before=payload["nbf"], expires_at=payload["exp"],
            )
        except (AttributeError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ProtocolError("invalid realtime ticket") from error
        now = self._now()
        if now < claims.not_before or now >= claims.expires_at:
            raise ProtocolError("expired realtime ticket")
        return claims


class TicketVerifier:
    def __init__(self, codec: SignedTicketCodec, status_store: TicketStatusStore) -> None:
        self._codec = codec
        self._status_store = status_store

    def verify_active(self, ticket: str) -> TicketClaims:
        claims = self._codec.verify(ticket)
        if not self._status_store.is_active(claims, int(time.time())):
            # Keep the close reason generic. Revocation/existence must not leak.
            raise ProtocolError("realtime access denied")
        return claims

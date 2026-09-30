"""Pure guards for the server-authoritative WebSocket event stream.

Ticket signature validation and database access live at the FastAPI boundary.
This module deliberately makes channel scope, client frame allowlist and event
deduplication deterministic and testable without a socket server.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID


class ProtocolError(ValueError):
    """A realtime frame, channel or event violates the contract."""


class EventDisposition(str, Enum):
    ACCEPTED = "accepted"
    DUPLICATE = "duplicate"
    STALE = "stale"


def canonical_tournament_id(tournament_id: str) -> str:
    try:
        return str(UUID(tournament_id))
    except (TypeError, ValueError, AttributeError) as error:
        raise ProtocolError("tournament id must be a UUID") from error


def official_channel(tournament_id: str) -> str:
    """The sole V0.1 server-to-client channel for one tournament."""
    return f"tournament/{canonical_tournament_id(tournament_id)}/official-events"


@dataclass(frozen=True)
class AccessGrant:
    """Claims from an access ticket already verified by the server."""

    subject_id: str
    tournament_id: str
    role: str

    def __post_init__(self) -> None:
        if not self.subject_id:
            raise ProtocolError("subject id is required")
        if self.role not in {"organizer", "participant", "spectator"}:
            raise ProtocolError("unsupported tournament role")
        object.__setattr__(self, "tournament_id", canonical_tournament_id(self.tournament_id))


def authorize_subscription(grant: AccessGrant, requested_channel: str) -> str:
    """Allow only the exact channel for the tournament in a validated grant."""
    expected = official_channel(grant.tournament_id)
    if requested_channel != expected:
        raise ProtocolError("subscription is not authorized for this tournament")
    return expected


def validate_client_frame(frame: object) -> dict[str, object]:
    """Allow only authentication/resume control frames; never client publishing."""
    if not isinstance(frame, dict):
        raise ProtocolError("realtime frame must be an object")
    frame_type = frame.get("type")
    if frame_type == "authenticate":
        if (
            set(frame) != {"type", "ticket", "channel"}
            or not isinstance(frame.get("ticket"), str)
            or not frame["ticket"]
            or not isinstance(frame.get("channel"), str)
            or not frame["channel"]
        ):
            raise ProtocolError("invalid authentication frame")
        return {"type": "authenticate", "ticket": frame["ticket"], "channel": frame["channel"]}
    if frame_type == "resume":
        sequence = frame.get("afterSequence")
        if set(frame) != {"type", "afterSequence"} or isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
            raise ProtocolError("invalid resume frame")
        return {"type": "resume", "afterSequence": sequence}
    raise ProtocolError("client publishing is not supported")


@dataclass(frozen=True)
class OfficialEvent:
    """A public event that the internal server publisher may serialize."""

    event_id: str
    tournament_id: str
    sequence: int
    event_type: str
    payload: dict[str, object]

    def __post_init__(self) -> None:
        try:
            str(UUID(self.event_id))
        except (TypeError, ValueError, AttributeError) as error:
            raise ProtocolError("event id must be a UUID") from error
        object.__setattr__(self, "tournament_id", canonical_tournament_id(self.tournament_id))
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence < 1:
            raise ProtocolError("event sequence must be a positive integer")
        if not isinstance(self.event_type, str) or not self.event_type:
            raise ProtocolError("event type is required")
        if not isinstance(self.payload, dict):
            raise ProtocolError("event payload must be an object")

    def to_wire(self) -> dict[str, object]:
        return {"type": "official-event", "eventId": self.event_id, "tournamentId": self.tournament_id, "sequence": self.sequence, "eventType": self.event_type, "payload": self.payload}


@dataclass
class EventCursor:
    """Requires replay after a gap and treats at-least-once delivery safely."""

    tournament_id: str
    last_sequence: int = 0
    _recent_ids: deque[str] = field(default_factory=lambda: deque(maxlen=512), init=False)
    _recent_id_set: set[str] = field(default_factory=set, init=False)

    def __post_init__(self) -> None:
        self.tournament_id = canonical_tournament_id(self.tournament_id)
        if isinstance(self.last_sequence, bool) or not isinstance(self.last_sequence, int) or self.last_sequence < 0:
            raise ProtocolError("cursor sequence must be nonnegative")

    def accept(self, event: OfficialEvent) -> EventDisposition:
        if event.tournament_id != self.tournament_id:
            raise ProtocolError("event belongs to a different tournament")
        if event.event_id in self._recent_id_set:
            return EventDisposition.DUPLICATE
        if event.sequence <= self.last_sequence:
            return EventDisposition.STALE
        if event.sequence != self.last_sequence + 1:
            raise ProtocolError("event sequence gap; resume from the saved cursor")
        if len(self._recent_ids) == self._recent_ids.maxlen:
            self._recent_id_set.remove(self._recent_ids.popleft())
        self._recent_ids.append(event.event_id)
        self._recent_id_set.add(event.event_id)
        self.last_sequence = event.sequence
        return EventDisposition.ACCEPTED

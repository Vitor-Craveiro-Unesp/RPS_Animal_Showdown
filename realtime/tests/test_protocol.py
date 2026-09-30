from __future__ import annotations
import unittest
from realtime.protocol import AccessGrant, EventCursor, EventDisposition, OfficialEvent, ProtocolError, authorize_subscription, official_channel, validate_client_frame

TOURNAMENT_A = "11111111-1111-1111-1111-111111111111"
TOURNAMENT_B = "22222222-2222-2222-2222-222222222222"
EVENT_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
EVENT_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


def event(event_id: str = EVENT_A, sequence: int = 1, tournament_id: str = TOURNAMENT_A) -> OfficialEvent:
    return OfficialEvent(event_id, tournament_id, sequence, "round.resolved", {"public": True})


class RealtimeAuthorizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.grant = AccessGrant("subject-1", TOURNAMENT_A, "participant")

    def test_authorizes_exact_granted_tournament_channel(self) -> None:
        channel = official_channel(TOURNAMENT_A)
        self.assertEqual(authorize_subscription(self.grant, channel), channel)

    def test_rejects_cross_tournament_subscription(self) -> None:
        with self.assertRaises(ProtocolError):
            authorize_subscription(self.grant, official_channel(TOURNAMENT_B))

    def test_rejects_wildcard_channel(self) -> None:
        with self.assertRaises(ProtocolError):
            authorize_subscription(self.grant, "tournament/*/official-events")

    def test_client_cannot_publish_official_event(self) -> None:
        with self.assertRaises(ProtocolError):
            validate_client_frame({"type": "official-event", "winner": "forged"})

    def test_only_strict_control_frames_are_accepted(self) -> None:
        self.assertEqual(
            validate_client_frame(
                {"type": "authenticate", "ticket": "signed-ticket", "channel": official_channel(TOURNAMENT_A)}
            )["type"],
            "authenticate",
        )
        self.assertEqual(validate_client_frame({"type": "resume", "afterSequence": 0})["afterSequence"], 0)
        with self.assertRaises(ProtocolError):
            validate_client_frame({"type": "resume", "afterSequence": True})


class RealtimeOrderingTests(unittest.TestCase):
    def test_accepts_contiguous_events(self) -> None:
        cursor = EventCursor(TOURNAMENT_A)
        self.assertEqual(cursor.accept(event()), EventDisposition.ACCEPTED)
        self.assertEqual(cursor.accept(event(EVENT_B, 2)), EventDisposition.ACCEPTED)

    def test_duplicate_event_is_ignored(self) -> None:
        cursor = EventCursor(TOURNAMENT_A)
        cursor.accept(event())
        self.assertEqual(cursor.accept(event()), EventDisposition.DUPLICATE)

    def test_replayed_event_after_reconnect_is_stale(self) -> None:
        self.assertEqual(EventCursor(TOURNAMENT_A, 3).accept(event(EVENT_A, 3)), EventDisposition.STALE)

    def test_gap_requires_replay(self) -> None:
        with self.assertRaisesRegex(ProtocolError, "gap"):
            EventCursor(TOURNAMENT_A).accept(event(EVENT_B, 2))

    def test_event_from_other_tournament_is_rejected(self) -> None:
        with self.assertRaisesRegex(ProtocolError, "different tournament"):
            EventCursor(TOURNAMENT_A).accept(event(tournament_id=TOURNAMENT_B))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from realtime.protocol import ProtocolError
from realtime.tickets import SignedTicketCodec, TicketClaims, TicketVerifier

TOURNAMENT = "11111111-1111-1111-1111-111111111111"
TICKET = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


class StatusStore:
    def __init__(self, active: bool = True) -> None:
        self.active = active

    def is_active(self, claims: TicketClaims, now: int) -> bool:
        return self.active and claims.ticket_id == TICKET and now == 100


class TicketTests(unittest.TestCase):
    def setUp(self) -> None:
        self.codec = SignedTicketCodec(b"x" * 32, now=lambda: 100)
        self.claims = TicketClaims(TICKET, "member-1", TOURNAMENT, "participant", 200, 50)

    def test_signed_ticket_returns_canonical_claims(self) -> None:
        claims = self.codec.verify(self.codec.issue(self.claims))
        self.assertEqual(claims.grant.tournament_id, TOURNAMENT)
        self.assertEqual(claims.grant.subject_id, "member-1")

    def test_tampered_ticket_is_rejected(self) -> None:
        ticket = self.codec.issue(self.claims)
        with self.assertRaises(ProtocolError):
            self.codec.verify(ticket[:-1] + ("a" if ticket[-1] != "a" else "b"))

    def test_revoked_or_missing_persistent_ticket_is_rejected(self) -> None:
        verifier = TicketVerifier(self.codec, StatusStore(active=False))
        with self.assertRaisesRegex(ProtocolError, "access denied"):
            verifier.verify_active(self.codec.issue(self.claims))

    def test_expired_ticket_is_rejected_before_store_lookup(self) -> None:
        expired = SignedTicketCodec(b"x" * 32, now=lambda: 200)
        ticket = expired.issue(TicketClaims(TICKET, "member-1", TOURNAMENT, "participant", 200, 50))
        with self.assertRaisesRegex(ProtocolError, "expired"):
            expired.verify(ticket)


if __name__ == "__main__":
    unittest.main()

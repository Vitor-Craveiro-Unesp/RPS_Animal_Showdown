from __future__ import annotations

import asyncio
import unittest
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from realtime.protocol import OfficialEvent, official_channel
from realtime.tickets import SignedTicketCodec, TicketClaims, TicketVerifier
from realtime.websocket import InMemoryEventStream, OriginPolicy, register_realtime_endpoint

TOURNAMENT_A = "11111111-1111-1111-1111-111111111111"
TOURNAMENT_B = "22222222-2222-2222-2222-222222222222"
TICKET_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
EVENT_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
ORIGIN = "http://localhost:3000"


class ActiveTickets:
    def __init__(self, ticket_id: str) -> None:
        self.ticket_id = ticket_id

    def is_active(self, claims: TicketClaims, now: int) -> bool:
        return claims.ticket_id == self.ticket_id and now < claims.expires_at


class WebSocketConnectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stream = InMemoryEventStream()
        codec = SignedTicketCodec(b"x" * 32)
        self.ticket = codec.issue(TicketClaims(TICKET_ID, "subject-a", TOURNAMENT_A, "participant", 4_102_444_800, 0))
        app = FastAPI()
        register_realtime_endpoint(
            app,
            verifier=TicketVerifier(codec, ActiveTickets(TICKET_ID)),
            stream=self.stream,
            origins=OriginPolicy(frozenset({ORIGIN})),
        )
        self.client = TestClient(app)

    def authenticate(self, socket, tournament_id: str = TOURNAMENT_A) -> None:
        socket.send_json({"type": "authenticate", "ticket": self.ticket, "channel": official_channel(tournament_id)})

    def test_valid_ticket_replays_only_its_tournament_events(self) -> None:
        asyncio.run(self.stream.append(OfficialEvent(EVENT_ID, TOURNAMENT_A, 1, "round.resolved", {"winner": "player-a"})))
        asyncio.run(self.stream.append(OfficialEvent("cccccccc-cccc-cccc-cccc-cccccccccccc", TOURNAMENT_B, 1, "round.resolved", {})))
        with self.client.websocket_connect("/v1/realtime", headers={"origin": ORIGIN}) as socket:
            self.authenticate(socket)
            self.assertEqual(socket.receive_json(), {"type": "subscribed", "channel": official_channel(TOURNAMENT_A)})
            socket.send_json({"type": "resume", "afterSequence": 0})
            event = socket.receive_json()
            self.assertEqual(event["tournamentId"], TOURNAMENT_A)
            self.assertEqual(event["eventId"], EVENT_ID)

    def test_cross_tournament_channel_is_closed(self) -> None:
        with self.client.websocket_connect("/v1/realtime", headers={"origin": ORIGIN}) as socket:
            self.authenticate(socket, TOURNAMENT_B)
            with self.assertRaises(WebSocketDisconnect) as closed:
                socket.receive_json()
        self.assertEqual(closed.exception.code, 1008)

    def test_client_cannot_publish_official_event(self) -> None:
        with self.client.websocket_connect("/v1/realtime", headers={"origin": ORIGIN}) as socket:
            self.authenticate(socket)
            socket.receive_json()
            socket.send_json({"type": "resume", "afterSequence": 0})
            socket.send_json({"type": "official-event", "winner": "forged"})
            with self.assertRaises(WebSocketDisconnect) as closed:
                socket.receive_json()
        self.assertEqual(closed.exception.code, 1008)

    def test_disallowed_origin_is_closed_before_authentication(self) -> None:
        # A close before ``accept`` rejects the upgrade itself, so TestClient
        # raises on entering the context rather than on the first receive.
        with self.assertRaises(WebSocketDisconnect) as closed:
            with self.client.websocket_connect("/v1/realtime", headers={"origin": "https://attacker.invalid"}):
                pass
        self.assertEqual(closed.exception.code, 1008)

    def test_authentication_timeout_closes_the_socket(self) -> None:
        app = FastAPI()
        codec = SignedTicketCodec(b"x" * 32)
        register_realtime_endpoint(
            app,
            verifier=TicketVerifier(codec, ActiveTickets(TICKET_ID)),
            stream=InMemoryEventStream(),
            origins=OriginPolicy(frozenset({ORIGIN})),
            authentication_timeout_seconds=0.01,
        )
        client = TestClient(app)
        with client.websocket_connect("/v1/realtime", headers={"origin": ORIGIN}) as socket:
            with self.assertRaises(WebSocketDisconnect) as closed:
                socket.receive_json()
        self.assertEqual(closed.exception.code, 1008)

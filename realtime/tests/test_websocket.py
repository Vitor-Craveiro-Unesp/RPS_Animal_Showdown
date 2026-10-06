from __future__ import annotations

import asyncio
import unittest
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from realtime.protocol import OfficialEvent, official_channel
from realtime.tickets import SignedTicketCodec, TicketClaims, TicketVerifier
from realtime.websocket import DatabaseBackedEventStream, InMemoryEventStream, OriginPolicy, register_realtime_endpoint

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
        self.active_tickets = ActiveTickets(TICKET_ID)
        app = FastAPI()
        register_realtime_endpoint(
            app,
            verifier=TicketVerifier(codec, self.active_tickets),
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

    def test_normal_client_disconnect_cleans_up_without_protocol_error(self) -> None:
        with self.client.websocket_connect("/v1/realtime", headers={"origin": ORIGIN}) as socket:
            self.authenticate(socket)
            self.assertEqual(socket.receive_json()["type"], "subscribed")
            socket.send_json({"type": "resume", "afterSequence": 0})
        self.assertFalse(self.stream._subscribers.get(TOURNAMENT_A))

    def test_database_backed_live_fanout_does_not_retain_replay_in_memory(self) -> None:
        stream = DatabaseBackedEventStream(InMemoryEventStream())
        event = OfficialEvent(EVENT_ID, TOURNAMENT_A, 1, "round_resolved", {})
        queue = asyncio.run(stream.subscribe(TOURNAMENT_A))
        asyncio.run(stream.publish(event))
        self.assertEqual(queue.get_nowait(), event)
        self.assertEqual(stream.live_fanout._events, {})
        asyncio.run(stream.unsubscribe(TOURNAMENT_A, queue))

    def test_slow_live_subscriber_queue_is_bounded(self) -> None:
        stream = DatabaseBackedEventStream(InMemoryEventStream())
        queue = asyncio.run(stream.subscribe(TOURNAMENT_A))
        for number in range(1, 258):
            asyncio.run(stream.publish(OfficialEvent(str(UUID(int=number + 1)), TOURNAMENT_A, number, "round_resolved", {})))
        self.assertEqual(queue.qsize(), 256)
        self.assertEqual(queue.get_nowait().sequence, 2)
        asyncio.run(stream.unsubscribe(TOURNAMENT_A, queue))

    def test_replay_continues_across_bounded_pages(self) -> None:
        self.stream._events[TOURNAMENT_A] = [
            OfficialEvent(str(UUID(int=number + 1)), TOURNAMENT_A, number, "round_resolved", {})
            for number in range(1, 252)
        ]
        with self.client.websocket_connect("/v1/realtime", headers={"origin": ORIGIN}) as socket:
            self.authenticate(socket)
            self.assertEqual(socket.receive_json()["type"], "subscribed")
            socket.send_json({"type": "resume", "afterSequence": 0})
            sequences = [socket.receive_json()["sequence"] for _ in range(251)]
        self.assertEqual(sequences, list(range(1, 252)))

    def test_revoked_ticket_is_rejected_before_replay_on_existing_socket(self) -> None:
        with self.client.websocket_connect("/v1/realtime", headers={"origin": ORIGIN}) as socket:
            self.authenticate(socket)
            self.assertEqual(socket.receive_json()["type"], "subscribed")
            self.active_tickets.ticket_id = "revoked"
            socket.send_json({"type": "resume", "afterSequence": 0})
            with self.assertRaises(WebSocketDisconnect) as closed:
                socket.receive_json()
        self.assertEqual(closed.exception.code, 1008)

    def test_replay_budget_closes_connection_after_one_thousand_events(self) -> None:
        self.stream._events[TOURNAMENT_A] = [
            OfficialEvent(str(UUID(int=number + 1)), TOURNAMENT_A, number, "round_resolved", {})
            for number in range(1, 1002)
        ]
        with self.client.websocket_connect("/v1/realtime", headers={"origin": ORIGIN}) as socket:
            self.authenticate(socket)
            socket.receive_json()
            socket.send_json({"type": "resume", "afterSequence": 0})
            self.assertEqual([socket.receive_json()["sequence"] for _ in range(1_000)], list(range(1, 1_001)))
            with self.assertRaises(WebSocketDisconnect) as closed:
                socket.receive_json()
        self.assertEqual(closed.exception.code, 1013)

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

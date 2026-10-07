import time
from dataclasses import replace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from realtime.protocol import official_channel, validate_client_frame, ProtocolError
from realtime.tickets import SignedTicketCodec, TicketClaims, TicketVerifier
from realtime.websocket import InMemoryEventStream, OriginPolicy, register_realtime_endpoint

ROOM = "11111111-1111-1111-1111-111111111111"
OTHER = "22222222-2222-2222-2222-222222222222"
ORIGIN = "http://localhost:3000"
REVOKED = "33333333-3333-3333-3333-333333333333"


def setup_connection(*, cooldown=0):
    now = [int(time.time())]
    codec = SignedTicketCodec(b'x' * 32, now=lambda: now[0])
    old = TicketClaims(str(uuid4()), "player", ROOM, "participant", now[0] + 300, now[0] - 1)
    fresh = replace(old, ticket_id=str(uuid4()), expires_at=now[0] + 600)
    class Tickets:
        calls = 0
        revoked = set()
        def is_active(self, claims, at):
            self.calls += 1
            return claims.ticket_id not in self.revoked
    tickets = Tickets()
    app = FastAPI()
    register_realtime_endpoint(app, verifier=TicketVerifier(codec, tickets), stream=InMemoryEventStream(),
                              origins=OriginPolicy(frozenset({ORIGIN})), minimum_renewal_interval_seconds=cooldown)
    return TestClient(app), codec, old, fresh, now, tickets


def authenticate(socket, codec, old):
    socket.send_json({"type": "authenticate", "ticket": codec.issue(old), "channel": official_channel(ROOM)})
    assert socket.receive_json()["type"] == "subscribed"
    socket.send_json({"type": "resume", "afterSequence": 0})


def test_renewal_survives_original_expiration_and_keeps_subscription():
    client, codec, old, fresh, now, _ = setup_connection()
    with client.websocket_connect('/v1/realtime', headers={"origin": ORIGIN}) as socket:
        authenticate(socket, codec, old)
        socket.send_json({"type": "renew", "ticket": codec.issue(fresh)})
        assert socket.receive_json()["expiresAtMs"] == fresh.expires_at * 1000
        now[0] = old.expires_at + 1
        socket.send_json({"type": "resume", "afterSequence": 0})
        newer = replace(fresh, ticket_id=str(uuid4()), expires_at=fresh.expires_at + 300)
        socket.send_json({"type": "renew", "ticket": codec.issue(newer)})
        assert socket.receive_json()["type"] == "renewed"


@pytest.mark.parametrize('mutation', [
    {"tournament_id": OTHER}, {"subject_id": "other-player"}, {"role": "organizer"},
    {"expires_at": 1, "not_before": 0}, {"ticket_id": REVOKED}, {},
])
def test_renewal_cannot_change_identity_or_reuse_expired_revoked_or_old_grant(mutation):
    client, codec, old, fresh, _, tickets = setup_connection()
    tickets.revoked.add(REVOKED)
    replacement = replace(fresh, **mutation) if mutation else old
    with client.websocket_connect('/v1/realtime', headers={"origin": ORIGIN}) as socket:
        authenticate(socket, codec, old)
        socket.send_json({"type": "renew", "ticket": codec.issue(replacement)})
        with pytest.raises(WebSocketDisconnect) as closed:
            socket.receive_json()
        assert closed.value.code == 1008


def test_renewal_cooldown_rejects_flood_before_querying_ticket_store():
    client, codec, old, fresh, _, tickets = setup_connection(cooldown=30)
    with client.websocket_connect('/v1/realtime', headers={"origin": ORIGIN}) as socket:
        authenticate(socket, codec, old)
        socket.send_json({"type": "renew", "ticket": codec.issue(fresh)})
        with pytest.raises(WebSocketDisconnect) as closed:
            socket.receive_json()
        assert closed.value.code == 1008
    assert tickets.calls == 2  # handshake + initial resume, never the renewal


def test_renewal_frame_is_strict_and_bounded():
    for frame in ({"type": "renew", "ticket": ""}, {"type": "renew", "ticket": "x" * 4097},
                  {"type": "renew", "ticket": "valid", "channel": "other"}):
        with pytest.raises(ProtocolError):
            validate_client_frame(frame)


@pytest.mark.parametrize('frame', [{"type": "renew", "ticket": "x"}, {"type": "resume", "afterSequence": 0}])
def test_control_frame_before_authentication_closes_cleanly(frame):
    client, *_ = setup_connection()
    with client.websocket_connect('/v1/realtime', headers={"origin": ORIGIN}) as socket:
        socket.send_json(frame)
        with pytest.raises(WebSocketDisconnect) as closed:
            socket.receive_json()
        assert closed.value.code == 1008


def test_revocation_after_renewal_still_blocks_replay():
    client, codec, old, fresh, _, tickets = setup_connection()
    with client.websocket_connect('/v1/realtime', headers={"origin": ORIGIN}) as socket:
        authenticate(socket, codec, old)
        socket.send_json({"type": "renew", "ticket": codec.issue(fresh)})
        assert socket.receive_json()["type"] == "renewed"
        tickets.revoked.add(fresh.ticket_id)
        socket.send_json({"type": "resume", "afterSequence": 0})
        with pytest.raises(WebSocketDisconnect) as closed:
            socket.receive_json()
        assert closed.value.code == 1008

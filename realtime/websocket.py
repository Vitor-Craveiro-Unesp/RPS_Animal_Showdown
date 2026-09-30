"""A server-to-client FastAPI WebSocket router with replay and channel isolation."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Protocol

from fastapi import WebSocket, WebSocketDisconnect

from .protocol import OfficialEvent, ProtocolError, authorize_subscription, validate_client_frame
from .tickets import TicketVerifier


class EventStream(Protocol):
    async def events_after(self, tournament_id: str, sequence: int) -> tuple[OfficialEvent, ...]:
        ...

    async def subscribe(self, tournament_id: str) -> asyncio.Queue[OfficialEvent]:
        ...

    async def unsubscribe(self, tournament_id: str, queue: asyncio.Queue[OfficialEvent]) -> None:
        ...


@dataclass
class InMemoryEventStream:
    """Executable test/local adapter; production uses PostgreSQLEventStream."""

    _events: dict[str, list[OfficialEvent]] = field(default_factory=dict)
    _subscribers: dict[str, set[asyncio.Queue[OfficialEvent]]] = field(default_factory=dict)

    async def append(self, event: OfficialEvent) -> None:
        events = self._events.setdefault(event.tournament_id, [])
        if any(stored.event_id == event.event_id for stored in events):
            return
        events.append(event)
        for subscriber in self._subscribers.get(event.tournament_id, set()).copy():
            subscriber.put_nowait(event)

    async def publish(self, event: OfficialEvent) -> None:
        """Outbox-worker compatible publishing entrypoint."""
        await self.append(event)

    async def events_after(self, tournament_id: str, sequence: int) -> tuple[OfficialEvent, ...]:
        return tuple(event for event in self._events.get(tournament_id, []) if event.sequence > sequence)

    async def subscribe(self, tournament_id: str) -> asyncio.Queue[OfficialEvent]:
        queue: asyncio.Queue[OfficialEvent] = asyncio.Queue()
        self._subscribers.setdefault(tournament_id, set()).add(queue)
        return queue

    async def unsubscribe(self, tournament_id: str, queue: asyncio.Queue[OfficialEvent]) -> None:
        subscribers = self._subscribers.get(tournament_id)
        if subscribers:
            subscribers.discard(queue)


@dataclass
class DatabaseBackedEventStream:
    """Durable replay plus a process-local fanout fed only by the outbox worker.

    V0.1 runs a single backend process. A multi-process deployment needs a
    shared fanout adapter, while replay remains correct because it is always
    served from PostgreSQL first.
    """

    replay_store: EventStream
    live_fanout: InMemoryEventStream = field(default_factory=InMemoryEventStream)

    async def events_after(self, tournament_id: str, sequence: int) -> tuple[OfficialEvent, ...]:
        return await self.replay_store.events_after(tournament_id, sequence)

    async def subscribe(self, tournament_id: str) -> asyncio.Queue[OfficialEvent]:
        return await self.live_fanout.subscribe(tournament_id)

    async def unsubscribe(self, tournament_id: str, queue: asyncio.Queue[OfficialEvent]) -> None:
        await self.live_fanout.unsubscribe(tournament_id, queue)

    async def publish(self, event: OfficialEvent) -> None:
        await self.live_fanout.publish(event)


@dataclass(frozen=True)
class OriginPolicy:
    allowed_origins: frozenset[str]

    def allows(self, origin: str | None) -> bool:
        return origin is not None and origin in self.allowed_origins


def create_realtime_endpoint(
    *,
    verifier: TicketVerifier,
    stream: EventStream,
    origins: OriginPolicy,
    authentication_timeout_seconds: float = 10.0,
):
    """Create the endpoint callable; registration remains explicit at the Backend boundary."""
    async def official_events(websocket: WebSocket) -> None:
        # Closing an ASGI websocket before ``accept`` rejects the upgrade.  Do
        # this before allocating a connection or reading an untrusted frame.
        if not origins.allows(websocket.headers.get("origin")):
            await websocket.close(code=1008)
            return
        subscription: asyncio.Queue[OfficialEvent] | None = None
        tournament_id: str | None = None
        receive_task: asyncio.Task | None = None
        event_task: asyncio.Task | None = None
        try:
            await websocket.accept()
            authenticate = validate_client_frame(
                await asyncio.wait_for(websocket.receive_json(), timeout=authentication_timeout_seconds)
            )
            claims = verifier.verify_active(str(authenticate["ticket"]))
            channel = authorize_subscription(claims.grant, str(authenticate["channel"]))
            tournament_id = claims.tournament_id
            subscription = await stream.subscribe(tournament_id)
            await websocket.send_json({"type": "subscribed", "channel": channel})

            resume = validate_client_frame(
                await asyncio.wait_for(websocket.receive_json(), timeout=authentication_timeout_seconds)
            )
            if resume["type"] != "resume":
                raise ProtocolError("resume is required after authentication")
            after_sequence = int(resume["afterSequence"])
            last_sent_sequence = after_sequence
            for event in await stream.events_after(tournament_id, after_sequence):
                await websocket.send_json(event.to_wire())
                last_sent_sequence = max(last_sent_sequence, event.sequence)

            receive_task = asyncio.create_task(websocket.receive_json())
            event_task = asyncio.create_task(subscription.get())
            while True:
                done, _ = await asyncio.wait({receive_task, event_task}, return_when=asyncio.FIRST_COMPLETED)
                if event_task in done:
                    event = event_task.result()
                    # The subscription starts before durable replay to avoid a
                    # gap.  At-least-once fanout can therefore overlap replay;
                    # suppress the duplicate on this connection.
                    if event.sequence > last_sent_sequence:
                        await websocket.send_json(event.to_wire())
                        last_sent_sequence = event.sequence
                    event_task = asyncio.create_task(subscription.get())
                if receive_task in done:
                    # A client may replay after detecting a gap, but can never publish.
                    frame = validate_client_frame(receive_task.result())
                    if frame["type"] != "resume":
                        raise ProtocolError("client publishing is not supported")
                    resume_after = int(frame["afterSequence"])
                    for event in await stream.events_after(tournament_id, resume_after):
                        await websocket.send_json(event.to_wire())
                        last_sent_sequence = max(last_sent_sequence, event.sequence)
                    receive_task = asyncio.create_task(websocket.receive_json())
        except (asyncio.TimeoutError, ProtocolError, ValueError, WebSocketDisconnect):
            await websocket.close(code=1008)
        except asyncio.CancelledError:
            # TestClient and ASGI servers cancel the handler after a peer
            # disconnects.  The ``finally`` block below still owns cleanup;
            # do not leak cancellation through the protocol boundary.
            pass
        finally:
            for task in (receive_task, event_task):
                if task is not None and not task.done():
                    task.cancel()
            # Do not await cancelled child tasks here: an ASGI disconnect can
            # arrive in a cancellation scope, and awaiting during that scope
            # propagates its cancellation to TestClient/the server instead of
            # completing the close handshake.  Both tasks have been explicitly
            # cancelled and hold no externally reachable subscription.
            if subscription is not None and tournament_id is not None:
                await stream.unsubscribe(tournament_id, subscription)

    return official_events


def register_realtime_endpoint(
    application,
    *,
    verifier: TicketVerifier,
    stream: EventStream,
    origins: OriginPolicy,
    authentication_timeout_seconds: float = 10.0,
) -> None:
    """Register the socket without taking ownership of the HTTP application factory.

    `add_api_websocket_route` avoids a FastAPI 0.142 lazy-router regression that
    omits WebSocket routes nested through `include_router`.
    """
    application.add_api_websocket_route(
        "/v1/realtime",
        create_realtime_endpoint(
            verifier=verifier,
            stream=stream,
            origins=origins,
            authentication_timeout_seconds=authentication_timeout_seconds,
        ),
    )

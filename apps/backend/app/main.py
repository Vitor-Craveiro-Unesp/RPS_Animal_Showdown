"""Authoritative HTTP boundary for RPS: Animal Showdown.

Only validated player/organizer intentions enter here. Official outcomes are
delegated to the isolated Game Engine; this module never accepts client-sent
results, hearts, BYEs, brackets, advances, or champions.
"""

from __future__ import annotations

import asyncio
import logging
from hashlib import sha256
from os import getenv
from time import time
from typing import Annotated
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .engine_gateway import (
    GameEngineAdapter,
    EnginePlayerSnapshot,
    EngineUnavailable,
    GameEngineGateway,
    StartTournamentCommand,
    TrainingChoiceCommand,
)
from .models import (
    CreateTournamentIntent,
    EmptyIntent,
    RepeatTournamentIntent,
    GuestTrainingChoiceIntent,
    JoinTournamentIntent,
    StrategyIntent,
    TournamentConfigurationIntent,
    TrainingChoiceIntent,
)
from .public_state import official_state_view
from .security import (
    PostgresFixedWindowRateLimiter,
    RateLimit,
    RateLimitExceeded,
    RateLimiter,
    RateLimiterUnavailable,
    SlidingWindowRateLimiter,
)
from .postgres_store import PostgresTournamentStore
from .store import (
    InMemoryTournamentStore,
    InvalidCredential,
    PlayerRecord,
    StoreError,
    TournamentRecord,
)


RATE_LIMITS = {
    "join": RateLimit(max_requests=12, window_seconds=600),
    "strategy": RateLimit(max_requests=20, window_seconds=60),
    "admin": RateLimit(max_requests=20, window_seconds=60),
    "training": RateLimit(max_requests=30, window_seconds=60),
    "guest_training": RateLimit(max_requests=30, window_seconds=60),
    # This is deliberately checked before participant capability lookup so a
    # stream of invalid bearer values cannot brute-force the room boundary.
    "player_auth_ip": RateLimit(max_requests=120, window_seconds=60),
    "player_auth": RateLimit(max_requests=20, window_seconds=60),
    "realtime": RateLimit(max_requests=30, window_seconds=60),
}

DEFAULT_ALLOWED_ORIGINS = ("http://localhost:3000",)
PRODUCTION_ENVIRONMENT = "production"
MAX_API_BODY_BYTES = 64 * 1024
logger = logging.getLogger(__name__)


class RealtimeRateLimitMiddleware:
    """Reject websocket abuse before its handler accepts the handshake."""

    def __init__(self, app, *, limiter: RateLimiter) -> None:
        self.app = app
        self.limiter = limiter

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "websocket" and scope.get("path") == "/v1/realtime":
            client = scope.get("client")
            subject = f"ip:{client[0]}" if client else "ip:unknown"
            try:
                self.limiter.check("realtime", subject, RATE_LIMITS["realtime"])
            except RateLimitExceeded:
                # This occurs before websocket.accept(), so failed handshakes
                # cannot consume connection resources or enumerate tickets.
                await send({"type": "websocket.close", "code": 1013})
                return
            except RateLimiterUnavailable:
                # Fail closed before ``accept``.  A local fallback would make
                # reconnect abuse bypass the shared multi-instance budget.
                await send({"type": "websocket.close", "code": 1013})
                return
        await self.app(scope, receive, send)


def _allowed_origins() -> tuple[str, ...]:
    configured = getenv("ALLOWED_ORIGINS")
    if not configured:
        if getenv("APP_ENV", "development").strip().lower() == PRODUCTION_ENVIRONMENT:
            raise RuntimeError("ALLOWED_ORIGINS is required when APP_ENV=production.")
        return DEFAULT_ALLOWED_ORIGINS
    origins = tuple(origin.strip().rstrip("/") for origin in configured.split(",") if origin.strip())
    if not origins or "*" in origins:
        raise RuntimeError("ALLOWED_ORIGINS must contain one or more explicit origins.")
    for origin in origins:
        parsed = urlparse(origin)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path or parsed.params or parsed.query or parsed.fragment:
            raise RuntimeError("ALLOWED_ORIGINS must contain absolute HTTP(S) origins without paths.")
    return origins


def _client_subject(request: Request) -> str:
    # X-Forwarded-For and Forwarded are intentionally ignored.  A deployment
    # proxy must strip client-supplied versions and make the verified peer IP
    # available to ASGI; trusting arbitrary headers enables trivial spoofing.
    return f"ip:{request.client.host}" if request.client else "ip:unknown"


def _credential_from_header(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, credential = authorization.partition(" ")
    if scheme.lower() != "bearer" or not credential:
        return None
    return credential


def _credential_subject(credential: str | None) -> str:
    if not credential:
        return "credential:anonymous"
    return f"credential:{sha256(credential.encode('utf-8')).hexdigest()}"


def _raise_store_error(error: StoreError) -> None:
    headers = {"WWW-Authenticate": "Bearer"} if isinstance(error, InvalidCredential) else None
    raise HTTPException(status_code=error.status_code, detail=error.detail, headers=headers) from error


def _player_view(player: PlayerRecord) -> dict[str, object]:
    return {
        "player_id": player.id,
        "display_name": player.display_name,
        "animal_id": player.animal_id,
        "ready": player.ready,
        "strategy_locked": player.strategy_locked,
        "membership_status": player.membership_status,
        "removed": player.removed,
    }


def create_app(
    store: InMemoryTournamentStore | PostgresTournamentStore | None = None,
    limiter: RateLimiter | None = None,
    engine: GameEngineGateway | None = None,
) -> FastAPI:
    """Build an app with replaceable infrastructure adapters for tests/deploy."""
    database_url = getenv("DATABASE_URL")
    is_production = getenv("APP_ENV", "development").strip().lower() == PRODUCTION_ENVIRONMENT
    if store is None and not database_url:
        raise RuntimeError(
            "DATABASE_URL is required for the API service. "
            "Pass an explicit InMemoryTournamentStore only to isolated unit tests."
        )
    tournament_store = store or PostgresTournamentStore(database_url)
    logger.info(
        "application configured environment=%s durable_store=%s",
        getenv("APP_ENV", "development").strip().lower(),
        isinstance(tournament_store, PostgresTournamentStore),
    )
    guest_training_sessions: dict[str, object] = {}
    rate_limiter: RateLimiter = limiter or (
        PostgresFixedWindowRateLimiter(database_url or "")
        if isinstance(tournament_store, PostgresTournamentStore)
        else SlidingWindowRateLimiter()
    )
    engine_gateway = engine or GameEngineAdapter()
    # The public client never needs the framework's interactive API explorer.
    # Keep it useful in local development while reducing production endpoint
    # discovery and avoiding a script-bearing surface on the API origin.
    app = FastAPI(
        title="RPS: Animal Showdown API",
        version="0.1.0",
        docs_url=None if is_production else "/docs",
        redoc_url=None if is_production else "/redoc",
        openapi_url=None if is_production else "/openapi.json",
    )
    # Bearer capabilities are carried in Authorization headers, never cookies.
    # Consequently this boundary does not accept credentialed CORS requests and
    # does not need a cookie-CSRF exception. Production supplies an exact list.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(_allowed_origins()),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        """Set response hardening independently of the deployment proxy.

        Bearer capabilities and short-lived realtime tickets are delivered in
        JSON only.  Explicitly prevent browser/proxy caching for every API
        response so a successful creation or join response cannot be replayed
        from shared history or cache storage.
        """
        request.state.server_received_at_ms = int(time() * 1000)
        content_length = request.headers.get("content-length")
        if request.url.path.startswith("/v1/") and content_length:
            try:
                body_is_too_large = int(content_length) > MAX_API_BODY_BYTES
            except ValueError:
                response = JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": "Invalid Content-Length."})
            else:
                response = (
                    JSONResponse(status_code=status.HTTP_413_CONTENT_TOO_LARGE, content={"detail": "Request body too large."})
                    if body_is_too_large
                    else await call_next(request)
                )
        else:
            response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=(), usb=()")
        response.headers.setdefault("Content-Security-Policy", "default-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        if request.url.path.startswith("/v1/"):
            response.headers.setdefault("Cache-Control", "no-store, private, max-age=0")
            response.headers.setdefault("Pragma", "no-cache")
        return response

    def limit(request: Request, operation: str, subject: str | None = None) -> None:
        try:
            rate_limiter.check(operation, subject or _client_subject(request), RATE_LIMITS[operation])
        except RateLimitExceeded as error:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
                headers={"Retry-After": str(error.retry_after_seconds)},
            ) from error
        except RateLimiterUnavailable as error:
            # Do not silently downgrade to process memory.  An unavailable
            # shared limiter means abuse protections cannot be enforced.
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Request protection is temporarily unavailable.",
                headers={"Retry-After": "5"},
            ) from error

    def require_organizer(
        code: str,
        request: Request,
        authorization: Annotated[str | None, Header()] = None,
    ) -> TournamentRecord:
        # This must occur before capability validation. Otherwise a rejected
        # credential can brute-force administrative access without a budget.
        credential = _credential_from_header(authorization)
        limit(request, "admin")
        limit(request, "admin", _credential_subject(credential))
        try:
            return tournament_store.authorize_organizer(code.upper(), credential)
        except StoreError as error:
            _raise_store_error(error)

    def require_player(
        code: str,
        request: Request,
        authorization: Annotated[str | None, Header()] = None,
    ) -> tuple[TournamentRecord, PlayerRecord]:
        credential = _credential_from_header(authorization)
        limit(request, "player_auth_ip")
        limit(request, "player_auth", _credential_subject(credential))
        try:
            return tournament_store.authorize_player(code.upper(), credential)
        except StoreError as error:
            _raise_store_error(error)

    def require_room(
        code: str,
        request: Request,
        authorization: Annotated[str | None, Header()] = None,
    ) -> TournamentRecord:
        """Authorize either room capability without turning a view into public data."""
        credential = _credential_from_header(authorization)
        limit(request, "player_auth_ip")
        limit(request, "player_auth", _credential_subject(credential))
        try:
            return tournament_store.authorize_organizer(code.upper(), credential)
        except StoreError:
            try:
                tournament, _ = tournament_store.authorize_player(code.upper(), credential)
                return tournament
            except StoreError as error:
                _raise_store_error(error)

    realtime_ticket_codec = None
    if isinstance(tournament_store, PostgresTournamentStore):
        from realtime.postgres import PostgresOutboxWorker, PostgresRealtimeStore
        from realtime.tickets import SignedTicketCodec, TicketVerifier
        from realtime.websocket import DatabaseBackedEventStream, OriginPolicy, register_realtime_endpoint

        signing_key = getenv("REALTIME_TICKET_SIGNING_KEY")
        if not signing_key:
            raise RuntimeError("REALTIME_TICKET_SIGNING_KEY is required when DATABASE_URL is configured.")
        realtime_store = PostgresRealtimeStore(database_url or "")
        realtime_ticket_codec = SignedTicketCodec(signing_key.encode("utf-8"))
        event_stream = DatabaseBackedEventStream(replay_store=realtime_store)
        outbox_worker = PostgresOutboxWorker(database_url or "", worker_id=f"backend-{uuid4()}")
        app.add_middleware(RealtimeRateLimitMiddleware, limiter=rate_limiter)
        register_realtime_endpoint(
            app,
            verifier=TicketVerifier(realtime_ticket_codec, realtime_store),
            stream=event_stream,
            origins=OriginPolicy(frozenset(_allowed_origins())),
        )

        async def drain_outbox() -> None:
            while True:
                try:
                    published = await outbox_worker.publish_one(event_stream)
                except Exception as error:
                    # A failed item remains leased/retryable.  Keep the
                    # server running, but do not hide an operational failure:
                    # the DB row has `last_error_code` and the process logs
                    # a redacted classification for alerting/health
                    # integration.
                    app.state.outbox_last_error = type(error).__name__
                    logger.warning("realtime outbox publish failed: %s", type(error).__name__)
                    published = False
                await asyncio.sleep(0.05 if published else 0.5)

        async def advance_competition() -> None:
            """Resume durable running tournaments one official Engine round at a time."""
            while True:
                try:
                    progressed = await asyncio.to_thread(
                        tournament_store.advance_one_running_tournament, engine_gateway
                    )
                except Exception as error:
                    app.state.competition_last_error = type(error).__name__
                    logger.exception("official competition transition failed")
                    progressed = False
                await asyncio.sleep(0.1 if progressed else 0.5)

        @app.on_event("startup")
        async def start_outbox_worker() -> None:
            app.state.outbox_task = asyncio.create_task(drain_outbox())
            app.state.competition_task = asyncio.create_task(advance_competition())
            logger.info("durable realtime and competition workers started")

        @app.on_event("shutdown")
        async def stop_outbox_worker() -> None:
            for task_name in ("competition_task", "outbox_task"):
                task = getattr(app.state, task_name, None)
                if task is not None:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            logger.info("durable realtime and competition workers stopped")

    @app.get("/health", tags=["system"])
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/tournaments", status_code=status.HTTP_201_CREATED, tags=["tournaments"])
    def create_tournament(intent: CreateTournamentIntent) -> dict[str, object]:
        tournament, organizer_token = tournament_store.create_tournament(
            intent.capacity,
            intent.hearts_required,
            sound_effects_enabled=intent.sound_effects_enabled,
            background_music_enabled=intent.background_music_enabled,
            movement_speed=intent.movement_speed,
            countdown_speed=intent.countdown_speed,
        )
        logger.info("tournament created tournament_id=%s", tournament.id)
        # This is the only response that contains the organizer capability.
        return {
            "tournament_id": tournament.id,
            "tournament_code": tournament.code,
            "organizer_access_token": organizer_token,
            "organizer_token_expires_at": tournament.organizer_token_expires_at.isoformat(),
            "sound_effects_enabled": tournament.sound_effects_enabled,
            "background_music_enabled": tournament.background_music_enabled,
            "hearts_required": tournament.hearts_required,
            "movement_speed": tournament.movement_speed,
            "countdown_speed": tournament.countdown_speed,
        }

    @app.post("/v1/tournaments/join", status_code=status.HTTP_201_CREATED, tags=["players"])
    def join_tournament(intent: JoinTournamentIntent, request: Request) -> dict[str, object]:
        limit(request, "join")
        try:
            tournament, player, player_token = tournament_store.join(
                intent.tournament_code, intent.display_name, intent.animal_id
            )
        except StoreError as error:
            _raise_store_error(error)
        return {
            "tournament_id": tournament.id,
            "tournament_code": tournament.code,
            "hearts_required": tournament.hearts_required,
            "movement_speed": tournament.movement_speed,
            "countdown_speed": tournament.countdown_speed,
            "player": _player_view(player),
            "player_access_token": player_token,
        }

    @app.get("/v1/tournaments/{code}/players/me", tags=["players"])
    def get_current_player(
        room: tuple[TournamentRecord, PlayerRecord] = Depends(require_player),
    ) -> dict[str, object]:
        tournament, player = room
        return {
            "tournament_id": tournament.id,
            "tournament_code": tournament.code,
            "tournament_started": tournament.started,
            "hearts_required": tournament.hearts_required,
            "movement_speed": tournament.movement_speed,
            "countdown_speed": tournament.countdown_speed,
            "player": _player_view(player),
        }

    @app.put("/v1/tournaments/{code}/players/me/strategy", status_code=status.HTTP_204_NO_CONTENT, tags=["players"])
    def save_strategy(
        intent: StrategyIntent,
        request: Request,
        authorization: Annotated[str | None, Header()] = None,
        room: tuple[TournamentRecord, PlayerRecord] = Depends(require_player),
    ) -> Response:
        credential = _credential_from_header(authorization)
        limit(request, "strategy")
        limit(request, "strategy", _credential_subject(credential))
        tournament, player = room
        try:
            tournament_store.save_strategy(tournament, player, intent)
        except StoreError as error:
            _raise_store_error(error)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post("/v1/tournaments/{code}/players/me/ready", status_code=status.HTTP_204_NO_CONTENT, tags=["players"])
    def mark_ready(
        intent: EmptyIntent,
        request: Request,
        authorization: Annotated[str | None, Header()] = None,
        room: tuple[TournamentRecord, PlayerRecord] = Depends(require_player),
    ) -> Response:
        credential = _credential_from_header(authorization)
        limit(request, "strategy")
        limit(request, "strategy", _credential_subject(credential))
        tournament, player = room
        try:
            tournament_store.mark_ready(tournament, player)
        except StoreError as error:
            _raise_store_error(error)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post("/v1/tournaments/{code}/training/choice", tags=["training"])
    def submit_training_choice(
        intent: TrainingChoiceIntent,
        request: Request,
        authorization: Annotated[str | None, Header()] = None,
        room: tuple[TournamentRecord, PlayerRecord] = Depends(require_player),
    ) -> object:
        credential = _credential_from_header(authorization)
        limit(request, "training")
        limit(request, "training", _credential_subject(credential))
        tournament, player = room
        if tournament.started or not player.ready or player.strategy is None:
            raise HTTPException(status_code=409, detail="Training is not available.")
        session = tournament_store.training_session_for(tournament, player)
        command = TrainingChoiceCommand(
            training_id=session.training_id if session else str(uuid4()),
            player_id=player.id,
            hearts_required=tournament.hearts_required,
            strategy=dict(player.strategy),
            move=intent.move,
            state=session.state if session else None,
        )
        try:
            result = engine_gateway.run_training_choice(command)
        except EngineUnavailable as error:
            raise HTTPException(status_code=503, detail="Training is temporarily unavailable.") from error
        try:
            tournament_store.save_training_session(tournament, player, result.training_id, result.state)
        except StoreError as error:
            _raise_store_error(error)
        return {"training_id": result.training_id, "state": result.snapshot}

    @app.post("/v1/training/guest/choice", tags=["training"])
    def submit_guest_training_choice(
        intent: GuestTrainingChoiceIntent,
        request: Request,
        training_session: Annotated[str | None, Header(alias="X-Training-Session")] = None,
    ) -> object:
        """Run a server-calculated, non-persistent practice without a room."""
        limit(request, "guest_training")
        session_id = training_session if training_session in guest_training_sessions else str(uuid4())
        command = TrainingChoiceCommand(
            training_id=session_id,
            player_id="guest-character",
            hearts_required=intent.hearts_required,
            strategy=intent.strategy.model_dump(),
            move=intent.move,
            state=guest_training_sessions.get(session_id),
        )
        try:
            result = engine_gateway.run_training_choice(command)
        except EngineUnavailable as error:
            raise HTTPException(status_code=503, detail="Training is temporarily unavailable.") from error
        if result.snapshot.get("status") == "completed":
            guest_training_sessions.pop(session_id, None)
        else:
            guest_training_sessions[session_id] = result.state
        return {"training_id": result.training_id, "state": result.snapshot}

    @app.post("/v1/tournaments/{code}/training/reset", status_code=status.HTTP_204_NO_CONTENT, tags=["training"])
    def reset_training(
        request: Request,
        authorization: Annotated[str | None, Header()] = None,
        room: tuple[TournamentRecord, PlayerRecord] = Depends(require_player),
    ) -> Response:
        """Start a fresh isolated practice session after a previous simulation."""
        credential = _credential_from_header(authorization)
        limit(request, "training")
        limit(request, "training", _credential_subject(credential))
        tournament, player = room
        if tournament.started or not player.ready or player.strategy is None:
            raise HTTPException(status_code=409, detail="Training is not available.")
        try:
            tournament_store.clear_training_session(tournament, player)
        except StoreError as error:
            _raise_store_error(error)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.get("/v1/tournaments/{code}/admin/participants", tags=["admin"])
    def list_participants(
        request: Request,
        authorization: Annotated[str | None, Header()] = None,
        tournament: TournamentRecord = Depends(require_organizer),
    ) -> dict[str, object]:
        # Keep removals visible to the organizer as room history. They remain
        # excluded from capacity and from the confirmed-player start rule.
        participants = [_player_view(player) for player in tournament.players.values()]
        return {"tournament_id": tournament.id, "tournament_code": tournament.code, "participants": participants}

    @app.patch("/v1/tournaments/{code}/admin/configuration", tags=["admin"])
    def update_configuration(
        intent: TournamentConfigurationIntent,
        request: Request,
        authorization: Annotated[str | None, Header()] = None,
        tournament: TournamentRecord = Depends(require_organizer),
    ) -> dict[str, object]:
        try:
            tournament_store.update_configuration(
                tournament,
                intent.capacity,
                intent.hearts_required,
                intent.sound_effects_enabled,
                intent.background_music_enabled,
                intent.movement_speed,
                intent.countdown_speed,
            )
        except StoreError as error:
            _raise_store_error(error)
        return {
            "capacity": tournament.capacity,
            "hearts_required": tournament.hearts_required,
            "sound_effects_enabled": tournament.sound_effects_enabled,
            "background_music_enabled": tournament.background_music_enabled,
            "movement_speed": tournament.movement_speed,
            "countdown_speed": tournament.countdown_speed,
        }

    @app.post("/v1/tournaments/{code}/admin/close-registration", status_code=status.HTTP_204_NO_CONTENT, tags=["admin"])
    def close_registration(
        intent: EmptyIntent,
        request: Request,
        authorization: Annotated[str | None, Header()] = None,
        tournament: TournamentRecord = Depends(require_organizer),
    ) -> Response:
        try:
            tournament_store.close_registration(tournament)
        except StoreError as error:
            _raise_store_error(error)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.delete("/v1/tournaments/{code}/admin/players/{player_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["admin"])
    def remove_player(
        player_id: str,
        request: Request,
        authorization: Annotated[str | None, Header()] = None,
        tournament: TournamentRecord = Depends(require_organizer),
    ) -> Response:
        try:
            tournament_store.remove_player(tournament, player_id)
        except StoreError as error:
            _raise_store_error(error)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post("/v1/tournaments/{code}/admin/start", tags=["admin"])
    def start_tournament(
        intent: EmptyIntent,
        request: Request,
        authorization: Annotated[str | None, Header()] = None,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")] = "",
        tournament: TournamentRecord = Depends(require_organizer),
    ) -> dict[str, object]:
        credential = _credential_from_header(authorization)
        if isinstance(tournament_store, PostgresTournamentStore):
            try:
                result = tournament_store.start_tournament_atomic(
                    code=tournament.code,
                    credential=credential,
                    idempotency_key=idempotency_key,
                    engine=engine_gateway,
                )
                logger.info("tournament start processed tournament_id=%s", tournament.id)
                return result
            except EngineUnavailable as error:
                raise HTTPException(status_code=503, detail="Official tournament start is temporarily unavailable.") from error
            except StoreError as error:
                _raise_store_error(error)
        players = tournament_store.ready_players_snapshot(tournament)
        if len(players) < 2:
            raise HTTPException(status_code=409, detail="At least two confirmed participants are required.")
        command = StartTournamentCommand(
            tournament_id=tournament.id,
            hearts_required=tournament.hearts_required,
            players=tuple(
                EnginePlayerSnapshot(player_id=player.id, strategy=dict(player.strategy or {})) for player in players
            ),
        )
        try:
            result = engine_gateway.start_tournament(command)
        except EngineUnavailable as error:
            # No official fields were mutated; clients cannot bypass the Engine.
            raise HTTPException(status_code=503, detail="Official tournament start is temporarily unavailable.") from error
        try:
            tournament_store.commit_started(
                tournament,
                tuple(player.id for player in players),
                state_reference=result.state_reference,
                state_snapshot=result.snapshot,
            )
        except StoreError as error:
            _raise_store_error(error)
        logger.info("tournament start processed tournament_id=%s", tournament.id)
        return {
            "status": "started",
            "tournament_id": tournament.id,
            "state_reference": result.state_reference,
        }

    @app.post("/v1/tournaments/{code}/admin/repeat", tags=["admin"])
    def repeat_tournament(
        intent: RepeatTournamentIntent,
        authorization: Annotated[str | None, Header()] = None,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")] = "",
        tournament: TournamentRecord = Depends(require_organizer),
    ) -> dict[str, object]:
        if not isinstance(tournament_store, PostgresTournamentStore):
            raise HTTPException(status_code=503, detail="Repeating requires durable persistence.")
        try:
            return tournament_store.repeat_tournament_atomic(code=tournament.code,
                credential=_credential_from_header(authorization),idempotency_key=idempotency_key,
                expected_run_id=intent.expected_run_id,engine=engine_gateway)
        except StoreError as error:
            _raise_store_error(error)
        except EngineUnavailable as error:
            raise HTTPException(status_code=503, detail="New execution is temporarily unavailable.") from error

    @app.post("/v1/tournaments/{code}/realtime/ticket", tags=["realtime"])
    def issue_realtime_ticket(
        request: Request,
        code: str,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, object]:
        credential = _credential_from_header(authorization)
        limit(request, "realtime")
        limit(request, "realtime", _credential_subject(credential))
        if not isinstance(tournament_store, PostgresTournamentStore) or realtime_ticket_codec is None:
            raise HTTPException(status_code=503, detail="Realtime is not configured for this environment.")
        try:
            ticket, expires_at = tournament_store.issue_realtime_ticket(code.upper(), credential, realtime_ticket_codec)
        except StoreError as error:
            _raise_store_error(error)
        return {"ticket": ticket, "expires_at": expires_at.isoformat()}

    @app.get("/v1/tournaments/{code}/official-state", tags=["tournaments"])
    def get_official_state(
        request: Request,
        tournament: TournamentRecord = Depends(require_room),
    ) -> dict[str, object]:
        """Authenticated fallback snapshot for replay gaps and reconnects.

        This is intentionally a server-produced public projection, never the
        canonical Engine document that holds private strategies.
        """
        if not tournament.started:
            raise HTTPException(status_code=409, detail="Official tournament state is not available.")
        try:
            if isinstance(tournament_store, PostgresTournamentStore):
                snapshot, state_version, start_sequence, presentation = tournament_store.official_state_snapshot_for(tournament)
            else:
                snapshot = tournament.official_state_snapshot
                state_version = None
            if snapshot is None:
                raise StoreError("Official tournament state is not available.")
            public = official_state_view(tournament, snapshot, state_version=state_version)
            if isinstance(tournament_store, PostgresTournamentStore):
                public["run_start_sequence"] = start_sequence
                if presentation:
                    public.update(presentation)
            # Available even before the first duel, so every viewer can
            # calibrate its clock before the first realtime event arrives.
            public["server_received_at_ms"] = request.state.server_received_at_ms
            public["server_time_ms"] = int(time() * 1000)
            return public
        except StoreError as error:
            _raise_store_error(error)

    @app.post("/v1/tournaments/{code}/admin/access/revoke", status_code=status.HTTP_204_NO_CONTENT, tags=["admin"])
    def revoke_organizer_access(
        intent: EmptyIntent,
        request: Request,
        authorization: Annotated[str | None, Header()] = None,
        tournament: TournamentRecord = Depends(require_organizer),
    ) -> Response:
        tournament_store.revoke_organizer_access(tournament)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return app


# Uvicorn imports this name.  Missing durable configuration is intentionally a
# process-start failure instead of an unsafe fallback to process-local memory.
app = create_app()

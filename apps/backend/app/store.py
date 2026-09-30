"""In-memory local-development repository and room authorization checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from hmac import compare_digest
from typing import Callable
from uuid import uuid4

from .models import StrategyIntent
from .security import generate_access_token, generate_tournament_code


def utc_now() -> datetime:
    return datetime.now(UTC)


def credential_digest(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


@dataclass
class PlayerRecord:
    id: str
    display_name: str
    animal_id: str
    access_token_digest: str
    strategy: dict[str, object] | None = None
    ready: bool = False
    strategy_locked: bool = False
    removed: bool = False


@dataclass
class TrainingSessionRecord:
    """Server-held simulation state; it is never part of tournament state."""

    training_id: str
    state: object


@dataclass
class TournamentRecord:
    id: str
    code: str
    capacity: int
    hearts_required: int
    organizer_token_digest: str
    organizer_token_expires_at: datetime
    sound_effects_enabled: bool = True
    background_music_enabled: bool = True
    movement_speed: str = "1"
    countdown_speed: str = "1"
    organizer_token_revoked: bool = False
    registration_open: bool = True
    started: bool = False
    players: dict[str, PlayerRecord] = field(default_factory=dict)
    official_state_reference: str | None = None
    official_state_snapshot: dict[str, object] | None = None
    training_sessions: dict[str, TrainingSessionRecord] = field(default_factory=dict)


class StoreError(Exception):
    status_code = 409
    detail = "Tournament state does not allow this operation."


class TournamentUnavailable(StoreError):
    status_code = 404
    detail = "Tournament is not available."


class RoomForbidden(StoreError):
    status_code = 403
    detail = "You are not authorized for this room."


class InvalidCredential(StoreError):
    status_code = 401
    detail = "A valid room credential is required."


class InMemoryTournamentStore:
    """Reference adapter only. Never use it for a multi-instance deployment."""

    def __init__(
        self,
        now: Callable[[], datetime] = utc_now,
        organizer_token_ttl: timedelta = timedelta(hours=12),
    ) -> None:
        self._now = now
        self._organizer_token_ttl = organizer_token_ttl
        self._tournaments: dict[str, TournamentRecord] = {}

    def create_tournament(
        self,
        capacity: int,
        hearts_required: int,
        *,
        sound_effects_enabled: bool = True,
        background_music_enabled: bool = True,
        movement_speed: str = "1",
        countdown_speed: str = "1",
    ) -> tuple[TournamentRecord, str]:
        for _ in range(5):
            code = generate_tournament_code()
            if code not in self._tournaments:
                token = generate_access_token()
                tournament = TournamentRecord(
                    id=str(uuid4()),
                    code=code,
                    capacity=capacity,
                    hearts_required=hearts_required,
                    sound_effects_enabled=sound_effects_enabled,
                    background_music_enabled=background_music_enabled,
                    movement_speed=movement_speed,
                    countdown_speed=countdown_speed,
                    organizer_token_digest=credential_digest(token),
                    organizer_token_expires_at=self._now() + self._organizer_token_ttl,
                )
                self._tournaments[code] = tournament
                return tournament, token
        raise RuntimeError("Could not allocate an opaque tournament code.")

    def get_available_tournament(self, code: str) -> TournamentRecord:
        tournament = self._tournaments.get(code)
        if tournament is None or not tournament.registration_open or tournament.started:
            raise TournamentUnavailable()
        return tournament

    def get_tournament(self, code: str) -> TournamentRecord:
        tournament = self._tournaments.get(code)
        if tournament is None:
            raise TournamentUnavailable()
        return tournament

    def _credential_is_known(self, credential: str) -> bool:
        digest = credential_digest(credential)
        for tournament in self._tournaments.values():
            if compare_digest(tournament.organizer_token_digest, digest):
                return True
            if any(compare_digest(player.access_token_digest, digest) for player in tournament.players.values()):
                return True
        return False

    def authorize_organizer(self, code: str, credential: str | None) -> TournamentRecord:
        tournament = self.get_tournament(code)
        if not credential:
            raise InvalidCredential()
        digest = credential_digest(credential)
        if not compare_digest(tournament.organizer_token_digest, digest):
            if self._credential_is_known(credential):
                raise RoomForbidden()
            raise InvalidCredential()
        if tournament.organizer_token_revoked or self._now() >= tournament.organizer_token_expires_at:
            raise InvalidCredential()
        return tournament

    def authorize_player(self, code: str, credential: str | None) -> tuple[TournamentRecord, PlayerRecord]:
        tournament = self.get_tournament(code)
        if not credential:
            raise InvalidCredential()
        digest = credential_digest(credential)
        for player in tournament.players.values():
            if compare_digest(player.access_token_digest, digest):
                if player.removed:
                    raise InvalidCredential()
                return tournament, player
        if self._credential_is_known(credential):
            raise RoomForbidden()
        raise InvalidCredential()

    def join(self, code: str, display_name: str, animal_id: str) -> tuple[TournamentRecord, PlayerRecord, str]:
        tournament = self.get_available_tournament(code)
        active_players = [player for player in tournament.players.values() if not player.removed]
        if len(active_players) >= tournament.capacity:
            raise TournamentUnavailable()
        token = generate_access_token()
        player = PlayerRecord(
            # Player identity crosses the Engine, persisted snapshots and
            # realtime. Keep one canonical hyphenated UUID everywhere.
            id=str(uuid4()),
            display_name=display_name,
            animal_id=animal_id,
            access_token_digest=credential_digest(token),
        )
        tournament.players[player.id] = player
        return tournament, player, token

    def save_strategy(self, tournament: TournamentRecord, player: PlayerRecord, strategy: StrategyIntent) -> None:
        if tournament.started or player.strategy_locked:
            raise StoreError()
        player.strategy = strategy.model_dump(mode="json")

    def mark_ready(self, tournament: TournamentRecord, player: PlayerRecord) -> None:
        if tournament.started or player.strategy_locked or player.strategy is None:
            raise StoreError()
        player.ready = True

    def update_configuration(
        self,
        tournament: TournamentRecord,
        capacity: int,
        hearts_required: int,
        sound_effects_enabled: bool,
        background_music_enabled: bool,
        movement_speed: str,
        countdown_speed: str,
    ) -> None:
        if tournament.started:
            raise StoreError()
        active_players = sum(not player.removed for player in tournament.players.values())
        if capacity < active_players:
            raise StoreError()
        tournament.capacity = capacity
        tournament.hearts_required = hearts_required
        tournament.sound_effects_enabled = sound_effects_enabled
        tournament.background_music_enabled = background_music_enabled
        tournament.movement_speed = movement_speed
        tournament.countdown_speed = countdown_speed

    def close_registration(self, tournament: TournamentRecord) -> None:
        if tournament.started:
            raise StoreError()
        tournament.registration_open = False

    def remove_player(self, tournament: TournamentRecord, player_id: str) -> None:
        if tournament.started:
            raise StoreError()
        player = tournament.players.get(player_id)
        if player is None or player.removed:
            raise TournamentUnavailable()
        player.removed = True

    def ready_players_snapshot(self, tournament: TournamentRecord) -> tuple[PlayerRecord, ...]:
        return tuple(
            player
            for player in tournament.players.values()
            if not player.removed and player.ready and player.strategy is not None
        )

    def commit_started(
        self,
        tournament: TournamentRecord,
        player_ids: tuple[str, ...],
        *,
        state_reference: str,
        state_snapshot: dict[str, object],
    ) -> None:
        if tournament.started:
            raise StoreError()
        if len(player_ids) < 2 or len(player_ids) != len(set(player_ids)):
            raise StoreError()
        if any(
            player_id not in tournament.players
            or tournament.players[player_id].removed
            or not tournament.players[player_id].ready
            or tournament.players[player_id].strategy is None
            for player_id in player_ids
        ):
            raise StoreError()
        tournament.registration_open = False
        tournament.started = True
        tournament.official_state_reference = state_reference
        tournament.official_state_snapshot = state_snapshot
        # Training is explicitly isolated and must terminate at official start.
        tournament.training_sessions.clear()
        for player_id in player_ids:
            tournament.players[player_id].strategy_locked = True

    def training_session_for(self, tournament: TournamentRecord, player: PlayerRecord) -> TrainingSessionRecord | None:
        if tournament.started or player.removed:
            raise StoreError()
        return tournament.training_sessions.get(player.id)

    def save_training_session(
        self,
        tournament: TournamentRecord,
        player: PlayerRecord,
        training_id: str,
        state: object,
    ) -> None:
        if tournament.started or player.removed:
            raise StoreError()
        tournament.training_sessions[player.id] = TrainingSessionRecord(training_id=training_id, state=state)

    def revoke_organizer_access(self, tournament: TournamentRecord) -> None:
        tournament.organizer_token_revoked = True

"""PostgreSQL repository for the authoritative tournament aggregate.

The in-memory store remains useful to unit-test the HTTP boundary.  This
adapter is the deployment path: capabilities, strategy documents, Engine
snapshots, transitions, events and outbox rows are committed together.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any, Callable
from uuid import UUID, uuid4

from rps_game_engine import tournament_state_from_snapshot

from .competitive_events import events_for_round
from .engine_gateway import EnginePlayerSnapshot, EngineUnavailable, GameEngineGateway, StartTournamentCommand
from .models import StrategyIntent
from .public_state import official_state_view
from .security import generate_access_token, generate_tournament_code
from .store import (
    InvalidCredential,
    PlayerRecord,
    RoomForbidden,
    StoreError,
    TrainingSessionRecord,
    TournamentRecord,
    TournamentUnavailable,
    credential_digest,
    utc_now,
)


class InvalidIdempotencyKey(StoreError):
    status_code = 422
    detail = "Idempotency-Key must be a UUID."


class IdempotencyConflict(StoreError):
    status_code = 409
    detail = "Idempotency-Key was already used for a different request."


class PostgresTournamentStore:
    """Durable adapter. Every mutation scopes SQL by canonical tournament UUID."""

    persistent = True

    def __init__(
        self,
        database_url: str,
        now: Callable[[], datetime] = utc_now,
        organizer_token_ttl: timedelta = timedelta(hours=12),
        player_token_ttl: timedelta = timedelta(hours=12),
    ) -> None:
        self._database_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        self._now = now
        self._organizer_token_ttl = organizer_token_ttl
        self._player_token_ttl = player_token_ttl
        # Training never contributes to the official aggregate. It is kept
        # deliberately outside PostgreSQL state until a future UX requirement
        # calls for resumable training sessions.
        self._training_sessions: dict[tuple[str, str], TrainingSessionRecord] = {}

    def _connect(self):
        try:
            import psycopg
        except ImportError as error:  # pragma: no cover - deployment configuration
            raise RuntimeError("psycopg is required for the PostgreSQL tournament store") from error
        return psycopg.connect(self._database_url)

    @staticmethod
    def _rules(
        hearts_required: int,
        animals: dict[str, str] | None = None,
        *,
        sound_effects_enabled: bool = True,
        background_music_enabled: bool = True,
        movement_speed: str = "1",
        countdown_speed: str = "1",
    ) -> dict[str, object]:
        return {
            "hearts_required": hearts_required,
            "sound_effects_enabled": sound_effects_enabled,
            "background_music_enabled": background_music_enabled,
            "movement_speed": movement_speed,
            "countdown_speed": countdown_speed,
            "animals": animals or {},
            "registration_open": True,
        }

    @staticmethod
    def _read_rules(value: object) -> dict[str, object]:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            loaded = json.loads(value)
            if isinstance(loaded, dict):
                return loaded
        raise RuntimeError("Persisted tournament rules are invalid.")

    @staticmethod
    def _record(row: tuple[Any, ...], players: dict[str, PlayerRecord] | None = None) -> TournamentRecord:
        room_id, code, status, capacity, rules = row
        parsed_rules = PostgresTournamentStore._read_rules(rules)
        hearts = parsed_rules.get("hearts_required")
        if isinstance(hearts, bool) or not isinstance(hearts, int) or hearts < 1:
            raise RuntimeError("Persisted hearts_required is invalid.")
        registration_open = parsed_rules.get("registration_open", True)
        if not isinstance(registration_open, bool):
            raise RuntimeError("Persisted registration_open is invalid.")
        sound_effects_enabled = parsed_rules.get("sound_effects_enabled", True)
        background_music_enabled = parsed_rules.get("background_music_enabled", True)
        if not isinstance(sound_effects_enabled, bool) or not isinstance(background_music_enabled, bool):
            raise RuntimeError("Persisted audio configuration is invalid.")
        movement_speed = parsed_rules.get("movement_speed", "1")
        countdown_speed = parsed_rules.get("countdown_speed", "1")
        if movement_speed not in {"0.5", "1", "2", "4", "8"} or countdown_speed not in {"0.5", "1", "2", "4", "8"}:
            raise RuntimeError("Persisted presentation speed is invalid.")
        return TournamentRecord(
            id=str(room_id),
            code=code,
            capacity=capacity,
            hearts_required=hearts,
            organizer_token_digest="",  # capabilities are queried directly.
            organizer_token_expires_at=datetime.max.replace(tzinfo=UTC),
            sound_effects_enabled=sound_effects_enabled,
            background_music_enabled=background_music_enabled,
            movement_speed=movement_speed,
            countdown_speed=countdown_speed,
            registration_open=status == "lobby" and registration_open,
            started=status in {"running", "completed"},
            players=players or {},
        )

    def _get_tournament_row(self, cursor, code: str, *, lock: bool = False) -> tuple[Any, ...]:
        cursor.execute(
            "SELECT id, access_code, status, capacity, rules FROM tournaments WHERE access_code = %s" + (" FOR UPDATE" if lock else ""),
            (code,),
        )
        row = cursor.fetchone()
        if row is None:
            raise TournamentUnavailable()
        return row

    def _load_players(self, cursor, tournament: TournamentRecord) -> dict[str, PlayerRecord]:
        cursor.execute(
            """
            SELECT member.id, member.display_name, member.membership_status,
                   strategy.strategy_document, strategy.locked_at
              FROM tournament_members member
              LEFT JOIN player_strategies strategy
                ON strategy.tournament_id = member.tournament_id
               AND strategy.member_id = member.id
               AND strategy.locked_at IS NULL
             WHERE member.tournament_id = %s AND member.role = 'participant'
             ORDER BY member.created_at, member.id
            """,
            (tournament.id,),
        )
        # A DB-API cursor holds only the result of its most recent statement.
        # Materialize members before reading the rules below; otherwise the
        # second SELECT silently replaces this result and a durable aggregate
        # appears to have no participants.
        member_rows = cursor.fetchall()
        cursor.execute("SELECT rules FROM tournaments WHERE id = %s", (tournament.id,))
        rules_row = cursor.fetchone()
        rules = self._read_rules(rules_row[0]) if rules_row else {}
        animals = rules.get("animals", {})
        if not isinstance(animals, dict):
            animals = {}
        players: dict[str, PlayerRecord] = {}
        for player_id, name, member_status, strategy, locked_at in member_rows:
            canonical_id = str(player_id)
            players[canonical_id] = PlayerRecord(
                id=canonical_id,
                display_name=name,
                animal_id=str(animals.get(canonical_id, "unknown")),
                access_token_digest="",
                strategy=self._read_rules(strategy) if strategy is not None else None,
                ready=member_status == "ready",
                strategy_locked=locked_at is not None or tournament.started,
                removed=member_status == "removed",
                membership_status=member_status,
            )
        return players

    def _tournament(self, cursor, code: str, *, lock: bool = False) -> TournamentRecord:
        tournament = self._record(self._get_tournament_row(cursor, code, lock=lock))
        tournament.players = self._load_players(cursor, tournament)
        return tournament

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
            tournament_id, organizer_subject_id, capability_id = uuid4(), uuid4(), uuid4()
            code, token = generate_tournament_code(), generate_access_token()
            expires_at = self._now() + self._organizer_token_ttl
            try:
                with self._connect() as connection, connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO tournaments (id, access_code, organizer_subject_id, capacity, rules)
                        VALUES (%s, %s, %s, %s, %s::jsonb)
                        """,
                        (
                            str(tournament_id),
                            code,
                            str(organizer_subject_id),
                            capacity,
                            json.dumps(
                                self._rules(
                                    hearts_required,
                                    sound_effects_enabled=sound_effects_enabled,
                                    background_music_enabled=background_music_enabled,
                                    movement_speed=movement_speed,
                                    countdown_speed=countdown_speed,
                                )
                            ),
                        ),
                    )
                    cursor.execute(
                        """
                        INSERT INTO tournament_access_capabilities
                          (id, tournament_id, subject_id, role, secret_hash, expires_at)
                        VALUES (%s, %s, %s, 'organizer', %s, %s)
                        """,
                        (str(capability_id), str(tournament_id), str(organizer_subject_id), credential_digest(token), expires_at),
                    )
                    return (
                        TournamentRecord(
                            id=str(tournament_id), code=code, capacity=capacity, hearts_required=hearts_required,
                            organizer_token_digest=credential_digest(token), organizer_token_expires_at=expires_at,
                            sound_effects_enabled=sound_effects_enabled,
                            background_music_enabled=background_music_enabled,
                            movement_speed=movement_speed,
                            countdown_speed=countdown_speed,
                        ),
                        token,
                    )
            except Exception as error:
                # A code collision is extraordinarily unlikely but recoverable; other
                # database errors must remain visible to operations.
                if "access_code" not in str(error):
                    raise
        raise RuntimeError("Could not allocate an opaque tournament code.")

    def get_available_tournament(self, code: str) -> TournamentRecord:
        with self._connect() as connection, connection.cursor() as cursor:
            tournament = self._tournament(cursor, code)
            if not tournament.registration_open or tournament.started:
                raise TournamentUnavailable()
            return tournament

    def get_tournament(self, code: str) -> TournamentRecord:
        with self._connect() as connection, connection.cursor() as cursor:
            return self._tournament(cursor, code)

    def official_state_snapshot_for(self, tournament: TournamentRecord) -> tuple[dict[str, object], int, int]:
        """Load the latest durable Engine snapshot without exposing it directly."""
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT s.state_document, s.state_version, r.start_sequence
                     FROM official_state_snapshots s JOIN tournaments t ON t.id=s.tournament_id
                     JOIN tournament_runs r ON r.tournament_id=t.id AND r.id=t.current_run_id
                    WHERE s.tournament_id = %s
                 ORDER BY s.state_version DESC
                    LIMIT 1""",
                (tournament.id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise StoreError("Official tournament state is not available.")
            snapshot = self._read_rules(row[0])
            if not isinstance(snapshot, dict) or not isinstance(row[1], int):
                raise RuntimeError("Persisted official state is invalid.")
            return snapshot, row[1], row[2]

    def _capability(self, cursor, tournament_id: str, credential: str | None, role: str | None = None) -> tuple[str, str, str]:
        if not credential:
            raise InvalidCredential()
        query = """
            SELECT id, subject_id, role
              FROM tournament_access_capabilities
             WHERE tournament_id = %s AND secret_hash = %s
               AND revoked_at IS NULL AND expires_at > CURRENT_TIMESTAMP
        """
        parameters: list[object] = [tournament_id, credential_digest(credential)]
        if role:
            query += " AND role = %s"
            parameters.append(role)
        cursor.execute(query, tuple(parameters))
        found = cursor.fetchone()
        if found is not None:
            return str(found[0]), str(found[1]), str(found[2])
        cursor.execute(
            "SELECT role FROM tournament_access_capabilities WHERE tournament_id = %s AND secret_hash = %s LIMIT 1",
            (tournament_id, credential_digest(credential)),
        )
        same_room = cursor.fetchone()
        if same_room is not None:
            # A revoked/expired capability is an authentication failure; an
            # active capability for a different role is an authorization one.
            if role is None or same_room[0] == role:
                raise InvalidCredential()
            raise RoomForbidden()
        cursor.execute(
            "SELECT 1 FROM tournament_access_capabilities WHERE secret_hash = %s LIMIT 1",
            (credential_digest(credential),),
        )
        if cursor.fetchone() is not None:
            raise RoomForbidden()
        raise InvalidCredential()

    def authorize_organizer(self, code: str, credential: str | None) -> TournamentRecord:
        with self._connect() as connection, connection.cursor() as cursor:
            tournament = self._tournament(cursor, code)
            self._capability(cursor, tournament.id, credential, "organizer")
            return tournament

    def authorize_player(self, code: str, credential: str | None) -> tuple[TournamentRecord, PlayerRecord]:
        with self._connect() as connection, connection.cursor() as cursor:
            tournament = self._tournament(cursor, code)
            _, subject_id, _ = self._capability(cursor, tournament.id, credential, "participant")
            player = tournament.players.get(subject_id)
            if player is None or player.removed:
                raise InvalidCredential()
            return tournament, player

    def join(self, code: str, display_name: str, animal_id: str) -> tuple[TournamentRecord, PlayerRecord, str]:
        with self._connect() as connection, connection.cursor() as cursor:
            tournament = self._tournament(cursor, code, lock=True)
            if not tournament.registration_open or tournament.started or sum(not player.removed for player in tournament.players.values()) >= tournament.capacity:
                raise TournamentUnavailable()
            player_id, capability_id, token = str(uuid4()), str(uuid4()), generate_access_token()
            expires_at = self._now() + self._player_token_ttl
            cursor.execute(
                """INSERT INTO tournament_members (id, tournament_id, subject_id, role, display_name)
                   VALUES (%s, %s, %s, 'participant', %s)""",
                (player_id, tournament.id, player_id, display_name),
            )
            cursor.execute(
                """INSERT INTO tournament_access_capabilities
                   (id, tournament_id, subject_id, role, secret_hash, expires_at)
                   VALUES (%s, %s, %s, 'participant', %s, %s)""",
                (capability_id, tournament.id, player_id, credential_digest(token), expires_at),
            )
            cursor.execute("SELECT rules FROM tournaments WHERE id = %s FOR UPDATE", (tournament.id,))
            rules = self._read_rules(cursor.fetchone()[0])
            animals = rules.setdefault("animals", {})
            if not isinstance(animals, dict):
                raise RuntimeError("Persisted tournament animal mapping is invalid.")
            animals[player_id] = animal_id
            cursor.execute("UPDATE tournaments SET rules = %s::jsonb, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (json.dumps(rules), tournament.id))
            player = PlayerRecord(player_id, display_name, animal_id, credential_digest(token))
            tournament.players[player_id] = player
            return tournament, player, token

    def save_strategy(self, tournament: TournamentRecord, player: PlayerRecord, strategy: StrategyIntent) -> None:
        payload = strategy.model_dump(mode="json")
        digest = sha256(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()).hexdigest()
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT status FROM tournaments WHERE id = %s FOR UPDATE", (tournament.id,))
            row = cursor.fetchone()
            if row is None or row[0] != "lobby":
                raise StoreError()
            cursor.execute(
                "SELECT id FROM player_strategies WHERE tournament_id = %s AND member_id = %s AND locked_at IS NULL FOR UPDATE",
                (tournament.id, player.id),
            )
            existing = cursor.fetchone()
            if existing:
                cursor.execute("UPDATE player_strategies SET strategy_document = %s::jsonb, strategy_digest = %s, saved_at = CURRENT_TIMESTAMP WHERE id = %s", (json.dumps(payload), digest, existing[0]))
            else:
                cursor.execute("INSERT INTO player_strategies (id, tournament_id, member_id, revision, strategy_document, strategy_digest) VALUES (%s, %s, %s, 1, %s::jsonb, %s)", (str(uuid4()), tournament.id, player.id, json.dumps(payload), digest))
            cursor.execute("UPDATE tournament_members SET membership_status = 'configuring_strategy', updated_at = CURRENT_TIMESTAMP WHERE id = %s AND tournament_id = %s", (player.id, tournament.id))

    def mark_ready(self, tournament: TournamentRecord, player: PlayerRecord) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT status FROM tournaments WHERE id = %s FOR UPDATE", (tournament.id,))
            if (row := cursor.fetchone()) is None or row[0] != "lobby":
                raise StoreError()
            cursor.execute("SELECT 1 FROM player_strategies WHERE tournament_id = %s AND member_id = %s AND locked_at IS NULL", (tournament.id, player.id))
            if cursor.fetchone() is None:
                raise StoreError()
            cursor.execute("UPDATE tournament_members SET membership_status = 'ready', updated_at = CURRENT_TIMESTAMP WHERE tournament_id = %s AND id = %s", (tournament.id, player.id))

    def ready_players_snapshot(self, tournament: TournamentRecord) -> tuple[PlayerRecord, ...]:
        return tuple(player for player in tournament.players.values() if not player.removed and player.ready and player.strategy is not None)

    def training_session_for(self, tournament: TournamentRecord, player: PlayerRecord) -> TrainingSessionRecord | None:
        if tournament.started or player.removed:
            raise StoreError()
        return self._training_sessions.get((tournament.id, player.id))

    def save_training_session(self, tournament: TournamentRecord, player: PlayerRecord, training_id: str, state: object) -> None:
        if tournament.started or player.removed:
            raise StoreError()
        self._training_sessions[(tournament.id, player.id)] = TrainingSessionRecord(training_id=training_id, state=state)

    def clear_training_session(self, tournament: TournamentRecord, player: PlayerRecord) -> None:
        """Discard ephemeral practice state; it is not authoritative tournament data."""
        if tournament.started or player.removed:
            raise StoreError()
        self._training_sessions.pop((tournament.id, player.id), None)

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
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT status, rules FROM tournaments WHERE id = %s FOR UPDATE", (tournament.id,))
            row = cursor.fetchone()
            if row is None or row[0] != "lobby" or capacity < sum(not player.removed for player in tournament.players.values()):
                raise StoreError()
            rules = self._read_rules(row[1])
            rules["hearts_required"] = hearts_required
            rules["sound_effects_enabled"] = sound_effects_enabled
            rules["background_music_enabled"] = background_music_enabled
            rules["movement_speed"] = movement_speed
            rules["countdown_speed"] = countdown_speed
            cursor.execute("UPDATE tournaments SET capacity = %s, rules = %s::jsonb, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (capacity, json.dumps(rules), tournament.id))
            tournament.capacity = capacity
            tournament.hearts_required = hearts_required
            tournament.sound_effects_enabled = sound_effects_enabled
            tournament.background_music_enabled = background_music_enabled
            tournament.movement_speed = movement_speed
            tournament.countdown_speed = countdown_speed

    def close_registration(self, tournament: TournamentRecord) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT rules FROM tournaments WHERE id = %s AND status = 'lobby' FOR UPDATE", (tournament.id,))
            row = cursor.fetchone()
            if row is None:
                raise StoreError()
            rules = self._read_rules(row[0]); rules["registration_open"] = False
            cursor.execute("UPDATE tournaments SET rules = %s::jsonb, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (json.dumps(rules), tournament.id))

    def remove_player(self, tournament: TournamentRecord, player_id: str) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT status FROM tournaments WHERE id = %s FOR UPDATE", (tournament.id,))
            if (row := cursor.fetchone()) is None or row[0] != "lobby":
                raise StoreError()
            cursor.execute("UPDATE tournament_members SET membership_status = 'removed', updated_at = CURRENT_TIMESTAMP WHERE tournament_id = %s AND id = %s AND role = 'participant' AND membership_status <> 'removed'", (tournament.id, player_id))
            if cursor.rowcount != 1:
                raise TournamentUnavailable()

    def revoke_organizer_access(self, tournament: TournamentRecord) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("UPDATE tournament_access_capabilities SET revoked_at = CURRENT_TIMESTAMP, revocation_reason = 'organizer_requested' WHERE tournament_id = %s AND role = 'organizer' AND revoked_at IS NULL", (tournament.id,))

    def issue_realtime_ticket(self, code: str, credential: str | None, codec) -> tuple[str, datetime]:
        """Issue a signed, short-lived ticket only after durable room authorization."""
        from realtime.tickets import TicketClaims

        now = self._now()
        # Ticket claims carry integer Unix seconds.  Persist the same whole-
        # second instants so PostgreSQL's active-ticket comparison cannot
        # reject a newly issued ticket merely because of sub-second precision.
        issued_at = datetime.fromtimestamp(int(now.timestamp()), UTC)
        expires_at = issued_at + timedelta(minutes=5)
        ticket_id = str(uuid4())
        with self._connect() as connection, connection.cursor() as cursor:
            tournament = self._tournament(cursor, code)
            capability_id, subject_id, role = self._capability(cursor, tournament.id, credential)
            claims = TicketClaims(
                ticket_id=ticket_id,
                subject_id=subject_id,
                tournament_id=tournament.id,
                role=role,
                not_before=int(issued_at.timestamp()),
                expires_at=int(expires_at.timestamp()),
            )
            cursor.execute(
                """INSERT INTO realtime_access_tickets
                   (id, tournament_id, capability_id, subject_id, role, issued_at, not_before, expires_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                # Keep all three timestamps from one application instant.  A
                # database DEFAULT CURRENT_TIMESTAMP can otherwise be a few
                # milliseconds later than `not_before`, violating the durable
                # ticket window constraint during a perfectly valid issuance.
                (ticket_id, tournament.id, capability_id, subject_id, role, issued_at, issued_at, expires_at),
            )
            return codec.issue(claims), expires_at

    def start_tournament_atomic(
        self, *, code: str, credential: str | None, idempotency_key: str, engine: GameEngineGateway
    ) -> dict[str, object]:
        """Lock, execute Engine, snapshot, event/outbox and response in one commit."""
        try:
            command_key = str(UUID(idempotency_key))
        except (ValueError, TypeError, AttributeError) as error:
            raise InvalidIdempotencyKey() from error
        request_fingerprint = sha256(b"POST /v1/tournaments/{code}/admin/start:v1:{}") .hexdigest()
        with self._connect() as connection, connection.cursor() as cursor:
            tournament = self._tournament(cursor, code, lock=True)
            _, actor_subject_id, _ = self._capability(cursor, tournament.id, credential, "organizer")
            cursor.execute(
                """INSERT INTO idempotency_commands (id, tournament_id, actor_subject_id, operation, idempotency_key, request_fingerprint)
                   VALUES (%s, %s, %s, 'start_tournament', %s, %s)
                   ON CONFLICT (tournament_id, actor_subject_id, operation, idempotency_key) DO NOTHING
                   RETURNING id""",
                (str(uuid4()), tournament.id, actor_subject_id, command_key, request_fingerprint),
            )
            inserted = cursor.fetchone()
            if inserted is None:
                cursor.execute("SELECT request_fingerprint, status, response FROM idempotency_commands WHERE tournament_id = %s AND actor_subject_id = %s AND operation = 'start_tournament' AND idempotency_key = %s", (tournament.id, actor_subject_id, command_key))
                fingerprint, command_status, response = cursor.fetchone()
                if fingerprint != request_fingerprint:
                    raise IdempotencyConflict()
                if command_status == "completed" and isinstance(response, dict):
                    return response
                raise StoreError()
            command_id = str(inserted[0])
            if tournament.started:
                raise StoreError()
            players = tuple(player for player in tournament.players.values() if not player.removed and player.ready and player.strategy is not None)
            if len(players) < 2:
                raise StoreError("At least two confirmed participants are required.")
            command = StartTournamentCommand(
                tournament_id=tournament.id, hearts_required=tournament.hearts_required,
                run_id=str(uuid4()),
                players=tuple(EnginePlayerSnapshot(player_id=player.id, strategy=dict(player.strategy or {})) for player in players),
            )
            result = engine.start_tournament(command)
            # Reject a malformed adapter result before it becomes durable state.
            try:
                restored_state = tournament_state_from_snapshot(result.snapshot)
            except Exception as error:
                raise EngineUnavailable("The Engine returned an invalid official snapshot.") from error
            if restored_state.tournament_id != tournament.id or restored_state.run_id != command.run_id:
                raise EngineUnavailable("The Engine returned a state for another tournament.")
            cursor.execute("UPDATE player_strategies SET locked_at = CURRENT_TIMESTAMP WHERE tournament_id = %s AND member_id = ANY(%s::uuid[]) AND locked_at IS NULL RETURNING id, member_id, strategy_document, strategy_digest", (tournament.id, [player.id for player in players]))
            locked = {str(member_id): (str(strategy_id), document, digest) for strategy_id, member_id, document, digest in cursor.fetchall()}
            if len(locked) != len(players):
                raise StoreError()
            snapshot_ids: dict[str, str] = {}
            for player in players:
                snapshot_id = str(uuid4()); snapshot_ids[player.id] = snapshot_id
                strategy_id, document, digest = locked[player.id]
                cursor.execute("""INSERT INTO official_player_snapshots (id, tournament_id, member_id, strategy_id, engine_player_id, display_name, animal_id, strategy_document, strategy_digest)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)""", (snapshot_id, tournament.id, player.id, strategy_id, player.id, player.display_name, player.animal_id, json.dumps(document), digest))
            cursor.execute("SELECT state_version, next_event_sequence FROM tournaments WHERE id = %s FOR UPDATE", (tournament.id,))
            previous_version, previous_sequence = cursor.fetchone()
            state_digest = sha256(json.dumps(result.snapshot, separators=(",", ":"), sort_keys=True).encode()).hexdigest()
            transition_id, event_id = str(uuid4()), str(uuid4())
            new_version, sequence = previous_version + 1, previous_sequence + 1
            cursor.execute("INSERT INTO tournament_runs (id,tournament_id,number,start_sequence,state_document) VALUES (%s,%s,1,%s,%s::jsonb)",
                (command.run_id,tournament.id,sequence,json.dumps(result.snapshot)))
            cursor.execute("UPDATE tournaments SET current_run_id=%s WHERE id=%s", (command.run_id,tournament.id))
            cursor.execute("UPDATE tournaments SET status = 'running', state_version = %s, next_event_sequence = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (new_version, sequence, tournament.id))
            cursor.execute("INSERT INTO official_transitions (id, tournament_id, command_id, transition_key, expected_state_version, resulting_state_version, state_digest) VALUES (%s, %s, %s, %s, %s, %s, %s)", (transition_id, tournament.id, command_id, str(uuid4()), previous_version, new_version, state_digest))
            cursor.execute("INSERT INTO official_state_snapshots (id, tournament_id, transition_id, state_version, state_document, state_digest) VALUES (%s, %s, %s, %s, %s::jsonb, %s)", (str(uuid4()), tournament.id, transition_id, new_version, json.dumps(result.snapshot), state_digest))
            current_round = result.snapshot.get("current_round")
            if isinstance(current_round, dict):
                for position, match in enumerate(current_round.get("matches", []), start=1):
                    battle = match.get("battle", {}) if isinstance(match, dict) else {}
                    if not isinstance(battle, dict):
                        raise EngineUnavailable("The Engine returned an invalid match snapshot.")
                    cursor.execute("""INSERT INTO official_matches (id, tournament_id, run_id, engine_match_id, bracket_round, bracket_position, player_one_snapshot_id, player_two_snapshot_id, status, match_state_document, state_digest)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)""", (str(uuid4()), tournament.id, command.run_id, match["match_id"], current_round["number"], position, snapshot_ids[battle["player_one_id"]], snapshot_ids[battle["player_two_id"]], match["status"], json.dumps(battle), sha256(json.dumps(battle, separators=(",", ":"), sort_keys=True).encode()).hexdigest()))
            public_payload = {"tournamentId": tournament.id, "runId": command.run_id, "stateVersion": new_version, "event": "tournament_started"}
            cursor.execute("INSERT INTO official_game_events (id, tournament_id, transition_id, sequence, event_type, public_payload) VALUES (%s, %s, %s, %s, 'tournament_started', %s::jsonb)", (event_id, tournament.id, transition_id, sequence, json.dumps(public_payload)))
            cursor.execute("INSERT INTO realtime_outbox (event_id, tournament_id) VALUES (%s, %s)", (event_id, tournament.id))
            response = {"status": "started", "tournament_id": tournament.id, "run_id": command.run_id, "state_reference": result.state_reference, "state_version": new_version}
            cursor.execute("UPDATE idempotency_commands SET status = 'completed', response = %s::jsonb, completed_at = CURRENT_TIMESTAMP WHERE id = %s AND tournament_id = %s", (json.dumps(response), command_id, tournament.id))
            for player in players:
                self._training_sessions.pop((tournament.id, player.id), None)
            return response

    def repeat_tournament_atomic(self, *, code: str, credential: str | None,
            idempotency_key: str, expected_run_id: str, engine: GameEngineGateway) -> dict[str, object]:
        """Create one independent run without deleting any prior competitive record."""
        try:
            key, expected = str(UUID(idempotency_key)), str(UUID(expected_run_id))
        except (ValueError, TypeError, AttributeError) as error:
            raise InvalidIdempotencyKey() from error
        fingerprint = sha256(f"repeat:{expected}".encode()).hexdigest()
        with self._connect() as connection, connection.cursor() as cursor:
            room = self._tournament(cursor, code, lock=True)
            _, actor, _ = self._capability(cursor, room.id, credential, "organizer")
            cursor.execute("SELECT request_fingerprint,response FROM idempotency_commands WHERE tournament_id=%s AND actor_subject_id=%s AND operation='repeat_tournament' AND idempotency_key=%s", (room.id,actor,key))
            prior = cursor.fetchone()
            if prior:
                if prior[0] != fingerprint:
                    raise IdempotencyConflict()
                return prior[1]
            cursor.execute("SELECT status,current_run_id,state_version,next_event_sequence FROM tournaments WHERE id=%s", (room.id,))
            status, old_run, version, sequence = cursor.fetchone()
            if status != 'completed' or str(old_run) != expected:
                raise StoreError("Only the current completed execution can be repeated.")
            cursor.execute("SELECT number,finished_at FROM tournament_runs WHERE tournament_id=%s AND id=%s", (room.id,old_run))
            number, finished = cursor.fetchone()
            if finished is None:
                raise StoreError("The execution has not finished.")
            cursor.execute("SELECT engine_player_id,strategy_document,id,strategy_digest FROM official_player_snapshots WHERE tournament_id=%s ORDER BY member_id", (room.id,))
            frozen = cursor.fetchall()
            for _, strategy, _, digest in frozen:
                if sha256(json.dumps(strategy,separators=(",",":"),sort_keys=True).encode()).hexdigest() != digest:
                    raise EngineUnavailable("Frozen strategy digest mismatch.")
            # Fresh server-side Fisher-Yates draw; no client bracket input.
            from secrets import SystemRandom
            SystemRandom().shuffle(frozen)
            run_id, command_id, transition_id, event_id = (str(uuid4()) for _ in range(4))
            command = StartTournamentCommand(room.id,room.hearts_required,
                tuple(EnginePlayerSnapshot(player_id,dict(strategy)) for player_id,strategy,_,_ in frozen),run_id)
            result = engine.start_tournament(command)
            restored = tournament_state_from_snapshot(result.snapshot)
            if (restored.tournament_id != room.id or restored.run_id != run_id
                    or restored.hearts_per_match != room.hearts_required
                    or restored.status.value != "active" or restored.completed_rounds
                    or {c["player_id"]:c["strategy"] for c in result.snapshot["competitors"]}
                       != {p[0]:p[1] for p in frozen}):
                raise EngineUnavailable("Invalid new execution.")
            digest = sha256(json.dumps(result.snapshot,separators=(",",":"),sort_keys=True).encode()).hexdigest()
            response = {"status":"started","tournament_id":room.id,"run_id":run_id,"run_number":number+1,"state_version":version+1}
            cursor.execute("""INSERT INTO idempotency_commands (id,tournament_id,actor_subject_id,operation,idempotency_key,request_fingerprint,status,response,completed_at)
                VALUES (%s,%s,%s,'repeat_tournament',%s,%s,'completed',%s::jsonb,CURRENT_TIMESTAMP)""",
                (command_id,room.id,actor,key,fingerprint,json.dumps(response)))
            cursor.execute("INSERT INTO tournament_runs (id,tournament_id,number,start_sequence,state_document) VALUES (%s,%s,%s,%s,%s::jsonb)",
                (run_id,room.id,number+1,sequence+1,json.dumps(result.snapshot)))
            cursor.execute("""UPDATE tournaments SET current_run_id=%s,status='running',state_version=%s,next_event_sequence=%s,
                updated_at=CURRENT_TIMESTAMP,next_transition_at=CURRENT_TIMESTAMP WHERE id=%s""",(run_id,version+1,sequence+1,room.id))
            cursor.execute("""INSERT INTO official_transitions (id,tournament_id,command_id,transition_key,expected_state_version,resulting_state_version,state_digest)
                VALUES (%s,%s,%s,%s,%s,%s,%s)""",(transition_id,room.id,command_id,str(uuid4()),version,version+1,digest))
            cursor.execute("""INSERT INTO official_state_snapshots (id,tournament_id,transition_id,state_version,state_document,state_digest)
                VALUES (%s,%s,%s,%s,%s::jsonb,%s)""",(str(uuid4()),room.id,transition_id,version+1,json.dumps(result.snapshot),digest))
            cursor.execute("DELETE FROM official_state_snapshots WHERE tournament_id=%s AND state_version<%s",(room.id,version+1))
            snapshot_ids = {p[0]:str(p[2]) for p in frozen}
            for position, match in enumerate(result.snapshot["current_round"]["matches"],1):
                battle = match["battle"]
                battle_digest = sha256(json.dumps(battle,separators=(",",":"),sort_keys=True).encode()).hexdigest()
                cursor.execute("""INSERT INTO official_matches (id,tournament_id,run_id,engine_match_id,bracket_round,bracket_position,
                    player_one_snapshot_id,player_two_snapshot_id,status,match_state_document,state_digest)
                    VALUES (%s,%s,%s,%s,1,%s,%s,%s,%s,%s::jsonb,%s)""",
                    (str(uuid4()),room.id,run_id,match["match_id"],position,snapshot_ids[battle["player_one_id"]],snapshot_ids[battle["player_two_id"]],match["status"],json.dumps(battle),battle_digest))
            payload = {"tournamentId":room.id,"runId":run_id,"runNumber":number+1,"stateVersion":version+1,
                "state":official_state_view(room,result.snapshot,state_version=version+1)}
            cursor.execute("INSERT INTO official_game_events (id,tournament_id,transition_id,sequence,event_type,public_payload) VALUES (%s,%s,%s,%s,'tournament_started',%s::jsonb)",
                (event_id,room.id,transition_id,sequence+1,json.dumps(payload)))
            cursor.execute("INSERT INTO realtime_outbox (event_id,tournament_id) VALUES (%s,%s)",(event_id,room.id))
            return response

    def advance_one_running_tournament(self, engine: GameEngineGateway) -> bool:
        """Commit one Engine round and its event ledger under a room row lock.

        Multiple backend workers may call this concurrently. PostgreSQL picks
        at most one worker per tournament; the version/round uniqueness checks
        provide an additional guard. A crashed worker leaves no partial round.
        """
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT id, access_code, state_version, next_event_sequence, current_run_id
                     FROM tournaments
                    WHERE status = 'running'
                      AND next_transition_at <= CURRENT_TIMESTAMP
                      AND updated_at <= CURRENT_TIMESTAMP - INTERVAL '1 second'
                 ORDER BY next_transition_at, id
                    LIMIT 1 FOR UPDATE SKIP LOCKED"""
            )
            candidate = cursor.fetchone()
            if candidate is None:
                return False
            tournament_id, code, previous_version, previous_sequence, current_run_id = candidate
            tournament_id = str(tournament_id)
            cursor.execute(
                """SELECT state_document, state_version
                     FROM official_state_snapshots
                    WHERE tournament_id = %s
                 ORDER BY state_version DESC LIMIT 1""",
                (tournament_id,),
            )
            saved = cursor.fetchone()
            if saved is None or saved[1] != previous_version:
                raise RuntimeError("Running tournament has no matching official snapshot.")
            previous_snapshot = self._read_rules(saved[0])
            previous = tournament_state_from_snapshot(previous_snapshot)
            if (previous.tournament_id != tournament_id or previous.status.value != "active"
                    or (previous.run_id or tournament_id) != str(current_run_id)):
                raise RuntimeError("Running tournament state does not match the database root.")

            # The immutable player snapshots are the private strategy source.
            # Verify the Engine document still agrees with those locked rows.
            cursor.execute(
                """SELECT engine_player_id, strategy_document, strategy_digest
                     FROM official_player_snapshots WHERE tournament_id = %s""",
                (tournament_id,),
            )
            frozen = {
                player_id: (self._read_rules(document), digest)
                for player_id, document, digest in cursor.fetchall()
            }
            if len(frozen) != len(previous.competitors):
                raise RuntimeError("Official player snapshot count is inconsistent.")
            for competitor in previous_snapshot["competitors"]:
                player_id = competitor["player_id"]
                strategy = competitor["strategy"]
                saved_strategy = frozen.get(player_id)
                digest = sha256(json.dumps(strategy, separators=(",", ":"), sort_keys=True).encode()).hexdigest()
                if saved_strategy is None or saved_strategy[0] != strategy or saved_strategy[1] != digest:
                    raise RuntimeError("Official strategy snapshot is inconsistent.")

            result = engine.advance_tournament(previous_snapshot)
            next_state = tournament_state_from_snapshot(result.snapshot)
            if (next_state != result.transition.state or next_state.tournament_id != tournament_id
                    or (next_state.run_id or tournament_id) != str(current_run_id)):
                raise EngineUnavailable("The Engine returned an inconsistent round snapshot.")
            new_version = previous_version + 1
            cursor.execute("""UPDATE tournament_runs SET state_document=%s::jsonb,
                first_place=%s,second_place=%s,third_place=%s,
                finished_at=CASE WHEN %s THEN CURRENT_TIMESTAMP ELSE NULL END
                WHERE tournament_id=%s AND id=%s AND finished_at IS NULL""",
                (json.dumps(result.snapshot), next_state.first_place,next_state.second_place,next_state.third_place,
                 next_state.champion_id is not None,tournament_id,current_run_id))
            if cursor.rowcount != 1:
                raise RuntimeError("Current execution is not active.")
            tournament = self._tournament(cursor, code)
            public_state = official_state_view(tournament, result.snapshot, state_version=new_version)
            events = events_for_round(
                previous, result.transition, state_version=new_version, public_state=public_state
            )
            if not events:
                raise RuntimeError("An official round must produce at least one public event.")
            state_digest = sha256(json.dumps(result.snapshot, separators=(",", ":"), sort_keys=True).encode()).hexdigest()
            transition_id = str(uuid4())
            status = "completed" if next_state.status.value == "completed" else "running"
            # A long sequence of unavoidable ties remains valid, but it must
            # not consume disk/CPU at one round per second indefinitely.
            tie_streak = 0
            if result.transition.match_round.lost_heart_player_id is None:
                active = next(match for match in previous.current_round.matches if match.status.value == "active")
                for round_ in reversed((*active.battle.rounds, result.transition.match_round)):
                    if round_.lost_heart_player_id is not None:
                        break
                    tie_streak += 1
            delay_seconds = min(3600, 2 ** min(max(tie_streak - 8, 0), 12))
            cursor.execute(
                """UPDATE tournaments
                      SET status = %s, state_version = %s, next_event_sequence = %s,
                          updated_at = CURRENT_TIMESTAMP,
                          next_transition_at = CURRENT_TIMESTAMP + (%s * INTERVAL '1 second')
                    WHERE id = %s AND state_version = %s""",
                (status, new_version, previous_sequence + len(events), delay_seconds,
                 tournament_id, previous_version),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("Tournament version changed during its locked transition.")
            cursor.execute(
                """INSERT INTO official_transitions
                   (id, tournament_id, transition_key, expected_state_version,
                    resulting_state_version, state_digest)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (transition_id, tournament_id, str(uuid4()), previous_version, new_version, state_digest),
            )
            cursor.execute(
                """INSERT INTO official_state_snapshots
                   (id, tournament_id, transition_id, state_version, state_document, state_digest)
                   VALUES (%s, %s, %s, %s, %s::jsonb, %s)""",
                (str(uuid4()), tournament_id, transition_id, new_version, json.dumps(result.snapshot), state_digest),
            )
            # The transition digest and normalized match-round ledger retain
            # history. Only the newest reconstructible full snapshot is needed
            # for recovery; retaining every cumulative document is quadratic.
            cursor.execute(
                "DELETE FROM official_state_snapshots WHERE tournament_id = %s AND state_version < %s",
                (tournament_id, new_version),
            )

            cursor.execute(
                """SELECT engine_player_id, id FROM official_player_snapshots
                    WHERE tournament_id = %s""", (tournament_id,),
            )
            player_snapshot_ids = {player_id: str(snapshot_id) for player_id, snapshot_id in cursor.fetchall()}
            all_rounds = [*result.snapshot["completed_rounds"]]
            if result.snapshot["current_round"] is not None:
                all_rounds.append(result.snapshot["current_round"])
            active_match_id = None
            if previous.current_round is not None:
                active_match_id = next(
                    match.match_id for match in previous.current_round.matches
                    if match.status.value == "active"
                )
            persisted_match_id = None
            persisted_round = None
            for bracket_round in all_rounds:
                for position, match in enumerate(bracket_round["matches"], start=1):
                    battle = match["battle"]
                    battle_digest = sha256(json.dumps(battle, separators=(",", ":"), sort_keys=True).encode()).hexdigest()
                    cursor.execute(
                        """INSERT INTO official_matches
                           (id, tournament_id, run_id, engine_match_id, bracket_round, bracket_position,
                            player_one_snapshot_id, player_two_snapshot_id, status,
                            match_state_document, state_digest, completed_at)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s,
                                   CASE WHEN %s = 'completed' THEN CURRENT_TIMESTAMP ELSE NULL END)
                           ON CONFLICT (tournament_id, engine_match_id) DO UPDATE
                             SET status = EXCLUDED.status,
                                 match_state_document = EXCLUDED.match_state_document,
                                 state_digest = EXCLUDED.state_digest,
                                 updated_at = CURRENT_TIMESTAMP,
                                 completed_at = CASE WHEN EXCLUDED.status = 'completed'
                                     THEN COALESCE(official_matches.completed_at, CURRENT_TIMESTAMP)
                                     ELSE NULL END
                           RETURNING id""",
                        (str(uuid4()), tournament_id, current_run_id, match["match_id"], bracket_round["number"], position,
                         player_snapshot_ids[battle["player_one_id"]],
                         player_snapshot_ids[battle["player_two_id"]], match["status"],
                         json.dumps(battle), battle_digest, match["status"]),
                    )
                    match_row_id = str(cursor.fetchone()[0])
                    if match["match_id"] == active_match_id:
                        persisted_match_id = match_row_id
                        persisted_round = battle["rounds"][-1]
            if persisted_match_id is None or persisted_round is None:
                raise RuntimeError("Engine round did not remain in the persisted bracket.")
            round_digest = sha256(json.dumps(persisted_round, separators=(",", ":"), sort_keys=True).encode()).hexdigest()
            cursor.execute(
                """INSERT INTO official_match_rounds
                   (id, tournament_id, match_id, round_number, state_version,
                    round_document, round_digest)
                   VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)""",
                (str(uuid4()), tournament_id, persisted_match_id, persisted_round["number"],
                 new_version, json.dumps(persisted_round), round_digest),
            )
            for offset, (event_type, payload) in enumerate(events, start=1):
                event_id = str(uuid4())
                cursor.execute(
                    """INSERT INTO official_game_events
                       (id, tournament_id, transition_id, sequence, event_type, public_payload)
                       VALUES (%s, %s, %s, %s, %s, %s::jsonb)""",
                    (event_id, tournament_id, transition_id, previous_sequence + offset,
                     event_type, json.dumps(payload)),
                )
                cursor.execute(
                    "INSERT INTO realtime_outbox (event_id, tournament_id) VALUES (%s, %s)",
                    (event_id, tournament_id),
                )
            return True

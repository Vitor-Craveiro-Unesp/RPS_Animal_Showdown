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

from .engine_gateway import EnginePlayerSnapshot, EngineUnavailable, GameEngineGateway, StartTournamentCommand
from .models import StrategyIntent
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
    def _rules(hearts_required: int, animals: dict[str, str] | None = None) -> dict[str, object]:
        return {"hearts_required": hearts_required, "animals": animals or {}, "registration_open": True}

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
        return TournamentRecord(
            id=str(room_id),
            code=code,
            capacity=capacity,
            hearts_required=hearts,
            organizer_token_digest="",  # capabilities are queried directly.
            organizer_token_expires_at=datetime.max.replace(tzinfo=UTC),
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
            )
        return players

    def _tournament(self, cursor, code: str, *, lock: bool = False) -> TournamentRecord:
        tournament = self._record(self._get_tournament_row(cursor, code, lock=lock))
        tournament.players = self._load_players(cursor, tournament)
        return tournament

    def create_tournament(self, capacity: int, hearts_required: int) -> tuple[TournamentRecord, str]:
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
                        (str(tournament_id), code, str(organizer_subject_id), capacity, json.dumps(self._rules(hearts_required))),
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

    def update_configuration(self, tournament: TournamentRecord, capacity: int, hearts_required: int) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT status, rules FROM tournaments WHERE id = %s FOR UPDATE", (tournament.id,))
            row = cursor.fetchone()
            if row is None or row[0] != "lobby" or capacity < sum(not player.removed for player in tournament.players.values()):
                raise StoreError()
            rules = self._read_rules(row[1]); rules["hearts_required"] = hearts_required
            cursor.execute("UPDATE tournaments SET capacity = %s, rules = %s::jsonb, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (capacity, json.dumps(rules), tournament.id))

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
                players=tuple(EnginePlayerSnapshot(player_id=player.id, strategy=dict(player.strategy or {})) for player in players),
            )
            result = engine.start_tournament(command)
            # Reject a malformed adapter result before it becomes durable state.
            try:
                restored_state = tournament_state_from_snapshot(result.snapshot)
            except Exception as error:
                raise EngineUnavailable("The Engine returned an invalid official snapshot.") from error
            if restored_state.tournament_id != tournament.id:
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
            cursor.execute("UPDATE tournaments SET status = 'running', state_version = %s, next_event_sequence = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (new_version, sequence, tournament.id))
            cursor.execute("INSERT INTO official_transitions (id, tournament_id, command_id, transition_key, expected_state_version, resulting_state_version, state_digest) VALUES (%s, %s, %s, %s, %s, %s, %s)", (transition_id, tournament.id, command_id, str(uuid4()), previous_version, new_version, state_digest))
            cursor.execute("INSERT INTO official_state_snapshots (id, tournament_id, transition_id, state_version, state_document, state_digest) VALUES (%s, %s, %s, %s, %s::jsonb, %s)", (str(uuid4()), tournament.id, transition_id, new_version, json.dumps(result.snapshot), state_digest))
            current_round = result.snapshot.get("current_round")
            if isinstance(current_round, dict):
                for position, match in enumerate(current_round.get("matches", []), start=1):
                    battle = match.get("battle", {}) if isinstance(match, dict) else {}
                    if not isinstance(battle, dict):
                        raise EngineUnavailable("The Engine returned an invalid match snapshot.")
                    cursor.execute("""INSERT INTO official_matches (id, tournament_id, engine_match_id, bracket_round, bracket_position, player_one_snapshot_id, player_two_snapshot_id, status, match_state_document, state_digest)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)""", (str(uuid4()), tournament.id, match["match_id"], current_round["number"], position, snapshot_ids[battle["player_one_id"]], snapshot_ids[battle["player_two_id"]], match["status"], json.dumps(battle), sha256(json.dumps(battle, separators=(",", ":"), sort_keys=True).encode()).hexdigest()))
            public_payload = {"tournamentId": tournament.id, "stateVersion": new_version, "event": "tournament_started"}
            cursor.execute("INSERT INTO official_game_events (id, tournament_id, transition_id, sequence, event_type, public_payload) VALUES (%s, %s, %s, %s, 'tournament_started', %s::jsonb)", (event_id, tournament.id, transition_id, sequence, json.dumps(public_payload)))
            cursor.execute("INSERT INTO realtime_outbox (event_id, tournament_id) VALUES (%s, %s)", (event_id, tournament.id))
            response = {"status": "started", "tournament_id": tournament.id, "state_reference": result.state_reference, "state_version": new_version}
            cursor.execute("UPDATE idempotency_commands SET status = 'completed', response = %s::jsonb, completed_at = CURRENT_TIMESTAMP WHERE id = %s AND tournament_id = %s", (json.dumps(response), command_id, tournament.id))
            for player in players:
                self._training_sessions.pop((tournament.id, player.id), None)
            return response

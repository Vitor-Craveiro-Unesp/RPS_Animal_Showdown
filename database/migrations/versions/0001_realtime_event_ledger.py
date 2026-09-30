"""Create the tournament-scoped authoritative event ledger.

Revision ID: 0001_realtime_event_ledger
Revises:
Create Date: 2026-09-29
"""
from alembic import op

revision = "0001_realtime_event_ledger"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Engine semantics are deliberately not encoded here. This is its durable envelope.
    op.execute("""
        CREATE TABLE tournaments (
            id UUID PRIMARY KEY,
            access_code TEXT NOT NULL UNIQUE,
            organizer_subject_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'lobby',
            capacity INTEGER NOT NULL,
            rules JSONB NOT NULL DEFAULT '{}'::jsonb,
            state_version BIGINT NOT NULL DEFAULT 0,
            next_event_sequence BIGINT NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT tournaments_status_check CHECK (status IN ('lobby', 'running', 'completed', 'cancelled')),
            CONSTRAINT tournaments_capacity_positive CHECK (capacity > 0),
            CONSTRAINT tournaments_state_version_nonnegative CHECK (state_version >= 0),
            CONSTRAINT tournaments_next_event_sequence_nonnegative CHECK (next_event_sequence >= 0)
        );

        CREATE TABLE tournament_members (
            id UUID PRIMARY KEY,
            tournament_id UUID NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
            subject_id TEXT NOT NULL,
            role TEXT NOT NULL,
            display_name TEXT NOT NULL,
            membership_status TEXT NOT NULL DEFAULT 'joined',
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT tournament_members_role_check CHECK (role IN ('organizer', 'participant', 'spectator')),
            CONSTRAINT tournament_members_status_check CHECK (membership_status IN ('joined', 'choosing_character', 'configuring_strategy', 'ready', 'disconnected', 'removed')),
            CONSTRAINT tournament_members_subject_per_tournament_unique UNIQUE (tournament_id, subject_id),
            CONSTRAINT tournament_members_tournament_id_unique UNIQUE (tournament_id, id)
        );
        CREATE INDEX tournament_members_by_tournament_idx ON tournament_members (tournament_id, role);

        CREATE TABLE idempotency_commands (
            id UUID PRIMARY KEY,
            tournament_id UUID NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
            actor_subject_id TEXT NOT NULL,
            operation TEXT NOT NULL,
            idempotency_key UUID NOT NULL,
            request_fingerprint TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'accepted',
            response JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMPTZ,
            CONSTRAINT idempotency_commands_operation_not_empty CHECK (length(operation) > 0),
            CONSTRAINT idempotency_commands_fingerprint_sha256_shape CHECK (request_fingerprint ~ '^[0-9a-f]{64}$'),
            CONSTRAINT idempotency_commands_status_check CHECK (status IN ('accepted', 'completed', 'rejected', 'failed')),
            CONSTRAINT idempotency_commands_scope_key_unique UNIQUE (tournament_id, actor_subject_id, operation, idempotency_key),
            CONSTRAINT idempotency_commands_tournament_id_unique UNIQUE (tournament_id, id)
        );

        CREATE TABLE official_transitions (
            id UUID PRIMARY KEY,
            tournament_id UUID NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
            command_id UUID,
            transition_key UUID NOT NULL,
            expected_state_version BIGINT NOT NULL,
            resulting_state_version BIGINT NOT NULL,
            state_digest TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT official_transitions_version_increment_check CHECK (resulting_state_version = expected_state_version + 1),
            CONSTRAINT official_transitions_state_digest_sha256_shape CHECK (state_digest ~ '^[0-9a-f]{64}$'),
            CONSTRAINT official_transitions_tournament_key_unique UNIQUE (tournament_id, transition_key),
            CONSTRAINT official_transitions_tournament_version_unique UNIQUE (tournament_id, resulting_state_version),
            CONSTRAINT official_transitions_tournament_version_digest_unique
                UNIQUE (tournament_id, resulting_state_version, state_digest),
            CONSTRAINT official_transitions_command_unique UNIQUE (command_id),
            CONSTRAINT official_transitions_tournament_id_unique UNIQUE (tournament_id, id),
            CONSTRAINT official_transitions_command_same_tournament_fk
                FOREIGN KEY (tournament_id, command_id)
                REFERENCES idempotency_commands (tournament_id, id) ON DELETE RESTRICT
        );

        CREATE TABLE official_game_events (
            id UUID PRIMARY KEY,
            tournament_id UUID NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
            transition_id UUID NOT NULL,
            sequence BIGINT NOT NULL,
            event_type TEXT NOT NULL,
            public_payload JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT official_game_events_sequence_positive CHECK (sequence > 0),
            CONSTRAINT official_game_events_type_not_empty CHECK (length(event_type) > 0),
            CONSTRAINT official_game_events_transition_same_tournament_fk
                FOREIGN KEY (tournament_id, transition_id)
                REFERENCES official_transitions (tournament_id, id) ON DELETE RESTRICT,
            CONSTRAINT official_game_events_tournament_id_unique UNIQUE (tournament_id, id),
            CONSTRAINT official_game_events_tournament_sequence_unique UNIQUE (tournament_id, sequence)
        );
        CREATE INDEX official_game_events_resume_idx ON official_game_events (tournament_id, sequence);

        CREATE TABLE realtime_outbox (
            event_id UUID PRIMARY KEY,
            tournament_id UUID NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
            available_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            lease_owner TEXT,
            lease_expires_at TIMESTAMPTZ,
            publish_attempts INTEGER NOT NULL DEFAULT 0,
            published_at TIMESTAMPTZ,
            last_error_code TEXT,
            CONSTRAINT realtime_outbox_event_same_tournament_fk
                FOREIGN KEY (tournament_id, event_id)
                REFERENCES official_game_events (tournament_id, id) ON DELETE CASCADE,
            CONSTRAINT realtime_outbox_publish_attempts_nonnegative CHECK (publish_attempts >= 0)
        );
        CREATE INDEX realtime_outbox_unpublished_idx ON realtime_outbox (available_at, event_id) WHERE published_at IS NULL;
    """)


def downgrade() -> None:
    op.execute("""
        DROP TABLE realtime_outbox;
        DROP TABLE official_game_events;
        DROP TABLE official_transitions;
        DROP TABLE idempotency_commands;
        DROP TABLE tournament_members;
        DROP TABLE tournaments;
    """)

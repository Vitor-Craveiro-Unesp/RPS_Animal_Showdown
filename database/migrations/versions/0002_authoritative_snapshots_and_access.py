"""Persist access grants and reconstructible authoritative game snapshots.

Revision ID: 0002_auth_snapshots
Revises: 0001_realtime_event_ledger
Create Date: 2026-09-29
"""
from alembic import op

revision = "0002_auth_snapshots"
down_revision = "0001_realtime_event_ledger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The Engine owns semantic validation of JSON state/strategy documents. These
    # tables preserve immutable server-validated documents for reconstruction.
    op.execute("""
        CREATE TABLE tournament_access_capabilities (
            id UUID PRIMARY KEY,
            tournament_id UUID NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
            subject_id TEXT NOT NULL,
            role TEXT NOT NULL,
            secret_hash TEXT NOT NULL,
            issued_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMPTZ NOT NULL,
            revoked_at TIMESTAMPTZ,
            revocation_reason TEXT,
            CONSTRAINT tournament_access_capabilities_role_check
                CHECK (role IN ('organizer', 'participant', 'spectator')),
            CONSTRAINT tournament_access_capabilities_secret_hash_shape
                CHECK (secret_hash ~ '^[0-9a-f]{64}$'),
            CONSTRAINT tournament_access_capabilities_expiry_check
                CHECK (expires_at > issued_at),
            CONSTRAINT tournament_access_capabilities_revocation_check
                CHECK ((revoked_at IS NULL AND revocation_reason IS NULL)
                    OR (revoked_at IS NOT NULL)),
            CONSTRAINT tournament_access_capabilities_tournament_id_unique
                UNIQUE (tournament_id, id)
        );
        CREATE INDEX tournament_access_capabilities_subject_idx
            ON tournament_access_capabilities (tournament_id, subject_id, role)
            WHERE revoked_at IS NULL;

        CREATE TABLE realtime_access_tickets (
            id UUID PRIMARY KEY,
            tournament_id UUID NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
            capability_id UUID NOT NULL,
            subject_id TEXT NOT NULL,
            role TEXT NOT NULL,
            issued_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            not_before TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMPTZ NOT NULL,
            revoked_at TIMESTAMPTZ,
            CONSTRAINT realtime_access_tickets_role_check
                CHECK (role IN ('organizer', 'participant', 'spectator')),
            CONSTRAINT realtime_access_tickets_window_check
                CHECK (expires_at > not_before AND not_before >= issued_at),
            CONSTRAINT realtime_access_tickets_capability_same_tournament_fk
                FOREIGN KEY (tournament_id, capability_id)
                REFERENCES tournament_access_capabilities (tournament_id, id)
                ON DELETE RESTRICT,
            CONSTRAINT realtime_access_tickets_tournament_id_unique
                UNIQUE (tournament_id, id)
        );
        CREATE INDEX realtime_access_tickets_active_idx
            ON realtime_access_tickets (id, tournament_id, expires_at)
            WHERE revoked_at IS NULL;

        CREATE TABLE player_strategies (
            id UUID PRIMARY KEY,
            tournament_id UUID NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
            member_id UUID NOT NULL,
            revision INTEGER NOT NULL,
            strategy_document JSONB NOT NULL,
            strategy_digest TEXT NOT NULL,
            saved_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            locked_at TIMESTAMPTZ,
            CONSTRAINT player_strategies_revision_positive CHECK (revision > 0),
            CONSTRAINT player_strategies_digest_shape CHECK (strategy_digest ~ '^[0-9a-f]{64}$'),
            CONSTRAINT player_strategies_member_same_tournament_fk
                FOREIGN KEY (tournament_id, member_id)
                REFERENCES tournament_members (tournament_id, id) ON DELETE CASCADE,
            CONSTRAINT player_strategies_member_revision_unique
                UNIQUE (tournament_id, member_id, revision),
            CONSTRAINT player_strategies_tournament_id_unique UNIQUE (tournament_id, id)
        );
        CREATE UNIQUE INDEX player_strategies_one_editable_per_member_idx
            ON player_strategies (tournament_id, member_id) WHERE locked_at IS NULL;

        CREATE TABLE official_player_snapshots (
            id UUID PRIMARY KEY,
            tournament_id UUID NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
            member_id UUID NOT NULL,
            strategy_id UUID NOT NULL,
            engine_player_id TEXT NOT NULL,
            display_name TEXT NOT NULL,
            animal_id TEXT NOT NULL,
            strategy_document JSONB NOT NULL,
            strategy_digest TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT official_player_snapshots_engine_player_id_not_empty CHECK (length(engine_player_id) > 0),
            CONSTRAINT official_player_snapshots_display_name_not_empty CHECK (length(display_name) > 0),
            CONSTRAINT official_player_snapshots_animal_id_not_empty CHECK (length(animal_id) > 0),
            CONSTRAINT official_player_snapshots_digest_shape CHECK (strategy_digest ~ '^[0-9a-f]{64}$'),
            CONSTRAINT official_player_snapshots_member_same_tournament_fk
                FOREIGN KEY (tournament_id, member_id)
                REFERENCES tournament_members (tournament_id, id) ON DELETE RESTRICT,
            CONSTRAINT official_player_snapshots_strategy_same_tournament_fk
                FOREIGN KEY (tournament_id, strategy_id)
                REFERENCES player_strategies (tournament_id, id) ON DELETE RESTRICT,
            CONSTRAINT official_player_snapshots_member_unique UNIQUE (tournament_id, member_id),
            CONSTRAINT official_player_snapshots_engine_player_unique UNIQUE (tournament_id, engine_player_id),
            CONSTRAINT official_player_snapshots_tournament_id_unique UNIQUE (tournament_id, id)
        );

        CREATE TABLE official_matches (
            id UUID PRIMARY KEY,
            tournament_id UUID NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
            engine_match_id TEXT NOT NULL,
            bracket_round INTEGER NOT NULL,
            bracket_position INTEGER NOT NULL,
            player_one_snapshot_id UUID NOT NULL,
            player_two_snapshot_id UUID NOT NULL,
            status TEXT NOT NULL,
            match_state_document JSONB NOT NULL,
            state_digest TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMPTZ,
            CONSTRAINT official_matches_engine_match_id_not_empty CHECK (length(engine_match_id) > 0),
            CONSTRAINT official_matches_round_positive CHECK (bracket_round > 0),
            CONSTRAINT official_matches_position_positive CHECK (bracket_position > 0),
            CONSTRAINT official_matches_distinct_players CHECK (player_one_snapshot_id <> player_two_snapshot_id),
            CONSTRAINT official_matches_status_check CHECK (status IN ('pending', 'active', 'completed')),
            CONSTRAINT official_matches_completed_at_check CHECK (
                (status = 'completed' AND completed_at IS NOT NULL)
                OR (status <> 'completed' AND completed_at IS NULL)
            ),
            CONSTRAINT official_matches_digest_shape CHECK (state_digest ~ '^[0-9a-f]{64}$'),
            CONSTRAINT official_matches_player_one_same_tournament_fk
                FOREIGN KEY (tournament_id, player_one_snapshot_id)
                REFERENCES official_player_snapshots (tournament_id, id) ON DELETE RESTRICT,
            CONSTRAINT official_matches_player_two_same_tournament_fk
                FOREIGN KEY (tournament_id, player_two_snapshot_id)
                REFERENCES official_player_snapshots (tournament_id, id) ON DELETE RESTRICT,
            CONSTRAINT official_matches_engine_match_unique UNIQUE (tournament_id, engine_match_id),
            CONSTRAINT official_matches_bracket_slot_unique UNIQUE (tournament_id, bracket_round, bracket_position),
            CONSTRAINT official_matches_tournament_id_unique UNIQUE (tournament_id, id)
        );

        CREATE TABLE official_match_rounds (
            id UUID PRIMARY KEY,
            tournament_id UUID NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
            match_id UUID NOT NULL,
            round_number INTEGER NOT NULL,
            state_version BIGINT NOT NULL,
            round_document JSONB NOT NULL,
            round_digest TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT official_match_rounds_round_positive CHECK (round_number > 0),
            CONSTRAINT official_match_rounds_state_version_positive CHECK (state_version > 0),
            CONSTRAINT official_match_rounds_digest_shape CHECK (round_digest ~ '^[0-9a-f]{64}$'),
            CONSTRAINT official_match_rounds_match_same_tournament_fk
                FOREIGN KEY (tournament_id, match_id)
                REFERENCES official_matches (tournament_id, id) ON DELETE RESTRICT,
            CONSTRAINT official_match_rounds_transition_same_tournament_fk
                FOREIGN KEY (tournament_id, state_version)
                REFERENCES official_transitions (tournament_id, resulting_state_version) ON DELETE RESTRICT,
            CONSTRAINT official_match_rounds_match_round_unique UNIQUE (tournament_id, match_id, round_number),
            CONSTRAINT official_match_rounds_tournament_state_version_unique UNIQUE (tournament_id, state_version)
        );

        CREATE TABLE official_state_snapshots (
            id UUID PRIMARY KEY,
            tournament_id UUID NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
            transition_id UUID NOT NULL,
            state_version BIGINT NOT NULL,
            state_document JSONB NOT NULL,
            state_digest TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT official_state_snapshots_digest_shape CHECK (state_digest ~ '^[0-9a-f]{64}$'),
            CONSTRAINT official_state_snapshots_transition_same_tournament_fk
                FOREIGN KEY (tournament_id, transition_id)
                REFERENCES official_transitions (tournament_id, id) ON DELETE RESTRICT,
            CONSTRAINT official_state_snapshots_digest_same_tournament_fk
                FOREIGN KEY (tournament_id, state_version, state_digest)
                REFERENCES official_transitions (tournament_id, resulting_state_version, state_digest) ON DELETE RESTRICT,
            CONSTRAINT official_state_snapshots_transition_unique UNIQUE (transition_id),
            CONSTRAINT official_state_snapshots_version_unique UNIQUE (tournament_id, state_version)
        );
    """)


def downgrade() -> None:
    op.execute("""
        DROP TABLE official_state_snapshots;
        DROP TABLE official_match_rounds;
        DROP TABLE official_matches;
        DROP TABLE official_player_snapshots;
        DROP TABLE player_strategies;
        DROP TABLE realtime_access_tickets;
        DROP TABLE tournament_access_capabilities;
    """)

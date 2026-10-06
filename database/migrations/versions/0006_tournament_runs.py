"""Independent executions and retained podium/history.

Revision ID: 0006_tournament_runs
Revises: 0005_competition_schedule
"""
from alembic import op

revision = "0006_tournament_runs"
down_revision = "0005_competition_schedule"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE tournament_runs (
            id UUID PRIMARY KEY,
            tournament_id UUID NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
            number INTEGER NOT NULL CHECK (number > 0),
            started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            finished_at TIMESTAMPTZ,
            start_sequence BIGINT NOT NULL CHECK (start_sequence > 0),
            state_document JSONB NOT NULL,
            first_place UUID, second_place UUID, third_place UUID,
            UNIQUE (tournament_id, id), UNIQUE (tournament_id, number)
        );
        INSERT INTO tournament_runs (id,tournament_id,number,started_at,finished_at,start_sequence,state_document,first_place)
          SELECT t.id,t.id,1,t.created_at,CASE WHEN t.status='completed' THEN t.updated_at ELSE NULL END,
                 1,s.state_document,(s.state_document->>'champion_id')::uuid
          FROM tournaments t JOIN LATERAL (
              SELECT state_document FROM official_state_snapshots
              WHERE tournament_id=t.id ORDER BY state_version DESC LIMIT 1
          ) s ON true;
        ALTER TABLE tournaments ADD COLUMN current_run_id UUID;
        UPDATE tournaments SET current_run_id=id WHERE id IN (SELECT id FROM tournament_runs);
        ALTER TABLE tournaments ADD CONSTRAINT tournaments_current_run_fk
          FOREIGN KEY (id,current_run_id) REFERENCES tournament_runs(tournament_id,id);
        ALTER TABLE official_matches ADD COLUMN run_id UUID;
        UPDATE official_matches SET run_id=tournament_id;
        ALTER TABLE official_matches ALTER COLUMN run_id SET NOT NULL;
        ALTER TABLE official_matches ADD CONSTRAINT official_matches_run_fk
          FOREIGN KEY (tournament_id,run_id) REFERENCES tournament_runs(tournament_id,id);
        ALTER TABLE official_matches DROP CONSTRAINT official_matches_bracket_slot_unique;
        ALTER TABLE official_matches ADD CONSTRAINT official_matches_bracket_slot_unique
          UNIQUE (tournament_id,run_id,bracket_round,bracket_position);
    """)


def downgrade():
    # Never discard execution history. Only an empty schema is reversible.
    op.execute("LOCK TABLE tournament_runs IN ACCESS EXCLUSIVE MODE")
    if op.get_bind().exec_driver_sql("SELECT EXISTS (SELECT 1 FROM tournament_runs)").scalar():
        raise RuntimeError("Run history is not safely downgradeable; restore a pre-migration backup.")
    op.execute("""
        ALTER TABLE tournaments DROP CONSTRAINT tournaments_current_run_fk;
        ALTER TABLE tournaments DROP COLUMN current_run_id;
        ALTER TABLE official_matches DROP CONSTRAINT official_matches_run_fk;
        ALTER TABLE official_matches DROP CONSTRAINT official_matches_bracket_slot_unique;
        ALTER TABLE official_matches DROP COLUMN run_id;
        ALTER TABLE official_matches ADD CONSTRAINT official_matches_bracket_slot_unique
          UNIQUE (tournament_id,bracket_round,bracket_position);
        DROP TABLE tournament_runs;
    """)

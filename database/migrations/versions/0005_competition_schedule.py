"""Persist the next eligible official transition for long tie streaks.

Revision ID: 0005_competition_schedule
Revises: 0004_rate_limits
"""
from alembic import op


revision = "0005_competition_schedule"
down_revision = "0004_rate_limits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE tournaments
          ADD COLUMN next_transition_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;
        CREATE INDEX tournaments_running_transition_idx
          ON tournaments (next_transition_at, id) WHERE status = 'running';
    """)


def downgrade() -> None:
    op.execute("""
        DROP INDEX tournaments_running_transition_idx;
        ALTER TABLE tournaments DROP COLUMN next_transition_at;
    """)

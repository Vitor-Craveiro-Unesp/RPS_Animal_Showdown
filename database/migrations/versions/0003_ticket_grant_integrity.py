"""Bind every durable realtime ticket to the exact capability grant.

Revision ID: 0003_ticket_grant_integrity
Revises: 0002_auth_snapshots
Create Date: 2026-09-29
"""
from alembic import op


revision = "0003_ticket_grant_integrity"
down_revision = "0002_auth_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The former FK bound ticket and capability to one tournament.  This
    # composite grant FK additionally prevents a ticket being persisted with a
    # subject or role borrowed from another capability in that same tournament.
    op.execute("""
        ALTER TABLE tournament_access_capabilities
            ADD CONSTRAINT tournament_access_capabilities_grant_unique
            UNIQUE (tournament_id, id, subject_id, role);

        ALTER TABLE realtime_access_tickets
            DROP CONSTRAINT realtime_access_tickets_capability_same_tournament_fk;

        ALTER TABLE realtime_access_tickets
            ADD CONSTRAINT realtime_access_tickets_capability_grant_same_tournament_fk
            FOREIGN KEY (tournament_id, capability_id, subject_id, role)
            REFERENCES tournament_access_capabilities (tournament_id, id, subject_id, role)
            ON DELETE RESTRICT;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE realtime_access_tickets
            DROP CONSTRAINT realtime_access_tickets_capability_grant_same_tournament_fk;

        ALTER TABLE realtime_access_tickets
            ADD CONSTRAINT realtime_access_tickets_capability_same_tournament_fk
            FOREIGN KEY (tournament_id, capability_id)
            REFERENCES tournament_access_capabilities (tournament_id, id)
            ON DELETE RESTRICT;

        ALTER TABLE tournament_access_capabilities
            DROP CONSTRAINT tournament_access_capabilities_grant_unique;
    """)

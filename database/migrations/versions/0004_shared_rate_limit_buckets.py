"""Add shared, expiring counters for public abuse controls.

Revision ID: 0004_rate_limits
Revises: 0003_ticket_grant_integrity
Create Date: 2026-09-29
"""
from alembic import op


revision = "0004_rate_limits"
down_revision = "0003_ticket_grant_integrity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE shared_rate_limit_buckets (
            operation TEXT NOT NULL,
            subject_hash TEXT NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            request_count INTEGER NOT NULL,
            PRIMARY KEY (operation, subject_hash),
            CONSTRAINT shared_rate_limit_operation_not_empty CHECK (length(operation) BETWEEN 1 AND 64),
            CONSTRAINT shared_rate_limit_subject_hash_shape CHECK (subject_hash ~ '^[0-9a-f]{64}$'),
            CONSTRAINT shared_rate_limit_count_positive CHECK (request_count > 0)
        );
        CREATE INDEX shared_rate_limit_buckets_expiry_idx
            ON shared_rate_limit_buckets (expires_at);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE shared_rate_limit_buckets;")

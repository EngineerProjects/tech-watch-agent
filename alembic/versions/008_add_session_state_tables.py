"""Add plan_versions and session_checkpoints tables

Revision ID: 008
Revises: 007
Create Date: 2026-05-20
"""

from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE IF NOT EXISTS plan_versions (
        id UUID PRIMARY KEY,
        session_id UUID NOT NULL REFERENCES research_sessions(id) ON DELETE CASCADE,
        version INTEGER NOT NULL,
        plan JSONB NOT NULL DEFAULT '[]'::jsonb,
        reason VARCHAR(200) NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_plan_versions_session_id ON plan_versions (session_id)")

    op.execute("""
    CREATE TABLE IF NOT EXISTS session_checkpoints (
        id UUID PRIMARY KEY,
        session_id UUID NOT NULL REFERENCES research_sessions(id) ON DELETE CASCADE,
        phase VARCHAR(50) NOT NULL,
        checkpoint_index INTEGER NOT NULL DEFAULT 0,
        state_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
        articles_snapshot JSONB NOT NULL DEFAULT '[]'::jsonb,
        results_snapshot JSONB NOT NULL DEFAULT '[]'::jsonb,
        is_latest BOOLEAN NOT NULL DEFAULT true,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_session_checkpoints_session_id ON session_checkpoints (session_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_session_checkpoints_latest ON session_checkpoints (session_id, is_latest)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_session_checkpoints_latest")
    op.execute("DROP INDEX IF EXISTS ix_session_checkpoints_session_id")
    op.execute("DROP TABLE IF EXISTS session_checkpoints")
    op.execute("DROP INDEX IF EXISTS ix_plan_versions_session_id")
    op.execute("DROP TABLE IF EXISTS plan_versions")

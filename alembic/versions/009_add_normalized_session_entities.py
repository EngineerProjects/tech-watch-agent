"""Add normalized session steps and session sources

Revision ID: 009
Revises: 008
Create Date: 2026-05-20
"""

from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE IF NOT EXISTS session_steps (
        id UUID PRIMARY KEY,
        session_id UUID NOT NULL REFERENCES research_sessions(id) ON DELETE CASCADE,
        step_id VARCHAR(120) NOT NULL,
        step_index INTEGER NOT NULL DEFAULT 0,
        name VARCHAR(255) NOT NULL,
        description TEXT NULL,
        step_type VARCHAR(50) NOT NULL,
        tool_name VARCHAR(100) NULL,
        status VARCHAR(50) NOT NULL,
        result TEXT NULL,
        error TEXT NULL,
        started_at TIMESTAMPTZ NULL,
        completed_at TIMESTAMPTZ NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_session_steps_unique ON session_steps (session_id, step_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_session_steps_session_index ON session_steps (session_id, step_index)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_session_steps_status ON session_steps (status)")

    op.execute("""
    CREATE TABLE IF NOT EXISTS session_sources (
        id UUID PRIMARY KEY,
        session_id UUID NOT NULL REFERENCES research_sessions(id) ON DELETE CASCADE,
        step_id VARCHAR(120) NULL,
        step_name VARCHAR(255) NULL,
        article_id UUID NULL REFERENCES articles(id) ON DELETE SET NULL,
        title VARCHAR(500) NOT NULL,
        url VARCHAR(1000) NOT NULL,
        source VARCHAR(255) NOT NULL,
        topic VARCHAR(255) NULL,
        summary TEXT NULL,
        published_date TIMESTAMPTZ NULL,
        relevance_score DOUBLE PRECISION NULL,
        tool_name VARCHAR(100) NULL,
        meta_data JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_session_sources_session_step_url ON session_sources (session_id, step_id, url)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_session_sources_source_created ON session_sources (source, created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_session_sources_session_id ON session_sources (session_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_session_sources_step_id ON session_sources (step_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_session_sources_article_id ON session_sources (article_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_session_sources_topic ON session_sources (topic)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_session_sources_topic")
    op.execute("DROP INDEX IF EXISTS ix_session_sources_article_id")
    op.execute("DROP INDEX IF EXISTS ix_session_sources_step_id")
    op.execute("DROP INDEX IF EXISTS ix_session_sources_session_id")
    op.execute("DROP INDEX IF EXISTS ix_session_sources_source_created")
    op.execute("DROP INDEX IF EXISTS ix_session_sources_session_step_url")
    op.execute("DROP TABLE IF EXISTS session_sources")
    op.execute("DROP INDEX IF EXISTS ix_session_steps_status")
    op.execute("DROP INDEX IF EXISTS ix_session_steps_session_index")
    op.execute("DROP INDEX IF EXISTS ix_session_steps_unique")
    op.execute("DROP TABLE IF EXISTS session_steps")

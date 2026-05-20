"""Add missing columns to research_sessions

Revision ID: 007
Revises: 006
Create Date: 2026-05-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add all columns that exist in the model but not in the DB schema
    op.add_column("research_sessions", sa.Column("phase", sa.String(50), nullable=True, server_default="plan"))
    op.add_column("research_sessions", sa.Column("plan", postgresql.JSONB(), nullable=True, server_default="{}"))
    op.add_column("research_sessions", sa.Column("plan_version", sa.Integer(), nullable=True, server_default="0"))
    op.add_column("research_sessions", sa.Column("current_step_index", sa.Integer(), nullable=True, server_default="0"))
    op.add_column("research_sessions", sa.Column("research_results", postgresql.JSONB(), nullable=True, server_default="[]"))
    op.add_column("research_sessions", sa.Column("analysis_results", sa.Text(), nullable=True))
    op.add_column("research_sessions", sa.Column("compacted_memory", postgresql.JSONB(), nullable=True, server_default="{}"))
    op.add_column("research_sessions", sa.Column("compaction_version", sa.Integer(), nullable=True, server_default="0"))
    op.add_column(
        "research_sessions",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_research_sessions_phase", "research_sessions", ["phase"])


def downgrade() -> None:
    op.drop_index("ix_research_sessions_phase", "research_sessions")
    op.drop_column("research_sessions", "updated_at")
    op.drop_column("research_sessions", "compaction_version")
    op.drop_column("research_sessions", "compacted_memory")
    op.drop_column("research_sessions", "analysis_results")
    op.drop_column("research_sessions", "research_results")
    op.drop_column("research_sessions", "current_step_index")
    op.drop_column("research_sessions", "plan_version")
    op.drop_column("research_sessions", "plan")
    op.drop_column("research_sessions", "phase")

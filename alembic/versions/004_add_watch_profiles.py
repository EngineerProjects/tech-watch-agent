"""add_watch_profiles

Revision ID: 004
Revises: 003
Create Date: 2026-05-20

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "watch_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("topics", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("depth", sa.String(20), nullable=False, server_default="standard"),
        sa.Column("format", sa.String(20), nullable=False, server_default="report"),
        sa.Column("angle", sa.String(20), nullable=False, server_default="both"),
        sa.Column("sources", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("language", sa.String(10), nullable=False, server_default="fr"),
        sa.Column("audience", sa.String(200), nullable=False, server_default="solo developer"),
        sa.Column("focus", sa.Text(), nullable=True),
        sa.Column("schedule_time", sa.String(10), nullable=True),
        sa.Column("schedule_days", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_watch_profiles_name", "watch_profiles", ["name"])
    op.create_index("ix_watch_profiles_is_active", "watch_profiles", ["is_active"])
    op.create_index("ix_watch_profiles_created_at", "watch_profiles", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_watch_profiles_created_at", table_name="watch_profiles")
    op.drop_index("ix_watch_profiles_is_active", table_name="watch_profiles")
    op.drop_index("ix_watch_profiles_name", table_name="watch_profiles")
    op.drop_table("watch_profiles")

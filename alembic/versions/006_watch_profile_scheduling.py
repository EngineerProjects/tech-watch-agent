"""Add extended scheduling fields to watch_profiles

Revision ID: 006
Revises: 005
Create Date: 2026-05-20
"""

from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "watch_profiles",
        sa.Column("schedule_type", sa.String(20), nullable=True),
    )
    op.add_column(
        "watch_profiles",
        sa.Column("schedule_date", sa.String(20), nullable=True),
    )
    op.add_column(
        "watch_profiles",
        sa.Column("schedule_interval_months", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("watch_profiles", "schedule_interval_months")
    op.drop_column("watch_profiles", "schedule_date")
    op.drop_column("watch_profiles", "schedule_type")

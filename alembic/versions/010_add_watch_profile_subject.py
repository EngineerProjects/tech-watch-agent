"""Add watch profile subject field.

Revision ID: 010
Revises: 009
Create Date: 2026-05-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("watch_profiles", sa.Column("subject", sa.String(length=500), nullable=True))
    op.execute("UPDATE watch_profiles SET subject = name WHERE subject IS NULL")


def downgrade() -> None:
    op.drop_column("watch_profiles", "subject")

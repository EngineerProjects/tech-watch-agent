"""Rename metadata column to meta_data (reserved by SQLAlchemy)

Revision ID: 002_rename_metadata
Revises: 001_initial
Create Date: 2026-05-10

Rename the 'metadata' column to 'meta_data' in articles, research_sessions,
and user_sessions tables to avoid conflict with SQLAlchemy's reserved
Base.metadata attribute.

Revision ID: 002_rename_metadata
Revises: 001_initial
Create Date: 2026-05-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '002_rename_metadata'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('articles', 'metadata', new_column_name='meta_data')
    op.alter_column('research_sessions', 'metadata', new_column_name='meta_data')
    op.alter_column('user_sessions', 'metadata', new_column_name='meta_data')


def downgrade() -> None:
    op.alter_column('articles', 'meta_data', new_column_name='metadata')
    op.alter_column('research_sessions', 'meta_data', new_column_name='metadata')
    op.alter_column('user_sessions', 'meta_data', new_column_name='metadata')

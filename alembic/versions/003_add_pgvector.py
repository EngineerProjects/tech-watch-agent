"""add_pgvector

Revision ID: 003
Revises: 002_rename_metadata
Create Date: 2026-05-10 15:43:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import pgvector.sqlalchemy


# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002_rename_metadata'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure pgvector extension exists
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # Cast the JSON array text representation directly to pgvector.
    # `ALTER COLUMN ... USING` does not accept subqueries in the transform
    # expression, so a direct text cast keeps the migration PostgreSQL-safe.
    op.execute(
        'ALTER TABLE articles '
        'ALTER COLUMN embedding_vector TYPE vector(1536) '
        'USING ( '
        '  CASE WHEN embedding_vector IS NULL THEN NULL '
        '  ELSE embedding_vector::text::vector(1536) '
        '  END '
        ')'
    )

    # Create HNSW index for fast vector similarity search
    op.execute(
        'CREATE INDEX ix_articles_embedding_vector ON articles '
        'USING hnsw (embedding_vector vector_cosine_ops)'
    )


def downgrade() -> None:
    # Drop HNSW index
    op.execute('DROP INDEX IF EXISTS ix_articles_embedding_vector')

    # Revert to JSONB
    op.execute(
        'ALTER TABLE articles '
        'ALTER COLUMN embedding_vector TYPE JSONB '
        'USING ( '
        '  CASE WHEN embedding_vector IS NULL THEN NULL '
        '  ELSE to_jsonb(embedding_vector::real[]) '
        '  END '
        ')'
    )

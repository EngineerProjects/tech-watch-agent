"""add_pgvector

Revision ID: 003
Revises: 002
Create Date: 2026-05-10 15:43:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import pgvector.sqlalchemy


# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure pgvector extension exists
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # Alter embedding_vector column type from JSONB to Vector(1536)
    op.execute(
        'ALTER TABLE articles '
        'ALTER COLUMN embedding_vector TYPE vector(1536) '
        'USING ( '
        '  CASE WHEN embedding_vector IS NULL THEN NULL '
        '  ELSE array(select jsonb_array_elements_text(embedding_vector)::real)::vector(1536) '
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

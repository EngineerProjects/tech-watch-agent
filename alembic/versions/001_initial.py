"""Initial migration - create all tables

Revision ID: 001_initial
Revises: 
Create Date: 2026-05-10

This initial migration creates all tables for the tech-watch-agent platform:
- users: User accounts and preferences
- user_topics: Topic subscriptions per user
- articles: Article storage with vector embeddings
- newsletter_runs: Newsletter generation history
- newsletter_run_articles: Junction table for articles in newsletters
- research_sessions: Deep research session tracking
- tool_executions: Tool execution logging
- user_sessions: User session context tracking

Revision ID: 001_initial
Revises: 
Create Date: 2026-05-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension for vector similarity search
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('username', sa.String(100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('preferences', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_users_email', 'users', ['email'])

    # Create user_topics table
    op.create_table(
        'user_topics',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('topic', sa.String(255), nullable=False),
        sa.Column('frequency', sa.String(50), nullable=False, server_default='daily'),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_user_topics_user_id', 'user_topics', ['user_id'])
    op.create_index('ix_user_topics_topic', 'user_topics', ['topic'])

    # Create articles table
    op.create_table(
        'articles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('url', sa.String(1000), nullable=False),
        sa.Column('source', sa.String(255), nullable=False),
        sa.Column('topic', sa.String(255), nullable=False),
        sa.Column('published_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('relevance_score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('embedding_vector', postgresql.JSONB(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_articles_title', 'articles', ['title'])
    op.create_index('ix_articles_url', 'articles', ['url'], unique=True)
    op.create_index('ix_articles_source', 'articles', ['source'])
    op.create_index('ix_articles_topic', 'articles', ['topic'])
    op.create_index('ix_articles_created_at', 'articles', ['created_at'])
    op.create_index('ix_articles_topic_relevance', 'articles', ['topic', 'relevance_score'])
    op.create_index('ix_articles_source_created', 'articles', ['source', 'created_at'])

    # Create newsletter_runs table
    op.create_table(
        'newsletter_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('subject', sa.String(500), nullable=False),
        sa.Column('markdown_content', sa.Text(), nullable=False),
        sa.Column('html_content', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('topics_covered', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('articles_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('delivery_success', sa.Boolean(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('execution_time_seconds', sa.Float(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_newsletter_runs_user_id', 'newsletter_runs', ['user_id'])
    op.create_index('ix_newsletter_runs_status', 'newsletter_runs', ['status'])
    op.create_index('ix_newsletter_runs_started_at', 'newsletter_runs', ['started_at'])

    # Create newsletter_run_articles junction table
    op.create_table(
        'newsletter_run_articles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('newsletter_run_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('newsletter_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('article_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('articles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('order_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('relevance_score', sa.Integer(), nullable=False, server_default='0'),
    )
    op.create_index('ix_newsletter_run_articles_newsletter_run_id', 'newsletter_run_articles', ['newsletter_run_id'])
    op.create_index('ix_newsletter_run_articles_article_id', 'newsletter_run_articles', ['article_id'])
    op.create_index('ix_newsletter_run_article_unique', 'newsletter_run_articles', ['newsletter_run_id', 'article_id'], unique=True)

    # Create research_sessions table
    op.create_table(
        'research_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('research_brief', sa.Text(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('final_report', sa.Text(), nullable=True),
        sa.Column('notes', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('raw_notes', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('metadata', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('iterations_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_research_sessions_user_id', 'research_sessions', ['user_id'])
    op.create_index('ix_research_sessions_status', 'research_sessions', ['status'])
    op.create_index('ix_research_sessions_created_at', 'research_sessions', ['created_at'])

    # Create tool_executions table
    op.create_table(
        'tool_executions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('research_sessions.id', ondelete='CASCADE'), nullable=True),
        sa.Column('tool_name', sa.String(100), nullable=False),
        sa.Column('tool_input', postgresql.JSONB(), nullable=False),
        sa.Column('tool_output', sa.Text(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('execution_time_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_tool_executions_session_id', 'tool_executions', ['session_id'])
    op.create_index('ix_tool_executions_tool_name', 'tool_executions', ['tool_name'])
    op.create_index('ix_tool_executions_created_at', 'tool_executions', ['created_at'])

    # Create user_sessions table
    op.create_table(
        'user_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True),
        sa.Column('preferences', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('topics', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('seen_article_ids', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('metadata', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_user_sessions_user_id', 'user_sessions', ['user_id'])
    op.create_index('ix_user_sessions_created_at', 'user_sessions', ['created_at'])

    # Create article_embeddings table for vector similarity search (requires pgvector)
    op.create_table(
        'article_embeddings',
        sa.Column('id', sa.String(255), primary_key=True),
        sa.Column('embedding', postgresql.JSONB(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_article_embeddings_created', 'article_embeddings', ['created_at'])
    # Note: ivfflat index should be created separately after ensuring pgvector is available
    # op.execute('CREATE INDEX idx_article_embeddings_cosine ON article_embeddings USING ivfflat (embedding cosine)')


def downgrade() -> None:
    """Drop all tables in reverse order of creation."""
    op.drop_table('article_embeddings')
    op.drop_table('user_sessions')
    op.drop_table('tool_executions')
    op.drop_table('research_sessions')
    op.drop_table('newsletter_run_articles')
    op.drop_table('newsletter_runs')
    op.drop_table('articles')
    op.drop_table('user_topics')
    op.drop_table('users')
    op.execute('DROP EXTENSION IF EXISTS vector')
"""
Database models for tech-watch-agent.

This module defines all SQLAlchemy ORM models for the application.
Models are organized by domain: articles, runs, users, etc.

Each model includes:
- Proper typing with Mapped annotations
- Relationship definitions
- Timestamps for auditing
- Indexes for query optimization
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.db.base import Base


class User(Base):
    """User model for multi-user support.

    Stores user information and preferences for personalized newsletter delivery.
    Future expansion: OAuth, API keys, team management.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    preferences: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
    )

    # Relationships
    newsletter_runs = relationship("NewsletterRun", back_populates="user", lazy="dynamic")
    user_topics = relationship("UserTopic", back_populates="user", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"


class UserTopic(Base):
    """User subscription to newsletter topics.

    Links users to their subscribed topics with frequency preferences.
    Allows users to customize which topics they want to receive.
    """

    __tablename__ = "user_topics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    topic: Mapped[str] = mapped_column(String(255), index=True)
    frequency: Mapped[str] = mapped_column(String(50), default="daily")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    user = relationship("User", back_populates="user_topics")

    def __repr__(self) -> str:
        return f"<UserTopic(user_id={self.user_id}, topic={self.topic})>"


class Article(Base):
    """Article model for storing collected articles.

    Stores article metadata and content for newsletter generation.
    Articles are deduplicated by title + url combination.
    Supports full-text search and topic categorization.
    """

    __tablename__ = "articles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    title: Mapped[str] = mapped_column(String(500), index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String(1000), index=True)
    source: Mapped[str] = mapped_column(String(255), index=True)
    topic: Mapped[str] = mapped_column(String(255), index=True)
    published_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    relevance_score: Mapped[int] = mapped_column(Integer, default=0)
    embedding_vector: Mapped[Optional[list[float]]] = mapped_column(Vector(1536), nullable=True)
    meta_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )

    # Relationships
    newsletter_runs = relationship(
        "NewsletterRunArticle",
        back_populates="article",
        lazy="dynamic",
    )

    # Indexes for common queries
    __table_args__ = (
        Index("ix_articles_topic_relevance", "topic", "relevance_score"),
        Index("ix_articles_source_created", "source", "created_at"),
        Index("ix_articles_url", "url", unique=True),
    )

    def __repr__(self) -> str:
        return f"<Article(id={self.id}, title={self.title[:50]}...)>"


class NewsletterRun(Base):
    """Newsletter run model for tracking generation history.

    Records each newsletter generation event with status and content.
    Provides historical data for analytics and user preferences.
    """

    __tablename__ = "newsletter_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    subject: Mapped[str] = mapped_column(String(500))
    markdown_content: Mapped[str] = mapped_column(Text)
    html_content: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), index=True)
    topics_covered: Mapped[dict] = mapped_column(JSONB, default=list)
    articles_count: Mapped[int] = mapped_column(Integer, default=0)
    delivery_success: Mapped[bool] = mapped_column(Boolean, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_time_seconds: Mapped[Optional[float]] = mapped_column(nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="newsletter_runs")
    articles = relationship(
        "NewsletterRunArticle",
        back_populates="newsletter_run",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"<NewsletterRun(id={self.id}, status={self.status})>"


class NewsletterRunArticle(Base):
    """Junction table linking articles to newsletter runs.

    Many-to-many relationship between articles and newsletter runs.
    Allows tracking which articles were included in each newsletter.
    """

    __tablename__ = "newsletter_run_articles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    newsletter_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("newsletter_runs.id", ondelete="CASCADE"),
        index=True,
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="CASCADE"),
        index=True,
    )
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    relevance_score: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    newsletter_run = relationship("NewsletterRun", back_populates="articles")
    article = relationship("Article", back_populates="newsletter_runs")

    # Unique constraint to prevent duplicate article inclusion
    __table_args__ = (
        Index(
            "ix_newsletter_run_article_unique",
            "newsletter_run_id",
            "article_id",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return f"<NewsletterRunArticle(run={self.newsletter_run_id}, article={self.article_id})>"


class ResearchSession(Base):
    """Research session model for deep research agent.

    Tracks deep research sessions with their status, findings, and metadata.
    Enables resuming research and tracking research history.
    """

    __tablename__ = "research_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    research_brief: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), index=True)
    final_report: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[list] = mapped_column(JSONB, default=list)
    raw_notes: Mapped[list] = mapped_column(JSONB, default=list)
    meta_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    iterations_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<ResearchSession(id={self.id}, status={self.status})>"


class ToolExecution(Base):
    """Tool execution log for debugging and analytics.

    Records all tool executions with timing and results.
    Useful for debugging, performance optimization, and cost tracking.
    """

    __tablename__ = "tool_executions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_sessions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    tool_name: Mapped[str] = mapped_column(String(100), index=True)
    tool_input: Mapped[dict] = mapped_column(JSONB)
    tool_output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_time_ms: Mapped[Optional[int]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )

    def __repr__(self) -> str:
        return f"<ToolExecution(tool={self.tool_name}, success={self.success})>"


class UserSession(Base):
    """User session model for tracking context across interactions.

    Stores session data for users, including preferences, followed topics,
    and previously seen articles. Enables personalized newsletter delivery
    and user experience tracking.
    """

    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    preferences: Mapped[dict] = mapped_column(JSONB, default=dict)
    topics: Mapped[list] = mapped_column(JSONB, default=list)
    seen_article_ids: Mapped[list] = mapped_column(JSONB, default=list)
    meta_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
    )

    # Relationships
    user = relationship("User", back_populates="sessions", foreign_keys=[user_id])

    def __repr__(self) -> str:
        return f"<UserSession(id={self.id}, user_id={self.user_id}, is_active={self.is_active})>"
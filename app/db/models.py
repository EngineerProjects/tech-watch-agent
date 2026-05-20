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
    TypeDecorator,
    CHAR,
)
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    Vector = None

from app.db.base import Base


class GUID(TypeDecorator):
    """Platform-independent GUID type.

    Uses PostgreSQL's UUID type when available, otherwise uses CHAR(36).
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value if isinstance(value, uuid.UUID) else uuid.UUID(value)
        if isinstance(value, uuid.UUID):
            return str(value)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, uuid.UUID):
            return uuid.UUID(value)
        return value


class JSONType(TypeDecorator):
    """Platform-independent JSON type.

    Uses PostgreSQL's JSONB when available, otherwise uses generic JSON.
    """

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_JSONB())
        return dialect.type_descriptor(JSON())


class User(Base):
    """User model for multi-user support.

    Stores user information and preferences for personalized newsletter delivery.
    Future expansion: OAuth, API keys, team management.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    preferences: Mapped[dict] = mapped_column(JSONType(), default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    newsletter_runs = relationship("NewsletterRun", back_populates="user", lazy="dynamic")
    user_topics = relationship("UserTopic", back_populates="user", lazy="dynamic")
    sessions = relationship("UserSession", back_populates="user")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"


class UserTopic(Base):
    """User subscription to newsletter topics.

    Links users to their subscribed topics with frequency preferences.
    Allows users to customize which topics they want to receive.
    """

    __tablename__ = "user_topics"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
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
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    title: Mapped[str] = mapped_column(String(500), index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String(1000))
    source: Mapped[str] = mapped_column(String(255), index=True)
    topic: Mapped[str] = mapped_column(String(255), index=True)
    published_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    relevance_score: Mapped[int] = mapped_column(Integer, default=0)
    embedding_vector: Mapped[Optional[list[float]]] = mapped_column(Vector(1536), nullable=True)
    meta_data: Mapped[dict] = mapped_column(JSONType(), default=dict)
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
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    subject: Mapped[str] = mapped_column(String(500))
    markdown_content: Mapped[str] = mapped_column(Text)
    html_content: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), index=True)
    topics_covered: Mapped[dict] = mapped_column(JSONType(), default=list)
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
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    newsletter_run_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("newsletter_runs.id", ondelete="CASCADE"),
        index=True,
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
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
    
    Features:
    - Plan persistence: Full execution plan stored and updated
    - Versioning: Track plan revisions with reasons
    - Checkpointing: Resume interrupted sessions
    - Phase tracking: PLAN → RESEARCH → SYNTHESIS → COMPLETED
    """

    __tablename__ = "research_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    research_brief: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), index=True)
    phase: Mapped[str] = mapped_column(String(50), default="plan", index=True)
    final_report: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[list] = mapped_column(JSONType(), default=list)
    raw_notes: Mapped[list] = mapped_column(JSONType(), default=list)
    meta_data: Mapped[dict] = mapped_column(JSONType(), default=dict)
    iterations_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Plan persistence fields
    plan: Mapped[dict] = mapped_column(JSONType(), default=dict)
    plan_version: Mapped[int] = mapped_column(Integer, default=0)
    current_step_index: Mapped[int] = mapped_column(Integer, default=0)
    research_results: Mapped[list] = mapped_column(JSONType(), default=list)
    analysis_results: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Memory compaction (for agent context management)
    compacted_memory: Mapped[dict] = mapped_column(JSONType(), default=dict)
    compaction_version: Mapped[int] = mapped_column(Integer, default=0)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<ResearchSession(id={self.id}, status={self.status}, phase={self.phase})>"


class PlanVersion(Base):
    """Version history for research session plans.
    
    Tracks all plan versions with reasons for revision.
    Enables rollback and audit trail of plan evolution.
    """

    __tablename__ = "plan_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("research_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    plan: Mapped[dict] = mapped_column(JSONType())
    reason: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<PlanVersion(session={self.session_id}, version={self.version})>"


class SessionCheckpoint(Base):
    """Checkpoint for resumable session state.
    
    Stores full state at each phase transition for recovery.
    Enables resuming interrupted sessions from exact point.
    """

    __tablename__ = "session_checkpoints"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("research_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    phase: Mapped[str] = mapped_column(String(50), nullable=False)
    checkpoint_index: Mapped[int] = mapped_column(Integer, default=0)
    state_snapshot: Mapped[dict] = mapped_column(JSONType())
    articles_snapshot: Mapped[list] = mapped_column(JSONType(), default=list)
    results_snapshot: Mapped[list] = mapped_column(JSONType(), default=list)
    is_latest: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<SessionCheckpoint(session={self.session_id}, phase={self.phase}, latest={self.is_latest})>"


class ToolExecution(Base):
    """Tool execution log for debugging and analytics.

    Records all tool executions with timing and results.
    Useful for debugging, performance optimization, and cost tracking.
    """

    __tablename__ = "tool_executions"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("research_sessions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    tool_name: Mapped[str] = mapped_column(String(100), index=True)
    tool_input: Mapped[dict] = mapped_column(JSONType())
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


class WatchProfile(Base):
    """Named watch profile — user-configured recurring tech watch job.

    Encapsulates everything needed to run an autonomous tech watch:
    topics, depth, output format, source preferences, schedule, and
    free-form focus instructions that shape the prompt context.
    """

    __tablename__ = "watch_profiles"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    topics: Mapped[list] = mapped_column(JSONType(), default=list)
    depth: Mapped[str] = mapped_column(String(20), default="standard")   # brief|standard|deep
    format: Mapped[str] = mapped_column(String(20), default="report")    # digest|report|newsletter
    angle: Mapped[str] = mapped_column(String(20), default="both")       # technical|business|both
    sources: Mapped[list] = mapped_column(JSONType(), default=list)      # web,arxiv,reddit,github,youtube
    language: Mapped[str] = mapped_column(String(10), default="fr")
    audience: Mapped[str] = mapped_column(String(200), default="solo developer")
    focus: Mapped[Optional[str]] = mapped_column(Text, nullable=True)    # free-form instructions
    schedule_time: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)   # "08:00"
    schedule_days: Mapped[list] = mapped_column(JSONType(), default=list)             # ["monday"]
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<WatchProfile(id={self.id}, name={self.name!r}, depth={self.depth})>"


class AppConfig(Base):
    """Runtime configuration overrides stored in DB.

    Keys match ENV VAR names (lowercase). Values overlay env-var defaults
    at the dashboard layer; agents always see the in-memory Settings object.
    """

    __tablename__ = "app_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<AppConfig(key={self.key!r})>"


class UserSession(Base):
    """User session model for tracking context across interactions.

    Stores session data for users, including preferences, followed topics,
    and previously seen articles. Enables personalized newsletter delivery
    and user experience tracking.
    """

    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    preferences: Mapped[dict] = mapped_column(JSONType(), default=dict)
    topics: Mapped[list] = mapped_column(JSONType(), default=list)
    seen_article_ids: Mapped[list] = mapped_column(JSONType(), default=list)
    meta_data: Mapped[dict] = mapped_column(JSONType(), default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    user = relationship("User", back_populates="sessions")

    def __repr__(self) -> str:
        return f"<UserSession(id={self.id}, user_id={self.user_id}, is_active={self.is_active})>"

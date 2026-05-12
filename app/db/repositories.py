"""
Repository layer for database operations.

This module provides repository classes that encapsulate database access patterns
for each domain entity. Repositories abstract SQL queries and provide a clean
interface for business logic.

Pattern: Each repository handles one entity type and provides CRUD operations
plus domain-specific queries.
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional, Sequence

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    Article,
    NewsletterRun,
    NewsletterRunArticle,
    PlanVersion,
    ResearchSession,
    SessionCheckpoint,
    ToolExecution,
    User,
    UserTopic,
)


class ArticleRepository:
    """Repository for Article entity operations.

    Provides database operations for articles including creation, retrieval,
    deduplication, and topic-based queries.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, article: Article) -> Article:
        """Create a new article in the database."""
        self.session.add(article)
        await self.session.flush()
        await self.session.refresh(article)
        return article

    async def get_by_id(self, article_id: uuid.UUID) -> Optional[Article]:
        """Get an article by its ID."""
        result = await self.session.execute(
            select(Article).where(Article.id == article_id)
        )
        return result.scalar_one_or_none()

    async def get_by_url(self, url: str) -> Optional[Article]:
        """Get an article by its URL for deduplication."""
        result = await self.session.execute(
            select(Article).where(Article.url == url)
        )
        return result.scalar_one_or_none()

    async def find_similar(self, title: str, url: str) -> Optional[Article]:
        """Find an article with similar title and URL for deduplication."""
        result = await self.session.execute(
            select(Article).where(
                and_(
                    func.lower(Article.title) == title.lower(),
                    func.lower(Article.url) == url.lower(),
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_by_topic(
        self,
        topic: str,
        limit: int = 50,
        min_relevance: int = 0,
    ) -> Sequence[Article]:
        """Get articles by topic, ordered by relevance."""
        result = await self.session.execute(
            select(Article)
            .where(
                and_(
                    Article.topic == topic,
                    Article.relevance_score >= min_relevance,
                )
            )
            .order_by(Article.relevance_score.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_recent(
        self,
        days: int = 7,
        limit: int = 100,
    ) -> Sequence[Article]:
        """Get recent articles from the last N days."""
        cutoff_date = datetime.now() - timedelta(days=days)
        result = await self.session.execute(
            select(Article)
            .where(Article.created_at >= cutoff_date)
            .order_by(Article.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def bulk_create(self, articles: list[Article]) -> list[Article]:
        """Create multiple articles efficiently."""
        self.session.add_all(articles)
        await self.session.flush()
        return articles

    async def count_by_topic(self) -> dict[str, int]:
        """Get article count grouped by topic."""
        result = await self.session.execute(
            select(Article.topic, func.count(Article.id))
            .group_by(Article.topic)
        )
        return {topic: count for topic, count in result.all()}


class NewsletterRunRepository:
    """Repository for NewsletterRun entity operations.

    Provides database operations for newsletter runs including creation,
    status tracking, and historical queries.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, run: NewsletterRun) -> NewsletterRun:
        """Create a new newsletter run."""
        self.session.add(run)
        await self.session.flush()
        await self.session.refresh(run)
        return run

    async def get_by_id(self, run_id: uuid.UUID) -> Optional[NewsletterRun]:
        """Get a newsletter run by ID."""
        result = await self.session.execute(
            select(NewsletterRun).where(NewsletterRun.id == run_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_articles(
        self, run_id: uuid.UUID
    ) -> Optional[NewsletterRun]:
        """Get a newsletter run with its associated articles."""
        result = await self.session.execute(
            select(NewsletterRun)
            .options(selectinload(NewsletterRun.articles).selectinload(NewsletterRunArticle.article))
            .where(NewsletterRun.id == run_id)
        )
        return result.scalar_one_or_none()

    async def get_recent(
        self,
        user_id: Optional[uuid.UUID] = None,
        limit: int = 10,
    ) -> Sequence[NewsletterRun]:
        """Get recent newsletter runs, optionally filtered by user."""
        query = select(NewsletterRun).order_by(NewsletterRun.started_at.desc())
        if user_id:
            query = query.where(NewsletterRun.user_id == user_id)
        query = query.limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def update_status(
        self,
        run_id: uuid.UUID,
        status: str,
        **kwargs,
    ) -> Optional[NewsletterRun]:
        """Update newsletter run status and additional fields."""
        result = await self.session.execute(
            select(NewsletterRun).where(NewsletterRun.id == run_id)
        )
        run = result.scalar_one_or_none()
        if run:
            run.status = status
            for key, value in kwargs.items():
                if hasattr(run, key):
                    setattr(run, key, value)
            await self.session.flush()
        return run

    async def add_article(
        self,
        run_id: uuid.UUID,
        article_id: uuid.UUID,
        order_index: int = 0,
        relevance_score: int = 0,
    ) -> NewsletterRunArticle:
        """Link an article to a newsletter run."""
        link = NewsletterRunArticle(
            newsletter_run_id=run_id,
            article_id=article_id,
            order_index=order_index,
            relevance_score=relevance_score,
        )
        self.session.add(link)
        await self.session.flush()
        return link

    async def get_stats(
        self, user_id: Optional[uuid.UUID] = None, days: int = 30
    ) -> dict:
        """Get newsletter run statistics for a time period."""
        cutoff_date = datetime.now() - timedelta(days=days)
        query = select(
            func.count(NewsletterRun.id).label("total_runs"),
            func.sum(
                func.case((NewsletterRun.delivery_success == True, 1), else_=0)
            ).label("successful_deliveries"),
            func.avg(NewsletterRun.execution_time_seconds).label("avg_execution_time"),
        ).where(NewsletterRun.started_at >= cutoff_date)

        if user_id:
            query = query.where(NewsletterRun.user_id == user_id)

        result = await self.session.execute(query)
        row = result.one()
        return {
            "total_runs": row.total_runs or 0,
            "successful_deliveries": row.successful_deliveries or 0,
            "avg_execution_time": row.avg_execution_time or 0,
        }


class UserRepository:
    """Repository for User entity operations.

    Provides database operations for users including creation,
    authentication support, and preference management.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, user: User) -> User:
        """Create a new user."""
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        """Get a user by ID."""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get a user by email address."""
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def update_preferences(
        self, user_id: uuid.UUID, preferences: dict
    ) -> Optional[User]:
        """Update user preferences."""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.preferences = preferences
            await self.session.flush()
        return user


class UserTopicRepository:
    """Repository for UserTopic entity operations.

    Provides database operations for user topic subscriptions.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, user_topic: UserTopic) -> UserTopic:
        """Create a new user topic subscription."""
        self.session.add(user_topic)
        await self.session.flush()
        await self.session.refresh(user_topic)
        return user_topic

    async def get_active_by_user(self, user_id: uuid.UUID) -> Sequence[UserTopic]:
        """Get all active topics for a user."""
        result = await self.session.execute(
            select(UserTopic).where(
                and_(
                    UserTopic.user_id == user_id,
                    UserTopic.is_active == True,
                )
            )
        )
        return result.scalars().all()

    async def toggle_active(
        self, user_id: uuid.UUID, topic: str, is_active: bool
    ) -> Optional[UserTopic]:
        """Toggle topic subscription status."""
        result = await self.session.execute(
            select(UserTopic).where(
                and_(
                    UserTopic.user_id == user_id,
                    UserTopic.topic == topic,
                )
            )
        )
        user_topic = result.scalar_one_or_none()
        if user_topic:
            user_topic.is_active = is_active
            await self.session.flush()
        return user_topic


class ResearchSessionRepository:
    """Repository for ResearchSession entity operations.

    Provides database operations for deep research sessions including
    creation, status tracking, and report retrieval.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, session: ResearchSession) -> ResearchSession:
        """Create a new research session."""
        self.session.add(session)
        await self.session.flush()
        await self.session.refresh(session)
        return session

    async def get_by_id(self, session_id: uuid.UUID) -> Optional[ResearchSession]:
        """Get a research session by ID."""
        result = await self.session.execute(
            select(ResearchSession).where(ResearchSession.id == session_id)
        )
        return result.scalar_one_or_none()

    async def update_status(
        self, session_id: uuid.UUID, status: str, **kwargs
    ) -> Optional[ResearchSession]:
        """Update research session status."""
        result = await self.session.execute(
            select(ResearchSession).where(ResearchSession.id == session_id)
        )
        session_obj = result.scalar_one_or_none()
        if session_obj:
            session_obj.status = status
            for key, value in kwargs.items():
                if hasattr(session_obj, key):
                    setattr(session_obj, key, value)
            await self.session.flush()
        return session_obj

    async def get_recent(
        self, user_id: Optional[uuid.UUID] = None, limit: int = 10
    ) -> Sequence[ResearchSession]:
        """Get recent research sessions."""
        query = select(ResearchSession).order_by(ResearchSession.created_at.desc())
        if user_id:
            query = query.where(ResearchSession.user_id == user_id)
        query = query.limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_by_status(self, status: str, limit: int = 10) -> Sequence[ResearchSession]:
        """Get sessions by status (e.g., 'research', 'failed', 'completed')."""
        query = (
            select(ResearchSession)
            .where(ResearchSession.status == status)
            .order_by(ResearchSession.updated_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_interruptible_sessions(self) -> Sequence[ResearchSession]:
        """Get sessions that can be resumed (not completed or failed)."""
        query = (
            select(ResearchSession)
            .where(
                and_(
                    ResearchSession.status.in_(["created", "running", "research"]),
                    ResearchSession.phase.in_(["plan", "research", "collection", "analysis"]),
                )
            )
            .order_by(ResearchSession.updated_at.desc())
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_plan_versions(self, session_id: uuid.UUID) -> Sequence[PlanVersion]:
        """Get all plan versions for a session."""
        query = (
            select(PlanVersion)
            .where(PlanVersion.session_id == session_id)
            .order_by(PlanVersion.version.asc())
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_checkpoints(self, session_id: uuid.UUID) -> Sequence[SessionCheckpoint]:
        """Get all checkpoints for a session."""
        query = (
            select(SessionCheckpoint)
            .where(SessionCheckpoint.session_id == session_id)
            .order_by(SessionCheckpoint.created_at.desc())
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_latest_checkpoint(self, session_id: uuid.UUID) -> Optional[SessionCheckpoint]:
        """Get the latest checkpoint for a session."""
        query = (
            select(SessionCheckpoint)
            .where(
                and_(
                    SessionCheckpoint.session_id == session_id,
                    SessionCheckpoint.is_latest == True,
                )
            )
            .order_by(SessionCheckpoint.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()


class ToolExecutionRepository:
    """Repository for ToolExecution entity operations.

    Provides database operations for tool execution logging
    and analytics.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, execution: ToolExecution) -> ToolExecution:
        """Create a new tool execution log."""
        self.session.add(execution)
        await self.session.flush()
        await self.session.refresh(execution)
        return execution

    async def get_by_session(
        self, session_id: uuid.UUID, limit: int = 100
    ) -> Sequence[ToolExecution]:
        """Get tool executions for a research session."""
        result = await self.session.execute(
            select(ToolExecution)
            .where(ToolExecution.session_id == session_id)
            .order_by(ToolExecution.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_stats(days: int = 7) -> dict:
        """Get tool execution statistics."""
        cutoff_date = datetime.now() - timedelta(days=days)
        result = await Session.execute(
            select(
                ToolExecution.tool_name,
                func.count(ToolExecution.id).label("count"),
                func.avg(ToolExecution.execution_time_ms).label("avg_time"),
            )
            .where(ToolExecution.created_at >= cutoff_date)
            .group_by(ToolExecution.tool_name)
        )
        return {
            name: {"count": count, "avg_time": avg_time}
            for name, count, avg_time in result.all()
        }
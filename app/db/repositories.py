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

from sqlalchemy import select, func, and_, or_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    AppConfig,
    Article,
    EmailGroup,
    EmailGroupRecipient,
    NewsletterRun,
    NewsletterRunArticle,
    PlanVersion,
    ResearchSession,
    SessionCheckpoint,
    SessionSource,
    SessionStep,
    ToolExecution,
    User,
    UserTopic,
    WatchProfile,
)


class AppConfigRepository:
    """Key-value store for runtime configuration overrides."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, key: str) -> str | None:
        result = await self.session.get(AppConfig, key)
        return result.value if result else None

    async def get_all(self) -> dict[str, str]:
        result = await self.session.execute(select(AppConfig))
        return {row.key: row.value for row in result.scalars() if row.value is not None}

    async def set(self, key: str, value: str, description: str | None = None) -> None:
        existing = await self.session.get(AppConfig, key)
        if existing:
            existing.value = value
        else:
            self.session.add(AppConfig(key=key, value=value, description=description))
        await self.session.flush()

    async def bulk_set(self, updates: dict[str, str]) -> None:
        for key, value in updates.items():
            await self.set(key, value)

    async def delete(self, key: str) -> None:
        existing = await self.session.get(AppConfig, key)
        if existing:
            await self.session.delete(existing)
            await self.session.flush()


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

    async def delete(self, session_id: uuid.UUID) -> bool:
        """Delete a research session and all cascade-linked session entities."""
        session_obj = await self.get_by_id(session_id)
        if not session_obj:
            return False
        await self.session.delete(session_obj)
        await self.session.flush()
        return True


class SessionStepRepository:
    """Repository for normalized session steps."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def replace_for_session(self, session_id: uuid.UUID, steps: list[SessionStep]) -> None:
        await self.session.execute(delete(SessionStep).where(SessionStep.session_id == session_id))
        if steps:
            self.session.add_all(steps)
        await self.session.flush()

    async def list_for_session(self, session_id: uuid.UUID) -> Sequence[SessionStep]:
        result = await self.session.execute(
            select(SessionStep)
            .where(SessionStep.session_id == session_id)
            .order_by(SessionStep.step_index.asc())
        )
        return result.scalars().all()


class SessionSourceRepository:
    """Repository for normalized session sources."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def replace_for_session(self, session_id: uuid.UUID, sources: list[SessionSource]) -> None:
        await self.session.execute(delete(SessionSource).where(SessionSource.session_id == session_id))
        if sources:
            self.session.add_all(sources)
        await self.session.flush()

    async def list_recent(
        self,
        *,
        limit: int = 100,
        session_id: Optional[uuid.UUID] = None,
        query: Optional[str] = None,
        source: Optional[str] = None,
    ) -> list[dict]:
        stmt = (
            select(SessionSource, ResearchSession)
            .join(ResearchSession, ResearchSession.id == SessionSource.session_id)
        )
        if session_id:
            stmt = stmt.where(SessionSource.session_id == session_id)
        if source:
            stmt = stmt.where(func.lower(SessionSource.source) == source.lower())
        if query:
            like = f"%{query.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(SessionSource.title).like(like),
                    func.lower(SessionSource.url).like(like),
                    func.lower(func.coalesce(SessionSource.summary, "")).like(like),
                    func.lower(func.coalesce(ResearchSession.research_brief, "")).like(like),
                )
            )

        stmt = stmt.order_by(SessionSource.created_at.desc()).limit(limit)

        result = await self.session.execute(stmt)
        rows = []
        for source_row, research_session in result.all():
            rows.append({
                "id": str(source_row.id),
                "session_id": str(source_row.session_id),
                "session_brief": research_session.research_brief,
                "step_id": source_row.step_id,
                "step_name": source_row.step_name,
                "article_id": str(source_row.article_id) if source_row.article_id else None,
                "title": source_row.title,
                "url": source_row.url,
                "source": source_row.source,
                "topic": source_row.topic,
                "summary": source_row.summary,
                "published_date": source_row.published_date.isoformat() if source_row.published_date else None,
                "relevance_score": source_row.relevance_score,
                "tool_name": source_row.tool_name,
                "created_at": source_row.created_at.isoformat() if source_row.created_at else None,
            })

        if rows:
            return rows

        from app.services.session_manager import extract_normalized_sources

        fallback_stmt = select(ResearchSession).order_by(ResearchSession.updated_at.desc()).limit(limit)
        if session_id:
            fallback_stmt = fallback_stmt.where(ResearchSession.id == session_id)

        fallback_result = await self.session.execute(fallback_stmt)
        fallback_rows = []
        for research_session in fallback_result.scalars().all():
            for item in extract_normalized_sources(research_session.research_results or []):
                row = {
                    "id": f"fallback-{research_session.id}-{item['step_id'] or 'na'}-{abs(hash(item['url']))}",
                    "session_id": str(research_session.id),
                    "session_brief": research_session.research_brief,
                    "step_id": item["step_id"],
                    "step_name": item["step_name"],
                    "article_id": None,
                    "title": item["title"],
                    "url": item["url"],
                    "source": item["source"],
                    "topic": item["topic"],
                    "summary": item["summary"],
                    "published_date": item["published_date"].isoformat() if item["published_date"] else None,
                    "relevance_score": item["relevance_score"],
                    "tool_name": item["tool_name"],
                    "created_at": research_session.updated_at.isoformat() if research_session.updated_at else None,
                }
                if source and row["source"].lower() != source.lower():
                    continue
                if query:
                    haystack = " ".join(str(row.get(key) or "").lower() for key in ("title", "summary", "session_brief", "source", "topic"))
                    if query.lower() not in haystack:
                        continue
                fallback_rows.append(row)
                if len(fallback_rows) >= limit:
                    return fallback_rows
        return fallback_rows


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

    async def get_stats(self, days: int = 7) -> dict:
        """Get tool execution statistics."""
        cutoff_date = datetime.now() - timedelta(days=days)
        result = await self.session.execute(
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


class EmailGroupRepository:
    """CRUD repository for EmailGroup entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _detail_query(self):
        return select(EmailGroup).options(
            selectinload(EmailGroup.recipients),
            selectinload(EmailGroup.watch_profiles),
        )

    async def create(self, group: EmailGroup) -> EmailGroup:
        self.session.add(group)
        await self.session.flush()
        return await self.get_by_id(group.id) or group

    async def get_by_id(self, group_id: uuid.UUID) -> Optional[EmailGroup]:
        result = await self.session.execute(
            self._detail_query().where(EmailGroup.id == group_id)
        )
        return result.scalar_one_or_none()

    async def list_all(self, active_only: bool = False) -> Sequence[EmailGroup]:
        query = self._detail_query()
        if active_only:
            query = query.where(EmailGroup.is_active.is_(True))
        query = query.order_by(EmailGroup.created_at.desc())
        result = await self.session.execute(query)
        return result.scalars().all()

    async def update(self, group: EmailGroup) -> EmailGroup:
        await self.session.flush()
        return await self.get_by_id(group.id) or group

    async def delete(self, group_id: uuid.UUID) -> bool:
        group = await self.get_by_id(group_id)
        if not group:
            return False
        await self.session.delete(group)
        await self.session.flush()
        return True

    async def replace_recipients(
        self,
        group: EmailGroup,
        recipients: list[dict[str, str | None]],
    ) -> None:
        normalized: list[dict[str, str | None]] = []
        seen: set[str] = set()
        for item in recipients:
            email = str(item.get("email") or "").strip().lower()
            if not email or email in seen:
                continue
            seen.add(email)
            normalized.append({
                "email": email,
                "label": str(item.get("label") or "").strip() or None,
            })

        group.recipients.clear()
        for item in normalized:
            group.recipients.append(
                EmailGroupRecipient(
                    email=item["email"],
                    label=item["label"],
                )
            )
        await self.session.flush()

    async def resolve_recipients_for_profile(self, profile: WatchProfile) -> list[str]:
        recipients: list[str] = []
        seen: set[str] = set()
        for group in profile.email_groups:
            if not group.is_active:
                continue
            for recipient in group.recipients:
                email = recipient.email.strip().lower()
                if not email or email in seen:
                    continue
                seen.add(email)
                recipients.append(email)
        return recipients


class WatchProfileRepository:
    """CRUD repository for WatchProfile entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _detail_query(self):
        return select(WatchProfile).options(
            selectinload(WatchProfile.email_groups).selectinload(EmailGroup.recipients)
        )

    async def create(self, profile: WatchProfile) -> WatchProfile:
        self.session.add(profile)
        await self.session.flush()
        return await self.get_by_id(profile.id) or profile

    async def get_by_id(self, profile_id: uuid.UUID) -> Optional[WatchProfile]:
        result = await self.session.execute(
            self._detail_query().where(WatchProfile.id == profile_id)
        )
        return result.scalar_one_or_none()

    async def list_all(self, active_only: bool = False) -> Sequence[WatchProfile]:
        query = self._detail_query()
        if active_only:
            query = query.where(WatchProfile.is_active.is_(True))
        query = query.order_by(WatchProfile.created_at.desc())
        result = await self.session.execute(query)
        return result.scalars().all()

    async def update(self, profile: WatchProfile) -> WatchProfile:
        await self.session.flush()
        return await self.get_by_id(profile.id) or profile

    async def delete(self, profile_id: uuid.UUID) -> bool:
        profile = await self.get_by_id(profile_id)
        if not profile:
            return False
        await self.session.delete(profile)
        await self.session.flush()
        return True

    async def touch_last_run(self, profile_id: uuid.UUID) -> None:
        profile = await self.get_by_id(profile_id)
        if profile:
            profile.last_run_at = datetime.utcnow()
            await self.session.flush()

    async def set_email_groups(self, profile: WatchProfile, group_ids: list[uuid.UUID]) -> None:
        if not group_ids:
            profile.email_groups = []
            await self.session.flush()
            return

        result = await self.session.execute(
            select(EmailGroup)
            .options(selectinload(EmailGroup.recipients))
            .where(EmailGroup.id.in_(group_ids))
        )
        groups = result.scalars().all()
        found_ids = {group.id for group in groups}
        missing_ids = [group_id for group_id in group_ids if group_id not in found_ids]
        if missing_ids:
            missing = ", ".join(str(group_id) for group_id in missing_ids)
            raise ValueError(f"Unknown email group ids: {missing}")

        ordered_groups = sorted(groups, key=lambda group: group_ids.index(group.id))
        profile.email_groups = ordered_groups
        await self.session.flush()

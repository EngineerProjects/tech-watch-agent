"""
Session management for user context.

This module provides session management capabilities for tracking user
context across agent interactions. It enables personalization and
persistent state across multiple newsletter generations.

Sessions store:
- User preferences and interests
- Previously seen articles
- Topic preferences
- Interaction history
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
import uuid

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger


logger = get_logger(__name__)


@dataclass
class Session:
    """Represents a user session for tracking context.

    Attributes:
        id: Unique session identifier
        user_id: User identifier (optional for anonymous sessions)
        created_at: Session creation timestamp
        updated_at: Last update timestamp
        preferences: User preferences dictionary
        topics: List of followed topics
        seen_article_ids: IDs of articles already shown to the user
        metadata: Additional session metadata
        is_active: Whether the session is currently active
    """

    id: uuid.UUID
    user_id: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime
    preferences: dict[str, Any] = field(default_factory=dict)
    topics: list[str] = field(default_factory=list)
    seen_article_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    is_active: bool = True


class SessionManager:
    """Manages user sessions and context.

    This class handles session creation, retrieval, and updates.
    It stores session data in the database for persistence across
    application restarts.

    Usage:
        manager = SessionManager(session)
        session = await manager.get_or_create_session(user_id)
        await manager.update_preferences(session.id, {"theme": "dark"})
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the session manager.

        Args:
            session: Async database session
        """
        self.session = session

    async def get_or_create_session(
        self,
        user_id: Optional[uuid.UUID] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Session:
        """Get an existing session or create a new one.

        Args:
            user_id: Optional user ID to associate with the session
            metadata: Optional initial metadata

        Returns:
            The existing or newly created session
        """
        # Try to find an existing active session for the user
        if user_id:
            existing = await self.get_active_session(user_id)
            if existing:
                return existing

        # Create new session
        session = Session(
            id=uuid.uuid4(),
            user_id=user_id,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            meta_data=metadata or {},
        )

        # Store in database
        from app.db.models import UserSession

        db_session = UserSession(
            id=session.id,
            user_id=session.user_id,
            preferences=session.preferences,
            topics=session.topics,
            seen_article_ids=session.seen_article_ids,
            meta_data=session.metadata,
            is_active=session.is_active,
        )

        self.session.add(db_session)
        await self.session.flush()
        await self.session.refresh(db_session)

        logger.info("Created new session: %s", session.id)
        return session

    async def get_session(self, session_id: uuid.UUID) -> Optional[Session]:
        """Get a session by ID.

        Args:
            session_id: The session ID to retrieve

        Returns:
            The session or None if not found
        """
        from app.db.models import UserSession

        result = await self.session.execute(
            select(UserSession).where(UserSession.id == session_id)
        )
        db_session = result.scalar_one_or_none()

        if db_session is None:
            return None

        return self._db_to_session(db_session)

    async def get_active_session(self, user_id: uuid.UUID) -> Optional[Session]:
        """Get the active session for a user.

        Args:
            user_id: The user ID

        Returns:
            The active session or None if not found
        """
        from app.db.models import UserSession

        result = await self.session.execute(
            select(UserSession).where(
                and_(
                    UserSession.user_id == user_id,
                    UserSession.is_active == True,
                )
            )
        )
        db_session = result.scalar_one_or_none()

        if db_session is None:
            return None

        return self._db_to_session(db_session)

    async def update_preferences(
        self,
        session_id: uuid.UUID,
        preferences: dict[str, Any],
    ) -> Optional[Session]:
        """Update session preferences.

        Args:
            session_id: The session to update
            preferences: New preferences to merge

        Returns:
            The updated session or None if not found
        """
        from app.db.models import UserSession

        result = await self.session.execute(
            select(UserSession).where(UserSession.id == session_id)
        )
        db_session = result.scalar_one_or_none()

        if db_session is None:
            return None

        # Merge preferences
        db_session.preferences = {**db_session.preferences, **preferences}
        db_session.updated_at = datetime.now()

        await self.session.flush()
        return self._db_to_session(db_session)

    async def add_topic(
        self,
        session_id: uuid.UUID,
        topic: str,
    ) -> Optional[Session]:
        """Add a topic to the session.

        Args:
            session_id: The session to update
            topic: Topic to add

        Returns:
            The updated session or None if not found
        """
        from app.db.models import UserSession

        result = await self.session.execute(
            select(UserSession).where(UserSession.id == session_id)
        )
        db_session = result.scalar_one_or_none()

        if db_session is None:
            return None

        if topic not in db_session.topics:
            db_session.topics = db_session.topics + [topic]

        db_session.updated_at = datetime.now()
        await self.session.flush()
        return self._db_to_session(db_session)

    async def mark_article_seen(
        self,
        session_id: uuid.UUID,
        article_id: str,
    ) -> Optional[Session]:
        """Mark an article as seen by the session.

        Args:
            session_id: The session to update
            article_id: ID of the article to mark

        Returns:
            The updated session or None if not found
        """
        from app.db.models import UserSession

        result = await self.session.execute(
            select(UserSession).where(UserSession.id == session_id)
        )
        db_session = result.scalar_one_or_none()

        if db_session is None:
            return None

        if article_id not in db_session.seen_article_ids:
            db_session.seen_article_ids = db_session.seen_article_ids + [article_id]

        db_session.updated_at = datetime.now()
        await self.session.flush()
        return self._db_to_session(db_session)

    async def deactivate_session(self, session_id: uuid.UUID) -> bool:
        """Deactivate a session.

        Args:
            session_id: The session to deactivate

        Returns:
            True if deactivated, False if not found
        """
        from app.db.models import UserSession

        result = await self.session.execute(
            select(UserSession).where(UserSession.id == session_id)
        )
        db_session = result.scalar_one_or_none()

        if db_session is None:
            return False

        db_session.is_active = False
        db_session.updated_at = datetime.now()
        await self.session.flush()
        return True

    def _db_to_session(self, db_session: "UserSession") -> Session:
        """Convert database model to Session object.

        Args:
            db_session: The database session model

        Returns:
            Session domain object
        """
        return Session(
            id=db_session.id,
            user_id=db_session.user_id,
            created_at=db_session.created_at,
            updated_at=db_session.updated_at,
            preferences=db_session.preferences or {},
            topics=db_session.topics or [],
            seen_article_ids=db_session.seen_article_ids or [],
            meta_data=db_session.meta_data or {},
            is_active=db_session.is_active,
        )
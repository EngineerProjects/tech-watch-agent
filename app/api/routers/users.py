import uuid
from typing import Any
from fastapi import APIRouter, HTTPException

from app.db.base import async_session_factory
from app.db.repositories import UserRepository, UserTopicRepository
from app.db.models import User, UserTopic
from app.api.models import UserCreate, UserResponse, UserTopicCreate

router = APIRouter(prefix="/users", tags=["Users"])

@router.post("", response_model=UserResponse)
async def create_user(user: UserCreate) -> UserResponse:
    """Create a new user."""
    async with async_session_factory() as session:
        repo = UserRepository(session)

        # Check if email exists
        existing = await repo.get_by_email(user.email)
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

        # Create user
        db_user = User(
            email=user.email,
            username=user.username,
            preferences=user.preferences,
        )
        created = await repo.create(db_user)
        await session.commit()

        return UserResponse(
            id=str(created.id),
            email=created.email,
            username=created.username,
            preferences=created.preferences,
            is_active=created.is_active,
            created_at=created.created_at,
        )

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: str) -> UserResponse:
    """Get a user by ID."""
    async with async_session_factory() as session:
        repo = UserRepository(session)
        user = await repo.get_by_id(uuid.UUID(user_id))

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return UserResponse(
            id=str(user.id),
            email=user.email,
            username=user.username,
            preferences=user.preferences,
            is_active=user.is_active,
            created_at=user.created_at,
        )

@router.get("/{user_id}/topics")
async def get_user_topics(user_id: str) -> list[dict[str, Any]]:
    """Get topics for a user."""
    async with async_session_factory() as session:
        repo = UserTopicRepository(session)
        topics = await repo.get_active_by_user(uuid.UUID(user_id))
        return [
            {
                "id": str(t.id),
                "topic": t.topic,
                "frequency": t.frequency,
                "is_active": t.is_active,
            }
            for t in topics
        ]

@router.post("/{user_id}/topics")
async def add_user_topic(user_id: str, topic: UserTopicCreate) -> dict[str, Any]:
    """Add a topic for a user."""
    async with async_session_factory() as session:
        repo = UserTopicRepository(session)

        user_topic = UserTopic(
            user_id=uuid.UUID(user_id),
            topic=topic.topic,
            frequency=topic.frequency,
        )
        created = await repo.create(user_topic)
        await session.commit()

        return {
            "id": str(created.id),
            "topic": created.topic,
            "frequency": created.frequency,
        }

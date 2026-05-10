"""
Database base module.

Provides SQLAlchemy async engine, session factory, and base class for all ORM models.
Uses PostgreSQL with asyncpg driver for high-performance async operations.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.config.settings import get_settings

# Get database URL from settings
_settings = get_settings()
DATABASE_URL = _settings.database_url


class Base(DeclarativeBase):
    """Base class for all ORM models in the application.

    This class provides the declarative base for SQLAlchemy models.
    All database models should inherit from this class to ensure
    consistent configuration and metadata handling.
    """

    pass


# Async engine configuration for production use
# Using create_async_engine for async operations with asyncpg
engine = create_async_engine(
    DATABASE_URL,
    echo=_settings.app_env == "development",
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Async session factory - used for dependency injection and background tasks
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def init_db() -> None:
    """Initialize the database by creating all tables.

    This function should be called on application startup to ensure
    all database tables exist before the application starts processing requests.

    Note: In production, consider using Alembic for database migrations
    instead of creating tables on startup.
    """
    async with engine.begin() as conn:
        # Create all tables based on ORM model definitions
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections gracefully.

    This function should be called on application shutdown to ensure
    all database connections are properly closed and resources are released.
    """
    await engine.dispose()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides an async database session.

    This function is designed to be used as a FastAPI dependency with Depends().
    It automatically handles session creation and cleanup, ensuring that
    database sessions are properly closed after each request.

    Usage:
        @app.get("/articles")
        async def get_articles(db: AsyncSession = Depends(get_db_session)):
            result = await db.execute(select(Article))
            return result.scalars().all()

    Yields:
        AsyncSession: An async SQLAlchemy session for database operations.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for database sessions outside of FastAPI dependency injection.

    This function provides a programmatic way to obtain a database session
    for use in background tasks, CLI commands, or other non-request contexts.

    Usage:
        async with get_db_context() as db:
            article = Article(title="Test", content="Content")
            db.add(article)
            await db.flush()

    Yields:
        AsyncSession: An async SQLAlchemy session for database operations.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
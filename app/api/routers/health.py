from typing import Any
from fastapi import APIRouter

from app.db.base import async_session_factory
from app.rag.memory_manager import MemoryManager
from app.config.settings import get_settings
from app.api.models import HealthResponse, StatsResponse

router = APIRouter(tags=["Health"])

async def _get_stats(session) -> dict[str, Any]:
    """Get system statistics from database."""
    from sqlalchemy import select, func, and_
    from app.db.models import User, Article, NewsletterRun

    # Get article count
    article_count = await session.scalar(select(func.count()).select_from(Article))

    # Get user count
    user_count = await session.scalar(select(func.count()).select_from(User))

    # Get newsletter run stats
    run_stats = await session.scalar(
        select(
            func.count(NewsletterRun.id).label("total"),
            func.sum(
                func.case((NewsletterRun.delivery_success == True, 1), else_=0)
            ).label("successful"),
        )
    )

    return {
        "total_articles": article_count or 0,
        "total_users": user_count or 0,
        "total_newsletter_runs": run_stats.total if run_stats else 0,
        "successful_deliveries": run_stats.successful if run_stats and run_stats.successful else 0,
        "active_sessions": 0,  # Would need session table count
    }


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Comprehensive health check endpoint."""
    settings = get_settings()
    health = {
        "status": "ok",
        "database": "unknown",
        "memory": "unknown",
        "agents": {}
    }

    # Check database
    try:
        async with async_session_factory() as session:
            from sqlalchemy import text
            await session.execute(text("SELECT 1"))
        health["database"] = "healthy"
    except Exception as exc:
        health["database"] = f"error: {exc}"

    # Check memory
    try:
        async with async_session_factory() as session:
            manager = MemoryManager(session)
            memory_health = await manager.health_check()
            health["memory"] = "healthy" if memory_health.get("database") == "healthy" else "error"
    except Exception:
        health["memory"] = "not_initialized"

    # Check agents
    try:
        from app.agents.newsletter.agent import create_newsletter_agent
        agent = create_newsletter_agent(settings)
        health["agents"]["newsletter"] = True
    except Exception:
        health["agents"]["newsletter"] = False

    try:
        from app.agents.deep_research.agent import create_deep_research_agent
        agent = create_deep_research_agent(settings=settings)
        health["agents"]["deep_research"] = True
    except Exception:
        health["agents"]["deep_research"] = False

    return HealthResponse(**health)


@router.get("/status")
async def status() -> dict[str, Any]:
    """Get system status and statistics."""
    async with async_session_factory() as session:
        stats = await _get_stats(session)
    return stats


@router.get("/stats", response_model=StatsResponse, tags=["Stats"])
async def get_stats() -> StatsResponse:
    """Get system statistics."""
    async with async_session_factory() as session:
        stats = await _get_stats(session)
        return StatsResponse(**stats)

from typing import Any
from fastapi import APIRouter, HTTPException

from app.db.base import async_session_factory
from app.rag.memory_manager import MemoryManager
from app.config.settings import get_settings
from app.api.models import HealthResponse, StatsResponse

router = APIRouter(tags=["Health"])


async def _get_stats(session) -> dict[str, Any]:
    """Get system statistics from database."""
    from sqlalchemy import case, func, select
    from app.db.models import Article, NewsletterRun, ResearchSession, User

    article_count = await session.scalar(select(func.count(Article.id))) or 0
    user_count = await session.scalar(select(func.count(User.id))) or 0
    active_sessions = await session.scalar(
        select(func.count(ResearchSession.id)).where(ResearchSession.status == "running")
    ) or 0

    newsletter_row = (
        await session.execute(
            select(
                func.count(NewsletterRun.id).label("total"),
                func.coalesce(
                    func.sum(case((NewsletterRun.delivery_success.is_(True), 1), else_=0)),
                    0,
                ).label("successful"),
            )
        )
    ).one()

    return {
        "total_articles": article_count,
        "total_users": user_count,
        "total_newsletter_runs": newsletter_row.total or 0,
        "successful_deliveries": newsletter_row.successful or 0,
        "active_sessions": active_sessions,
    }


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Comprehensive health check endpoint."""
    settings = get_settings()
    health = {
        "status": "ok",
        "database": "unknown",
        "memory": "unknown",
        "agents": {},
    }

    try:
        async with async_session_factory() as session:
            from sqlalchemy import text

            await session.execute(text("SELECT 1"))
        health["database"] = "healthy"
    except Exception as exc:
        health["database"] = f"error: {exc}"

    try:
        async with async_session_factory() as session:
            manager = MemoryManager(session)
            memory_health = await manager.health_check()
            memory_ok = (
                memory_health.get("database") == "healthy"
                and memory_health.get("vector_store") == "healthy"
            )
            health["memory"] = "healthy" if memory_ok else "degraded"
    except Exception as exc:
        health["memory"] = f"error: {exc}"

    try:
        from app.agents.newsletter.agent import create_newsletter_agent

        create_newsletter_agent(settings)
        health["agents"]["newsletter"] = True
    except Exception:
        health["agents"]["newsletter"] = False

    try:
        from app.agents.deep_research.agent import create_deep_research_agent

        create_deep_research_agent(settings=settings)
        health["agents"]["deep_research"] = True
    except Exception:
        health["agents"]["deep_research"] = False

    if (
        health["database"] != "healthy"
        or health["memory"] != "healthy"
        or not all(health["agents"].values())
    ):
        health["status"] = "degraded"

    return HealthResponse(**health)


@router.get("/status")
async def status() -> dict[str, Any]:
    """Get system status and statistics."""
    try:
        async with async_session_factory() as session:
            return await _get_stats(session)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not load system status: {exc}") from exc


@router.get("/stats", response_model=StatsResponse, tags=["Stats"])
async def get_stats() -> StatsResponse:
    """Get system statistics."""
    try:
        async with async_session_factory() as session:
            stats = await _get_stats(session)
        return StatsResponse(**stats)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not load stats: {exc}") from exc

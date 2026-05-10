import uuid
from typing import Any, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query

from app.db.base import async_session_factory
from app.db.repositories import NewsletterRunRepository
from app.agents.newsletter.agent import create_newsletter_agent
from app.config.settings import get_settings
from app.api.models import NewsletterGenerateRequest, NewsletterGenerateResponse
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/newsletter", tags=["Newsletter"])

@router.post("/generate", response_model=NewsletterGenerateResponse)
async def generate_newsletter(
    payload: NewsletterGenerateRequest,
    background_tasks: BackgroundTasks,
) -> NewsletterGenerateResponse:
    """Generate a newsletter (async or sync)."""
    try:
        resolved_settings = get_settings()
        agent = create_newsletter_agent(resolved_settings)

        # Run synchronously for now (background_tasks not fully implemented)
        result = await agent.execute({
            "topics": payload.topics,
            "send_email": payload.send_email,
        })

        if not result.success:
            raise HTTPException(status_code=500, detail=result.errors[0] if result.errors else "Generation failed")

        output = result.output
        newsletter = output.get("newsletter", "")

        # Get first line as subject
        subject = newsletter.split("\n")[0] if newsletter else "Tech Watch Newsletter"
        subject = subject.replace("#", "").strip()

        return NewsletterGenerateResponse(
            run_id=str(result.session_id) if result.session_id else str(uuid.uuid4()),
            subject=subject,
            article_count=output.get("article_count", 0),
            status="completed",
            preview=newsletter[:500],
        )

    except Exception as exc:
        logger.error("Newsletter generation failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

@router.post("/generate/sync", response_model=NewsletterGenerateResponse)
async def generate_newsletter_sync(payload: NewsletterGenerateRequest) -> NewsletterGenerateResponse:
    """Generate a newsletter synchronously."""
    return await generate_newsletter(payload, BackgroundTasks())

@router.get("/history")
async def newsletter_history(
    user_id: Optional[str] = None,
    limit: int = Query(10),
) -> list[dict[str, Any]]:
    """Get newsletter generation history."""
    async with async_session_factory() as session:
        repo = NewsletterRunRepository(session)

        user_uuid = uuid.UUID(user_id) if user_id else None
        runs = await repo.get_recent(user_uuid, limit)

        return [
            {
                "id": str(run.id),
                "subject": run.subject,
                "status": run.status,
                "articles_count": run.articles_count,
                "delivery_success": run.delivery_success,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            }
            for run in runs
        ]

@router.get("/stats")
async def newsletter_stats(user_id: Optional[str] = None) -> dict[str, Any]:
    """Get newsletter statistics."""
    async with async_session_factory() as session:
        repo = NewsletterRunRepository(session)
        user_uuid = uuid.UUID(user_id) if user_id else None
        stats = await repo.get_stats(user_uuid)
        return stats

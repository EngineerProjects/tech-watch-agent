import uuid
from typing import Any, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query

from app.db.base import async_session_factory
from app.db.repositories import NewsletterRunRepository
from app.config.settings import get_settings
from app.api.models import NewsletterGenerateRequest, NewsletterGenerateResponse
from app.core.logging import get_logger
from app.core.research_brief import build_research_brief, derive_session_title

logger = get_logger(__name__)
router = APIRouter(prefix="/newsletter", tags=["Newsletter"])


@router.post("/generate", response_model=NewsletterGenerateResponse)
async def generate_newsletter(
    payload: NewsletterGenerateRequest,
    _background_tasks: BackgroundTasks,
) -> NewsletterGenerateResponse:
    """Generate newsletter content via the orchestrator pipeline and optionally deliver it."""
    try:
        from app.agents.orchestrator.agent import OrchestratorAgent

        topics = payload.topics or []
        subject = f"Newsletter: {', '.join(topics[:3])}" if topics else "Newsletter Tech Watch"
        task = build_research_brief(
            subject=subject,
            topics=topics or None,
            research_instructions=None,
        )

        agent = OrchestratorAgent()
        result = await agent.execute({
            "task": task,
            "subject": subject,
            "title": derive_session_title(subject=subject, task=task),
            "topics": topics,
            "send_email": payload.send_email,
            "autonomous": True,
        })

        if not result.success:
            raise HTTPException(
                status_code=500,
                detail=result.errors[0] if result.errors else "Generation failed",
            )

        output = result.output or {}
        report = output.get("report") or ""
        article_count = len(output.get("research_results", []))
        subject_line = report.split("\n")[0].replace("#", "").strip() if report else subject

        return NewsletterGenerateResponse(
            run_id=str(result.session_id) if result.session_id else str(uuid.uuid4()),
            subject=subject_line,
            article_count=article_count,
            status="completed",
            preview=report[:500],
            email_sent=output.get("email_sent", False),
            delivery_message="Newsletter générée via orchestrateur",
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Newsletter generation failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/generate/sync", response_model=NewsletterGenerateResponse)
async def generate_newsletter_sync(payload: NewsletterGenerateRequest) -> NewsletterGenerateResponse:
    """Generate a newsletter synchronously (alias for /generate)."""
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

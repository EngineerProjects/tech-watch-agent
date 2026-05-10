import uuid
from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Query

from app.db.base import async_session_factory
from app.db.repositories import ResearchSessionRepository
from app.agents.deep_research.agent import create_deep_research_agent
from app.agents.deep_research.config import DeepResearchConfig
from app.config.settings import get_settings
from app.api.models import DeepResearchRequest, DeepResearchResponse
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/research", tags=["Deep Research"])

@router.post("", response_model=DeepResearchResponse)
async def start_research(payload: DeepResearchRequest) -> DeepResearchResponse:
    """Start a deep research session."""
    try:
        resolved_settings = get_settings()
        config = DeepResearchConfig(
            research_depth=payload.research_depth,
            allow_clarification=payload.allow_clarification,
        )
        agent = create_deep_research_agent(config=config, settings=resolved_settings)

        result = await agent.execute({
            "query": payload.query,
        })

        if not result.success:
            raise HTTPException(status_code=500, detail=result.errors[0] if result.errors else "Research failed")

        output = result.output

        return DeepResearchResponse(
            session_id=str(result.session_id) if result.session_id else str(uuid.uuid4()),
            status="completed",
            final_report=output.get("report"),
            research_brief=output.get("research_brief"),
            notes_count=len(output.get("notes", [])),
        )

    except Exception as exc:
        logger.error("Deep research failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

@router.get("/history")
async def research_history(
    user_id: Optional[str] = None,
    limit: int = Query(10),
) -> list[dict[str, Any]]:
    """Get research session history."""
    async with async_session_factory() as session:
        repo = ResearchSessionRepository(session)

        user_uuid = uuid.UUID(user_id) if user_id else None
        sessions = await repo.get_recent(user_uuid, limit)

        return [
            {
                "id": str(s.id),
                "research_brief": s.research_brief[:200],
                "status": s.status,
                "final_report_length": len(s.final_report) if s.final_report else 0,
                "iterations_count": s.iterations_count,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
            }
            for s in sessions
        ]

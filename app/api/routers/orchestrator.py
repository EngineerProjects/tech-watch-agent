from fastapi import APIRouter
from app.config.settings import get_settings
from app.api.models import OrchestratorRequest, OrchestratorResponse
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/orchestrator", tags=["Orchestrator"])

@router.post("/run", response_model=OrchestratorResponse)
async def run_orchestrator(payload: OrchestratorRequest) -> OrchestratorResponse:
    """Run the orchestrator agent for research and report generation."""
    from app.scheduler.service import OrchestratorScheduler
    resolved_settings = get_settings()

    try:
        scheduler = OrchestratorScheduler(
            mode=payload.mode,
            settings=resolved_settings,
        )
        result = await scheduler.run_task(
            task=payload.task,
            topics=payload.topics,
            send_email=payload.send_email,
        )

        return OrchestratorResponse(
            success=result.get("success", False),
            report=result.get("report"),
            subject=result.get("subject"),
            email_sent=result.get("email_sent", False),
            research_results_count=len(result.get("research_results", [])),
            plan_steps=len(result.get("plan", [])),
            execution_time=result.get("execution_time"),
            errors=result.get("errors", []),
        )
    except Exception as exc:
        logger.error("Orchestrator endpoint failed: %s", exc)
        return OrchestratorResponse(
            success=False,
            email_sent=False,
            errors=[str(exc)],
        )

@router.post("/task", response_model=OrchestratorResponse)
async def run_orchestrator_task(payload: OrchestratorRequest) -> OrchestratorResponse:
    """Alias for /orchestrator/run with full task control."""
    return await run_orchestrator(payload)

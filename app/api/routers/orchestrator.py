from fastapi import APIRouter
from app.config.settings import get_settings
from app.api.models import OrchestratorRequest, OrchestratorResponse
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/orchestrator", tags=["Orchestrator"])


@router.post("/run", response_model=OrchestratorResponse)
async def run_orchestrator(payload: OrchestratorRequest) -> OrchestratorResponse:
    """Run the orchestrator agent for research and report generation.

    Mode:
    - autonomous=True (default): Fully automated, no human approval needed.
                                 Use for scheduled tasks (e.g., "2x per week").
    - autonomous=False: Interactive mode with human approval checkpoints.
                       Use for on-demand research with review before sending.
    """
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
            autonomous=payload.autonomous,
        )

        return OrchestratorResponse(
            success=result.get("success", False),
            report=result.get("report"),
            subject=result.get("subject"),
            email_sent=result.get("email_sent", False),
            research_results_count=len(result.get("research_results", [])),
            plan_steps=len(result.get("plan", [])),
            execution_time=result.get("execution_time"),
            quality_score=result.get("quality_score"),
            approval_status=result.get("approval_status"),
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


@router.post("/schedule", response_model=dict)
async def setup_scheduled_task(
    task: str = "Weekly tech watch",
    topics: list[str] | None = None,
    schedule_times: list[str] | None = None,
) -> dict:
    """Set up a scheduled autonomous task.

    This endpoint configures the scheduler to run the orchestrator
    automatically at specified times (e.g., ["08:00", "18:00"]).
    """
    from app.scheduler.service import OrchestratorScheduler
    from app.config.settings import get_settings

    scheduler = OrchestratorScheduler(
        mode="v2",
        settings=get_settings(),
    )

    scheduler.start_scheduler(
        task=task,
        topics=topics,
        schedule_times=schedule_times or ["08:00", "18:00"],
    )

    return {
        "status": "scheduled",
        "task": task,
        "schedule_times": schedule_times,
        "mode": "autonomous",
    }


@router.get("/status", response_model=dict)
async def get_orchestrator_status() -> dict:
    """Get the current runtime status of the orchestrator."""
    from app.scheduler.service import OrchestratorScheduler

    return {
        "status": "ok",
        "mode": "available",
        "capabilities": {
            "autonomous": True,
            "interactive": True,
            "v1_compatible": True,
            "v2_orchestrator": True,
        },
    }

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from typing import Optional
from app.config.settings import get_settings
from app.api.models import OrchestratorRequest, OrchestratorResponse
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/orchestrator", tags=["Orchestrator"])


@router.post("/run", response_model=OrchestratorResponse)
async def run_orchestrator(payload: OrchestratorRequest) -> OrchestratorResponse:
    """Run the full orchestrator pipeline (plan → research → synthesis → email)."""
    try:
        from app.agents.orchestrator.agent import OrchestratorAgent

        agent = OrchestratorAgent()
        result = await agent.execute({
            "task": payload.task,
            "topics": payload.topics,
            "send_email": payload.send_email,
            "autonomous": payload.autonomous,
        })

        if result.success:
            output = result.output or {}
            return OrchestratorResponse(
                success=True,
                session_id=str(result.session_id) if result.session_id else output.get("session_id"),
                report=output.get("report"),
                email_sent=output.get("email_sent", False),
                research_results_count=len(output.get("research_results", [])),
                plan_steps=len(output.get("plan", [])),
                execution_time=result.metadata.get("execution_time_seconds"),
                quality_score=result.metadata.get("quality_score"),
                errors=[],
            )

        return OrchestratorResponse(
            success=False,
            email_sent=False,
            errors=result.errors,
        )

    except Exception as exc:
        logger.error("Orchestrator endpoint failed: %s", exc)
        return OrchestratorResponse(
            success=False,
            email_sent=False,
            errors=[str(exc)],
        )


@router.get("/stream")
async def stream_orchestrator(
    task: str = Query(..., description="Research task to execute"),
    topics: Optional[list[str]] = Query(None, description="Optional topic list"),
    autonomous: bool = Query(True, description="Run without human intervention"),
):
    """Run the orchestrator and stream events in real-time via SSE (GET for EventSource compatibility)."""
    from app.services.streaming_service import StreamingOrchestratorService

    service = StreamingOrchestratorService()

    return StreamingResponse(
        service.stream_run(
            task=task,
            topics=topics,
            autonomous=autonomous,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/task", response_model=OrchestratorResponse)
async def run_orchestrator_task(payload: OrchestratorRequest) -> OrchestratorResponse:
    """Alias for /orchestrator/run with full task control."""
    return await run_orchestrator(payload)


@router.post("/schedule", response_model=dict)
async def setup_scheduled_task(
    task: str = "Weekly tech watch",
    topics: Optional[list[str]] = None,
    schedule_times: Optional[list[str]] = None,
) -> dict:
    """Set up a scheduled autonomous task."""
    from app.scheduler.service import OrchestratorScheduler

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

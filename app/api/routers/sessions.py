"""
Session management API endpoints.

Provides endpoints for:
- Listing sessions (all, interruptible, by status)
- Getting session details (with plan, checkpoints)
- Resuming interrupted sessions
- Getting plan version history
- Getting checkpoint history
"""

import uuid
from datetime import datetime
from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Query

from app.db.base import async_session_factory
from app.db.repositories import ResearchSessionRepository
from app.core.logging import get_logger


logger = get_logger(__name__)
router = APIRouter(prefix="/sessions", tags=["Sessions"])


@router.get("")
async def list_sessions(
    status: Optional[str] = Query(None, description="Filter by status (created, running, completed, failed)"),
    interruptible: bool = Query(False, description="Only return sessions that can be resumed"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """List research sessions with optional filters."""
    async with async_session_factory() as session:
        repo = ResearchSessionRepository(session)

        if interruptible:
            sessions = await repo.get_interruptible_sessions()
        elif status:
            sessions = await repo.get_by_status(status, limit)
        else:
            user_uuid = uuid.UUID(user_id) if user_id else None
            sessions = await repo.get_recent(user_uuid, limit)

        return {
            "sessions": [
                {
                    "id": str(s.id),
                    "research_brief": s.research_brief[:200] + "..." if len(s.research_brief) > 200 else s.research_brief,
                    "status": s.status,
                    "phase": s.phase,
                    "plan_version": s.plan_version,
                    "compaction_version": s.compaction_version,
                    "iterations_count": s.iterations_count,
                    "has_checkpoint": s.phase in ["research", "collection", "analysis"],
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                    "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                }
                for s in sessions
            ],
            "total": len(sessions),
        }


@router.get("/{session_id}")
async def get_session(session_id: str) -> dict[str, Any]:
    """Get detailed session information including plan and results."""
    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID format")

    async with async_session_factory() as session:
        repo = ResearchSessionRepository(session)
        research_session = await repo.get_by_id(session_uuid)

        if not research_session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Get plan versions
        plan_versions = await repo.get_plan_versions(session_uuid)

        # Get checkpoints
        checkpoints = await repo.get_checkpoints(session_uuid)

        return {
            "id": str(research_session.id),
            "user_id": str(research_session.user_id) if research_session.user_id else None,
            "research_brief": research_session.research_brief,
            "status": research_session.status,
            "phase": research_session.phase,
            "final_report": research_session.final_report,
            "notes": research_session.notes,
            "raw_notes": research_session.raw_notes,
            "meta_data": research_session.meta_data,
            "iterations_count": research_session.iterations_count,
            "plan_version": research_session.plan_version,
            "current_step_index": research_session.current_step_index,
            "compaction_version": research_session.compaction_version,
            "plan": research_session.plan,
            "research_results": research_session.research_results,
            "analysis_results": research_session.analysis_results,
            "compacted_memory": research_session.compacted_memory,
            "plan_versions": [
                {
                    "version": pv.version,
                    "reason": pv.reason,
                    "created_at": pv.created_at.isoformat() if pv.created_at else None,
                }
                for pv in plan_versions
            ],
            "checkpoints": [
                {
                    "phase": cp.phase,
                    "checkpoint_index": cp.checkpoint_index,
                    "is_latest": cp.is_latest,
                    "created_at": cp.created_at.isoformat() if cp.created_at else None,
                }
                for cp in checkpoints
            ],
            "created_at": research_session.created_at.isoformat() if research_session.created_at else None,
            "updated_at": research_session.updated_at.isoformat() if research_session.updated_at else None,
            "completed_at": research_session.completed_at.isoformat() if research_session.completed_at else None,
        }


@router.get("/{session_id}/plan")
async def get_session_plan_versions(session_id: str) -> dict[str, Any]:
    """Get plan version history for a session."""
    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID format")

    async with async_session_factory() as session:
        repo = ResearchSessionRepository(session)
        research_session = await repo.get_by_id(session_uuid)

        if not research_session:
            raise HTTPException(status_code=404, detail="Session not found")

        plan_versions = await repo.get_plan_versions(session_uuid)

        return {
            "session_id": session_id,
            "current_version": research_session.plan_version,
            "current_plan": research_session.plan,
            "current_step_index": research_session.current_step_index,
            "versions": [
                {
                    "version": pv.version,
                    "plan": pv.plan,
                    "reason": pv.reason,
                    "created_at": pv.created_at.isoformat() if pv.created_at else None,
                }
                for pv in plan_versions
            ],
        }


@router.get("/{session_id}/checkpoints")
async def get_session_checkpoints(session_id: str) -> dict[str, Any]:
    """Get checkpoint history for a session."""
    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID format")

    async with async_session_factory() as session:
        repo = ResearchSessionRepository(session)
        research_session = await repo.get_by_id(session_uuid)

        if not research_session:
            raise HTTPException(status_code=404, detail="Session not found")

        checkpoints = await repo.get_checkpoints(session_uuid)
        latest_checkpoint = await repo.get_latest_checkpoint(session_uuid)

        return {
            "session_id": session_id,
            "latest_checkpoint": {
                "phase": latest_checkpoint.phase,
                "checkpoint_index": latest_checkpoint.checkpoint_index,
                "created_at": latest_checkpoint.created_at.isoformat() if latest_checkpoint.created_at else None,
            } if latest_checkpoint else None,
            "checkpoints": [
                {
                    "id": str(cp.id),
                    "phase": cp.phase,
                    "checkpoint_index": cp.checkpoint_index,
                    "is_latest": cp.is_latest,
                    "articles_count": len(cp.articles_snapshot) if cp.articles_snapshot else 0,
                    "results_count": len(cp.results_snapshot) if cp.results_snapshot else 0,
                    "created_at": cp.created_at.isoformat() if cp.created_at else None,
                }
                for cp in checkpoints
            ],
        }


@router.get("/{session_id}/checkpoint/latest")
async def get_latest_checkpoint(session_id: str) -> dict[str, Any]:
    """Get the latest checkpoint details for resume."""
    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID format")

    async with async_session_factory() as session:
        repo = ResearchSessionRepository(session)
        research_session = await repo.get_by_id(session_uuid)

        if not research_session:
            raise HTTPException(status_code=404, detail="Session not found")

        checkpoint = await repo.get_latest_checkpoint(session_uuid)

        if not checkpoint:
            raise HTTPException(status_code=404, detail="No checkpoint found for this session")

        return {
            "session_id": session_id,
            "checkpoint_id": str(checkpoint.id),
            "phase": checkpoint.phase,
            "checkpoint_index": checkpoint.checkpoint_index,
            "state_snapshot": checkpoint.state_snapshot,
            "articles_snapshot": checkpoint.articles_snapshot,
            "results_snapshot": checkpoint.results_snapshot,
            "created_at": checkpoint.created_at.isoformat() if checkpoint.created_at else None,
        }


@router.post("/{session_id}/resume")
async def resume_session(
    session_id: str,
    from_checkpoint: bool = Query(True, description="Resume from latest checkpoint if available"),
) -> dict[str, Any]:
    """Resume an interrupted session from checkpoint.

    This endpoint:
    1. Gets the session details
    2. Retrieves the latest checkpoint
    3. Returns state to resume orchestrator execution
    """
    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID format")

    async with async_session_factory() as session:
        repo = ResearchSessionRepository(session)
        research_session = await repo.get_by_id(session_uuid)

        if not research_session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Check if session can be resumed
        if research_session.status in ["completed", "failed"]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot resume session with status '{research_session.status}'"
            )

        # Get latest checkpoint
        checkpoint = await repo.get_latest_checkpoint(session_uuid) if from_checkpoint else None

        return {
            "resumable": True,
            "session_id": session_id,
            "research_brief": research_session.research_brief,
            "status": research_session.status,
            "phase": research_session.phase,
            "plan": research_session.plan,
            "current_step_index": research_session.current_step_index,
            "plan_version": research_session.plan_version,
            "checkpoint_available": checkpoint is not None,
            "checkpoint": {
                "id": str(checkpoint.id),
                "phase": checkpoint.phase,
                "checkpoint_index": checkpoint.checkpoint_index,
                "state_snapshot": checkpoint.state_snapshot,
                "articles_snapshot": checkpoint.articles_snapshot,
                "results_snapshot": checkpoint.results_snapshot,
                "created_at": checkpoint.created_at.isoformat() if checkpoint.created_at else None,
            } if checkpoint else None,
            "resume_instructions": _get_resume_instructions(research_session.phase),
        }


def _get_resume_instructions(phase: str) -> str:
    """Get instructions for resuming from a specific phase."""
    instructions = {
        "plan": "Start from planning phase. The session was interrupted before research began.",
        "research": "Resume from research phase. Some steps may have completed, check plan status.",
        "collection": "Resume from collection phase. Research results are available in checkpoint.",
        "analysis": "Resume from analysis phase. Research data is collected and checkpointed.",
        "synthesis": "Resume from synthesis phase. Analysis is complete, generating final report.",
        "delivery": "Resume from delivery phase. Report is ready, sending email.",
    }
    return instructions.get(
        phase,
        f"Resume from '{phase}' phase. Review checkpoint data for exact state."
    )


@router.get("/interruptible")
async def list_interruptible_sessions() -> dict[str, Any]:
    """List all sessions that can be resumed (not completed or failed)."""
    async with async_session_factory() as session:
        repo = ResearchSessionRepository(session)
        sessions = await repo.get_interruptible_sessions()

        return {
            "sessions": [
                {
                    "id": str(s.id),
                    "research_brief": s.research_brief[:200] + "..." if len(s.research_brief) > 200 else s.research_brief,
                    "status": s.status,
                    "phase": s.phase,
                    "plan_version": s.plan_version,
                    "current_step_index": s.current_step_index,
                    "has_checkpoint": True,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                }
                for s in sessions
            ],
            "total": len(sessions),
            "message": f"Found {len(sessions)} resumable sessions",
        }

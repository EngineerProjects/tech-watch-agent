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
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.security import require_admin_access
from app.db.base import async_session_factory
from app.db.repositories import ResearchSessionRepository
from app.core.logging import get_logger
from app.services.session_manager import normalize_plan_payload


logger = get_logger(__name__)
router = APIRouter(prefix="/sessions", tags=["Sessions"], dependencies=[Depends(require_admin_access)])


def _session_title(session: Any) -> str:
    meta = session.meta_data if isinstance(session.meta_data, dict) else {}
    title = meta.get("title") or meta.get("subject") or session.research_brief
    return str(title)


def _session_subject(session: Any) -> Optional[str]:
    meta = session.meta_data if isinstance(session.meta_data, dict) else {}
    subject = meta.get("subject")
    return str(subject) if isinstance(subject, str) and subject.strip() else None


def _session_research_instructions(session: Any) -> Optional[str]:
    meta = session.meta_data if isinstance(session.meta_data, dict) else {}
    value = meta.get("research_instructions")
    return str(value) if isinstance(value, str) and value.strip() else None


def _serialize_session_summary(session: Any) -> dict[str, Any]:
    title = _session_title(session)
    research_brief = session.research_brief[:200] + "..." if len(session.research_brief) > 200 else session.research_brief
    meta = session.meta_data if isinstance(session.meta_data, dict) else {}
    return {
        "id": str(session.id),
        "title": title,
        "subject": _session_subject(session),
        "research_instructions": _session_research_instructions(session),
        "research_brief": research_brief,
        "meta_data": meta,
        "status": session.status,
        "phase": session.phase,
        "plan_version": session.plan_version,
        "compaction_version": session.compaction_version,
        "iterations_count": session.iterations_count,
        "has_checkpoint": session.phase in ["research", "collection", "analysis"],
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        "completed_at": session.completed_at.isoformat() if session.completed_at else None,
    }


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
            "sessions": [_serialize_session_summary(s) for s in sessions],
            "total": len(sessions),
        }


@router.get("/interruptible")
async def list_interruptible_sessions() -> dict[str, Any]:
    """List all sessions that can be resumed (not completed or failed)."""
    async with async_session_factory() as session:
        repo = ResearchSessionRepository(session)
        sessions = await repo.get_interruptible_sessions()

        return {
            "sessions": [
                {
                    **_serialize_session_summary(s),
                    "current_step_index": s.current_step_index,
                    "has_checkpoint": True,
                }
                for s in sessions
            ],
            "total": len(sessions),
            "message": f"Found {len(sessions)} resumable sessions",
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

        plan_versions = await repo.get_plan_versions(session_uuid)
        checkpoints = await repo.get_checkpoints(session_uuid)

        return {
            "id": str(research_session.id),
            "user_id": str(research_session.user_id) if research_session.user_id else None,
            "title": _session_title(research_session),
            "subject": _session_subject(research_session),
            "research_instructions": _session_research_instructions(research_session),
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
            "plan": normalize_plan_payload(research_session.plan),
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
            "current_plan": normalize_plan_payload(research_session.plan),
            "current_step_index": research_session.current_step_index,
            "versions": [
                {
                    "version": pv.version,
                    "plan": normalize_plan_payload(pv.plan),
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

        if research_session.status in ["completed", "failed"]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot resume session with status '{research_session.status}'"
            )

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


@router.delete("/{session_id}", status_code=204)
async def delete_session(session_id: str) -> None:
    """Delete a research session and all persisted session-specific entities."""
    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID format")

    async with async_session_factory() as session:
        repo = ResearchSessionRepository(session)
        deleted = await repo.delete(session_uuid)
        if not deleted:
            raise HTTPException(status_code=404, detail="Session not found")
        await session.commit()

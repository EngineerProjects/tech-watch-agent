"""
Session Manager for orchestrator agent.

Provides comprehensive session management with:
- Plan persistence at phase transitions
- Plan versioning with audit trail
- Checkpoint/resume functionality
- Memory compaction for agent context management
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from app.core.logging import get_logger


logger = get_logger(__name__)


class SessionPhase(str, Enum):
    """Session phases for tracking progress."""
    PLAN = "plan"
    RESEARCH = "research"
    COLLECTION = "collection"
    ANALYSIS = "analysis"
    SYNTHESIS = "synthesis"
    DELIVERY = "delivery"
    COMPLETED = "completed"
    FAILED = "failed"


class CompactionReason(str, Enum):
    """Reasons for memory compaction."""
    PHASE_TRANSITION = "phase_transition"
    CONTEXT_LIMIT_WARNING = "context_limit_warning"
    STEP_COMPLETED = "step_completed"
    MANUAL = "manual"
    CHECKPOINT = "checkpoint"


@dataclass
class CompactionResult:
    """Result of memory compaction operation."""
    success: bool
    compacted_data: dict
    original_size: int
    compacted_size: int
    compression_ratio: float
    summary: str
    key_insights: list[str]
    sources_count: int


class SessionManager:
    """Manages session lifecycle with persistence, versioning, and compaction.
    
    Features:
    - Save plan at each phase transition
    - Version control for plan changes
    - Checkpoint/resume for interrupted sessions
    - Memory compaction to avoid LLM context limits
    """

    # Compaction thresholds
    MAX_WORKING_MEMORY_SIZE = 50000  # chars
    CONTEXT_WARNING_THRESHOLD = 40000  # chars
    SUMMARY_THRESHOLD = 10000  # chars per article summary

    def __init__(self, session_id: uuid.UUID) -> None:
        self.session_id = session_id
        self._db_session = None
        self._session = None
        self._phase = SessionPhase.PLAN

    async def initialize(self) -> None:
        """Initialize session from database."""
        from app.db.base import get_db_context
        from app.db.models import ResearchSession
        
        self._db_session = get_db_context().__enter__()
        
        result = await self._db_session.execute(
            select(ResearchSession).where(ResearchSession.id == self.session_id)
        )
        self._session = result.scalar_one_or_none()
        
        if self._session:
            self._phase = SessionPhase(self._session.phase)

    async def close(self) -> None:
        """Close database session."""
        if self._db_session:
            await self._db_session.close()

    @property
    def session(self):
        """Get the database session object."""
        return self._session

    @property
    def phase(self) -> SessionPhase:
        """Get current session phase."""
        return self._phase

    async def save_phase(
        self,
        phase: SessionPhase,
        plan: list[dict],
        current_step_index: int,
        reason: str = "phase_transition",
    ) -> None:
        """Save session state at phase transition.
        
        Args:
            phase: New phase to transition to
            plan: Current execution plan
            current_step_index: Current step being executed
            reason: Reason for this version (for audit trail)
        """
        from app.db.models import ResearchSession, PlanVersion
        from sqlalchemy import update
        
        if not self._session:
            logger.warning("Session not initialized, skipping phase save")
            return

        try:
            # Create plan version
            new_version = PlanVersion(
                id=uuid.uuid4(),
                session_id=self.session_id,
                version=self._session.plan_version + 1,
                plan={"steps": plan, "current_index": current_step_index},
                reason=reason,
            )
            self._db_session.add(new_version)

            # Update session
            self._session.phase = phase.value
            self._session.plan = {"steps": plan}
            self._session.plan_version = self._session.plan_version + 1
            self._session.current_step_index = current_step_index
            self._session.updated_at = datetime.now()

            await self._db_session.commit()
            
            self._phase = phase
            logger.info(
                "Phase saved: session=%s, phase=%s, version=%d",
                self.session_id, phase.value, self._session.plan_version
            )

        except Exception as exc:
            logger.error("Failed to save phase: %s", exc)
            await self._db_session.rollback()
            raise

    async def create_checkpoint(
        self,
        phase: SessionPhase,
        state_snapshot: dict,
        articles: list[dict],
        results: list[dict],
    ) -> str:
        """Create a checkpoint for resumable state.
        
        Args:
            phase: Current phase
            state_snapshot: Full state dict
            articles: Current articles list
            results: Research results
            
        Returns:
            Checkpoint ID
        """
        from app.db.models import SessionCheckpoint
        
        if not self._session:
            logger.warning("Session not initialized, skipping checkpoint")
            return ""

        try:
            # Mark previous checkpoints as not latest
            from sqlalchemy import update
            await self._db_session.execute(
                update(SessionCheckpoint)
                .where(SessionCheckpoint.session_id == self.session_id)
                .values(is_latest=False)
            )

            # Create new checkpoint
            checkpoint_id = uuid.uuid4()
            checkpoint = SessionCheckpoint(
                id=checkpoint_id,
                session_id=self.session_id,
                phase=phase.value,
                checkpoint_index=len(articles),
                state_snapshot=state_snapshot,
                articles_snapshot=articles,
                results_snapshot=results,
                is_latest=True,
            )
            self._db_session.add(checkpoint)
            await self._db_session.commit()

            logger.info(
                "Checkpoint created: session=%s, phase=%s, checkpoint=%s",
                self.session_id, phase.value, checkpoint_id
            )
            return str(checkpoint_id)

        except Exception as exc:
            logger.error("Failed to create checkpoint: %s", exc)
            await self._db_session.rollback()
            return ""

    async def get_latest_checkpoint(self) -> Optional[dict]:
        """Get the latest checkpoint for this session.
        
        Returns:
            Checkpoint data dict or None
        """
        from app.db.models import SessionCheckpoint
        
        if not self._session:
            return None

        try:
            result = await self._db_session.execute(
                select(SessionCheckpoint)
                .where(
                    SessionCheckpoint.session_id == self.session_id,
                    SessionCheckpoint.is_latest == True,
                )
                .order_by(SessionCheckpoint.created_at.desc())
                .limit(1)
            )
            checkpoint = result.scalar_one_or_none()
            
            if checkpoint:
                return {
                    "id": str(checkpoint.id),
                    "phase": checkpoint.phase,
                    "checkpoint_index": checkpoint.checkpoint_index,
                    "state_snapshot": checkpoint.state_snapshot,
                    "articles_snapshot": checkpoint.articles_snapshot,
                    "results_snapshot": checkpoint.results_snapshot,
                    "created_at": checkpoint.created_at.isoformat(),
                }
            return None

        except Exception as exc:
            logger.error("Failed to get checkpoint: %s", exc)
            return None

    async def resume_from_checkpoint(self) -> Optional[dict]:
        """Resume session from latest checkpoint.
        
        Returns:
            Resumed state dict or None
        """
        checkpoint = await self.get_latest_checkpoint()
        
        if not checkpoint:
            logger.info("No checkpoint found for session %s", self.session_id)
            return None

        logger.info(
            "Resuming from checkpoint: session=%s, phase=%s, index=%d",
            self.session_id, checkpoint["phase"], checkpoint["checkpoint_index"]
        )
        
        return checkpoint

    async def get_plan_versions(self) -> list[dict]:
        """Get all plan versions for this session.
        
        Returns:
            List of version dicts ordered by version number
        """
        from app.db.models import PlanVersion
        
        if not self._session:
            return []

        try:
            result = await self._db_session.execute(
                select(PlanVersion)
                .where(PlanVersion.session_id == self.session_id)
                .order_by(PlanVersion.version.asc())
            )
            versions = result.scalars().all()
            
            return [
                {
                    "version": v.version,
                    "plan": v.plan,
                    "reason": v.reason,
                    "created_at": v.created_at.isoformat(),
                }
                for v in versions
            ]

        except Exception as exc:
            logger.error("Failed to get plan versions: %s", exc)
            return []

    async def update_research_results(self, results: list[dict]) -> None:
        """Update research results in session.
        
        Args:
            results: New research results to save
        """
        if not self._session:
            return

        try:
            # Merge with existing results (avoid duplicates by URL)
            existing_urls = {
                r.get("url") for r in self._session.research_results 
                if isinstance(r, dict) and r.get("url")
            }
            
            for result in results:
                if isinstance(result, dict) and result.get("url"):
                    if result["url"] not in existing_urls:
                        self._session.research_results.append(result)
                        existing_urls.add(result["url"])

            self._session.updated_at = datetime.now()
            await self._db_session.commit()

        except Exception as exc:
            logger.error("Failed to update research results: %s", exc)
            await self._db_session.rollback()

    async def save_analysis_results(self, analysis: str) -> None:
        """Save analysis results.
        
        Args:
            analysis: Analysis text to save
        """
        if not self._session:
            return

        try:
            self._session.analysis_results = analysis
            self._session.updated_at = datetime.now()
            await self._db_session.commit()

        except Exception as exc:
            logger.error("Failed to save analysis: %s", exc)
            await self._db_session.rollback()

    def estimate_memory_size(self, state: dict) -> int:
        """Estimate current memory size from state.
        
        Args:
            state: Current orchestrator state
            
        Returns:
            Estimated size in characters
        """
        size = 0
        
        # Plan size
        if "plan" in state:
            size += len(json.dumps(state["plan"]))
        
        # Research results size
        if "research_results" in state:
            for r in state["research_results"]:
                if isinstance(r, dict):
                    size += len(json.dumps(r.get("data", "")))
        
        # Analysis size
        if "analysis_results" in state:
            size += len(str(state["analysis_results"]))
        
        return size

    async def compact_memory(
        self,
        state: dict,
        reason: CompactionReason = CompactionReason.PHASE_TRANSITION,
    ) -> CompactionResult:
        """Compact agent memory to avoid context limits.
        
        This does NOT compact articles (kept full for RAG).
        Compacts: research results summaries, analysis, step histories.
        
        Args:
            state: Current orchestrator state
            reason: Reason for compaction
            
        Returns:
            CompactionResult with compacted data and stats
        """
        original_size = self.estimate_memory_size(state)
        
        if original_size < self.CONTEXT_WARNING_THRESHOLD:
            return CompactionResult(
                success=True,
                compacted_data={},
                original_size=original_size,
                compacted_size=0,
                compression_ratio=0,
                summary="No compaction needed - memory below threshold",
                key_insights=[],
                sources_count=len(state.get("research_results", [])),
            )

        try:
            # Extract key information
            research_results = state.get("research_results", [])
            analysis_results = state.get("analysis_results", "")
            plan = state.get("plan", [])
            
            # Summarize each research result (keep articles full for RAG)
            summarized_results = []
            for r in research_results:
                if isinstance(r, dict):
                    data = r.get("data", [])
                    if isinstance(data, list):
                        # Summarize each article (keep full for RAG)
                        summaries = []
                        for item in data[:20]:  # Limit to 20 items
                            if isinstance(item, dict):
                                summaries.append({
                                    "title": item.get("title", ""),
                                    "summary": self._summarize_text(
                                        item.get("summary", ""), 
                                        self.SUMMARY_THRESHOLD // 4
                                    ),
                                    "url": item.get("url", ""),
                                    "source": item.get("source", ""),
                                })
                        summarized_results.append({
                            "step_id": r.get("step_id", ""),
                            "tool": r.get("tool", ""),
                            "count": len(data),
                            "summaries": summaries,
                        })
                    else:
                        summarized_results.append(r)

            # Compact analysis
            compacted_analysis = ""
            if analysis_results:
                compacted_analysis = self._summarize_text(
                    analysis_results, 
                    self.MAX_WORKING_MEMORY_SIZE // 4
                )

            # Count completed steps
            completed_steps = sum(
                1 for step in plan 
                if step.get("status") == "done"
            )

            # Build compacted memory
            compacted_data = {
                "research_summary": {
                    "total_results": len(research_results),
                    "steps_completed": completed_steps,
                    "steps_total": len(plan),
                    "summarized_results": summarized_results,
                },
                "analysis_compacted": compacted_analysis,
                "compaction_info": {
                    "reason": reason.value,
                    "timestamp": datetime.now().isoformat(),
                    "original_size": original_size,
                },
            }

            compacted_size = len(json.dumps(compacted_data))
            
            # Generate key insights summary
            key_insights = self._extract_key_insights(summarized_results)

            # Save compaction to session
            if self._session:
                self._session.compacted_memory = compacted_data
                self._session.compaction_version += 1
                self._session.updated_at = datetime.now()
                await self._db_session.commit()

            compression_ratio = (original_size - compacted_size) / original_size if original_size > 0 else 0

            result = CompactionResult(
                success=True,
                compacted_data=compacted_data,
                original_size=original_size,
                compacted_size=compacted_size,
                compression_ratio=compression_ratio,
                summary=f"Compacted {len(research_results)} results to {len(summarized_results)} summaries",
                key_insights=key_insights,
                sources_count=len(research_results),
            )

            logger.info(
                "Memory compaction: session=%s, original=%d, compacted=%d, ratio=%.1f%%",
                self.session_id, original_size, compacted_size, compression_ratio * 100
            )

            return result

        except Exception as exc:
            logger.error("Memory compaction failed: %s", exc)
            return CompactionResult(
                success=False,
                compacted_data={},
                original_size=original_size,
                compacted_size=0,
                compression_ratio=0,
                summary=f"Compaction failed: {exc}",
                key_insights=[],
                sources_count=0,
            )

    def _summarize_text(self, text: str, max_length: int) -> str:
        """Summarize text to max length while preserving key points.
        
        Args:
            text: Text to summarize
            max_length: Maximum length in characters
            
        Returns:
            Summarized text
        """
        if not text or len(text) <= max_length:
            return text

        # Simple truncation with ellipsis
        return text[:max_length].rsplit(" ", 1)[0] + "..."

    def _extract_key_insights(self, results: list[dict]) -> list[str]:
        """Extract key insights from summarized results.
        
        Args:
            results: Summarized research results
            
        Returns:
            List of key insight strings
        """
        insights = []
        
        for r in results:
            tool = r.get("tool", "unknown")
            count = r.get("count", 0)
            summaries = r.get("summaries", [])
            
            if summaries:
                first_title = summaries[0].get("title", "Untitled")
                insights.append(f"{tool}: {count} results, top: {first_title[:50]}")
            else:
                insights.append(f"{tool}: {count} results")

        return insights[:10]  # Limit to 10 insights


async def create_session(
    task: str,
    user_id: Optional[uuid.UUID] = None,
    topics: Optional[list[str]] = None,
) -> uuid.UUID:
    """Create a new research session.
    
    Args:
        task: Research task/brief
        user_id: Optional user ID
        topics: Optional list of topics
        
    Returns:
        New session ID
    """
    from app.db.base import get_db_context
    from app.db.models import ResearchSession
    
    session_id = uuid.uuid4()
    
    async with get_db_context() as db:
        session = ResearchSession(
            id=session_id,
            user_id=user_id,
            research_brief=task,
            status="created",
            phase="plan",
            meta_data={"topics": topics or []},
        )
        db.add(session)
        await db.commit()
        
        logger.info("Created research session: %s", session_id)
        return session_id


async def get_session(session_id: uuid.UUID) -> Optional[dict]:
    """Get session by ID.
    
    Args:
        session_id: Session UUID
        
    Returns:
        Session data dict or None
    """
    from app.db.base import get_db_context
    from app.db.models import ResearchSession
    
    async with get_db_context() as db:
        result = await db.execute(
            select(ResearchSession).where(ResearchSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        
        if session:
            return {
                "id": str(session.id),
                "user_id": str(session.user_id) if session.user_id else None,
                "research_brief": session.research_brief,
                "status": session.status,
                "phase": session.phase,
                "plan": session.plan,
                "plan_version": session.plan_version,
                "current_step_index": session.current_step_index,
                "research_results": session.research_results,
                "analysis_results": session.analysis_results,
                "final_report": session.final_report,
                "compaction_version": session.compaction_version,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "updated_at": session.updated_at.isoformat() if session.updated_at else None,
                "completed_at": session.completed_at.isoformat() if session.completed_at else None,
            }
        return None

"""
Streaming service for orchestrator agent events.

Broadcasts real-time updates from the orchestrator's LangGraph execution
to the frontend via SSE (Server-Sent Events).

Events include:
- session_created: New research session initialized
- phase_transition: Orchestrator moved to a new phase (plan, research, etc.)
- plan_updated: Research plan generated or revised
- step_started/step_completed: Execution of a specific plan step
- research_result: New research finding/article found
- report_chunk: Segment of the markdown report being generated
- synthesis_started/completed: Final synthesis progress
- session_completed: Full pipeline finished
"""

from __future__ import annotations

import json
import uuid
import asyncio
from datetime import datetime
from typing import Any, AsyncGenerator, Optional

from app.agents.orchestrator.agent import OrchestratorAgent
from app.core.logging import get_logger
from app.core.research_brief import derive_session_title


logger = get_logger(__name__)

# SSE comment sent periodically to keep the connection alive
_KEEPALIVE = ": keepalive\n\n"
_KEEPALIVE_INTERVAL = 15.0  # seconds between keepalives


async def _finalize_session(
    session_uuid: uuid.UUID,
    status: str,
    *,
    final_report: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    """Unconditionally mark a session as completed or failed in the DB.

    Called by the streaming service at the very end of every run so the
    status is always accurate, even when the synthesizer node crashes.
    """
    try:
        from sqlalchemy import select
        from app.db.base import get_db_context
        from app.db.models import ResearchSession as _RS

        async with get_db_context() as db:
            result = await db.execute(select(_RS).where(_RS.id == session_uuid))
            session = result.scalar_one_or_none()
            if session is None:
                return
            session.status = status
            session.phase = status  # "completed" or "failed"
            session.updated_at = datetime.now()
            if status == "completed":
                session.completed_at = datetime.now()
                if final_report:
                    session.final_report = final_report
            if error:
                session.meta_data = {**(session.meta_data or {}), "last_error": str(error)[:500]}
            await db.commit()
            logger.info("Session %s finalized as %s", session_uuid, status)
    except Exception as exc:
        logger.warning("Could not finalize session %s: %s", session_uuid, exc)


async def cleanup_stale_running_sessions(max_age_hours: int = 3) -> int:
    """Mark sessions stuck in 'running' state for too long as 'failed'.

    Called at startup so orphaned sessions (from crashes/deploys) don't
    pollute the 'En cours' filter forever.
    Returns the number of sessions cleaned up.
    """
    try:
        from sqlalchemy import select, update
        from app.db.base import get_db_context
        from app.db.models import ResearchSession as _RS
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(hours=max_age_hours)

        async with get_db_context() as db:
            result = await db.execute(
                select(_RS).where(
                    _RS.status == "running",
                    _RS.created_at < cutoff,
                )
            )
            stale = result.scalars().all()
            for s in stale:
                s.status = "failed"
                s.phase = "failed"
                meta = s.meta_data or {}
                meta["last_error"] = f"Session timed out after {max_age_hours}h (auto-cleanup)"
                s.meta_data = meta
                s.updated_at = datetime.now()
            if stale:
                await db.commit()
                logger.info("Cleaned up %d stale running sessions", len(stale))
            return len(stale)
    except Exception as exc:
        logger.warning("Stale session cleanup failed: %s", exc)
        return 0


class StreamingOrchestratorService:
    """Service to run orchestrator and stream events in real-time."""

    def __init__(self, agent: Optional[OrchestratorAgent] = None) -> None:
        self.agent = agent or OrchestratorAgent()

    async def stream_run(
        self,
        task: str,
        topics: Optional[list[str]] = None,
        session_id: Optional[str] = None,
        autonomous: bool = True,
        subject: Optional[str] = None,
        title: Optional[str] = None,
        research_instructions: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Run the orchestrator and yield SSE-formatted events.

        Uses a producer/consumer queue so keepalive comments can be
        interleaved while the LLM is thinking (preventing browser timeout).
        """
        session_uuid = uuid.UUID(session_id) if session_id else uuid.uuid4()
        session_id = str(session_uuid)

        # Create DB record immediately so the session appears in the list as "running"
        # and persistence nodes (save_phase, update_session) find a row to update.
        try:
            from sqlalchemy import select
            from app.db.base import get_db_context
            from app.db.models import ResearchSession as _RS
            from app.services.session_manager import create_session as _create_session
            async with get_db_context() as db:
                existing = (await db.execute(select(_RS).where(_RS.id == session_uuid))).scalar_one_or_none()
            if existing is None:
                await _create_session(task=task, topics=topics, session_id=session_uuid, meta_data={"title": derive_session_title(title=title, subject=subject, task=task), "subject": subject or derive_session_title(task=task), "research_instructions": research_instructions})
        except Exception as exc:
            logger.warning("Could not pre-create session record: %s", exc)

        await self.agent.setup()

        # Auto-fetch memory context
        memory_info = ""
        try:
            from app.tools.memory.search_memory import SearchMemoryTool
            memory_tool = SearchMemoryTool()
            memory_result = await memory_tool.execute({"query": task, "top_k": 5})
            if memory_result.get("success"):
                memory_context = memory_result.get("data", {})
                recent = memory_context.get("results", []) or memory_context.get("recent_articles", [])
                if recent:
                    memory_info = f"\n\nContext from memory ({len(recent)} recent articles):\n"
                    memory_info += "\n".join([
                        f"- {a.get('title', 'Unknown')}: {a.get('summary', '')[:200]}..."
                        for a in recent[:3]
                    ])
        except Exception as exc:
            logger.warning("Streaming memory search failed: %s", exc)

        full_task = task + memory_info if memory_info else task

        initial_state = {
            "session_id": session_id,
            "task": full_task,
            "research_brief": task,
            "task_id": f"orch_{session_uuid}",
            "topics": topics or [],
            "send_email": True,
            "metadata": {"topics": topics or [], "subject": subject, "research_instructions": research_instructions, "title": derive_session_title(title=title, subject=subject, task=task)},
            "plan": [],
            "current_step_index": 0,
            "articles": [],
            "research_results": [],
            "analysis_results": "",
            "synthesis_result": "",
            "final_report": "",
            "email_sent": False,
            "errors": [],
            "iteration_count": 0,
            "max_iterations": 5,
            "autonomous": autonomous,
        }

        # Yield the first event synchronously before entering the queue loop
        yield self._format_sse("session_created", {
            "session_id": session_id,
            "task": task,
            "timestamp": datetime.now().isoformat()
        })

        # Queue: producer fills it, consumer yields to client with keepalives
        queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=200)

        async def _produce() -> None:
            _SKIP_NAMES = {"LangGraph", "_route_after_planner", "__start__", "__end__"}
            final_state: dict[str, Any] = {}
            try:
                async for event in self.agent._graph.astream_events(
                    initial_state,
                    version="v1",
                    config={"configurable": {"thread_id": session_id}}
                ):
                    kind = event["event"]
                    name = event["name"]
                    msg: str | None = None

                    if kind == "on_chain_start" and name == "LangGraph":
                        msg = self._format_sse("phase_transition", {"phase": "initializing"})

                    elif kind == "on_chain_start" and name not in _SKIP_NAMES:
                        msg = self._format_sse("phase_transition", {
                            "phase": name,
                            "status": "started",
                            "timestamp": datetime.now().isoformat()
                        })

                    elif kind == "on_chain_end" and name not in _SKIP_NAMES:
                        output = event.get("data", {}).get("output", {})
                        if not isinstance(output, dict):
                            output = {}
                        else:
                            final_state.update(output)

                        if "plan" in output and output["plan"]:
                            await queue.put(self._format_sse("plan_updated", {
                                "plan": output["plan"],
                                "timestamp": datetime.now().isoformat()
                            }))

                        if name in ("dispatcher", "dispatcher_parallel"):
                            results = output.get("research_results") or []
                            # For parallel dispatch, emit one event per step result so
                            # the frontend shows results as they complete. For sequential
                            # dispatcher, results[-1] is the current step.
                            emit_results = results if name == "dispatcher_parallel" else results[-1:]
                            for step_result in emit_results:
                                raw_data = step_result.get("data", [])
                                articles_preview: list[dict] = []
                                if isinstance(raw_data, list):
                                    for item in raw_data[:15]:
                                        if isinstance(item, dict) and item.get("url"):
                                            articles_preview.append({
                                                "title": item.get("title") or item.get("name") or "",
                                                "url": item.get("url", ""),
                                                "source": item.get("source", ""),
                                                "published_date": item.get("published_date") or item.get("date") or "",
                                                "summary": (item.get("summary") or "")[:300],
                                                "relevance_score": item.get("relevance_score"),
                                            })
                                await queue.put(self._format_sse("research_result", {
                                    "step_id": step_result.get("step_id"),
                                    "step_name": step_result.get("step_name", ""),
                                    "tool": step_result.get("tool", ""),
                                    "count": step_result.get("count", 0),
                                    "articles": articles_preview,
                                    "timestamp": datetime.now().isoformat()
                                }))

                        elif name == "synthesizer":
                            report = output.get("final_report", "")
                            if report:
                                chunk_size = 400
                                for i in range(0, len(report), chunk_size):
                                    await queue.put(self._format_sse("report_chunk", {
                                        "chunk": report[i:i + chunk_size],
                                        "timestamp": datetime.now().isoformat()
                                    }))
                                    await asyncio.sleep(0.01)
                                await queue.put(self._format_sse("report_completed", {
                                    "report_length": len(report),
                                    "timestamp": datetime.now().isoformat()
                                }))
                            # Emit updated plan so the synthesis step shows as DONE in sidebar
                            if "plan" in output and output["plan"]:
                                await queue.put(self._format_sse("plan_updated", {
                                    "plan": output["plan"],
                                    "timestamp": datetime.now().isoformat()
                                }))

                    elif kind == "on_custom_event" and name == "report_chunk":
                        msg = self._format_sse("report_chunk", {
                            "chunk": event["data"].get("chunk", ""),
                            "timestamp": datetime.now().isoformat()
                        })

                    if msg:
                        await queue.put(msg)

                final_report = final_state.get("final_report")
                errors = final_state.get("errors")
                if isinstance(final_report, str) and final_report.strip():
                    await _finalize_session(session_uuid, "completed", final_report=final_report)
                    await queue.put(self._format_sse("session_completed", {
                        "session_id": session_id,
                        "status": "completed",
                        "timestamp": datetime.now().isoformat()
                    }))
                else:
                    error_message = "Rapport final non généré"
                    if isinstance(errors, list):
                        for err in reversed(errors):
                            if err:
                                error_message = str(err)
                                break
                    elif errors:
                        error_message = str(errors)

                    await _finalize_session(session_uuid, "failed", error=error_message)
                    await queue.put(self._format_sse("session_failed", {
                        "session_id": session_id,
                        "error": error_message,
                        "timestamp": datetime.now().isoformat()
                    }))

            except Exception as exc:
                logger.error("Streaming orchestrator failed: %s", exc)
                await _finalize_session(session_uuid, "failed", error=str(exc))
                await queue.put(self._format_sse("session_failed", {
                    "session_id": session_id,
                    "error": str(exc),
                    "timestamp": datetime.now().isoformat()
                }))
            finally:
                await queue.put(None)  # sentinel — consumer exits loop

        producer_task = asyncio.create_task(_produce())

        try:
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=_KEEPALIVE_INTERVAL)
                    if item is None:
                        break
                    yield item
                except asyncio.TimeoutError:
                    # No event in the last N seconds — send keepalive comment
                    yield _KEEPALIVE
        finally:
            producer_task.cancel()
            try:
                await producer_task
            except (asyncio.CancelledError, Exception):
                pass

    def _format_sse(self, event_name: str, data: dict) -> str:
        """Format data as an SSE message."""
        return f"event: {event_name}\ndata: {json.dumps(data)}\n\n"

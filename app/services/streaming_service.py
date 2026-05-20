"""
Streaming service for orchestrator agent events.

Broadcats real-time updates from the orchestrator's LangGraph execution
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
from app.agents.orchestrator.state import StepStatus
from app.core.logging import get_logger


logger = get_logger(__name__)


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
    ) -> AsyncGenerator[str, None]:
        """Run the orchestrator and yield SSE-formatted events.

        Args:
            task: Research task
            topics: Optional topic list
            session_id: Optional session ID to resume or track
            autonomous: Whether to run without human intervention

        Yields:
            SSE formatted strings: "event: <name>\ndata: <json>\n\n"
        """
        # 1. Initialize session if not provided
        session_uuid = uuid.UUID(session_id) if session_id else uuid.uuid4()
        session_id = str(session_uuid)

        # 2. Setup agent
        await self.agent.setup()
        
        # 3. Create initial state
        # Note: We duplicate some logic from OrchestratorAgent.execute here 
        # to have full control over the stream.
        
        # Auto-fetch memory context
        memory_context = None
        try:
            from app.tools.memory.search_memory import SearchMemoryTool
            memory_tool = SearchMemoryTool()
            memory_result = await memory_tool.execute({"query": task, "top_k": 5})
            if memory_result.get("success"):
                memory_context = memory_result.get("data", {})
        except Exception as exc:
            logger.warning("Streaming memory search failed: %s", exc)

        memory_info = ""
        if memory_context:
            recent = memory_context.get("results", []) or memory_context.get("recent_articles", [])
            if recent:
                memory_info = f"\n\nContext from memory ({len(recent)} recent articles):\n"
                memory_info += "\n".join([
                    f"- {a.get('title', 'Unknown')}: {a.get('summary', '')[:200]}..."
                    for a in recent[:3]
                ])
        
        full_task = task + memory_info if memory_info else task

        initial_state = {
            "session_id": session_id,
            "task": full_task,
            "research_brief": task,
            "task_id": f"orch_{session_uuid}",
            "topics": topics or [],
            "send_email": True,
            "metadata": {"topics": topics or []},
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

        # Yield session created event
        yield self._format_sse("session_created", {
            "session_id": session_id,
            "task": task,
            "timestamp": datetime.now().isoformat()
        })

        try:
            # 4. Stream graph execution
            # We use astream_events to catch node transitions and tool outputs
            async for event in self.agent._graph.astream_events(
                initial_state, 
                version="v1",
                config={"configurable": {"thread_id": session_id}}
            ):
                kind = event["event"]
                name = event["name"]
                
                # a) Node transitions (Phases)
                if kind == "on_chain_start" and name == "LangGraph":
                    yield self._format_sse("phase_transition", {"phase": "initializing"})
                
                elif kind == "on_node_start":
                    yield self._format_sse("phase_transition", {
                        "phase": name,
                        "status": "started",
                        "timestamp": datetime.now().isoformat()
                    })
                
                elif kind == "on_node_end":
                    # Extract interesting data from state update
                    output = event.get("data", {}).get("output", {})
                    
                    if name == "planner" and "plan" in output:
                        yield self._format_sse("plan_updated", {
                            "plan": output["plan"],
                            "timestamp": datetime.now().isoformat()
                        })
                    
                    elif name == "dispatcher" or name == "dispatcher_parallel":
                        if "research_results" in output and output["research_results"]:
                            latest = output["research_results"][-1]
                            yield self._format_sse("research_result", {
                                "step_id": latest.get("step_id"),
                                "tool": latest.get("tool"),
                                "count": latest.get("count"),
                                "timestamp": datetime.now().isoformat()
                            })
                    
                    elif name == "synthesizer" and "final_report" in output:
                        yield self._format_sse("report_completed", {
                            "report_length": len(output["final_report"]),
                            "timestamp": datetime.now().isoformat()
                        })

                elif kind == "on_custom_event":
                    if name == "report_chunk":
                        yield self._format_sse("report_chunk", {
                            "chunk": event["data"].get("chunk", ""),
                            "timestamp": datetime.now().isoformat()
                        })

                # c) Tool execution
                elif kind == "on_tool_start":
                    yield self._format_sse("step_started", {
                        "tool": name,
                        "timestamp": datetime.now().isoformat()
                    })
                
                elif kind == "on_tool_end":
                    yield self._format_sse("step_completed", {
                        "tool": name,
                        "success": True, # Assume success if no error in event
                        "timestamp": datetime.now().isoformat()
                    })

            # 5. Final event
            yield self._format_sse("session_completed", {
                "session_id": session_id,
                "status": "completed",
                "timestamp": datetime.now().isoformat()
            })

        except Exception as exc:
            logger.error("Streaming orchestrator failed: %s", exc)
            yield self._format_sse("session_failed", {
                "session_id": session_id,
                "error": str(exc),
                "timestamp": datetime.now().isoformat()
            })

    def _format_sse(self, event_name: str, data: dict) -> str:
        """Format data as an SSE message."""
        return f"event: {event_name}\ndata: {json.dumps(data)}\n\n"

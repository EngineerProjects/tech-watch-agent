"""
Orchestrator agent implementation.

This is the main orchestrator agent that coordinates all other agents
and tools to complete research tasks end-to-end.

Features:
- LangGraph StateGraph workflow with conditional routing
- Checkpointing support (memory + PostgreSQL)
- Retry policies with exponential backoff
- Fallback chains for tool failures
- Human-in-the-loop approval checkpoints (optional)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
import uuid

from app.agents.base.base_agent import BaseAgent, AgentConfig, AgentResult
from app.agents.orchestrator.config import OrchestratorConfig
from app.agents.orchestrator.graph import OrchestratorGraphBuilder
from app.agents.orchestrator.state import OrchestratorState
from app.agents.orchestrator.nodes import OrchestratorNodes
from app.config.settings import Settings, get_settings
from app.core.logging import get_logger
from app.core.research_brief import build_research_brief, derive_session_title


logger = get_logger(__name__)


class OrchestratorAgent(BaseAgent):
    """Main orchestrator agent for comprehensive tech research.

    This agent coordinates the full pipeline:
    1. Planning - Generate execution plan from task
    2. Research - Parallel tool dispatch (web, social, papers)
    3. Collection - Aggregate all results
    4. Validation - Ensure quality thresholds met
    5. Analysis - Extract key insights
    6. Synthesis - Create final report
    7. Delivery - Send email

    Uses LangGraph StateGraph with supervisor pattern.
    Falls back to legacy NewsletterOrchestrator for V1 compatibility.

    Features:
        - Checkpointing for state persistence (memory/postgres)
        - Retry policies with exponential backoff
        - Fallback chains for tool failures
        - Human-in-the-loop approval checkpoints (optional)
    """

    def __init__(
        self,
        config: Optional[OrchestratorConfig] = None,
        settings: Optional[Settings] = None,
        nodes: Optional[OrchestratorNodes] = None,
    ) -> None:
        if config is None:
            config = OrchestratorConfig()

        super().__init__(config=config, settings=settings)

        self._nodes = nodes
        self._graph = None
        self._config = config

    @property
    def name(self) -> str:
        return "orchestrator"

    @property
    def description(self) -> str:
        return "Main orchestrator that plans, coordinates research, and delivers reports"

    async def setup(self) -> None:
        """Set up agent resources."""
        logger.info("Setting up orchestrator agent")

        if self._nodes is None:
            self._nodes = OrchestratorNodes(
                max_articles=5,
                min_sources=2,
                enable_session_persistence=self._config.enable_session_persistence,
            )

        graph_builder = OrchestratorGraphBuilder(
            nodes=self._nodes,
            enable_checkpointing=self._config.enable_checkpointing,
            checkpoint_backend=self._config.checkpoint_backend,
        )
        self._graph = graph_builder.build()

        logger.info("Orchestrator agent setup complete")

    async def execute(
        self,
        input_data: Any,
        session_id: Optional[str] = None,
        memory_context: Optional[dict[str, Any]] = None,
    ) -> AgentResult:
        """Execute the orchestrator pipeline.

        Args:
            input_data: Can be:
                - str: The research task
                - dict: {"task": str, "topics": list[str], "send_email": bool}
            session_id: Optional session ID for memory tracking
            memory_context: Optional pre-loaded memory context for RAG

        Returns:
            AgentResult with final_report, email_sent status, and metadata
        """
        start_time = datetime.now()

        subject: Optional[str] = None
        research_instructions: Optional[str] = None
        title: Optional[str] = None

        if isinstance(input_data, str):
            task = input_data
            topics: Optional[list[str]] = None
            send_email = True
            autonomous = self._config.autonomous
        elif isinstance(input_data, dict):
            subject = input_data.get("subject") or None
            research_instructions = input_data.get("research_instructions") or None
            title = input_data.get("title") or None
            task = input_data.get("task", str(input_data))
            topics = input_data.get("topics")
            send_email = input_data.get("send_email", True)
            autonomous = input_data.get("autonomous", self._config.autonomous)
            if subject:
                task = build_research_brief(subject, topics, research_instructions)
            if session_id is None:
                session_id = input_data.get("session_id")
            if memory_context is None:
                memory_context = input_data.get("memory_context")
        else:
            task = str(input_data)
            topics = None
            send_email = True
            autonomous = self._config.autonomous

        logger.info("Orchestrator starting task: %s", task[:100])

        session_uuid: Optional[uuid.UUID] = None
        if session_id:
            try:
                session_uuid = uuid.UUID(session_id)
            except ValueError:
                logger.warning("Invalid session_id '%s', creating a new session", session_id)

        if session_uuid is None:
            from app.services.session_manager import create_session as create_research_session

            session_uuid = await create_research_session(
                task=task,
                topics=topics,
                meta_data={
                    "title": derive_session_title(title=title, subject=subject, task=task),
                    "subject": subject or derive_session_title(task=task),
                    "research_instructions": research_instructions,
                },
            )
            session_id = str(session_uuid)

        if self._nodes is not None:
            self._nodes._session_id = str(session_uuid)
            self._nodes._session_manager = None

        # --- Memory context integration ---
        if memory_context is None:
            try:
                from app.tools.memory.search_memory import SearchMemoryTool
                memory_tool = SearchMemoryTool()
                logger.info("Fetching memory context for task: %s", task[:50])
                memory_result = await memory_tool.execute({"query": task, "top_k": 5})
                if memory_result.get("success"):
                    memory_context = memory_result.get("data", {})
                    logger.info("Found %d relevant articles in memory", memory_context.get("count", 0))
            except Exception as exc:
                logger.warning("Auto memory search failed: %s", exc)

        memory_info = ""
        if memory_context:
            recent = memory_context.get("results", []) or memory_context.get("recent_articles", [])
            if recent:
                memory_info = f"\n\nContext from memory ({len(recent)} recent articles):\n"
                memory_info += "\n".join([
                    f"- {a.get('title', 'Unknown')}: {a.get('summary', '')[:200]}..."
                    for a in recent[:3]
                ])

        if memory_info:
            task = task + memory_info
        # --- End memory context integration ---

        try:
            await self.setup()

            result_state = await self._graph.ainvoke({
                "session_id": str(session_uuid),
                "task": task,
                "research_brief": task,
                "task_id": f"orch_{session_uuid}",
                "topics": topics or [],
                "send_email": send_email,
                "metadata": {"topics": topics or [], "subject": subject, "research_instructions": research_instructions, "title": derive_session_title(title=title, subject=subject, task=task)},
                "plan": [],
                "current_step_index": 0,
                "articles": [],
                "research_results": [],
                "analysis_results": "",
                "synthesis_result": "",
                "final_report": "",
                "email_sent": False,
                "email_result": None,
                "validation_errors": [],
                "quality_score": 0.0,
                "iteration_count": 0,
                "max_iterations": self._config.max_iterations,
                "approval_status": "",
                "approval_result": "",
                "approved_at": None,
                "errors": [],
                "started_at": None,
                "completed_at": None,
                "approval_threshold": self._config.approval_threshold,
                "autonomous": autonomous,
                "plan_attempts": 0,
                "max_plan_retries": 3,
                "resumed_from_checkpoint": False,
            })

            execution_time = (datetime.now() - start_time).total_seconds()

            report = result_state.get("final_report", "")
            email_sent = result_state.get("email_sent", False)
            email_result = result_state.get("email_result")
            errors = result_state.get("errors", [])
            research_count = len(result_state.get("research_results", []))
            plan_steps = len(result_state.get("plan", []))

            metadata = {
                "task": task[:200],
                "plan_steps": plan_steps,
                "research_results": research_count,
                "email_sent": email_sent,
                "email_result": email_result,
                "execution_time_seconds": execution_time,
                "iteration_count": result_state.get("iteration_count", 0),
                "validation_errors": result_state.get("validation_errors", []),
                "session_id": str(session_uuid),
            }

            if not report:
                logger.error("Orchestrator produced no report")
                return AgentResult.create_error(
                    errors=errors if errors else ["No report generated"],
                    metadata=metadata,
                )

            logger.info(
                "Orchestrator completed: %d steps, %d results, email=%s (%.1fs)",
                plan_steps, research_count, email_sent, execution_time,
            )

            return AgentResult.create_success(
                output={
                    "session_id": str(session_uuid),
                    "report": report,
                    "email_sent": email_sent,
                    "email_result": email_result,
                    "research_results": result_state.get("research_results", []),
                    "plan": result_state.get("plan", []),
                },
                metadata=metadata,
                session_id=session_uuid,
            )

        except Exception as exc:
            logger.error("Orchestrator execution failed: %s", exc)
            execution_time = (datetime.now() - start_time).total_seconds()
            return AgentResult.create_error(
                errors=[str(exc)],
                metadata={
                    "task": task[:200],
                    "execution_time_seconds": execution_time,
                    "session_id": str(session_uuid) if session_uuid else None,
                },
            )

    async def cleanup(self) -> None:
        """Clean up agent resources."""
        logger.info("Orchestrator agent cleanup complete")


def create_orchestrator_agent(
    config: Optional[OrchestratorConfig] = None,
    settings: Optional[Settings] = None,
) -> OrchestratorAgent:
    """Factory function to create an orchestrator agent."""
    return OrchestratorAgent(config=config, settings=settings)

"""
Orchestrator LangGraph workflow definition.

Defines the graph structure for the orchestrator agent:
supervisor -> planner -> dispatcher (x N) -> collector -> validator
                                                        |
                                                        v
                              synthesizer -> emailer -> END

Conditional routing handles:
- Plan not generated -> back to planner
- Validation failed -> retry dispatcher (up to max_iterations)
- All steps done -> collector
- Report generated -> emailer
- Human approval checkpoints (optional)

Features:
- Retry policies for resilient node execution
- Checkpointing support (memory + PostgreSQL)
- Human-in-the-loop approval checkpoints (optional)
- Fallback chains for tool failures
"""

from __future__ import annotations

from typing import Any, Literal, Optional, TypedDict

from langgraph.graph import END, StateGraph

from app.agents.orchestrator.state import OrchestratorState, StepStatus
from app.agents.orchestrator.nodes import OrchestratorNodes
from app.core.logging import get_logger


logger = get_logger(__name__)


class RetryPolicy(TypedDict, total=False):
    """Retry policy configuration for nodes."""

    max_attempts: int
    initial_interval: float
    backoff_factor: float
    max_interval: float


DEFAULT_RETRY_POLICY: RetryPolicy = {
    "max_attempts": 3,
    "initial_interval": 1.0,
    "backoff_factor": 2.0,
    "max_interval": 60.0,
}


class OrchestratorGraphBuilder:
    """Builder for the orchestrator workflow graph."""

    def __init__(
        self,
        nodes: Optional[OrchestratorNodes] = None,
        enable_checkpointing: bool = False,
        checkpoint_backend: Literal["memory", "postgres"] = "memory",
    ) -> None:
        self.nodes = nodes or OrchestratorNodes()
        self._enable_checkpointing = enable_checkpointing
        self._checkpoint_backend = checkpoint_backend
        self._checkpointer = None

    def _get_checkpointer(self):
        """Get or create the checkpointer based on configuration."""
        if self._checkpointer is not None:
            return self._checkpointer

        if not self._enable_checkpointing:
            return None

        if self._checkpoint_backend == "memory":
            try:
                from langgraph.checkpoint.memory import MemorySaver
                self._checkpointer = MemorySaver()
                logger.info("Using MemorySaver checkpointer")
            except ImportError:
                logger.warning("MemorySaver not available")
                return None
        elif self._checkpoint_backend == "postgres":
            try:
                from langgraph.checkpoint.postgres import PostgresSaver
                from app.config.settings import get_settings
                settings = get_settings()
                if settings.database_sync_url:
                    self._checkpointer = PostgresSaver.from_conn_string(
                        settings.database_sync_url
                    )
                    logger.info("Using PostgresSaver checkpointer")
                else:
                    logger.warning("No database_sync_url configured for PostgresSaver")
                    return None
            except ImportError:
                logger.warning("PostgresSaver not available")
                return None

        return self._checkpointer

    def build(self) -> StateGraph:
        workflow = StateGraph(OrchestratorState)

        workflow.add_node("supervisor", self.nodes.supervisor)
        workflow.add_node("planner", self.nodes.planner)
        workflow.add_node("dispatcher", self.nodes.dispatcher)
        workflow.add_node("dispatcher_parallel", self.nodes.dispatcher_parallel)
        workflow.add_node("collector", self.nodes.collector)
        workflow.add_node("validator", self.nodes.validator)
        workflow.add_node("human_approval", self.nodes.human_approval)
        workflow.add_node("analyzer", self.nodes.analyzer)
        workflow.add_node("synthesizer", self.nodes.synthesizer)
        workflow.add_node("emailer", self.nodes.emailer)

        workflow.set_entry_point("supervisor")

        workflow.add_edge("supervisor", "planner")

        # After planning, try parallel dispatch first
        workflow.add_edge("planner", "dispatcher_parallel")

        # dispatcher_parallel handles all pending research steps then goes to collector
        workflow.add_edge("dispatcher_parallel", "collector")

        # dispatcher node handles one step at a time, then decides what to do next
        workflow.add_conditional_edges(
            "dispatcher",
            self._route_after_dispatcher,
            {
                "continue": "dispatcher",
                "collect": "collector",
            }
        )

        workflow.add_edge("collector", "validator")

        workflow.add_conditional_edges(
            "validator",
            self._route_after_validation,
            {
                "retry": "dispatcher",
                "approval": "human_approval",
            }
        )

        workflow.add_conditional_edges(
            "human_approval",
            self._route_after_approval,
            {
                "proceed": "analyzer",
                "retry": "dispatcher",
            }
        )

        workflow.add_edge("analyzer", "synthesizer")
        workflow.add_edge("synthesizer", "emailer")
        workflow.add_edge("emailer", END)

        checkpointer = self._get_checkpointer()
        return workflow.compile(checkpointer=checkpointer)

    def _route_after_dispatcher(self, state: OrchestratorState) -> Literal["continue", "collect"]:
        """Route after sequential dispatcher: continue to next step or go to collector."""
        plan = state.get("plan", [])
        current_idx = state.get("current_step_index", 0)
        
        if current_idx < len(plan):
            return "continue"
        return "collect"

    def _route_after_validation(self, state: OrchestratorState) -> Literal["retry", "approval"]:
        errors = state.get("validation_errors", [])
        iteration = state.get("iteration_count", 0)
        max_iter = state.get("max_iterations", 5)

        if errors and iteration < max_iter:
            return "retry"
        return "approval"

    def _route_after_approval(self, state: OrchestratorState) -> Literal["proceed", "retry"]:
        approval_result = state.get("approval_result", "pending")
        if approval_result == "approved":
            return "proceed"
        return "retry"


class OrchestratorWorkflow:
    """Main orchestrator workflow class.

    Coordinates the full research pipeline:
    1. Plan generation
    2. Parallel research dispatch
    3. Result collection and validation
    4. Analysis and synthesis
    5. Email delivery
    """

    def __init__(self, nodes: Optional[OrchestratorNodes] = None, checkpointer=None) -> None:
        self.nodes = nodes or OrchestratorNodes()
        self.graph_builder = OrchestratorGraphBuilder(nodes=self.nodes)
        self._graph = self.graph_builder.build(checkpointer=checkpointer)

    def run(self, task: str, topics: Optional[list[str]] = None) -> OrchestratorState:
        """Execute the orchestrator workflow.

        Args:
            task: The research task description
            topics: Optional list of topics to focus on

        Returns:
            OrchestratorState with results from all stages
        """
        initial_state: OrchestratorState = {
            "task": task,
            "task_id": f"orch_{id(task)}",
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
            "iteration_count": 0,
            "max_iterations": 5,
            "errors": [],
            "started_at": None,
            "completed_at": None,
        }

        if topics:
            initial_state["task"] = f"{task} (topics: {', '.join(topics)})"

        result = self._graph.invoke(initial_state)
        logger.info("Orchestrator workflow completed")
        return result

    async def run_async(self, task: str, topics: Optional[list[str]] = None, task_id: Optional[str] = None) -> OrchestratorState:
        """Async execution of the orchestrator workflow."""
        initial_state: OrchestratorState = {
            "task": task,
            "task_id": task_id or f"orch_{id(task)}",
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
            "iteration_count": 0,
            "max_iterations": 5,
            "errors": [],
            "started_at": None,
            "completed_at": None,
        }

        if topics:
            initial_state["task"] = f"{task} (topics: {', '.join(topics)})"

        result = await self._graph.ainvoke(initial_state)
        logger.info("Orchestrator workflow completed")
        return result


def create_orchestrator_workflow(
    nodes: Optional[OrchestratorNodes] = None,
    checkpointer=None,
) -> OrchestratorWorkflow:
    """Factory function to create an orchestrator workflow."""
    return OrchestratorWorkflow(nodes=nodes, checkpointer=checkpointer)
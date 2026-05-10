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
"""

from __future__ import annotations

from typing import Literal, Optional

from langgraph.graph import END, StateGraph

from app.agents.orchestrator.state import OrchestratorState, StepStatus
from app.agents.orchestrator.nodes import OrchestratorNodes
from app.core.logging import get_logger


logger = get_logger(__name__)


class OrchestratorGraphBuilder:
    """Builder for the orchestrator workflow graph."""

    def __init__(self, nodes: Optional[OrchestratorNodes] = None) -> None:
        self.nodes = nodes or OrchestratorNodes()

    def build(self) -> StateGraph:
        workflow = StateGraph(OrchestratorState)

        workflow.add_node("supervisor", self.nodes.supervisor)
        workflow.add_node("planner", self.nodes.planner)
        workflow.add_node("dispatcher", self.nodes.dispatcher)
        workflow.add_node("dispatcher_parallel", self.nodes.dispatcher_parallel)
        workflow.add_node("collector", self.nodes.collector)
        workflow.add_node("validator", self.nodes.validator)
        workflow.add_node("analyzer", self.nodes.analyzer)
        workflow.add_node("synthesizer", self.nodes.synthesizer)
        workflow.add_node("emailer", self.nodes.emailer)

        workflow.set_entry_point("supervisor")

        workflow.add_edge("supervisor", "planner")

        workflow.add_edge("planner", "dispatcher_parallel")

        workflow.add_edge("dispatcher", "dispatcher")
        workflow.add_edge("dispatcher_parallel", "collector")

        workflow.add_edge("collector", "validator")

        workflow.add_conditional_edges(
            "validator",
            self._route_after_validation,
            {
                "retry": "dispatcher",
                "analyze": "analyzer",
            }
        )

        workflow.add_edge("analyzer", "synthesizer")
        workflow.add_edge("synthesizer", "emailer")
        workflow.add_edge("emailer", END)

        return workflow.compile()

    def _route_after_validation(self, state: OrchestratorState) -> Literal["retry", "analyze"]:
        errors = state.get("validation_errors", [])
        iteration = state.get("iteration_count", 0)
        max_iter = state.get("max_iterations", 5)

        if errors and iteration < max_iter:
            return "retry"
        return "analyze"


class OrchestratorWorkflow:
    """Main orchestrator workflow class.

    Coordinates the full research pipeline:
    1. Plan generation
    2. Parallel research dispatch
    3. Result collection and validation
    4. Analysis and synthesis
    5. Email delivery
    """

    def __init__(self, nodes: Optional[OrchestratorNodes] = None) -> None:
        self.nodes = nodes or OrchestratorNodes()
        self.graph_builder = OrchestratorGraphBuilder(nodes=self.nodes)
        self._graph = self.graph_builder.build()

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

    async def run_async(self, task: str, topics: Optional[list[str]] = None) -> OrchestratorState:
        """Async version of run()."""
        import asyncio
        return await asyncio.to_thread(self.run, task, topics)


def create_orchestrator_workflow(
    nodes: Optional[OrchestratorNodes] = None,
) -> OrchestratorWorkflow:
    """Factory function to create an orchestrator workflow."""
    return OrchestratorWorkflow(nodes=nodes)
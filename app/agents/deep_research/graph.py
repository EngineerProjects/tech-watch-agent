"""
LangGraph workflow definition for the deep research agent.

This module defines the LangGraph workflow that orchestrates the
deep research process. It combines multiple subgraphs (supervisor,
researcher) into a coherent pipeline.

Architecture:
- Main graph handles entry point and final report
- Supervisor subgraph manages research delegation
- Researcher subgraph conducts individual research
"""

from typing import Optional

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.deep_research.state import (
    DeepResearchAgentState,
    SupervisorState,
    ResearcherState,
    ResearcherOutputState,
)
from app.agents.deep_research.nodes import DeepResearchNodes
from app.agents.deep_research.config import DeepResearchConfig
from app.core.logging import get_logger


logger = get_logger(__name__)


class DeepResearchGraphBuilder:
    """Builder for constructing the deep research workflow.

    This class provides a fluent interface for building the deep
    research workflow with customizable nodes and edges.

    Usage:
        builder = DeepResearchGraphBuilder()
        builder.with_config(my_config)
        graph = builder.build()
    """

    def __init__(
        self,
        config: Optional[DeepResearchConfig] = None,
        nodes: Optional[DeepResearchNodes] = None,
    ) -> None:
        """Initialize the graph builder.

        Args:
            config: Optional configuration
            nodes: Optional pre-configured nodes
        """
        self.config = config or DeepResearchConfig()
        self.nodes = nodes or DeepResearchNodes(config=self.config)

    def build(self, checkpointer=None) -> CompiledStateGraph:
        """Build and compile the complete workflow graph.

        Returns:
            Compiled LangGraph ready for execution
        """
        # Build the main agent graph
        main_graph = StateGraph(
            DeepResearchAgentState,
            config_schema=DeepResearchConfig,
        )

        # Add main workflow nodes
        main_graph.add_node("clarify_with_user", self.nodes.clarify_with_user)
        main_graph.add_node("write_research_brief", self.nodes.write_research_brief)
        main_graph.add_node("research_supervisor", self._build_supervisor_subgraph())
        main_graph.add_node("final_report_generation", self.nodes.final_report_generation)

        # Define main workflow edges
        main_graph.add_edge(START, "clarify_with_user")
        main_graph.add_edge("write_research_brief", "research_supervisor")
        main_graph.add_edge("research_supervisor", "final_report_generation")
        main_graph.add_edge("final_report_generation", END)

        return main_graph.compile(checkpointer=checkpointer)

    def _build_supervisor_subgraph(self) -> CompiledStateGraph:
        """Build the supervisor subgraph.

        The supervisor manages research delegation to sub-agents.
        It implements a loop of planning -> delegating -> assessing.

        Returns:
            Compiled supervisor subgraph
        """
        supervisor_graph = StateGraph(
            SupervisorState,
            config_schema=DeepResearchConfig,
        )

        supervisor_graph.add_node("supervisor", self.nodes.supervisor)
        supervisor_graph.add_node("supervisor_tools", self.nodes.supervisor_tools)

        supervisor_graph.add_edge(START, "supervisor")
        supervisor_graph.add_edge("supervisor_tools", "supervisor")

        return supervisor_graph.compile()

    def get_graph_info(self) -> dict:
        """Get information about the compiled graph.

        Returns:
            Dictionary with graph metadata
        """
        return {
            "name": "deep_research",
            "nodes": ["clarify_with_user", "write_research_brief", "research_supervisor", "final_report_generation"],
            "entry_point": "clarify_with_user",
            "config_schema": "DeepResearchConfig",
        }


class DeepResearchWorkflow:
    """The main deep research workflow.

    This class encapsulates the complete deep research pipeline
    using LangGraph. It coordinates the supervisor, researchers,
    and final report generation.

    Usage:
        workflow = DeepResearchWorkflow()
        result = workflow.run(user_messages=[HumanMessage(content="Research AI trends")])
        print(result["final_report"])
    """

    def __init__(
        self,
        config: Optional[DeepResearchConfig] = None,
        nodes: Optional[DeepResearchNodes] = None,
        checkpointer=None,
    ) -> None:
        """Initialize the workflow.

        Args:
            config: Optional configuration
            nodes: Optional pre-configured nodes
        """
        self.config = config or DeepResearchConfig()
        self.nodes = nodes or DeepResearchNodes(config=self.config)
        self.graph = self._build_graph(checkpointer=checkpointer)

    def _build_graph(self, checkpointer=None) -> CompiledStateGraph:
        """Build the workflow graph.

        Returns:
            Compiled LangGraph
        """
        builder = DeepResearchGraphBuilder(
            config=self.config,
            nodes=self.nodes,
        )
        return builder.build(checkpointer=checkpointer)

    def run(
        self,
        messages: list,
        research_brief: Optional[str] = None,
    ) -> DeepResearchAgentState:
        """Run the deep research workflow.

        Args:
            messages: List of messages (user input)
            research_brief: Optional pre-defined research brief

        Returns:
            The final state with research results
        """
        initial_state: DeepResearchAgentState = {
            "messages": messages,
            "supervisor_messages": [],
            "research_brief": research_brief or "",
            "notes": [],
            "raw_notes": [],
            "final_report": "",
            "metadata": {},
            "errors": [],
        }

        try:
            logger.info("Starting deep research workflow")
            import asyncio
            result = asyncio.get_event_loop().run_until_complete(
                self.graph.ainvoke(
                    initial_state,
                    config={
                        "configurable": {
                            "research_model": self.config.research_model,
                            "compression_model": self.config.compression_model,
                            "final_report_model": self.config.final_report_model,
                            "max_researcher_iterations": self.config.max_researcher_iterations,
                            "max_react_tool_calls": self.config.max_react_tool_calls,
                            "max_concurrent_research_units": self.config.max_concurrent_research_units,
                            "allow_clarification": self.config.allow_clarification,
                            "research_depth": self.config.research_depth,
                        }
                    },
                )
            )
            logger.info("Deep research workflow completed")
            return result

        except Exception as exc:
            logger.error("Deep research workflow failed: %s", exc)
            initial_state["errors"].append(str(exc))
            return initial_state

    async def run_async(
        self,
        messages: list,
        research_brief: Optional[str] = None,
    ) -> DeepResearchAgentState:
        """Async version of run for concurrent execution.

        Args:
            messages: List of messages
            research_brief: Optional pre-defined brief

        Returns:
            The final state with research results
        """
        import asyncio
        return await asyncio.to_thread(self.run, messages, research_brief)

    def get_graph_info(self) -> dict:
        """Get information about the workflow.

        Returns:
            Dictionary with workflow metadata
        """
        return DeepResearchGraphBuilder(
            config=self.config,
            nodes=self.nodes,
        ).get_graph_info()


# Factory function for creating the workflow
def create_deep_research_workflow(
    config: Optional[DeepResearchConfig] = None,
    checkpointer=None,
) -> DeepResearchWorkflow:
    """Create a configured deep research workflow.

    Args:
        config: Optional configuration

    Returns:
        DeepResearchWorkflow instance
    """
    return DeepResearchWorkflow(config=config, checkpointer=checkpointer)
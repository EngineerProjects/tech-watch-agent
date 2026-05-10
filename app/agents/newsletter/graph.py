"""
Newsletter workflow graph definition.

This module defines the LangGraph workflow for newsletter generation.
The workflow is composed of multiple stages (nodes) that process
articles from initial collection to final newsletter composition.

The graph architecture follows a linear pipeline pattern:
researcher -> analyst -> opinion_writer -> editor

Each node processes the current state and passes results to the next stage.
"""

from typing import Optional

from langgraph.graph import END, StateGraph

from app.agents.base.agent_state import AgentState
from app.agents.newsletter.nodes import NewsletterNodes
from app.agents.newsletter.state import NewsletterState
from app.core.logging import get_logger
from app.core.models import Article


logger = get_logger(__name__)


class NewsletterGraphBuilder:
    """Builder class for constructing the newsletter workflow graph.

    This class provides a fluent interface for configuring and building
    the newsletter generation workflow. It allows customization of nodes,
    edges, and conditional routing.

    Usage:
        builder = NewsletterGraphBuilder()
        builder.add_custom_node("preprocessor", preprocess_articles)
        graph = builder.build()

        result = graph.invoke(initial_state)
    """

    def __init__(self, nodes: Optional[NewsletterNodes] = None) -> None:
        """Initialize the graph builder.

        Args:
            nodes: Optional nodes instance (creates new if not provided)
        """
        self.nodes = nodes or NewsletterNodes()
        self._custom_nodes: dict[str, callable] = {}
        self._entry_point: str = "researcher"
        self._edges: list[tuple[str, str]] = []

    def add_node(self, name: str, handler: callable) -> "NewsletterGraphBuilder":
        """Add a custom node to the graph.

        Args:
            name: Node name
            handler: Node handler function

        Returns:
            Self for chaining
        """
        self._custom_nodes[name] = handler
        return self

    def set_entry_point(self, name: str) -> "NewsletterGraphBuilder":
        """Set the entry point node.

        Args:
            name: Node name to start from

        Returns:
            Self for chaining
        """
        self._entry_point = name
        return self

    def add_edge(self, from_node: str, to_node: str) -> "NewsletterGraphBuilder":
        """Add an edge between nodes.

        Args:
            from_node: Source node name
            to_node: Target node name

        Returns:
            Self for chaining
        """
        self._edges.append((from_node, to_node))
        return self

    def build(self) -> StateGraph:
        """Build and compile the workflow graph.

        Returns:
            Compiled StateGraph ready for execution
        """
        workflow = StateGraph(NewsletterState)

        # Add default nodes
        workflow.add_node("researcher", self.nodes.researcher)
        workflow.add_node("analyst", self.nodes.analyst)
        workflow.add_node("opinion_writer", self.nodes.opinion_writer)
        workflow.add_node("editor", self.nodes.editor)

        # Add custom nodes
        for name, handler in self._custom_nodes.items():
            workflow.add_node(name, handler)

        # Set entry point
        workflow.set_entry_point(self._entry_point)

        # Add default edges
        workflow.add_edge("researcher", "analyst")
        workflow.add_edge("analyst", "opinion_writer")
        workflow.add_edge("opinion_writer", "editor")
        workflow.add_edge("editor", END)

        # Add custom edges
        for from_node, to_node in self._edges:
            workflow.add_edge(from_node, to_node)

        return workflow.compile()


class NewsletterWorkflow:
    """The main newsletter generation workflow.

    This class encapsulates the newsletter generation pipeline using LangGraph.
    It coordinates the execution of multiple agent nodes that transform
    raw articles into a polished newsletter.

    The workflow follows these stages:
    1. Researcher - Analyzes and summarizes collected articles
    2. Analyst - Extracts key insights and trends
    3. Opinion Writer - Provides commentary and analysis
    4. Editor - Composes the final newsletter

    Attributes:
        nodes: The newsletter agent nodes
        graph: The compiled LangGraph
    """

    def __init__(self, nodes: Optional[NewsletterNodes] = None) -> None:
        """Initialize the newsletter workflow.

        Args:
            nodes: Optional nodes instance (creates new if not provided)
        """
        self.nodes = nodes or NewsletterNodes()
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the workflow graph.

        Creates a StateGraph with the newsletter generation pipeline.
        The graph mirrors newsletter-agent's linear flow, but with isolated
        nodes that can be customized or extended for deep-research variants.

        Returns:
            Compiled StateGraph
        """
        # Use the builder for cleaner graph construction
        builder = NewsletterGraphBuilder(nodes=self.nodes)
        return builder.build()

    def run(self, articles: list[Article]) -> NewsletterState:
        """Execute the newsletter generation workflow.

        Takes a list of articles and processes them through the full
        pipeline to generate a newsletter.

        Args:
            articles: List of Article objects to process

        Returns:
            NewsletterState with the generated newsletter and metadata
        """
        # Initialize state from articles
        initial_state: NewsletterState = {
            "raw_articles": [article.to_dict() for article in articles],
            "research_summary": "",
            "key_insights": "",
            "opinion_analysis": "",
            "final_newsletter": "",
        }

        try:
            logger.info("Starting newsletter workflow with %d articles", len(articles))
            result = self.graph.invoke(initial_state)
            logger.info("Newsletter workflow completed successfully")
            return result

        except Exception as exc:
            logger.error("Newsletter workflow failed: %s", exc)
            # Return initial state with error indication
            initial_state["error"] = str(exc)
            return initial_state

    async def run_async(self, articles: list[Article]) -> NewsletterState:
        """Async version of run for concurrent execution.

        Args:
            articles: List of Article objects to process

        Returns:
            NewsletterState with the generated newsletter
        """
        import asyncio

        return await asyncio.to_thread(self.run, articles)

    def get_graph_info(self) -> dict:
        """Get information about the compiled graph.

        Returns:
            Dictionary with graph metadata
        """
        return {
            "nodes": list(self.graph.nodes.keys()) if hasattr(self.graph, "nodes") else [],
            "entry_point": "researcher",
        }
from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.agents.newsletter.nodes import NewsletterNodes
from app.agents.newsletter.state import NewsletterState
from app.core.logging import get_logger
from app.core.models import Article


logger = get_logger(__name__)


class NewsletterWorkflow:
    def __init__(self, nodes: NewsletterNodes | None = None) -> None:
        self.nodes = nodes or NewsletterNodes()
        self.graph = self._build_graph()

    def _build_graph(self):
        # The graph mirrors newsletter-agent's linear flow, but the nodes are now
        # isolated so we can later branch into deep-research variants cleanly.
        workflow = StateGraph(NewsletterState)
        workflow.add_node("researcher", self.nodes.researcher)
        workflow.add_node("analyst", self.nodes.analyst)
        workflow.add_node("opinion_writer", self.nodes.opinion_writer)
        workflow.add_node("editor", self.nodes.editor)

        workflow.set_entry_point("researcher")
        workflow.add_edge("researcher", "analyst")
        workflow.add_edge("analyst", "opinion_writer")
        workflow.add_edge("opinion_writer", "editor")
        workflow.add_edge("editor", END)
        return workflow.compile()

    def run(self, articles: list[Article]) -> NewsletterState:
        initial_state: NewsletterState = {
            "raw_articles": [article.to_dict() for article in articles],
            "research_summary": "",
            "key_insights": "",
            "opinion_analysis": "",
            "final_newsletter": "",
        }

        try:
            return self.graph.invoke(initial_state)
        except Exception as exc:
            logger.error("Newsletter workflow failed: %s", exc)
            return initial_state

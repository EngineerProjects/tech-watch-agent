"""
Newsletter agent module.

This module provides the newsletter generation agent that orchestrates
the collection of articles, analysis, and newsletter composition.

The agent follows a multi-stage pipeline:
1. Research - Collect articles from web sources
2. Analysis - Extract key insights and themes
3. Opinion Writing - Analyze trends and provide commentary
4. Editorial - Compose final newsletter
"""

from app.agents.newsletter.graph import NewsletterWorkflow, NewsletterGraphBuilder
from app.agents.newsletter.nodes import NewsletterNodes
from app.agents.newsletter.state import NewsletterState
from app.agents.newsletter.agent import NewsletterAgent

__all__ = [
    "NewsletterWorkflow",
    "NewsletterGraphBuilder",
    "NewsletterNodes",
    "NewsletterState",
    "NewsletterAgent",
]
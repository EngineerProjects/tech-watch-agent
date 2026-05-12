"""
Newsletter agent implementation.

This module provides the NewsletterAgent class that extends BaseAgent
to generate newsletters from collected articles. It coordinates the
workflow of collecting articles, analyzing them, and composing the final
newsletter content.

The agent uses LangGraph for workflow orchestration with multiple stages:
- Article collection from various sources
- Research and summarization
- Key insight extraction
- Opinion analysis
- Final newsletter composition
"""

from datetime import datetime
from typing import Any, Optional
from dataclasses import dataclass, field

from app.agents.base.base_agent import BaseAgent, AgentConfig, AgentResult
from app.agents.base.agent_state import AgentState
from app.agents.newsletter.graph import NewsletterWorkflow
from app.agents.newsletter.nodes import NewsletterNodes
from app.config.settings import Settings, get_settings
from app.core.models import Article, NewsletterRunResult
from app.core.logging import get_logger


logger = get_logger(__name__)


@dataclass
class NewsletterAgentConfig(AgentConfig):
    """Configuration specific to the newsletter agent.

    Extends AgentConfig with newsletter-specific settings like
    max articles, topics, and delivery options.
    """

    max_articles_per_topic: int = 5
    topics: list[str] = field(default_factory=list)
    send_email: bool = True
    include_opinions: bool = True
    newsletter_title: str = "Tech Watch Agent"


class NewsletterAgent(BaseAgent):
    """Agent for generating newsletters from web content.

    This agent orchestrates the newsletter generation process by:
    1. Collecting articles from configured sources
    2. Running them through a multi-stage analysis pipeline
    3. Generating a polished newsletter

    The agent uses dependency injection for services (LLM, article service, etc.)
    to allow flexible testing and configuration.

    Attributes:
        workflow: The LangGraph workflow for newsletter generation
        nodes: The agent nodes for each pipeline stage
    """

    def __init__(
        self,
        config: Optional[NewsletterAgentConfig] = None,
        settings: Optional[Settings] = None,
        workflow: Optional[NewsletterWorkflow] = None,
        nodes: Optional[NewsletterNodes] = None,
    ) -> None:
        """Initialize the newsletter agent.

        Args:
            config: Agent configuration
            settings: Application settings
            workflow: Optional pre-configured workflow (for testing)
            nodes: Optional pre-configured nodes (for testing)
        """
        # Use default config if not provided
        if config is None:
            config = NewsletterAgentConfig()

        super().__init__(config=config, settings=settings)

        self._workflow = workflow
        self._nodes = nodes
        self._article_service = None

    async def setup(self) -> None:
        """Set up agent resources.

        Initializes the workflow and any required services.
        """
        logger.info("Setting up newsletter agent")

        # Create nodes if not provided
        if self._nodes is None:
            self._nodes = NewsletterNodes()

        # Create workflow if not provided
        if self._workflow is None:
            self._workflow = NewsletterWorkflow(nodes=self._nodes)

        # Lazy load article service to avoid circular imports
        if self._article_service is None:
            from app.services.article_service import ArticleService

            self._article_service = ArticleService(self.settings)

        logger.info("Newsletter agent setup complete")

    async def execute(self, input_data: Any) -> AgentResult:
        """Execute the newsletter generation.

        This method orchestrates the full newsletter generation pipeline:
        1. Fetch articles for configured topics (or use provided ones)
        2. Run the articles through the analysis workflow
        3. Return the generated newsletter

        Args:
            input_data: Can be a dict with optional keys:
                - 'topics': list of topics to cover
                - 'articles': pre-fetched articles to use (bypasses fetching)
                - 'send_email': whether to send email

        Returns:
            AgentResult containing the generated newsletter
        """
        await self.setup()

        topics = None
        articles_input = None
        send_email = self.config.send_email

        if isinstance(input_data, dict):
            topics = input_data.get("topics")
            articles_input = input_data.get("articles")
            send_email = input_data.get("send_email", send_email)
        elif isinstance(input_data, str):
            topics = [input_data]

        if topics is None:
            topics = self.config.topics or self.settings.newsletter_topics

        logger.info("Generating newsletter for topics: %s", topics)

        try:
            if articles_input:
                articles = articles_input
                logger.info("Using %d pre-fetched articles", len(articles))
            else:
                articles = await self._article_service.fetch_articles_for_topics(topics)

            if not articles:
                return AgentResult.create_error(
                    errors=["No articles collected for the given topics"],
                    metadata={"topics": topics},
                )

            logger.info("Processing %d articles", len(articles))

            workflow_state = await self._workflow.run_async(articles)

            if workflow_state.get("error"):
                logger.warning("Workflow returned error: %s", workflow_state["error"])

            final_newsletter = workflow_state.get("final_newsletter", "").strip()

            if not final_newsletter:
                return AgentResult.create_error(
                    errors=["Newsletter workflow returned empty content"],
                    metadata={"article_count": len(articles)},
                )

            sources_text = self._format_sources_for_metadata(articles)

            metadata = {
                "article_count": len(articles),
                "topics": topics,
                "topics_covered": list(set(a.topic for a in articles if hasattr(a, "topic"))),
                "quality_score": workflow_state.get("quality_score", 0),
                "workflow_error": workflow_state.get("error"),
                "newsletter_length": len(final_newsletter),
                "sources": sources_text,
            }

            return AgentResult.create_success(
                output={
                    "newsletter": final_newsletter,
                    "articles": [a.to_dict() for a in articles],
                    "workflow_state": workflow_state,
                    "subject": self._extract_subject(final_newsletter),
                },
                metadata=metadata,
            )

        except Exception as exc:
            logger.error("Newsletter generation failed: %s", exc)
            return AgentResult.create_error(
                errors=[str(exc)],
                metadata={"topics": topics},
            )

    def _extract_subject(self, newsletter: str) -> str:
        lines = newsletter.strip().split("\n")
        if lines:
            first = lines[0].strip()
            if first.startswith("#"):
                return first.lstrip("#").strip()
            return first
        return self.config.newsletter_title

    @staticmethod
    def _format_sources_for_metadata(articles: list) -> str:
        """Format sources as a numbered reference list for metadata.

        Args:
            articles: List of Article objects

        Returns:
            Formatted sources string
        """
        if not articles:
            return "No sources."

        lines = []
        seen: set[str] = set()
        for i, article in enumerate(articles, start=1):
            if hasattr(article, "url"):
                url = article.url
            elif isinstance(article, dict):
                url = article.get("url", "")
            else:
                continue

            if not url or url in seen:
                continue
            seen.add(url)

            if hasattr(article, "title"):
                title = article.title
                source = article.source
            else:
                title = article.get("title", "Unknown")
                source = article.get("source", "")

            lines.append(f"[{i}] {title} ({source or 'web'}) — {url}")

        return "\n".join(lines) if lines else "No sources."

    async def run(self, task: str, **kwargs) -> AgentResult:
        """Alias for execute() matching BaseAgent interface.

        Args:
            task: The task/topic to generate newsletter for

        Returns:
            AgentResult containing the generated newsletter
        """
        return await self.execute(task)

    async def generate_with_delivery(
        self,
        topics: Optional[list[str]] = None,
        send_email: bool = True,
    ) -> NewsletterRunResult:
        """Generate a newsletter and optionally deliver it via email.

        This method is a convenience wrapper that handles both generation
        and delivery in a single call. It uses the orchestrator for proper
        delivery handling.

        Args:
            topics: Optional list of topics to cover
            send_email: Whether to send the newsletter via email

        Returns:
            NewsletterRunResult with the generated content and delivery status
        """
        from app.scheduler.service import NewsletterOrchestrator

        orchestrator = NewsletterOrchestrator(settings=self.settings)

        return await orchestrator.generate_newsletter(
            topics=topics,
            send_email=send_email,
        )

    def get_supported_topics(self) -> list[str]:
        """Get the list of topics this agent can handle.

        Returns:
            List of supported topic strings
        """
        return self.config.topics or self.settings.newsletter_topics


# Factory function for creating the agent
def create_newsletter_agent(
    settings: Optional[Settings] = None,
) -> NewsletterAgent:
    """Factory function to create a configured newsletter agent.

    Args:
        settings: Optional settings (uses defaults if not provided)

    Returns:
        Configured NewsletterAgent instance
    """
    if settings is None:
        settings = get_settings()

    config = NewsletterAgentConfig(
        name="newsletter",
        topics=settings.newsletter_topics,
        max_articles_per_topic=settings.max_articles_per_topic,
        newsletter_title=settings.newsletter_title,
    )

    return NewsletterAgent(config=config, settings=settings)
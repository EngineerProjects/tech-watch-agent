from __future__ import annotations

from app.agents.newsletter.state import NewsletterState
from app.core.logging import get_logger
from app.prompts.newsletter import (
    ANALYSIS_SYSTEM_PROMPT,
    ANALYSIS_USER_PROMPT,
    EDITOR_SYSTEM_PROMPT,
    EDITOR_USER_PROMPT,
    OPINION_SYSTEM_PROMPT,
    OPINION_USER_PROMPT,
    RESEARCH_SYSTEM_PROMPT,
    RESEARCH_USER_PROMPT,
)
from app.services.llm import ChatCompletionClient


logger = get_logger(__name__)


class NewsletterNodes:
    def __init__(self, llm_client: ChatCompletionClient | None = None) -> None:
        self.llm_client = llm_client

    def _client(self) -> ChatCompletionClient:
        # Lazy initialization keeps imports cheap for tests and API startup.
        if self.llm_client is None:
            self.llm_client = ChatCompletionClient()
        return self.llm_client

    def researcher(self, state: NewsletterState) -> NewsletterState:
        articles = state.get("raw_articles", [])
        if not articles:
            logger.warning("Researcher received no articles")
            return state

        articles_text = self._format_articles(articles)
        state["research_summary"] = self._client().generate_completion(
            prompt=RESEARCH_USER_PROMPT.format(articles_text=articles_text),
            system_message=RESEARCH_SYSTEM_PROMPT,
            temperature=0.3,
            extra_headers={"X-Title": "tech-watch-agent"},
        )
        return state

    def analyst(self, state: NewsletterState) -> NewsletterState:
        research_summary = state.get("research_summary", "")
        if not research_summary:
            logger.warning("Analyst received no research summary")
            return state

        state["key_insights"] = self._client().generate_completion(
            prompt=ANALYSIS_USER_PROMPT.format(research_summary=research_summary),
            system_message=ANALYSIS_SYSTEM_PROMPT,
            temperature=0.4,
            extra_headers={"X-Title": "tech-watch-agent"},
        )
        return state

    def opinion_writer(self, state: NewsletterState) -> NewsletterState:
        research_summary = state.get("research_summary", "")
        key_insights = state.get("key_insights", "")
        if not research_summary or not key_insights:
            logger.warning("Opinion writer received incomplete state")
            return state

        state["opinion_analysis"] = self._client().generate_completion(
            prompt=OPINION_USER_PROMPT.format(
                research_summary=research_summary,
                key_insights=key_insights,
            ),
            system_message=OPINION_SYSTEM_PROMPT,
            temperature=0.6,
            extra_headers={"X-Title": "tech-watch-agent"},
        )
        return state

    def editor(self, state: NewsletterState) -> NewsletterState:
        state["final_newsletter"] = self._client().generate_completion(
            prompt=EDITOR_USER_PROMPT.format(
                research_summary=state.get("research_summary", ""),
                key_insights=state.get("key_insights", ""),
                opinion_analysis=state.get("opinion_analysis", ""),
            ),
            system_message=EDITOR_SYSTEM_PROMPT,
            temperature=0.4,
            extra_headers={"X-Title": "tech-watch-agent"},
        )
        return state

    def quality_checker(self, state: NewsletterState) -> NewsletterState:
        """Evaluate the quality of gathered content and determine routing."""
        articles = state.get("raw_articles", [])
        research_summary = state.get("research_summary", "")

        article_count = len(articles)
        summary_length = len(research_summary)

        quality_score = 0.0
        quality_factors = []

        if article_count >= 5:
            quality_score += 0.4
            quality_factors.append(f"{article_count} articles (>= 5)")
        elif article_count >= 3:
            quality_score += 0.2
            quality_factors.append(f"{article_count} articles (>= 3)")
        else:
            quality_factors.append(f"Only {article_count} articles")

        if summary_length > 500:
            quality_score += 0.3
            quality_factors.append("Good summary length")
        elif summary_length > 200:
            quality_score += 0.15
            quality_factors.append("Adequate summary length")

        if any(a.get("url") for a in articles if isinstance(a, dict)):
            quality_score += 0.3
            quality_factors.append("Articles have sources")

        quality_score = min(quality_score, 1.0)

        state["quality_score"] = quality_score
        state["quality_factors"] = quality_factors

        if quality_score >= 0.7:
            state["quality_routing"] = "standard"
        elif quality_score >= 0.4:
            state["quality_routing"] = "enhanced"
        else:
            state["quality_routing"] = "basic"

        logger.info(
            "Quality check: score=%.2f, routing=%s, factors=%s",
            quality_score,
            state["quality_routing"],
            quality_factors,
        )

        return state

    def enhanced_analyst(self, state: NewsletterState) -> NewsletterState:
        """Enhanced analyst for lower quality content - more thorough analysis."""
        research_summary = state.get("research_summary", "")
        if not research_summary:
            return self.analyst(state)

        prompt = f"""You are a thorough research analyst. Provide an in-depth analysis.

Research Summary:
{research_summary}

Provide:
1. Key themes and patterns
2. Significant developments
3. Implications and predictions
4. Related topics to monitor

Be comprehensive and analytical."""

        state["key_insights"] = self._client().generate_completion(
            prompt=prompt,
            system_message="You are an expert research analyst.",
            temperature=0.5,
            max_tokens=2000,
        )
        return state

    @staticmethod
    def _format_articles(articles: list[dict[str, object]]) -> str:
        # We flatten article objects into a compact textual bundle because it is
        # easier to keep prompts stable than passing provider-specific tool state.
        lines: list[str] = []
        for index, article in enumerate(articles, start=1):
            title = article.get("title", "No title")
            topic = article.get("topic", "Unknown")
            summary = article.get("summary", "No summary")
            url = article.get("url", "No URL")
            lines.append(
                f"{index}. {title}\n"
                f"   Topic: {topic}\n"
                f"   Summary: {summary}\n"
                f"   URL: {url}"
            )
        return "\n".join(lines)

from __future__ import annotations

import asyncio

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
        if self.llm_client is None:
            self.llm_client = ChatCompletionClient()
        return self.llm_client

    async def _async_generate(
        self,
        prompt: str,
        system_message: str,
        temperature: float = 0.4,
        max_tokens: int = 0,
        extra_headers: dict | None = None,
    ) -> str:
        """Generate completion using async LLM call."""
        client = self._client()
        kwargs: dict = {
            "prompt": prompt,
            "system_message": system_message,
            "temperature": temperature,
        }
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        if extra_headers:
            kwargs["extra_headers"] = extra_headers
        return await client.async_generate_completion(**kwargs)

    async def researcher(self, state: NewsletterState) -> NewsletterState:
        articles = state.get("raw_articles", [])
        if not articles:
            logger.warning("Researcher received no articles")
            return state

        articles_text = self._format_articles(articles)
        state["research_summary"] = await self._async_generate(
            prompt=RESEARCH_USER_PROMPT.format(articles_text=articles_text),
            system_message=RESEARCH_SYSTEM_PROMPT,
            temperature=0.3,
            extra_headers={"X-Title": "tech-watch-agent"},
        )
        return state

    async def analyst(self, state: NewsletterState) -> NewsletterState:
        research_summary = state.get("research_summary", "")
        if not research_summary:
            logger.warning("Analyst received no research summary")
            return state

        state["key_insights"] = await self._async_generate(
            prompt=ANALYSIS_USER_PROMPT.format(research_summary=research_summary),
            system_message=ANALYSIS_SYSTEM_PROMPT,
            temperature=0.4,
            extra_headers={"X-Title": "tech-watch-agent"},
        )
        return state

    async def opinion_writer(self, state: NewsletterState) -> NewsletterState:
        research_summary = state.get("research_summary", "")
        key_insights = state.get("key_insights", "")
        if not research_summary or not key_insights:
            logger.warning("Opinion writer received incomplete state")
            return state

        state["opinion_analysis"] = await self._async_generate(
            prompt=OPINION_USER_PROMPT.format(
                research_summary=research_summary,
                key_insights=key_insights,
            ),
            system_message=OPINION_SYSTEM_PROMPT,
            temperature=0.6,
            extra_headers={"X-Title": "tech-watch-agent"},
        )
        return state

    async def editor(self, state: NewsletterState) -> NewsletterState:
        articles = state.get("raw_articles", [])
        sources_text = self._format_sources(articles)

        state["final_newsletter"] = await self._async_generate(
            prompt=EDITOR_USER_PROMPT.format(
                research_summary=state.get("research_summary", ""),
                key_insights=state.get("key_insights", ""),
                opinion_analysis=state.get("opinion_analysis", ""),
                sources=sources_text,
            ),
            system_message=EDITOR_SYSTEM_PROMPT,
            temperature=0.4,
            extra_headers={"X-Title": "tech-watch-agent"},
        )
        return state

    @staticmethod
    def _format_sources(articles: list[dict[str, object]]) -> str:
        """Format article list as a sources reference section.

        Creates a numbered list of sources with title and URL for citation.
        """
        if not articles:
            return "No sources available."

        lines = []
        seen_urls: set[str] = set()
        for i, article in enumerate(articles, start=1):
            url = article.get("url", "")
            title = article.get("title", "Unknown source")
            source = article.get("source", "")

            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)

            lines.append(f"[{i}] {title} — {source or 'web'}\n    {url}")

        return "\n".join(lines) if lines else "No sources available."

    def quality_checker(self, state: NewsletterState) -> NewsletterState:
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

    async def enhanced_analyst(self, state: NewsletterState) -> NewsletterState:
        research_summary = state.get("research_summary", "")
        if not research_summary:
            return await self.analyst(state)

        prompt = f"""You are a thorough research analyst. Provide an in-depth analysis.

Research Summary:
{research_summary}

Provide:
1. Key themes and patterns
2. Significant developments
3. Implications and predictions
4. Related topics to monitor

Be comprehensive and analytical."""

        state["key_insights"] = await self._async_generate(
            prompt=prompt,
            system_message="You are an expert research analyst.",
            temperature=0.5,
            max_tokens=2000,
        )
        return state

    @staticmethod
    def _format_articles(articles: list[dict[str, object]]) -> str:
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

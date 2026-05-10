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

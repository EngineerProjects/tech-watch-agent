"""API-backed multi-provider web search.

Keeps paid / API-key providers separate from the free SearXNG path.
`web_search` only uses the providers explicitly enabled in runtime settings.
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from app.config.settings import Settings, get_settings
from app.core.logging import get_logger
from app.tools.base import BaseTool, ToolCategory, ToolResult

logger = get_logger(__name__)

_PROVIDER_ORDER = ("tavily", "exa", "langsearch")


class MultiProviderSearchTool(BaseTool):
    """Parallel search across active API-backed providers.

    SearXNG is intentionally excluded from this tool so the planner can choose
    between a free/self-hosted path (`free_search` / `searxng`) and a
    credit-backed path (`web_search`).
    """

    def __init__(self, settings: Optional[Settings] = None, max_results: int = 20) -> None:
        super().__init__()
        self._settings = settings or get_settings()
        self._max_results = max_results

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Parallel web search across active API providers (Tavily, Exa, LangSearch), without SearXNG"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SEARCH

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "categories": {"type": "string", "default": "general,news"},
                "language": {"type": "string", "default": "all"},
                "time_range": {"type": "string", "default": ""},
            },
            "required": ["query"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        query = params.get("query", "")
        if not query:
            return ToolResult(success=False, data=None, error="query is required")

        active_providers = self._get_active_providers()
        if not active_providers:
            return ToolResult(
                success=False,
                data=None,
                error="No API-backed web providers are active or configured",
            )

        provider_tasks: list[asyncio.Task] = []
        provider_names: list[str] = []
        for provider in active_providers:
            task = self._create_task(provider, query)
            if task is None:
                continue
            provider_names.append(provider)
            provider_tasks.append(task)

        if not provider_tasks:
            return ToolResult(
                success=False,
                data=None,
                error="No active web providers are ready to execute",
            )

        raw_results = await asyncio.gather(*provider_tasks, return_exceptions=True)

        seen_urls: dict[str, dict[str, Any]] = {}
        providers_used: list[str] = []

        for name, res in zip(provider_names, raw_results):
            if isinstance(res, Exception):
                logger.warning("Provider '%s' raised: %s", name, res)
                continue
            if not isinstance(res, dict) or not res.get("success"):
                logger.debug("Provider '%s' returned failure", name)
                continue

            articles = self._extract_articles(res.get("data"), name)
            if not articles:
                logger.debug("Provider '%s' returned 0 articles", name)
                continue

            providers_used.append(name)
            for art in articles:
                url = art.get("url", "")
                if not url:
                    continue
                if url not in seen_urls:
                    seen_urls[url] = art
                    continue
                existing_score = seen_urls[url].get("relevance_score") or 0
                new_score = art.get("relevance_score") or 0
                if new_score > existing_score:
                    seen_urls[url] = art

        merged = list(seen_urls.values())[: self._max_results]
        if not merged:
            logger.warning("[web_search] Active providers returned 0 results for '%s'", query[:80])
            return ToolResult(
                success=True,
                data=[],
                error=None,
                metadata={"count": 0, "providers": providers_used, "mode": "api"},
            )

        logger.info("[web_search] %d results from %s for '%s'", len(merged), providers_used, query[:60])
        return ToolResult(
            success=True,
            data=merged,
            error=None,
            metadata={"count": len(merged), "providers": providers_used, "query": query, "mode": "api"},
        )

    def _get_active_providers(self) -> list[str]:
        configured = []
        seen: set[str] = set()
        for provider in getattr(self._settings, "search_web_providers", []) or []:
            normalized = str(provider).strip().lower()
            if not normalized or normalized in seen:
                continue
            if normalized not in _PROVIDER_ORDER:
                logger.debug("Ignoring unsupported web provider '%s'", normalized)
                continue
            seen.add(normalized)
            configured.append(normalized)
        return configured

    def _create_task(self, provider: str, query: str) -> asyncio.Task | None:
        if provider == "tavily" and self._settings.tavily_api_key:
            from app.tools.web.tavily import TavilySearchTool

            tool = TavilySearchTool(api_key=self._settings.tavily_api_key, max_results=self._max_results)
            return asyncio.create_task(tool.execute({"query": query}))
        if provider == "exa" and self._settings.exa_api_key:
            from app.tools.web.exa import ExaSearchTool

            tool = ExaSearchTool(api_key=self._settings.exa_api_key, max_results=self._max_results)
            return asyncio.create_task(tool.execute({"query": query}))
        if provider == "langsearch" and self._settings.langsearch_api_key:
            from app.tools.web.langsearch import LangSearchTool

            tool = LangSearchTool(api_key=self._settings.langsearch_api_key, max_results=self._max_results)
            return asyncio.create_task(tool.execute({"query": query}))

        logger.debug("Skipping inactive or unconfigured web provider '%s'", provider)
        return None

    @staticmethod
    def _extract_articles(data: Any, provider: str) -> list[dict[str, Any]]:
        if isinstance(data, list):
            return [
                {
                    "title": a.get("title", ""),
                    "url": a.get("url", ""),
                    "summary": a.get("summary") or a.get("description") or a.get("content") or "",
                    "source": a.get("source") or (a.get("url", "").split("/")[2] if a.get("url") else ""),
                    "published_date": a.get("published_date") or a.get("date") or "",
                    "relevance_score": a.get("score") or a.get("relevance_score"),
                    "provider": provider,
                }
                for a in data
                if isinstance(a, dict) and a.get("url")
            ]

        if isinstance(data, dict):
            results = data.get("results") or data.get("articles") or []
            if results:
                return MultiProviderSearchTool._extract_articles(results, provider)

        return []

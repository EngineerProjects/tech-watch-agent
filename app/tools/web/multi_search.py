"""Multi-provider search tool.

Fires SearXNG and all configured API-key providers in parallel,
merges results and deduplicates by URL.  Providers that have no API key
configured are silently skipped.
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from app.config.settings import Settings, get_settings
from app.core.logging import get_logger
from app.tools.base import BaseTool, ToolCategory, ToolResult

logger = get_logger(__name__)


class MultiProviderSearchTool(BaseTool):
    """Parallel search across SearXNG + configured paid providers.

    Priority / merge strategy:
      1. SearXNG  — always tried (self-hosted, free, multi-engine)
      2. Tavily   — tried if TAVILY_API_KEY is set
      3. (Exa, LangSearch) — tried if their keys are set

    Results are merged and deduplicated by URL.  Items found by more than
    one provider are kept once with the highest relevance_score.
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
        return "Multi-provider web search (SearXNG + Tavily when available), deduped by URL"

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

        categories = params.get("categories", "general,news")
        language = params.get("language", "all")
        time_range = params.get("time_range", "") or ""

        provider_tasks: list[asyncio.Task] = []
        provider_names: list[str] = []

        # Always include SearXNG
        try:
            from app.tools.web.searxng import SearXNGSearchTool
            srx_tool = SearXNGSearchTool(settings=self._settings)
            provider_tasks.append(asyncio.create_task(
                srx_tool.execute({"query": query, "categories": categories,
                                  "language": language, "time_range": time_range})
            ))
            provider_names.append("searxng")
        except Exception as exc:
            logger.debug("SearXNG unavailable: %s", exc)

        # Tavily if key is set
        if self._settings.tavily_api_key:
            try:
                from app.tools.web.tavily import TavilySearchTool
                tav_tool = TavilySearchTool(api_key=self._settings.tavily_api_key,
                                            max_results=self._max_results)
                provider_tasks.append(asyncio.create_task(
                    tav_tool.execute({"query": query})
                ))
                provider_names.append("tavily")
            except Exception as exc:
                logger.debug("Tavily unavailable: %s", exc)

        # Exa if key is set
        if getattr(self._settings, "exa_api_key", None):
            try:
                from app.tools.web.exa import ExaSearchTool
                exa_tool = ExaSearchTool(api_key=self._settings.exa_api_key,
                                         max_results=self._max_results)
                provider_tasks.append(asyncio.create_task(
                    exa_tool.execute({"query": query})
                ))
                provider_names.append("exa")
            except Exception as exc:
                logger.debug("Exa unavailable: %s", exc)

        if not provider_tasks:
            return ToolResult(success=False, data=None, error="No search providers configured")

        raw_results = await asyncio.gather(*provider_tasks, return_exceptions=True)

        # Merge and deduplicate
        seen_urls: dict[str, dict] = {}  # url → best article dict
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
                else:
                    # Keep highest relevance_score
                    existing_score = seen_urls[url].get("relevance_score") or 0
                    new_score = art.get("relevance_score") or 0
                    if new_score > existing_score:
                        seen_urls[url] = art

        merged = list(seen_urls.values())[: self._max_results]

        if not merged:
            logger.warning(
                "[multi_search] All providers returned 0 results for '%s'", query[:80]
            )
            return ToolResult(success=True, data=[], error=None,
                              metadata={"count": 0, "providers": providers_used})

        logger.info(
            "[multi_search] %d results from %s for '%s'",
            len(merged), providers_used, query[:60],
        )
        return ToolResult(
            success=True,
            data=merged,
            error=None,
            metadata={"count": len(merged), "providers": providers_used, "query": query},
        )

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_articles(data: Any, provider: str) -> list[dict]:
        """Normalise any provider output to a flat list of article dicts."""
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
                for a in data if isinstance(a, dict) and a.get("url")
            ]

        if isinstance(data, dict):
            # Tavily: {"results": [...], "answer": ...}
            results = data.get("results") or []
            if results:
                return MultiProviderSearchTool._extract_articles(results, provider)
            # Generic articles key
            articles = data.get("articles") or []
            if articles:
                return MultiProviderSearchTool._extract_articles(articles, provider)

        return []

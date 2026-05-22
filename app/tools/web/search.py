from __future__ import annotations

import asyncio
from typing import Any

from app.config.settings import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class NewsSearchService:
    """Search coordinator for article ingestion and deep-research URL discovery.

    Strategy:
      1. Try the free/self-hosted provider group first (`search_free_providers`).
      2. If that yields nothing, fallback through the configured API-backed web
         providers (`search_web_providers`) in order.

    This keeps SearXNG as the default free path while still allowing robust
    fallbacks when quotas or coverage require it.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def search_news_urls(self, topic: str, max_results: int = 10) -> list[str]:
        for provider_fn in self._iter_url_providers():
            provider_name = provider_fn.__name__.removeprefix("_try_")
            try:
                urls = await provider_fn(topic, max_results)
                if urls:
                    logger.info("[search] provider=%s query='%s' results=%d", provider_name, topic[:80], len(urls))
                    return urls
                logger.debug("[search] provider=%s returned 0 results for '%s'", provider_name, topic[:80])
            except Exception as exc:
                logger.warning("[search] provider=%s failed for '%s': %s", provider_name, topic[:80], exc)

        logger.warning("[search] all providers failed for '%s', returning static fallback", topic)
        return self.settings.news_sources[:max_results]

    async def search(self, query: str, max_results: int = 10) -> list[dict[str, Any]]:
        try:
            searxng_results = await self._search_searxng(query, max_results)
        except Exception as exc:
            logger.debug("SearXNG search failed for '%s': %s", query, exc)
            searxng_results = []

        if searxng_results:
            logger.info("search: %d free results for '%s'", len(searxng_results), query)
            return searxng_results[:max_results]

        provider_fns = self._iter_detail_fallbacks()
        tasks = [self._safe_detail_search(fn, query, max_results) for fn in provider_fns]
        if not tasks:
            logger.warning("[search] no fallback search providers are configured for '%s'", query[:80])
            return []

        raw_results = await asyncio.gather(*tasks)
        seen: set[str] = set()
        combined: list[dict[str, Any]] = []
        for items in raw_results:
            for item in items:
                url = item.get("url", "")
                if url and url not in seen:
                    seen.add(url)
                    combined.append(item)

        if combined:
            logger.info("search: %d fallback results for '%s'", len(combined), query)
            return combined[:max_results]

        logger.warning("[search] all providers returned 0 results for '%s'", query[:80])
        return []

    def _iter_url_providers(self) -> list[Any]:
        providers: list[Any] = []
        for provider in self._normalized(self.settings.search_free_providers):
            if provider == "searxng":
                providers.append(self._try_searxng)
        for provider in self._normalized(self.settings.search_web_providers):
            if provider == "tavily":
                providers.append(self._try_tavily)
            elif provider == "exa":
                providers.append(self._try_exa)
            elif provider == "langsearch":
                providers.append(self._try_langsearch)
        return providers

    def _iter_detail_fallbacks(self) -> list[Any]:
        providers: list[Any] = []
        for provider in self._normalized(self.settings.search_web_providers):
            if provider == "tavily":
                providers.append(self._search_tavily)
            elif provider == "exa":
                providers.append(self._search_exa)
            elif provider == "langsearch":
                providers.append(self._search_langsearch)
        return providers

    @staticmethod
    def _normalized(providers: list[str] | None) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for provider in providers or []:
            normalized = str(provider).strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(normalized)
        return ordered

    async def _safe_detail_search(self, fn: Any, query: str, max_results: int) -> list[dict[str, Any]]:
        try:
            return await fn(query, max_results) or []
        except Exception as exc:
            logger.debug("%s search failed for '%s': %s", fn.__name__, query, exc)
            return []

    async def _try_searxng(self, topic: str, max_results: int) -> list[str]:
        from app.tools.web.searxng import SearXNGSearchTool

        tool = SearXNGSearchTool(base_url=self.settings.searxng_url, max_results=max_results)
        urls = await tool.search_urls(topic)
        return urls[:max_results]

    async def _search_searxng(self, query: str, max_results: int) -> list[dict[str, Any]]:
        from app.tools.web.searxng import SearXNGSearchTool

        tool = SearXNGSearchTool(base_url=self.settings.searxng_url, max_results=max_results)
        result = await tool.execute({"query": query})
        if result.get("success") and result.get("data"):
            return result.get("data", [])
        return []

    async def _try_tavily(self, topic: str, max_results: int) -> list[str]:
        if not self.settings.tavily_api_key:
            return []
        from app.tools.web.tavily import TavilySearchTool

        tool = TavilySearchTool(api_key=self.settings.tavily_api_key, max_results=max_results)
        result = await tool.execute({"query": topic})
        if result.get("success") and result.get("data"):
            data = result.get("data")
            items = data if isinstance(data, list) else data.get("results", [])
            return [r.get("url", "") for r in items if r.get("url")][:max_results]
        return []

    async def _search_tavily(self, query: str, max_results: int) -> list[dict[str, Any]]:
        if not self.settings.tavily_api_key:
            return []
        from app.tools.web.tavily import TavilySearchTool

        tool = TavilySearchTool(api_key=self.settings.tavily_api_key, max_results=max_results)
        result = await tool.execute({"query": query})
        if result.get("success") and result.get("data"):
            data = result.get("data")
            items = data if isinstance(data, list) else data.get("results", [])
            return [
                {"title": r.get("title", ""), "url": r.get("url", ""), "description": r.get("content", "")}
                for r in items
                if r.get("url")
            ]
        return []

    async def _try_exa(self, topic: str, max_results: int) -> list[str]:
        if not self.settings.exa_api_key:
            return []
        from app.tools.web.exa import ExaSearchTool

        tool = ExaSearchTool(api_key=self.settings.exa_api_key, max_results=max_results)
        result = await tool.execute({"query": topic})
        if result.get("success") and result.get("data"):
            return [r.get("url", "") for r in result.get("data", []) if r.get("url")][:max_results]
        return []

    async def _search_exa(self, query: str, max_results: int) -> list[dict[str, Any]]:
        if not self.settings.exa_api_key:
            return []
        from app.tools.web.exa import ExaSearchTool

        tool = ExaSearchTool(api_key=self.settings.exa_api_key, max_results=max_results)
        result = await tool.execute({"query": query})
        if result.get("success") and result.get("data"):
            return result.get("data", [])
        return []

    async def _try_langsearch(self, topic: str, max_results: int) -> list[str]:
        if not self.settings.langsearch_api_key:
            return []
        from app.tools.web.langsearch import LangSearchTool

        tool = LangSearchTool(api_key=self.settings.langsearch_api_key, max_results=max_results)
        result = await tool.execute({"query": topic})
        if result.get("success") and result.get("data"):
            return [r.get("url", "") for r in result.get("data", []) if r.get("url")][:max_results]
        return []

    async def _search_langsearch(self, query: str, max_results: int) -> list[dict[str, Any]]:
        if not self.settings.langsearch_api_key:
            return []
        from app.tools.web.langsearch import LangSearchTool

        tool = LangSearchTool(api_key=self.settings.langsearch_api_key, max_results=max_results)
        result = await tool.execute({"query": query})
        if result.get("success") and result.get("data"):
            return result.get("data", [])
        return []

    @staticmethod
    def _dedupe(urls: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for u in urls:
            if u and u not in seen:
                seen.add(u)
                out.append(u)
        return out

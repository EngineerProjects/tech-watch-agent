from __future__ import annotations

from typing import Any, Optional

from app.config.settings import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class NewsSearchService:
    """Multi-provider search coordinator with automatic fallback.

    Priority chain (skips providers that are unconfigured or fail):
      1. SearXNG  — self-hosted metasearch, free, no key needed
      2. Tavily   — high-quality AI search, requires TAVILY_API_KEY
      3. Exa      — neural search, requires EXA_API_KEY
      4. LangSearch — free tier, requires LANGSEARCH_API_KEY
      5. Static sources — always available, last resort

    Returns a list of URLs for backward compatibility with all existing callers.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def search_news_urls(self, topic: str, max_results: int = 10) -> list[str]:
        for provider_fn in (
            self._try_searxng,
            self._try_tavily,
            self._try_exa,
            self._try_langsearch,
        ):
            provider_name = provider_fn.__name__.removeprefix("_try_")
            try:
                urls = await provider_fn(topic, max_results)
                if urls:
                    logger.info(
                        "[search] provider=%s query='%s' results=%d",
                        provider_name,
                        topic[:80],
                        len(urls),
                    )
                    return urls
                logger.debug("[search] provider=%s returned 0 results for '%s'", provider_name, topic[:80])
            except Exception as exc:
                logger.warning("[search] provider=%s failed for '%s': %s", provider_name, topic[:80], exc)

        logger.warning("[search] all providers failed for '%s', returning static fallback", topic)
        return self.settings.news_sources[:max_results]

    async def search(self, query: str, max_results: int = 10) -> list[dict[str, Any]]:
        """Run SearXNG + Tavily in parallel, merge and deduplicate results.

        Falls back to the remaining providers sequentially if both primary
        providers yield nothing.
        """
        import asyncio

        async def _safe(fn: Any, *args: Any) -> list[dict]:
            try:
                return await fn(*args) or []
            except Exception as exc:
                logger.debug("%s search failed for '%s': %s", fn.__name__, query, exc)
                return []

        # Fire the two primary providers in parallel
        searxng_results, tavily_results = await asyncio.gather(
            _safe(self._search_searxng, query, max_results),
            _safe(self._search_tavily, query, max_results),
        )

        # Merge, dedup by URL, preserve order (SearXNG first)
        seen: set[str] = set()
        combined: list[dict] = []
        for item in searxng_results + tavily_results:
            url = item.get("url", "")
            if url and url not in seen:
                seen.add(url)
                combined.append(item)

        if combined:
            logger.info(
                "search: %d results (searxng=%d, tavily=%d) for '%s'",
                len(combined), len(searxng_results), len(tavily_results), query,
            )
            return combined[:max_results * 2]  # allow more results when multi-provider

        # Fallback chain for remaining providers
        for provider_fn in (self._search_exa, self._search_langsearch):
            provider_name = provider_fn.__name__.removeprefix("_search_")
            try:
                results = await provider_fn(query, max_results)
                if results:
                    logger.info("[search] fallback provider=%s query='%s' results=%d", provider_name, query[:80], len(results))
                    return results
            except Exception as exc:
                logger.warning("[search] fallback provider=%s failed for '%s': %s", provider_name, query[:80], exc)

        logger.warning("[search] all providers returned 0 results for '%s'", query[:80])
        return []

    # ── SearXNG ────────────────────────────────────────────────────────────────

    async def _try_searxng(self, topic: str, max_results: int) -> list[str]:
        from app.tools.web.searxng import SearXNGSearchTool

        tool = SearXNGSearchTool(base_url=self.settings.searxng_url, max_results=max_results)
        urls = await tool.search_urls(topic)
        return urls[:max_results]

    async def _search_searxng(self, query: str, max_results: int) -> list[dict]:
        from app.tools.web.searxng import SearXNGSearchTool

        tool = SearXNGSearchTool(base_url=self.settings.searxng_url, max_results=max_results)
        result = await tool.execute({"query": query})
        if result.success and result.data:
            return result.data
        return []

    # ── Tavily ─────────────────────────────────────────────────────────────────

    async def _try_tavily(self, topic: str, max_results: int) -> list[str]:
        if not self.settings.tavily_api_key:
            return []
        from app.tools.web.tavily import TavilySearchTool

        tool = TavilySearchTool(api_key=self.settings.tavily_api_key, max_results=max_results)
        result = await tool.execute({"query": topic})
        if result.success and result.data:
            items = result.data if isinstance(result.data, list) else result.data.get("results", [])
            return [r.get("url", "") for r in items if r.get("url")][:max_results]
        return []

    async def _search_tavily(self, query: str, max_results: int) -> list[dict]:
        if not self.settings.tavily_api_key:
            return []
        from app.tools.web.tavily import TavilySearchTool

        tool = TavilySearchTool(api_key=self.settings.tavily_api_key, max_results=max_results)
        result = await tool.execute({"query": query})
        if result.success and result.data:
            items = result.data if isinstance(result.data, list) else result.data.get("results", [])
            return [
                {"title": r.get("title", ""), "url": r.get("url", ""), "description": r.get("content", "")}
                for r in items
                if r.get("url")
            ]
        return []

    # ── Exa ────────────────────────────────────────────────────────────────────

    async def _try_exa(self, topic: str, max_results: int) -> list[str]:
        if not self.settings.exa_api_key:
            return []
        from app.tools.web.exa import ExaSearchTool

        tool = ExaSearchTool(api_key=self.settings.exa_api_key, max_results=max_results)
        result = await tool.execute({"query": topic})
        if result.success and result.data:
            return [r.get("url", "") for r in result.data if r.get("url")][:max_results]
        return []

    async def _search_exa(self, query: str, max_results: int) -> list[dict]:
        if not self.settings.exa_api_key:
            return []
        from app.tools.web.exa import ExaSearchTool

        tool = ExaSearchTool(api_key=self.settings.exa_api_key, max_results=max_results)
        result = await tool.execute({"query": query})
        if result.success and result.data:
            return result.data
        return []

    # ── LangSearch ─────────────────────────────────────────────────────────────

    async def _try_langsearch(self, topic: str, max_results: int) -> list[str]:
        if not self.settings.langsearch_api_key:
            return []
        from app.tools.web.langsearch import LangSearchTool

        tool = LangSearchTool(api_key=self.settings.langsearch_api_key, max_results=max_results)
        result = await tool.execute({"query": topic})
        if result.success and result.data:
            return [r.get("url", "") for r in result.data if r.get("url")][:max_results]
        return []

    async def _search_langsearch(self, query: str, max_results: int) -> list[dict]:
        if not self.settings.langsearch_api_key:
            return []
        from app.tools.web.langsearch import LangSearchTool

        tool = LangSearchTool(api_key=self.settings.langsearch_api_key, max_results=max_results)
        result = await tool.execute({"query": query})
        if result.success and result.data:
            return result.data
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

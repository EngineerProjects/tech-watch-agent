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
            try:
                urls = await provider_fn(topic, max_results)
                if urls:
                    logger.info(
                        "search_news_urls: got %d results via %s for '%s'",
                        len(urls),
                        provider_fn.__name__.removeprefix("_try_"),
                        topic,
                    )
                    return urls
            except Exception as exc:
                logger.debug("%s failed for '%s': %s", provider_fn.__name__, topic, exc)

        logger.warning("All search providers failed for '%s', using static fallback", topic)
        return self.settings.news_sources[:max_results]

    async def search(self, query: str, max_results: int = 10) -> list[dict[str, Any]]:
        """Like search_news_urls but returns full result dicts with title+url+description."""
        for provider_fn in (
            self._search_searxng,
            self._search_tavily,
            self._search_exa,
            self._search_langsearch,
        ):
            try:
                results = await provider_fn(query, max_results)
                if results:
                    return results
            except Exception as exc:
                logger.debug("%s search failed for '%s': %s", provider_fn.__name__, query, exc)

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

from __future__ import annotations

from typing import Any, Optional

import httpx

from app.config.settings import Settings, get_settings
from app.core.logging import get_logger
from app.tools.base import BaseTool, ToolCategory, ToolResult

logger = get_logger(__name__)


class SearXNGSearchTool(BaseTool):
    """Metasearch via self-hosted SearXNG instance.

    Queries multiple engines (Google, Bing, Brave, DDG…) in parallel and
    returns deduplicated results. Free and unlimited — the default search
    provider when available.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        max_results: int = 10,
        timeout: int = 20,
        settings: Optional[Settings] = None,
    ) -> None:
        super().__init__()
        self._settings = settings or get_settings()
        self._base_url = (base_url or self._settings.searxng_url).rstrip("/")
        self._max_results = max_results
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "searxng"

    @property
    def description(self) -> str:
        return "Metasearch engine (Google, Bing, Brave…) via self-hosted SearXNG"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SEARCH

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "categories": {
                    "type": "string",
                    "description": "Engine category: general (default) or science",
                    "default": "general",
                },
                "language": {"type": "string", "default": "en"},
            },
            "required": ["query"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        query = params.get("query", "")
        categories = params.get("categories", "general")
        language = params.get("language", "en")

        if not query:
            return ToolResult(success=False, data=None, error="query is required")

        try:
            results = await self._search(query, categories, language)
            return ToolResult(
                success=True,
                data=results[: self._max_results],
                error=None,
                metadata={"count": len(results), "provider": "searxng", "query": query},
            )
        except Exception as exc:
            logger.warning("SearXNG search failed for '%s': %s", query, exc)
            return ToolResult(success=False, data=None, error=str(exc))

    async def _search(self, query: str, categories: str, language: str) -> list[dict]:
        async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
            resp = await client.get(
                f"{self._base_url}/search",
                params={
                    "q": query,
                    "format": "json",
                    "categories": categories,
                    "language": language,
                },
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()

        data = resp.json()
        results = []
        for item in data.get("results", []):
            results.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "description": item.get("content", ""),
                    "engine": item.get("engine", ""),
                    "score": item.get("score", 0.0),
                    "published_date": item.get("publishedDate", ""),
                }
            )
        return results

    async def search_urls(self, query: str, categories: str = "general") -> list[str]:
        """Convenience method: returns only URLs."""
        results = await self._search(query, categories, "en")
        return [r["url"] for r in results if r.get("url")]


class SearXNGSearchToolFactory:
    @staticmethod
    def from_settings(settings: Optional[Settings] = None) -> SearXNGSearchTool:
        s = settings or get_settings()
        return SearXNGSearchTool(base_url=s.searxng_url, settings=s)

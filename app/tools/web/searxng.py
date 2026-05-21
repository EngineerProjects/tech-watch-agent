from __future__ import annotations

import asyncio
from typing import Any, Optional

import httpx

from app.config.settings import Settings, get_settings
from app.core.logging import get_logger
from app.tools.base import BaseTool, ToolCategory, ToolResult

logger = get_logger(__name__)

# Map common time_range strings the planner might pass to SearXNG-valid values.
# SearXNG only accepts: "day", "month", "year" (or None/empty).
_TIME_RANGE_MAP = {
    "1d": "day", "7d": "day", "24h": "day", "today": "day",
    "1w": "week", "week": "week",
    "1m": "month", "30d": "month", "month": "month",
    "1y": "year", "365d": "year", "year": "year",
}
_VALID_TIME_RANGES = {"day", "week", "month", "year"}


class SearXNGSearchTool(BaseTool):
    """Metasearch via self-hosted SearXNG instance.

    Improvements over the basic /search call:
    - Multi-page fetch (2 pages = up to 20 results instead of 10)
    - time_range normalisation ("7d" → "day", "1m" → "month" …)
    - news + general categories tried in parallel
    - Optional per-result content enrichment for top-N URLs
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        max_results: int = 15,
        timeout: int = 20,
        pages: int = 2,
        settings: Optional[Settings] = None,
    ) -> None:
        super().__init__()
        self._settings = settings or get_settings()
        self._base_url = (base_url or self._settings.searxng_url).rstrip("/")
        self._max_results = max_results
        self._timeout = timeout
        self._pages = pages  # number of pages to fetch per query

    @property
    def name(self) -> str:
        return "searxng"

    @property
    def description(self) -> str:
        return "Metasearch engine (Google, Bing, Brave…) via self-hosted SearXNG — multi-page, multi-category"

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
                    "description": "Engine categories (default: general,news)",
                    "default": "general,news",
                },
                "language": {"type": "string", "default": "all"},
                "time_range": {
                    "type": "string",
                    "description": "Time filter: day, week, month, year (or 7d, 1m…)",
                    "default": "",
                },
            },
            "required": ["query"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        query = params.get("query", "")
        categories = params.get("categories", "general,news")
        language = params.get("language", "all")
        raw_time_range = params.get("time_range", "") or ""
        time_range = self._normalize_time_range(raw_time_range)

        if not query:
            return ToolResult(success=False, data=None, error="query is required")

        try:
            results = await self._search_multi(query, categories, language, time_range)
            trimmed = results[: self._max_results]
            if not trimmed:
                logger.warning(
                    "SearXNG returned 0 results for query '%s' (url=%s, time_range=%s)",
                    query, self._base_url, time_range or "none",
                )
            else:
                logger.info(
                    "SearXNG: %d results for '%s' (pages=%d)",
                    len(trimmed), query[:80], self._pages,
                )
            return ToolResult(
                success=True,
                data=trimmed,
                error=None,
                metadata={"count": len(trimmed), "provider": "searxng", "query": query},
            )
        except Exception as exc:
            logger.warning("SearXNG search failed for '%s' (url=%s): %s", query, self._base_url, exc)
            return ToolResult(success=False, data=None, error=str(exc))

    # ── Internal helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _normalize_time_range(raw: str) -> str:
        """Convert planner time strings to SearXNG-valid values."""
        if not raw:
            return ""
        normalized = _TIME_RANGE_MAP.get(raw.lower().strip(), raw.lower().strip())
        return normalized if normalized in _VALID_TIME_RANGES else ""

    async def _search_multi(
        self,
        query: str,
        categories: str,
        language: str,
        time_range: str,
    ) -> list[dict]:
        """Fetch multiple pages in parallel and deduplicate by URL."""
        page_tasks = [
            self._fetch_page(query, categories, language, time_range, page)
            for page in range(1, self._pages + 1)
        ]
        pages = await asyncio.gather(*page_tasks, return_exceptions=True)

        seen_urls: set[str] = set()
        merged: list[dict] = []
        for result in pages:
            if isinstance(result, Exception):
                logger.debug("SearXNG page fetch error: %s", result)
                continue
            for item in result:
                url = item.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    merged.append(item)

        # Sort by score descending
        merged.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        return merged

    async def _fetch_page(
        self,
        query: str,
        categories: str,
        language: str,
        time_range: str,
        page: int,
    ) -> list[dict]:
        """Fetch a single page from SearXNG."""
        params: dict[str, Any] = {
            "q": query,
            "format": "json",
            "categories": categories,
            "language": language,
            "pageno": page,
        }
        if time_range:
            params["time_range"] = time_range

        async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
            resp = await client.get(
                f"{self._base_url}/search",
                params=params,
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()

        data = resp.json()
        results = []
        for item in data.get("results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "summary": item.get("content", ""),
                "description": item.get("content", ""),
                "engine": item.get("engine", ""),
                "score": item.get("score", 0.0),
                "published_date": item.get("publishedDate", ""),
                "source": item.get("url", "").split("/")[2] if item.get("url") else "",
            })
        return results

    async def search_urls(self, query: str, categories: str = "general,news") -> list[str]:
        """Convenience method: returns only URLs."""
        results = await self._search_multi(query, categories, "all", "")
        return [r["url"] for r in results if r.get("url")]


class SearXNGSearchToolFactory:
    @staticmethod
    def from_settings(settings: Optional[Settings] = None) -> SearXNGSearchTool:
        s = settings or get_settings()
        return SearXNGSearchTool(base_url=s.searxng_url, settings=s)

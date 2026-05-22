"""Specialized academic and code search with SearXNG-first fallback orchestration."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from app.config.settings import Settings, get_settings
from app.core.logging import get_logger
from app.tools.base import BaseTool, ToolCategory, ToolResult

logger = get_logger(__name__)

_FOCUS_TO_CATEGORIES = {
    "academic": "science",
    "code": "it,general",
}


class ResearchSearchTool(BaseTool):
    """Specialized search for academic and code-heavy research.

    Strategy:
    1. Query SearXNG first for broad/free recall.
    2. If the result set is thin, fan out to the enabled specialized providers
       for that focus area in parallel.
    """

    def __init__(self, settings: Optional[Settings] = None, max_results: int = 15) -> None:
        super().__init__()
        self._settings = settings or get_settings()
        self._max_results = max_results

    @property
    def name(self) -> str:
        return "research_search"

    @property
    def description(self) -> str:
        return "Focused academic or code search: SearXNG first, then specialized providers like ArXiv, Semantic Scholar, OpenAlex, or GitHub"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SEARCH

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "focus": {"type": "string", "enum": ["academic", "code"], "default": "academic"},
                "limit": {"type": "integer", "default": 10},
                "time_range": {"type": "string", "default": ""},
                "year": {"type": "string", "description": "Optional year filter for academic providers"},
            },
            "required": ["query"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        query = params.get("query", "")
        if not query:
            return ToolResult(success=False, data=None, error="query is required")

        focus = str(params.get("focus", "academic") or "academic").lower()
        if focus not in _FOCUS_TO_CATEGORIES:
            return ToolResult(success=False, data=None, error="focus must be 'academic' or 'code'")

        limit = min(int(params.get("limit", self._max_results)), self._max_results)
        time_range = params.get("time_range", "") or ""
        year = params.get("year", "") or ""

        searxng_results = await self._search_searxng(query, focus, time_range)
        providers_used = ["searxng"] if searxng_results else []

        if len(searxng_results) >= limit:
            trimmed = self._dedupe(searxng_results)[:limit]
            return ToolResult(
                success=True,
                data=trimmed,
                error=None,
                metadata={"count": len(trimmed), "providers": providers_used, "focus": focus},
            )

        fallback_results = await self._search_focus_fallbacks(query, focus, limit, year)
        if fallback_results:
            providers_used.extend([provider for provider in fallback_results[1] if provider not in providers_used])

        merged = self._dedupe(searxng_results + fallback_results[0])[:limit]
        return ToolResult(
            success=True,
            data=merged,
            error=None,
            metadata={"count": len(merged), "providers": providers_used, "focus": focus},
        )

    async def _search_searxng(self, query: str, focus: str, time_range: str) -> list[dict[str, Any]]:
        from app.tools.web.searxng import SearXNGSearchTool

        tool = SearXNGSearchTool(settings=self._settings, max_results=self._max_results)
        result = await tool.execute(
            {
                "query": query,
                "categories": _FOCUS_TO_CATEGORIES[focus],
                "language": "all",
                "time_range": time_range,
            }
        )
        if result.get("success") and result.get("data"):
            return [self._normalise_item(item, "searxng") for item in result.get("data", []) if isinstance(item, dict)]
        return []

    async def _search_focus_fallbacks(
        self,
        query: str,
        focus: str,
        limit: int,
        year: str,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        providers = self._active_focus_providers(focus)
        if not providers:
            return [], []

        tasks: list[asyncio.Task] = []
        names: list[str] = []
        for provider in providers:
            task = self._create_focus_task(provider, query, limit, year)
            if task is None:
                continue
            tasks.append(task)
            names.append(provider)

        if not tasks:
            return [], []

        raw_results = await asyncio.gather(*tasks, return_exceptions=True)
        merged: list[dict[str, Any]] = []
        used: list[str] = []
        for provider, result in zip(names, raw_results):
            if isinstance(result, Exception):
                logger.warning("Focused provider '%s' raised: %s", provider, result)
                continue
            if not result:
                continue
            used.append(provider)
            merged.extend(result)
        return merged, used

    def _active_focus_providers(self, focus: str) -> list[str]:
        raw = getattr(self._settings, f"search_{focus}_providers", []) or []
        providers: list[str] = []
        seen: set[str] = set()
        for provider in raw:
            normalized = str(provider).strip().lower()
            if not normalized or normalized == "searxng" or normalized in seen:
                continue
            seen.add(normalized)
            providers.append(normalized)
        return providers

    def _create_focus_task(
        self,
        provider: str,
        query: str,
        limit: int,
        year: str,
    ) -> asyncio.Task | None:
        if provider == "semantic_scholar":
            from app.tools.web.semantic_scholar import SemanticScholarTool

            tool = SemanticScholarTool(
                api_key=self._settings.semantic_scholar_api_key,
                settings=self._settings,
                max_results=limit,
            )
            payload = {"query": query, "limit": limit}
            if year:
                payload["year"] = year
            return asyncio.create_task(self._run_and_normalise(provider, tool.execute(payload)))

        if provider == "openalex":
            from app.tools.web.openalex import OpenAlexTool

            tool = OpenAlexTool()
            return asyncio.create_task(self._run_and_normalise(provider, tool.execute({"query": query, "limit": limit})))

        if provider == "arxiv":
            from app.tools.social.arxiv import ArXivTool

            tool = ArXivTool()
            return asyncio.create_task(
                self._run_and_normalise(provider, tool.execute({"action": "search", "query": query, "limit": limit, "sort_by": "relevance"}))
            )

        if provider == "github":
            from app.tools.social.github import GitHubTool

            tool = GitHubTool(settings=self._settings)
            return asyncio.create_task(
                self._run_and_normalise(provider, tool.execute({"action": "search_repos", "query": query, "limit": limit}))
            )

        logger.debug("Ignoring unsupported focused provider '%s'", provider)
        return None

    async def _run_and_normalise(self, provider: str, awaitable: Any) -> list[dict[str, Any]]:
        result = await awaitable
        if not result or not result.get("success"):
            return []
        return self._normalise_provider_result(provider, result.get("data"))

    def _normalise_provider_result(self, provider: str, data: Any) -> list[dict[str, Any]]:
        if provider == "semantic_scholar":
            return [
                {
                    "title": item.get("title", ""),
                    "url": item.get("url") or item.get("pdf_url", ""),
                    "summary": item.get("abstract", ""),
                    "source": item.get("venue", "Semantic Scholar"),
                    "published_date": item.get("published_date") or item.get("year") or "",
                    "relevance_score": item.get("citation_count"),
                    "provider": provider,
                }
                for item in (data or [])
                if isinstance(item, dict) and (item.get("url") or item.get("pdf_url"))
            ]

        if provider == "openalex":
            items = data.get("results", []) if isinstance(data, dict) else []
            return [
                {
                    "title": item.get("title", ""),
                    "url": item.get("url") or item.get("pdf_url", ""),
                    "summary": ", ".join(item.get("authors", [])[:3]),
                    "source": "OpenAlex",
                    "published_date": str(item.get("year") or ""),
                    "relevance_score": item.get("cited_by"),
                    "provider": provider,
                }
                for item in items
                if isinstance(item, dict) and (item.get("url") or item.get("pdf_url"))
            ]

        if provider == "arxiv":
            return [
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "summary": item.get("abstract", ""),
                    "source": "arXiv",
                    "published_date": item.get("published") or item.get("updated") or "",
                    "relevance_score": None,
                    "provider": provider,
                }
                for item in (data or [])
                if isinstance(item, dict) and item.get("url")
            ]

        if provider == "github":
            return [
                {
                    "title": item.get("name", ""),
                    "url": item.get("url", ""),
                    "summary": item.get("description", ""),
                    "source": "GitHub",
                    "published_date": item.get("updated", ""),
                    "relevance_score": item.get("stars"),
                    "provider": provider,
                }
                for item in (data or [])
                if isinstance(item, dict) and item.get("url")
            ]

        return []

    @staticmethod
    def _normalise_item(item: dict[str, Any], provider: str) -> dict[str, Any]:
        return {
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "summary": item.get("summary") or item.get("description") or item.get("content") or "",
            "source": item.get("source") or provider,
            "published_date": item.get("published_date") or item.get("date") or "",
            "relevance_score": item.get("score") or item.get("relevance_score"),
            "provider": provider,
        }

    @staticmethod
    def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        merged: list[dict[str, Any]] = []
        for item in items:
            url = item.get("url", "")
            if not url or url in seen:
                continue
            seen.add(url)
            merged.append(item)
        return merged

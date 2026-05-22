"""Free/self-hosted search mode powered by SearXNG first."""

from __future__ import annotations

from typing import Any, Optional

from app.config.settings import Settings, get_settings
from app.core.logging import get_logger
from app.tools.base import BaseTool, ToolCategory, ToolResult

logger = get_logger(__name__)

_FOCUS_TO_CATEGORIES = {
    "general": "general,news",
    "web": "general,news",
    "academic": "science",
    "code": "it,general",
}


class FreeSearchTool(BaseTool):
    """Free and self-hosted search entrypoint.

    Uses the providers configured in `search_free_providers`. Today this is
    primarily SearXNG, which gives the planner a stable, quota-light path
    distinct from the API-backed `web_search` tool.
    """

    def __init__(self, settings: Optional[Settings] = None, max_results: int = 15) -> None:
        super().__init__()
        self._settings = settings or get_settings()
        self._max_results = max_results

    @property
    def name(self) -> str:
        return "free_search"

    @property
    def description(self) -> str:
        return "Free/self-hosted search via SearXNG, with focus modes for general, academic, or code discovery"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SEARCH

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "focus": {
                    "type": "string",
                    "enum": ["general", "web", "academic", "code"],
                    "default": "general",
                },
                "categories": {"type": "string", "description": "Optional SearXNG category override"},
                "language": {"type": "string", "default": "all"},
                "time_range": {"type": "string", "default": ""},
                "limit": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        query = params.get("query", "")
        if not query:
            return ToolResult(success=False, data=None, error="query is required")

        focus = str(params.get("focus", "general") or "general").lower()
        categories = params.get("categories") or _FOCUS_TO_CATEGORIES.get(focus, _FOCUS_TO_CATEGORIES["general"])
        language = params.get("language", "all")
        time_range = params.get("time_range", "") or ""
        limit = min(int(params.get("limit", self._max_results)), self._max_results)

        active_providers = self._active_providers()
        if not active_providers:
            return ToolResult(success=False, data=None, error="No free search providers are active")

        results: list[dict[str, Any]] = []
        providers_used: list[str] = []
        for provider in active_providers:
            if provider != "searxng":
                logger.debug("Ignoring unsupported free provider '%s'", provider)
                continue
            provider_results = await self._search_searxng(query, categories, language, time_range)
            if provider_results:
                providers_used.append(provider)
                results.extend(provider_results)
                break

        deduped = self._dedupe(results)[:limit]
        return ToolResult(
            success=True,
            data=deduped,
            error=None,
            metadata={"count": len(deduped), "providers": providers_used, "focus": focus},
        )

    def _active_providers(self) -> list[str]:
        providers = getattr(self._settings, "search_free_providers", None) or ["searxng"]
        return [str(provider).strip().lower() for provider in providers if str(provider).strip()]

    async def _search_searxng(
        self,
        query: str,
        categories: str,
        language: str,
        time_range: str,
    ) -> list[dict[str, Any]]:
        from app.tools.web.searxng import SearXNGSearchTool

        tool = SearXNGSearchTool(settings=self._settings, max_results=self._max_results)
        result = await tool.execute(
            {
                "query": query,
                "categories": categories,
                "language": language,
                "time_range": time_range,
            }
        )
        if result.get("success") and result.get("data"):
            return [self._normalise_item(item, "searxng") for item in result.get("data", []) if isinstance(item, dict)]
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

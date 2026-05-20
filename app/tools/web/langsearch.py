from __future__ import annotations

from typing import Any, Optional

import httpx

from app.config.settings import Settings, get_settings
from app.core.logging import get_logger
from app.tools.base import BaseTool, ToolCategory, ToolResult

logger = get_logger(__name__)

LANGSEARCH_API_URL = "https://api.langsearch.com/v1/web-search"


class LangSearchTool(BaseTool):
    """Web search via LangSearch — free tier available, no credit card required.

    Good quality general search with snippet + summary per result.
    Requires LANGSEARCH_API_KEY (free at langsearch.com).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        max_results: int = 10,
        timeout: int = 20,
        settings: Optional[Settings] = None,
    ) -> None:
        super().__init__()
        self._settings = settings or get_settings()
        self._api_key = api_key or self._settings.langsearch_api_key
        self._max_results = max_results
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "langsearch"

    @property
    def description(self) -> str:
        return "Web search via LangSearch — free tier, returns snippets and summaries"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SEARCH

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "count": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        query = params.get("query", "")
        count = min(int(params.get("count", self._max_results)), 10)

        if not query:
            return ToolResult(success=False, data=None, error="query is required")
        if not self._api_key:
            return ToolResult(success=False, data=None, error="LANGSEARCH_API_KEY not configured")

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    LANGSEARCH_API_URL,
                    json={"query": query, "count": count},
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                )
                resp.raise_for_status()

            data = resp.json()
            results = [
                {
                    "title": r.get("name", ""),
                    "url": r.get("url", ""),
                    "description": r.get("snippet", ""),
                    "summary": r.get("summary", ""),
                }
                for r in data.get("webPages", {}).get("value", [])
            ]
            return ToolResult(
                success=True,
                data=results,
                error=None,
                metadata={"count": len(results), "provider": "langsearch", "query": query},
            )
        except Exception as exc:
            logger.warning("LangSearch failed for '%s': %s", query, exc)
            return ToolResult(success=False, data=None, error=str(exc))


class LangSearchToolFactory:
    @staticmethod
    def from_settings(settings: Optional[Settings] = None) -> LangSearchTool:
        s = settings or get_settings()
        return LangSearchTool(api_key=s.langsearch_api_key, settings=s)

from __future__ import annotations

from typing import Any, Optional

import httpx

from app.config.settings import Settings, get_settings
from app.core.logging import get_logger
from app.tools.base import BaseTool, ToolCategory, ToolResult

logger = get_logger(__name__)

EXA_API_URL = "https://api.exa.ai/search"


class ExaSearchTool(BaseTool):
    """Web search via Exa AI — strong on recent technical content.

    Exa uses neural search and is particularly good at finding relevant
    developer and research content. Requires EXA_API_KEY.
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
        self._api_key = api_key or self._settings.exa_api_key
        self._max_results = max_results
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "exa_search"

    @property
    def description(self) -> str:
        return "Neural web search via Exa AI — strong on recent technical and research content"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SEARCH

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "num_results": {"type": "integer", "default": 10},
            },
            "required": ["query"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        query = params.get("query", "")
        num_results = min(int(params.get("num_results", self._max_results)), 10)

        if not query:
            return ToolResult(success=False, data=None, error="query is required")
        if not self._api_key:
            return ToolResult(success=False, data=None, error="EXA_API_KEY not configured")

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    EXA_API_URL,
                    params={"query": query, "numResults": num_results},
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
                resp.raise_for_status()

            data = resp.json()
            results = [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "description": r.get("snippet", ""),
                    "score": r.get("score", 0.0),
                }
                for r in data.get("results", [])
            ]
            return ToolResult(
                success=True,
                data=results,
                error=None,
                metadata={"count": len(results), "provider": "exa", "query": query},
            )
        except Exception as exc:
            logger.warning("Exa search failed for '%s': %s", query, exc)
            return ToolResult(success=False, data=None, error=str(exc))


class ExaSearchToolFactory:
    @staticmethod
    def from_settings(settings: Optional[Settings] = None) -> ExaSearchTool:
        s = settings or get_settings()
        return ExaSearchTool(api_key=s.exa_api_key, settings=s)

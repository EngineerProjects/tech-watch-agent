"""
Tavily search tool for deep research.

Provides high-quality web search specifically designed for AI agents.
Tavily offers optimized search for research tasks with features like:
- Domain filtering and freshness control
- Search result ranking by relevance
- Comprehensive content extraction
- Multi-source aggregation
"""

from __future__ import annotations

from typing import Any, Optional

import httpx

from app.tools.base import BaseTool, ToolCategory, ToolResult
from app.config.settings import Settings, get_settings
from app.core.logging import get_logger


logger = get_logger(__name__)


TAVILY_API_URL = "https://api.tavily.com/search"


class TavilySearchTool(BaseTool):
    """High-quality web search tool for AI research agents.

    Tavily is specifically designed for AI applications, providing:
    - Optimized search results for research tasks
    - Domain filtering and freshness control
    - Comprehensive answer extraction from multiple sources
    - Relevant content ranking and deduplication

    Attributes:
        api_key: Tavily API key
        max_results: Maximum number of results to return
        search_depth: "basic" or "advanced" (advanced = more comprehensive)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        max_results: int = 10,
        search_depth: str = "advanced",
        settings: Optional[Settings] = None,
    ) -> None:
        super().__init__()
        self._settings = settings or get_settings()
        self._api_key = api_key or self._settings.tavily_api_key
        self._max_results = max_results
        self._search_depth = search_depth

    @property
    def name(self) -> str:
        return "tavily_search"

    @property
    def description(self) -> str:
        return """High-quality web search specifically designed for AI research agents.
Use this for conducting comprehensive research on any topic. Tavily provides:
- Optimized search results for research
- Domain filtering and freshness control
- Comprehensive content from multiple sources
- Relevant ranking and deduplication

Best for: deep research, fact-checking, multi-source synthesis."""

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SEARCH

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to research",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results (default: 10, max: 20)",
                    "default": 10,
                },
                "search_depth": {
                    "type": "string",
                    "description": "Search depth: 'basic' or 'advanced'",
                    "enum": ["basic", "advanced"],
                    "default": "advanced",
                },
                "domains": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of specific domains to search",
                },
            },
            "required": ["query"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        query = params.get("query", "")
        max_results = params.get("max_results", self._max_results)
        search_depth = params.get("search_depth", self._search_depth)
        domains = params.get("domains")

        if not query:
            return {
                "success": False,
                "data": None,
                "error": "No query provided",
                "metadata": {},
            }

        if not self._api_key:
            return {
                "success": False,
                "data": None,
                "error": "Tavily API key not configured. Set TAVILY_API_KEY in .env",
                "metadata": {},
            }

        payload = {
            "query": query,
            "max_results": min(max_results, 20),
            "search_depth": search_depth if search_depth in ("basic", "advanced") else "advanced",
            "include_answer": True,
            "include_raw_content": False,
            "include_images": False,
        }

        if domains and isinstance(domains, list) and domains:
            payload["domains"] = domains[:5]

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    TAVILY_API_URL,
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            logger.error("Tavily API error: %s", exc)
            return {
                "success": False,
                "data": None,
                "error": f"Tavily API error: {exc.response.status_code}",
                "metadata": {},
            }
        except httpx.HTTPError as exc:
            logger.error("Tavily request failed: %s", exc)
            return {
                "success": False,
                "data": None,
                "error": f"Request failed: {exc}",
                "metadata": {},
            }

        results = data.get("results", [])
        answer = data.get("answer")
        query_time = data.get("response_time", 0)

        formatted_results = []
        for r in results:
            formatted_results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", "")[:500],
                "score": r.get("score", 0),
                "published_date": r.get("published_date"),
            })

        formatted = {
            "query": query,
            "answer": answer,
            "results": formatted_results,
            "count": len(formatted_results),
            "query_time_ms": round(query_time * 1000, 1) if query_time else None,
        }

        logger.info(
            "Tavily search '%s': %d results (%.1fms)",
            query[:50],
            len(formatted_results),
            query_time * 1000 if query_time else 0,
        )

        return {
            "success": True,
            "data": formatted,
            "error": None,
            "metadata": {
                "query": query,
                "result_count": len(formatted_results),
                "has_answer": bool(answer),
                "search_depth": search_depth,
            },
        }

    async def execute_safe(self, params: dict[str, Any]) -> dict[str, Any]:
        """Safe wrapper that always returns dict."""
        return await self.execute(params)


class TavilySearchToolFactory:
    """Factory for creating Tavily search tools with different configurations."""

    @staticmethod
    def create_basic(max_results: int = 5) -> TavilySearchTool:
        return TavilySearchTool(max_results=max_results, search_depth="basic")

    @staticmethod
    def create_advanced(max_results: int = 10) -> TavilySearchTool:
        return TavilySearchTool(max_results=max_results, search_depth="advanced")

    @staticmethod
    def create_research(max_results: int = 15) -> TavilySearchTool:
        return TavilySearchTool(max_results=max_results, search_depth="advanced")

    @staticmethod
    def from_settings(settings: Optional[Settings] = None) -> TavilySearchTool:
        settings = settings or get_settings()
        return TavilySearchTool(api_key=settings.tavily_api_key)
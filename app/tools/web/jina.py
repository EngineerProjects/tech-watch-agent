from __future__ import annotations

from typing import Any, Optional

import httpx

from app.config.settings import Settings, get_settings
from app.core.logging import get_logger
from app.tools.base import BaseTool, ToolCategory, ToolResult

logger = get_logger(__name__)

JINA_READER_PREFIX = "https://r.jina.ai/"
JINA_SEARCH_URL = "https://s.jina.ai/"


class JinaReaderTool(BaseTool):
    """Convert any URL to clean LLM-readable markdown via Jina Reader.

    Prepends https://r.jina.ai/ to any URL to get a clean markdown
    version of the page. No API key needed for basic use.
    Optional JINA_API_KEY for higher rate limits and better extraction.

    Also supports web search via https://s.jina.ai/ (returns grounded
    search results with full page content, not just snippets).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: int = 30,
        max_content_length: int = 50000,
        settings: Optional[Settings] = None,
    ) -> None:
        super().__init__()
        self._settings = settings or get_settings()
        self._api_key = api_key or self._settings.jina_api_key
        self._timeout = timeout
        self._max_content_length = max_content_length

    @property
    def name(self) -> str:
        return "jina_reader"

    @property
    def description(self) -> str:
        return (
            "Convert any URL to clean markdown (r.jina.ai) or search the web "
            "with full-content results (s.jina.ai). No API key required for basic use."
        )

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.CRAWL

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to convert to markdown"},
                "query": {"type": "string", "description": "Search query (alternative to url)"},
            },
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        url = params.get("url", "")
        query = params.get("query", "")

        if not url and not query:
            return ToolResult(success=False, data=None, error="url or query is required")

        try:
            if query:
                return await self._search(query)
            return await self._read(url)
        except Exception as exc:
            logger.warning("Jina failed for '%s': %s", url or query, exc)
            return ToolResult(success=False, data=None, error=str(exc))

    async def _read(self, url: str) -> ToolResult:
        headers = {"Accept": "text/plain,application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
            resp = await client.get(f"{JINA_READER_PREFIX}{url}", headers=headers)
            resp.raise_for_status()

        content = resp.text[: self._max_content_length]
        return ToolResult(
            success=True,
            data={"url": url, "content": content, "length": len(content)},
            error=None,
            metadata={"provider": "jina_reader", "mode": "read"},
        )

    async def _search(self, query: str) -> ToolResult:
        headers = {"Accept": "application/json", "X-Return-Format": "markdown"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
            resp = await client.get(
                f"{JINA_SEARCH_URL}{httpx.URL('', params={'q': query})}",
                headers=headers,
            )
            resp.raise_for_status()

        content = resp.text[: self._max_content_length]
        return ToolResult(
            success=True,
            data={"query": query, "content": content, "length": len(content)},
            error=None,
            metadata={"provider": "jina_reader", "mode": "search"},
        )

    async def read_url(self, url: str) -> str:
        """Convenience: return markdown content of a URL or empty string on error."""
        try:
            result = await self._read(url)
            if result.success and isinstance(result.data, dict):
                return result.data.get("content", "")
        except Exception:
            pass
        return ""


class JinaReaderToolFactory:
    @staticmethod
    def from_settings(settings: Optional[Settings] = None) -> JinaReaderTool:
        s = settings or get_settings()
        return JinaReaderTool(api_key=s.jina_api_key, settings=s)

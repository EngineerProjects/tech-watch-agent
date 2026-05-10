"""
Unified content extraction tool with smart fallback chain.

Provides a single interface for extracting clean content from URLs using
multiple scraping backends with automatic fallback:

Priority chain:
1. Crawl4AI (best markdown output, LLM-optimized)
2. Scrapling (best anti-bot, resilient selectors)
3. web_search → content extraction (fallback via existing search)

The tool automatically:
- Picks the best strategy based on URL and requirements
- Falls back to next tool if one fails
- Cleans output to markdown/text format
- Handles errors gracefully

Usage:
    result = await extractor.execute({
        "url": "https://example.com/article",
        "preference": "markdown"  # or "speed", "reliability"
    })
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from app.tools.base import BaseTool, ToolCategory, ToolResult
from app.core.logging import get_logger


logger = get_logger(__name__)


STRATEGIES = {
    "markdown": ["crawl4ai", "scrapling"],
    "speed": ["scrapling:basic", "scrapling"],
    "reliability": ["scrapling:stealth", "scrapling:basic", "crawl4ai"],
}


class ContentExtractorTool(BaseTool):
    """Unified content extraction tool with smart fallback.

    Provides a single interface that:
    - Tries the best tool for the job based on strategy
    - Automatically falls back if primary tool fails
    - Cleans and formats output consistently

    Strategies:
    - **markdown**: Best for LLM consumption (Crawl4AI → Scrapling)
    - **speed**: Fast HTTP with TLS fingerprint (Scrapling basic → Scrapling)
    - **reliability**: Maximum anti-bot bypass (Scrapling stealth → Crawl4AI)

    Output is always clean text/markdown with no HTML noise.
    """

    def __init__(
        self,
        default_strategy: str = "markdown",
        timeout: int = 60,
        max_content_length: int = 50000,
    ) -> None:
        super().__init__()
        self._default_strategy = default_strategy
        self._timeout = timeout
        self._max_content_length = max_content_length
        self._tools: dict[str, Any] = {}
        self._loaded = False

    @property
    def name(self) -> str:
        return "content_extractor"

    @property
    def description(self) -> str:
        return """Unified content extraction tool with automatic fallback.

Extracts clean content from URLs using multiple backends with smart fallback:
1. **Crawl4AI** (preferred): Best markdown output, LLM-optimized, content filters
2. **Scrapling** (fallback): Best anti-bot bypass, adaptive parsing

Strategies:
- **markdown** (default): Crawl4AI → Scrapling (best for AI/LLM content)
- **speed**: Scrapling basic (fastest, TLS fingerprint)
- **reliability**: Scrapling stealth → Crawl4AI (maximum anti-bot)

Features:
- Automatic fallback: tries best tool, falls back on failure
- Clean output: no nav, ads, scripts, or HTML noise
- Markdown/text format optimized for LLM consumption
- Timeout and length limits to control resource usage

Use this when you need reliable content extraction from any URL.
Input: {"url": "...", "strategy": "markdown|speed|reliability"}
"""

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.CRAWL

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to extract content from",
                },
                "strategy": {
                    "type": "string",
                    "description": "Extraction strategy: markdown (default), speed, reliability",
                    "enum": ["markdown", "speed", "reliability"],
                },
                "output_format": {
                    "type": "string",
                    "description": "Output format: markdown or text",
                    "enum": ["markdown", "text"],
                },
            },
            "required": ["url"],
        }

    def _load_tools(self) -> None:
        """Lazy load all available scraping tools."""
        if self._loaded:
            return

        self._tools = {}

        try:
            from app.tools.web.crawl4ai import Crawl4AITool
            self._tools["crawl4ai"] = Crawl4AITool(
                max_content_length=self._max_content_length,
                timeout=self._timeout,
            )
            logger.debug("ContentExtractor: loaded Crawl4AI")
        except Exception as exc:
            logger.debug("ContentExtractor: Crawl4AI not available: %s", exc)

        try:
            from app.tools.web.scrapling import ScraplingTool
            self._tools["scrapling"] = ScraplingTool(
                default_fetcher="basic",
                max_content_length=self._max_content_length,
                timeout=self._timeout,
            )
            self._tools["scrapling:basic"] = ScraplingTool(
                default_fetcher="basic",
                max_content_length=self._max_content_length,
                timeout=self._timeout,
            )
            self._tools["scrapling:stealth"] = ScraplingTool(
                default_fetcher="stealth",
                max_content_length=self._max_content_length,
                timeout=self._timeout,
            )
            self._tools["scrapling:dynamic"] = ScraplingTool(
                default_fetcher="dynamic",
                max_content_length=self._max_content_length,
                timeout=self._timeout,
            )
            logger.debug("ContentExtractor: loaded Scrapling")
        except Exception as exc:
            logger.debug("ContentExtractor: Scrapling not available: %s", exc)

        self._loaded = True
        logger.info("ContentExtractor loaded with tools: %s", list(self._tools.keys()))

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        url = params.get("url", "")
        strategy = params.get("strategy", self._default_strategy)
        output_format = params.get("output_format", "markdown")

        if not url:
            return {
                "success": False,
                "data": None,
                "error": "No URL provided",
                "metadata": {},
            }

        self._load_tools()

        if output_format == "text":
            params["output_format"] = "text"

        chain = STRATEGIES.get(strategy, STRATEGIES["markdown"])

        last_error = None
        for tool_name in chain:
            if tool_name not in self._tools:
                logger.debug("Skipping unavailable tool: %s", tool_name)
                continue

            tool = self._tools[tool_name]

            try:
                result = await tool.execute(params)

                if result.get("success"):
                    content = result.get("data", {}).get("content", "")
                    if len(content) > self._max_content_length:
                        content = content[:self._max_content_length] + f"\n\n... [truncated at {self._max_content_length} chars]"

                    logger.info("ContentExtractor: %s succeeded for %s (%d chars)", tool_name, url, len(content))

                    return {
                        "success": True,
                        "data": {
                            "content": content,
                            "url": url,
                            "strategy": strategy,
                            "tool_used": tool_name,
                            "original_result": result.get("data"),
                        },
                        "error": None,
                        "metadata": {
                            "strategy": strategy,
                            "tool_used": tool_name,
                            "content_length": len(content),
                            "url": url,
                        },
                    }

                last_error = result.get("error", "Unknown error")
                logger.debug("ContentExtractor: %s failed for %s: %s", tool_name, url, last_error)

            except Exception as exc:
                last_error = str(exc)
                logger.debug("ContentExtractor: %s exception for %s: %s", tool_name, url, exc)

        logger.warning("ContentExtractor: all tools failed for %s (last error: %s)", url, last_error)

        return {
            "success": False,
            "data": None,
            "error": f"All extraction tools failed. Last error: {last_error}",
            "metadata": {
                "strategy": strategy,
                "chain_tried": chain,
                "url": url,
            },
        }

    async def execute_safe(self, params: dict[str, Any]) -> dict[str, Any]:
        """Safe wrapper that catches errors."""
        try:
            return await self.execute(params)
        except Exception as exc:
            logger.error("ContentExtractor execute_safe error: %s", exc)
            return {
                "success": False,
                "data": None,
                "error": str(exc),
                "metadata": {},
            }


class ContentExtractorFactory:
    """Factory for creating ContentExtractorTool instances."""

    @staticmethod
    def create(
        default_strategy: str = "markdown",
        timeout: int = 60,
        max_content_length: int = 50000,
    ) -> ContentExtractorTool:
        """Create a ContentExtractorTool with specified configuration."""
        return ContentExtractorTool(
            default_strategy=default_strategy,
            timeout=timeout,
            max_content_length=max_content_length,
        )

    @staticmethod
    def from_settings(settings: Any = None) -> ContentExtractorTool:
        """Create a ContentExtractorTool from application settings."""
        if settings is None:
            from app.config.settings import get_settings
            settings = get_settings()

        default_strategy = getattr(settings, "content_extractor_strategy", "markdown")
        timeout = getattr(settings, "content_extractor_timeout", 60)
        max_length = getattr(settings, "content_extractor_max_length", 50000)

        return ContentExtractorTool(
            default_strategy=default_strategy,
            timeout=timeout,
            max_content_length=max_length,
        )
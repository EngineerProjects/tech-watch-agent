"""
Crawl4AI tool for LLM-optimized web crawling and markdown extraction.

Crawl4AI is an AI-powered web crawling library that converts web pages to
clean, structured markdown format optimized for LLM consumption.

Key features:
- Native markdown output (clean, no HTML noise)
- Built-in content filters (Pruning, BM25)
- LLM-based structured extraction (define extraction with natural language)
- JavaScript rendering via Playwright
- Chunking strategies for large pages
- High performance async crawling

Content filters:
- PruningContentFilter: removes low-relevance content based on text density
- BM25ContentFilter: filters based on user query relevance

This tool wraps Crawl4AI as a BaseTool for the tech-watch-agent.
"""

from __future__ import annotations

from typing import Any, Optional

from app.tools.base import BaseTool, ToolCategory, ToolResult
from app.core.logging import get_logger


logger = get_logger(__name__)


class Crawl4AITool(BaseTool):
    """LLM-optimized web crawler powered by Crawl4AI.

    Converts web pages to clean markdown format with optional content filtering.
    Designed for AI agents that need structured, readable content from web pages.

    Features:
    - Native markdown output (clean, no HTML noise)
    - Built-in content filters (PruningContentFilter, BM25ContentFilter)
    - LLM-based extraction (Pydantic schemas or natural language queries)
    - JavaScript rendering via Playwright
    - High performance async crawling

    Attributes:
        content_filter: Content filtering strategy - "none", "pruning", or "bm25"
        filter_threshold: Threshold for pruning filter (0.0-1.0)
        timeout: Request timeout in seconds
        max_content_length: Maximum content length to return (chars)
        headless: Run browser in headless mode
    """

    def __init__(
        self,
        content_filter: str = "pruning",
        filter_threshold: float = 0.48,
        timeout: int = 30,
        max_content_length: int = 50000,
        headless: bool = True,
    ) -> None:
        super().__init__()
        self._content_filter = content_filter
        self._filter_threshold = filter_threshold
        self._timeout = timeout
        self._max_content_length = max_content_length
        self._headless = headless

    @property
    def name(self) -> str:
        return "crawl4ai"

    @property
    def description(self) -> str:
        return """LLM-optimized web crawler that extracts clean markdown from web pages.

Key features:
- Native markdown output (clean, no HTML noise - perfect for LLMs)
- Content filtering: removes low-relevance content (nav, ads, footers)
- JavaScript rendering for dynamic pages
- LLM-based structured extraction (define data to extract in plain English)
- Async high-performance crawling

Content filters:
- **pruning**: Removes low text-density content (default, fast)
- **bm25**: Filters based on relevance to search query
- **none**: No filtering, raw markdown

Use this tool when:
- You need clean, structured markdown from any URL
- You want AI-ready content (RAG pipelines, summaries, analysis)
- The page requires JavaScript rendering
- You need structured data extraction via natural language

Output is always clean markdown with proper headers, lists, and formatting.
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
                    "description": "URL to crawl",
                },
                "content_filter": {
                    "type": "string",
                    "description": "Content filter: none, pruning, or bm25",
                    "enum": ["none", "pruning", "bm25"],
                },
                "query": {
                    "type": "string",
                    "description": "Search query for BM25 filter (improves relevance filtering)",
                },
                "threshold": {
                    "type": "number",
                    "description": "Filter threshold (0.0-1.0, default 0.48)",
                },
            },
            "required": ["url"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        url = params.get("url", "")
        content_filter = params.get("content_filter", self._content_filter)
        query = params.get("query", "")
        threshold = params.get("threshold", self._filter_threshold)

        if not url:
            return {
                "success": False,
                "data": None,
                "error": "No URL provided",
                "metadata": {},
            }

        try:
            content, metadata = await self._crawl(url, content_filter, query, threshold)

            if len(content) > self._max_content_length:
                content = content[:self._max_content_length] + f"\n\n... [content truncated at {self._max_content_length} chars]"

            logger.debug("Crawl4AI fetched %s: %d chars (filter: %s)", url, len(content), content_filter)

            return {
                "success": True,
                "data": {
                    "content": content,
                    "url": url,
                    "filter": content_filter,
                    "metadata": metadata,
                },
                "error": None,
                "metadata": {
                    "filter": content_filter,
                    "content_length": len(content),
                    "url": url,
                },
            }

        except Exception as exc:
            logger.error("Crawl4AI failed for %s: %s", url, exc)
            return {
                "success": False,
                "data": None,
                "error": str(exc),
                "metadata": {"url": url},
            }

    async def _crawl(self, url: str, content_filter: str, query: str, threshold: float) -> tuple[str, dict]:
        """Perform the crawl with configured filters."""
        try:
            from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
            from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
            from crawl4ai.content_filter_strategy import PruningContentFilter, BM25ContentFilter
        except ImportError:
            return "Crawl4AI is not installed. Run: pip install crawl4ai && crawl4ai-setup", {}

        browser_config = BrowserConfig(headless=self._headless)

        run_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            markdown_generator=self._build_markdown_generator(content_filter, query, threshold),
        )

        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=url, config=run_config)

            if not result.success:
                raise RuntimeError(f"Crawl failed: {result.error_message}")

            if content_filter == "none":
                raw = result.markdown.raw_markdown if hasattr(result.markdown, 'raw_markdown') else str(result.markdown)
                return raw, {"filter": "none", "crawl_status": "success"}
            else:
                fit = result.markdown.fit_markdown if hasattr(result.markdown, 'fit_markdown') else str(result.markdown)
                return fit, {"filter": content_filter, "crawl_status": "success"}

    def _build_markdown_generator(self, content_filter: str, query: str, threshold: float):
        """Build the markdown generator with appropriate content filter."""
        from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
        from crawl4ai.content_filter_strategy import PruningContentFilter, BM25ContentFilter

        if content_filter == "bm25" and query:
            content_filter_obj = BM25ContentFilter(
                user_query=query,
                bm25_threshold=threshold,
            )
        elif content_filter == "pruning":
            content_filter_obj = PruningContentFilter(
                threshold=threshold,
                threshold_type="fixed",
                min_word_threshold=0,
            )
        else:
            content_filter_obj = None

        return DefaultMarkdownGenerator(content_filter=content_filter_obj)

    async def execute_safe(self, params: dict[str, Any]) -> dict[str, Any]:
        """Safe wrapper that catches errors."""
        try:
            return await self.execute(params)
        except Exception as exc:
            logger.error("Crawl4AI execute_safe error: %s", exc)
            return {
                "success": False,
                "data": None,
                "error": str(exc),
                "metadata": {},
            }


class Crawl4AIToolFactory:
    """Factory for creating Crawl4AITool instances."""

    @staticmethod
    def create(
        content_filter: str = "pruning",
        filter_threshold: float = 0.48,
        timeout: int = 30,
        max_content_length: int = 50000,
        headless: bool = True,
    ) -> Crawl4AITool:
        """Create a Crawl4AITool with specified configuration."""
        return Crawl4AITool(
            content_filter=content_filter,
            filter_threshold=filter_threshold,
            timeout=timeout,
            max_content_length=max_content_length,
            headless=headless,
        )

    @staticmethod
    def from_settings(settings: Any = None) -> Crawl4AITool:
        """Create a Crawl4AITool from application settings."""
        if settings is None:
            from app.config.settings import get_settings
            settings = get_settings()

        content_filter = getattr(settings, "crawl4ai_filter", "pruning")
        threshold = getattr(settings, "crawl4ai_threshold", 0.48)
        timeout = getattr(settings, "crawl4ai_timeout", 30)
        max_length = getattr(settings, "crawl4ai_max_content_length", 50000)
        headless = getattr(settings, "crawl4ai_headless", True)

        return Crawl4AITool(
            content_filter=content_filter,
            filter_threshold=threshold,
            timeout=timeout,
            max_content_length=max_length,
            headless=headless,
        )
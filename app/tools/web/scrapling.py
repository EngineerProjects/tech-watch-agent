"""
Scrapling tool for adaptive web scraping and content extraction.

Scrapling is an adaptive web scraping framework that handles everything
from a single request to a full-scale crawl. Key features:

- Adaptive parsing: parser learns from website changes and automatically
  relocates elements when pages update
- Anti-bot bypass: stealth fetchers that bypass Cloudflare Turnstile out of the box
- Multi-mode fetching: fast HTTP requests with TLS fingerprint spoofing,
  or full browser automation via Playwright
- Spider framework: Scrapy-like API with concurrent multi-session crawls,
  pause/resume, and proxy rotation

This tool wraps Scrapling's capabilities as a BaseTool for the tech-watch-agent.
"""

from __future__ import annotations

import re
from typing import Any

from app.tools.base import BaseTool, ToolCategory, ToolResult
from app.core.logging import get_logger


logger = get_logger(__name__)


FETCHER_MODES = {
    "basic": "Fast HTTP requests with browser TLS fingerprint impersonation",
    "stealth": "Advanced stealth with anti-bot bypass (Cloudflare Turnstile)",
    "dynamic": "Full browser automation via Playwright (for JavaScript-heavy sites)",
}


class ScraplingTool(BaseTool):
    """Adaptive web scraping tool powered by Scrapling.

    Provides multiple fetching modes to handle different website complexities:
    - **basic**: Fast HTTP requests with TLS fingerprint impersonation
    - **stealth**: Advanced stealth with anti-bot bypass (bypasses Cloudflare Turnstile)
    - **dynamic**: Full browser automation for JavaScript-heavy sites

    Parser capabilities:
    - CSS selectors, XPath, regex-based selection
    - Text-based selection (find by content)
    - Similar element finding (find elements similar to target)
    - Adaptive element relocation on page changes

    Attributes:
        default_fetcher: Fetcher mode to use by default
        timeout: Request timeout in seconds
        max_content_length: Maximum content length to return (chars)
    """

    def __init__(
        self,
        default_fetcher: str = "basic",
        timeout: int = 30,
        max_content_length: int = 50000,
    ) -> None:
        super().__init__()
        self._default_fetcher = default_fetcher
        self._timeout = timeout
        self._max_content_length = max_content_length
        self._fetcher_instance = None
        self._dynamic_fetcher = None

    @property
    def name(self) -> str:
        return "scrapling"

    @property
    def description(self) -> str:
        return f"""Adaptive web scraping tool with multiple fetching modes.

Available modes:
- **basic**: Fast HTTP requests with TLS fingerprint impersonation
- **stealth**: Advanced stealth with anti-bot bypass (bypasses Cloudflare Turnstile, interstitial pages)
- **dynamic**: Full browser automation via Playwright for JavaScript-heavy sites

Parser capabilities:
- CSS selectors, XPath, regex-based selection
- Text-based selection
- Similar element finding
- Adaptive element relocation on page updates

Use this tool when:
- You need to extract structured content from a specific URL
- Standard web requests are blocked by anti-bot systems
- The target page requires JavaScript rendering
- You need reliable extraction that adapts to page changes

Input should be a URL with optional extraction instructions.
"""

    @property
    def category(self) -> str:
        return ToolCategory.WEB.value

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to scrape",
                },
                "mode": {
                    "type": "string",
                    "description": "Fetcher mode: basic, stealth, or dynamic",
                    "enum": ["basic", "stealth", "dynamic"],
                },
                "selector": {
                    "type": "string",
                    "description": "CSS selector, XPath, or text pattern to extract specific content. If omitted, extracts full page text.",
                },
                "instructions": {
                    "type": "string",
                    "description": "Natural language instructions for content extraction (used with adaptive parsing)",
                },
            },
            "required": ["url"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        url = params.get("url", "")
        mode = params.get("mode", self._default_fetcher)
        selector = params.get("selector", "")
        instructions = params.get("instructions", "")

        if not url:
            return {
                "success": False,
                "data": None,
                "error": "No URL provided",
                "metadata": {},
            }

        fetcher_mode = mode if mode in FETCHER_MODES else self._default_fetcher

        try:
            if fetcher_mode == "dynamic":
                content, metadata = await self._fetch_dynamic(url, selector, instructions)
            elif fetcher_mode == "stealth":
                content, metadata = await self._fetch_stealth(url, selector, instructions)
            else:
                content, metadata = await self._fetch_basic(url, selector, instructions)

            if len(content) > self._max_content_length:
                content = content[:self._max_content_length] + f"\n... [truncated at {self._max_content_length} chars]"

            logger.debug("ScraplingTool fetched %s via %s: %d chars", url, fetcher_mode, len(content))

            return {
                "success": True,
                "data": {
                    "content": content,
                    "url": url,
                    "mode": fetcher_mode,
                    "selector_used": selector,
                    "metadata": metadata,
                },
                "error": None,
                "metadata": {
                    "mode": fetcher_mode,
                    "content_length": len(content),
                    "url": url,
                },
            }

        except Exception as exc:
            logger.error("ScraplingTool failed for %s: %s", url, exc)
            return {
                "success": False,
                "data": None,
                "error": str(exc),
                "metadata": {"url": url, "mode": fetcher_mode},
            }

    async def _fetch_basic(self, url: str, selector: str, instructions: str) -> tuple[str, dict]:
        """Fetch using basic HTTP requests with TLS fingerprint."""
        fetcher = self._get_fetcher()
        response = await fetcher.fetch(url)
        return self._extract_content(response, selector, instructions)

    async def _fetch_stealth(self, url: str, selector: str, instructions: str) -> tuple[str, dict]:
        """Fetch using stealth mode for anti-bot bypass."""
        from scrapling.fetchers.stealth import StealthyFetcher
        fetcher = StealthyFetcher(timeout=self._timeout)
        try:
            response = await fetcher.fetch(url)
        finally:
            await fetcher.close()
        return self._extract_content(response, selector, instructions)

    async def _fetch_dynamic(self, url: str, selector: str, instructions: str) -> tuple[str, dict]:
        """Fetch using dynamic browser automation."""
        from scrapling.fetchers.dynamic import DynamicFetcher
        fetcher = self._get_dynamic_fetcher()
        try:
            response = await fetcher.fetch(url)
        finally:
            await fetcher.close()
        return self._extract_content(response, selector, instructions)

    def _get_fetcher(self):
        """Get or create the basic fetcher instance."""
        if self._fetcher_instance is None:
            from scrapling.fetchers.core import Fetcher
            self._fetcher_instance = Fetcher(timeout=self._timeout)
        return self._fetcher_instance

    def _get_dynamic_fetcher(self):
        """Get or create the dynamic fetcher instance."""
        if self._dynamic_fetcher is None:
            from scrapling.fetchers.dynamic import DynamicFetcher
            self._dynamic_fetcher = DynamicFetcher(timeout=self._timeout)
        return self._dynamic_fetcher

    def _extract_content(self, response, selector: str, instructions: str) -> tuple[str, dict]:
        """Extract content from response using selector or instructions."""
        from scrapling.parser import Selector
        page = Selector(response.html)

        if selector:
            try:
                if selector.startswith("//"):
                    elements = page.xpath(selector)
                else:
                    elements = page.css(selector)
                if elements:
                    content = "\n".join(e.get_all_text() or e.text or "" for e in elements if e.text)
                    return content, {"extraction_method": "selector", "elements_found": len(elements)}
            except Exception as exc:
                logger.warning("Selector extraction failed: %s", exc)

        if instructions:
            content = self._adaptive_extract(page, instructions)
            return content, {"extraction_method": "instructions"}

        return page.get_all_text(ignore_tags=("script", "style", "noscript")), {"extraction_method": "full_page"}

    def _adaptive_extract(self, page, instructions: str) -> str:
        """Use adaptive parsing based on natural language instructions."""
        instruction_lower = instructions.lower()

        if any(k in instruction_lower for k in ["article", "post", "blog", "content"]):
            article = page.find("article")
            if article:
                return article.get_all_text(ignore_tags=("script", "style"))

        if any(k in instruction_lower for k in ["title", "heading", "headline"]):
            h1 = page.find("h1")
            if h1:
                return h1.get_all_text()

        if any(k in instruction_lower for k in ["list", "items", "links"]):
            items = page.find_all("li") or page.css("a")
            if items:
                return "\n".join(f"- {item.text or item.get_all_text()}" for item in items[:20])

        if any(k in instruction_lower for k in ["price", "cost", "value"]):
            price_pattern = r"[$€£]\s*\d+"
            matches = page.find_by_regex(price_pattern)
            if matches:
                return " | ".join(m.text for m in matches if m.text)

        return page.get_all_text(ignore_tags=("script", "style", "noscript"))[:self._max_content_length]

    async def execute_safe(self, params: dict[str, Any]) -> dict[str, Any]:
        """Safe wrapper that catches errors."""
        try:
            return await self.execute(params)
        except Exception as exc:
            logger.error("ScraplingTool execute_safe error: %s", exc)
            return {
                "success": False,
                "data": None,
                "error": str(exc),
                "metadata": {},
            }


class ScraplingToolFactory:
    """Factory for creating ScraplingTool instances."""

    @staticmethod
    def create(
        default_fetcher: str = "basic",
        timeout: int = 30,
        max_content_length: int = 50000,
    ) -> ScraplingTool:
        """Create a ScraplingTool with specified configuration."""
        return ScraplingTool(
            default_fetcher=default_fetcher,
            timeout=timeout,
            max_content_length=max_content_length,
        )

    @staticmethod
    def from_settings(settings: Any = None) -> ScraplingTool:
        """Create a ScraplingTool from application settings."""
        if settings is None:
            from app.config.settings import get_settings
            settings = get_settings()

        default_fetcher = getattr(settings, "scrapling_fetcher", "basic")
        timeout = getattr(settings, "scrapling_timeout", 30)
        max_length = getattr(settings, "scrapling_max_content_length", 50000)

        return ScraplingTool(
            default_fetcher=default_fetcher,
            timeout=timeout,
            max_content_length=max_length,
        )
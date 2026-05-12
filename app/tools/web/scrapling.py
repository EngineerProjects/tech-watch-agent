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

Content is cleaned and converted to markdown/text for optimal LLM consumption.
Cleaner pipeline: remove noise (nav, ads, scripts, footers) → extract main content → convert to markdown.
"""

from __future__ import annotations

import re
from typing import Any

from app.tools.base import BaseTool, ToolCategory, ToolResult
from app.tools.web.cleaner import clean_html_content, extract_main_content, html_to_markdown
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
    - **dynamic**: Full browser automation via Playwright for JavaScript-heavy sites

    Content processing pipeline:
    1. Fetch page content (HTML)
    2. Clean noise (scripts, styles, nav, ads, footers)
    3. Extract main content (article, main, or largest text block)
    4. Convert to markdown/text format

    Parser capabilities:
    - CSS selectors, XPath, regex-based selection
    - Text-based selection (find by content)
    - Similar element finding (find elements similar to target)
    - Adaptive element relocation on page changes

    Attributes:
        default_fetcher: Fetcher mode to use by default
        timeout: Request timeout in seconds
        max_content_length: Maximum content length to return (chars)
        output_format: Output format - "markdown" or "text"
    """

    def __init__(
        self,
        default_fetcher: str = "basic",
        timeout: int = 30,
        max_content_length: int = 50000,
        output_format: str = "markdown",
    ) -> None:
        super().__init__()
        self._default_fetcher = default_fetcher
        self._timeout = timeout
        self._max_content_length = max_content_length
        self._output_format = output_format
        self._fetcher_instance = None
        self._dynamic_fetcher = None

    @property
    def name(self) -> str:
        return "scrapling"

    @property
    def description(self) -> str:
        return f"""Adaptive web scraping tool with multi-mode fetching and clean output.

Available modes:
- **basic**: Fast HTTP requests with TLS fingerprint impersonation (fastest)
- **stealth**: Advanced stealth with anti-bot bypass (Cloudflare Turnstile, interstitial)
- **dynamic**: Full browser automation via Playwright (for JavaScript-heavy sites)

Content processing (automatic):
1. Remove noise: scripts, styles, nav, ads, footers, social buttons
2. Extract main content: article/main div or largest text block
3. Convert to {self._output_format} for clean, LLM-ready output

Parser capabilities:
- CSS selectors, XPath, regex-based selection
- Text-based selection
- Similar element finding
- Adaptive element relocation on page updates

Use this tool when:
- You need clean {self._output_format} content from a specific URL
- Standard web requests are blocked by anti-bot systems
- The target page requires JavaScript rendering
- You need reliable extraction that adapts to page changes

Output is stripped of all noise and formatted as clean {self._output_format}.
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
                    "description": "URL to scrape",
                },
                "mode": {
                    "type": "string",
                    "description": "Fetcher mode: basic, stealth, or dynamic",
                    "enum": ["basic", "stealth", "dynamic"],
                },
                "selector": {
                    "type": "string",
                    "description": "CSS selector, XPath, or text pattern to extract specific content. If omitted, extracts main page content.",
                },
                "instructions": {
                    "type": "string",
                    "description": "Natural language instructions for targeted extraction (article, list, title, etc.)",
                },
                "output_format": {
                    "type": "string",
                    "description": "Output format: markdown or text",
                    "enum": ["markdown", "text"],
                },
            },
            "required": ["url"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        url = params.get("url", "")
        mode = params.get("mode", self._default_fetcher)
        selector = params.get("selector", "")
        instructions = params.get("instructions", "")
        output_fmt = params.get("output_format", self._output_format)

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
                content, metadata = await self._fetch_dynamic(url, selector, instructions, output_fmt)
            elif fetcher_mode == "stealth":
                content, metadata = await self._fetch_stealth(url, selector, instructions, output_fmt)
            else:
                content, metadata = await self._fetch_basic(url, selector, instructions, output_fmt)

            if len(content) > self._max_content_length:
                content = content[:self._max_content_length] + f"\n\n... [content truncated at {self._max_content_length} chars]"

            logger.debug("ScraplingTool fetched %s via %s: %d chars (format: %s)", url, fetcher_mode, len(content), output_fmt)

            return {
                "success": True,
                "data": {
                    "content": content,
                    "url": url,
                    "mode": fetcher_mode,
                    "format": output_fmt,
                    "selector_used": selector,
                    "metadata": metadata,
                },
                "error": None,
                "metadata": {
                    "mode": fetcher_mode,
                    "format": output_fmt,
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

    async def _fetch_basic(self, url: str, selector: str, instructions: str, output_fmt: str) -> tuple[str, dict]:
        """Fetch using basic HTTP requests with TLS fingerprint."""
        fetcher = self._get_fetcher()
        response = fetcher.get(url)
        return self._process_content(response, selector, instructions, output_fmt)

    async def _fetch_stealth(self, url: str, selector: str, instructions: str, output_fmt: str) -> tuple[str, dict]:
        """Fetch using stealth mode for anti-bot bypass."""
        from scrapling import StealthyFetcher
        fetcher = StealthyFetcher()
        response = fetcher.get(url)
        return self._process_content(response, selector, instructions, output_fmt)

    async def _fetch_dynamic(self, url: str, selector: str, instructions: str, output_fmt: str) -> tuple[str, dict]:
        """Fetch using dynamic browser automation."""
        from scrapling import DynamicFetcher
        fetcher = DynamicFetcher()
        response = fetcher.get(url)
        return self._process_content(response, selector, instructions, output_fmt)

    def _get_fetcher(self):
        """Get or create the basic fetcher instance."""
        if self._fetcher_instance is None:
            from scrapling import Fetcher
            self._fetcher_instance = Fetcher()
        return self._fetcher_instance

    def _get_dynamic_fetcher(self):
        """Get or create the dynamic fetcher instance."""
        if self._dynamic_fetcher is None:
            from scrapling import DynamicFetcher
            self._dynamic_fetcher = DynamicFetcher()
        return self._dynamic_fetcher

    def _process_content(self, page, selector: str, instructions: str, output_fmt: str) -> tuple[str, dict]:
        """Process raw page: clean → extract main → convert to format."""
        from scrapling import Selector

        if selector:
            try:
                if selector.startswith("//"):
                    elements = page.xpath(selector)
                else:
                    elements = page.css(selector)
                if elements:
                    raw = "\n".join(e.html_content for e in elements if e.html_content)
                    cleaned = clean_html_content(raw)
                    content = html_to_markdown(cleaned) if output_fmt == "markdown" else extract_main_content(raw)
                    return content, {"extraction_method": "selector", "elements_found": len(elements)}
            except Exception as exc:
                logger.warning("Selector extraction failed: %s", exc)

        if instructions:
            content = self._adaptive_extract(page, instructions)
            if content:
                cleaned = clean_html_content(content)
                return (html_to_markdown(cleaned) if output_fmt == "markdown" else extract_main_content(content)), {"extraction_method": "instructions"}

        raw_cleaned = clean_html_content(page.html_content)
        main_content = extract_main_content(raw_cleaned)
        if output_fmt == "markdown":
            final_content = self._text_to_markdown(main_content)
        else:
            final_content = main_content

        return final_content, {"extraction_method": "cleaned_main_content"}

    def _adaptive_extract(self, page, instructions: str) -> str:
        """Use adaptive parsing based on natural language instructions."""
        instruction_lower = instructions.lower()

        if any(k in instruction_lower for k in ["article", "post", "blog", "content", "main body"]):
            target = (
                page.find("article") or
                page.find("main") or
                page.css_first("[role='main']") or
                page.find("div", class_=re.compile(r"article|post|content", re.I)) or
                page.css_first(".post-content, .article-content, .entry-content")
            )
            if target:
                return target.html_content

        if any(k in instruction_lower for k in ["title", "heading", "headline"]):
            h1 = page.find("h1")
            if h1:
                return h1.get_all_text() or ""

        if any(k in instruction_lower for k in ["list", "items", "products", "links"]):
            items = page.find_all("li") or page.css("a")
            if items:
                return "\n".join(f"- {item.text or item.get_all_text()}" for item in items[:20] if item.text)

        if any(k in instruction_lower for k in ["price", "cost", "value", "pricing"]):
            price_pattern = r"[$€£]\s*\d+[\.,]?\d*"
            matches = page.find_by_regex(price_pattern)
            if matches:
                return " | ".join(m.text for m in matches if m.text)

        if any(k in instruction_lower for k in ["author", "date", "published"]):
            author = page.find(class_=re.compile(r"author|byline", re.I))
            date = page.find(class_=re.compile(r"date|published|time", re.I))
            result = []
            if author and author.text:
                result.append(f"Author: {author.text.strip()}")
            if date and date.text:
                result.append(f"Date: {date.text.strip()}")
            if result:
                return "\n".join(result)

        return ""

    @staticmethod
    def _text_to_markdown(text: str) -> str:
        """Convert plain text to basic markdown (headers, lists, etc.)."""
        import re
        lines = text.split("\n")
        result = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                result.append("")
                continue
            if re.match(r"^#{1,6}\s", stripped):
                result.append(stripped)
            elif re.match(r"^[\*\-]\s", stripped) or re.match(r"^\d+\.\s", stripped):
                result.append(stripped)
            elif re.match(r"^\"[^\"]+\"$|^[^\"]+\"$", stripped):
                result.append("> " + stripped.strip('"'))
            elif len(stripped) > 80 and not result[-1].startswith("#") if result else False:
                result.append(f"\n{stripped}\n")
            else:
                result.append(stripped)
        return "\n".join(result)

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
        output_format: str = "markdown",
    ) -> ScraplingTool:
        """Create a ScraplingTool with specified configuration."""
        return ScraplingTool(
            default_fetcher=default_fetcher,
            timeout=timeout,
            max_content_length=max_content_length,
            output_format=output_format,
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
        output_fmt = getattr(settings, "scrapling_output_format", "markdown")

        return ScraplingTool(
            default_fetcher=default_fetcher,
            timeout=timeout,
            max_content_length=max_length,
            output_format=output_fmt,
        )

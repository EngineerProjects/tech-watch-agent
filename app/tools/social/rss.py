"""
RSS/Atom feed monitoring tool.

This tool provides capabilities for monitoring RSS and Atom feeds,
aggregating content from multiple sources into a unified format.

Features:
- Fetch and parse RSS/Atom feeds
- Aggregate multiple feeds
- Track feed updates
- Extract article metadata
"""

from typing import Any, Optional
from datetime import datetime
from urllib.parse import urlparse

import feedparser

from app.tools.base import BaseTool, ToolCategory, ToolResult
from app.core.logging import get_logger


logger = get_logger(__name__)


class RSSTool(BaseTool):
    """Tool for RSS and Atom feed monitoring.

    Provides functionality to fetch and parse RSS/Atom feeds,
    aggregate content from multiple sources, and track updates.
    Uses the feedparser library for parsing.

    Attributes:
        default_timeout: Default timeout for feed requests (seconds)
    """

    def __init__(self, default_timeout: int = 30) -> None:
        """Initialize RSS tool.

        Args:
            default_timeout: Default timeout for HTTP requests
        """
        super().__init__()
        self._default_timeout = default_timeout

    @property
    def name(self) -> str:
        return "rss"

    @property
    def description(self) -> str:
        return """RSS/Atom feed monitoring tool for aggregating content
from multiple news sources. Use this to track blog posts, news articles,
podcast episodes, or any content published via RSS/Atom feeds."""

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SOCIAL

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["fetch", "aggregate", "discover", "feed_info"],
                    "description": "The RSS action to perform",
                },
                "url": {
                    "type": "string",
                    "description": "Feed URL (for fetch and feed_info actions)",
                },
                "urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of feed URLs (for aggregate action)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of items to return (default: 10)",
                    "default": 10,
                },
            },
            "required": ["action"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        """Execute RSS monitoring action.

        Args:
            params: Action and parameters for RSS operation

        Returns:
            ToolResult with RSS data or error
        """
        action = params.get("action")
        url = params.get("url", "")
        urls = params.get("urls", [])
        limit = params.get("limit", 10)

        try:
            if action == "fetch":
                return await self._fetch_feed(url, limit)
            elif action == "aggregate":
                return await self._aggregate_feeds(urls, limit)
            elif action == "discover":
                return await self._discover_feeds(url)
            elif action == "feed_info":
                return await self._get_feed_info(url)
            else:
                return {
                    "success": False,
                    "data": None,
                    "error": f"Unknown action: {action}",
                    "metadata": {},
                }

        except Exception as exc:
            logger.error("RSS tool error: %s", exc)
            return {
                "success": False,
                "data": None,
                "error": str(exc),
                "metadata": {},
            }

    async def _fetch_feed(self, url: str, limit: int) -> ToolResult:
        """Fetch and parse an RSS/Atom feed.

        Args:
            url: Feed URL
            limit: Maximum number of items

        Returns:
            ToolResult with feed items
        """
        if not url:
            return {
                "success": False,
                "data": None,
                "error": "Feed URL is required",
                "metadata": {},
            }

        try:
            parsed = feedparser.parse(url, timeout=self._default_timeout)

            if parsed.get("bozo_exception"):
                logger.warning("Feed parse warning for %s: %s", url, parsed.bozo_exception)

            feed_info = self._extract_feed_info(parsed.feed)
            items = self._extract_items(parsed.entries[:limit])

            return {
                "success": True,
                "data": {
                    "feed": feed_info,
                    "items": items,
                },
                "error": None,
                "metadata": {
                    "url": url,
                    "count": len(items),
                    "total": len(parsed.entries),
                },
            }

        except Exception as exc:
            return {
                "success": False,
                "data": None,
                "error": f"Failed to fetch feed: {str(exc)}",
                "metadata": {},
            }

    async def _aggregate_feeds(self, urls: list[str], limit: int) -> ToolResult:
        """Aggregate items from multiple feeds.

        Args:
            urls: List of feed URLs
            limit: Maximum number of total items

        Returns:
            ToolResult with aggregated items
        """
        if not urls:
            return {
                "success": False,
                "data": None,
                "error": "At least one feed URL is required",
                "metadata": {},
            }

        all_items = []
        errors = []

        for url in urls:
            try:
                result = await self._fetch_feed(url, limit=20)  # Fetch more for aggregation
                if result["success"]:
                    items = result["data"]["items"]
                    for item in items:
                        item["_source_feed"] = url
                    all_items.extend(items)
                else:
                    errors.append({"url": url, "error": result["error"]})
            except Exception as exc:
                errors.append({"url": url, "error": str(exc)})

        # Sort by date (newest first) and limit
        all_items.sort(key=lambda x: x.get("published", ""), reverse=True)
        aggregated_items = all_items[:limit]

        return {
            "success": True,
            "data": aggregated_items,
            "error": None,
            "metadata": {
                "feeds_count": len(urls),
                "total_items": len(aggregated_items),
                "errors": errors if errors else None,
            },
        }

    async def _discover_feeds(self, url: str) -> ToolResult:
        """Discover RSS/Atom feeds on a website.

        Args:
            url: Website URL to search for feeds

        Returns:
            ToolResult with discovered feeds
        """
        if not url:
            return {
                "success": False,
                "data": None,
                "error": "Website URL is required",
                "metadata": {},
            }

        import httpx

        # Common feed paths to check
        feed_paths = [
            "/feed",
            "/rss",
            "/atom.xml",
            "/feed.xml",
            "/rss.xml",
            "/index.xml",
            "/blog/feed",
            "/feed/rss",
        ]

        discovered_feeds = []

        # Parse base URL
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            # Check HTML page for feed links
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    # Look for feed links in HTML
                    import re
                    feed_links = re.findall(
                        r'<link[^>]+(?:type="application/rss\+xml"|type="application/atom\+xml")[^>]+href="([^"]+)"',
                        response.text,
                        re.IGNORECASE,
                    )

                    for feed_url in feed_links:
                        if feed_url.startswith("/"):
                            feed_url = base_url + feed_url
                        discovered_feeds.append({"url": feed_url, "method": "link_tag"})

            except Exception:
                pass

            # Check common feed paths
            for path in feed_paths:
                try:
                    feed_url = base_url + path
                    response = await client.head(feed_url)
                    if response.status_code == 200:
                        discovered_feeds.append({"url": feed_url, "method": "path_check"})
                except Exception:
                    pass

        return {
            "success": True,
            "data": discovered_feeds,
            "error": None,
            "metadata": {
                "website": url,
                "feeds_found": len(discovered_feeds),
            },
        }

    async def _get_feed_info(self, url: str) -> ToolResult:
        """Get information about a feed without fetching items.

        Args:
            url: Feed URL

        Returns:
            ToolResult with feed metadata
        """
        result = await self._fetch_feed(url, limit=0)
        if result["success"]:
            return {
                "success": True,
                "data": result["data"]["feed"],
                "error": None,
                "metadata": {"url": url},
            }
        return result

    def _extract_feed_info(self, feed) -> dict[str, Any]:
        """Extract metadata from parsed feed.

        Args:
            feed: Parsed feed object

        Returns:
            Dictionary with feed metadata
        """
        return {
            "title": getattr(feed, "title", ""),
            "description": getattr(feed, "description", ""),
            "link": getattr(feed, "link", ""),
            "language": getattr(feed, "language", ""),
            "ttl": getattr(feed, "ttl", None),
            "image": getattr(feed, "image", {}).get("href", "") if hasattr(feed, "image") else "",
            "last_updated": getattr(feed, "updated", "") or getattr(feed, "published", ""),
        }

    def _extract_items(self, entries: list) -> list[dict[str, Any]]:
        """Extract items from parsed feed entries.

        Args:
            entries: List of parsed feed entries

        Returns:
            List of item dictionaries
        """
        items = []

        for entry in entries:
            item = {
                "title": getattr(entry, "title", ""),
                "link": getattr(entry, "link", ""),
                "description": getattr(entry, "description", "") or getattr(entry, "summary", ""),
                "author": getattr(entry, "author", ""),
                "published": getattr(entry, "published", "") or getattr(entry, "updated", ""),
                "guid": getattr(entry, "id", "") or getattr(entry, "link", ""),
            }

            # Extract categories/tags
            if hasattr(entry, "tags"):
                item["tags"] = [tag.term for tag in entry.tags]

            # Extract media content
            if hasattr(entry, "media_content"):
                item["media"] = [
                    {"url": m.get("url"), "type": m.get("type")}
                    for m in entry.media_content
                    if m.get("url")
                ]

            # Extract enclosure (podcast/video)
            if hasattr(entry, "enclosures") and entry.enclosures:
                enclosure = entry.enclosures[0]
                item["enclosure"] = {
                    "url": enclosure.get("href", ""),
                    "type": enclosure.get("type", ""),
                    "length": enclosure.get("length", ""),
                }

            # Clean description
            if item.get("description"):
                # Remove HTML tags for clean text
                import re
                item["description"] = re.sub(r"<[^>]+>", "", item["description"])
                item["description"] = item["description"][:500]

            items.append(item)

        return items

    def _format_item_summary(self, item: dict) -> str:
        """Format a feed item into a readable summary string.

        Args:
            item: Item dictionary

        Returns:
            Formatted summary string
        """
        lines = [
            f"**{item.get('title', 'Untitled')}**",
        ]

        if item.get("author"):
            lines.append(f"By: {item['author']}")

        if item.get("published"):
            lines.append(f"Published: {item['published'][:10]}")

        if item.get("description"):
            lines.append(f"\n{item['description'][:200]}...")

        if item.get("link"):
            lines.append(f"\n[Read more]({item['link']})")

        return "\n".join(lines)


# Predefined feed sources for common topics
DEFAULT_FEED_SOURCES = {
    "tech": [
        "https://techcrunch.com/feed/",
        "https://www.theverge.com/rss/index.xml",
        "https://feeds.feedburner.com/TechCrunch/",
    ],
    "ai": [
        "https://blogs.nvidia.com/feed/",
        "https://blog.google/technology/ai/feed/",
        "https://blogs.bing.com/search/feed",
    ],
    "security": [
        "https://feeds.feedburner.com/TheHackersNews",
        "https://www.schneier.com/blog/feed/atom/",
    ],
    "programming": [
        "https://dev.to/feed",
        "https://feed.pythonpapers.org/people.html",
    ],
}


def get_topic_feeds(topic: str) -> list[str]:
    """Get predefined feed URLs for a topic.

    Args:
        topic: Topic name (e.g., 'tech', 'ai', 'security')

    Returns:
        List of feed URLs for the topic
    """
    return DEFAULT_FEED_SOURCES.get(topic.lower(), [])
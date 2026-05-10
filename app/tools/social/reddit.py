"""
Reddit monitoring tool.

This tool provides capabilities for monitoring Reddit subreddits,
tracking hot posts, and searching for relevant discussions.

Features:
- Get hot/new/top posts from subreddits
- Search posts by keyword
- Track posts about specific topics
- Monitor comment activity
"""

import re
from typing import Any, Optional

from app.tools.base import BaseTool, ToolCategory, ToolResult
from app.core.logging import get_logger


logger = get_logger(__name__)


class RedditTool(BaseTool):
    """Tool for Reddit monitoring and search.

    Provides functionality to monitor subreddits, get trending posts,
    and search for relevant discussions. Uses Reddit's public JSON API.

    Attributes:
        user_agent: User agent string for Reddit API requests
    """

    def __init__(self, user_agent: str = "tech-watch-agent/1.0") -> None:
        """Initialize Reddit tool.

        Args:
            user_agent: User agent string for API requests
        """
        super().__init__()
        self._user_agent = user_agent
        self._base_url = "https://www.reddit.com"

    @property
    def name(self) -> str:
        return "reddit"

    @property
    def description(self) -> str:
        return """Reddit monitoring tool for tracking subreddit discussions,
hot posts, and trending topics. Use this to find trending discussions,
monitor community reactions to news, or discover popular content in any topic."""

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
                    "enum": ["hot", "new", "top", "search", "subreddit_info"],
                    "description": "The Reddit action to perform",
                },
                "subreddit": {
                    "type": "string",
                    "description": "Subreddit name (e.g., 'technology', 'machinelearning')",
                },
                "query": {
                    "type": "string",
                    "description": "Search query (for search action)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (default: 10)",
                    "default": 10,
                },
                "time_range": {
                    "type": "string",
                    "enum": ["hour", "day", "week", "month", "year", "all"],
                    "description": "Time range for top posts (default: week)",
                    "default": "week",
                },
            },
            "required": ["action"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        """Execute Reddit monitoring action.

        Args:
            params: Action and parameters for Reddit operation

        Returns:
            ToolResult with Reddit data or error
        """
        action = params.get("action")
        subreddit = params.get("subreddit", "")
        query = params.get("query", "")
        limit = params.get("limit", 10)
        time_range = params.get("time_range", "week")

        try:
            if action == "hot":
                return await self._get_posts(subreddit, "hot", limit)
            elif action == "new":
                return await self._get_posts(subreddit, "new", limit)
            elif action == "top":
                return await self._get_posts(subreddit, "top", limit, time_range)
            elif action == "search":
                return await self._search_posts(query, subreddit, limit)
            elif action == "subreddit_info":
                return await self._get_subreddit_info(subreddit)
            else:
                return {
                    "success": False,
                    "data": None,
                    "error": f"Unknown action: {action}",
                    "metadata": {},
                }

        except Exception as exc:
            logger.error("Reddit tool error: %s", exc)
            return {
                "success": False,
                "data": None,
                "error": str(exc),
                "metadata": {},
            }

    async def _get_posts(
        self,
        subreddit: str,
        sort: str,
        limit: int,
        time_range: Optional[str] = None,
    ) -> ToolResult:
        """Get posts from a subreddit.

        Args:
            subreddit: Subreddit name
            sort: Sort type (hot, new, top)
            limit: Maximum results
            time_range: Time range for top posts

        Returns:
            ToolResult with post list
        """
        if not subreddit:
            return {
                "success": False,
                "data": None,
                "error": "Subreddit is required",
                "metadata": {},
            }

        import httpx

        # Build URL
        url = f"{self._base_url}/r/{subreddit}/{sort}.json"
        params = {"limit": limit}
        if sort == "top" and time_range:
            params["t"] = time_range

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                url,
                params=params,
                headers={"User-Agent": self._user_agent},
            )

        if response.status_code != 200:
            return {
                "success": False,
                "data": None,
                "error": f"Reddit API error: {response.status_code}",
                "metadata": {},
            }

        data = response.json()
        posts = self._parse_posts(data)

        return {
            "success": True,
            "data": posts,
            "error": None,
            "metadata": {"subreddit": subreddit, "sort": sort, "count": len(posts)},
        }

    async def _search_posts(
        self,
        query: str,
        subreddit: Optional[str],
        limit: int,
    ) -> ToolResult:
        """Search posts on Reddit.

        Args:
            query: Search query
            subreddit: Optional subreddit to limit search
            limit: Maximum results

        Returns:
            ToolResult with search results
        """
        if not query:
            return {
                "success": False,
                "data": None,
                "error": "Search query is required",
                "metadata": {},
            }

        import httpx

        # Build search URL
        url = f"{self._base_url}/search.json"
        params = {
            "q": query,
            "limit": limit,
            "sort": "relevance",
        }
        if subreddit:
            params["restrict_sr"] = "on"
            params["sr_name"] = subreddit

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                url,
                params=params,
                headers={"User-Agent": self._user_agent},
            )

        if response.status_code != 200:
            return {
                "success": False,
                "data": None,
                "error": f"Reddit API error: {response.status_code}",
                "metadata": {},
            }

        data = response.json()
        posts = self._parse_posts(data)

        return {
            "success": True,
            "data": posts,
            "error": None,
            "metadata": {"query": query, "subreddit": subreddit, "count": len(posts)},
        }

    async def _get_subreddit_info(self, subreddit: str) -> ToolResult:
        """Get subreddit information.

        Args:
            subreddit: Subreddit name

        Returns:
            ToolResult with subreddit details
        """
        if not subreddit:
            return {
                "success": False,
                "data": None,
                "error": "Subreddit is required",
                "metadata": {},
            }

        import httpx

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self._base_url}/r/{subreddit}/about.json",
                headers={"User-Agent": self._user_agent},
            )

        if response.status_code != 200:
            return {
                "success": False,
                "data": None,
                "error": f"Reddit API error: {response.status_code}",
                "metadata": {},
            }

        data = response.json().get("data", {})

        if not data or data.get("error"):
            return {
                "success": False,
                "data": None,
                "error": "Subreddit not found",
                "metadata": {},
            }

        info = {
            "name": data.get("display_name", ""),
            "title": data.get("title", ""),
            "description": data.get("public_description", ""),
            "subscribers": data.get("subscribers", 0),
            "active_users": data.get("active_user_count", 0),
            "url": f"https://reddit.com/r/{data.get('display_name', '')}",
            "created": data.get("created_utc", 0),
        }

        return {
            "success": True,
            "data": info,
            "error": None,
            "metadata": {"subreddit": subreddit},
        }

    def _parse_posts(self, data: dict) -> list[dict[str, Any]]:
        """Parse Reddit API response into simplified post format.

        Args:
            data: Raw Reddit API response

        Returns:
            List of simplified post dictionaries
        """
        posts = []
        children = data.get("data", {}).get("children", [])

        for child in children:
            post_data = child.get("data", {})
            if not post_data:
                continue

            # Extract post information
            post = {
                "id": post_data.get("id", ""),
                "title": post_data.get("title", ""),
                "score": post_data.get("score", 0),
                "num_comments": post_data.get("num_comments", 0),
                "author": post_data.get("author", ""),
                "subreddit": post_data.get("subreddit", ""),
                "url": post_data.get("url", ""),
                "permalink": f"https://reddit.com{post_data.get('permalink', '')}",
                "created": post_data.get("created_utc", 0),
                "selftext": post_data.get("selftext", "")[:500] if post_data.get("selftext") else "",
                "link_flair_text": post_data.get("link_flair_text", ""),
            }

            # Add thumbnail if available
            thumbnail = post_data.get("thumbnail", "")
            if thumbnail and thumbnail.startswith("http"):
                post["thumbnail"] = thumbnail

            # Add preview images if available
            preview = post_data.get("preview", {})
            if preview:
                images = preview.get("images", [])
                if images:
                    post["preview_url"] = images[0].get("source", {}).get("url", "")

            posts.append(post)

        return posts

    def _format_post_summary(self, post: dict) -> str:
        """Format a post into a readable summary string.

        Args:
            post: Post dictionary

        Returns:
            Formatted summary string
        """
        lines = [
            f"**{post['title']}**",
            f"Score: {post['score']} | Comments: {post['num_comments']}",
            f"By: {post['author']} in r/{post['subreddit']}",
        ]
        if post.get("selftext"):
            lines.append(f"\n{post['selftext'][:200]}...")
        lines.append(f"\n[Link]({post['permalink']})")

        return "\n".join(lines)
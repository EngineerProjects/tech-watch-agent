"""
Social media monitoring tools initialization.

This module exports tools for monitoring social platforms:
- GitHub: Repository updates, trending repos, issues
- Reddit: Subreddit monitoring, hot posts
- ArXiv: Academic paper discovery
- RSS: RSS/Atom feed aggregation
- YouTube: Video transcript extraction
"""

from app.tools.social.github import GitHubTool
from app.tools.social.reddit import RedditTool
from app.tools.social.arxiv import ArXivTool
from app.tools.social.rss import RSSTool
from app.tools.social.youtube import YouTubeTool, is_valid_youtube_url, format_duration

__all__ = [
    "GitHubTool",
    "RedditTool",
    "ArXivTool",
    "RSSTool",
    "YouTubeTool",
    "is_valid_youtube_url",
    "format_duration",
]
"""
Social media monitoring tools initialization.

This module exports tools for monitoring social platforms:
- GitHub: Repository updates, trending repos, issues
- Reddit: Subreddit monitoring, hot posts
- ArXiv: Academic paper discovery
- RSS: RSS/Atom feed aggregation
"""

from app.tools.social.github import GitHubTool
from app.tools.social.reddit import RedditTool
from app.tools.social.arxiv import ArXivTool
from app.tools.social.rss import RSSTool

__all__ = [
    "GitHubTool",
    "RedditTool",
    "ArXivTool",
    "RSSTool",
]
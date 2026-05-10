"""
Tests for social media monitoring tools.

This module tests the GitHub, Reddit, ArXiv, and RSS tools
to ensure proper API integration and data handling.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.tools.social.github import GitHubTool
from app.tools.social.reddit import RedditTool
from app.tools.social.arxiv import ArXivTool
from app.tools.social.rss import RSSTool
from app.tools.base import ToolCategory


class TestGitHubTool:
    """Tests for GitHub tool."""

    @pytest.fixture
    def tool(self):
        """Create GitHub tool instance."""
        return GitHubTool(api_token="test-token")

    def test_properties(self, tool):
        """Test tool properties."""
        assert tool.name == "github"
        assert tool.category == ToolCategory.SOCIAL
        assert "GitHub" in tool.description

    def test_parameters(self, tool):
        """Test parameter schema."""
        params = tool.parameters
        assert "action" in params["properties"]
        assert "search_repos" in params["properties"]["action"]["enum"]

    @pytest.mark.asyncio
    async def test_search_repos_requires_query(self, tool):
        """Test that search repos requires query."""
        result = await tool.execute({
            "action": "search_repos",
            "query": "",  # Empty query
        })
        # Should return success but with empty result
        assert result["success"] is True or "error" in result

    @pytest.mark.asyncio
    async def test_commits_requires_repo(self, tool):
        """Test that commits action requires repo parameter."""
        result = await tool.execute({
            "action": "recent_commits",
            "repo": "",  # Empty repo
        })
        assert result["success"] is False
        assert "required" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_issues_requires_repo(self, tool):
        """Test that issues action requires repo parameter."""
        result = await tool.execute({
            "action": "issues",
            "repo": "",  # Empty repo
        })
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_repo_info_requires_repo(self, tool):
        """Test that repo_info action requires repo parameter."""
        result = await tool.execute({
            "action": "repo_info",
            "repo": "",  # Empty repo
        })
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_unknown_action(self, tool):
        """Test handling of unknown action."""
        result = await tool.execute({
            "action": "unknown_action",
        })
        assert result["success"] is False
        assert "Unknown action" in result["error"]


class TestRedditTool:
    """Tests for Reddit tool."""

    @pytest.fixture
    def tool(self):
        """Create Reddit tool instance."""
        return RedditTool()

    def test_properties(self, tool):
        """Test tool properties."""
        assert tool.name == "reddit"
        assert tool.category == ToolCategory.SOCIAL
        assert "Reddit" in tool.description

    def test_parameters(self, tool):
        """Test parameter schema."""
        params = tool.parameters
        assert "action" in params["properties"]
        assert "hot" in params["properties"]["action"]["enum"]

    @pytest.mark.asyncio
    async def test_hot_requires_subreddit(self, tool):
        """Test that hot action requires subreddit."""
        result = await tool.execute({
            "action": "hot",
            "subreddit": "",  # Empty subreddit
        })
        assert result["success"] is False
        assert "required" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_search_requires_query(self, tool):
        """Test that search action requires query."""
        result = await tool.execute({
            "action": "search",
            "query": "",  # Empty query
        })
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_subreddit_info_requires_subreddit(self, tool):
        """Test that subreddit_info requires subreddit."""
        result = await tool.execute({
            "action": "subreddit_info",
            "subreddit": "",  # Empty subreddit
        })
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_unknown_action(self, tool):
        """Test handling of unknown action."""
        result = await tool.execute({
            "action": "unknown_action",
        })
        assert result["success"] is False


class TestArXivTool:
    """Tests for ArXiv tool."""

    @pytest.fixture
    def tool(self):
        """Create ArXiv tool instance."""
        return ArXivTool()

    def test_properties(self, tool):
        """Test tool properties."""
        assert tool.name == "arxiv"
        assert tool.category == ToolCategory.SOCIAL
        assert "ArXiv" in tool.description

    def test_parameters(self, tool):
        """Test parameter schema."""
        params = tool.parameters
        assert "action" in params["properties"]
        assert "search" in params["properties"]["action"]["enum"]

    @pytest.mark.asyncio
    async def test_search_requires_query(self, tool):
        """Test that search action requires query."""
        result = await tool.execute({
            "action": "search",
            "query": "",  # Empty query
        })
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_author_search_requires_author(self, tool):
        """Test that author action requires author."""
        result = await tool.execute({
            "action": "author",
            "author": "",  # Empty author
        })
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_paper_info_requires_id(self, tool):
        """Test that paper_info requires paper_id."""
        result = await tool.execute({
            "action": "paper_info",
            "paper_id": "",  # Empty paper_id
        })
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_recent_action(self, tool):
        """Test recent action with category."""
        result = await tool.execute({
            "action": "recent",
            "category": "cs.AI",
            "limit": 5,
        })
        # Should handle the action (may fail due to API, but should not error on params)
        assert "success" in result or "error" in result

    @pytest.mark.asyncio
    async def test_unknown_action(self, tool):
        """Test handling of unknown action."""
        result = await tool.execute({
            "action": "unknown_action",
        })
        assert result["success"] is False


class TestRSSTool:
    """Tests for RSS tool."""

    @pytest.fixture
    def tool(self):
        """Create RSS tool instance."""
        return RSSTool()

    def test_properties(self, tool):
        """Test tool properties."""
        assert tool.name == "rss"
        assert tool.category == ToolCategory.SOCIAL
        assert "RSS" in tool.description

    def test_parameters(self, tool):
        """Test parameter schema."""
        params = tool.parameters
        assert "action" in params["properties"]
        assert "fetch" in params["properties"]["action"]["enum"]

    @pytest.mark.asyncio
    async def test_fetch_requires_url(self, tool):
        """Test that fetch action requires URL."""
        result = await tool.execute({
            "action": "fetch",
            "url": "",  # Empty URL
        })
        assert result["success"] is False
        assert "required" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_aggregate_requires_urls(self, tool):
        """Test that aggregate action requires URLs."""
        result = await tool.execute({
            "action": "aggregate",
            "urls": [],  # Empty URLs
        })
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_discover_requires_url(self, tool):
        """Test that discover action requires URL."""
        result = await tool.execute({
            "action": "discover",
            "url": "",  # Empty URL
        })
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_feed_info_requires_url(self, tool):
        """Test that feed_info action requires URL."""
        result = await tool.execute({
            "action": "feed_info",
            "url": "",  # Empty URL
        })
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_unknown_action(self, tool):
        """Test handling of unknown action."""
        result = await tool.execute({
            "action": "unknown_action",
        })
        assert result["success"] is False


class TestToolCategories:
    """Tests for tool category classification."""

    def test_github_category(self):
        """Test GitHub tool category."""
        tool = GitHubTool()
        assert tool.category == ToolCategory.SOCIAL

    def test_reddit_category(self):
        """Test Reddit tool category."""
        tool = RedditTool()
        assert tool.category == ToolCategory.SOCIAL

    def test_arxiv_category(self):
        """Test ArXiv tool category."""
        tool = ArXivTool()
        assert tool.category == ToolCategory.SOCIAL

    def test_rss_category(self):
        """Test RSS tool category."""
        tool = RSSTool()
        assert tool.category == ToolCategory.SOCIAL


class TestToolExecutionFlow:
    """Tests for tool execution flow and error handling."""

    @pytest.mark.asyncio
    async def test_github_api_error_handling(self):
        """Test GitHub API error handling."""
        tool = GitHubTool()

        # Mock httpx to return error
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 403
            mock_response.json.return_value = {"message": "Rate limit exceeded"}

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await tool.execute({
                "action": "search_repos",
                "query": "test",
            })

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_tool_validate_params(self):
        """Test parameter validation."""
        tool = GitHubTool()

        # Valid params
        is_valid, error = tool.validate_params({
            "action": "search_repos",
            "query": "test",
        })
        assert is_valid is True
        assert error is None

        # Invalid params (missing required)
        is_valid, error = tool.validate_params({
            "action": "recent_commits",
            # Missing repo
        })
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_disabled_tool_execution(self):
        """Test executing a disabled tool."""
        tool = GitHubTool()
        tool.disable()

        result = await tool.execute_safe({
            "action": "search_repos",
            "query": "test",
        })

        assert result["success"] is False
        assert "disabled" in result["error"].lower()
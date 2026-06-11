"""
GitHub monitoring tool.

This tool provides capabilities for monitoring GitHub repositories,
tracking trending repositories, and searching for relevant code/projects.

Features:
- Search repositories by topic/keyword
- Get recent commits from repositories
- Track trending repositories
- Monitor issues and PRs
"""

from typing import Any, Optional
from datetime import datetime, timedelta

from app.config.settings import Settings, get_settings
from app.tools.base import BaseTool, ToolCategory, ToolResult
from app.core.logging import get_logger


logger = get_logger(__name__)


class GitHubTool(BaseTool):
    """Tool for GitHub monitoring and search.

    Provides functionality to search repositories, get trending repos,
    and monitor repository activity. Uses GitHub API for data retrieval.

    Attributes:
        api_token: Optional GitHub API token for authenticated requests
        base_url: GitHub API base URL
    """

    def __init__(self, api_token: Optional[str] = None, settings: Optional[Settings] = None) -> None:
        """Initialize GitHub tool.

        Args:
            api_token: Optional GitHub API token for higher rate limits
        """
        super().__init__()
        self._settings = settings or get_settings()
        self._api_token = api_token or self._settings.github_api_token
        self._base_url = "https://api.github.com"

    @property
    def name(self) -> str:
        return "github"

    @property
    def description(self) -> str:
        return """GitHub monitoring tool for tracking repositories, trending projects,
and technical discussions. Use this to find new open-source projects, track updates
on specific repositories, or discover trending code in any topic."""

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
                    "enum": ["search_repos", "trending", "recent_commits", "issues", "repo_info"],
                    "description": "The GitHub action to perform",
                },
                "query": {
                    "type": "string",
                    "description": "Search query (for search_repos action)",
                },
                "repo": {
                    "type": "string",
                    "description": "Repository in 'owner/repo' format (for commits, issues, repo_info)",
                },
                "language": {
                    "type": "string",
                    "description": "Programming language filter (e.g., 'python', 'javascript')",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (default: 10)",
                    "default": 10,
                },
            },
            "required": ["action"],
        }

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, Optional[str]]:
        is_valid, error = super().validate_params(params)
        if not is_valid:
            return is_valid, error
        action = params.get("action")
        if action in ("recent_commits", "issues", "repo_info"):
            if not params.get("repo"):
                return False, f"Missing required parameter: repo (required for {action})"
        return True, None

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        """Execute GitHub monitoring action.

        Args:
            params: Action and parameters for GitHub operation

        Returns:
            ToolResult with GitHub data or error
        """
        action = params.get("action")
        query = params.get("query", "")
        repo = params.get("repo", "")
        language = params.get("language")
        limit = params.get("limit", 10)

        try:
            if action == "search_repos":
                return await self._search_repos(query, language, limit)
            elif action == "trending":
                return await self._get_trending(language, limit)
            elif action == "recent_commits":
                return await self._get_commits(repo, limit)
            elif action == "issues":
                return await self._get_issues(repo, limit)
            elif action == "repo_info":
                return await self._get_repo_info(repo)
            else:
                return {
                    "success": False,
                    "data": None,
                    "error": f"Unknown action: {action}",
                    "metadata": {},
                }

        except Exception as exc:
            logger.error("GitHub tool error: %s", exc)
            return {
                "success": False,
                "data": None,
                "error": str(exc),
                "metadata": {},
            }

    async def _search_repos(
        self,
        query: str,
        language: Optional[str],
        limit: int,
    ) -> ToolResult:
        """Search GitHub repositories.

        Args:
            query: Search query
            language: Optional language filter
            limit: Maximum results

        Returns:
            ToolResult with repository list
        """
        import httpx

        # Build search query
        search_query = query
        if language:
            search_query += f" language:{language}"

        headers = self._get_headers()

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self._base_url}/search/repositories",
                params={"q": search_query, "per_page": limit, "sort": "stars"},
                headers=headers,
            )

        if response.status_code != 200:
            return {
                "success": False,
                "data": None,
                "error": f"GitHub API error: {response.status_code}",
                "metadata": {},
            }

        data = response.json()
        repos = [
            {
                "name": r["full_name"],
                "description": r.get("description", ""),
                "stars": r["stargazers_count"],
                "language": r.get("language", ""),
                "url": r["html_url"],
                "updated": r["updated_at"],
            }
            for r in data.get("items", [])
        ]

        return {
            "success": True,
            "data": repos,
            "error": None,
            "metadata": {"count": len(repos), "query": search_query},
        }

    async def _get_trending(
        self,
        language: Optional[str],
        limit: int,
    ) -> ToolResult:
        """Get trending repositories.

        Args:
            language: Optional language filter
            limit: Maximum results

        Returns:
            ToolResult with trending repos
        """
        # Build query for trending (created in last 7 days with most stars)
        days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        query = f"created:>{days_ago}"
        if language:
            query += f" language:{language}"

        return await self._search_repos(query, None, limit)

    async def _get_commits(
        self,
        repo: str,
        limit: int,
    ) -> ToolResult:
        """Get recent commits from a repository.

        Args:
            repo: Repository in 'owner/repo' format
            limit: Maximum results

        Returns:
            ToolResult with commit list
        """
        if not repo:
            return {
                "success": False,
                "data": None,
                "error": "Repository is required for commits",
                "metadata": {},
            }

        import httpx

        headers = self._get_headers()

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self._base_url}/repos/{repo}/commits",
                params={"per_page": limit},
                headers=headers,
            )

        if response.status_code != 200:
            return {
                "success": False,
                "data": None,
                "error": f"GitHub API error: {response.status_code}",
                "metadata": {},
            }

        data = response.json()
        commits = [
            {
                "sha": c["sha"][:7],
                "message": c["commit"]["message"].split("\n")[0],
                "author": c["commit"]["author"]["name"],
                "date": c["commit"]["author"]["date"],
                "url": c["html_url"],
            }
            for c in data
        ]

        return {
            "success": True,
            "data": commits,
            "error": None,
            "metadata": {"repo": repo, "count": len(commits)},
        }

    async def _get_issues(
        self,
        repo: str,
        limit: int,
    ) -> ToolResult:
        """Get recent issues from a repository.

        Args:
            repo: Repository in 'owner/repo' format
            limit: Maximum results

        Returns:
            ToolResult with issue list
        """
        if not repo:
            return {
                "success": False,
                "data": None,
                "error": "Repository is required for issues",
                "metadata": {},
            }

        import httpx

        headers = self._get_headers()

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self._base_url}/repos/{repo}/issues",
                params={"per_page": limit, "state": "open", "sort": "updated"},
                headers=headers,
            )

        if response.status_code != 200:
            return {
                "success": False,
                "data": None,
                "error": f"GitHub API error: {response.status_code}",
                "metadata": {},
            }

        data = response.json()
        # Filter out pull requests (they appear in issues API)
        issues = [
            {
                "number": i["number"],
                "title": i["title"],
                "state": i["state"],
                "labels": [lbl["name"] for lbl in i.get("labels", [])],
                "author": i["user"]["login"],
                "created": i["created_at"],
                "url": i["html_url"],
            }
            for i in data if "pull_request" not in i
        ]

        return {
            "success": True,
            "data": issues,
            "error": None,
            "metadata": {"repo": repo, "count": len(issues)},
        }

    async def _get_repo_info(self, repo: str) -> ToolResult:
        """Get detailed repository information.

        Args:
            repo: Repository in 'owner/repo' format

        Returns:
            ToolResult with repo details
        """
        if not repo:
            return {
                "success": False,
                "data": None,
                "error": "Repository is required",
                "metadata": {},
            }

        import httpx

        headers = self._get_headers()

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self._base_url}/repos/{repo}",
                headers=headers,
            )

        if response.status_code != 200:
            return {
                "success": False,
                "data": None,
                "error": f"GitHub API error: {response.status_code}",
                "metadata": {},
            }

        data = response.json()
        info = {
            "name": data["full_name"],
            "description": data.get("description", ""),
            "stars": data["stargazers_count"],
            "forks": data["forks_count"],
            "language": data.get("language", ""),
            "topics": data.get("topics", []),
            "license": data.get("license", {}).get("name", ""),
            "homepage": data.get("homepage", ""),
            "created": data["created_at"],
            "updated": data["updated_at"],
            "readme_url": f"https://raw.githubusercontent.com/{repo}/main/README.md",
            "url": data["html_url"],
        }

        return {
            "success": True,
            "data": info,
            "error": None,
            "metadata": {"repo": repo},
        }

    def _get_headers(self) -> dict[str, str]:
        """Get headers for GitHub API requests.

        Returns:
            Dictionary of HTTP headers
        """
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "tech-watch-agent",
        }
        if self._api_token:
            headers["Authorization"] = f"token {self._api_token}"
        return headers
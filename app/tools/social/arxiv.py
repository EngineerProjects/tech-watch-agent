"""
ArXiv monitoring tool.

This tool provides capabilities for discovering and tracking academic papers
from ArXiv, the largest open-access preprint repository.

Features:
- Search papers by topic/keyword
- Get recent papers by category
- Track papers by author
- Fetch paper metadata and abstracts
"""

import re
from typing import Any, Optional
from datetime import datetime

from app.tools.base import BaseTool, ToolCategory, ToolResult
from app.core.logging import get_logger


logger = get_logger(__name__)


class ArXivTool(BaseTool):
    """Tool for ArXiv paper discovery and monitoring.

    Provides functionality to search academic papers, get recent publications,
    and track research trends. Uses ArXiv's Atom feed API.

    Attributes:
        base_url: ArXiv API base URL
    """

    def __init__(self) -> None:
        """Initialize ArXiv tool."""
        super().__init__()
        self._base_url = "https://export.arxiv.org/api/query"

    @property
    def name(self) -> str:
        return "arxiv"

    @property
    def description(self) -> str:
        return """ArXiv monitoring tool for discovering academic papers and
research publications. Use this to find cutting-edge research, track
new publications in specific fields, or discover foundational papers."""

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
                    "enum": ["search", "recent", "author", "paper_info"],
                    "description": "The ArXiv action to perform",
                },
                "query": {
                    "type": "string",
                    "description": "Search query (for search action)",
                },
                "category": {
                    "type": "string",
                    "description": "ArXiv category (e.g., 'cs.AI', 'cs.LG', 'stat.ML')",
                },
                "author": {
                    "type": "string",
                    "description": "Author name (for author action)",
                },
                "paper_id": {
                    "type": "string",
                    "description": "ArXiv paper ID (for paper_info action)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (default: 10)",
                    "default": 10,
                },
                "sort_by": {
                    "type": "string",
                    "enum": ["relevance", "lastUpdatedDate", "submittedDate"],
                    "description": "Sort order for results",
                    "default": "relevance",
                },
            },
            "required": ["action"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        """Execute ArXiv monitoring action.

        Args:
            params: Action and parameters for ArXiv operation

        Returns:
            ToolResult with ArXiv data or error
        """
        action = params.get("action") or "search"
        query = params.get("query", "")
        category = params.get("category", "")
        author = params.get("author", "")
        paper_id = params.get("paper_id", "")
        limit = params.get("limit", 10)
        sort_by = params.get("sort_by", "relevance")

        try:
            if action == "search":
                return await self._search_papers(query, category, limit, sort_by)
            elif action == "recent":
                return await self._get_recent(category, limit)
            elif action == "author":
                return await self._search_by_author(author, limit)
            elif action == "paper_info":
                return await self._get_paper_info(paper_id)
            else:
                return {
                    "success": False,
                    "data": None,
                    "error": f"Unknown action: {action}",
                    "metadata": {},
                }

        except Exception as exc:
            logger.error("ArXiv tool error: %s", exc)
            return {
                "success": False,
                "data": None,
                "error": str(exc),
                "metadata": {},
            }

    async def _search_papers(
        self,
        query: str,
        category: str,
        limit: int,
        sort_by: str,
    ) -> ToolResult:
        """Search for papers on ArXiv.

        Args:
            query: Search query
            category: Optional category filter
            limit: Maximum results
            sort_by: Sort order

        Returns:
            ToolResult with paper list
        """
        if not query:
            return {
                "success": False,
                "data": None,
                "error": "Search query is required",
                "metadata": {},
            }

        # Build search query
        search_query = query
        if category:
            search_query += f" AND cat:{category}"

        return await self._query_arxiv(search_query, limit, sort_by)

    async def _get_recent(
        self,
        category: str,
        limit: int,
    ) -> ToolResult:
        """Get recent papers, optionally filtered by category.

        Args:
            category: Optional category filter
            limit: Maximum results

        Returns:
            ToolResult with recent papers
        """
        query = f"cat:{category}" if category else "all"
        return await self._query_arxiv(query, limit, "submittedDate")

    async def _search_by_author(
        self,
        author: str,
        limit: int,
    ) -> ToolResult:
        """Search papers by author name.

        Args:
            author: Author name
            limit: Maximum results

        Returns:
            ToolResult with author's papers
        """
        if not author:
            return {
                "success": False,
                "data": None,
                "error": "Author name is required",
                "metadata": {},
            }

        search_query = f"au:{author}"
        return await self._query_arxiv(search_query, limit, "relevance")

    async def _get_paper_info(self, paper_id: str) -> ToolResult:
        """Get detailed information about a paper.

        Args:
            paper_id: ArXiv paper ID (e.g., '2301.12345')

        Returns:
            ToolResult with paper details
        """
        if not paper_id:
            return {
                "success": False,
                "data": None,
                "error": "Paper ID is required",
                "metadata": {},
            }

        # Clean paper ID
        paper_id = paper_id.strip()
        if not paper_id.startswith("arxiv:"):
            paper_id = f"arxiv:{paper_id}"

        import httpx

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(
                self._base_url,
                params={"id_list": paper_id.replace("arxiv:", "")},
            )

        if response.status_code != 200:
            return {
                "success": False,
                "data": None,
                "error": f"ArXiv API error: {response.status_code}",
                "metadata": {},
            }

        papers = self._parse_atom_feed(response.text)
        if papers:
            return {
                "success": True,
                "data": papers[0],
                "error": None,
                "metadata": {"paper_id": paper_id},
            }

        return {
            "success": False,
            "data": None,
            "error": "Paper not found",
            "metadata": {},
        }

    async def _query_arxiv(
        self,
        search_query: str,
        limit: int,
        sort_by: str,
    ) -> ToolResult:
        """Execute a query against ArXiv API.

        Args:
            search_query: ArXiv search query
            limit: Maximum results
            sort_by: Sort order

        Returns:
            ToolResult with query results
        """
        import httpx

        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            response = await client.get(
                self._base_url,
                params={
                    "search_query": search_query,
                    "start": 0,
                    "max_results": limit,
                    "sortBy": sort_by,
                    "sortOrder": "descending",
                },
            )

        if response.status_code != 200:
            return {
                "success": False,
                "data": None,
                "error": f"ArXiv API error: {response.status_code}",
                "metadata": {},
            }

        papers = self._parse_atom_feed(response.text)

        return {
            "success": True,
            "data": papers,
            "error": None,
            "metadata": {"query": search_query, "count": len(papers)},
        }

    def _parse_atom_feed(self, xml_content: str) -> list[dict[str, Any]]:
        """Parse ArXiv Atom feed into simplified format.

        Args:
            xml_content: Raw XML content from ArXiv API

        Returns:
            List of simplified paper dictionaries
        """
        papers = []

        # Simple XML parsing without external dependencies
        # Extract entry blocks
        entries = re.findall(r"<entry>(.*?)</entry>", xml_content, re.DOTALL)

        for entry in entries:
            paper = {}

            # Extract ID
            id_match = re.search(r"<id>(.*?)</id>", entry)
            if id_match:
                paper["id"] = id_match.group(1).split("/")[-1]
                paper["url"] = id_match.group(1)

            # Extract title
            title_match = re.search(r"<title>(.*?)</title>", entry, re.DOTALL)
            if title_match:
                paper["title"] = self._clean_text(title_match.group(1))

            # Extract summary/abstract
            summary_match = re.search(r"<summary>(.*?)</summary>", entry, re.DOTALL)
            if summary_match:
                paper["abstract"] = self._clean_text(summary_match.group(1))[:500]

            # Extract authors
            authors = re.findall(r"<name>(.*?)</name>", entry)
            paper["authors"] = [self._clean_text(a) for a in authors]

            # Extract published date
            published_match = re.search(r"<published>(.*?)</published>", entry)
            if published_match:
                paper["published"] = published_match.group(1)[:10]

            # Extract updated date
            updated_match = re.search(r"<updated>(.*?)</updated>", entry)
            if updated_match:
                paper["updated"] = updated_match.group(1)[:10]

            # Extract category
            categories = re.findall(r"<category term=\"([^\"]+)\"", entry)
            if categories:
                paper["categories"] = categories

            # Extract comment
            comment_match = re.search(r"<arxiv:comment>(.*?)</arxiv:comment>", entry)
            if comment_match:
                paper["comments"] = self._clean_text(comment_match.group(1))

            # Extract journal reference
            journal_match = re.search(r"<arxiv:journal_ref>(.*?)</arxiv:journal_ref>", entry)
            if journal_match:
                paper["journal_ref"] = self._clean_text(journal_match.group(1))

            papers.append(paper)

        return papers

    @staticmethod
    def _clean_text(text: str) -> str:
        """Clean and normalize text from XML.

        Args:
            text: Raw text with possible newlines

        Returns:
            Cleaned text
        """
        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _format_paper_summary(self, paper: dict) -> str:
        """Format a paper into a readable summary string.

        Args:
            paper: Paper dictionary

        Returns:
            Formatted summary string
        """
        lines = [
            f"**{paper.get('title', 'Untitled')}**",
            f"Authors: {', '.join(paper.get('authors', [])[:3])}",
            f"Published: {paper.get('published', 'Unknown')}",
        ]

        if paper.get("abstract"):
            lines.append(f"\nAbstract: {paper['abstract'][:300]}...")

        if paper.get("url"):
            lines.append(f"\n[Read on ArXiv]({paper['url']})")

        return "\n".join(lines)


# Category mapping for common research areas
ARXIV_CATEGORIES = {
    "cs.AI": "Artificial Intelligence",
    "cs.LG": "Machine Learning",
    "cs.CL": "Computation and Language",
    "cs.CV": "Computer Vision and Pattern Recognition",
    "cs.NE": "Neural and Evolutionary Computing",
    "cs.RO": "Robotics",
    "cs.CL": "Computational Complexity",
    "stat.ML": "Machine Learning (Statistics)",
    "math.ST": "Statistics Theory",
    "q-bio": "Quantitative Biology",
    "q-fin": "Quantitative Finance",
}


def get_category_description(category: str) -> str:
    """Get human-readable description for an ArXiv category.

    Args:
        category: ArXiv category code

    Returns:
        Description or the category itself if not found
    """
    return ARXIV_CATEGORIES.get(category, category)
"""
OpenAlex search tool for academic research.

OpenAlex is a free and open-source alternative to Google Scholar.
It provides a comprehensive index of scholarly works, authors, venues, and institutions.
"""

from __future__ import annotations

import httpx
from typing import Any, Optional, Dict, List

from app.tools.base import BaseTool, ToolCategory, ToolResult
from app.core.logging import get_logger


logger = get_logger(__name__)


OPENALEX_API_URL = "https://api.openAlex.org/works"


class OpenAlexTool(BaseTool):
    """Tool for searching academic publications via OpenAlex API.

    OpenAlex is a fully open database of the world's scholarly papers,
    researchers, journals, and institutions.
    """

    @property
    def name(self) -> str:
        return "openalex"

    @property
    def description(self) -> str:
        return """Search OpenAlex for academic publications and research papers.
OpenAlex is a free and open alternative to Google Scholar.
Use this to find peer-reviewed articles, citations, and scholarly information.

Best for: free academic research, finding foundational papers, citation analysis."""

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SEARCH

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The academic search query",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (default: 10)",
                    "default": 10,
                },
            },
            "required": ["query"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        query = params.get("query", "")
        limit = params.get("limit", 10)

        if not query:
            return {
                "success": False,
                "data": None,
                "error": "No query provided",
                "metadata": {},
            }

        params = {
            "search": query,
            "per_page": min(limit, 50),
        }

        # OpenAlex requests you include an email to be in their "polite" pool
        headers = {
            "User-Agent": "tech-watch-agent (https://github.com/amiche/tech-watch-agent; mailto:projectsengineer6@gmail.com)"
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    OPENALEX_API_URL,
                    params=params,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            logger.error("OpenAlex request failed: %s", exc)
            return {
                "success": False,
                "data": None,
                "error": str(exc),
                "metadata": {},
            }

        results = data.get("results", [])
        formatted_results = []
        
        for idx, item in enumerate(results, 1):
            title = item.get('display_name', 'No title')
            link = item.get('doi', '') or item.get('ids', {}).get('mag', '')
            pdf_url = item.get('open_access', {}).get('oa_url', '')
            
            # Extract authors
            authors = [a.get('author', {}).get('display_name', '') for a in item.get('authorships', [])[:3]]
            
            publication_year = item.get('publication_year', '')
            cited_by = item.get('cited_by_count', 0)
            
            # Abstract is sometimes available in a weird inverted index format
            # For simplicity, we'll skip the full abstract reconstruction here
            # or just take the snippet if available.

            result_item = {
                "index": idx,
                "title": title,
                "url": link,
                "pdf_url": pdf_url,
                "authors": authors,
                "year": publication_year,
                "cited_by": cited_by,
            }
            formatted_results.append(result_item)

        return {
            "success": True,
            "data": {
                "query": query,
                "results": formatted_results,
                "count": len(formatted_results)
            },
            "error": None,
            "metadata": {
                "query": query,
                "result_count": len(formatted_results),
                "provider": "openalex"
            },
        }

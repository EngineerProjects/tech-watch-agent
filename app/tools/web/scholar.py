"""
Google Scholar search tool for academic research.

Uses Serper API to retrieve relevant information from academic publications.
"""

from __future__ import annotations

import json
import httpx
from typing import Any, Optional, Dict, List

from app.tools.base import BaseTool, ToolCategory, ToolResult
from app.config.settings import Settings, get_settings
from app.core.logging import get_logger


logger = get_logger(__name__)


SERPER_SCHOLAR_URL = "google.serper.dev"


class GoogleScholarTool(BaseTool):
    """Tool for searching academic publications via Google Scholar.

    Uses the Serper.dev API to access Google Scholar results, including:
    - Publication titles and authors
    - Publication year and source
    - Citation counts
    - Links to PDF versions where available
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        super().__init__()
        self._settings = settings or get_settings()
        self._api_key = api_key or self._settings.serper_api_key

    @property
    def name(self) -> str:
        return "google_scholar"

    @property
    def description(self) -> str:
        return """Search Google Scholar for academic publications and research papers.
Use this to find peer-reviewed articles, citations, and scholarly information
on technical or scientific topics.

Best for: academic research, finding foundational papers, verifying scientific claims."""

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

        if not self._api_key:
            return {
                "success": False,
                "data": None,
                "error": "Serper API key not configured. Set SERPER_API_KEY in .env",
                "metadata": {},
            }

        headers = {
            'X-API-KEY': self._api_key,
            'Content-Type': 'application/json'
        }
        payload = json.dumps({"q": query})

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"https://{SERPER_SCHOLAR_URL}/scholar",
                    content=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            logger.error("Serper Scholar API error: %s", exc)
            return {
                "success": False,
                "data": None,
                "error": f"API error: {exc.response.status_code}",
                "metadata": {},
            }
        except Exception as exc:
            logger.error("Serper Scholar request failed: %s", exc)
            return {
                "success": False,
                "data": None,
                "error": str(exc),
                "metadata": {},
            }

        organic_results = data.get("organic", [])
        formatted_results = []
        
        for idx, item in enumerate(organic_results[:limit], 1):
            title = item.get('title', 'No title')
            link = item.get('link', '')
            pdf_url = item.get('pdfUrl', '')
            publication_info = item.get('publicationInfo', '')
            year = item.get('year', '')
            cited_by = item.get('citedBy', '')
            snippet = item.get('snippet', '').replace("Your browser can't play this video.", "").strip()

            result_item = {
                "index": idx,
                "title": title,
                "url": link,
                "pdf_url": pdf_url,
                "publication": publication_info,
                "year": year,
                "cited_by": cited_by,
                "snippet": snippet
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
                "provider": "serper_google_scholar"
            },
        }

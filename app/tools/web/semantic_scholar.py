from __future__ import annotations

from typing import Any, Optional

import httpx

from app.config.settings import Settings, get_settings
from app.core.logging import get_logger
from app.tools.base import BaseTool, ToolCategory, ToolResult

logger = get_logger(__name__)

SEMANTIC_SCHOLAR_URL = "https://api.semanticscholar.org/graph/v1/paper/search"


class SemanticScholarTool(BaseTool):
    """Academic paper search via Semantic Scholar.

    Free API with optional key for higher rate limits. Returns papers
    with citation counts, open-access PDF links, and author metadata.
    Covers CS, AI, ML, medicine, physics, and more.
    """

    FIELDS = (
        "title,authors,abstract,year,citationCount,"
        "openAccessPdf,externalIds,publicationDate,venue"
    )

    def __init__(
        self,
        api_key: Optional[str] = None,
        max_results: int = 10,
        timeout: int = 30,
        settings: Optional[Settings] = None,
    ) -> None:
        super().__init__()
        self._settings = settings or get_settings()
        self._api_key = api_key or getattr(self._settings, "semantic_scholar_api_key", "")
        self._max_results = max_results
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "semantic_scholar"

    @property
    def description(self) -> str:
        return (
            "Academic paper search with citation counts and PDF links. "
            "Free API, no key required for basic use."
        )

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SEARCH

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Research query"},
                "limit": {"type": "integer", "default": 10, "maximum": 50},
                "year": {
                    "type": "string",
                    "description": "Year filter, e.g. '2024' or '2023-2025'",
                },
            },
            "required": ["query"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        query = params.get("query", "")
        limit = min(int(params.get("limit", self._max_results)), 50)
        year = params.get("year", "")

        if not query:
            return ToolResult(success=False, data=None, error="query is required")

        try:
            request_params: dict[str, Any] = {
                "query": query,
                "limit": limit,
                "fields": self.FIELDS,
            }
            if year:
                request_params["year"] = year

            email = getattr(self._settings, "sender_email", "") or "tech-watch@localhost"
            headers: dict[str, str] = {
                "User-Agent": f"tech-watch-agent/1.0 (mailto:{email})",
            }
            if self._api_key:
                headers["x-api-key"] = self._api_key

            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    SEMANTIC_SCHOLAR_URL, params=request_params, headers=headers
                )
                resp.raise_for_status()

            data = resp.json()
            papers = []
            for p in data.get("data", []):
                pdf_url = ""
                if p.get("openAccessPdf"):
                    pdf_url = p["openAccessPdf"].get("url", "")

                paper_url = ""
                ext_ids = p.get("externalIds", {})
                if ext_ids.get("DOI"):
                    paper_url = f"https://doi.org/{ext_ids['DOI']}"
                elif ext_ids.get("ArXiv"):
                    paper_url = f"https://arxiv.org/abs/{ext_ids['ArXiv']}"

                authors = [a.get("name", "") for a in p.get("authors", [])[:5]]

                papers.append(
                    {
                        "title": p.get("title", ""),
                        "url": paper_url,
                        "pdf_url": pdf_url,
                        "abstract": (p.get("abstract") or "")[:500],
                        "authors": authors,
                        "year": p.get("year"),
                        "citation_count": p.get("citationCount", 0),
                        "venue": p.get("venue", ""),
                        "published_date": p.get("publicationDate", ""),
                    }
                )

            return ToolResult(
                success=True,
                data=papers,
                error=None,
                metadata={"count": len(papers), "provider": "semantic_scholar", "query": query},
            )
        except Exception as exc:
            logger.warning("Semantic Scholar search failed for '%s': %s", query, exc)
            return ToolResult(success=False, data=None, error=str(exc))

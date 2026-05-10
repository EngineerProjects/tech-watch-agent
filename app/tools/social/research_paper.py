"""
Research paper analysis tool.

This tool provides capabilities for downloading, parsing, and analyzing
academic research papers from various sources including arXiv, Semantic Scholar,
and direct PDF URLs.

Features:
- Download PDFs from URLs
- Extract text and metadata from PDFs
- Search Semantic Scholar for papers
- Analyze paper content for relevance
- Extract key sections (abstract, intro, conclusion)
"""

from typing import Any, Optional
import re
import io

from app.tools.base import BaseTool, ToolCategory, ToolResult
from app.core.logging import get_logger


logger = get_logger(__name__)


class ResearchPaperTool(BaseTool):
    """Tool for academic research paper analysis.

    Provides functionality to download and analyze research papers from
    various academic sources. Supports PDF extraction, metadata parsing,
    and content analysis.

    Attributes:
        cache_dir: Optional directory for caching downloaded papers
    """

    def __init__(self, cache_dir: Optional[str] = None) -> None:
        """Initialize research paper tool.

        Args:
            cache_dir: Optional directory to cache downloaded papers
        """
        super().__init__()
        self._cache_dir = cache_dir

    @property
    def name(self) -> str:
        return "research_paper"

    @property
    def description(self) -> str:
        return """Research paper analysis tool for extracting and analyzing
academic papers from various sources. Use this to:
- Download and parse PDFs from URLs (arXiv, direct links)
- Search Semantic Scholar for relevant papers
- Extract text, metadata, and key sections from papers
- Analyze paper content for tech relevance"""

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
                    "enum": ["download_pdf", "extract_text", "search_papers", "analyze_paper", "get_metadata"],
                    "description": "The research paper action to perform",
                },
                "url": {
                    "type": "string",
                    "description": "PDF URL or paper URL (for download/extract)",
                },
                "arxiv_id": {
                    "type": "string",
                    "description": "arXiv paper ID (e.g., '2301.12345')",
                },
                "query": {
                    "type": "string",
                    "description": "Search query (for search_papers action)",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results (default: 10)",
                    "default": 10,
                },
                "source": {
                    "type": "string",
                    "enum": ["arxiv", "semantic_scholar", "google_scholar", "direct"],
                    "description": "Paper source for search",
                    "default": "semantic_scholar",
                },
                "extract_sections": {
                    "type": "boolean",
                    "description": "Extract key sections (abstract, intro, conclusion)",
                    "default": True,
                },
            },
            "required": ["action"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        """Execute research paper action.

        Args:
            params: Action and parameters

        Returns:
            ToolResult with paper data or error
        """
        action = params.get("action")
        url = params.get("url", "")
        arxiv_id = params.get("arxiv_id", "")
        query = params.get("query", "")
        max_results = params.get("max_results", 10)
        source = params.get("source", "semantic_scholar")
        extract_sections = params.get("extract_sections", True)

        try:
            if action == "download_pdf":
                return await self._download_pdf(url or self._arxiv_url(arxiv_id))
            elif action == "extract_text":
                return await self._extract_text_from_url(url, extract_sections)
            elif action == "search_papers":
                return await self._search_papers(query, max_results, source)
            elif action == "analyze_paper":
                return await self._analyze_paper(url or self._arxiv_url(arxiv_id))
            elif action == "get_metadata":
                return await self._get_metadata(url or self._arxiv_url(arxiv_id))
            else:
                return {
                    "success": False,
                    "data": None,
                    "error": f"Unknown action: {action}",
                    "metadata": {},
                }

        except Exception as exc:
            logger.error("Research paper tool error: %s", exc)
            return {
                "success": False,
                "data": None,
                "error": str(exc),
                "metadata": {},
            }

    @staticmethod
    def _arxiv_url(arxiv_id: str) -> str:
        """Convert arXiv ID to PDF URL.

        Args:
            arxiv_id: arXiv paper ID

        Returns:
            PDF URL for the paper
        """
        # Clean the ID
        arxiv_id = arxiv_id.strip()
        if not arxiv_id:
            return ""

        # Handle different formats
        if "/" not in arxiv_id:
            # Just the number, assume current format
            return f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        else:
            return f"https://arxiv.org/pdf/{arxiv_id}.pdf"

    async def _download_pdf(self, url: str) -> ToolResult:
        """Download a PDF from URL.

        Args:
            url: PDF URL

        Returns:
            ToolResult with download status
        """
        if not url:
            return {
                "success": False,
                "data": None,
                "error": "URL is required",
                "metadata": {},
            }

        try:
            import httpx

            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                response = await client.get(url)

            if response.status_code != 200:
                return {
                    "success": False,
                    "data": None,
                    "error": f"Download failed: HTTP {response.status_code}",
                    "metadata": {},
                }

            content_type = response.headers.get("content-type", "")
            if "pdf" not in content_type.lower() and not url.endswith(".pdf"):
                return {
                    "success": False,
                    "data": None,
                    "error": "URL does not point to a PDF",
                    "metadata": {},
                }

            # Get file size
            size = len(response.content)
            size_kb = size / 1024

            return {
                "success": True,
                "data": {
                    "url": url,
                    "size_bytes": size,
                    "size_kb": round(size_kb, 2),
                    "downloaded": True,
                },
                "error": None,
                "metadata": {"size_kb": round(size_kb, 2)},
            }

        except Exception as exc:
            return {
                "success": False,
                "data": None,
                "error": f"Download error: {str(exc)}",
                "metadata": {},
            }

    async def _extract_text_from_url(self, url: str, extract_sections: bool) -> ToolResult:
        """Extract text from a PDF URL.

        Args:
            url: PDF URL
            extract_sections: Whether to extract key sections

        Returns:
            ToolResult with extracted text
        """
        if not url:
            return {
                "success": False,
                "data": None,
                "error": "URL is required",
                "metadata": {},
            }

        try:
            import httpx

            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                response = await client.get(url)

            if response.status_code != 200:
                return {
                    "success": False,
                    "data": None,
                    "error": f"Download failed: HTTP {response.status_code}",
                    "metadata": {},
                }

            pdf_content = response.content

            # Try to extract text using pymupdf
            try:
                import fitz  # PyMuPDF

                doc = fitz.open(stream=pdf_content, filetype="pdf")
                text_parts = []
                pages = []

                for page_num, page in enumerate(doc):
                    text = page.get_text()
                    if text.strip():
                        text_parts.append(f"--- Page {page_num + 1} ---\n{text}")
                        pages.append(text)

                full_text = "\n\n".join(text_parts)
                doc.close()

                result = {
                    "text": full_text,
                    "page_count": len(doc) if hasattr(doc, '__len__') else len(pages),
                    "character_count": len(full_text),
                    "url": url,
                }

                if extract_sections:
                    result["sections"] = self._extract_sections(full_text)

                return {
                    "success": True,
                    "data": result,
                    "error": None,
                    "metadata": {
                        "pages": len(pages),
                        "characters": len(full_text),
                    },
                }

            except ImportError:
                return {
                    "success": False,
                    "data": None,
                    "error": "PyMuPDF not installed. Install with: pip install pymupdf",
                    "metadata": {},
                }

        except Exception as exc:
            return {
                "success": False,
                "data": None,
                "error": f"Extraction error: {str(exc)}",
                "metadata": {},
            }

    async def _search_papers(self, query: str, max_results: int, source: str) -> ToolResult:
        """Search for research papers.

        Args:
            query: Search query
            max_results: Maximum results
            source: Paper source

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

        if source == "semantic_scholar":
            return await self._search_semantic_scholar(query, max_results)
        elif source == "arxiv":
            return await self._search_arxiv(query, max_results)
        else:
            return await self._search_semantic_scholar(query, max_results)

    async def _search_semantic_scholar(self, query: str, max_results: int) -> ToolResult:
        """Search Semantic Scholar API.

        Args:
            query: Search query
            max_results: Maximum results

        Returns:
            ToolResult with papers
        """
        try:
            import httpx

            api_url = "https://api.semanticscholar.org/graph/v1/paper/search"
            params = {
                "query": query,
                "limit": max_results,
                "fields": "title,authors,abstract,year,citationCount,openAccessPdf,venue,externalIds",
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(api_url, params=params)

            if response.status_code != 200:
                return {
                    "success": False,
                    "data": None,
                    "error": f"API error: {response.status_code}",
                    "metadata": {},
                }

            data = response.json()
            papers = []

            for paper in data.get("data", []):
                # Get PDF URL if available
                pdf_url = None
                if paper.get("openAccessPdf"):
                    pdf_url = paper["openAccessPdf"].get("url")

                # Get arXiv ID if available
                arxiv_id = None
                if paper.get("externalIds", {}).get("ArXiv"):
                    arxiv_id = paper["externalIds"]["ArXiv"]

                papers.append({
                    "title": paper.get("title", ""),
                    "authors": [a.get("name", "") for a in paper.get("authors", [])[:5]],
                    "abstract": paper.get("abstract", "")[:500] if paper.get("abstract") else "",
                    "year": paper.get("year"),
                    "citations": paper.get("citationCount", 0),
                    "venue": paper.get("venue", ""),
                    "arxiv_id": arxiv_id,
                    "pdf_url": pdf_url,
                    "semantic_scholar_url": f"https://www.semanticscholar.org/paper/{paper.get('paperId', '')}",
                })

            return {
                "success": True,
                "data": papers,
                "error": None,
                "metadata": {"query": query, "count": len(papers)},
            }

        except Exception as exc:
            return {
                "success": False,
                "data": None,
                "error": str(exc),
                "metadata": {},
            }

    async def _search_arxiv(self, query: str, max_results: int) -> ToolResult:
        """Search arXiv for papers.

        Args:
            query: Search query
            max_results: Maximum results

        Returns:
            ToolResult with arXiv papers
        """
        # Use the ArXiv tool for this
        from app.tools.social.arxiv import ArXivTool

        arxiv_tool = ArXivTool()
        return await arxiv_tool.execute({
            "action": "search",
            "query": query,
            "limit": max_results,
        })

    async def _analyze_paper(self, url: str) -> ToolResult:
        """Perform comprehensive paper analysis.

        Args:
            url: PDF URL

        Returns:
            ToolResult with analysis
        """
        # Get metadata
        metadata_result = await self._get_metadata(url)

        # Get full text
        text_result = await self._extract_text_from_url(url, extract_sections=True)

        if text_result["success"]:
            return {
                "success": True,
                "data": {
                    "metadata": metadata_result["data"] if metadata_result["success"] else None,
                    "content": text_result["data"],
                },
                "error": None,
                "metadata": {"url": url},
            }

        return metadata_result

    async def _get_metadata(self, url: str) -> ToolResult:
        """Extract metadata from a paper URL.

        Args:
            url: Paper URL

        Returns:
            ToolResult with metadata
        """
        # Check if it's an arXiv URL
        arxiv_match = re.search(r'arxiv\.org/abs/([0-9.]+)', url)
        if arxiv_match:
            return await self._get_arxiv_metadata(arxiv_match.group(1))

        # Try to get metadata from Semantic Scholar if we have a title
        # This is a simplified version - full implementation would parse
        # the PDF or follow redirects

        return {
            "success": True,
            "data": {
                "url": url,
                "source": "unknown",
            },
            "error": None,
            "metadata": {},
        }

    async def _get_arxiv_metadata(self, arxiv_id: str) -> ToolResult:
        """Get metadata from arXiv.

        Args:
            arxiv_id: arXiv paper ID

        Returns:
            ToolResult with arXiv metadata
        """
        try:
            import httpx

            # Get abstract page
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"https://arxiv.org/abs/{arxiv_id}")

            if response.status_code != 200:
                return {
                    "success": False,
                    "data": None,
                    "error": f"Failed to fetch arXiv: {response.status_code}",
                    "metadata": {},
                }

            html = response.text

            # Extract metadata
            title_match = re.search(r'<title>(.*?)</title>', html)
            title = title_match.group(1).replace(" arXiv", "").strip() if title_match else ""

            authors_match = re.search(r'<div class="authors">(.*?)</div>', html, re.DOTALL)
            authors = []
            if authors_match:
                author_names = re.findall(r'>([^<]+)<', authors_match.group(1))
                authors = [a.strip() for a in author_names if a.strip()]

            abstract_match = re.search(r'<blockquote class="abstract">(.*?)</blockquote>', html, re.DOTALL)
            abstract = ""
            if abstract_match:
                abstract = re.sub(r'<[^>]+>', '', abstract_match.group(1)).strip()

            subjects_match = re.search(r'<td class="datatable-subject">(.*?)</td>', html, re.DOTALL)
            subjects = []
            if subjects_match:
                subjects = [s.strip() for s in re.findall(r'>([^<]+)<', subjects_match.group(1))]

            return {
                "success": True,
                "data": {
                    "title": title,
                    "authors": authors,
                    "abstract": abstract,
                    "subjects": subjects,
                    "arxiv_id": arxiv_id,
                    "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}.pdf",
                    "url": f"https://arxiv.org/abs/{arxiv_id}",
                },
                "error": None,
                "metadata": {"arxiv_id": arxiv_id},
            }

        except Exception as exc:
            return {
                "success": False,
                "data": None,
                "error": str(exc),
                "metadata": {},
            }

    def _extract_sections(self, text: str) -> dict[str, str]:
        """Extract key sections from paper text.

        Args:
            text: Full paper text

        Returns:
            Dictionary of sections
        """
        sections = {}

        # Look for common section headings
        section_patterns = {
            "abstract": [r"Abstract", r"ABSTRACT"],
            "introduction": [r"1\.?\s*Introduction", r"INTRODUCTION"],
            "methods": [r"1\.?\s*Method", r"METHODOLOGY", r"METHODS"],
            "results": [r"1\.?\s*Results?", r"RESULTS"],
            "discussion": [r"1\.?\s*Discussion", r"DISCUSSION"],
            "conclusion": [r"1\.?\s*Conclusion", r"CONCLUSION", r"CONCLUSIONS?"],
        }

        for section_name, patterns in section_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    # Extract section content (simplified - just get text after heading)
                    start = match.end()
                    # Find next major section or end
                    next_section = re.search(r"\n\s*(?=1\.?\s*[A-Z])", text[start:])
                    if next_section:
                        section_text = text[start:start + next_section.start()].strip()
                    else:
                        section_text = text[start:start + 2000].strip()

                    sections[section_name] = section_text[:1000]  # Limit length
                    break

        return sections

    def _format_paper_summary(self, paper: dict) -> str:
        """Format paper info into readable summary.

        Args:
            paper: Paper dictionary

        Returns:
            Formatted summary
        """
        lines = [
            f"**{paper.get('title', 'Untitled')}**",
        ]

        if paper.get("authors"):
            lines.append(f"Authors: {', '.join(paper['authors'][:3])}")

        if paper.get("year"):
            lines.append(f"Year: {paper['year']}")

        if paper.get("abstract"):
            lines.append(f"\nAbstract: {paper['abstract'][:300]}...")

        return "\n".join(lines)


# Helper functions for research workflow

def extract_arxiv_id(url: str) -> Optional[str]:
    """Extract arXiv ID from URL.

    Args:
        url: arXiv URL

    Returns:
        arXiv ID or None
    """
    match = re.search(r'arxiv\.org/(?:abs|pdf)/([0-9.]+)', url)
    return match.group(1) if match else None


def is_pdf_url(url: str) -> bool:
    """Check if URL points to a PDF.

    Args:
        url: URL to check

    Returns:
        True if PDF URL
    """
    return url.endswith(".pdf") or ".pdf?" in url


def format_citation(paper: dict) -> str:
    """Format paper as academic citation.

    Args:
        paper: Paper dictionary

    Returns:
        Formatted citation
    """
    authors = paper.get("authors", [])
    if len(authors) > 3:
        author_str = f"{authors[0]} et al."
    else:
        author_str = ", ".join(authors)

    year = paper.get("year", "n.d.")
    title = paper.get("title", "Untitled")

    citation = f"{author_str} ({year}). {title}"

    if paper.get("arxiv_id"):
        citation += f". arXiv:{paper['arxiv_id']}"

    return citation
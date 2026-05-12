"""
PDF Downloader tool for fetching and parsing academic papers.

Downloads PDF files from URLs (ArXiv, PDF URLs, etc.), extracts text
content for analysis, and cleans up temporary files after processing.

Features:
- Download PDFs from any URL
- Extract text content using PyMuPDF
- Automatic cleanup of temporary files
- Metadata extraction (title from filename, page count, etc.)
"""

from __future__ import annotations

import os
import re
import tempfile
import uuid
from pathlib import Path
from typing import Any, Optional

import httpx

from app.tools.base import BaseTool, ToolCategory, ToolResult
from app.core.logging import get_logger


logger = get_logger(__name__)

PDF_TEMP_DIR = Path(tempfile.gettempdir()) / "tech_watch_pdfs"
PDF_TEMP_DIR.mkdir(exist_ok=True)


class PDFDownloaderTool(BaseTool):
    """Tool for downloading and parsing PDF documents.

    Downloads PDFs from URLs, extracts text content, and cleans up
    temporary files. Uses PyMuPDF for text extraction.

    Attributes:
        timeout: Download timeout in seconds
        max_file_size_mb: Maximum PDF file size to download
        default_max_pages: Maximum pages to extract (for large documents)
    """

    def __init__(
        self,
        timeout: int = 120,
        max_file_size_mb: int = 50,
        default_max_pages: int = 50,
    ) -> None:
        super().__init__()
        self.timeout = timeout
        self.max_file_size_mb = max_file_size_mb
        self.default_max_pages = default_max_pages

    @property
    def name(self) -> str:
        return "pdf_downloader"

    @property
    def description(self) -> str:
        return """PDF Downloader tool for fetching and extracting text from
academic papers and PDF documents. Use this to download papers from ArXiv,
retrieve PDF content from URLs, and extract text for analysis. Automatically
cleans up temporary files after extraction."""

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.CRAWL

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL of the PDF to download",
                },
                "max_pages": {
                    "type": "integer",
                    "description": "Maximum number of pages to extract (default: 50)",
                    "default": 50,
                },
                "extract_metadata": {
                    "type": "boolean",
                    "description": "Extract document metadata (title, author, etc.)",
                    "default": True,
                },
                "source": {
                    "type": "string",
                    "description": "Source identifier (e.g., 'arxiv', 'openalex', 'custom')",
                    "default": "unknown",
                },
            },
            "required": ["url"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        """Download and parse a PDF document.

        Args:
            params: Must include 'url'. Optional: 'max_pages', 'extract_metadata', 'source'

        Returns:
            ToolResult with extracted text and metadata
        """
        url = params.get("url", "")
        if not url:
            return {
                "success": False,
                "data": None,
                "error": "Missing required parameter: url",
                "metadata": {},
            }

        max_pages = params.get("max_pages", self.default_max_pages)
        extract_metadata = params.get("extract_metadata", True)
        source = params.get("source", "unknown")

        temp_path: Optional[Path] = None
        try:
            temp_path = await self._download_pdf(url)
            if temp_path is None:
                return {
                    "success": False,
                    "data": None,
                    "error": f"Failed to download PDF from {url}",
                    "metadata": {},
                }

            text_content = await self._extract_text(temp_path, max_pages)

            metadata = {}
            if extract_metadata:
                metadata = await self._extract_metadata(temp_path, url)

            result = {
                "url": url,
                "source": source,
                "text": text_content,
                "text_length": len(text_content),
                "pages_extracted": min(
                    self._count_pages(temp_path),
                    max_pages,
                ),
                **metadata,
            }

            return {
                "success": True,
                "data": result,
                "error": None,
                "metadata": {
                    "url": url,
                    "source": source,
                    "size_bytes": temp_path.stat().st_size if temp_path.exists() else 0,
                },
            }

        except Exception as exc:
            logger.error("PDF download/parse failed for %s: %s", url, exc)
            return {
                "success": False,
                "data": None,
                "error": str(exc),
                "metadata": {},
            }
        finally:
            if temp_path and temp_path.exists():
                self._cleanup(temp_path)

    async def _download_pdf(self, url: str) -> Optional[Path]:
        """Download PDF to temporary file.

        Args:
            url: PDF URL

        Returns:
            Path to downloaded file or None on failure
        """
        file_id = uuid.uuid4().hex[:12]
        dest_path = PDF_TEMP_DIR / f"{file_id}.pdf"

        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; tech-watch-agent/1.0)",
        }

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()

            content_length = response.headers.get("content-length")
            if content_length:
                size_mb = int(content_length) / (1024 * 1024)
                if size_mb > self.max_file_size_mb:
                    raise ValueError(
                        f"PDF too large: {size_mb:.1f}MB (max: {self.max_file_size_mb}MB)"
                    )

            dest_path.write_bytes(response.content)

            if not self._is_pdf(dest_path):
                dest_path.unlink(missing_ok=True)
                raise ValueError("Downloaded file is not a valid PDF")

        logger.debug("Downloaded PDF to %s", dest_path)
        return dest_path

    def _is_pdf(self, path: Path) -> bool:
        if path.stat().st_size < 4:
            return False
        with open(path, "rb") as f:
            header = f.read(4)
        return header == b"%PDF"

    async def _extract_text(self, path: Path, max_pages: int) -> str:
        """Extract text from PDF using PyMuPDF.

        Args:
            path: Path to PDF file
            max_pages: Maximum pages to process

        Returns:
            Extracted text content
        """
        import pymupdf

        text_parts: list[str] = []
        with pymupdf.open(path) as doc:
            total_pages = len(doc)
            pages_to_read = min(total_pages, max_pages)

            for page_num in range(pages_to_read):
                page = doc[page_num]
                text = page.get_text()
                if text.strip():
                    text_parts.append(f"[Page {page_num + 1}]\n{text.strip()}")

        return "\n\n".join(text_parts)

    def _count_pages(self, path: Path) -> int:
        """Count pages in PDF without full extraction."""
        import pymupdf
        with pymupdf.open(path) as doc:
            return len(doc)

    async def _extract_metadata(self, path: Path, url: str) -> dict[str, Any]:
        """Extract document metadata from PDF.

        Args:
            path: Path to PDF file
            url: Original URL

        Returns:
            Metadata dict
        """
        import pymupdf

        metadata: dict[str, Any] = {
            "filename": path.name,
            "title": self._title_from_url(url),
        }

        try:
            with pymupdf.open(path) as doc:
                metadata["total_pages"] = len(doc)
                doc_metadata = doc.metadata
                if doc_metadata:
                    if doc_metadata.get("title"):
                        metadata["title"] = doc_metadata["title"]
                    if doc_metadata.get("author"):
                        metadata["author"] = doc_metadata["author"]
                    if doc_metadata.get("subject"):
                        metadata["subject"] = doc_metadata["subject"]
                    if doc_metadata.get("creator"):
                        metadata["creator"] = doc_metadata["creator"]
                    if doc_metadata.get("producer"):
                        metadata["producer"] = doc_metadata["producer"]
                    creation_date = doc_metadata.get("creationDate")
                    if creation_date:
                        metadata["creation_date"] = creation_date
        except Exception as exc:
            logger.debug("Failed to extract PDF metadata: %s", exc)

        return metadata

    @staticmethod
    def _title_from_url(url: str) -> str:
        """Extract title-like string from URL."""
        filename = url.split("/")[-1]
        filename = re.sub(r"\?.*", "", filename)
        filename = re.sub(r"\.pdf$", "", filename, flags=re.IGNORECASE)
        filename = re.sub(r"[_-]+", " ", filename)
        return filename.strip()

    def _cleanup(self, path: Path) -> None:
        """Remove temporary PDF file.

        Args:
            path: Path to file to remove
        """
        try:
            if path.exists():
                path.unlink()
                logger.debug("Cleaned up temporary PDF: %s", path)
        except Exception as exc:
            logger.warning("Failed to cleanup PDF %s: %s", path, exc)


class ArXivPDFTool(BaseTool):
    """Convenience tool for downloading ArXiv papers as PDFs.

    Takes ArXiv paper ID or URL and downloads the PDF directly from ArXiv.
    """

    ARXIV_PDF_BASE = "https://arxiv.org/pdf"

    def __init__(self) -> None:
        super().__init__()
        self._downloader = PDFDownloaderTool()

    @property
    def name(self) -> str:
        return "arxiv_pdf"

    @property
    def description(self) -> str:
        return """ArXiv PDF Downloader. Downloads the PDF of an ArXiv paper
given its paper ID or URL. Extracts text content for analysis and automatically
cleans up temporary files."""

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.CRAWL

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "paper_id": {
                    "type": "string",
                    "description": "ArXiv paper ID (e.g., '2301.12345' or '2301.12345v2')",
                },
                "url": {
                    "type": "string",
                    "description": "Full ArXiv PDF URL (alternative to paper_id)",
                },
                "max_pages": {
                    "type": "integer",
                    "description": "Maximum pages to extract (default: 50)",
                    "default": 50,
                },
            },
            "required": ["paper_id"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        """Download ArXiv paper as PDF and extract text.

        Args:
            params: Must include 'paper_id' or 'url'

        Returns:
            ToolResult with extracted text and paper metadata
        """
        paper_id = params.get("paper_id", "")
        url = params.get("url", "")
        max_pages = params.get("max_pages", 50)

        if not paper_id and not url:
            return {
                "success": False,
                "data": None,
                "error": "Missing required parameter: paper_id or url",
                "metadata": {},
            }

        if not url:
            arxiv_id = paper_id.strip()
            url = f"{self.ARXIV_PDF_BASE}/{arxiv_id}.pdf"

        result = await self._downloader.execute({
            "url": url,
            "max_pages": max_pages,
            "extract_metadata": True,
            "source": "arxiv",
        })

        if result.get("success"):
            data = result.get("data", {})
            data["arxiv_id"] = paper_id or self._extract_arxiv_id(url)
            result["data"] = data

        return result

    @staticmethod
    def _extract_arxiv_id(url: str) -> str:
        match = re.search(r"arxiv\.org/pdf/([0-9.]+(?:v\d+)?)", url)
        if match:
            return match.group(1)
        return ""
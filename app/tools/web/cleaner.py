"""
Content cleaning utilities for web scraping.

Extracts clean, readable content from HTML pages by:
- Removing scripts, styles, nav, footers, ads
- Keeping only the main content area
- Converting to clean markdown/text
"""

from __future__ import annotations

import re
from typing import Optional


def clean_html_content(html: str) -> str:
    """Remove noise from HTML: scripts, styles, ads, nav, etc."""
    if not html:
        return ""

    soup = _get_soup(html)

    for tag in soup.find_all([
        "script", "style", "nav", "header", "footer", "aside",
        "noscript", "iframe", "form", "button", "svg", "meta",
        "noscript", "head"
    ]):
        tag.decompose()

    noise_classes = [
        "sidebar", "menu", "nav", "header", "footer", "advertisement",
        "ads", "ad", "social", "share", "comment", "comments",
        "related", "recommended", "newsletter", "popup", "modal",
        "cookie", "banner", "promo", "sponsor"
    ]
    for cls in noise_classes:
        for elem in soup.find_all(class_=re.compile(cls, re.I)):
            elem.decompose()

    noise_ids = ["sidebar", "nav", "header", "footer", "comments", "footer", "menu"]
    for nid in noise_ids:
        for elem in soup.find_all(id=re.compile(nid, re.I)):
            elem.decompose()

    main = (
        soup.find("article") or
        soup.find("main") or
        soup.find("div", class_=re.compile(r"content|article|post|entry", re.I)) or
        soup
    )

    return str(main)


def html_to_markdown(html: str) -> str:
    """Convert HTML to clean Markdown."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    lines = []

    for elem in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "blockquote", "pre", "code"]):
        text = elem.get_text(strip=True)
        if not text:
            continue

        tag = elem.name

        if tag == "h1":
            lines.append(f"\n# {text}\n")
        elif tag == "h2":
            lines.append(f"\n## {text}\n")
        elif tag == "h3":
            lines.append(f"\n### {text}\n")
        elif tag == "h4":
            lines.append(f"\n#### {text}\n")
        elif tag == "p":
            lines.append(f"{text}\n")
        elif tag == "ul":
            for li in elem.find_all("li", recursive=False):
                lines.append(f"- {li.get_text(strip=True)}\n")
        elif tag == "ol":
            for i, li in enumerate(elem.find_all("li", recursive=False), 1):
                lines.append(f"{i}. {li.get_text(strip=True)}\n")
        elif tag == "blockquote":
            lines.append(f"> {text}\n")
        elif tag in ("pre", "code"):
            lines.append(f"\n```\n{text}\n```\n")
        elif tag == "a":
            href = elem.get("href", "")
            if href:
                lines.append(f"[{text}]({href})")
            else:
                lines.append(text)

    return "\n".join(lines)


def extract_main_content(html: str) -> str:
    """Extract main readable content from HTML as clean text/markdown."""
    cleaned = clean_html_content(html)
    soup = _get_soup(cleaned)

    paragraphs = []
    for elem in soup.find_all(["h1", "h2", "h3", "h4", "p", "ul", "ol", "blockquote", "pre", "table"]):
        text = _clean_text(elem.get_text())

        if not text or len(text) < 10:
            continue

        tag = elem.name

        if tag.startswith("h"):
            level = int(tag[1])
            paragraphs.append(f"\n{'#' * (level + 1)} {text}\n")
        elif tag == "p":
            paragraphs.append(text + "\n")
        elif tag == "ul":
            for li in elem.find_all("li", recursive=False):
                txt = _clean_text(li.get_text())
                if txt:
                    paragraphs.append(f"- {txt}")
        elif tag == "ol":
            for i, li in enumerate(elem.find_all("li", recursive=False), 1):
                txt = _clean_text(li.get_text())
                if txt:
                    paragraphs.append(f"{i}. {txt}")
        elif tag == "blockquote":
            paragraphs.append(f"\n> {text}\n")
        elif tag == "pre":
            paragraphs.append(f"\n```\n{text}\n```\n")
        elif tag == "table":
            rows = []
            for row in elem.find_all("tr")[:20]:
                cells = [_clean_text(c.get_text()) for c in row.find_all(["th", "td"])]
                if cells:
                    rows.append(" | ".join(cells))
            if rows:
                paragraphs.append("\n" + "\n".join(rows) + "\n")

    return "\n".join(paragraphs).strip()


def _get_soup(html: str):
    from bs4 import BeautifulSoup
    return BeautifulSoup(html, "html.parser")


def _clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    text = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", text)
    return text
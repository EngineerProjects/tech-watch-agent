from __future__ import annotations

import urllib.parse

import httpx
from bs4 import BeautifulSoup

from app.config.settings import Settings, get_settings
from app.core.logging import get_logger


logger = get_logger(__name__)


class NewsSearchService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def search_news_urls(self, topic: str) -> list[str]:
        # V1 keeps discovery simple: query a general search engine, then
        # constrain results to a small trusted set of tech news domains.
        query = (
            f"{topic} news site:techcrunch.com OR site:theverge.com "
            "OR site:venturebeat.com OR site:wired.com"
        )
        duckduckgo_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"

        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                response = await client.get(
                    duckduckgo_url,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36"
                        )
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Search fallback to static sources for topic '%s': %s", topic, exc)
            return self.settings.news_sources[:5]

        urls: list[str] = []
        soup = BeautifulSoup(response.text, "html.parser")
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if not href.startswith("http"):
                continue
            if any(
                domain in href
                for domain in (
                    "techcrunch.com",
                    "theverge.com",
                    "venturebeat.com",
                    "wired.com",
                )
            ):
                urls.append(href)

        deduped = self._dedupe(urls)
        return deduped[:5] if deduped else self.settings.news_sources[:5]

    @staticmethod
    def _dedupe(urls: list[str]) -> list[str]:
        seen: set[str] = set()
        deduped: list[str] = []
        for url in urls:
            if url in seen:
                continue
            seen.add(url)
            deduped.append(url)
        return deduped

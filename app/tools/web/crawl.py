from __future__ import annotations

from datetime import datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.config.settings import Settings, get_settings
from app.core.logging import get_logger
from app.core.models import Article

logger = get_logger(__name__)


def _load_crawl4ai():
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig
    except ImportError:  # pragma: no cover - depends on optional runtime installation
        return None, None, None, None
    return AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig


class WebCrawler:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.timeout = self.settings.crawl_timeout_seconds
        self.max_articles = self.settings.max_articles_per_topic

    async def crawl_url(self, url: str, topic: str) -> list[Article]:
        # Crawl4AI is optional at import time because local dev and tests should
        # still work even if the browser stack is not installed yet.
        async_web_crawler, _, _, _ = _load_crawl4ai()
        if async_web_crawler is not None:
            try:
                return await self._crawl_with_crawl4ai(url, topic)
            except Exception as exc:
                logger.warning("Crawl4AI failed for %s, using fallback: %s", url, exc)

        return await self._fallback_crawl(url, topic)

    async def _crawl_with_crawl4ai(self, url: str, topic: str) -> list[Article]:
        async_web_crawler, browser_config_cls, cache_mode_cls, crawler_run_config_cls = _load_crawl4ai()
        assert async_web_crawler is not None
        assert browser_config_cls is not None
        assert cache_mode_cls is not None
        assert crawler_run_config_cls is not None

        browser_config = browser_config_cls(headless=True)
        crawler_config = crawler_run_config_cls(
            cache_mode=cache_mode_cls.BYPASS,
            word_count_threshold=10,
            page_timeout=60000,
        )

        async with async_web_crawler(config=browser_config) as crawler:
            result = await crawler.arun(url=url, config=crawler_config)

        if not result.success:
            message = getattr(result, "error_message", "unknown error")
            raise RuntimeError(f"crawl failed: {message}")

        if getattr(result, "cleaned_html", ""):
            return self._extract_articles_from_html(result.cleaned_html, url, topic)
        if getattr(result, "markdown", ""):
            return self._extract_articles_from_markdown(result.markdown, url, topic)

        return []

    async def _fallback_crawl(self, url: str, topic: str) -> list[Article]:
        try:
            async with httpx.AsyncClient(timeout=float(self.timeout)) as client:
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36"
                        )
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("Fallback crawl failed for %s: %s", url, exc)
            return []

        return self._extract_articles_from_html(response.text, url, topic)

    def _extract_articles_from_markdown(
        self,
        markdown_content: str,
        source_url: str,
        topic: str,
    ) -> list[Article]:
        # Some sources render cleaner markdown than HTML through Crawl4AI, so
        # this parser keeps a lightweight header-based fallback.
        articles: list[Article] = []
        current_title: str | None = None
        current_content: list[str] = []

        for raw_line in markdown_content.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            if line.startswith("#"):
                if current_title and len(current_title) > 15:
                    articles.append(
                        self._build_article(
                            title=current_title,
                            summary=" ".join(current_content)[:300],
                            url=source_url,
                            topic=topic,
                        )
                    )
                    if len(articles) >= self.max_articles:
                        break

                current_title = line.lstrip("#").strip()
                current_content = []
                continue

            if current_title and not line.startswith("[") and not line.startswith("http"):
                current_content.append(line)

        if current_title and len(current_title) > 15 and len(articles) < self.max_articles:
            articles.append(
                self._build_article(
                    title=current_title,
                    summary=" ".join(current_content)[:300],
                    url=source_url,
                    topic=topic,
                )
            )

        return articles[: self.max_articles]

    def _extract_articles_from_html(
        self,
        html_content: str,
        source_url: str,
        topic: str,
    ) -> list[Article]:
        # The selectors intentionally stay heuristic-based for V1. We prefer a
        # broad best-effort extractor here over per-site custom parsers.
        try:
            soup = BeautifulSoup(html_content, "html.parser")
        except Exception as exc:
            logger.error("HTML parsing failed for %s: %s", source_url, exc)
            return []

        selectors = [
            "article",
            ".post",
            ".article",
            ".story",
            ".entry",
            "[data-testid='post']",
            ".c-entry-box--compact",
            ".post-item",
            ".article-item",
            ".news-item",
            "h2",
            "h3",
        ]

        for selector in selectors:
            articles: list[Article] = []
            for element in soup.select(selector)[: self.max_articles * 2]:
                article = self._article_from_element(element, source_url, topic)
                if article is None:
                    continue
                articles.append(article)
                if len(articles) >= self.max_articles:
                    return articles
            if articles:
                return articles

        return []

    def _article_from_element(
        self,
        element: BeautifulSoup,
        source_url: str,
        topic: str,
    ) -> Article | None:
        title_element = element.find(["h1", "h2", "h3", "h4"])
        if title_element is None and element.name in {"h2", "h3"}:
            title_element = element

        if title_element is None:
            return None

        title = title_element.get_text(strip=True)
        if len(title) < 15:
            return None

        link_element = element.find("a", href=True)
        article_url = source_url
        if link_element is not None:
            href = link_element.get("href", "")
            if href.startswith("http"):
                article_url = href
            elif href.startswith("/"):
                article_url = urljoin(source_url, href)

        summary = self._extract_summary(element)
        return self._build_article(title=title, summary=summary, url=article_url, topic=topic)

    @staticmethod
    def _extract_summary(element: BeautifulSoup) -> str:
        content_element = element.find(
            ["p", "div"],
            class_=lambda value: bool(
                value and any(token in value.lower() for token in ("summary", "excerpt", "description"))
            ),
        )
        if content_element is not None:
            return content_element.get_text(strip=True)[:300]

        paragraph = element.find("p")
        if paragraph is not None:
            return paragraph.get_text(strip=True)[:300]

        return ""

    @staticmethod
    def _build_article(title: str, summary: str, url: str, topic: str) -> Article:
        return Article(
            title=title.strip(),
            summary=summary.strip(),
            url=url.strip(),
            topic=topic,
            published_date=datetime.now().strftime("%Y-%m-%d"),
            content=summary.strip(),
        )

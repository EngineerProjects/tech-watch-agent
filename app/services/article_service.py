from __future__ import annotations

import asyncio

from app.config.settings import Settings, get_settings
from app.core.logging import get_logger
from app.core.models import Article
from app.services.article_ranker import ArticleRanker
from app.tools.web.crawl import WebCrawler
from app.tools.web.search import NewsSearchService


logger = get_logger(__name__)


class ArticleService:
    def __init__(
        self,
        settings: Settings | None = None,
        search_service: NewsSearchService | None = None,
        crawler: WebCrawler | None = None,
        ranker: ArticleRanker | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.search_service = search_service or NewsSearchService(self.settings)
        self.crawler = crawler or WebCrawler(self.settings)
        self.ranker = ranker or ArticleRanker(self.settings)

    async def fetch_articles_for_topic(self, topic: str) -> list[Article]:
        logger.info("Fetching articles for topic: %s", topic)
        urls = await self.search_service.search_news_urls(topic)

        # Fan-out by source URL first, then rank once we have a merged candidate set.
        crawl_tasks = [self.crawler.crawl_url(url, topic) for url in urls]
        results = await asyncio.gather(*crawl_tasks, return_exceptions=True)

        articles: list[Article] = []
        for result in results:
            if isinstance(result, Exception):
                logger.error("Crawl task failed for topic '%s': %s", topic, result)
                continue
            articles.extend(result)

        unique_articles = self._dedupe_articles(articles)
        return self.ranker.filter_relevant_articles(unique_articles, topic)

    async def fetch_articles_for_topics(self, topics: list[str] | None = None) -> list[Article]:
        selected_topics = topics or self.settings.newsletter_topics
        all_articles: list[Article] = []

        for topic in selected_topics:
            topic_articles = await self.fetch_articles_for_topic(topic)
            all_articles.extend(topic_articles)
            await asyncio.sleep(1)

        return self._dedupe_articles(all_articles)

    @staticmethod
    def _dedupe_articles(articles: list[Article]) -> list[Article]:
        # Title + URL is enough for a V1 dedupe key and avoids collapsing
        # syndicated stories that share titles but link to different sources.
        seen: set[tuple[str, str]] = set()
        deduped: list[Article] = []

        for article in articles:
            key = (article.title.strip().lower(), article.url.strip().lower())
            if key in seen:
                continue
            seen.add(key)
            deduped.append(article)

        return deduped

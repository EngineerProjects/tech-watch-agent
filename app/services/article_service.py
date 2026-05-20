from __future__ import annotations

import asyncio

from app.config.settings import Settings, get_settings
from app.core.logging import get_logger
from app.core.models import Article
from app.services.article_ranker import ArticleRanker
from app.tools.web.crawl import WebCrawler
from app.tools.web.search import NewsSearchService


logger = get_logger(__name__)

_TECH_KEYWORDS = frozenset((
    "ai", "artificial", "intelligence", "tech", "technology", "startup",
    "openai", "google", "machine", "learning", "data", "algorithm",
    "neural", "deep", "llm", "model", "api", "software", "cloud",
))


async def _generate_embeddings(texts: list[str]) -> dict[int, list[float]]:
    """Generate embeddings for a list of texts outside of a DB transaction.

    Returns a sparse dict {index → embedding} — missing keys mean the embedding
    was skipped (no API key, import error, or provider failure).
    """
    settings = get_settings()
    if not (settings.llm_api_key or settings.zai_api_key):
        return {}
    try:
        from app.services.embedding.service import EmbeddingService
        service = EmbeddingService()
        results: dict[int, list[float]] = {}
        for i, text in enumerate(texts):
            if not text.strip():
                continue
            try:
                result = await service.embed(text[:2000])
                if result.provider != "fallback":
                    results[i] = result.embedding
            except Exception as exc:
                logger.debug("Embedding skipped for text[%d]: %s", i, exc)
        return results
    except Exception as exc:
        logger.debug("Embedding service unavailable: %s", exc)
        return {}


def _compute_relevance(title: str, summary: str, topic: str) -> int:
    """Keyword-based relevance score for an article against a topic."""
    title_l = title.lower()
    summary_l = summary.lower()
    score = 0
    for kw in topic.lower().split():
        if len(kw) < 3:
            continue
        if kw in title_l:
            score += 2
        if kw in summary_l:
            score += 1
    if score == 0 and any(k in title_l or k in summary_l for k in _TECH_KEYWORDS):
        score = 1
    return score


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
        seen: set[tuple[str, str]] = set()
        deduped: list[Article] = []

        for article in articles:
            key = (article.title.strip().lower(), article.url.strip().lower())
            if key in seen:
                continue
            seen.add(key)
            deduped.append(article)

        return deduped

    async def save_articles(self, articles: list[dict]) -> int:
        """Save articles to database with deduplication and embedding generation.

        Three-pass strategy:
          1. Identify new (non-duplicate) articles inside a read transaction.
          2. Generate embeddings outside the DB transaction (async HTTP calls).
          3. Bulk-insert with embeddings.
        """
        from sqlalchemy import select
        from app.db.base import get_db_context
        from app.db.models import Article
        import uuid

        if not articles:
            return 0

        # Pass 1 — deduplication
        new_articles: list[dict] = []
        async with get_db_context() as db:
            for article_data in articles:
                title = article_data.get("title", "").strip()
                url = article_data.get("url", "").strip()
                if not title or not url:
                    continue
                existing = await db.execute(
                    select(Article).where(
                        Article.title.ilike(title),
                        Article.url.ilike(url),
                    )
                )
                if not existing.scalar_one_or_none():
                    new_articles.append(article_data)

        if not new_articles:
            return 0

        # Pass 2 — embeddings (outside transaction to keep connection idle)
        embed_texts = [
            f"{a.get('title', '')} {a.get('summary', '')}".strip()
            for a in new_articles
        ]
        embeddings = await _generate_embeddings(embed_texts)

        # Pass 3 — insert
        saved = 0
        async with get_db_context() as db:
            for i, article_data in enumerate(new_articles):
                title = article_data.get("title", "").strip()
                url = article_data.get("url", "").strip()
                topic = article_data.get("topic", "")
                summary = article_data.get("summary", "")
                relevance_score = article_data.get("relevance_score", 0)
                if relevance_score == 0 and topic:
                    relevance_score = _compute_relevance(title, summary, topic)

                article = Article(
                    id=uuid.uuid4(),
                    title=title,
                    summary=summary,
                    content=article_data.get("content", ""),
                    url=url,
                    source=article_data.get("source", "orchestrator"),
                    topic=topic,
                    published_date=article_data.get("published_date"),
                    relevance_score=relevance_score,
                    embedding_vector=embeddings.get(i),
                    meta_data={
                        "tool": article_data.get("source", "unknown"),
                        "step": article_data.get("step_name", ""),
                    },
                )
                db.add(article)
                saved += 1

            await db.commit()
            logger.info(
                "Saved %d articles (%d with embeddings)",
                saved, len(embeddings),
            )
            return saved

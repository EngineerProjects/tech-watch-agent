"""
Article store for persistence and retrieval.

This module provides article storage capabilities that work with the
vector store for semantic search and deduplication. It handles article
creation, updates, and queries with integrated vector embeddings.

Key features:
- Automatic embedding generation
- Duplicate detection via vector similarity
- Topic-based filtering
- Time-based retention policies
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional, Sequence
import uuid

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.core.models import Article as CoreArticle
from app.rag.vector_store import VectorStore, EmbeddingConfig, SearchResult


logger = get_logger(__name__)


@dataclass
class ArticleFilter:
    """Filter criteria for article queries.

    Attributes:
        topics: List of topics to include
        sources: List of sources to include
        min_relevance: Minimum relevance score
        date_from: Start date for filtering
        date_to: End date for filtering
        exclude_ids: IDs to exclude from results
    """

    topics: Optional[list[str]] = None
    sources: Optional[list[str]] = None
    min_relevance: int = 0
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    exclude_ids: Optional[list[str]] = None


class ArticleStore:
    """Article storage with vector search capabilities.

    This class provides article persistence and retrieval with
    integrated vector embeddings for semantic search. It handles:
    - Article CRUD operations
    - Automatic deduplication
    - Topic-based queries
    - Vector similarity search

    Usage:
        store = ArticleStore(session)
        await store.save(article)
        articles = await store.get_by_topic("AI")
        similar = await store.find_similar(article)
    """

    def __init__(
        self,
        session: AsyncSession,
        vector_store: Optional[VectorStore] = None,
        embedding_config: Optional[EmbeddingConfig] = None,
    ) -> None:
        """Initialize the article store.

        Args:
            session: Async database session
            vector_store: Optional vector store for semantic search
            embedding_config: Embedding configuration
        """
        self.session = session
        self.vector_store = vector_store or VectorStore(
            session=session,
            config=embedding_config,
        )
        self._embedding_config = embedding_config or EmbeddingConfig()

    async def save(self, article: CoreArticle) -> uuid.UUID:
        """Save an article with vector embedding.

        Args:
            article: The article to save

        Returns:
            The article's UUID
        """
        from app.db.models import Article as DBArticle

        # Generate embedding
        text_to_embed = f"{article.title} {article.summary}"
        embedding = await self.vector_store.generate_embedding(text_to_embed)

        # Create database article
        db_article = DBArticle(
            id=uuid.uuid4(),
            title=article.title,
            summary=article.summary,
            content=article.content,
            url=article.url,
            source=article.source,
            topic=article.topic,
            published_date=article.published_date,
            relevance_score=article.relevance_score,
            embedding_vector=embedding,
        )

        self.session.add(db_article)
        await self.session.flush()
        await self.session.refresh(db_article)

        # Also store in vector store for similarity search
        await self.vector_store.upsert(
            id=str(db_article.id),
            embedding=embedding,
            metadata={
                "title": article.title,
                "url": article.url,
                "topic": article.topic,
                "source": article.source,
            },
        )

        logger.info("Saved article: %s (%s)", article.title[:50], db_article.id)
        return db_article.id

    async def save_many(self, articles: list[CoreArticle]) -> list[uuid.UUID]:
        """Save multiple articles efficiently.

        Args:
            articles: List of articles to save

        Returns:
            List of article UUIDs
        """
        ids = []
        for article in articles:
            article_id = await self.save(article)
            ids.append(article_id)
        return ids

    async def get_by_id(self, article_id: uuid.UUID) -> Optional[CoreArticle]:
        """Get an article by ID.

        Args:
            article_id: The article UUID

        Returns:
            The article or None if not found
        """
        from app.db.models import Article as DBArticle

        result = await self.session.execute(
            select(DBArticle).where(DBArticle.id == article_id)
        )
        db_article = result.scalar_one_or_none()

        if db_article is None:
            return None

        return self._db_to_article(db_article)

    async def get_by_url(self, url: str) -> Optional[CoreArticle]:
        """Get an article by URL.

        Args:
            url: The article URL

        Returns:
            The article or None if not found
        """
        from app.db.models import Article as DBArticle

        result = await self.session.execute(
            select(DBArticle).where(DBArticle.url == url)
        )
        db_article = result.scalar_one_or_none()

        if db_article is None:
            return None

        return self._db_to_article(db_article)

    async def get_by_topic(
        self,
        topic: str,
        limit: int = 50,
        min_relevance: int = 0,
    ) -> Sequence[CoreArticle]:
        """Get articles by topic.

        Args:
            topic: The topic to filter by
            limit: Maximum number of articles
            min_relevance: Minimum relevance score

        Returns:
            List of articles matching the criteria
        """
        from app.db.models import Article as DBArticle

        result = await self.session.execute(
            select(DBArticle)
            .where(
                and_(
                    DBArticle.topic == topic,
                    DBArticle.relevance_score >= min_relevance,
                )
            )
            .order_by(DBArticle.relevance_score.desc())
            .limit(limit)
        )

        return [self._db_to_article(a) for a in result.scalars().all()]

    async def search_similar(
        self,
        article: CoreArticle,
        threshold: float = 0.9,
        limit: int = 5,
    ) -> Sequence[CoreArticle]:
        """Find similar articles using vector similarity.

        Args:
            article: The article to find similarities for
            threshold: Minimum similarity score (0.0 to 1.0)
            limit: Maximum number of results

        Returns:
            List of similar articles
        """
        # Generate embedding for the article
        text_to_embed = f"{article.title} {article.summary}"
        embedding = await self.vector_store.generate_embedding(text_to_embed)

        # Search for similar articles
        results = await self.vector_store.search(
            query_embedding=embedding,
            top_k=limit + 1,  # +1 because the article itself might be in results
            similarity_threshold=threshold,
        )

        # Filter out the original article and convert to CoreArticle
        articles = []
        for result in results:
            if result.metadata.get("url") != article.url:
                article_id = uuid.UUID(result.id)
                db_article = await self.get_by_id(article_id)
                if db_article:
                    articles.append(db_article)

        return articles[:limit]

    async def find_duplicates(
        self,
        article: CoreArticle,
        threshold: float = 0.95,
    ) -> list[CoreArticle]:
        """Find duplicate articles.

        Args:
            article: The article to check
            threshold: Similarity threshold for duplicate detection

        Returns:
            List of duplicate articles
        """
        return list(await self.search_similar(article, threshold, 5))

    async def is_duplicate(
        self,
        title: str,
        url: str,
        similarity_threshold: float = 0.95,
    ) -> bool:
        """Check if an article is a duplicate.

        Args:
            title: Article title
            url: Article URL
            similarity_threshold: Threshold for duplicate detection

        Returns:
            True if duplicate, False otherwise
        """
        from app.db.models import Article as DBArticle

        # First check exact URL match
        result = await self.session.execute(
            select(DBArticle).where(DBArticle.url == url)
        )
        if result.scalar_one_or_none():
            return True

        # Then check title similarity
        result = await self.session.execute(
            select(DBArticle).where(
                func.lower(DBArticle.title) == title.lower()
            )
        )
        if result.scalar_one_or_none():
            return True

        return False

    async def get_recent(
        self,
        days: int = 7,
        limit: int = 100,
    ) -> Sequence[CoreArticle]:
        """Get recent articles.

        Args:
            days: Number of days to look back
            limit: Maximum number of articles

        Returns:
            List of recent articles
        """
        from app.db.models import Article as DBArticle

        cutoff_date = datetime.now() - timedelta(days=days)

        result = await self.session.execute(
            select(DBArticle)
            .where(DBArticle.created_at >= cutoff_date)
            .order_by(DBArticle.created_at.desc())
            .limit(limit)
        )

        return [self._db_to_article(a) for a in result.scalars().all()]

    async def query(self, filter: ArticleFilter) -> Sequence[CoreArticle]:
        """Query articles with custom filters.

        Args:
            filter: Filter criteria

        Returns:
            List of matching articles
        """
        from app.db.models import Article as DBArticle

        query = select(DBArticle)

        # Apply filters
        if filter.topics:
            query = query.where(DBArticle.topic.in_(filter.topics))

        if filter.sources:
            query = query.where(DBArticle.source.in_(filter.sources))

        if filter.min_relevance > 0:
            query = query.where(DBArticle.relevance_score >= filter.min_relevance)

        if filter.date_from:
            query = query.where(DBArticle.created_at >= filter.date_from)

        if filter.date_to:
            query = query.where(DBArticle.created_at <= filter.date_to)

        if filter.exclude_ids:
            # Convert to UUIDs for comparison
            exclude_uuids = [uuid.UUID(id) for id in filter.exclude_ids if self._is_valid_uuid(id)]
            if exclude_uuids:
                query = query.where(DBArticle.id.not_in(exclude_uuids))

        query = query.order_by(DBArticle.relevance_score.desc())

        result = await self.session.execute(query)
        return [self._db_to_article(a) for a in result.scalars().all()]

    async def delete_old(self, days: int = 90) -> int:
        """Delete old articles.

        Args:
            days: Age threshold in days

        Returns:
            Number of articles deleted
        """
        from app.db.models import Article as DBArticle

        cutoff_date = datetime.now() - timedelta(days=days)

        result = await self.session.execute(
            select(func.count(DBArticle.id)).where(DBArticle.created_at < cutoff_date)
        )
        count = result.scalar() or 0

        if count > 0:
            await self.session.execute(
                DBArticle.__table__.delete().where(DBArticle.created_at < cutoff_date)
            )
            await self.session.flush()

        logger.info("Deleted %d old articles (older than %d days)", count, days)
        return count

    def _db_to_article(self, db_article: "DBArticle") -> CoreArticle:
        """Convert database article to core Article model.

        Args:
            db_article: Database article model

        Returns:
            Core Article instance
        """
        return CoreArticle(
            title=db_article.title,
            summary=db_article.summary or "",
            url=db_article.url,
            topic=db_article.topic,
            published_date=db_article.published_date.isoformat() if db_article.published_date else None,
            content=db_article.content or "",
            source=db_article.source,
            relevance_score=db_article.relevance_score,
        )

    @staticmethod
    def _is_valid_uuid(value: str) -> bool:
        """Check if a string is a valid UUID.

        Args:
            value: String to check

        Returns:
            True if valid UUID, False otherwise
        """
        try:
            uuid.UUID(value)
            return True
        except (ValueError, TypeError):
            return False
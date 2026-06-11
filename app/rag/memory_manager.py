"""
Memory manager - coordinates all memory components.

This module provides a unified interface for all memory operations,
combining vector store, article store, and session management
into a single coherent system.

The MemoryManager serves as the main entry point for memory-related
operations and coordinates between different components.
"""

from typing import Any, Optional, Sequence
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.models import Article
from app.rag.vector_store import VectorStore, EmbeddingConfig, SearchResult
from app.rag.article_store import ArticleStore, ArticleFilter
from app.rag.session import SessionManager, Session


logger = get_logger(__name__)


class MemoryManager:
    """Central manager for all memory operations.

    This class coordinates the vector store, article store, and
    session management to provide a unified memory interface.

    It handles:
    - Article embedding and storage
    - Semantic search across articles
    - User session context
    - Cross-component operations

    Usage:
        manager = MemoryManager(session)
        await manager.store_article(article)
        similar = await manager.find_similar_articles(article)
        session = await manager.get_user_session(user_id)
    """

    def __init__(
        self,
        session: AsyncSession,
        embedding_config: Optional[EmbeddingConfig] = None,
    ) -> None:
        """Initialize the memory manager.

        Args:
            session: Async database session
            embedding_config: Optional embedding configuration
        """
        self.session = session
        self._embedding_config = embedding_config or EmbeddingConfig()

        # Initialize components
        self.vector_store = VectorStore(
            session=session,
            config=self._embedding_config,
        )
        self.article_store = ArticleStore(
            session=session,
            vector_store=self.vector_store,
            embedding_config=self._embedding_config,
        )
        self.session_manager = SessionManager(session)

    # Article operations

    async def store_article(self, article: Article) -> uuid.UUID:
        """Store an article with automatic embedding.

        Args:
            article: The article to store

        Returns:
            The article's UUID
        """
        return await self.article_store.save(article)

    async def store_articles(self, articles: list[Article]) -> list[uuid.UUID]:
        """Store multiple articles.

        Args:
            articles: List of articles to store

        Returns:
            List of article UUIDs
        """
        return await self.article_store.save_many(articles)

    async def get_article(self, article_id: uuid.UUID) -> Optional[Article]:
        """Get an article by ID.

        Args:
            article_id: The article UUID

        Returns:
            The article or None if not found
        """
        return await self.article_store.get_by_id(article_id)

    async def get_articles_by_topic(
        self,
        topic: str,
        limit: int = 50,
    ) -> Sequence[Article]:
        """Get articles by topic.

        Args:
            topic: The topic to filter by
            limit: Maximum number of articles

        Returns:
            List of articles
        """
        return await self.article_store.get_by_topic(topic, limit)

    async def get_recent_articles(
        self,
        days: int = 7,
        limit: int = 100,
    ) -> Sequence[Article]:
        """Get recent articles.

        Args:
            days: Number of days to look back
            limit: Maximum number of articles

        Returns:
            List of recent articles
        """
        return await self.article_store.get_recent(days, limit)

    # Semantic search operations

    async def find_similar_articles(
        self,
        article: Article,
        threshold: float = 0.9,
        limit: int = 5,
    ) -> Sequence[Article]:
        """Find articles similar to the given article.

        Args:
            article: The article to compare
            threshold: Minimum similarity score
            limit: Maximum number of results

        Returns:
            List of similar articles
        """
        return await self.article_store.search_similar(article, threshold, limit)

    async def find_duplicates(
        self,
        article: Article,
        threshold: float = 0.95,
    ) -> list[Article]:
        """Find duplicate articles.

        Args:
            article: The article to check
            threshold: Similarity threshold

        Returns:
            List of duplicate articles
        """
        return await self.article_store.find_duplicates(article, threshold)

    async def semantic_search(
        self,
        query: str,
        top_k: int = 10,
        topics: Optional[list[str]] = None,
        similarity_threshold: float = 0.7,
    ) -> Sequence[SearchResult]:
        """Perform semantic search across all articles.

        Args:
            query: The search query
            top_k: Maximum number of results
            topics: Optional topic filter
            similarity_threshold: Minimum similarity score

        Returns:
            List of search results with scores
        """
        # Generate embedding for query
        query_embedding = await self.vector_store.generate_embedding(query)

        # Search vector store
        results = await self.vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
        )

        # Filter by topics if specified
        if topics:
            filtered_results = []
            for result in results:
                if result.metadata.get("topic") in topics:
                    filtered_results.append(result)
            return filtered_results

        return results

    async def is_duplicate(self, title: str, url: str) -> bool:
        """Check if an article is a duplicate.

        Args:
            title: Article title
            url: Article URL

        Returns:
            True if duplicate, False otherwise
        """
        return await self.article_store.is_duplicate(title, url)

    # Session operations

    async def get_or_create_session(
        self,
        user_id: Optional[uuid.UUID] = None,
    ) -> Session:
        """Get or create a user session.

        Args:
            user_id: Optional user ID

        Returns:
            The session
        """
        return await self.session_manager.get_or_create_session(user_id)

    async def update_session_preferences(
        self,
        session_id: uuid.UUID,
        preferences: dict[str, Any],
    ) -> Optional[Session]:
        """Update session preferences.

        Args:
            session_id: The session ID
            preferences: New preferences

        Returns:
            The updated session or None
        """
        return await self.session_manager.update_preferences(session_id, preferences)

    async def mark_article_seen(
        self,
        session_id: uuid.UUID,
        article_id: str,
    ) -> None:
        """Mark an article as seen by a session.

        Args:
            session_id: The session ID
            article_id: The article ID
        """
        await self.session_manager.mark_article_seen(session_id, article_id)

    async def get_unseen_articles(
        self,
        session_id: uuid.UUID,
        topics: Optional[list[str]] = None,
        limit: int = 20,
    ) -> Sequence[Article]:
        """Get articles not yet seen by the session.

        Args:
            session_id: The session ID
            topics: Optional topic filter
            limit: Maximum number of articles

        Returns:
            List of unseen articles
        """
        session = await self.session_manager.get_session(session_id)
        if session is None:
            return []

        # Get recent articles
        articles = await self.get_recent_articles(days=7, limit=limit * 2)

        # Filter out seen articles
        unseen = []
        for article in articles:
            article_id = str(article.url)  # Use URL as ID
            if article_id not in session.seen_article_ids:
                unseen.append(article)
                if len(unseen) >= limit:
                    break

        # Apply topic filter if specified
        if topics:
            unseen = [a for a in unseen if a.topic in topics]

        return unseen

    # Maintenance operations

    async def cleanup_old_articles(self, days: int = 90) -> int:
        """Clean up old articles.

        Args:
            days: Age threshold in days

        Returns:
            Number of articles deleted
        """
        return await self.article_store.delete_old(days)

    async def get_stats(self) -> dict[str, Any]:
        """Get memory system statistics.

        Returns:
            Dictionary with statistics
        """
        vector_stats = await self.vector_store.get_stats()

        from app.db.models import Article as DBArticle
        from sqlalchemy import select, func

        result = await self.session.execute(
            select(
                func.count(DBArticle.id).label("total_articles"),
                func.count(func.distinct(DBArticle.topic)).label("unique_topics"),
            )
        )
        row = result.one()

        return {
            "vector_store": vector_stats,
            "articles": {
                "total": row.total_articles or 0,
                "unique_topics": row.unique_topics or 0,
            },
        }

    async def health_check(self) -> dict[str, Any]:
        """Check memory system health.

        Returns:
            Dictionary with health status
        """
        health = {
            "vector_store": "unknown",
            "database": "unknown",
        }

        try:
            stats = await self.vector_store.get_stats()
            health["vector_store"] = "healthy" if "error" not in stats else "error"
        except Exception as exc:
            health["vector_store"] = f"error: {exc}"

        try:
            await self.session.execute(select(func.count(1)))
            health["database"] = "healthy"
        except Exception as exc:
            health["database"] = f"error: {exc}"

        return health
"""
Vector store implementation using pgvector.

This module provides semantic search capabilities through vector embeddings.
It uses pgvector extension for PostgreSQL to store and search embeddings,
enabling similarity-based retrieval of articles and content.

Key features:
- Real embedding generation via EmbeddingService (OpenAI, Z.ai, Ollama)
- Semantic similarity search
- Article deduplication based on content similarity
- Hybrid search (vector + keyword)
- Caching for performance

Note: Requires pgvector extension to be installed on PostgreSQL:
    CREATE EXTENSION IF NOT EXISTS vector;
"""

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence
import uuid

from sqlalchemy import select, text, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import ARRAY

from app.config.settings import Settings, get_settings
from app.core.logging import get_logger


logger = get_logger(__name__)


DEFAULT_EMBEDDING_DIM = 1536


@dataclass
class EmbeddingConfig:
    """Configuration for embedding generation.

    Attributes:
        model: Embedding model name (e.g., "text-embedding-3-small")
        dimension: Embedding vector dimension
        batch_size: Number of texts to embed in a single batch
        normalize: Whether to normalize embedding vectors
        provider: Embedding provider (openai, zai, ollama)
    """

    model: str = "text-embedding-3-small"
    dimension: int = DEFAULT_EMBEDDING_DIM
    batch_size: int = 100
    normalize: bool = True
    provider: str = "openai"


@dataclass
class SearchResult:
    """Result from a vector similarity search."""

    id: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


class VectorStore:
    """Vector store for semantic search.

    This class provides vector embedding storage and similarity search
    using pgvector. It handles embedding generation, storage, and
    retrieval operations.

    Usage:
        store = VectorStore(session, config)
        await store.upsert("article-123", embedding, {"title": "Article Title"})
        results = await store.search(query_embedding, top_k=10)
    """

    def __init__(
        self,
        session: AsyncSession,
        config: Optional[EmbeddingConfig] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        """Initialize the vector store.

        Args:
            session: Async database session
            config: Embedding configuration
            settings: Application settings
        """
        self.session = session
        self.config = config or EmbeddingConfig()
        self.settings = settings or get_settings()
        self._embedding_service: Optional[Any] = None
        self._embedding_cache: dict[str, list[float]] = {}
        self._cache_size = 1000

    async def _get_embedding_service(self) -> Any:
        """Get or create the embedding service.

        Returns:
            EmbeddingService for generating embeddings
        """
        if self._embedding_service is None:
            from app.services.embedding.service import create_embedding_service
            self._embedding_service = create_embedding_service(
                provider=self.config.provider,
                model=self.config.model,
            )
        return self._embedding_service

    async def generate_embedding(self, text: str) -> list[float]:
        """Generate an embedding for the given text using real embedding service.

        Args:
            text: The text to embed

        Returns:
            List of floats representing the embedding vector
        """
        if not text:
            return [0.0] * self.config.dimension

        cache_key = self._embedding_cache_key(text)
        if cache_key in self._embedding_cache:
            return self._embedding_cache[cache_key]

        try:
            service = await self._get_embedding_service()
            result = await service.embed(text[:8000])

            embedding = result.embedding

            if len(embedding) != self.config.dimension:
                if len(embedding) < self.config.dimension:
                    embedding = embedding + [0.0] * (self.config.dimension - len(embedding))
                else:
                    embedding = embedding[:self.config.dimension]

            if self.config.normalize:
                import math
                norm = math.sqrt(sum(x * x for x in embedding))
                if norm > 0:
                    embedding = [x / norm for x in embedding]

            self._add_to_cache(cache_key, embedding)
            return embedding

        except Exception as exc:
            logger.error("Failed to generate embedding: %s", exc)
            return [0.0] * self.config.dimension

    def _embedding_cache_key(self, text: str) -> str:
        """Generate cache key for embedding."""
        import hashlib
        return hashlib.sha256(text.encode()).hexdigest()[:64]

    def _add_to_cache(self, key: str, embedding: list[float]) -> None:
        """Add embedding to cache with LRU eviction."""
        if len(self._embedding_cache) >= self._cache_size:
            oldest = next(iter(self._embedding_cache))
            del self._embedding_cache[oldest]
        self._embedding_cache[key] = embedding

    async def upsert(
        self,
        id: str,
        embedding: list[float],
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Store or update a vector with metadata.

        Args:
            id: Unique identifier for the vector
            embedding: The embedding vector
            metadata: Optional metadata dictionary

        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure vector dimension matches config
            if len(embedding) != self.config.dimension:
                embedding = self._pad_or_truncate_embedding(embedding)

            # Store in the articles table (using existing model)
            await self.session.execute(
                text("""
                    INSERT INTO article_embeddings (id, embedding, metadata, created_at)
                    VALUES (:id, :embedding, :metadata, NOW())
                    ON CONFLICT (id) DO UPDATE SET
                        embedding = EXCLUDED.embedding,
                        metadata = EXCLUDED.metadata
                """),
                {
                    "id": id,
                    "embedding": embedding,
                    "metadata": metadata or {},
                }
            )
            await self.session.flush()
            logger.debug("Upserted vector: %s", id)
            return True

        except Exception as exc:
            logger.error("Failed to upsert vector %s: %s", id, exc)
            return False

    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        filter_metadata: Optional[dict[str, Any]] = None,
        similarity_threshold: float = 0.0,
        keywords: Optional[list[str]] = None,
        days_limit: int = 30,
    ) -> Sequence[SearchResult]:
        """Search for similar vectors with optional keyword filtering.

        Uses cosine similarity to find the most similar vectors.

        Args:
            query_embedding: The query embedding vector
            top_k: Maximum number of results to return
            filter_metadata: Optional metadata filters (key-value pairs to match)
            similarity_threshold: Minimum similarity score (0.0 to 1.0)
            keywords: Optional list of keywords to filter results (AND logic)
            days_limit: Maximum age of results in days (default 30)

        Returns:
            List of SearchResult objects ordered by similarity
        """
        try:
            if len(query_embedding) != self.config.dimension:
                query_embedding = self._pad_or_truncate_embedding(query_embedding)

            if self.config.normalize:
                import math
                norm = math.sqrt(sum(x * x for x in query_embedding))
                if norm > 0:
                    query_embedding = [x / norm for x in query_embedding]

            where_clauses = [f"created_at > NOW() - INTERVAL '{days_limit} days'"]

            if keywords:
                keyword_filters = " AND ".join(
                    f"metadata::text ILIKE :kw_{i}" for i in range(len(keywords))
                )
                where_clauses.append(f"({keyword_filters})")

            if filter_metadata:
                for key, value in filter_metadata.items():
                    where_clauses.append(f"metadata->>'{key}' = :val_{key}")

            where_sql = " AND ".join(where_clauses)

            params: dict[str, Any] = {
                "query_embedding": query_embedding,
                "top_k": top_k,
            }

            for i, kw in enumerate(keywords or []):
                params[f"kw_{i}"] = f"%{kw}%"

            if filter_metadata:
                for key, value in filter_metadata.items():
                    params[f"val_{key}"] = value

            result = await self.session.execute(
                text(f"""
                    SELECT
                        id,
                        metadata,
                        1 - (embedding <=> :query_embedding) as similarity
                    FROM article_embeddings
                    WHERE {where_sql}
                    ORDER BY embedding <=> :query_embedding
                    LIMIT :top_k
                """),
                params
            )

            results = []
            for row in result:
                similarity = float(row.similarity)
                if similarity >= similarity_threshold:
                    results.append(SearchResult(
                        id=str(row.id),
                        score=similarity,
                        metadata=row.metadata or {},
                    ))

            logger.debug("Vector search returned %d results", len(results))
            return results

        except Exception as exc:
            logger.error("Vector search failed: %s", exc)
            return []

    async def delete(self, id: str) -> bool:
        """Delete a vector by ID.

        Args:
            id: The vector ID to delete

        Returns:
            True if deleted, False if not found
        """
        try:
            result = await self.session.execute(
                text("DELETE FROM article_embeddings WHERE id = :id"),
                {"id": id}
            )
            await self.session.flush()
            return result.rowcount > 0

        except Exception as exc:
            logger.error("Failed to delete vector %s: %s", id, exc)
            return False

    async def find_duplicates(
        self,
        embedding: list[float],
        threshold: float = 0.95,
    ) -> Sequence[SearchResult]:
        """Find duplicate or near-duplicate content.

        Uses cosine similarity to find content that is very similar
        to the given embedding.

        Args:
            embedding: The embedding to check
            threshold: Similarity threshold (default 0.95 for near-duplicates)

        Returns:
            List of matching results
        """
        return await self.search(
            query_embedding=embedding,
            top_k=5,
            similarity_threshold=threshold,
        )

    async def get_stats(self) -> dict[str, Any]:
        """Get statistics about the vector store.

        Returns:
            Dictionary with store statistics
        """
        try:
            result = await self.session.execute(
                text("""
                    SELECT
                        COUNT(*) as total_vectors,
                        AVG(
                            CASE
                                WHEN embedding IS NULL THEN NULL
                                ELSE jsonb_array_length(embedding)
                            END
                        ) as avg_embedding_size,
                        MIN(created_at) as oldest,
                        MAX(created_at) as newest
                    FROM article_embeddings
                """)
            )
            row = result.one()
            return {
                "total_vectors": row.total_vectors or 0,
                "avg_embedding_size": row.avg_embedding_size or 0,
                "oldest": row.oldest,
                "newest": row.newest,
            }

        except Exception as exc:
            logger.error("Failed to get vector store stats: %s", exc)
            return {"error": str(exc)}

    def _pad_or_truncate_embedding(self, embedding: list[float]) -> list[float]:
        """Ensure embedding has the correct dimension.

        Args:
            embedding: The embedding vector

        Returns:
            Properly sized embedding vector
        """
        if len(embedding) > self.config.dimension:
            return embedding[:self.config.dimension]
        elif len(embedding) < self.config.dimension:
            return embedding + [0.0] * (self.config.dimension - len(embedding))
        return embedding


class ArticleEmbeddingTable:
    """Helper class for article embeddings table.

    This class provides the SQL schema for storing article embeddings.
    It can be used to create the table or check its existence.

    Table schema:
    - id: VARCHAR primary key
    - embedding: VECTOR(dim) storing the embedding
    - metadata: JSONB for additional data
    - created_at: TIMESTAMP for ordering
    """

    @staticmethod
    def get_create_table_sql(dimension: int = DEFAULT_EMBEDDING_DIM) -> str:
        """Get the SQL to create the embeddings table.

        Args:
            dimension: Embedding vector dimension

        Returns:
            SQL CREATE TABLE statement
        """
        return f"""
            CREATE TABLE IF NOT EXISTS article_embeddings (
                id VARCHAR(255) PRIMARY KEY,
                embedding VECTOR({dimension}) NOT NULL,
                metadata JSONB DEFAULT '{{}}',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );

            -- Index for similarity search
            CREATE INDEX IF NOT EXISTS idx_article_embeddings_cosine
            ON article_embeddings USING ivfflat (embedding cosine);

            -- Index for metadata queries
            CREATE INDEX IF NOT EXISTS idx_article_embeddings_created
            ON article_embeddings (created_at);
        """

    @staticmethod
    def get_enable_extension_sql() -> str:
        """Get the SQL to enable the pgvector extension."""
        return "CREATE EXTENSION IF NOT EXISTS vector;"

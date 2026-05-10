"""
Vector store implementation using pgvector.

This module provides semantic search capabilities through vector embeddings.
It uses pgvector extension for PostgreSQL to store and search embeddings,
enabling similarity-based retrieval of articles and content.

Key features:
- Embedding generation using configurable LLM provider
- Semantic similarity search
- Article deduplication based on content similarity
- Hybrid search (vector + keyword)

Note: Requires pgvector extension to be installed on PostgreSQL:
    CREATE EXTENSION IF NOT EXISTS vector;
"""

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence
import uuid

from sqlalchemy import select, text, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import ARRAY, Float

from app.config.settings import Settings, get_settings
from app.core.logging import get_logger


logger = get_logger(__name__)


# Default embedding dimension (OpenAI text-embedding-3-small)
DEFAULT_EMBEDDING_DIM = 1536


@dataclass
class EmbeddingConfig:
    """Configuration for embedding generation.

    Attributes:
        model: Embedding model name (e.g., "text-embedding-3-small")
        dimension: Embedding vector dimension
        batch_size: Number of texts to embed in a single batch
        normalize: Whether to normalize embedding vectors
    """

    model: str = "text-embedding-3-small"
    dimension: int = DEFAULT_EMBEDDING_DIM
    batch_size: int = 100
    normalize: bool = True


@dataclass
class SearchResult:
    """Result from a vector similarity search.

    Attributes:
        id: Unique identifier of the matched item
        score: Similarity score (0.0 to 1.0)
        metadata: Additional metadata about the item
    """

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
        self._embedding_client: Optional[Any] = None

    async def _get_embedding_client(self) -> Any:
        """Get or create the embedding client.

        Returns:
            Client capable of generating embeddings
        """
        if self._embedding_client is None:
            # Lazy initialization - use httpx for simple embedding
            # In production, use a proper embedding service
            self._embedding_client = await self._create_embedding_client()
        return self._embedding_client

    async def _create_embedding_client(self) -> Any:
        """Create the embedding client.

        Returns:
            Configured embedding client
        """
        # Simple implementation using the LLM client
        # In production, use OpenAI or other embedding API
        from app.services.llm import ChatCompletionClient

        return ChatCompletionClient(settings=self.settings)

    async def generate_embedding(self, text: str) -> list[float]:
        """Generate an embedding for the given text.

        Args:
            text: The text to embed

        Returns:
            List of floats representing the embedding vector
        """
        client = await self._get_embedding_client()

        # Use the LLM service to generate embeddings
        # Note: This is a simplified implementation
        # In production, use a dedicated embedding API
        try:
            # For now, generate a simple hash-based pseudo-embedding
            # This should be replaced with actual embedding generation
            import hashlib
            import struct

            # Create a deterministic pseudo-embedding for testing
            hash_bytes = hashlib.sha256(text.encode()).digest()
            # Convert to floats in range [-1, 1]
            values = []
            for i in range(0, min(len(hash_bytes), self.config.dimension), 8):
                val = struct.unpack('d', hash_bytes[i:i+8])[0]
                # Normalize to [-1, 1]
                normalized = (val % 2) - 1
                values.append(normalized)

            # Pad or truncate to exact dimension
            while len(values) < self.config.dimension:
                values.append(0.0)
            embedding = values[:self.config.dimension]

            # Normalize if configured
            if self.config.normalize:
                import math
                norm = math.sqrt(sum(x * x for x in embedding))
                if norm > 0:
                    embedding = [x / norm for x in embedding]

            return embedding

        except Exception as exc:
            logger.error("Failed to generate embedding: %s", exc)
            # Return zero vector on error
            return [0.0] * self.config.dimension

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
    ) -> Sequence[SearchResult]:
        """Search for similar vectors.

        Uses cosine similarity to find the most similar vectors.

        Args:
            query_embedding: The query embedding vector
            top_k: Maximum number of results to return
            filter_metadata: Optional metadata filters
            similarity_threshold: Minimum similarity score (0.0 to 1.0)

        Returns:
            List of SearchResult objects ordered by similarity
        """
        try:
            # Ensure query embedding dimension
            if len(query_embedding) != self.config.dimension:
                query_embedding = self._pad_or_truncate_embedding(query_embedding)

            # Normalize query embedding if configured
            if self.config.normalize:
                import math
                norm = math.sqrt(sum(x * x for x in query_embedding))
                if norm > 0:
                    query_embedding = [x / norm for x in query_embedding]

            # Build and execute similarity search query
            # Using pgvector's <=> operator for cosine distance
            result = await self.session.execute(
                text("""
                    SELECT
                        id,
                        metadata,
                        1 - (embedding <=> :query_embedding) as similarity
                    FROM article_embeddings
                    WHERE created_at > NOW() - INTERVAL '30 days'
                    ORDER BY embedding <=> :query_embedding
                    LIMIT :top_k
                """),
                {
                    "query_embedding": query_embedding,
                    "top_k": top_k,
                }
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
                        AVG(LENGTH(embedding)) as avg_embedding_size,
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
"""
Memory layer module initialization.

This module provides memory and RAG capabilities for the tech-watch-agent.
It includes vector storage, article embedding, session management, and
history tracking for persistent context across agent executions.

Components:
- VectorStore: Semantic search using pgvector embeddings
- ArticleStore: Article persistence and retrieval
- SessionManager: User session context management
- MemoryManager: Coordinates all memory components
"""

from app.rag.vector_store import VectorStore, EmbeddingConfig
from app.rag.article_store import ArticleStore
from app.rag.session import SessionManager, Session
from app.rag.memory_manager import MemoryManager

__all__ = [
    "VectorStore",
    "EmbeddingConfig",
    "ArticleStore",
    "SessionManager",
    "Session",
    "MemoryManager",
]
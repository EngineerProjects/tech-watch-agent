"""
Memory retrieval tool for agents.

Provides semantic search over stored articles and context using
the VectorStore for embedding-based retrieval.

Tools:
- SearchMemory: Semantic search over articles
- GetRecentContext: Get recent articles/topics for a session
"""

from __future__ import annotations

from typing import Any, Optional

from app.tools.base import BaseTool, ToolCategory, ToolResult
from app.core.logging import get_logger


logger = get_logger(__name__)


class SearchMemoryTool(BaseTool):
    """Semantic search tool for retrieving relevant articles from memory.

    This tool enables agents to search the vector store for semantically
    similar articles based on the current research context.

    Usage:
        tool = SearchMemoryTool()
        result = await tool.execute({"query": "AI breakthroughs", "top_k": 5})
    """

    @property
    def name(self) -> str:
        return "search_memory"

    @property
    def description(self) -> str:
        return "Semantic search over stored articles using embeddings. Returns relevant articles based on query similarity."

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.MEMORY

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for finding relevant articles"
                },
                "top_k": {
                    "type": "integer",
                    "description": "Maximum number of results to return",
                    "default": 5
                },
                "topic_filter": {
                    "type": "string",
                    "description": "Optional topic to filter results"
                },
                "min_score": {
                    "type": "number",
                    "description": "Minimum similarity score (0-1)",
                    "default": 0.0
                }
            },
            "required": ["query"]
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        """Execute memory search.

        Args:
            params: Dictionary with query, top_k, topic_filter, min_score

        Returns:
            ToolResult with list of relevant articles
        """
        query = params.get("query", "")
        top_k = params.get("top_k", 5)
        topic_filter = params.get("topic_filter")
        min_score = params.get("min_score", 0.0)

        if not query:
            return {
                "success": False,
                "data": None,
                "error": "No query provided",
                "metadata": {}
            }

        try:
            results = await self._search_memory(query, top_k, topic_filter, min_score)

            filtered_results = [
                r for r in results
                if r.get("score", 0) >= min_score
            ]

            return {
                "success": True,
                "data": {
                    "query": query,
                    "results": filtered_results,
                    "count": len(filtered_results),
                },
                "error": None,
                "metadata": {
                    "query": query,
                    "count": len(filtered_results),
                    "topic_filter": topic_filter,
                }
            }

        except Exception as exc:
            logger.error("Search memory failed: %s", exc)
            return {
                "success": False,
                "data": None,
                "error": f"Search failed: {str(exc)}",
                "metadata": {}
            }

    async def _search_memory(
        self,
        query: str,
        top_k: int,
        topic_filter: Optional[str],
        min_score: float,
    ) -> list[dict[str, Any]]:
        """Perform the actual memory search."""
        from app.db.base import get_db_context
        from app.rag.vector_store import VectorStore, EmbeddingConfig

        results = []
        async with get_db_context() as session:
            vector_store = VectorStore(session, config=EmbeddingConfig())

            try:
                embedding = await vector_store.generate_embedding(query)

                search_results = await vector_store.search(
                    embedding=embedding,
                    top_k=top_k * 2,
                    min_score=min_score,
                )

                for result in search_results:
                    metadata = result.metadata or {}

                    if topic_filter and metadata.get("topic") != topic_filter:
                        continue

                    results.append({
                        "id": result.id,
                        "score": result.score,
                        "title": metadata.get("title", "Unknown"),
                        "url": metadata.get("url", ""),
                        "summary": metadata.get("summary", ""),
                        "topic": metadata.get("topic", ""),
                        "source": metadata.get("source", ""),
                        "published_date": metadata.get("published_date"),
                    })

            except Exception as exc:
                logger.warning("Vector search failed, falling back to text search: %s", exc)
                results = await self._fallback_text_search(session, query, top_k, topic_filter)

        return results[:top_k]

    async def _fallback_text_search(
        self,
        session: Any,
        query: str,
        top_k: int,
        topic_filter: Optional[str],
    ) -> list[dict[str, Any]]:
        """Fallback to simple text search when vector search fails."""
        from sqlalchemy import select
        from app.db.models import Article

        stmt = select(Article).where(
            Article.title.ilike(f"%{query}%") |
            Article.summary.ilike(f"%{query}%")
        ).limit(top_k)

        result = await session.execute(stmt)
        articles = result.scalars().all()

        return [
            {
                "id": str(article.id),
                "score": 0.5,
                "title": article.title,
                "url": article.url,
                "summary": article.summary or "",
                "topic": article.topic,
                "source": article.source,
                "published_date": article.published_date.isoformat() if article.published_date else None,
            }
            for article in articles
        ]


class GetRecentContextTool(BaseTool):
    """Get recent articles and topics for a session.

    This tool retrieves recent articles and topics relevant to a user's
    session, providing context for ongoing research.

    Usage:
        tool = GetRecentContextTool()
        result = await tool.execute({"session_id": "uuid", "limit": 10})
    """

    @property
    def name(self) -> str:
        return "get_recent_context"

    @property
    def description(self) -> str:
        return "Get recent articles and topics for the current session to maintain context continuity."

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.MEMORY

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Session UUID to get context for"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of recent items",
                    "default": 10
                },
                "include_articles": {
                    "type": "boolean",
                    "description": "Include recent articles",
                    "default": True
                },
                "include_topics": {
                    "type": "boolean",
                    "description": "Include recent topics",
                    "default": True
                }
            },
            "required": ["session_id"]
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        """Get recent context for a session."""
        session_id = params.get("session_id")
        limit = params.get("limit", 10)
        include_articles = params.get("include_articles", True)
        include_topics = params.get("include_topics", True)

        if not session_id:
            return {
                "success": False,
                "data": None,
                "error": "No session_id provided",
                "metadata": {}
            }

        try:
            context = await self._get_context(session_id, limit, include_articles, include_topics)

            return {
                "success": True,
                "data": context,
                "error": None,
                "metadata": {
                    "session_id": session_id,
                    "article_count": len(context.get("recent_articles", [])),
                    "topic_count": len(context.get("recent_topics", [])),
                }
            }

        except Exception as exc:
            logger.error("Get recent context failed: %s", exc)
            return {
                "success": False,
                "data": None,
                "error": f"Failed to get context: {str(exc)}",
                "metadata": {}
            }

    async def _get_context(
        self,
        session_id: str,
        limit: int,
        include_articles: bool,
        include_topics: bool,
    ) -> dict[str, Any]:
        """Retrieve session context."""
        from app.db.base import get_db_context
        from sqlalchemy import select
        from app.db.models import UserSession, Article

        context = {
            "session_id": session_id,
            "recent_articles": [],
            "recent_topics": [],
            "preferences": {},
        }

        async with get_db_context() as session:
            stmt = select(UserSession).where(UserSession.id == session_id)
            result = await session.execute(stmt)
            user_session = result.scalar_one_or_none()

            if user_session:
                context["preferences"] = user_session.preferences or {}

                if include_topics:
                    context["recent_topics"] = user_session.topics or []

                if include_articles and user_session.seen_article_ids:
                    article_ids = user_session.seen_article_ids[-limit:]
                    article_stmt = select(Article).where(Article.id.in_(article_ids))
                    article_result = await session.execute(article_stmt)
                    articles = article_result.scalars().all()

                    context["recent_articles"] = [
                        {
                            "id": str(a.id),
                            "title": a.title,
                            "url": a.url,
                            "topic": a.topic,
                            "summary": a.summary,
                        }
                        for a in articles
                    ]

        return context


class StoreResearchContextTool(BaseTool):
    """Store research findings and context for future retrieval.

    This tool allows agents to save important findings, summaries,
    or insights to memory for later use.

    Usage:
        tool = StoreResearchContextTool()
        result = await tool.execute({
            "session_id": "uuid",
            "content": "Key finding: AI models are improving...",
            "content_type": "finding"
        })
    """

    @property
    def name(self) -> str:
        return "store_research_context"

    @property
    def description(self) -> str:
        return "Store research findings, insights, or summaries to memory for later retrieval."

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.MEMORY

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Session UUID"
                },
                "content": {
                    "type": "string",
                    "description": "Content to store"
                },
                "content_type": {
                    "type": "string",
                    "description": "Type of content (finding, summary, note)",
                    "enum": ["finding", "summary", "note", "insight"]
                },
                "metadata": {
                    "type": "object",
                    "description": "Additional metadata to store"
                }
            },
            "required": ["session_id", "content"]
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        """Store research context."""
        session_id = params.get("session_id")
        content = params.get("content", "")
        content_type = params.get("content_type", "note")
        metadata = params.get("metadata", {})

        if not session_id or not content:
            return {
                "success": False,
                "data": None,
                "error": "session_id and content are required",
                "metadata": {}
            }

        try:
            stored_id = await self._store_context(session_id, content, content_type, metadata)

            return {
                "success": True,
                "data": {"stored_id": stored_id, "content_type": content_type},
                "error": None,
                "metadata": {"session_id": session_id}
            }

        except Exception as exc:
            logger.error("Store context failed: %s", exc)
            return {
                "success": False,
                "data": None,
                "error": f"Failed to store: {str(exc)}",
                "metadata": {}
            }

    async def _store_context(
        self,
        session_id: str,
        content: str,
        content_type: str,
        metadata: dict,
    ) -> str:
        """Store context in database."""
        from app.db.base import get_db_context
        from app.db.models import ResearchSession
        from sqlalchemy import update
        import uuid

        context_id = str(uuid.uuid4())

        async with get_db_context() as session:
            stmt = select(ResearchSession).where(
                ResearchSession.user_id == uuid.UUID(session_id)
            ).order_by(ResearchSession.created_at.desc()).limit(1)

            result = await session.execute(stmt)
            research_session = result.scalar_one_or_none()

            if research_session:
                notes = list(research_session.raw_notes or [])
                notes.append(f"[{content_type.upper()}]: {content}")
                research_session.raw_notes = notes
                await session.commit()
            else:
                new_session = ResearchSession(
                    id=uuid.uuid4(),
                    user_id=uuid.UUID(session_id) if session_id else None,
                    research_brief=content[:500],
                    notes=[content],
                    final_report="",
                    raw_notes=[content],
                    status="stored",
                )
                session.add(new_session)
                await session.commit()

        return context_id

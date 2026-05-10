"""
FastAPI main application with comprehensive API endpoints.

This module defines the FastAPI application with routes for:
- Newsletter generation agent
- Deep research agent
- Article management
- User management
- Tool registry
- Health checks and metrics
- History and statistics
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional
from contextlib import asynccontextmanager

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr

from app.config.settings import Settings, get_settings
from app.db.base import get_db_session, async_session_factory, init_db, close_db
from app.db.repositories import (
    ArticleRepository,
    NewsletterRunRepository,
    UserRepository,
    UserTopicRepository,
    ResearchSessionRepository,
)
from app.db.models import User, UserTopic, Article, NewsletterRun
from app.agents.newsletter.agent import create_newsletter_agent, NewsletterAgent
from app.agents.deep_research.agent import create_deep_research_agent, DeepResearchAgent
from app.agents.deep_research.config import DeepResearchConfig
from app.memory.memory_manager import MemoryManager
from app.tools.registry import get_global_registry, ToolRegistry
from app.tools.base import BaseTool, ToolCategory
from app.core.logging import get_logger


logger = get_logger(__name__)


# Request/Response Models

class HealthResponse(BaseModel):
    status: str
    database: str
    memory: str
    agents: dict[str, bool]


class UserCreate(BaseModel):
    email: EmailStr
    username: Optional[str] = None
    preferences: dict[str, Any] = Field(default_factory=dict)


class UserResponse(BaseModel):
    id: str
    email: str
    username: Optional[str]
    preferences: dict[str, Any]
    is_active: bool
    created_at: datetime


class UserTopicCreate(BaseModel):
    topic: str
    frequency: str = "daily"


class ArticleResponse(BaseModel):
    id: str
    title: str
    summary: Optional[str]
    url: str
    source: str
    topic: str
    published_date: Optional[datetime]
    relevance_score: int


class NewsletterGenerateRequest(BaseModel):
    topics: Optional[list[str]] = None
    send_email: bool = True
    user_id: Optional[str] = None


class NewsletterGenerateResponse(BaseModel):
    run_id: str
    subject: str
    article_count: int
    status: str
    preview: str


class DeepResearchRequest(BaseModel):
    query: str
    user_id: Optional[str] = None
    research_depth: str = "medium"
    allow_clarification: bool = True


class DeepResearchResponse(BaseModel):
    session_id: str
    status: str
    final_report: Optional[str]
    research_brief: Optional[str]
    notes_count: int


class ToolListResponse(BaseModel):
    tools: list[dict[str, Any]]
    count: int


class ToolExecuteRequest(BaseModel):
    tool_name: str
    params: dict[str, Any] = Field(default_factory=dict)


class ToolExecuteResponse(BaseModel):
    success: bool
    data: Optional[Any]
    error: Optional[str]
    metadata: dict[str, Any]


class StatsResponse(BaseModel):
    total_articles: int
    total_users: int
    total_newsletter_runs: int
    successful_deliveries: int
    active_sessions: int


class ArticleQuery(BaseModel):
    topics: Optional[list[str]] = None
    sources: Optional[list[str]] = None
    min_relevance: int = 0
    limit: int = 50


# Application lifespan management

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle - startup and shutdown."""
    # Startup
    logger.info("Starting tech-watch-agent API")
    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as exc:
        logger.warning("Database initialization skipped: %s", exc)

    # Initialize global tool registry with default tools
    _register_default_tools()

    yield

    # Shutdown
    logger.info("Shutting down tech-watch-agent API")
    try:
        await close_db()
    except Exception as exc:
        logger.warning("Database cleanup skipped: %s", exc)


def _register_default_tools():
    """Register default tools in the global registry."""
    registry = get_global_registry()

    # Only register if not already registered
    if "web_search" not in registry:
        from app.tools.web.search import NewsSearchService

        class RegisteredSearchTool(BaseTool):
            @property
            def name(self) -> str:
                return "web_search"

            @property
            def description(self) -> str:
                return "Search for news articles on the web"

            @property
            def category(self) -> ToolCategory:
                return ToolCategory.SEARCH

            @property
            def parameters(self) -> dict:
                return {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string", "description": "Topic to search for"}
                    },
                    "required": ["topic"]
                }

            async def execute(self, params: dict) -> dict:
                search = NewsSearchService()
                try:
                    urls = await search.search_news_urls(params.get("topic", ""))
                    return {
                        "success": True,
                        "data": urls,
                        "error": None,
                        "metadata": {"count": len(urls)}
                    }
                except Exception as exc:
                    return {
                        "success": False,
                        "data": None,
                        "error": str(exc),
                        "metadata": {}
                    }

        registry.register(RegisteredSearchTool())


# FastAPI Application Factory

def create_app(settings: Optional[Settings] = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    resolved_settings = settings or get_settings()

    app = FastAPI(
        title="tech-watch-agent API",
        version="0.2.0",
        description="Advanced multi-agent tech watch platform with deep research capabilities",
        lifespan=lifespan,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.settings = resolved_settings

    # Health and Status Endpoints

    @app.get("/health", response_model=HealthResponse, tags=["Health"])
    async def health_check() -> HealthResponse:
        """Comprehensive health check endpoint."""
        health = {
            "status": "ok",
            "database": "unknown",
            "memory": "unknown",
            "agents": {}
        }

        # Check database
        try:
            async with async_session_factory() as session:
                from sqlalchemy import text
                await session.execute(text("SELECT 1"))
            health["database"] = "healthy"
        except Exception as exc:
            health["database"] = f"error: {exc}"

        # Check memory
        try:
            manager = MemoryManager(session)
            memory_health = await manager.health_check()
            health["memory"] = "healthy" if memory_health.get("database") == "healthy" else "error"
        except Exception:
            health["memory"] = "not_initialized"

        # Check agents
        try:
            from app.agents.newsletter.agent import create_newsletter_agent
            agent = create_newsletter_agent(resolved_settings)
            health["agents"]["newsletter"] = True
        except Exception:
            health["agents"]["newsletter"] = False

        try:
            from app.agents.deep_research.agent import create_deep_research_agent
            agent = create_deep_research_agent(settings=resolved_settings)
            health["agents"]["deep_research"] = True
        except Exception:
            health["agents"]["deep_research"] = False

        return HealthResponse(**health)

    @app.get("/status", tags=["Health"])
    async def status() -> dict[str, Any]:
        """Get system status and statistics."""
        async with async_session_factory() as session:
            stats = await _get_stats(session)
        return stats

    # User Management Endpoints

    @app.post("/users", response_model=UserResponse, tags=["Users"])
    async def create_user(user: UserCreate) -> UserResponse:
        """Create a new user."""
        async with async_session_factory() as session:
            repo = UserRepository(session)

            # Check if email exists
            existing = await repo.get_by_email(user.email)
            if existing:
                raise HTTPException(status_code=400, detail="Email already registered")

            # Create user
            db_user = User(
                email=user.email,
                username=user.username,
                preferences=user.preferences,
            )
            created = await repo.create(db_user)
            await session.commit()

            return UserResponse(
                id=str(created.id),
                email=created.email,
                username=created.username,
                preferences=created.preferences,
                is_active=created.is_active,
                created_at=created.created_at,
            )

    @app.get("/users/{user_id}", response_model=UserResponse, tags=["Users"])
    async def get_user(user_id: str) -> UserResponse:
        """Get a user by ID."""
        async with async_session_factory() as session:
            repo = UserRepository(session)
            user = await repo.get_by_id(uuid.UUID(user_id))

            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            return UserResponse(
                id=str(user.id),
                email=user.email,
                username=user.username,
                preferences=user.preferences,
                is_active=user.is_active,
                created_at=user.created_at,
            )

    @app.get("/users/{user_id}/topics", tags=["Users"])
    async def get_user_topics(user_id: str) -> list[dict[str, Any]]:
        """Get topics for a user."""
        async with async_session_factory() as session:
            repo = UserTopicRepository(session)
            topics = await repo.get_active_by_user(uuid.UUID(user_id))
            return [
                {
                    "id": str(t.id),
                    "topic": t.topic,
                    "frequency": t.frequency,
                    "is_active": t.is_active,
                }
                for t in topics
            ]

    @app.post("/users/{user_id}/topics", tags=["Users"])
    async def add_user_topic(user_id: str, topic: UserTopicCreate) -> dict[str, Any]:
        """Add a topic for a user."""
        async with async_session_factory() as session:
            repo = UserTopicRepository(session)

            user_topic = UserTopic(
                user_id=uuid.UUID(user_id),
                topic=topic.topic,
                frequency=topic.frequency,
            )
            created = await repo.create(user_topic)
            await session.commit()

            return {
                "id": str(created.id),
                "topic": created.topic,
                "frequency": created.frequency,
            }

    # Article Endpoints

    @app.get("/articles", response_model=list[ArticleResponse], tags=["Articles"])
    async def list_articles(
        topics: Optional[str] = Query(None),
        sources: Optional[str] = Query(None),
        min_relevance: int = Query(0),
        limit: int = Query(50),
    ) -> list[ArticleResponse]:
        """List articles with optional filters."""
        topic_list = topics.split(",") if topics else None
        source_list = sources.split(",") if sources else None

        async with async_session_factory() as session:
            repo = ArticleRepository(session)

            if topic_list:
                articles = []
                for topic in topic_list:
                    topic_articles = await repo.get_by_topic(topic, limit)
                    articles.extend(topic_articles)
            else:
                articles = await repo.get_recent(limit=limit)

            return [
                ArticleResponse(
                    id=str(a.id),
                    title=a.title,
                    summary=a.summary,
                    url=a.url,
                    source=a.source,
                    topic=a.topic,
                    published_date=a.published_date,
                    relevance_score=a.relevance_score,
                )
                for a in articles[:limit]
            ]

    @app.get("/articles/{article_id}", response_model=ArticleResponse, tags=["Articles"])
    async def get_article(article_id: str) -> ArticleResponse:
        """Get a specific article."""
        async with async_session_factory() as session:
            repo = ArticleRepository(session)
            article = await repo.get_by_id(uuid.UUID(article_id))

            if not article:
                raise HTTPException(status_code=404, detail="Article not found")

            return ArticleResponse(
                id=str(article.id),
                title=article.title,
                summary=article.summary,
                url=article.url,
                source=article.source,
                topic=article.topic,
                published_date=article.published_date,
                relevance_score=article.relevance_score,
            )

    # Newsletter Endpoints

    @app.post("/newsletter/generate", response_model=NewsletterGenerateResponse, tags=["Newsletter"])
    async def generate_newsletter(
        payload: NewsletterGenerateRequest,
        background_tasks: BackgroundTasks,
    ) -> NewsletterGenerateResponse:
        """Generate a newsletter (async or sync)."""
        try:
            agent = create_newsletter_agent(resolved_settings)

            # Run synchronously for now (background_tasks not fully implemented)
            result = await agent.execute({
                "topics": payload.topics,
                "send_email": payload.send_email,
            })

            if not result.success:
                raise HTTPException(status_code=500, detail=result.errors[0] if result.errors else "Generation failed")

            output = result.output
            newsletter = output.get("newsletter", "")

            # Get first line as subject
            subject = newsletter.split("\n")[0] if newsletter else "Tech Watch Newsletter"
            subject = subject.replace("#", "").strip()

            return NewsletterGenerateResponse(
                run_id=str(result.session_id) if result.session_id else str(uuid.uuid4()),
                subject=subject,
                article_count=output.get("article_count", 0),
                status="completed",
                preview=newsletter[:500],
            )

        except Exception as exc:
            logger.error("Newsletter generation failed: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc))

    @app.post("/newsletter/generate/sync", response_model=NewsletterGenerateResponse, tags=["Newsletter"])
    async def generate_newsletter_sync(payload: NewsletterGenerateRequest) -> NewsletterGenerateResponse:
        """Generate a newsletter synchronously."""
        return await generate_newsletter(payload, BackgroundTasks())

    @app.get("/newsletter/history", tags=["Newsletter"])
    async def newsletter_history(
        user_id: Optional[str] = None,
        limit: int = Query(10),
    ) -> list[dict[str, Any]]:
        """Get newsletter generation history."""
        async with async_session_factory() as session:
            repo = NewsletterRunRepository(session)

            user_uuid = uuid.UUID(user_id) if user_id else None
            runs = await repo.get_recent(user_uuid, limit)

            return [
                {
                    "id": str(run.id),
                    "subject": run.subject,
                    "status": run.status,
                    "articles_count": run.articles_count,
                    "delivery_success": run.delivery_success,
                    "started_at": run.started_at.isoformat() if run.started_at else None,
                    "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                }
                for run in runs
            ]

    @app.get("/newsletter/stats", tags=["Newsletter"])
    async def newsletter_stats(user_id: Optional[str] = None) -> dict[str, Any]:
        """Get newsletter statistics."""
        async with async_session_factory() as session:
            repo = NewsletterRunRepository(session)
            user_uuid = uuid.UUID(user_id) if user_id else None
            stats = await repo.get_stats(user_uuid)
            return stats

    # Deep Research Endpoints

    @app.post("/research", response_model=DeepResearchResponse, tags=["Deep Research"])
    async def start_research(payload: DeepResearchRequest) -> DeepResearchResponse:
        """Start a deep research session."""
        try:
            config = DeepResearchConfig(
                research_depth=payload.research_depth,
                allow_clarification=payload.allow_clarification,
            )
            agent = create_deep_research_agent(config=config, settings=resolved_settings)

            result = await agent.execute({
                "query": payload.query,
            })

            if not result.success:
                raise HTTPException(status_code=500, detail=result.errors[0] if result.errors else "Research failed")

            output = result.output

            return DeepResearchResponse(
                session_id=str(result.session_id) if result.session_id else str(uuid.uuid4()),
                status="completed",
                final_report=output.get("report"),
                research_brief=output.get("research_brief"),
                notes_count=len(output.get("notes", [])),
            )

        except Exception as exc:
            logger.error("Deep research failed: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/research/history", tags=["Deep Research"])
    async def research_history(
        user_id: Optional[str] = None,
        limit: int = Query(10),
    ) -> list[dict[str, Any]]:
        """Get research session history."""
        async with async_session_factory() as session:
            repo = ResearchSessionRepository(session)

            user_uuid = uuid.UUID(user_id) if user_id else None
            sessions = await repo.get_recent(user_uuid, limit)

            return [
                {
                    "id": str(s.id),
                    "research_brief": s.research_brief[:200],
                    "status": s.status,
                    "final_report_length": len(s.final_report) if s.final_report else 0,
                    "iterations_count": s.iterations_count,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                }
                for s in sessions
            ]

    # Tool Registry Endpoints

    @app.get("/tools", response_model=ToolListResponse, tags=["Tools"])
    async def list_tools() -> ToolListResponse:
        """List all registered tools."""
        registry = get_global_registry()
        tools = registry.list_tools_metadata()

        return ToolListResponse(
            tools=[t.to_dict() for t in tools],
            count=len(tools),
        )

    @app.get("/tools/{tool_name}", tags=["Tools"])
    async def get_tool(tool_name: str) -> dict[str, Any]:
        """Get details about a specific tool."""
        registry = get_global_registry()
        tool = registry.get(tool_name)

        if not tool:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

        return tool.metadata.to_dict()

    @app.post("/tools/execute", response_model=ToolExecuteResponse, tags=["Tools"])
    async def execute_tool(payload: ToolExecuteRequest) -> ToolExecuteResponse:
        """Execute a tool with given parameters."""
        registry = get_global_registry()
        tool = registry.get(payload.tool_name)

        if not tool:
            raise HTTPException(status_code=404, detail=f"Tool '{payload.tool_name}' not found")

        try:
            result = await tool.execute_safe(payload.params)
            return ToolExecuteResponse(
                success=result.get("success", False),
                data=result.get("data"),
                error=result.get("error"),
                metadata=result.get("metadata", {}),
            )
        except Exception as exc:
            return ToolExecuteResponse(
                success=False,
                data=None,
                error=str(exc),
                metadata={},
            )

    # Stats Endpoint

    @app.get("/stats", response_model=StatsResponse, tags=["Stats"])
    async def get_stats() -> StatsResponse:
        """Get system statistics."""
        async with async_session_factory() as session:
            stats = await _get_stats(session)
            return StatsResponse(**stats)

    return app


async def _get_stats(session) -> dict[str, Any]:
    """Get system statistics from database."""
    from sqlalchemy import select, func, and_

    # Get article count
    article_count = await session.scalar(select(func.count()).select_from(Article))

    # Get user count
    user_count = await session.scalar(select(func.count()).select_from(User))

    # Get newsletter run stats
    run_stats = await session.scalar(
        select(
            func.count(NewsletterRun.id).label("total"),
            func.sum(
                func.case((NewsletterRun.delivery_success == True, 1), else_=0)
            ).label("successful"),
        )
    )

    return {
        "total_articles": article_count or 0,
        "total_users": user_count or 0,
        "total_newsletter_runs": run_stats.total if run_stats else 0,
        "successful_deliveries": run_stats.successful if run_stats and run_stats.successful else 0,
        "active_sessions": 0,  # Would need session table count
    }


# Create the default app instance
app = create_app()
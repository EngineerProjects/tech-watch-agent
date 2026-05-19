"""
FastAPI main application with comprehensive API endpoints.

This module defines the FastAPI application with routes imported from `app/api/routers`.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.config.settings import Settings, get_settings
from app.db.base import init_db, close_db
from app.tools.registry import get_global_registry
from app.tools.base import BaseTool, ToolCategory
from app.core.logging import get_logger

# Import routers
from app.api.routers import (
    health_router,
    users_router,
    articles_router,
    newsletter_router,
    orchestrator_router,
    research_router,
    sessions_router,
    tools_router,
    llm_router,
)
from app.dashboard import dashboard_router


logger = get_logger(__name__)


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
    from app.config.settings import get_settings
    _register_default_tools(get_settings())

    yield

    # Shutdown
    logger.info("Shutting down tech-watch-agent API")
    try:
        await close_db()
    except Exception as exc:
        logger.warning("Database cleanup skipped: %s", exc)


def _register_default_tools(settings: Optional[Settings] = None) -> None:
    """Register default tools in the global registry."""
    registry = get_global_registry()
    resolved_settings = settings or get_settings()

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

    # Register Tavily search tool if API key is configured
    if "tavily_search" not in registry:
        from app.tools.web.tavily import TavilySearchTool

        try:
            tavily_tool = TavilySearchTool()
            if tavily_tool._api_key:
                registry.register(tavily_tool)
                logger.info("Registered Tavily search tool")
            else:
                logger.info("Tavily API key not set, skipping Tavily tool registration")
        except Exception:
            pass

    # Register Scrapling tool (adaptive web scraping with anti-bot bypass)
    if "scrapling" not in registry:
        from app.tools.web.scrapling import ScraplingToolFactory

        try:
            scrapling_tool = ScraplingToolFactory.from_settings(resolved_settings)
            registry.register(scrapling_tool)
            logger.info("Registered Scrapling tool (fetcher: %s)", resolved_settings.scrapling_fetcher)
        except Exception as exc:
            logger.warning("Failed to register Scrapling tool: %s", exc)

    # Register Crawl4AI tool (LLM-optimized markdown output)
    if "crawl4ai" not in registry:
        from app.tools.web.crawl4ai import Crawl4AIToolFactory

        try:
            crawl4ai_tool = Crawl4AIToolFactory.from_settings(resolved_settings)
            registry.register(crawl4ai_tool)
            logger.info("Registered Crawl4AI tool (filter: %s)", resolved_settings.crawl4ai_filter)
        except Exception as exc:
            logger.warning("Failed to register Crawl4AI tool: %s", exc)

    # Register Content Extractor (unified tool with smart fallback)
    if "content_extractor" not in registry:
        from app.tools.web.extractor import ContentExtractorFactory

        try:
            extractor_tool = ContentExtractorFactory.from_settings(resolved_settings)
            registry.register(extractor_tool)
            logger.info("Registered Content Extractor (strategy: %s)", resolved_settings.content_extractor_strategy)
        except Exception as exc:
            logger.warning("Failed to register Content Extractor: %s", exc)


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    resolved_settings = settings or get_settings()

    app = FastAPI(
        title="tech-watch-agent API",
        version="0.3.0",
        description="Advanced multi-agent tech watch platform with orchestrator, deep research, and newsletter capabilities",
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

    # Include routers
    app.include_router(health_router)
    app.include_router(users_router)
    app.include_router(articles_router)
    app.include_router(newsletter_router)
    app.include_router(orchestrator_router)
    app.include_router(research_router)
    app.include_router(sessions_router)
    app.include_router(tools_router)
    app.include_router(llm_router)
    app.include_router(dashboard_router)

    @app.get("/", include_in_schema=False)
    async def root_redirect():
        return RedirectResponse(url="/ui")

    return app


# Create the default app instance
app = create_app()
"""
FastAPI main application with comprehensive API endpoints.

This module defines the FastAPI application with routes imported from `app/api/routers`.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.config.settings import Settings, get_settings
from app.db.base import close_db
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
    watch_profiles_router,
    config_router,
    sources_router,
    email_groups_router,
)
from app.dashboard import dashboard_router


logger = get_logger(__name__)

# Track profiles currently executing so we don't double-trigger
_running_profile_ids: set[str] = set()


async def _execute_scheduled_profile(profile_id: str, profile_name: str) -> None:
    """Run a single WatchProfile as a background task."""
    _running_profile_ids.add(profile_id)
    try:
        import uuid as _uuid
        from app.core.watch_context import WatchContext
        from app.db.base import async_session_factory
        from app.db.repositories import EmailGroupRepository, WatchProfileRepository
        from app.scheduler.service import OrchestratorScheduler

        async with async_session_factory() as db:
            repo = WatchProfileRepository(db)
            group_repo = EmailGroupRepository(db)
            profile = await repo.get_by_id(_uuid.UUID(profile_id))
            if not profile:
                return

            recipients = await group_repo.resolve_recipients_for_profile(profile)
            ctx = WatchContext.from_profile(profile)
            task = f"Tech watch: {', '.join(ctx.topics)}" if ctx.topics else "Weekly tech watch"

            scheduler = OrchestratorScheduler(mode="v2", settings=get_settings())
            await scheduler.run_task(
                task=task,
                topics=ctx.topics or None,
                send_email=bool(recipients),
                autonomous=True,
                watch_context=ctx,
                recipients_override=recipients or None,
            )

            await repo.touch_last_run(_uuid.UUID(profile_id))
            await db.commit()

        logger.info("Scheduled profile '%s' completed", profile_name)
    except Exception as exc:
        logger.error("Scheduled profile '%s' failed: %s", profile_name, exc)
    finally:
        _running_profile_ids.discard(profile_id)


async def _profile_scheduler_loop() -> None:
    """Background loop: every 60 s, trigger any WatchProfile due to run."""
    logger.info("In-process profile scheduler started")
    while True:
        await asyncio.sleep(60)
        tz_name = get_settings().timezone
        try:
            tz = ZoneInfo(tz_name)
        except ZoneInfoNotFoundError:
            logger.warning("Unknown timezone '%s', falling back to UTC", tz_name)
            tz = ZoneInfo("UTC")
        now = datetime.now(tz)
        current_hhmm = now.strftime("%H:%M")
        current_day = now.strftime("%A").lower()

        try:
            from app.db.base import async_session_factory
            from app.db.repositories import WatchProfileRepository

            async with async_session_factory() as db:
                repo = WatchProfileRepository(db)
                profiles = await repo.list_all(active_only=True)

            for p in profiles:
                if not p.schedule_time or p.schedule_time != current_hhmm:
                    continue

                stype = (p.schedule_type or "weekly").lower()

                if stype == "weekly":
                    if p.schedule_days and current_day not in [d.lower() for d in p.schedule_days]:
                        continue

                elif stype == "once":
                    if not p.schedule_date:
                        continue
                    if p.schedule_date != now.strftime("%Y-%m-%d"):
                        continue
                    # After running once, deactivate so it doesn't re-fire
                    if p.last_run_at and p.last_run_at.date() == now.date():
                        continue

                elif stype in ("monthly", "custom"):
                    if not p.schedule_date:
                        continue
                    from datetime import date as _date
                    try:
                        start = _date.fromisoformat(p.schedule_date)
                    except ValueError:
                        continue
                    interval = max(1, p.schedule_interval_months or 1)
                    today = now.date()
                    if today.day != start.day:
                        continue
                    # Check we're on an N-month boundary from the start date
                    months_diff = (today.year - start.year) * 12 + (today.month - start.month)
                    if months_diff < 0 or months_diff % interval != 0:
                        continue

                else:
                    # Unknown type — fall back to weekly logic
                    if p.schedule_days and current_day not in [d.lower() for d in p.schedule_days]:
                        continue

                pid = str(p.id)
                if pid in _running_profile_ids:
                    logger.info("Profile '%s' already running, skipping", p.name)
                    continue

                logger.info("Scheduler: triggering profile '%s' (type=%s)", p.name, stype)
                asyncio.create_task(_execute_scheduled_profile(pid, p.name))

                # Deactivate one-time profiles after firing
                if stype == "once":
                    try:
                        from app.db.base import async_session_factory as _asf
                        from app.db.repositories import WatchProfileRepository as _WPR
                        import uuid as _uuid2
                        async with _asf() as _db:
                            _repo = _WPR(_db)
                            _p = await _repo.get_by_id(_uuid2.UUID(pid))
                            if _p:
                                _p.is_active = False
                                await _repo.update(_p)
                                await _db.commit()
                    except Exception as _exc:
                        logger.warning("Could not deactivate once-profile '%s': %s", p.name, _exc)

        except Exception as exc:
            logger.error("Scheduler loop error: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle - startup and shutdown."""
    # Startup
    logger.info("Starting tech-watch-agent API")
    logger.info("Database schema initialization is managed by Alembic migrations")

    # Load DB config overrides so UI-saved settings take effect at runtime
    try:
        from app.db.base import async_session_factory
        from app.db.repositories import AppConfigRepository
        from app.config.settings import set_db_overrides
        from app.core.crypto import decrypt_overrides
        async with async_session_factory() as db:
            raw_overrides = await AppConfigRepository(db).get_all()
        if raw_overrides:
            overrides = decrypt_overrides(raw_overrides)
            set_db_overrides(overrides)
            logger.info("Applied %d DB config overrides to settings", len(overrides))
    except Exception as exc:
        logger.warning("Could not load DB config overrides: %s", exc)

    # Initialize global tool registry with default tools
    from app.config.settings import get_settings
    _register_default_tools(get_settings())

    # Register remaining tools (github, reddit, arxiv, youtube, memory, email, etc.)
    from app.tools.registry_init import initialize_tools
    initialize_tools()

    # Register agent-based tools (deep_research, newsletter)
    from app.agents import initialize_agents
    initialize_agents()

    # Clean up sessions stuck in "running" from previous crashes/deploys
    try:
        from app.services.streaming_service import cleanup_stale_running_sessions
        cleaned = await cleanup_stale_running_sessions(max_age_hours=1)
        if cleaned:
            logger.info("Startup: marked %d orphaned sessions as failed", cleaned)
    except Exception as _exc:
        logger.warning("Stale session cleanup skipped: %s", _exc)

    # Start persistent APScheduler (falls back silently if apscheduler not installed)
    from app.scheduler.persistent import get_profile_scheduler
    profile_scheduler = get_profile_scheduler()
    try:
        await profile_scheduler.start()
    except Exception as _sched_exc:
        logger.warning("APScheduler init failed, falling back to polling loop: %s", _sched_exc)
        profile_scheduler = None

    # Fallback polling loop if APScheduler unavailable
    scheduler_task = None
    if not (profile_scheduler and profile_scheduler.is_ready):
        scheduler_task = asyncio.create_task(_profile_scheduler_loop())

    yield

    # Shutdown
    logger.info("Shutting down tech-watch-agent API")
    if profile_scheduler and profile_scheduler.is_ready:
        await profile_scheduler.stop()
    if scheduler_task:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass
    try:
        await close_db()
    except Exception as exc:
        logger.warning("Database cleanup skipped: %s", exc)


def _register_default_tools(settings: Optional[Settings] = None) -> None:
    """Register default tools in the global registry."""
    registry = get_global_registry()
    resolved_settings = settings or get_settings()

    # API-backed search providers kept separate from SearXNG/free search.
    if "web_search" not in registry:
        try:
            from app.tools.web.multi_search import MultiProviderSearchTool
            registry.register(MultiProviderSearchTool(settings=resolved_settings))
            logger.info("Registered MultiProviderSearch tool as 'web_search'")
        except Exception as exc:
            logger.warning("Failed to register MultiProviderSearch tool: %s", exc)

    # Free/self-hosted search entrypoint.
    if "free_search" not in registry:
        try:
            from app.tools.web.free_search import FreeSearchTool
            registry.register(FreeSearchTool(settings=resolved_settings))
            logger.info("Registered FreeSearch tool")
        except Exception as exc:
            logger.warning("Failed to register FreeSearch tool: %s", exc)

    # Specialized research search for academic/code discovery.
    if "research_search" not in registry:
        try:
            from app.tools.web.research_search import ResearchSearchTool
            registry.register(ResearchSearchTool(settings=resolved_settings))
            logger.info("Registered ResearchSearch tool")
        except Exception as exc:
            logger.warning("Failed to register ResearchSearch tool: %s", exc)

    # Register SearXNG (self-hosted metasearch — primary free search provider)
    if "searxng" not in registry:
        from app.tools.web.searxng import SearXNGSearchToolFactory

        try:
            searxng_tool = SearXNGSearchToolFactory.from_settings(resolved_settings)
            registry.register(searxng_tool)
            logger.info("Registered SearXNG tool (url: %s)", resolved_settings.searxng_url)
        except Exception as exc:
            logger.warning("Failed to register SearXNG tool: %s", exc)

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
        except Exception as exc:
            logger.warning("Failed to register Tavily tool: %s", exc)

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

    # Register Exa search (neural search, requires EXA_API_KEY)
    if "exa_search" not in registry:
        from app.tools.web.exa import ExaSearchToolFactory

        try:
            exa_tool = ExaSearchToolFactory.from_settings(resolved_settings)
            if exa_tool._api_key:
                registry.register(exa_tool)
                logger.info("Registered Exa search tool")
            else:
                logger.debug("EXA_API_KEY not set, skipping Exa tool")
        except Exception as exc:
            logger.warning("Failed to register Exa tool: %s", exc)

    # Register LangSearch (free tier, no credit card)
    if "langsearch" not in registry:
        from app.tools.web.langsearch import LangSearchToolFactory

        try:
            ls_tool = LangSearchToolFactory.from_settings(resolved_settings)
            if ls_tool._api_key:
                registry.register(ls_tool)
                logger.info("Registered LangSearch tool")
            else:
                logger.debug("LANGSEARCH_API_KEY not set, skipping LangSearch tool")
        except Exception as exc:
            logger.warning("Failed to register LangSearch tool: %s", exc)

    # Register Jina Reader (URL→markdown, no key required for basic use)
    if "jina_reader" not in registry:
        from app.tools.web.jina import JinaReaderToolFactory

        try:
            jina_tool = JinaReaderToolFactory.from_settings(resolved_settings)
            registry.register(jina_tool)
            logger.info("Registered Jina Reader tool")
        except Exception as exc:
            logger.warning("Failed to register Jina Reader tool: %s", exc)

    # Register Semantic Scholar (academic search, free)
    if "semantic_scholar" not in registry:
        from app.tools.web.semantic_scholar import SemanticScholarTool

        try:
            registry.register(SemanticScholarTool())
            logger.info("Registered Semantic Scholar tool")
        except Exception as exc:
            logger.warning("Failed to register Semantic Scholar tool: %s", exc)

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
    # allow_origins=["*"] is incompatible with allow_credentials=True per the CORS spec.
    # Explicit origins are required for credentialed requests.
    cors_origins = list(resolved_settings.cors_origins)
    if resolved_settings.frontend_url and resolved_settings.frontend_url not in cors_origins:
        cors_origins.append(resolved_settings.frontend_url)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
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
    app.include_router(watch_profiles_router)
    app.include_router(config_router)
    app.include_router(sources_router)
    app.include_router(email_groups_router)
    app.include_router(dashboard_router)

    @app.get("/", include_in_schema=False)
    async def root_redirect():
        return RedirectResponse(url=resolved_settings.frontend_url)

    return app


# Create the default app instance
app = create_app()
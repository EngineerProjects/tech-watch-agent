"""
API Routers module.
"""

from app.api.routers.health import router as health_router
from app.api.routers.users import router as users_router
from app.api.routers.articles import router as articles_router
from app.api.routers.newsletter import router as newsletter_router
from app.api.routers.orchestrator import router as orchestrator_router
from app.api.routers.research import router as research_router
from app.api.routers.sessions import router as sessions_router
from app.api.routers.tools import router as tools_router
from app.api.routers.llm import router as llm_router
from app.api.routers.watch_profiles import router as watch_profiles_router
from app.api.routers.config import router as config_router
from app.api.routers.sources import router as sources_router

__all__ = [
    "health_router",
    "users_router",
    "articles_router",
    "newsletter_router",
    "orchestrator_router",
    "research_router",
    "sessions_router",
    "tools_router",
    "llm_router",
    "watch_profiles_router",
    "config_router",
    "sources_router",
]

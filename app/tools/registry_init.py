"""
Tool initialization module.

This module handles the registration of all available tools
at application startup.
"""

from app.tools.registry import get_global_registry, register_tool
from app.core.logging import get_logger


logger = get_logger(__name__)


def initialize_tools() -> None:
    """Initialize and register all available tools.
    
    This function should be called at application startup
    to make all tools available in the registry.
    """
    registry = get_global_registry()
    tools_registered = 0
    
    # Web Search Tools
    # SearXNG — pure single-provider tool (used directly by the planner when it says tool_name="searxng")
    try:
        from app.tools.web.searxng import SearXNGSearchTool
        searxng_tool = SearXNGSearchTool()
        register_tool(searxng_tool)
        tools_registered += 1
        logger.info("Registered SearXNG search tool")
    except (ImportError, ValueError) as e:
        logger.warning(f"SearXNG not available: {e}")

    # Tavily — registered under its own name for direct calls and multi-provider
    try:
        from app.tools.web.tavily import TavilySearchTool
        tool = TavilySearchTool()
        if tool._api_key:
            register_tool(tool)
            tools_registered += 1
            logger.info("Registered Tavily search tool")
        else:
            logger.debug("Tavily not configured (no TAVILY_API_KEY)")
    except (ImportError, ValueError) as e:
        logger.debug(f"Tavily not available: {e}")

    # web_search — API-backed providers only (Tavily / Exa / LangSearch)
    try:
        from app.tools.web.multi_search import MultiProviderSearchTool
        register_tool(MultiProviderSearchTool())
        tools_registered += 1
        logger.info("Registered MultiProviderSearch tool as 'web_search'")
    except (ImportError, ValueError) as e:
        logger.warning(f"MultiProviderSearch not available: {e}")

    # free_search — SearXNG-first, quota-light discovery path
    try:
        from app.tools.web.free_search import FreeSearchTool
        register_tool(FreeSearchTool())
        tools_registered += 1
        logger.info("Registered FreeSearch tool")
    except (ImportError, ValueError) as e:
        logger.warning(f"FreeSearch not available: {e}")

    # research_search — academic/code focused search, SearXNG first then fan-out
    try:
        from app.tools.web.research_search import ResearchSearchTool
        register_tool(ResearchSearchTool())
        tools_registered += 1
        logger.info("Registered ResearchSearch tool")
    except (ImportError, ValueError) as e:
        logger.warning(f"ResearchSearch not available: {e}")
    
    try:
        from app.tools.web.semantic_scholar import SemanticScholarTool
        register_tool(SemanticScholarTool())
        tools_registered += 1
        logger.info("Registered Semantic Scholar tool")
    except (ImportError, ValueError) as e:
        logger.debug(f"Semantic Scholar not available: {e}")

    try:
        from app.tools.web.openalex import OpenAlexTool
        register_tool(OpenAlexTool())
        tools_registered += 1
        logger.info("Registered OpenAlex tool")
    except (ImportError, ValueError) as e:
        logger.debug(f"OpenAlex not available: {e}")
    
    try:
        from app.tools.web.scholar import GoogleScholarTool
        register_tool(GoogleScholarTool())
        tools_registered += 1
        logger.info("Registered Google Scholar tool")
    except (ImportError, ValueError) as e:
        logger.debug(f"Google Scholar not available: {e}")
    
    try:
        from app.tools.web.think import ThinkTool
        register_tool(ThinkTool())
        tools_registered += 1
        logger.info("Registered Think tool")
    except (ImportError, ValueError) as e:
        logger.debug(f"Think tool not available: {e}")
    
    try:
        from app.tools.web.extractor import ContentExtractorTool
        register_tool(ContentExtractorTool())
        tools_registered += 1
        logger.info("Registered Content Extractor tool")
    except (ImportError, ValueError) as e:
        logger.debug(f"Content Extractor not available: {e}")
    
    # Social/Monitoring Tools
    try:
        from app.tools.social.github import GitHubTool
        register_tool(GitHubTool())
        tools_registered += 1
        logger.info("Registered GitHub tool")
    except (ImportError, ValueError) as e:
        logger.warning(f"Could not import GitHubTool: {e}")
    
    try:
        from app.tools.social.reddit import RedditTool
        register_tool(RedditTool())
        tools_registered += 1
        logger.info("Registered Reddit tool")
    except (ImportError, ValueError) as e:
        logger.warning(f"Could not import RedditTool: {e}")
    
    try:
        from app.tools.social.arxiv import ArXivTool
        register_tool(ArXivTool())
        tools_registered += 1
        logger.info("Registered ArXiv tool")
    except (ImportError, ValueError) as e:
        logger.warning(f"Could not import ArXivTool: {e}")
    
    try:
        from app.tools.social.research_paper import ResearchPaperTool
        register_tool(ResearchPaperTool())
        tools_registered += 1
        logger.info("Registered Research Paper tool")
    except (ImportError, ValueError) as e:
        logger.warning(f"Could not import ResearchPaperTool: {e}")
    
    try:
        from app.tools.social.youtube import YouTubeTool
        register_tool(YouTubeTool())
        tools_registered += 1
        logger.info("Registered YouTube tool")
    except (ImportError, ValueError) as e:
        logger.warning(f"Could not import YouTubeTool: {e}")

    # Memory/RAG Tools
    try:
        from app.tools.memory.search_memory import SearchMemoryTool
        register_tool(SearchMemoryTool())
        tools_registered += 1
        logger.info("Registered SearchMemory tool")
    except (ImportError, ValueError) as e:
        logger.warning(f"Could not import SearchMemoryTool: {e}")

    try:
        from app.tools.memory.search_memory import GetRecentContextTool
        register_tool(GetRecentContextTool())
        tools_registered += 1
        logger.info("Registered GetRecentContext tool")
    except (ImportError, ValueError) as e:
        logger.warning(f"Could not import GetRecentContextTool: {e}")

    try:
        from app.tools.memory.search_memory import StoreResearchContextTool
        register_tool(StoreResearchContextTool())
        tools_registered += 1
        logger.info("Registered StoreResearchContext tool")
    except (ImportError, ValueError) as e:
        logger.warning(f"Could not import StoreResearchContextTool: {e}")

    # Delivery Tools
    try:
        from app.tools.delivery.email_tool import EmailTool, EmailPreviewTool

        email_tool = EmailTool()
        register_tool(email_tool)
        tools_registered += 1
        logger.info("Registered Email tool")

        email_preview_tool = EmailPreviewTool()
        register_tool(email_preview_tool)
        tools_registered += 1
        logger.info("Registered Email Preview tool")
    except (ImportError, ValueError) as e:
        logger.warning(f"Could not import Email tools: {e}")

    logger.info(f"Tool initialization complete: {tools_registered} tools registered")


def get_tools_summary() -> dict:
    """Get a summary of registered tools."""
    registry = get_global_registry()
    return {
        "total_tools": registry.count,
        "tools": registry.list_tools(),
        "categories": list(set(t.category.value for t in registry)),
    }
"""
Agent workflows and registry.

This module provides:
- AgentRegistry: Centralized agent management
- AgentAsTool: Wrapper to use agents as tools
- Initialization for agent registration
"""

from app.agents.registry import (
    AgentRegistry,
    AgentMetadata,
    AgentAsTool,
    get_agent_registry,
    register_agent,
    get_agent,
    wrap_agent_as_tool,
)

__all__ = [
    "AgentRegistry",
    "AgentMetadata",
    "AgentAsTool",
    "get_agent_registry",
    "register_agent",
    "get_agent",
    "wrap_agent_as_tool",
]


def initialize_agents() -> None:
    """Initialize and register all available agents.

    This should be called at application startup to make
    agents available for orchestration.
    """
    from app.agents.deep_research.agent import create_deep_research_agent
    from app.agents.newsletter.agent import create_newsletter_agent

    # Register deep_research agent
    deep_research = create_deep_research_agent()
    register_agent(
        name="deep_research",
        agent=deep_research,
        metadata=AgentMetadata(
            name="deep_research",
            description="Multi-agent supervisor-researcher pattern for in-depth investigations",
            category="research",
            supports_async=True,
            supports_parallel=True,
            max_execution_time_seconds=600,
        ),
    )

    # Register newsletter agent (legacy V1)
    newsletter = create_newsletter_agent()
    register_agent(
        name="newsletter",
        agent=newsletter,
        metadata=AgentMetadata(
            name="newsletter",
            description="Newsletter generation agent for periodic tech summaries",
            category="synthesis",
            supports_async=True,
            supports_parallel=False,
            max_execution_time_seconds=300,
        ),
    )

"""
Agent registry for managing agent instances.

This module provides centralized agent lifecycle management,
allowing agents to be registered, retrieved, and used as tools
by other agents.
"""

from typing import Any, Optional
from dataclasses import dataclass, field

from app.agents.base.base_agent import BaseAgent, AgentResult
from app.core.logging import get_logger


logger = get_logger(__name__)


@dataclass
class AgentMetadata:
    """Metadata for a registered agent."""

    name: str
    description: str
    category: str = "general"
    version: str = "1.0.0"
    supports_async: bool = True
    supports_parallel: bool = True
    requires_auth: bool = False
    max_execution_time_seconds: int = 300


class AgentRegistry:
    """Central registry for agent instances.

    Provides:
    - Registration/lookup of agents
    - Factory methods for agent creation
    - Agent-as-tool wrapping for integration with tool registries
    - Lifecycle management

    Usage:
        registry = AgentRegistry()
        registry.register("deep_research", deep_research_agent)

        # Get agent
        agent = registry.get("deep_research")

        # Wrap as tool for use in orchestrator
        tool = registry.wrap_as_tool("deep_research")
    """

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}
        self._metadata: dict[str, AgentMetadata] = {}

    def register(
        self,
        name: str,
        agent: BaseAgent,
        metadata: Optional[AgentMetadata] = None,
    ) -> None:
        """Register an agent.

        Args:
            name: Unique identifier for the agent
            agent: Agent instance
            metadata: Optional metadata for the agent
        """
        if name in self._agents:
            logger.warning("Overwriting existing agent: %s", name)

        self._agents[name] = agent

        if metadata is None:
            metadata = AgentMetadata(
                name=name,
                description=agent.description or f"Agent: {name}",
            )
        self._metadata[name] = metadata

        logger.info("Registered agent: %s", name)

    def unregister(self, name: str) -> bool:
        """Unregister an agent.

        Args:
            name: Agent name to unregister

        Returns:
            True if unregistered, False if not found
        """
        if name not in self._agents:
            return False

        del self._agents[name]
        self._metadata.pop(name, None)
        logger.info("Unregistered agent: %s", name)
        return True

    def get(self, name: str) -> Optional[BaseAgent]:
        """Get an agent by name.

        Args:
            name: Agent name

        Returns:
            Agent instance or None if not found
        """
        return self._agents.get(name)

    def get_metadata(self, name: str) -> Optional[AgentMetadata]:
        """Get agent metadata.

        Args:
            name: Agent name

        Returns:
            AgentMetadata or None
        """
        return self._metadata.get(name)

    def list_agents(self) -> list[str]:
        """List all registered agent names."""
        return list(self._agents.keys())

    def list_metadata(self) -> list[AgentMetadata]:
        """List all agent metadata."""
        return list(self._metadata.values())

    def wrap_as_tool(self, name: str) -> Optional["AgentAsTool"]:
        """Wrap an agent as a tool for use in orchestrators.

        This allows agents to be called like regular tools
        in dispatcher nodes.

        Args:
            name: Agent name to wrap

        Returns:
            AgentAsTool instance or None if agent not found
        """
        agent = self.get(name)
        if agent is None:
            logger.error("Cannot wrap agent '%s': not found in registry", name)
            return None

        return AgentAsTool(agent=agent, agent_name=name)

    def is_registered(self, name: str) -> bool:
        """Check if an agent is registered."""
        return name in self._agents


class AgentAsTool:
    """Wrapper to use an agent as a tool.

    This enables agents to be dispatched by orchestrator nodes
    using the same interface as regular tools.

    The tool interface requires:
    - name property
    - description property
    - category property (optional)
    - execute(params) method returning ToolResult

    Usage in orchestrator nodes:
        # Instead of directly importing deep_research agent:
        agent_tool = registry.wrap_as_tool("deep_research")
        result = await agent_tool.execute({"query": "topic"})

    Attributes:
        agent: The wrapped agent instance
        agent_name: Name of the agent in registry
    """

    def __init__(self, agent: BaseAgent, agent_name: str) -> None:
        self._agent = agent
        self._agent_name = agent_name
        self._enabled = True

    @property
    def name(self) -> str:
        return f"agent:{self._agent_name}"

    @property
    def description(self) -> str:
        return f"Agent: {self._agent.description or self._agent_name}"

    @property
    def category(self) -> str:
        return "agent"

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "category": "agent",
            "agent_name": self._agent_name,
            "type": "agent_as_tool",
        }

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """Execute the wrapped agent.

        Args:
            params: Parameters to pass to the agent.
                - query: The main query (passed as string)
                - messages: Optional conversation messages
                - metadata: Optional metadata dict

        Returns:
            ToolResult dict with success/data/error/metadata
        """
        if not self._enabled:
            return {
                "success": False,
                "data": None,
                "error": f"Agent '{self._agent_name}' is disabled",
                "metadata": {},
            }

        try:
            # Extract agent input from params
            input_data = self._prepare_input(params)

            # Execute the agent
            result = await self._agent.run(input_data)

            # Convert AgentResult to ToolResult format
            if result.success:
                return {
                    "success": True,
                    "data": result.output,
                    "error": None,
                    "metadata": {
                        "agent": self._agent_name,
                        "execution_time": result.execution_time,
                        "session_id": str(result.session_id) if result.session_id else None,
                        **result.metadata,
                    },
                }
            else:
                return {
                    "success": False,
                    "data": None,
                    "error": "; ".join(result.errors) if result.errors else "Agent execution failed",
                    "metadata": {
                        "agent": self._agent_name,
                        "execution_time": result.execution_time,
                        **result.metadata,
                    },
                }

        except Exception as exc:
            logger.error("AgentAsTool '%s' execution failed: %s", self._agent_name, exc)
            return {
                "success": False,
                "data": None,
                "error": f"Agent execution error: {str(exc)}",
                "metadata": {"agent": self._agent_name},
            }

    async def execute_safe(self, params: dict[str, Any]) -> dict[str, Any]:
        """Execute with validation and error handling."""
        if not self._enabled:
            return {
                "success": False,
                "data": None,
                "error": f"Agent '{self._agent_name}' is disabled",
                "metadata": {},
            }
        return await self.execute(params)

    def _prepare_input(self, params: dict[str, Any]) -> Any:
        """Prepare agent input from tool params.

        Handles different param formats to create appropriate
        agent input (string or dict).
        """
        # Check for explicit query parameter
        query = params.get("query", "")

        # Check for task parameter (alias)
        if not query:
            query = params.get("task", "")

        # If no explicit input, use all params as context
        if not query and params:
            # Convert params to formatted input
            return params

        # Build agent input
        if query:
            # Check if additional context is provided
            messages = params.get("messages")
            metadata = params.get("metadata")

            if messages or metadata:
                return {
                    "query": query,
                    "messages": messages,
                    "metadata": metadata,
                }
            return query

        # Fallback: return params as dict
        return params


# Global registry instance
_global_registry: Optional[AgentRegistry] = None


def get_agent_registry() -> AgentRegistry:
    """Get the global agent registry singleton."""
    global _global_registry
    if _global_registry is None:
        _global_registry = AgentRegistry()
    return _global_registry


def register_agent(
    name: str,
    agent: BaseAgent,
    metadata: Optional[AgentMetadata] = None,
) -> None:
    """Register an agent in the global registry.

    Convenience function for registering agents.

    Args:
        name: Agent name
        agent: Agent instance
        metadata: Optional metadata
    """
    get_agent_registry().register(name, agent, metadata)


def get_agent(name: str) -> Optional[BaseAgent]:
    """Get an agent from the global registry.

    Args:
        name: Agent name

    Returns:
        Agent or None
    """
    return get_agent_registry().get(name)


def wrap_agent_as_tool(name: str):
    """Wrap an agent as a tool from global registry.

    Args:
        name: Agent name

    Returns:
        AgentAsTool or None
    """
    return get_agent_registry().wrap_as_tool(name)
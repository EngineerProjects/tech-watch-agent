"""
Base agent class and configuration.

This module provides the foundational BaseAgent class that all agents
should inherit from. It defines the common interface and lifecycle methods
for agents, along with configuration management.

Design principles:
- Dependency injection for services (LLM, tools, etc.)
- Async-first design for concurrent operations
- Type-safe configuration via Pydantic
- Comprehensive error handling and logging
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Sequence
import uuid

from app.config.settings import Settings, get_settings
from app.core.logging import get_logger


logger = get_logger(__name__)


@dataclass
class AgentConfig:
    """Configuration for an agent instance.

    This dataclass holds all configuration options for an agent,
    including model settings, behavior flags, and resource limits.

    Attributes:
        name: Human-readable name for the agent
        model: LLM model identifier (e.g., "openai/gpt-4.1-mini")
        temperature: Sampling temperature (0.0 to 2.0)
        max_tokens: Maximum tokens in response
        max_iterations: Maximum number of agent iterations
        timeout_seconds: Timeout for agent execution
        enable_thinking: Whether to enable chain-of-thought reasoning
        custom_settings: Agent-specific custom settings
    """

    name: str = "BaseAgent"
    model: str = "openai/gpt-4.1-mini"
    temperature: float = 0.3
    max_tokens: int = 2000
    max_iterations: int = 10
    timeout_seconds: int = 300
    enable_thinking: bool = False
    custom_settings: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary representation."""
        return {
            "name": self.name,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "max_iterations": self.max_iterations,
            "timeout_seconds": self.timeout_seconds,
            "enable_thinking": self.enable_thinking,
            "custom_settings": self.custom_settings,
        }


@dataclass
class AgentResult:
    """Result from an agent execution.

    This dataclass encapsulates the outcome of an agent run,
    including success status, output, metadata, and any errors.

    Attributes:
        success: Whether the agent completed successfully
        output: The agent's output (type depends on agent type)
        metadata: Additional metadata about the execution
        errors: List of errors encountered during execution
        execution_time: Time taken for execution in seconds
        session_id: Unique identifier for this execution session
    """

    success: bool
    output: Optional[Any] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    execution_time: Optional[float] = None
    session_id: Optional[uuid.UUID] = None

    @classmethod
    def create_success(
        cls,
        output: Any,
        metadata: Optional[dict[str, Any]] = None,
        session_id: Optional[uuid.UUID] = None,
    ) -> "AgentResult":
        """Factory method to create a successful result."""
        return cls(
            success=True,
            output=output,
            metadata=metadata or {},
            errors=[],
            session_id=session_id,
        )

    @classmethod
    def create_error(
        cls,
        errors: list[str],
        metadata: Optional[dict[str, Any]] = None,
    ) -> "AgentResult":
        """Factory method to create an error result."""
        return cls(
            success=False,
            output=None,
            metadata=metadata or {},
            errors=errors,
        )


class BaseAgent(ABC):
    """Abstract base class for all agents.

    This class defines the common interface and lifecycle methods that
    all agents must implement. It provides dependency injection, logging,
    error handling, and execution tracking.

    Agents should inherit from this class and implement:
    - setup(): Initialize agent-specific resources
    - execute(): Main agent execution logic
    - cleanup(): Release agent-specific resources

    Example:
        class MyAgent(BaseAgent):
            def __init__(self, config: AgentConfig, llm_client: LLMClient):
                super().__init__(config)
                self.llm_client = llm_client

            async def setup(self) -> None:
                await self.llm_client.initialize()

            async def execute(self, input_data: Any) -> AgentResult:
                # Agent logic here
                pass

            async def cleanup(self) -> None:
                await self.llm_client.close()
    """

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        """Initialize the base agent.

        Args:
            config: Agent configuration (uses defaults if not provided)
            settings: Application settings (uses global settings if not provided)
        """
        self.config = config or AgentConfig()
        self.settings = settings or get_settings()
        self._is_initialized = False
        self._current_session_id: Optional[uuid.UUID] = None

    @property
    def name(self) -> str:
        """Get the agent's name."""
        return self.config.name

    @property
    def is_initialized(self) -> bool:
        """Check if the agent is initialized."""
        return self._is_initialized

    async def initialize(self) -> None:
        """Initialize the agent before first use.

        This method should be called before executing the agent.
        It calls the setup() method which subclasses can override
        to perform agent-specific initialization.

        Raises:
            RuntimeError: If the agent is already initialized
        """
        if self._is_initialized:
            raise RuntimeError(f"Agent '{self.name}' is already initialized")

        logger.info("Initializing agent: %s", self.name)
        await self.setup()
        self._is_initialized = True

    @abstractmethod
    async def setup(self) -> None:
        """Set up agent-specific resources.

        Subclasses should override this method to initialize
        any resources they need (LLM clients, tool registries, etc.).

        Example:
            async def setup(self) -> None:
                self.llm = await create_llm_client(self.config.model)
                self.tools = await self._load_tools()
        """
        pass

    @abstractmethod
    async def execute(self, input_data: Any) -> AgentResult:
        """Execute the agent with the given input.

        This is the main entry point for agent execution. Subclasses
        must implement this method with their specific logic.

        Args:
            input_data: The input data for the agent (type depends on agent)

        Returns:
            AgentResult with the execution outcome

        Raises:
            RuntimeError: If the agent is not initialized
        """
        pass

    async def cleanup(self) -> None:
        """Clean up agent resources.

        This method is called when the agent is no longer needed.
        Subclasses should override this method to release any
        resources they hold (connections, caches, etc.).

        Example:
            async def cleanup(self) -> None:
                await self.llm.close()
                self.cache.clear()
        """
        logger.info("Cleaning up agent: %s", self.name)
        self._is_initialized = False

    async def run(self, input_data: Any) -> AgentResult:
        """Run the agent with automatic lifecycle management.

        This is a convenience method that handles initialization,
        execution, and cleanup automatically. Use this method
        for single-shot agent invocations.

        Args:
            input_data: The input data for the agent

        Returns:
            AgentResult with the execution outcome
        """
        start_time = datetime.now()

        # Ensure initialization
        if not self._is_initialized:
            await self.initialize()

        # Create session ID
        self._current_session_id = uuid.uuid4()

        try:
            # Execute with error handling
            result = await self.execute(input_data)
            result.session_id = self._current_session_id

            # Calculate execution time
            elapsed = (datetime.now() - start_time).total_seconds()
            result.execution_time = elapsed

            logger.info(
                "Agent '%s' completed in %.2fs (session=%s)",
                self.name,
                elapsed,
                self._current_session_id,
            )

            return result

        except Exception as exc:
            # Handle unexpected errors
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.error(
                "Agent '%s' failed after %.2fs: %s",
                self.name,
                elapsed,
                exc,
            )

            return AgentResult.create_error(
                errors=[str(exc)],
                metadata={
                    "session_id": str(self._current_session_id),
                    "execution_time": elapsed,
                },
            )

        finally:
            # Always cleanup
            await self.cleanup()
            self._current_session_id = None

    def get_metadata(self) -> dict[str, Any]:
        """Get agent metadata for debugging and monitoring.

        Returns:
            Dictionary with agent configuration and status
        """
        return {
            "name": self.name,
            "model": self.config.model,
            "is_initialized": self._is_initialized,
            "current_session_id": str(self._current_session_id) if self._current_session_id else None,
            "config": self.config.to_dict(),
        }

    def validate_input(self, input_data: Any) -> bool:
        """Validate input data before execution.

        Subclasses can override this method to implement
        input validation specific to their needs.

        Args:
            input_data: The input to validate

        Returns:
            True if valid, False otherwise
        """
        return input_data is not None


class AgentRegistry:
    """Registry for managing multiple agent instances.

    This class provides a central registry for all agents in the system,
    enabling dynamic agent creation, lookup, and lifecycle management.

    Usage:
        registry = AgentRegistry()
        registry.register("newsletter", newsletter_agent)
        agent = registry.get("newsletter")
    """

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}
        self._enabled: set[str] = set()

    def register(self, name: str, agent: BaseAgent) -> None:
        """Register an agent with a given name.

        Args:
            name: The name to register the agent under
            agent: The agent instance to register

        Raises:
            ValueError: If an agent with this name already exists
        """
        if name in self._agents:
            raise ValueError(f"Agent '{name}' is already registered")
        self._agents[name] = agent
        self._enabled.add(name)

    def get(self, name: str) -> Optional[BaseAgent]:
        """Get an agent by name.

        Args:
            name: The name of the agent to retrieve

        Returns:
            The agent instance or None if not found
        """
        return self._agents.get(name)

    def unregister(self, name: str) -> bool:
        """Unregister an agent by name.

        Args:
            name: The name of the agent to unregister

        Returns:
            True if unregistered, False if not found
            
        Raises:
            KeyError: If the agent is not registered (for backwards compat)
        """
        if name not in self._agents:
            raise KeyError(f"Agent '{name}' is not registered")
        del self._agents[name]
        self._enabled.discard(name)
        return True

    def is_enabled(self, name: str) -> bool:
        """Check if an agent is enabled.
        
        Args:
            name: Agent name
            
        Returns:
            True if enabled (always true for base registry)
        """
        return name in self._agents

    def list_agents(self) -> list[str]:
        """List all registered agent names.

        Returns:
            List of registered agent names
        """
        return list(self._agents.keys())

    async def initialize_all(self) -> None:
        """Initialize all registered agents."""
        for name, agent in self._agents.items():
            try:
                await agent.initialize()
            except Exception as exc:
                logger.error("Failed to initialize agent '%s': %s", name, exc)

    async def cleanup_all(self) -> None:
        """Clean up all registered agents."""
        for name, agent in self._agents.items():
            try:
                await agent.cleanup()
            except Exception as exc:
                logger.error("Failed to cleanup agent '%s': %s", name, exc)

    @property
    def count(self) -> int:
        """Return number of registered agents."""
        return len(self._agents)

    def __contains__(self, name: str) -> bool:
        """Check if agent is registered (supports 'in' operator)."""
        return name in self._agents

    def enable(self, name: str) -> bool:
        """Enable a registered agent."""
        if name not in self._agents:
            return False
        self._enabled.add(name)
        return True

    def disable(self, name: str) -> bool:
        """Disable a registered agent."""
        if name not in self._agents:
            return False
        self._enabled.discard(name)
        return True

    def is_enabled(self, name: str) -> bool:
        """Check if an agent is enabled."""
        return name in self._enabled

    def list_by_category(self, category: str) -> list[str]:
        """List agents by category (not applicable for this registry)."""
        return []
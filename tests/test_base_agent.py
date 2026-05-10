"""
Tests for the agent base module.

This module tests the BaseAgent class and AgentConfig dataclass,
ensuring proper initialization, lifecycle management, and error handling.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.base.base_agent import (
    BaseAgent,
    AgentConfig,
    AgentResult,
    AgentRegistry,
)


class TestAgentConfig:
    """Tests for AgentConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = AgentConfig()

        assert config.name == "BaseAgent"
        assert config.model == "openai/gpt-4.1-mini"
        assert config.temperature == 0.3
        assert config.max_tokens == 2000
        assert config.max_iterations == 10
        assert config.timeout_seconds == 300
        assert config.enable_thinking is False
        assert config.custom_settings == {}

    def test_custom_values(self):
        """Test custom configuration values."""
        config = AgentConfig(
            name="TestAgent",
            model="openai/gpt-4o",
            temperature=0.7,
            max_tokens=4000,
            max_iterations=5,
            enable_thinking=True,
            custom_settings={"key": "value"},
        )

        assert config.name == "TestAgent"
        assert config.model == "openai/gpt-4o"
        assert config.temperature == 0.7
        assert config.max_tokens == 4000
        assert config.max_iterations == 5
        assert config.enable_thinking is True
        assert config.custom_settings == {"key": "value"}

    def test_to_dict(self):
        """Test conversion to dictionary."""
        config = AgentConfig(name="TestAgent", model="test-model")
        config_dict = config.to_dict()

        assert isinstance(config_dict, dict)
        assert config_dict["name"] == "TestAgent"
        assert config_dict["model"] == "test-model"
        assert "custom_settings" in config_dict


class TestAgentResult:
    """Tests for AgentResult dataclass."""

    def test_create_success(self):
        """Test creating a successful result."""
        result = AgentResult.create_success(
            output="test output",
            metadata={"key": "value"},
        )

        assert result.success is True
        assert result.output == "test output"
        assert result.metadata == {"key": "value"}
        assert result.errors == []

    def test_create_error(self):
        """Test creating an error result."""
        result = AgentResult.create_error(
            errors=["error 1", "error 2"],
            metadata={"context": "test"},
        )

        assert result.success is False
        assert result.output is None
        assert result.errors == ["error 1", "error 2"]
        assert result.metadata == {"context": "test"}

    def test_result_with_session_id(self):
        """Test result with session ID."""
        import uuid

        session_id = uuid.uuid4()
        result = AgentResult.create_success(
            output="output",
            session_id=session_id,
        )

        assert result.session_id == session_id


class TestAgentRegistry:
    """Tests for AgentRegistry class."""

    def test_register_agent(self):
        """Test registering an agent."""
        registry = AgentRegistry()
        mock_agent = MagicMock(spec=BaseAgent)
        mock_agent.name = "test_agent"

        registry.register("test", mock_agent)

        assert "test" in registry.list_agents()
        assert registry.get("test") == mock_agent

    def test_register_duplicate_raises(self):
        """Test that registering duplicate names raises error."""
        registry = AgentRegistry()
        mock_agent = MagicMock(spec=BaseAgent)
        mock_agent.name = "test"

        registry.register("test", mock_agent)

        with pytest.raises(ValueError, match="already registered"):
            registry.register("test", mock_agent)

    def test_unregister_agent(self):
        """Test unregistering an agent."""
        registry = AgentRegistry()
        mock_agent = MagicMock(spec=BaseAgent)
        mock_agent.name = "test"

        registry.register("test", mock_agent)
        assert registry.unregister("test") is True
        assert registry.get("test") is None

    def test_unregister_nonexistent_raises(self):
        """Test that unregistering nonexistent agent raises error."""
        registry = AgentRegistry()

        with pytest.raises(KeyError, match="not registered"):
            registry.unregister("nonexistent")

    def test_enable_disable_tool(self):
        """Test enabling and disabling tools."""
        registry = AgentRegistry()
        mock_agent = MagicMock(spec=BaseAgent)
        mock_agent.name = "test"
        mock_agent.enabled = True

        registry.register("test", mock_agent)

        assert registry.is_enabled("test") is True

        registry.disable("test")
        assert registry.is_enabled("test") is False

        registry.enable("test")
        assert registry.is_enabled("test") is True

    def test_list_by_category_not_applicable(self):
        """Test that list_by_category is available (placeholder for tool system)."""
        registry = AgentRegistry()
        # This is a placeholder - actual category filtering is in ToolRegistry
        assert registry.count == 0

    def test_contains_operator(self):
        """Test 'in' operator for registry."""
        registry = AgentRegistry()
        mock_agent = MagicMock(spec=BaseAgent)
        mock_agent.name = "test"

        registry.register("test", mock_agent)

        assert "test" in registry
        assert "nonexistent" not in registry


class TestBaseAgentImplementation(BaseAgent):
    """Test implementation of BaseAgent for testing."""

    async def setup(self) -> None:
        """Implementation of setup."""
        self.setup_called = True

    async def execute(self, input_data: Any) -> AgentResult:
        """Implementation of execute."""
        return AgentResult.create_success(output=f"Processed: {input_data}")

    async def cleanup(self) -> None:
        """Implementation of cleanup."""
        self.cleanup_called = True


class TestBaseAgent:
    """Tests for BaseAgent class."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = MagicMock()
        settings.llm_model = "test-model"
        return settings

    @pytest.fixture
    def agent(self, mock_settings):
        """Create a test agent instance."""
        config = AgentConfig(name="TestAgent")
        return TestBaseAgentImplementation(config=config, settings=mock_settings)

    def test_initialization(self, agent):
        """Test agent initialization."""
        assert agent.name == "TestAgent"
        assert agent.is_initialized is False

    def test_get_metadata(self, agent):
        """Test getting agent metadata."""
        metadata = agent.get_metadata()

        assert metadata["name"] == "TestAgent"
        assert "config" in metadata
        assert metadata["is_initialized"] is False

    def test_validate_input(self, agent):
        """Test input validation."""
        assert agent.validate_input(None) is False
        assert agent.validate_input("test") is True
        assert agent.validate_input({"key": "value"}) is True

    @pytest.mark.asyncio
    async def test_initialize(self, agent):
        """Test agent initialization."""
        await agent.initialize()

        assert agent.is_initialized is True
        assert hasattr(agent, "setup_called")
        assert agent.setup_called is True

    @pytest.mark.asyncio
    async def test_initialize_twice_raises(self, agent):
        """Test that initializing twice raises error."""
        await agent.initialize()

        with pytest.raises(RuntimeError, match="already initialized"):
            await agent.initialize()

    @pytest.mark.asyncio
    async def test_run_complete_lifecycle(self, agent):
        """Test complete agent lifecycle with run()."""
        result = await agent.run("test input")

        assert result.success is True
        assert result.output == "Processed: test input"
        assert result.session_id is not None

    @pytest.mark.asyncio
    async def test_run_with_error(self, agent):
        """Test error handling in run()."""

        class ErrorAgent(BaseAgent):
            async def setup(self) -> None:
                pass

            async def execute(self, input_data: Any) -> AgentResult:
                raise ValueError("Test error")

            async def cleanup(self) -> None:
                pass

        error_agent = ErrorAgent(config=AgentConfig(name="ErrorAgent"))
        result = await error_agent.run("test")

        assert result.success is False
        assert "Test error" in result.errors

    @pytest.mark.asyncio
    async def test_cleanup_called(self, agent):
        """Test that cleanup is called after run()."""
        await agent.run("test")

        assert hasattr(agent, "cleanup_called")
        assert agent.cleanup_called is True


# Example test for agent extension pattern
class TestAgentExtensionPattern:
    """Tests demonstrating proper agent extension pattern."""

    def test_extending_base_agent(self):
        """Test that subclasses properly implement abstract methods."""
        # This should work without errors
        class MinimalAgent(BaseAgent):
            async def setup(self) -> None:
                pass

            async def execute(self, input_data: Any) -> AgentResult:
                return AgentResult.create_success(output="done")

            async def cleanup(self) -> None:
                pass

        agent = MinimalAgent()
        assert agent.name == "BaseAgent"  # Uses default name
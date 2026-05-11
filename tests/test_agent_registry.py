"""
Tests for the agent registry and AgentAsTool pattern.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.agents.registry import (
    AgentRegistry,
    AgentMetadata,
    AgentAsTool,
    get_agent_registry,
    register_agent,
    get_agent,
    wrap_agent_as_tool,
)
from app.agents.base.base_agent import BaseAgent, AgentConfig, AgentResult


class MockAgent(BaseAgent):
    """Mock agent for testing."""

    @property
    def description(self) -> str:
        return "Mock test agent"

    async def setup(self) -> None:
        self._setup_called = True

    async def execute(self, input_data) -> AgentResult:
        return AgentResult.create_success(
            output={"result": f"processed: {input_data}"},
            metadata={"input": str(input_data)[:50]},
        )


@pytest.fixture
def fresh_registry():
    """Create a fresh registry for each test."""
    return AgentRegistry()


@pytest.fixture
def mock_agent():
    """Create a mock agent."""
    config = AgentConfig(name="test_agent")
    return MockAgent(config=config)


class TestAgentRegistry:
    """Tests for AgentRegistry."""

    def test_register_agent(self, fresh_registry, mock_agent):
        """Test registering an agent."""
        fresh_registry.register("test", mock_agent)
        assert "test" in fresh_registry.list_agents()

    def test_unregister_agent(self, fresh_registry, mock_agent):
        """Test unregistering an agent."""
        fresh_registry.register("test", mock_agent)
        assert fresh_registry.unregister("test")
        assert "test" not in fresh_registry.list_agents()

    def test_get_agent(self, fresh_registry, mock_agent):
        """Test retrieving an agent."""
        fresh_registry.register("test", mock_agent)
        agent = fresh_registry.get("test")
        assert agent is mock_agent

    def test_get_nonexistent_agent(self, fresh_registry):
        """Test retrieving a non-existent agent returns None."""
        assert fresh_registry.get("nonexistent") is None

    def test_register_with_metadata(self, fresh_registry, mock_agent):
        """Test registering with custom metadata."""
        metadata = AgentMetadata(
            name="test",
            description="Test agent",
            category="testing",
        )
        fresh_registry.register("test", mock_agent, metadata)
        
        retrieved_meta = fresh_registry.get_metadata("test")
        assert retrieved_meta.description == "Test agent"
        assert retrieved_meta.category == "testing"

    def test_list_metadata(self, fresh_registry, mock_agent):
        """Test listing all agent metadata."""
        fresh_registry.register("agent1", mock_agent)
        fresh_registry.register("agent2", mock_agent)
        
        metadata_list = fresh_registry.list_metadata()
        assert len(metadata_list) == 2

    def test_is_registered(self, fresh_registry, mock_agent):
        """Test checking if agent is registered."""
        fresh_registry.register("test", mock_agent)
        assert fresh_registry.is_registered("test")
        assert not fresh_registry.is_registered("other")


class TestAgentAsTool:
    """Tests for AgentAsTool wrapper."""

    def test_wrap_agent(self, mock_agent):
        """Test wrapping an agent as a tool."""
        tool = AgentAsTool(agent=mock_agent, agent_name="test_agent")
        
        assert tool.name == "agent:test_agent"
        assert "Agent:" in tool.description
        assert tool.category == "agent"

    def test_tool_enabled_property(self, mock_agent):
        """Test tool enabled property."""
        tool = AgentAsTool(agent=mock_agent, agent_name="test_agent")
        assert tool.enabled is True
        
        tool.disable()
        assert tool.enabled is False
        
        tool.enable()
        assert tool.enabled is True

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_agent):
        """Test successful tool execution."""
        tool = AgentAsTool(agent=mock_agent, agent_name="test_agent")
        
        result = await tool.execute({"query": "test query"})
        
        assert result["success"] is True
        assert "data" in result
        assert result["metadata"]["agent"] == "test_agent"

    @pytest.mark.asyncio
    async def test_execute_disabled(self, mock_agent):
        """Test executing a disabled tool."""
        tool = AgentAsTool(agent=mock_agent, agent_name="test_agent")
        tool.disable()
        
        result = await tool.execute({"query": "test"})
        
        assert result["success"] is False
        assert "disabled" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_safe(self, mock_agent):
        """Test execute_safe method."""
        tool = AgentAsTool(agent=mock_agent, agent_name="test_agent")
        
        result = await tool.execute_safe({"query": "test"})
        
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_prepare_input_with_query(self, mock_agent):
        """Test input preparation with query param."""
        tool = AgentAsTool(agent=mock_agent, agent_name="test")
        
        input_data = tool._prepare_input({"query": "my query"})
        
        assert input_data == "my query"

    @pytest.mark.asyncio
    async def test_prepare_input_with_task(self, mock_agent):
        """Test input preparation with task param."""
        tool = AgentAsTool(agent=mock_agent, agent_name="test")
        
        input_data = tool._prepare_input({"task": "my task"})
        
        assert input_data == "my task"

    @pytest.mark.asyncio
    async def test_prepare_input_with_full_context(self, mock_agent):
        """Test input preparation with full context."""
        tool = AgentAsTool(agent=mock_agent, agent_name="test")
        
        input_data = tool._prepare_input({
            "query": "my query",
            "metadata": {"source": "test"}
        })
        
        assert isinstance(input_data, dict)
        assert input_data["query"] == "my query"


class TestGlobalRegistry:
    """Tests for global registry functions."""

    def test_get_global_registry(self):
        """Test getting global registry."""
        registry = get_agent_registry()
        assert registry is not None

    def test_register_and_get_agent(self):
        """Test register_agent and get_agent functions."""
        config = AgentConfig(name="global_test")
        agent = MockAgent(config=config)
        
        register_agent("global_test", agent)
        retrieved = get_agent("global_test")
        
        assert retrieved is agent

    def test_wrap_agent_as_tool(self):
        """Test wrap_agent_as_tool function."""
        config = AgentConfig(name="wrap_test")
        agent = MockAgent(config=config)
        
        register_agent("wrap_test", agent)
        tool = wrap_agent_as_tool("wrap_test")
        
        assert tool is not None
        assert tool.name == "agent:wrap_test"
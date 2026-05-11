"""
Tests for the tool plugin system.

This module tests the BaseTool abstract class and ToolRegistry,
ensuring proper tool registration, execution, and management.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.tools.base import (
    BaseTool,
    ToolResult,
    ToolMetadata,
    ToolCategory,
    CompositeTool,
)
from app.tools.registry import (
    ToolRegistry,
    get_global_registry,
    register_tool,
)


class MockSearchTool(BaseTool):
    """Mock tool for testing."""

    @property
    def name(self) -> str:
        return "mock_search"

    @property
    def description(self) -> str:
        return "A mock search tool for testing"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SEARCH

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["query"],
        }

    async def execute(self, params: dict) -> ToolResult:
        query = params.get("query", "")
        return {
            "success": True,
            "data": [f"Result for: {query}"],
            "error": None,
            "metadata": {"count": 1},
        }


class MockCrawlTool(BaseTool):
    """Another mock tool for testing."""

    @property
    def name(self) -> str:
        return "mock_crawl"

    @property
    def description(self) -> str:
        return "A mock crawl tool for testing"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.CRAWL

    async def execute(self, params: dict) -> ToolResult:
        return {
            "success": True,
            "data": "Crawled content",
            "error": None,
            "metadata": {},
        }


class TestToolMetadata:
    """Tests for ToolMetadata dataclass."""

    def test_creation(self):
        """Test creating tool metadata."""
        metadata = ToolMetadata(
            name="test_tool",
            description="A test tool",
            category=ToolCategory.SEARCH,
        )

        assert metadata.name == "test_tool"
        assert metadata.description == "A test tool"
        assert metadata.category == ToolCategory.SEARCH

    def test_to_dict(self):
        """Test converting metadata to dictionary."""
        metadata = ToolMetadata(
            name="test_tool",
            description="A test tool",
            category=ToolCategory.API,
        )

        metadata_dict = metadata.to_dict()

        assert isinstance(metadata_dict, dict)
        assert metadata_dict["name"] == "test_tool"
        assert metadata_dict["category"] == "api"


class TestToolResult:
    """Tests for ToolResult TypedDict."""

    def test_success_result(self):
        """Test creating a success result."""
        result: ToolResult = {
            "success": True,
            "data": "test data",
            "error": None,
            "metadata": {"key": "value"},
        }

        assert result["success"] is True
        assert result["data"] == "test data"

    def test_error_result(self):
        """Test creating an error result."""
        result: ToolResult = {
            "success": False,
            "data": None,
            "error": "Something went wrong",
            "metadata": {},
        }

        assert result["success"] is False
        assert result["error"] == "Something went wrong"


class TestBaseTool:
    """Tests for BaseTool abstract class."""

    def test_abstract_methods_required(self):
        """Test that abstract methods must be implemented."""
        with pytest.raises(TypeError, match="abstract"):
            BaseTool()

    def test_mock_tool_execution(self):
        """Test executing a mock tool."""
        tool = MockSearchTool()
        result = asyncio.run(tool.execute({"query": "test"}))

        assert result["success"] is True

    def test_validate_params_valid(self):
        """Test parameter validation with valid params."""
        tool = MockSearchTool()
        is_valid, error = tool.validate_params({"query": "test"})

        assert is_valid is True
        assert error is None

    def test_validate_params_missing_required(self):
        """Test parameter validation with missing required param."""
        tool = MockSearchTool()
        is_valid, error = tool.validate_params({})

        assert is_valid is False
        assert "query" in error

    def test_enable_disable(self):
        """Test enabling and disabling tools."""
        tool = MockCrawlTool()

        assert tool.enabled is True

        tool.disable()
        assert tool.enabled is False

        tool.enable()
        assert tool.enabled is True

    @pytest.mark.asyncio
    async def test_execute_safe_disabled_tool(self):
        """Test executing a disabled tool."""
        tool = MockCrawlTool()
        tool.disable()

        result = await tool.execute_safe({"param": "value"})

        assert result["success"] is False
        assert "disabled" in result["error"]


class TestToolRegistry:
    """Tests for ToolRegistry class."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for each test."""
        return ToolRegistry()

    def test_register_tool(self, registry):
        """Test registering a tool."""
        tool = MockSearchTool()
        registry.register(tool)

        assert "mock_search" in registry
        assert registry.get("mock_search") == tool

    def test_register_with_custom_name(self, registry):
        """Test registering with custom name."""
        tool = MockSearchTool()
        registry.register(tool, name="custom_name")

        assert "custom_name" in registry
        assert registry.get("custom_name") == tool

    def test_register_with_aliases(self, registry):
        """Test registering with aliases."""
        tool = MockSearchTool()
        registry.register(tool, aliases=["search", "lookup"])

        assert registry.get("search") == tool
        assert registry.get("lookup") == tool

    def test_register_duplicate_raises(self, registry):
        """Test that registering duplicate raises error."""
        tool1 = MockSearchTool()
        tool2 = MockSearchTool()

        registry.register(tool1)

        with pytest.raises(ValueError, match="already registered"):
            registry.register(tool2)

    def test_unregister(self, registry):
        """Test unregistering a tool."""
        tool = MockSearchTool()
        registry.register(tool)

        assert registry.unregister("mock_search") is True
        assert "mock_search" not in registry

    def test_unregister_nonexistent(self, registry):
        """Test unregistering nonexistent tool."""
        assert registry.unregister("nonexistent") is False

    def test_get_or_raise(self, registry):
        """Test get_or_raise method."""
        tool = MockSearchTool()
        registry.register(tool)

        retrieved = registry.get_or_raise("mock_search")
        assert retrieved == tool

    def test_get_or_raise_raises(self, registry):
        """Test get_or_raise raises for missing tool."""
        with pytest.raises(KeyError, match="not found"):
            registry.get_or_raise("nonexistent")

    def test_list_tools(self, registry):
        """Test listing all tools."""
        registry.register(MockSearchTool())
        registry.register(MockCrawlTool())

        tools = registry.list_tools()

        assert len(tools) == 2
        assert "mock_search" in tools
        assert "mock_crawl" in tools

    def test_list_by_category(self, registry):
        """Test filtering tools by category."""
        search_tool = MockSearchTool()
        crawl_tool = MockCrawlTool()

        registry.register(search_tool)
        registry.register(crawl_tool)

        search_tools = registry.list_tools_by_category(ToolCategory.SEARCH)
        crawl_tools = registry.list_tools_by_category(ToolCategory.CRAWL)

        assert len(search_tools) == 1
        assert search_tools[0].name == "mock_search"
        assert len(crawl_tools) == 1
        assert crawl_tools[0].name == "mock_crawl"

    def test_enable_disable_tools(self, registry):
        """Test enabling and disabling tools."""
        tool = MockSearchTool()
        registry.register(tool)

        assert registry.is_enabled("mock_search") is True

        registry.disable("mock_search")
        assert registry.is_enabled("mock_search") is False

        registry.enable("mock_search")
        assert registry.is_enabled("mock_search") is True

    def test_list_tools_metadata(self, registry):
        """Test getting metadata for all tools."""
        registry.register(MockSearchTool())
        registry.register(MockCrawlTool())

        metadata_list = registry.list_tools_metadata()

        assert len(metadata_list) == 2
        names = [m.name for m in metadata_list]
        assert "mock_search" in names
        assert "mock_crawl" in names

    def test_clear_registry(self, registry):
        """Test clearing the registry."""
        registry.register(MockSearchTool())
        registry.register(MockCrawlTool())

        assert registry.count == 2

        registry.clear()

        assert registry.count == 0

    def test_iteration(self, registry):
        """Test iterating over registry."""
        registry.register(MockSearchTool())
        registry.register(MockCrawlTool())

        tools = list(registry)
        assert len(tools) == 2


class TestGlobalRegistry:
    """Tests for global registry functions."""

    def test_get_global_registry(self):
        """Test getting the global registry."""
        registry = get_global_registry()

        assert registry is not None
        assert isinstance(registry, ToolRegistry)

    def test_register_tool_decorator(self):
        """Test the register_tool decorator."""
        # Note: This modifies global state, so we test it carefully
        registry = get_global_registry()
        initial_count = registry.count

        # Create a unique tool name for this test
        tool_name = f"test_tool_{id(self)}"

        class TestTool(BaseTool):
            @property
            def name(self) -> str:
                return tool_name

            @property
            def description(self) -> str:
                return "Test tool"

            async def execute(self, params: dict) -> ToolResult:
                return {"success": True, "data": None, "error": None, "metadata": {}}

        decorated_tool = register_tool(TestTool())

        # Tool should be registered
        assert registry.count >= initial_count
        assert registry.get(tool_name) is not None

        # Cleanup
        registry.unregister(tool_name)


class TestCompositeTool:
    """Tests for CompositeTool class."""

    def test_add_get_tools(self):
        """Test adding and getting sub-tools."""
        composite = CompositeTool()
        search_tool = MockSearchTool()
        crawl_tool = MockCrawlTool()

        composite.add_tool("search", search_tool)
        composite.add_tool("crawl", crawl_tool)

        assert composite.get_tool("search") == search_tool
        assert composite.get_tool("crawl") == crawl_tool
        assert composite.get_tool("nonexistent") is None

    def test_tools_property(self):
        """Test getting all tools."""
        composite = CompositeTool()
        composite.add_tool("search", MockSearchTool())
        composite.add_tool("crawl", MockCrawlTool())

        tools = composite.tools

        assert len(tools) == 2
        assert "search" in tools
        assert "crawl" in tools
"""
Base tool abstraction and common types.

This module defines the core interfaces and types for the tool plugin system.
All tools should inherit from BaseTool and follow the defined conventions.

The tool system is designed to be:
- Extensible: New tools can be added without modifying existing code
- Testable: Tools can be tested in isolation
- Type-safe: Strong typing throughout the system
- Async-first: Tools support async execution for concurrency
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from typing_extensions import TypedDict


class ToolCategory(Enum):
    """Categories for organizing tools.

    Tools are grouped by their primary function to help with
    discovery and management.
    """

    SEARCH = "search"  # Web/Database search tools
    CRAWL = "crawl"  # Content fetching/scraping tools
    SOCIAL = "social"  # Social media monitoring (GitHub, Reddit, etc.)
    API = "api"  # External API integrations
    DATA = "data"  # Data processing/analysis tools
    UTILITY = "utility"  # General utility tools
    MEMORY = "memory"  # Memory/retrieval tools


@dataclass
class ToolMetadata:
    """Metadata for a tool.

    Provides descriptive information about a tool including
    its name, description, parameters schema, and category.

    Attributes:
        name: Unique identifier for the tool
        description: Human-readable description of what the tool does
        category: The category this tool belongs to
        parameters: JSON schema for tool parameters
        examples: Example parameter combinations
        version: Tool version string
        author: Tool author information
    """

    name: str
    description: str
    category: ToolCategory = ToolCategory.UTILITY
    parameters: dict[str, Any] = field(default_factory=dict)
    examples: list[dict[str, Any]] = field(default_factory=list)
    version: str = "1.0.0"
    author: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert metadata to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "parameters": self.parameters,
            "examples": self.examples,
            "version": self.version,
            "author": self.author,
        }


class ToolResult(TypedDict):
    """Result from a tool execution.

    This TypedDict defines the standard response format for all tools.
    All tools should return results in this format for consistency.

    Attributes:
        success: Whether the tool executed successfully
        data: The output data from the tool (type depends on tool)
        error: Error message if execution failed
        metadata: Additional metadata about the execution
    """

    success: bool
    data: Optional[Any]  # Tool-specific output data
    error: Optional[str]  # Error message if success is False
    metadata: dict[str, Any]  # Execution metadata (duration, etc.)


class BaseTool(ABC):
    """Abstract base class for all tools.

    This class defines the interface that all tools must implement.
    Tools are the primary way to extend the agent's capabilities.

    Subclasses must implement:
    - name: Unique identifier for the tool
    - description: Human-readable description
    - parameters: JSON schema for tool parameters
    - execute(): The main tool logic

    Example:
        class WebSearchTool(BaseTool):
            @property
            def name(self) -> str:
                return "web_search"

            @property
            def description(self) -> str:
                return "Search the web for information"

            @property
            def parameters(self) -> dict:
                return {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"}
                    },
                    "required": ["query"]
                }

            async def execute(self, params: dict) -> ToolResult:
                # Tool implementation
                ...
    """

    def __init__(self) -> None:
        """Initialize the tool."""
        self._enabled = True

    @property
    @abstractmethod
    def name(self) -> str:
        """Get the tool's unique name.

        This name is used to identify the tool in the registry
        and in agent tool calls. Should be snake_case.

        Returns:
            The tool's unique name
        """
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Get the tool's description.

        This description is used in tool discovery and documentation.
        Should explain what the tool does and when to use it.

        Returns:
            The tool's description
        """
        pass

    @property
    def category(self) -> ToolCategory:
        """Get the tool's category.

        Override this property to categorize your tool appropriately.

        Returns:
            The tool's category (defaults to UTILITY)
        """
        return ToolCategory.UTILITY

    @property
    def parameters(self) -> dict[str, Any]:
        """Get the tool's parameter schema.

        This should return a JSON schema defining the tool's parameters.
        Used for validation and agent tool binding.

        Returns:
            JSON schema for tool parameters
        """
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    @property
    def metadata(self) -> ToolMetadata:
        """Get tool metadata.

        Returns metadata about the tool including version, author, etc.

        Returns:
            ToolMetadata instance with tool information
        """
        return ToolMetadata(
            name=self.name,
            description=self.description,
            category=self.category,
            parameters=self.parameters,
        )

    @abstractmethod
    async def execute(self, params: dict[str, Any]) -> ToolResult:
        """Execute the tool with the given parameters.

        This is the main entry point for tool execution. Implement
        the tool's logic here.

        Args:
            params: Dictionary of parameters for the tool

        Returns:
            ToolResult with the execution outcome

        Example:
            async def execute(self, params: dict) -> ToolResult:
                query = params.get("query")
                if not query:
                    return {
                        "success": False,
                        "data": None,
                        "error": "Missing required parameter: query",
                        "metadata": {},
                    }

                try:
                    results = await self.search(query)
                    return {
                        "success": True,
                        "data": results,
                        "error": None,
                        "metadata": {"count": len(results)},
                    }
                except Exception as exc:
                    return {
                        "success": False,
                        "data": None,
                        "error": str(exc),
                        "metadata": {},
                    }
        """
        pass

    def validate_params(self, params: dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate parameters before execution.

        Override this method to implement custom validation logic.
        Default implementation checks required parameters.

        Args:
            params: The parameters to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Get required parameters from schema
        required = self.parameters.get("required", [])

        # Check for missing required parameters
        for param in required:
            if param not in params or params[param] is None:
                return False, f"Missing required parameter: {param}"

        return True, None

    @property
    def enabled(self) -> bool:
        """Check if the tool is enabled."""
        return self._enabled

    def enable(self) -> None:
        """Enable the tool."""
        self._enabled = True

    def disable(self) -> None:
        """Disable the tool."""
        self._enabled = False

    async def execute_safe(self, params: dict[str, Any]) -> ToolResult:
        """Execute with validation and error handling.

        Convenience method that handles validation and exceptions.

        Returns:
            ToolResult with standardized format
        """
        # Check if enabled
        if not self._enabled:
            return {
                "success": False,
                "data": None,
                "error": f"Tool '{self.name}' is disabled",
                "metadata": {},
            }

        # Validate parameters
        is_valid, error = self.validate_params(params)
        if not is_valid:
            return {
                "success": False,
                "data": None,
                "error": error,
                "metadata": {},
            }

        # Execute with error handling
        try:
            return await self.execute(params)
        except Exception as exc:
            return {
                "success": False,
                "data": None,
                "error": f"Tool execution failed: {str(exc)}",
                "metadata": {},
            }


class CompositeTool(BaseTool):
    """A tool composed of multiple sub-tools.

    This class allows combining multiple tools into a single
    logical tool. Useful for tools that need to perform
    multiple operations in sequence.

    Subclasses should override execute() to coordinate sub-tool calls.
    """

    def __init__(self) -> None:
        super().__init__()
        self._tools: dict[str, BaseTool] = {}

    @property
    def name(self) -> str:
        return "composite_tool"

    @property
    def description(self) -> str:
        return "A tool composed of multiple sub-tools"

    def add_tool(self, name: str, tool: BaseTool) -> None:
        """Add a sub-tool to this composite.

        Args:
            name: Name to register the tool under
            tool: The tool to add
        """
        self._tools[name] = tool

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a sub-tool by name.

        Args:
            name: Name of the tool to retrieve

        Returns:
            The tool or None if not found
        """
        return self._tools.get(name)

    @property
    def tools(self) -> dict[str, BaseTool]:
        """Get all sub-tools."""
        return self._tools.copy()

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        raise NotImplementedError("Subclasses must implement execute()")
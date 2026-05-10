"""
Tool registry for dynamic tool management.

This module provides the ToolRegistry class for managing tool instances
and the global registry singleton for application-wide access.

The registry supports:
- Dynamic tool registration/unregistration
- Tool lookup by name
- Category-based filtering
- Tool enabling/disabling
- Automatic tool initialization
"""

from typing import Optional
from collections import defaultdict

from app.core.logging import get_logger
from app.tools.base import BaseTool, ToolCategory, ToolMetadata


logger = get_logger(__name__)


# Global registry instance (singleton pattern)
_global_registry: Optional["ToolRegistry"] = None


class ToolRegistry:
    """Registry for managing tool instances.

    This class provides centralized management of all tools in the system.
    It supports dynamic registration, lookup, and lifecycle management.

    Usage:
        # Register a tool
        registry = ToolRegistry()
        registry.register(my_tool)

        # Get a tool
        tool = registry.get("web_search")

        # List all tools
        tools = registry.list_tools()

        # Filter by category
        search_tools = registry.list_tools_by_category(ToolCategory.SEARCH)
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._tools: dict[str, BaseTool] = {}
        self._categories: dict[ToolCategory, list[str]] = defaultdict(list)
        self._aliases: dict[str, str] = {}  # name aliases

    def register(
        self,
        tool: BaseTool,
        name: Optional[str] = None,
        aliases: Optional[list[str]] = None,
    ) -> None:
        """Register a tool in the registry.

        Args:
            tool: The tool instance to register
            name: Optional custom name (defaults to tool.name)
            aliases: Optional list of alternative names

        Raises:
            ValueError: If a tool with the same name is already registered
        """
        tool_name = name or tool.name

        # Check for duplicate registration
        if tool_name in self._tools:
            raise ValueError(
                f"Tool '{tool_name}' is already registered. "
                f"Unregister first or use a different name."
            )

        # Register the tool
        self._tools[tool_name] = tool

        # Add to category index
        category = tool.category
        if tool_name not in self._categories[category]:
            self._categories[category].append(tool_name)

        # Register aliases
        if aliases:
            for alias in aliases:
                if alias in self._tools:
                    raise ValueError(f"Alias '{alias}' conflicts with existing tool name")
                self._aliases[alias] = tool_name

        logger.info("Registered tool: %s (category: %s)", tool_name, category.value)

    def unregister(self, name: str) -> bool:
        """Unregister a tool from the registry.

        Args:
            name: Name of the tool to unregister

        Returns:
            True if the tool was unregistered, False if not found
        """
        if name not in self._tools:
            return False

        tool = self._tools[name]

        # Remove from main registry
        del self._tools[name]

        # Remove from category index
        category = tool.category
        if name in self._categories[category]:
            self._categories[category].remove(name)

        # Remove aliases
        aliases_to_remove = [alias for alias, target in self._aliases.items() if target == name]
        for alias in aliases_to_remove:
            del self._aliases[alias]

        logger.info("Unregistered tool: %s", name)
        return True

    def get(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name.

        Resolves aliases and returns the tool if found.

        Args:
            name: Name of the tool (or alias)

        Returns:
            The tool instance or None if not found
        """
        # Resolve alias if needed
        resolved_name = self._aliases.get(name, name)
        return self._tools.get(resolved_name)

    def get_or_raise(self, name: str) -> BaseTool:
        """Get a tool by name, raising an exception if not found.

        Args:
            name: Name of the tool

        Returns:
            The tool instance

        Raises:
            KeyError: If the tool is not found
        """
        tool = self.get(name)
        if tool is None:
            raise KeyError(f"Tool '{name}' not found in registry")
        return tool

    def list_tools(self) -> list[str]:
        """Get list of all registered tool names.

        Returns:
            List of tool names
        """
        return list(self._tools.keys())

    def list_tools_by_category(self, category: ToolCategory) -> list[BaseTool]:
        """Get all tools in a specific category.

        Args:
            category: The category to filter by

        Returns:
            List of tools in the category
        """
        tool_names = self._categories.get(category, [])
        return [self._tools[name] for name in tool_names if name in self._tools]

    def list_tools_metadata(self) -> list[ToolMetadata]:
        """Get metadata for all registered tools.

        Returns:
            List of ToolMetadata for all tools
        """
        return [tool.metadata for tool in self._tools.values()]

    def get_by_category(self, category: ToolCategory) -> list[BaseTool]:
        """Get all tools in a category (alias for list_tools_by_category).

        Args:
            category: The category to filter by

        Returns:
            List of tools in the category
        """
        return self.list_tools_by_category(category)

    def enable(self, name: str) -> bool:
        """Enable a tool.

        Args:
            name: Name of the tool to enable

        Returns:
            True if enabled, False if tool not found
        """
        tool = self.get(name)
        if tool:
            tool.enable()
            logger.info("Enabled tool: %s", name)
            return True
        return False

    def disable(self, name: str) -> bool:
        """Disable a tool.

        Args:
            name: Name of the tool to disable

        Returns:
            True if disabled, False if tool not found
        """
        tool = self.get(name)
        if tool:
            tool.disable()
            logger.info("Disabled tool: %s", name)
            return True
        return False

    def is_enabled(self, name: str) -> bool:
        """Check if a tool is enabled.

        Args:
            name: Name of the tool

        Returns:
            True if enabled, False if disabled or not found
        """
        tool = self.get(name)
        return tool is not None and tool.enabled

    def clear(self) -> None:
        """Clear all tools from the registry."""
        count = len(self._tools)
        self._tools.clear()
        self._categories.clear()
        self._aliases.clear()
        logger.info("Cleared %d tools from registry", count)

    @property
    def count(self) -> int:
        """Get the number of registered tools."""
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        """Check if a tool is registered (supports 'in' operator)."""
        return name in self._tools

    def __iter__(self):
        """Iterate over registered tools."""
        return iter(self._tools.values())


def get_global_registry() -> ToolRegistry:
    """Get the global tool registry singleton.

    Returns:
        The global ToolRegistry instance
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry


def register_tool(
    tool: BaseTool,
    name: Optional[str] = None,
    aliases: Optional[list[str]] = None,
) -> None:
    """Register a tool in the global registry.

    Convenience function for registering tools to the global registry.

    Args:
        tool: The tool instance to register
        name: Optional custom name
        aliases: Optional list of aliases

    Example:
        @register_tool
        class MyTool(BaseTool):
            ...
    """
    registry = get_global_registry()
    registry.register(tool, name, aliases)


def get_tool(name: str) -> Optional[BaseTool]:
    """Get a tool from the global registry.

    Args:
        name: Name of the tool

    Returns:
        The tool or None if not found
    """
    return get_global_registry().get(name)


# Decorator for automatic tool registration
def tool(
    name: Optional[str] = None,
    category: ToolCategory = ToolCategory.UTILITY,
    aliases: Optional[list[str]] = None,
):
    """Decorator for registering a tool class with the global registry.

    This decorator automatically instantiates and registers a tool class
    when the module is imported.

    Args:
        name: Optional custom name for the tool
        category: Tool category
        aliases: Optional list of aliases

    Usage:
        @tool(name="web_search", category=ToolCategory.SEARCH)
        class WebSearchTool(BaseTool):
            ...
    """

    def decorator(cls: type[BaseTool]) -> type[BaseTool]:
        # Create instance and register
        instance = cls()
        registry = get_global_registry()
        registry.register(instance, name, aliases)
        return cls

    return decorator
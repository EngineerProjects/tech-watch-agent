"""
Tool plugin system for tech-watch-agent.

This module provides a flexible plugin architecture for extending the agent's
capabilities through custom tools. Tools can perform web searches, interact with
APIs, scrape content, or any other operation the agent might need.

Design principles:
- BaseTool abstract class for consistent interface
- ToolResult TypedDict for standardized responses
- Plugin registry for dynamic tool loading
- Async-first design for concurrent operations
"""

from app.tools.base import BaseTool, ToolResult, ToolMetadata, ToolCategory
from app.tools.registry import ToolRegistry, get_global_registry, register_tool

__all__ = [
    "BaseTool",
    "ToolResult",
    "ToolMetadata",
    "ToolCategory",
    "ToolRegistry",
    "get_global_registry",
    "register_tool",
]
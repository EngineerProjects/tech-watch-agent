"""
MCP (Model Context Protocol) server and client for deep research tool integration.

MCP allows AI agents to use tools via a standardized protocol.
This module provides both an MCP server (exposes our tools) and
an MCP client wrapper (for consuming external MCP servers).

The MCP server follows the official MCP spec and exposes our tools
as MCP resources and tools that any MCP-compatible agent can use.
"""

from __future__ import annotations

import json
from typing import Any, Optional
from dataclasses import dataclass, field
from enum import Enum

from app.core.logging import get_logger


logger = get_logger(__name__)


class MCPMethod(str, Enum):
    INITIALIZE = "initialize"
    TOOLS_LIST = "tools/list"
    TOOLS_CALL = "tools/call"
    RESOURCES_LIST = "resources/list"
    RESOURCES_READ = "resources/read"
    PROMPTS_LIST = "prompts/list"
    PROMPTS_GET = "prompts/get"


@dataclass
class MCPTool:
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass
class MCPResource:
    uri: str
    name: str
    description: str
    mime_type: str = "application/json"


@dataclass
class MCPPrompt:
    name: str
    description: str
    arguments: list[dict[str, str]]


@dataclass
class MCPRequest:
    jsonrpc: str = "2.0"
    id: int | str | None = None
    method: str = ""
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPResponse:
    jsonrpc: str = "2.0"
    id: int | str | None = None
    result: Any = None
    error: dict[str, Any] | None = None


class MCPServer:
    """MCP server that exposes tools to compatible agents.

    Implements the MCP JSON-RPC protocol. Agents can connect via HTTP/SSE
    and call our registered tools using the MCP protocol.

    Usage:
        server = MCPServer()
        server.register_tool(tavily_search_tool)
        server.register_tool(web_crawl_tool)
        await server.start(port=8080)
    """

    def __init__(self, name: str = "tech-watch-agent", version: str = "1.0.0") -> None:
        self.name = name
        self.version = version
        self._tools: dict[str, Any] = {}
        self._resources: dict[str, MCPResource] = {}
        self._prompts: dict[str, MCPPrompt] = {}

    def register_tool(self, tool: Any) -> None:
        """Register a tool with the MCP server.

        Args:
            tool: A BaseTool instance to expose via MCP
        """
        tool_name = getattr(tool, "name", str(tool))
        self._tools[tool_name] = tool
        logger.info("MCP registered tool: %s", tool_name)

    def register_resource(self, resource: MCPResource) -> None:
        self._resources[resource.uri] = resource

    def register_prompt(self, prompt: MCPPrompt) -> None:
        self._prompts[prompt.name] = prompt

    def list_tools(self) -> list[MCPTool]:
        """List all registered tools as MCP tools."""
        tools = []
        for name, tool in self._tools.items():
            tools.append(MCPTool(
                name=getattr(tool, "name", name),
                description=getattr(tool, "description", ""),
                input_schema=getattr(tool, "parameters", {"type": "object", "properties": {}}),
            ))
        return tools

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Handle an MCP JSON-RPC request.

        Args:
            request: JSON-RPC request dict

        Returns:
            JSON-RPC response dict
        """
        method = request.get("method", "")
        req_id = request.get("id")
        params = request.get("params", {})

        response: dict[str, Any] = {"jsonrpc": "2.0", "id": req_id}

        try:
            if method == MCPMethod.INITIALIZE.value:
                response["result"] = {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {"listChanged": True},
                        "resources": {"subscribe": True, "listChanged": True},
                        "prompts": {"listChanged": True},
                    },
                    "serverInfo": {
                        "name": self.name,
                        "version": self.version,
                    },
                }

            elif method == MCPMethod.TOOLS_LIST.value:
                tools = self.list_tools()
                response["result"] = {
                    "tools": [
                        {
                            "name": t.name,
                            "description": t.description,
                            "inputSchema": t.input_schema,
                        }
                        for t in tools
                    ]
                }

            elif method == MCPMethod.TOOLS_CALL.value:
                tool_name = params.get("name", "")
                arguments = params.get("arguments", {})

                tool = self._tools.get(tool_name)
                if tool is None:
                    response["error"] = {
                        "code": -32602,
                        "message": f"Tool '{tool_name}' not found",
                    }
                else:
                    import asyncio
                    if hasattr(tool, "execute"):
                        result = asyncio.run(tool.execute(arguments))
                    elif hasattr(tool, "execute_safe"):
                        result = asyncio.run(tool.execute_safe(arguments))
                    else:
                        result = {"success": False, "error": "Tool has no execute method"}

                    response["result"] = {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(result, ensure_ascii=False, default=str),
                            }
                        ],
                        "isError": not result.get("success", False),
                    }

            elif method == MCPMethod.RESOURCES_LIST.value:
                response["result"] = {
                    "resources": [
                        {"uri": r.uri, "name": r.name, "description": r.description, "mimeType": r.mime_type}
                        for r in self._resources.values()
                    ]
                }

            elif method == MCPMethod.PROMPTS_LIST.value:
                response["result"] = {
                    "prompts": [
                        {"name": p.name, "description": p.description, "arguments": p.arguments}
                        for p in self._prompts.values()
                    ]
                }

            else:
                response["error"] = {"code": -32601, "message": f"Method '{method}' not found"}

        except Exception as exc:
            logger.error("MCP handle_request error: %s", exc)
            response["error"] = {"code": -32603, "message": str(exc)}

        return response


class MCPClient:
    """MCP client for connecting to external MCP servers.

    Allows the deep research agent to use tools from external MCP servers
    (like Tavily MCP, search APIs, etc.) via the MCP protocol.

    Usage:
        client = MCPClient("http://localhost:8080")
        await client.initialize()
        result = await client.call_tool("tavily_search", {"query": "AI news"})
    """

    def __init__(self, server_url: str, api_key: Optional[str] = None) -> None:
        self.server_url = server_url.rstrip("/")
        self._api_key = api_key
        self._session_id: Optional[str] = None
        self._protocol_version: Optional[str] = None
        self._tools: list[dict] = []
        self._initialized = False

    async def initialize(self) -> dict[str, Any]:
        """Initialize connection to MCP server.

        Returns:
            Server info and capabilities
        """
        import httpx

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                },
                "clientInfo": {
                    "name": "tech-watch-agent",
                    "version": "1.0.0",
                },
            },
        }

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.server_url,
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()

            self._initialized = True
            self._protocol_version = data.get("result", {}).get("protocolVersion")
            self._tools = data.get("result", {}).get("capabilities", {}).get("tools", {})

            logger.info("MCP client initialized: %s", self.server_url)
            return data.get("result", {})

        except Exception as exc:
            logger.error("MCP initialization failed: %s", exc)
            return {"error": str(exc)}

    async def list_tools(self) -> list[dict[str, Any]]:
        """List available tools from MCP server.

        Returns:
            List of tool definitions
        """
        if not self._initialized:
            await self.initialize()

        import httpx

        payload = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.server_url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
            return data.get("result", {}).get("tools", [])
        except Exception as exc:
            logger.error("MCP list_tools failed: %s", exc)
            return []

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a tool on the MCP server.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool execution result
        """
        if not self._initialized:
            await self.initialize()

        import httpx

        payload = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(self.server_url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()

            result = data.get("result", {})
            content = result.get("content", [])
            if content and content[0].get("type") == "text":
                return json.loads(content[0]["text"])
            return result

        except Exception as exc:
            logger.error("MCP call_tool '%s' failed: %s", tool_name, exc)
            return {"success": False, "error": str(exc)}

    @property
    def tools(self) -> list[dict]:
        return self._tools

    @property
    def is_initialized(self) -> bool:
        return self._initialized


class MCPToolAdapter:
    """Adapter that wraps an MCP client tool as a local BaseTool.

    Allows using external MCP tools as if they were local tools,
    making them compatible with the tool registry.

    Usage:
        adapter = MCPToolAdapter(mcp_client, "tavily_search")
        result = await adapter.execute({"query": "AI news"})
    """

    def __init__(self, mcp_client: MCPClient, tool_name: str, description: str = "") -> None:
        self._client = mcp_client
        self._tool_name = tool_name
        self._description = description
        self._schema: dict[str, Any] = {}

    async def _load_schema(self) -> None:
        tools = await self._client.list_tools()
        for t in tools:
            if t.get("name") == self._tool_name:
                self._schema = t.get("inputSchema", {})
                if not self._description:
                    self._description = t.get("description", "")
                break

    @property
    def name(self) -> str:
        return f"mcp_{self._tool_name}"

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> dict[str, Any]:
        return self._schema

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """Execute via MCP client."""
        if not self._client.is_initialized:
            await self._client.initialize()
        if not self._schema:
            await self._load_schema()
        return await self._client.call_tool(self._tool_name, params)

    async def execute_safe(self, params: dict[str, Any]) -> dict[str, Any]:
        """Safe execute wrapper."""
        return await self.execute(params)
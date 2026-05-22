from typing import Any
from fastapi import APIRouter, Depends, HTTPException

from app.api.security import require_admin_access
from app.tools.registry import get_global_registry
from app.api.models import ToolListResponse, ToolExecuteRequest, ToolExecuteResponse

router = APIRouter(prefix="/tools", tags=["Tools"])

@router.get("", response_model=ToolListResponse)
async def list_tools() -> ToolListResponse:
    """List all registered tools."""
    registry = get_global_registry()
    tools = registry.list_tools_metadata()

    return ToolListResponse(
        tools=[t.to_dict() for t in tools],
        count=len(tools),
    )

@router.get("/{tool_name}")
async def get_tool(tool_name: str) -> dict[str, Any]:
    """Get details about a specific tool."""
    registry = get_global_registry()
    tool = registry.get(tool_name)

    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    return tool.metadata.to_dict()

@router.post("/execute", response_model=ToolExecuteResponse, dependencies=[Depends(require_admin_access)])
async def execute_tool(payload: ToolExecuteRequest) -> ToolExecuteResponse:
    """Execute a tool with given parameters."""
    registry = get_global_registry()
    tool = registry.get(payload.tool_name)

    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{payload.tool_name}' not found")

    try:
        result = await tool.execute_safe(payload.params)
        return ToolExecuteResponse(
            success=result.get("success", False),
            data=result.get("data"),
            error=result.get("error"),
            metadata=result.get("metadata", {}),
        )
    except Exception as exc:
        return ToolExecuteResponse(
            success=False,
            data=None,
            error=str(exc),
            metadata={},
        )

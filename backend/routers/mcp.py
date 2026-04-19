"""MCP 工具对外 REST 路由。

- GET  /api/mcp/tools              列出工具元数据
- GET  /api/mcp/health             注册表健康与调用计数
- POST /api/mcp/tools/{name}/call  调用指定工具

REST 仅作为 MCP 协议在无 SDK 环境下的降级入口；保留工具名、入参 schema
与后续真实 MCP 传输一致，替换传输层时调用端无需改造。
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services.mcp import McpServer


router = APIRouter(prefix="/api/mcp", tags=["mcp"])

_server = McpServer()


class InvokeReq(BaseModel):
    args: Dict[str, Any] = Field(default_factory=dict)


@router.get("/tools")
def list_tools():
    return {"tools": _server.list_tools()}


@router.get("/health")
def health():
    return _server.health()


@router.post("/tools/{tool_name}/call")
def call_tool(tool_name: str, body: InvokeReq):
    result = _server.call_tool(tool_name, body.args)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result

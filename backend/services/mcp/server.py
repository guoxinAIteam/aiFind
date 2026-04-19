"""MCP Server 侧最小实现。

本地直接通过 ToolRegistry 调度；对外通过 /api/mcp 路由暴露。当且仅当
mcp SDK 可用时，可在此处拓展为 `mcp.server.Server` 真实 MCP 传输。
"""
from __future__ import annotations

from typing import Any, Dict

from backend.services.mcp.registry import ToolRegistry, registry


class McpServer:
    """工具调度门面。

    之所以包一层而不直接对外 export registry，是为了后续加上：
    - 分布式调用链 trace 透传
    - 鉴权（X-MCP-Token）校验
    - 结构化日志与熔断计数
    """

    def __init__(self, reg: ToolRegistry = registry) -> None:
        self._reg = reg
        # 触发默认工具注册
        from backend.services.mcp import tools  # noqa: F401

    def list_tools(self):
        return self._reg.list_tools()

    def call_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        return self._reg.invoke(name, args)

    def health(self) -> Dict[str, Any]:
        return self._reg.health()

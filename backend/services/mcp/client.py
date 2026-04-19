"""MCP Client：决策中枢调用上下游的统一入口。

当前实现：
- 本地注册表直连（进程内 tool 调用）
- 未来拓展：通过 stdio / sse / websocket 的真实 MCP 传输
"""
from __future__ import annotations

from typing import Any, Dict

from backend.services.mcp.registry import ToolRegistry, registry


class McpClient:
    def __init__(self, reg: ToolRegistry = registry) -> None:
        self._reg = reg
        from backend.services.mcp import tools  # noqa: F401 — 触发工具注册

    def invoke(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """调用一个工具；内部已做限流与异常归一化。"""
        return self._reg.invoke(tool_name, args)

    def list_tools(self):
        return self._reg.list_tools()

"""MCP 协议适配层。

本期以"协议-就位，SDK-未接入"的最小可用形态落地：
- Server：在 aiFind 进程内暴露标准 JSON-RPC 风格工具（通过 /api/mcp/* 路由）
- Client：统一包装上下游调用，无 MCP SDK 时降级为原生 HTTP
- Registry：工具注册表 + 鉴权/健康检查/调用计数
"""

from backend.services.mcp.registry import registry  # noqa: F401
from backend.services.mcp.server import McpServer  # noqa: F401
from backend.services.mcp.client import McpClient  # noqa: F401

__all__ = ["registry", "McpServer", "McpClient"]

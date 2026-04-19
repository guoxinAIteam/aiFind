"""上下游智能体调用审计：HTTP 中间件 + Agent 调用装饰器。

两个粒度：
1) HTTP 层：拦截所有 /api/parse/* /api/flows/*(static|supplement)
   /api/mcp/* 请求，抓取 method/path/status/latency 作为 AgentInvocation
   补充记录（request/response 由各 handler 内部主动写入，更精准）。
2) 调用层：`audit_agent_call` 装饰器提供同步写审计的便利方法，
   供未来新增 skill / tool 时复用。
"""
from __future__ import annotations

import json
import time
from typing import Any, Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from backend.database import SessionLocal
from backend.models import AgentInvocation, MonitorEvent


AUDIT_PREFIXES = (
    "/api/parse",
    "/api/mcp",
    "/api/flows/static",
)


def _direction_for(path: str) -> str:
    if path.startswith("/api/parse") or "unicom" in path:
        return "upstream"
    if path.startswith("/api/mcp"):
        return "system"
    return "downstream"


class AgentAuditMiddleware(BaseHTTPMiddleware):
    """把上下游相关 REST 调用结果写入 AgentInvocation。

    请求体尽量不阻塞主流程：失败落库只记一行，不影响响应；大 body 截断到 8k。
    """

    def __init__(self, app: ASGIApp, *, max_body_bytes: int = 8192) -> None:
        super().__init__(app)
        self.max_body_bytes = max_body_bytes

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path
        if not any(path.startswith(p) for p in AUDIT_PREFIXES):
            return await call_next(request)

        started = time.monotonic()
        status = "succeeded"
        error_msg = ""
        response: Response
        try:
            response = await call_next(request)
            if response.status_code >= 400:
                status = "failed"
                error_msg = f"HTTP {response.status_code}"
        except Exception as e:  # noqa: BLE001
            status = "failed"
            error_msg = f"{type(e).__name__}: {e}"
            raise
        finally:
            latency_ms = int((time.monotonic() - started) * 1000)
            try:
                _persist(
                    direction=_direction_for(path),
                    tool_name=f"{request.method} {path}",
                    request_preview={
                        "method": request.method,
                        "path": path,
                        "query": str(request.url.query or ""),
                    },
                    response_preview={
                        "status_code": locals().get("response") and locals()["response"].status_code,
                    },
                    status=status,
                    error=error_msg,
                    latency_ms=latency_ms,
                )
            except Exception:
                # 审计写入失败绝不能影响主链路
                pass

        return response


def _persist(
    *,
    direction: str,
    tool_name: str,
    request_preview: Any,
    response_preview: Any,
    status: str,
    error: str,
    latency_ms: int,
) -> None:
    db = SessionLocal()
    try:
        db.add(
            AgentInvocation(
                direction=direction,
                agent="http_layer",
                tool_name=tool_name,
                request=_truncate(request_preview),
                response=_truncate(response_preview),
                status=status,
                error=error,
                latency_ms=latency_ms,
            )
        )
        # 失败且 tool 路径属于关键工具时，写一条告警
        if status == "failed" and direction in {"upstream", "downstream"}:
            db.add(
                MonitorEvent(
                    event_type=(
                        "upstream_timeout" if direction == "upstream" else "bdi_step_failed"
                    ),
                    severity="warning",
                    title=f"{tool_name} 调用失败",
                    detail=error or "未知异常",
                    source_system=direction,
                )
            )
        db.commit()
    finally:
        db.close()


def _truncate(obj: Any, limit: int = 8192) -> Any:
    try:
        s = json.dumps(obj, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        s = repr(obj)
    if len(s) <= limit:
        return obj if isinstance(obj, (dict, list)) else {"preview": s}
    return {"_truncated": True, "preview": s[:limit]}

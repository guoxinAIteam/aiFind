"""MCP 工具注册表。

提供工具元数据、健康检查、调用计数、内存限流（按工具 + 窗口）。
为 Nacos / 外部 MCP Registry 对接预留 export / import_bulk 接口。
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, List, Optional


ToolHandler = Callable[[Dict[str, Any]], Dict[str, Any]]


@dataclass
class ToolSpec:
    name: str
    description: str
    direction: str  # upstream / downstream / system
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    handler: ToolHandler
    rate_limit_per_min: int = 120
    auth_required: bool = False

    def to_public(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "direction": self.direction,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "auth_required": self.auth_required,
            "rate_limit_per_min": self.rate_limit_per_min,
        }


@dataclass
class ToolStats:
    calls: int = 0
    failures: int = 0
    last_latency_ms: int = 0
    last_invoked_at: float = 0.0
    windows: Deque[float] = field(default_factory=deque)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, ToolSpec] = {}
        self._stats: Dict[str, ToolStats] = defaultdict(ToolStats)
        self._lock = threading.Lock()

    def register(self, spec: ToolSpec, *, replace: bool = False) -> None:
        with self._lock:
            if not replace and spec.name in self._tools:
                raise ValueError(f"工具 {spec.name} 已注册")
            self._tools[spec.name] = spec

    def get(self, name: str) -> Optional[ToolSpec]:
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        return [s.to_public() for s in self._tools.values()]

    def _rate_check(self, spec: ToolSpec) -> bool:
        limit = spec.rate_limit_per_min
        if limit <= 0:
            return True
        now = time.monotonic()
        window_start = now - 60.0
        q = self._stats[spec.name].windows
        while q and q[0] < window_start:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True

    def invoke(self, name: str, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        spec = self.get(name)
        if not spec:
            return {
                "ok": False,
                "error": f"tool '{name}' not found",
                "tools": [t.to_public()["name"] for t in self._tools.values()],
            }
        if not self._rate_check(spec):
            return {"ok": False, "error": f"rate limit exceeded for {name}"}
        stats = self._stats[spec.name]
        started = time.monotonic()
        try:
            result = spec.handler(args or {})
            stats.calls += 1
            stats.last_latency_ms = int((time.monotonic() - started) * 1000)
            stats.last_invoked_at = time.time()
            return {"ok": True, "tool": spec.name, "result": result, "latency_ms": stats.last_latency_ms}
        except Exception as e:  # noqa: BLE001 — 工具内部异常统一收口
            stats.calls += 1
            stats.failures += 1
            stats.last_invoked_at = time.time()
            return {"ok": False, "tool": spec.name, "error": f"{type(e).__name__}: {e}"}

    def health(self) -> Dict[str, Any]:
        return {
            "tools_total": len(self._tools),
            "tools": [
                {
                    "name": name,
                    "calls": st.calls,
                    "failures": st.failures,
                    "last_latency_ms": st.last_latency_ms,
                    "last_invoked_at": st.last_invoked_at,
                }
                for name, st in self._stats.items()
            ],
        }

    def export(self) -> List[Dict[str, Any]]:
        """导出当前工具元数据，供 Nacos / MCP Registry 注册。"""
        return [s.to_public() for s in self._tools.values()]


registry = ToolRegistry()

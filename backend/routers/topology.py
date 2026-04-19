"""3D 全景大屏拓扑 API。

- GET /api/topology/snapshot  首帧：静态拓扑 + 当前活跃任务 + 节点聚合指标
- GET /api/topology/stream    SSE：每 1.5s 推一次 task_tick + event delta

前端 /topology 页面首帧调 snapshot，再通过 SSE 接增量；SSE 断开后由前端
自行降级到 5s 轮询 snapshot。
"""
from __future__ import annotations

import asyncio
import datetime as _dt
import json
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.database import SessionLocal, get_db
from backend.models import (
    AgentInvocation,
    BdiTaskBinding,
    CollectTask,
    FlowStep,
    MonitorEvent,
    SystemMetric,
)


router = APIRouter(prefix="/api/topology", tags=["topology"])


# ---------------------------------------------------------------------------
# 静态节点/边定义
# ---------------------------------------------------------------------------

LAYER_SOURCES = 1
LAYER_UPSTREAM = 2
LAYER_CORE = 3
LAYER_BDI = 4
LAYER_TARGETS = 5


# key 必须与前端坐标映射保持一致；label 为展示文本
NODE_DEFS: List[Dict[str, Any]] = [
    # Layer 1 数据源
    {"key": "sftp",         "layer": LAYER_SOURCES,  "label": "SFTP 文件源",   "kind": "source"},
    {"key": "kafka",        "layer": LAYER_SOURCES,  "label": "Kafka",           "kind": "source"},
    {"key": "hdfs_src",     "layer": LAYER_SOURCES,  "label": "HDFS 源",         "kind": "source"},
    {"key": "doc_spec",     "layer": LAYER_SOURCES,  "label": "接口规范文档",   "kind": "source"},
    # Layer 2 上游 AI 解析
    {"key": "unicom_ai",    "layer": LAYER_UPSTREAM, "label": "联通 AI 解析",   "kind": "upstream"},
    {"key": "doc_parser",   "layer": LAYER_UPSTREAM, "label": "aiFind 文档解析", "kind": "upstream"},
    # Layer 3 aiFind 决策中枢
    {"key": "parse",        "layer": LAYER_CORE,     "label": "Parse Router",    "kind": "core"},
    {"key": "flows",        "layer": LAYER_CORE,     "label": "Flow Orchestrator", "kind": "core"},
    {"key": "mcp",          "layer": LAYER_CORE,     "label": "MCP Registry",    "kind": "core"},
    {"key": "skills",       "layer": LAYER_CORE,     "label": "Skill Hub",       "kind": "core"},
    # Layer 4 BDI 执行
    {"key": "resource",     "layer": LAYER_BDI,      "label": "资源注册",        "kind": "bdi"},
    {"key": "modeling",     "layer": LAYER_BDI,      "label": "数据建模",        "kind": "bdi"},
    {"key": "mapping",      "layer": LAYER_BDI,      "label": "映射设计",        "kind": "bdi"},
    {"key": "flow_mgmt",    "layer": LAYER_BDI,      "label": "流程管理",        "kind": "bdi"},
    # Layer 5 目标端
    {"key": "hbase",        "layer": LAYER_TARGETS,  "label": "HBase",           "kind": "target"},
    {"key": "hive",         "layer": LAYER_TARGETS,  "label": "Hive / MC",       "kind": "target"},
    {"key": "hdfs_dst",     "layer": LAYER_TARGETS,  "label": "HDFS 目标",       "kind": "target"},
]

NODE_INDEX: Dict[str, Dict[str, Any]] = {n["key"]: n for n in NODE_DEFS}


def _edges() -> List[Dict[str, str]]:
    edges: List[Dict[str, str]] = []
    # 数据源 -> 上游 AI
    for s in ("sftp", "kafka", "hdfs_src"):
        edges.append({"from": s, "to": "unicom_ai"})
    edges.append({"from": "doc_spec", "to": "doc_parser"})
    edges.append({"from": "doc_spec", "to": "unicom_ai"})
    # 上游 AI -> 决策中枢
    edges.append({"from": "unicom_ai", "to": "parse"})
    edges.append({"from": "doc_parser", "to": "parse"})
    edges.append({"from": "parse", "to": "flows"})
    edges.append({"from": "flows", "to": "mcp"})
    edges.append({"from": "flows", "to": "skills"})
    edges.append({"from": "mcp", "to": "skills"})
    # 决策中枢 -> BDI
    for s in ("flows", "mcp"):
        for t in ("resource", "modeling", "mapping", "flow_mgmt"):
            edges.append({"from": s, "to": t})
    # BDI -> 目标端
    for s in ("modeling", "mapping", "flow_mgmt"):
        edges.append({"from": s, "to": "hbase"})
        edges.append({"from": s, "to": "hive"})
        edges.append({"from": s, "to": "hdfs_dst"})
    return edges


EDGES: List[Dict[str, str]] = _edges()


# ---------------------------------------------------------------------------
# 任务 -> 拓扑路径映射
# ---------------------------------------------------------------------------


def _task_path(task: CollectTask) -> List[str]:
    """为一个任务推导出它在拓扑图上的路径（节点 key 列表）。

    静态采集场景按 8 阶段骨架；legacy 6 步场景按 HBase 通道骨架。
    """
    if (task.scenario or "") == "static_bdi":
        # sftp/kafka/hdfs_src 之一 → unicom_ai → parse → flows → modeling → mapping → flow_mgmt → hive
        return [
            "sftp",
            "unicom_ai",
            "parse",
            "flows",
            "modeling",
            "mapping",
            "flow_mgmt",
            "hive",
        ]
    # legacy HBase 通道（kafka → flows → skills → HBase → hdfs → hive）
    return [
        "kafka",
        "flows",
        "skills",
        "hbase",
        "hdfs_dst",
        "hive",
    ]


_STAGE_TO_NODE: Dict[str, str] = {
    "intake": "flows",
    "parsing": "parse",
    "transforming": "flows",
    "bdi_executing": "modeling",
    "monitoring": "flow_mgmt",
    "error_handling": "flows",
    "testing": "flow_mgmt",
    "online": "hive",
}


def _current_node(task: CollectTask) -> Optional[str]:
    if (task.scenario or "") == "static_bdi":
        return _STAGE_TO_NODE.get((task.stage or "").strip(), None)
    # legacy：按 current_step 粗略映射
    step = int(task.current_step or 0)
    legacy_path = ["kafka", "flows", "skills", "hbase", "hdfs_dst", "hive"]
    idx = max(0, min(len(legacy_path) - 1, step))
    return legacy_path[idx]


# ---------------------------------------------------------------------------
# 聚合指标（面向每个节点）
# ---------------------------------------------------------------------------


_AGENT_TO_NODE: Dict[str, str] = {
    "unicom_ai_parser": "unicom_ai",
    "http_layer": "parse",
    "bdi_executor": "modeling",
}


def _invocations_metrics(db: Session) -> Dict[str, Dict[str, Any]]:
    """聚合每个节点的调用次数、失败数、平均延迟。

    只统计近 24h 的 AgentInvocation，避免早期冷启动数据压制新鲜指标。
    """
    since = _dt.datetime.utcnow() - _dt.timedelta(hours=24)
    rows = (
        db.query(AgentInvocation)
        .filter(AgentInvocation.created_at >= since)
        .all()
    )
    buckets: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"calls": 0, "fail": 0, "latency_sum": 0, "latency_n": 0}
    )
    for r in rows:
        node = _AGENT_TO_NODE.get(r.agent or "")
        if node is None:
            # http 审计按 path 推断：/api/parse* -> parse, /api/mcp* -> mcp, /api/flows/static* -> flows
            tool = r.tool_name or ""
            if "/api/parse" in tool:
                node = "parse"
            elif "/api/mcp" in tool:
                node = "mcp"
            elif "/api/flows/static" in tool:
                node = "flows"
        if not node:
            continue
        b = buckets[node]
        b["calls"] += 1
        if r.status != "succeeded":
            b["fail"] += 1
        if r.latency_ms:
            b["latency_sum"] += int(r.latency_ms)
            b["latency_n"] += 1
    result: Dict[str, Dict[str, Any]] = {}
    for k, b in buckets.items():
        avg = int(b["latency_sum"] / b["latency_n"]) if b["latency_n"] else 0
        result[k] = {
            "calls": b["calls"],
            "fail": b["fail"],
            "avg_latency_ms": avg,
        }
    return result


def _target_pressure(db: Session) -> Dict[str, Dict[str, Any]]:
    """目标端节点从 SystemMetric 抽取资源压力。"""
    since = _dt.datetime.utcnow() - _dt.timedelta(hours=6)
    rows = (
        db.query(SystemMetric)
        .filter(SystemMetric.recorded_at >= since)
        .all()
    )
    by_src: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    for m in rows:
        src = (m.source_system or "").strip()
        if not src:
            continue
        by_src[src][(m.metric_name or "").strip()].append(float(m.metric_value))

    def avg(src: str, key: str) -> float:
        vs = by_src.get(src, {}).get(key, [])
        return sum(vs) / len(vs) if vs else 0.0

    return {
        "hbase": {
            "cpu": round(avg("HBase", "cpu_usage"), 1),
            "mem": round(avg("HBase", "memory_usage"), 1),
        },
        "hive": {
            "cpu": round(avg("Hive", "cpu_usage") or avg("MC", "cpu_usage"), 1),
            "mem": round(avg("Hive", "memory_usage") or avg("MC", "memory_usage"), 1),
        },
        "hdfs_dst": {
            "cpu": round(avg("HDFS", "cpu_usage"), 1),
            "mem": round(avg("HDFS", "memory_usage"), 1),
        },
    }


def _node_status(metrics: Dict[str, Any], unresolved_alerts: int) -> str:
    """统一计算节点状态：healthy / busy / warning / critical / idle。"""
    fail = int(metrics.get("fail") or 0)
    calls = int(metrics.get("calls") or 0)
    if unresolved_alerts > 0 and calls == 0:
        return "warning"
    if calls == 0:
        return "idle"
    if fail == 0:
        return "busy" if calls > 10 else "healthy"
    rate = fail / max(1, calls)
    if rate >= 0.3:
        return "critical"
    if rate >= 0.1:
        return "warning"
    return "busy" if calls > 10 else "healthy"


def _unresolved_by_source(db: Session) -> Dict[str, int]:
    rows = (
        db.query(MonitorEvent.source_system, func.count(MonitorEvent.id))
        .filter(MonitorEvent.resolved == 0)
        .group_by(MonitorEvent.source_system)
        .all()
    )
    out: Dict[str, int] = {}
    for src, cnt in rows:
        if not src:
            continue
        # 把常见大小写写法都兼容一下
        key = str(src).lower()
        out[key] = int(cnt)
    return out


def _collect_active_tasks(db: Session) -> List[Dict[str, Any]]:
    rows = (
        db.query(CollectTask)
        .filter(CollectTask.status.in_(["running", "waiting_supplement", "pending"]))
        .order_by(CollectTask.id.desc())
        .limit(80)
        .all()
    )
    out: List[Dict[str, Any]] = []
    for t in rows:
        path = _task_path(t)
        current = _current_node(t) or path[max(0, min(len(path) - 1, int(t.current_step or 0)))]
        out.append(
            {
                "id": t.id,
                "name": t.name,
                "scenario": t.scenario or "legacy",
                "status": t.status,
                "stage": t.stage or "",
                "progress": int(t.progress or 0),
                "current_step": int(t.current_step or 0),
                "total_steps": int(t.total_steps or 0),
                "path": path,
                "current_node": current,
            }
        )
    return out


def _recent_failed_tasks(db: Session, limit: int = 20) -> List[Dict[str, Any]]:
    since = _dt.datetime.utcnow() - _dt.timedelta(hours=24)
    rows = (
        db.query(CollectTask)
        .filter(CollectTask.status == "failed", CollectTask.created_at >= since)
        .order_by(CollectTask.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": t.id,
            "name": t.name,
            "scenario": t.scenario or "legacy",
            "stage": t.stage or "",
            "error_message": t.error_message or "",
        }
        for t in rows
    ]


def _hud_stats(db: Session, active_tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = db.query(CollectTask).count()
    running = sum(1 for t in active_tasks if t["status"] == "running")
    waiting = sum(1 for t in active_tasks if t["status"] == "waiting_supplement")
    failed = db.query(CollectTask).filter(CollectTask.status == "failed").count()
    completed = db.query(CollectTask).filter(CollectTask.status == "completed").count()
    alerts = (
        db.query(MonitorEvent)
        .filter(
            MonitorEvent.resolved == 0,
            MonitorEvent.severity.in_(["warning", "critical"]),
        )
        .count()
    )
    # 粗略 TPS：近 60s 的 AgentInvocation 数量 / 60
    since = _dt.datetime.utcnow() - _dt.timedelta(seconds=60)
    recent = (
        db.query(func.count(AgentInvocation.id))
        .filter(AgentInvocation.created_at >= since)
        .scalar()
        or 0
    )
    return {
        "total_tasks": total,
        "running": running,
        "waiting": waiting,
        "failed": failed,
        "completed": completed,
        "alerts": alerts,
        "tps": round(recent / 60.0, 2),
        "updated_at": _dt.datetime.utcnow().isoformat() + "Z",
    }


def _build_nodes(
    inv: Dict[str, Dict[str, Any]],
    pressure: Dict[str, Dict[str, Any]],
    alerts_by_src: Dict[str, int],
    active_tasks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    # 统计每个节点上的活跃任务数
    tasks_on_node: Dict[str, int] = defaultdict(int)
    for t in active_tasks:
        if t.get("current_node"):
            tasks_on_node[t["current_node"]] += 1

    out: List[Dict[str, Any]] = []
    for n in NODE_DEFS:
        key = n["key"]
        m = dict(inv.get(key) or {})
        if key in pressure:
            m.update(pressure[key])
        active_count = tasks_on_node.get(key, 0)
        m["active_tasks"] = active_count
        alerts = alerts_by_src.get(key.lower(), 0)
        status = _node_status(m, alerts)
        if active_count > 0 and status in {"healthy", "idle"}:
            status = "busy"
        out.append(
            {
                **n,
                "status": status,
                "alerts": alerts,
                "metrics": m,
            }
        )
    return out


def _build_snapshot(db: Session) -> Dict[str, Any]:
    inv = _invocations_metrics(db)
    pressure = _target_pressure(db)
    alerts_by_src = _unresolved_by_source(db)
    active_tasks = _collect_active_tasks(db)
    nodes = _build_nodes(inv, pressure, alerts_by_src, active_tasks)
    stats = _hud_stats(db, active_tasks)
    return {
        "nodes": nodes,
        "edges": EDGES,
        "active_tasks": active_tasks,
        "recent_failed": _recent_failed_tasks(db),
        "stats": stats,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/snapshot")
def get_snapshot(db: Session = Depends(get_db)) -> Dict[str, Any]:
    return _build_snapshot(db)


_LAST_EVENT_IDS: Dict[int, int] = {}


def _delta_events(db: Session, conn_id: int) -> List[Dict[str, Any]]:
    last_id = _LAST_EVENT_IDS.get(conn_id, 0)
    rows = (
        db.query(MonitorEvent)
        .filter(MonitorEvent.id > last_id)
        .order_by(MonitorEvent.id.asc())
        .limit(20)
        .all()
    )
    if rows:
        _LAST_EVENT_IDS[conn_id] = rows[-1].id
    return [
        {
            "id": e.id,
            "severity": e.severity,
            "source_system": e.source_system,
            "event_type": e.event_type,
            "title": e.title,
            "created_at": str(e.created_at) if e.created_at else None,
        }
        for e in rows
    ]


async def _sse_generator(conn_id: int, interval_s: float = 1.5):
    # 首条"hello"便于前端立即确认连通
    yield _sse_line({"type": "hello", "ts": _dt.datetime.utcnow().isoformat() + "Z"})
    # init: _LAST_EVENT_IDS 取当前最大 id，避免第一次推送把历史都洗一遍
    db = SessionLocal()
    try:
        max_id = db.query(func.max(MonitorEvent.id)).scalar() or 0
        _LAST_EVENT_IDS[conn_id] = int(max_id)
    finally:
        db.close()

    try:
        while True:
            db = SessionLocal()
            try:
                active_tasks = _collect_active_tasks(db)
                stats = _hud_stats(db, active_tasks)
                yield _sse_line(
                    {
                        "type": "task_tick",
                        "tasks": active_tasks,
                        "stats": stats,
                    }
                )
                events = _delta_events(db, conn_id)
                for ev in events:
                    yield _sse_line({"type": "event", **ev})
            finally:
                db.close()
            await asyncio.sleep(interval_s)
    except asyncio.CancelledError:
        _LAST_EVENT_IDS.pop(conn_id, None)
        raise


def _sse_line(payload: Dict[str, Any]) -> bytes:
    return ("data: " + json.dumps(payload, ensure_ascii=False) + "\n\n").encode("utf-8")


@router.get("/stream")
async def get_stream():
    conn_id = id(object())
    return StreamingResponse(
        _sse_generator(conn_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ---------------------------------------------------------------------------
# 节点详情：最近调用 + 最近事件 + 关联 BDI 绑定
# ---------------------------------------------------------------------------


@router.get("/nodes/{node_key}")
def node_detail(node_key: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    node = NODE_INDEX.get(node_key)
    if not node:
        return {"error": f"unknown node {node_key}"}
    # 最近 20 条调用：按 agent 归属 + http path 推断
    invocations = (
        db.query(AgentInvocation)
        .order_by(AgentInvocation.id.desc())
        .limit(200)
        .all()
    )
    matched_invs: List[Dict[str, Any]] = []
    for r in invocations:
        key = _AGENT_TO_NODE.get(r.agent or "")
        if not key:
            tool = r.tool_name or ""
            if "/api/parse" in tool:
                key = "parse"
            elif "/api/mcp" in tool:
                key = "mcp"
            elif "/api/flows/static" in tool:
                key = "flows"
        if key != node_key:
            continue
        matched_invs.append(
            {
                "id": r.id,
                "direction": r.direction,
                "agent": r.agent,
                "tool_name": r.tool_name,
                "status": r.status,
                "error": r.error or "",
                "latency_ms": r.latency_ms,
                "created_at": str(r.created_at) if r.created_at else None,
            }
        )
        if len(matched_invs) >= 20:
            break

    events = (
        db.query(MonitorEvent)
        .filter(MonitorEvent.source_system.ilike(f"%{node_key}%"))
        .order_by(MonitorEvent.id.desc())
        .limit(10)
        .all()
    )
    # 若是 BDI 阶段节点，展示最近绑定
    bindings: List[Dict[str, Any]] = []
    if node["kind"] == "bdi":
        brows = (
            db.query(BdiTaskBinding)
            .order_by(BdiTaskBinding.id.desc())
            .limit(10)
            .all()
        )
        bindings = [
            {
                "id": b.id,
                "task_id": b.task_id,
                "bdi_task_id": b.bdi_task_id,
                "full_status": b.full_status,
                "last_step": b.last_step,
                "updated_at": str(b.updated_at) if b.updated_at else None,
            }
            for b in brows
        ]
    return {
        "node": node,
        "invocations": matched_invs,
        "events": [
            {
                "id": e.id,
                "severity": e.severity,
                "title": e.title,
                "event_type": e.event_type,
                "source_system": e.source_system,
                "created_at": str(e.created_at) if e.created_at else None,
            }
            for e in events
        ],
        "bdi_bindings": bindings,
    }

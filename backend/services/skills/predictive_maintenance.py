"""预测性维护 Skill"""
import datetime as _dt
from typing import Any, Dict, List, Optional

from backend.services.skills import BaseSkill, hub


def predict_capacity(
    current_rps: float,
    growth_rate_pct_month: float,
    months_ahead: int = 3,
) -> Dict[str, Any]:
    if months_ahead < 1:
        months_ahead = 1
    factor = (1 + growth_rate_pct_month / 100.0) ** months_ahead
    projected = round(current_rps * factor, 2)
    headroom_pct = max(0.0, round((1.5 * current_rps - projected) / max(projected, 1e-6) * 100, 1))
    return {
        "current_rps": current_rps,
        "projected_rps": projected,
        "months_ahead": months_ahead,
        "growth_rate_pct_month": growth_rate_pct_month,
        "recommend_scale_out": projected > current_rps * 1.35,
        "estimated_headroom_pct": headroom_pct,
    }


def health_check(
    component: str, metrics: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    m = metrics or {}
    cpu = m.get("cpu_usage", 55.0)
    mem = m.get("memory_usage", 60.0)
    lat = m.get("latency_p99", 200.0)
    score = int(max(0, min(100, 100 - (cpu + mem) / 4 - min(lat / 50, 30))))
    status = "healthy" if score >= 75 else ("degraded" if score >= 50 else "critical")
    return {
        "component": component,
        "score": score,
        "status": status,
        "signals": {"cpu_usage": cpu, "memory_usage": mem, "latency_p99": lat},
    }


def recommend_maintenance_window(
    blackout_weekdays: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """建议维护窗口：优先周末凌晨（简化规则）。"""
    blackout = set(blackout_weekdays or [])
    now = _dt.datetime.utcnow()
    candidates: List[Dict[str, Any]] = []
    for d in range(1, 15):
        t = now + _dt.timedelta(days=d)
        if t.weekday() in blackout:
            continue
        if t.weekday() >= 5:
            start = t.replace(hour=2, minute=0, second=0, microsecond=0)
            candidates.append(
                {
                    "start_utc": start.isoformat() + "Z",
                    "duration_hours": 4,
                    "reason": "周末业务低峰",
                }
            )
    if not candidates:
        t = now + _dt.timedelta(days=7 - now.weekday())
        start = t.replace(hour=3, minute=0, second=0, microsecond=0)
        candidates.append(
            {
                "start_utc": start.isoformat() + "Z",
                "duration_hours": 2,
                "reason": "默认可选窗口",
            }
        )
    return {"windows": candidates[:3]}


class PredictiveMaintenanceSkill(BaseSkill):
    name = "predictive_maintenance"
    version = "1.0"

    def list_actions(self) -> list[str]:
        return ["predict_capacity", "health_check", "recommend_maintenance_window"]

    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action == "predict_capacity":
            return predict_capacity(
                float(params.get("current_rps", 0)),
                float(params.get("growth_rate_pct_month", 5)),
                int(params.get("months_ahead", 3)),
            )
        if action == "health_check":
            comp = str(params.get("component", "platform"))
            met = params.get("metrics")
            if met is not None and not isinstance(met, dict):
                return {"error": "metrics must be a dict of floats"}
            m_float = {str(k): float(v) for k, v in (met or {}).items()} if met else None
            return health_check(comp, m_float)
        if action == "recommend_maintenance_window":
            bw = params.get("blackout_weekdays")
            if bw is not None and not isinstance(bw, list):
                return {"error": "blackout_weekdays must be a list of ints"}
            return recommend_maintenance_window(bw)
        return {"error": f"Unknown action: {action}"}


hub.register(PredictiveMaintenanceSkill())

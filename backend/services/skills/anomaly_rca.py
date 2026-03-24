"""异常检测与根因分析 Skill"""
import statistics
from typing import Any, Dict, List, Optional

from backend.services.skills import BaseSkill, hub


def analyze_anomaly(metrics: List[float]) -> Dict[str, Any]:
    if not metrics:
        return {"status": "no_data"}
    mean = statistics.mean(metrics)
    stdev = statistics.stdev(metrics) if len(metrics) > 1 else 0
    anomalies = [i for i, v in enumerate(metrics) if abs(v - mean) > 3 * stdev] if stdev else []
    return {
        "mean": round(mean, 2),
        "stdev": round(stdev, 2),
        "anomaly_indexes": anomalies,
        "status": "anomaly_detected" if anomalies else "normal",
    }


def root_cause_analysis(
    metrics: List[float], context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    base = analyze_anomaly(metrics)
    ctx = context or {}
    causes: List[str] = []
    if base.get("status") == "no_data":
        return {**base, "likely_causes": [], "confidence": 0.0}
    if base.get("status") == "anomaly_detected":
        causes.append("指标出现超过 3σ 的尖刺，可能为突发流量或下游阻塞")
        if ctx.get("component") == "Flink":
            causes.append("Flink 侧常见：反压、Kafka Lag、Checkpoint 超时")
        elif ctx.get("component") == "HBase":
            causes.append("HBase 侧常见：Region 热点、RS 负载不均、MemStore 抖动")
    else:
        causes.append("序列在统计意义上平稳，若无业务感知异常可继续观察")
    return {
        **base,
        "likely_causes": causes,
        "confidence": 0.75 if base.get("status") == "anomaly_detected" else 0.4,
    }


def suggest_fix(analysis: Dict[str, Any]) -> Dict[str, Any]:
    status = analysis.get("status")
    fixes: List[str] = []
    if status == "no_data":
        fixes.append("补充采集时间序列数据后再做 RCA")
    elif status == "anomaly_detected":
        fixes.append("检查对应时间窗口的发布、扩容与限流策略")
        fixes.append("对异常点索引做 Trace 关联（Flink Task / HBase Region）")
        fixes.append("若为持续尖刺，考虑调低并行度或增加资源并观察 Lag")
    else:
        fixes.append("保持当前基线监控，无需紧急变更")
    return {"suggestions": fixes, "based_on": status}


class AnomalyRCASkill(BaseSkill):
    name = "anomaly_rca"
    version = "1.0"

    def list_actions(self) -> list[str]:
        return ["detect_anomaly", "root_cause_analysis", "suggest_fix"]

    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action == "detect_anomaly":
            raw = params.get("metrics")
            if not isinstance(raw, list):
                return {"error": "metrics must be a list of numbers"}
            try:
                m = [float(x) for x in raw]
            except (TypeError, ValueError):
                return {"error": "metrics must be numeric"}
            return analyze_anomaly(m)
        if action == "root_cause_analysis":
            raw = params.get("metrics")
            if not isinstance(raw, list):
                return {"error": "metrics must be a list of numbers"}
            try:
                m = [float(x) for x in raw]
            except (TypeError, ValueError):
                return {"error": "metrics must be numeric"}
            ctx = params.get("context") if isinstance(params.get("context"), dict) else None
            return root_cause_analysis(m, ctx)
        if action == "suggest_fix":
            analysis = params.get("analysis")
            if not isinstance(analysis, dict):
                return {"error": "analysis dict required (e.g. output of detect_anomaly)"}
            return suggest_fix(analysis)
        return {"error": f"Unknown action: {action}"}


hub.register(AnomalyRCASkill())

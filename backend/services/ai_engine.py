"""AI 引擎 — 向后兼容层，实际实现已迁移至 skills/ 子模块"""
from backend.services.skills.flow_orchestration import (
    STEP_TEMPLATES,
    calculate_pre_regions,
    generate_hbase_create_cmd,
    generate_flink_config,
    generate_bulkload_cmd,
)
from backend.services.skills.param_optimization import validate_params, recommend_params
from backend.services.skills.anomaly_rca import analyze_anomaly
from backend.services.skills.knowledge_graph import search_knowledge
from backend.services.skills import hub as skill_hub

__all__ = [
    "STEP_TEMPLATES",
    "calculate_pre_regions",
    "generate_hbase_create_cmd",
    "generate_flink_config",
    "generate_bulkload_cmd",
    "validate_params",
    "recommend_params",
    "analyze_anomaly",
    "search_knowledge",
    "skill_hub",
]

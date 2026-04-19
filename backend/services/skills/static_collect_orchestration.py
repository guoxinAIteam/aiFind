"""静态（离线）采集 8 阶段编排模板。

对应 docs/智能采集技术方案.docx 第六节的端到端流程：
任务发起 → AI 解析 → 参数转换 → BDI 调度 → 实时跟踪 → 异常处理
→ 任务测试 → 上线调度
"""
from __future__ import annotations

from typing import Any, Dict, List


STATIC_STAGE_TEMPLATES: List[Dict[str, Any]] = [
    {
        "step_order": 1,
        "stage": "intake",
        "name": "任务发起与需求录入",
        "description": "接收采集需求文本或接口规范文档，生成任务 ID 与初始状态",
        "automation": "auto",
        "operations": [
            {"id": "1.1", "name": "创建任务与初始化状态", "type": "auto", "confirm_required": False},
        ],
    },
    {
        "step_order": 2,
        "stage": "parsing",
        "name": "AI 智能解析与参数提取",
        "description": "调用联通能开 AI 智能体提取源端/目标端/FTP/表结构等结构化参数",
        "automation": "auto",
        "operations": [
            {"id": "2.1", "name": "调用上游 AI 解析智能体", "type": "auto", "confirm_required": False},
            {"id": "2.2", "name": "解析结果合法性校验", "type": "auto", "confirm_required": False},
            {
                "id": "2.3",
                "name": "缺失参数用户补全",
                "type": "manual",
                "confirm_required": True,
                "optional": True,
            },
        ],
    },
    {
        "step_order": 3,
        "stage": "transforming",
        "name": "参数标准化转换与 BDI 入参生成",
        "description": "按 BDI 入参规范自动映射，生成合规的 BDI 全量入参并二次校验",
        "automation": "auto",
        "operations": [
            {"id": "3.1", "name": "上游结果映射到 BDI 入参", "type": "auto", "confirm_required": False},
            {"id": "3.2", "name": "BDI 入参二次校验", "type": "auto", "confirm_required": False},
        ],
    },
    {
        "step_order": 4,
        "stage": "bdi_executing",
        "name": "BDI 全流程自动化执行调度",
        "description": "通过 MCP/HTTP 调度下游执行：数据建模 → 映射设计 → 流程管理",
        "automation": "auto",
        "operations": [
            {"id": "4.1", "name": "数据建模", "type": "auto", "confirm_required": False},
            {"id": "4.2", "name": "映射设计", "type": "auto", "confirm_required": False},
            {"id": "4.3", "name": "流程管理（创建/关联/调度）", "type": "auto", "confirm_required": False},
        ],
    },
    {
        "step_order": 5,
        "stage": "monitoring",
        "name": "执行状态实时跟踪与可视化展示",
        "description": "接收下游进度/日志，同步给前端，写入审计记录",
        "automation": "auto",
        "operations": [
            {"id": "5.1", "name": "接收进度与日志", "type": "auto", "confirm_required": False},
        ],
    },
    {
        "step_order": 6,
        "stage": "error_handling",
        "name": "异常处理与故障恢复",
        "description": "分级异常处理：网络重试、参数补全、系统熔断；提供人工干预入口",
        "automation": "semi-auto",
        "optional": True,
        "operations": [
            {"id": "6.1", "name": "识别并分类异常", "type": "auto", "confirm_required": False},
            {"id": "6.2", "name": "自动重试 / 人工修复", "type": "semi-auto", "confirm_required": True},
        ],
    },
    {
        "step_order": 7,
        "stage": "testing",
        "name": "任务测试与结果验证",
        "description": "连通性、数据准确性、调度有效性校验",
        "automation": "auto",
        "operations": [
            {"id": "7.1", "name": "连通性校验", "type": "auto", "confirm_required": False},
            {"id": "7.2", "name": "数据准确性抽查", "type": "auto", "confirm_required": False},
            {"id": "7.3", "name": "生成任务执行报告", "type": "auto", "confirm_required": False},
        ],
    },
    {
        "step_order": 8,
        "stage": "online",
        "name": "任务上线与调度运维",
        "description": "按配置上线与定时调度，持续监控",
        "automation": "auto",
        "operations": [
            {"id": "8.1", "name": "上线并注册调度", "type": "auto", "confirm_required": False},
        ],
    },
]


STAGE_ORDER = [t["stage"] for t in STATIC_STAGE_TEMPLATES]


def build_initial_steps() -> List[Dict[str, Any]]:
    """返回可持久化为 FlowStep.sub_steps 的模板副本。"""
    return [
        {
            **t,
            "operations": [{**op, "status": "pending"} for op in t["operations"]],
        }
        for t in STATIC_STAGE_TEMPLATES
    ]

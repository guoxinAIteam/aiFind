"""MCP 工具：unicom_ai_parse_collection_requirement。

对齐技术方案 Table 0，把上游 AI 解析智能体封装为 MCP 标准工具。
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict

from backend.services.mcp.registry import ToolSpec, registry
from backend.services.upstream import (
    UnicomParseClient,
    UnicomParseConfig,
    UnicomParseError,
    extract_structured_result,
)


TOOL_NAME = "unicom_ai_parse_collection_requirement"


INPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["requirement"],
    "properties": {
        "requirement": {"type": "string", "description": "采集需求 / 接口规范文本"},
        "user_name": {"type": "string", "default": "aiFind"},
        "conversation_id": {"type": "string"},
    },
}


OUTPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "content": {"type": "string"},
        "structured": {"type": "object"},
        "conversation_id": {"type": "string"},
        "message_id": {"type": "string"},
        "latency_ms": {"type": "integer"},
    },
}


def _mock_on() -> bool:
    return os.environ.get("UNICOM_MOCK", "").strip().lower() in {"1", "true", "yes"}


def _mock_call(args: Dict[str, Any]) -> Dict[str, Any]:
    structured = {
        "source_info": {
            "source_code": "sftp_cb_224",
            "source_file_path": "/sftp/data/src_ai_caiji",
            "source_row_split_char": "UNIX换行符",
            "source_col_split_char": "逗号",
            "source_ext": "gz",
        },
        "target_info": {
            "target_code": "305实时数仓集群_hive",
            "target_database_name": "paimon_src",
            "table_name": "src_ai_caiji",
        },
        "task_base_info": {
            "logic_dir": "治理监控测试",
            "logic_project": "经分",
            "logic_data_level": "SRC",
            "logic_topic_name": "CUS(客户域)",
            "logic_type": "5G",
            "physical_dir": "测试目录",
        },
    }
    return {
        "content": json.dumps(structured, ensure_ascii=False),
        "structured": structured,
        "conversation_id": "mock-conv",
        "message_id": "mock-msg",
        "latency_ms": 0,
        "_mock": True,
    }


def _handler(args: Dict[str, Any]) -> Dict[str, Any]:
    requirement = str(args.get("requirement") or "").strip()
    if not requirement:
        raise ValueError("requirement 必填")
    if _mock_on():
        return _mock_call(args)
    try:
        client = UnicomParseClient(UnicomParseConfig.from_env(require=True))
    except UnicomParseError as e:
        raise RuntimeError(f"上游配置不全: {e}") from e
    result = client.invoke(
        requirement,
        user_name=str(args.get("user_name") or "aiFind"),
        conversation_id=args.get("conversation_id"),
    )
    structured = result.structured or extract_structured_result(result.content)
    return {
        "content": result.content,
        "structured": structured,
        "conversation_id": result.conversation_id,
        "message_id": result.message_id,
        "latency_ms": result.latency_ms,
    }


registry.register(
    ToolSpec(
        name=TOOL_NAME,
        description="调用联通能开 AI 解析智能体，从需求/接口规范中抽取结构化参数",
        direction="upstream",
        input_schema=INPUT_SCHEMA,
        output_schema=OUTPUT_SCHEMA,
        handler=_handler,
        rate_limit_per_min=60,
        auth_required=True,
    ),
    replace=True,
)

"""MCP 工具：BDI 全流程 / 4 个原子工具。

对齐技术方案 Table 1 + docs/BDI入参说明及执行流程.docx 的 4 核心步骤。
"""
from __future__ import annotations

from typing import Any, Dict

from backend.services.downstream import (
    BdiClient,
    BdiClientConfig,
    BdiClientError,
    BdiParams,
)
from backend.services.mcp.registry import ToolSpec, registry


BDI_INPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": list(BdiParams.model_fields.keys()),
    "properties": {
        name: {"type": "string", "description": (field.description or "")}
        for name, field in BdiParams.model_fields.items()
    },
}


BDI_OUTPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "code": {"type": "integer"},
        "message": {"type": "string"},
        "full_status": {"type": "string"},
        "task_detail": {"type": "object"},
        "execute_log": {"type": "array"},
    },
}


def _build_params(args: Dict[str, Any]) -> BdiParams:
    try:
        return BdiParams(**args)
    except Exception as e:  # ValidationError 也归并 RuntimeError
        raise ValueError(f"BDI 入参校验失败: {e}") from e


def _response(resp) -> Dict[str, Any]:
    return {
        "code": resp.code,
        "message": resp.message,
        "full_status": resp.full_status,
        "task_detail": resp.task_detail,
        "execute_log": resp.execute_log,
        "latency_ms": resp.latency_ms,
    }


def _handle_full(args: Dict[str, Any]) -> Dict[str, Any]:
    params = _build_params(args)
    client = BdiClient(BdiClientConfig.from_env())
    try:
        resp = client.call_full_process(params)
    except BdiClientError as e:
        raise RuntimeError(str(e)) from e
    return _response(resp)


def _handle_atom(method_name: str):
    def _inner(args: Dict[str, Any]) -> Dict[str, Any]:
        params = _build_params(args)
        client = BdiClient(BdiClientConfig.from_env())
        method = getattr(client, method_name)
        try:
            resp = method(params)
        except BdiClientError as e:
            raise RuntimeError(str(e)) from e
        return _response(resp)

    return _inner


_ATOMIC_TOOLS = [
    (
        "bdi_resource_register",
        "BDI 资源注册：在下游智能体为数据源/目标登记连接器（现阶段可忽略，兼容保留）",
        "call_resource_register",
    ),
    (
        "bdi_data_modeling",
        "BDI 数据建模：基于入参反向建模生成逻辑/物理模型",
        "call_data_modeling",
    ),
    (
        "bdi_mapping_design",
        "BDI 映射设计：生成源-目标字段映射",
        "call_mapping_design",
    ),
    (
        "bdi_flow_management",
        "BDI 流程管理：创建/关联采集流程并调度",
        "call_flow_management",
    ),
]


registry.register(
    ToolSpec(
        name="bdi_full_process_execution",
        description="BDI 全流程一键执行：数据建模 → 映射设计 → 流程管理",
        direction="downstream",
        input_schema=BDI_INPUT_SCHEMA,
        output_schema=BDI_OUTPUT_SCHEMA,
        handler=_handle_full,
        rate_limit_per_min=30,
        auth_required=True,
    ),
    replace=True,
)

for tool_name, desc, method_name in _ATOMIC_TOOLS:
    registry.register(
        ToolSpec(
            name=tool_name,
            description=desc,
            direction="downstream",
            input_schema=BDI_INPUT_SCHEMA,
            output_schema=BDI_OUTPUT_SCHEMA,
            handler=_handle_atom(method_name),
            rate_limit_per_min=60,
            auth_required=True,
        ),
        replace=True,
    )

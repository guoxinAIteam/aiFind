"""BDI 离线采集执行智能体客户端。

严格对齐 docs/BDI入参说明及执行流程.docx：
- 核心步骤：资源注册 -> 数据建模 -> 映射设计 -> 流程管理
- 16 个关键入参字段：key、skill_name、logic_dir、logic_project、
  logic_data_level、logic_topic_name、logic_type、source_code、
  source_file_path、source_row_split_char、source_col_split_char、
  source_ext、target_code、target_database_name、physical_dir、table_name
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ----- 枚举约束（基于 docs 示例与说明梳理，未列举的值视为 warning） -------------

LOGIC_DATA_LEVELS = ("SRC", "STG", "ODS", "DWD", "DWS", "APP")
ROW_SPLIT_CHARS = ("UNIX换行符", "WINDOWS换行符", "自定义")
COL_SPLIT_CHARS = ("逗号", "制表符", "竖线", "分号", "0x01", "自定义")


class BdiClientError(RuntimeError):
    """下游调用异常。"""


# ----- 入参模型 ---------------------------------------------------------------


class BdiParams(BaseModel):
    """BDI 全流程入参，完全匹配 docs/BDI入参说明及执行流程.docx。"""

    key: str = Field(..., description="权限校验密钥")
    skill_name: str = Field(..., description="调用 skill 的名称")
    logic_dir: str = Field(..., description="逻辑设计器存放目录")
    logic_project: str = Field(..., description="逻辑设计器对应项目")
    logic_data_level: str = Field(..., description="数据分层，如 SRC")
    logic_topic_name: str = Field(..., description="逻辑设计器主题域")
    logic_type: str = Field(..., description="逻辑设计业务分类")
    source_code: str = Field(..., description="源端连接器编码")
    source_file_path: str = Field("", description="源端 SFTP 目录")
    source_row_split_char: str = Field(..., description="源端文件行间分隔符")
    source_col_split_char: str = Field(..., description="源端文件字段分隔符")
    source_ext: str = Field(..., description="源端文件后缀，不带点")
    target_code: str = Field(..., description="目标端连接器编码")
    target_database_name: str = Field(..., description="目标端数据库名称")
    physical_dir: str = Field(..., description="所有物理设计器存放目录")
    table_name: str = Field(..., description="表名称")

    @field_validator("source_ext")
    @classmethod
    def _strip_leading_dot(cls, v: str) -> str:
        if v and v.startswith("."):
            raise ValueError("source_ext 不应带点，例如填 gz，不要填 .gz")
        return v

    @field_validator(
        "key",
        "skill_name",
        "logic_dir",
        "logic_project",
        "logic_data_level",
        "logic_topic_name",
        "logic_type",
        "source_code",
        "source_row_split_char",
        "source_col_split_char",
        "source_ext",
        "target_code",
        "target_database_name",
        "physical_dir",
        "table_name",
    )
    @classmethod
    def _non_blank(cls, v: str, info: Any) -> str:
        if not isinstance(v, str) or not v.strip():
            field_name = getattr(info, "field_name", "字段")
            raise ValueError(f"{field_name} 必填且不能为空字符串")
        return v.strip()

    def check_enums(self) -> List[Dict[str, str]]:
        """返回枚举软约束的 warning 列表（不抛异常，交 UI 展示）。"""
        warnings: List[Dict[str, str]] = []
        if self.logic_data_level not in LOGIC_DATA_LEVELS:
            warnings.append(
                {
                    "field": "logic_data_level",
                    "message": f"非标准数据分层: {self.logic_data_level}，建议 ∈ {LOGIC_DATA_LEVELS}",
                }
            )
        if self.source_row_split_char not in ROW_SPLIT_CHARS:
            warnings.append(
                {
                    "field": "source_row_split_char",
                    "message": f"非标准行分隔符: {self.source_row_split_char}，建议 ∈ {ROW_SPLIT_CHARS}",
                }
            )
        if self.source_col_split_char not in COL_SPLIT_CHARS:
            warnings.append(
                {
                    "field": "source_col_split_char",
                    "message": f"非标准列分隔符: {self.source_col_split_char}，建议 ∈ {COL_SPLIT_CHARS}",
                }
            )
        return warnings

    def to_payload(self) -> Dict[str, Any]:
        """导出供下游 API 的完整入参。"""
        return self.model_dump()


# ----- 客户端响应归一化 -------------------------------------------------------


@dataclass
class BdiResponse:
    code: int
    message: str
    task_detail: Dict[str, Any]
    full_status: str
    execute_log: List[Dict[str, Any]]
    latency_ms: int
    raw: Dict[str, Any]

    @property
    def ok(self) -> bool:
        return int(self.code) == 0


# ----- 客户端配置 -------------------------------------------------------------


@dataclass
class BdiClientConfig:
    base_url: str = ""
    key: str = ""
    skill_name: str = "接口规范-sftp-数据库-realease.skill"
    timeout_s: float = 120.0
    mock: bool = False

    @classmethod
    def from_env(cls) -> "BdiClientConfig":
        mock = os.environ.get("BDI_MOCK", "").strip().lower() in {"1", "true", "yes"}
        return cls(
            base_url=os.environ.get("BDI_BASE_URL", "").strip(),
            key=os.environ.get("BDI_KEY", "").strip(),
            skill_name=os.environ.get(
                "BDI_SKILL_NAME", "接口规范-sftp-数据库-realease.skill"
            ).strip(),
            timeout_s=float(os.environ.get("BDI_TIMEOUT_S", "120")),
            mock=mock,
        )


# ----- 客户端 -----------------------------------------------------------------


class BdiClient:
    """BDI 智能体 HTTP 客户端。

    原子工具：call_resource_register / call_data_modeling /
    call_mapping_design / call_flow_management；
    组合工具：call_full_process（一键全流程）。
    """

    # 原子路径（真实联调前保持可覆盖）
    PATH_RESOURCE_REGISTER = "/api/bdi/resource/register"
    PATH_DATA_MODELING = "/api/bdi/data/modeling"
    PATH_MAPPING_DESIGN = "/api/bdi/mapping/design"
    PATH_FLOW_MANAGEMENT = "/api/bdi/flow/management"
    PATH_FULL_PROCESS = "/api/bdi/full-process"

    def __init__(self, config: Optional[BdiClientConfig] = None):
        self.config = config or BdiClientConfig.from_env()

    # --- 原子调用 -------------------------------------------------------------

    def call_resource_register(self, params: BdiParams) -> BdiResponse:
        return self._call(self.PATH_RESOURCE_REGISTER, params, step="resource_register")

    def call_data_modeling(self, params: BdiParams) -> BdiResponse:
        return self._call(self.PATH_DATA_MODELING, params, step="data_modeling")

    def call_mapping_design(self, params: BdiParams) -> BdiResponse:
        return self._call(self.PATH_MAPPING_DESIGN, params, step="mapping_design")

    def call_flow_management(self, params: BdiParams) -> BdiResponse:
        return self._call(self.PATH_FLOW_MANAGEMENT, params, step="flow_management")

    # --- 组合调用 -------------------------------------------------------------

    def call_full_process(self, params: BdiParams) -> BdiResponse:
        return self._call(self.PATH_FULL_PROCESS, params, step="full_process")

    # --- 内部实现 -------------------------------------------------------------

    def _call(self, path: str, params: BdiParams, *, step: str) -> BdiResponse:
        payload = params.to_payload()
        started = time.monotonic()

        if self.config.mock or not self.config.base_url:
            return self._mock_response(step, payload, started)

        url = self.config.base_url.rstrip("/") + path
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout_s) as resp:
                raw_bytes = resp.read()
        except urllib.error.HTTPError as e:
            raise BdiClientError(
                f"BDI HTTP {e.code} {e.reason}: "
                f"{e.read().decode('utf-8', 'replace')[:500]}"
            ) from e
        except urllib.error.URLError as e:
            raise BdiClientError(f"BDI 调用失败 ({url}): {e}") from e

        text = raw_bytes.decode("utf-8", errors="replace")
        try:
            obj = json.loads(text)
        except ValueError as e:
            raise BdiClientError(f"BDI 响应非 JSON: {text[:500]}") from e
        latency_ms = int((time.monotonic() - started) * 1000)
        return _normalize_response(obj, latency_ms)

    def _mock_response(
        self, step: str, payload: Dict[str, Any], started: float
    ) -> BdiResponse:
        table = payload.get("table_name", "unknown")
        raw = {
            "code": 0,
            "message": f"[MOCK] {step} 执行成功",
            "data": {
                "task_detail": {
                    "task_id": f"bdi_mock_{step}_{table}",
                    "flow_id": f"flow_{table}",
                    "mapping_id": f"mapping_{table}",
                    "model_id": f"model_{table}",
                    "step": step,
                },
                "full_status": "succeeded",
                "execute_log": [
                    {"step": step, "status": "ok", "message": f"[MOCK] {step} 完成"},
                ],
            },
        }
        return _normalize_response(raw, int((time.monotonic() - started) * 1000))


def _normalize_response(obj: Dict[str, Any], latency_ms: int) -> BdiResponse:
    data = obj.get("data") if isinstance(obj, dict) else None
    data = data if isinstance(data, dict) else {}
    task_detail = data.get("task_detail")
    task_detail = task_detail if isinstance(task_detail, dict) else {}
    execute_log = data.get("execute_log")
    execute_log = execute_log if isinstance(execute_log, list) else []
    full_status = str(data.get("full_status") or obj.get("full_status") or "unknown")
    return BdiResponse(
        code=int(obj.get("code", -1)),
        message=str(obj.get("message", "")),
        task_detail=task_detail,
        full_status=full_status,
        execute_log=execute_log,
        latency_ms=latency_ms,
        raw=obj if isinstance(obj, dict) else {"raw": obj},
    )

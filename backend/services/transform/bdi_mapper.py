"""上游 AI 解析结果 -> 下游 BDI 全流程入参。

使用默认值策略（source_row_split_char=UNIX换行符、col=逗号 等），
无法确定的字段通过 MappingResult.missing 报出，交由前端引导用户补全。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from backend.services.downstream.bdi_client import BdiParams


@dataclass
class MappingIssue:
    field_path: str
    reason: str


@dataclass
class MappingResult:
    params: Optional[BdiParams]
    payload: Dict[str, Any]
    missing: List[MappingIssue] = field(default_factory=list)
    warnings: List[Dict[str, str]] = field(default_factory=list)
    used_defaults: Dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.params is not None and not self.missing


# 字段缺省策略：在无法从上游解析得到时使用
DEFAULT_SOURCE_ROW_SPLIT_CHAR = "UNIX换行符"
DEFAULT_SOURCE_COL_SPLIT_CHAR = "逗号"
DEFAULT_SOURCE_EXT = "gz"


def default_bdi_values() -> Dict[str, Any]:
    """提供一组"开箱即用"的默认值（不覆盖必须由用户 / 上游提供的字段）。"""
    return {
        "key": os.environ.get("BDI_KEY", "").strip(),
        "skill_name": os.environ.get(
            "BDI_SKILL_NAME", "接口规范-sftp-数据库-realease.skill"
        ).strip(),
        "source_row_split_char": DEFAULT_SOURCE_ROW_SPLIT_CHAR,
        "source_col_split_char": DEFAULT_SOURCE_COL_SPLIT_CHAR,
        "source_ext": DEFAULT_SOURCE_EXT,
        "source_file_path": "",
    }


def _get(obj: Dict[str, Any], path: str) -> Any:
    cur: Any = obj
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


_SOURCE_FIELD_MAP = {
    "source_code": "source_info.source_code",
    "source_file_path": "source_info.source_file_path",
    "source_row_split_char": "source_info.source_row_split_char",
    "source_col_split_char": "source_info.source_col_split_char",
    "source_ext": "source_info.source_ext",
}

_TARGET_FIELD_MAP = {
    "target_code": "target_info.target_code",
    "target_database_name": "target_info.target_database_name",
    "table_name": "target_info.table_name",
}

_TASK_FIELD_MAP = {
    "logic_dir": "task_base_info.logic_dir",
    "logic_project": "task_base_info.logic_project",
    "logic_data_level": "task_base_info.logic_data_level",
    "logic_topic_name": "task_base_info.logic_topic_name",
    "logic_type": "task_base_info.logic_type",
    "physical_dir": "task_base_info.physical_dir",
}


def upstream_to_bdi(
    structured: Dict[str, Any],
    *,
    overrides: Optional[Dict[str, Any]] = None,
) -> MappingResult:
    """把上游 extract_structured_result 返回的字典映射为 BDI 入参。

    overrides 优先级：overrides > upstream > defaults。
    """
    defaults = default_bdi_values()
    used_defaults: Dict[str, Any] = {}
    payload: Dict[str, Any] = {}

    # 1) 先填缺省
    payload.update(defaults)
    for k, v in defaults.items():
        if v:
            used_defaults[k] = v

    # 2) 上游字段映射
    for field_name, path in (
        *_SOURCE_FIELD_MAP.items(),
        *_TARGET_FIELD_MAP.items(),
        *_TASK_FIELD_MAP.items(),
    ):
        value = _get(structured, path)
        if value not in (None, "", [], {}):
            payload[field_name] = value
            # 若上游提供了值，解除 used_defaults 标记
            used_defaults.pop(field_name, None)

    # 3) 用户覆盖
    if overrides:
        for k, v in overrides.items():
            if v in (None, "", [], {}):
                continue
            payload[k] = v
            used_defaults.pop(k, None)

    # 4) 缺失字段检查（基于 BdiParams 的必填列表）
    missing: List[MappingIssue] = []
    for field_name in (
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
    ):
        if not payload.get(field_name):
            missing.append(MappingIssue(field_path=field_name, reason=_field_reason(field_name)))

    params: Optional[BdiParams] = None
    warnings: List[Dict[str, str]] = []
    if not missing:
        try:
            params = BdiParams(**payload)
            warnings = params.check_enums()
        except ValidationError as ve:
            # 降级：把校验失败也作为 missing 呈现给前端
            for err in ve.errors():
                loc = err.get("loc", ())
                missing.append(
                    MappingIssue(
                        field_path=".".join(str(x) for x in loc),
                        reason=err.get("msg", "参数非法"),
                    )
                )

    return MappingResult(
        params=params,
        payload=payload,
        missing=missing,
        warnings=warnings,
        used_defaults=used_defaults,
    )


def apply_user_supplement(
    payload: Dict[str, Any], values: Dict[str, Any]
) -> Dict[str, Any]:
    """将用户补全结果合并进 payload，忽略空值。"""
    out = dict(payload or {})
    for k, v in (values or {}).items():
        if v in (None, "", [], {}):
            continue
        out[k] = v
    return out


_REASON_MAP: Dict[str, str] = {
    "key": "权限校验密钥，通常由管理员配置",
    "skill_name": "调用 skill 的名称",
    "logic_dir": "逻辑设计器目录（项目限定可选）",
    "logic_project": "逻辑设计器对应项目",
    "logic_data_level": "数据分层，如 SRC/ODS/DWD",
    "logic_topic_name": "逻辑设计器主题域",
    "logic_type": "业务分类，如 5G、客户域",
    "source_code": "源端连接器编码，如 sftp_cb_224",
    "source_file_path": "源端 SFTP 目录",
    "source_row_split_char": "源端文件行间分隔符",
    "source_col_split_char": "源端文件字段分隔符",
    "source_ext": "源端文件后缀，不带点",
    "target_code": "目标端连接器编码",
    "target_database_name": "目标端数据库名称",
    "physical_dir": "所有物理设计器存放目录",
    "table_name": "表名称",
}


def _field_reason(name: str) -> str:
    return _REASON_MAP.get(name, name)

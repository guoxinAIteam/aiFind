"""阶段二：BDI 入参模型 + 映射器 单测。"""
import pytest

from backend.services.downstream.bdi_client import (
    BdiClient,
    BdiClientConfig,
    BdiParams,
    COL_SPLIT_CHARS,
    LOGIC_DATA_LEVELS,
    ROW_SPLIT_CHARS,
)
from backend.services.transform.bdi_mapper import (
    MappingResult,
    apply_user_supplement,
    upstream_to_bdi,
)


FULL_STRUCTURED = {
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


def test_bdi_params_rejects_leading_dot_on_ext():
    with pytest.raises(Exception):
        BdiParams(
            key="k",
            skill_name="s",
            logic_dir="d",
            logic_project="p",
            logic_data_level="SRC",
            logic_topic_name="t",
            logic_type="l",
            source_code="c",
            source_file_path="",
            source_row_split_char="UNIX换行符",
            source_col_split_char="逗号",
            source_ext=".gz",
            target_code="tc",
            target_database_name="db",
            physical_dir="pd",
            table_name="tb",
        )


def test_bdi_params_enum_warnings_soft():
    p = BdiParams(
        key="k",
        skill_name="s",
        logic_dir="d",
        logic_project="p",
        logic_data_level="CUSTOM",  # 非标准
        logic_topic_name="t",
        logic_type="l",
        source_code="c",
        source_file_path="",
        source_row_split_char="UNIX换行符",
        source_col_split_char="逗号",
        source_ext="gz",
        target_code="tc",
        target_database_name="db",
        physical_dir="pd",
        table_name="tb",
    )
    warnings = p.check_enums()
    assert any(w["field"] == "logic_data_level" for w in warnings)
    # 合法枚举不产生 warning
    assert all(w["field"] != "source_row_split_char" for w in warnings)
    assert "UNIX换行符" in ROW_SPLIT_CHARS
    assert "逗号" in COL_SPLIT_CHARS
    assert "SRC" in LOGIC_DATA_LEVELS


def test_upstream_to_bdi_full_mapping(monkeypatch):
    monkeypatch.setenv("BDI_KEY", "test_key_123")
    result = upstream_to_bdi(FULL_STRUCTURED)
    assert isinstance(result, MappingResult)
    assert result.ok, result.missing
    p = result.params
    assert p is not None
    assert p.source_code == "sftp_cb_224"
    assert p.target_database_name == "paimon_src"
    assert p.logic_data_level == "SRC"
    assert p.key == "test_key_123"


def test_upstream_to_bdi_missing_fields(monkeypatch):
    monkeypatch.delenv("BDI_KEY", raising=False)
    partial = {"source_info": {"source_code": "sftp_cb_224"}}
    result = upstream_to_bdi(partial)
    assert not result.ok
    missing_paths = {m.field_path for m in result.missing}
    # key 来自 env，未设置 -> 必缺失
    assert "key" in missing_paths
    assert "target_code" in missing_paths
    assert "table_name" in missing_paths


def test_upstream_to_bdi_overrides_win():
    overrides = {"key": "override_key", "logic_dir": "override_dir"}
    result = upstream_to_bdi(FULL_STRUCTURED, overrides=overrides)
    assert result.params is not None
    assert result.params.key == "override_key"
    assert result.params.logic_dir == "override_dir"


def test_apply_user_supplement_ignores_blanks():
    base = {"a": 1, "b": 2}
    got = apply_user_supplement(base, {"b": "", "c": "v", "d": None})
    assert got == {"a": 1, "b": 2, "c": "v"}


def test_bdi_client_mock_full_process(monkeypatch):
    monkeypatch.setenv("BDI_KEY", "k")
    result = upstream_to_bdi(FULL_STRUCTURED)
    assert result.params is not None
    client = BdiClient(BdiClientConfig(mock=True))
    resp = client.call_full_process(result.params)
    assert resp.ok
    assert resp.task_detail["task_id"].startswith("bdi_mock_full_process")
    assert resp.execute_log and resp.execute_log[0]["status"] == "ok"


def test_bdi_client_mock_atomic_steps(monkeypatch):
    monkeypatch.setenv("BDI_KEY", "k")
    result = upstream_to_bdi(FULL_STRUCTURED)
    client = BdiClient(BdiClientConfig(mock=True))
    for call in (
        client.call_resource_register,
        client.call_data_modeling,
        client.call_mapping_design,
        client.call_flow_management,
    ):
        resp = call(result.params)  # type: ignore[arg-type]
        assert resp.ok
        assert resp.full_status == "succeeded"

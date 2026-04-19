"""阶段一：上游 MD5 签名 + 响应解析单测。"""
import hashlib

import pytest

from backend.services.upstream.unicom_parser import (
    build_access_token,
    extract_structured_result,
    _extract_response_content,
    _parse_sse_line,
)


def test_build_access_token_matches_java_spec():
    """拼接顺序必须与 docs/AIAgent.java generateAccessToken 完全一致。"""
    args = dict(
        app_id="654803172359757824",
        team_id="1724420775949",
        sk="sk-4HPjzYrCp1IMcoUSMgKlxU1AYpmonifn30neYNJXDbw",
        conversation_id="convId123",
        message_id="msgId123",
        timestamp="20260419000000",
        content="hello world",
    )
    tok = build_access_token(**args)
    expected = hashlib.md5(
        (
            args["app_id"]
            + args["timestamp"]
            + args["team_id"]
            + args["sk"]
            + args["team_id"]
            + args["conversation_id"]
            + args["message_id"]
            + args["content"]
        ).encode("utf-8")
    ).hexdigest()
    assert tok == expected
    assert len(tok) == 32


def test_build_access_token_rejects_missing_fields():
    with pytest.raises(Exception):
        build_access_token(
            app_id="",
            team_id="t",
            sk="k",
            conversation_id="c",
            message_id="m",
            timestamp="ts",
            content="x",
        )


def test_extract_structured_result_from_fenced_json():
    text = """
思考过程：看起来是 CBSS 场景。
```json
{"source_info":{"source_code":"sftp_cb_224"},"table_structure":[{"name":"c1"}]}
```
"""
    got = extract_structured_result(text)
    assert got["source_info"]["source_code"] == "sftp_cb_224"
    assert got["table_structure"] == [{"name": "c1"}]


def test_extract_structured_result_from_nested_data():
    text = '{"data": {"source_info": {"source_code": "x"}, "table_structure": [{"n": 1}]}}'
    got = extract_structured_result(text)
    assert got["source_info"] == {"source_code": "x"}
    assert got["table_structure"] == [{"n": 1}]


def test_extract_response_content_from_envelope():
    raw = '{"data": {"result": {"content": "hello"}}}'
    assert _extract_response_content(raw) == "hello"


def test_parse_sse_line_skips_done():
    assert _parse_sse_line("data: [DONE]") is None
    assert _parse_sse_line("") is None


def test_parse_sse_line_extracts_content_envelope():
    got = _parse_sse_line('data: {"data": {"result": {"content": "abc"}}}')
    assert got == "abc"

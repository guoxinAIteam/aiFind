"""联通能开 AI 解析智能体客户端。

对齐 docs/AIAgent.java：
- MD5 签名：md5(appId + timestamp + teamId + sk + teamId + conversationId + messageId + content)
- timestamp 格式：yyyyMMddHHmmss，60 秒窗口
- 请求：POST JSON，stream 控制流式返回
- 响应：核心提取 data.result.content 中的结构化参数
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional


DEFAULT_UNICOM_API_URL = "https://ai-agent.chinaunicom.cn/uia/api/robot/chat/stream/v1"


class UnicomParseError(RuntimeError):
    """上游解析调用失败。"""


@dataclass
class UnicomParseConfig:
    """调用联通 AI 智能体所需的凭据与端点配置。"""

    app_id: str
    team_id: str
    sk: str
    api_url: str = DEFAULT_UNICOM_API_URL
    timeout_s: float = 60.0

    @classmethod
    def from_env(cls, *, require: bool = False) -> "UnicomParseConfig":
        app_id = os.environ.get("UNICOM_APP_ID", "").strip()
        team_id = os.environ.get("UNICOM_TEAM_ID", "").strip()
        sk = os.environ.get("UNICOM_SK", "").strip()
        api_url = os.environ.get("UNICOM_API_URL", DEFAULT_UNICOM_API_URL).strip()
        timeout_s = float(os.environ.get("UNICOM_TIMEOUT_S", "60"))
        if require and not (app_id and team_id and sk):
            missing = [
                name
                for name, v in (
                    ("UNICOM_APP_ID", app_id),
                    ("UNICOM_TEAM_ID", team_id),
                    ("UNICOM_SK", sk),
                )
                if not v
            ]
            raise UnicomParseError(
                f"缺少上游调用环境变量: {', '.join(missing)}"
            )
        return cls(app_id=app_id, team_id=team_id, sk=sk, api_url=api_url, timeout_s=timeout_s)


def _md5_hex(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def build_access_token(
    *,
    app_id: str,
    team_id: str,
    sk: str,
    conversation_id: str,
    message_id: str,
    timestamp: str,
    content: str,
) -> str:
    """与 docs/AIAgent.java 的 generateAccessToken 完全等价。"""
    for name, val in (
        ("timestamp", timestamp),
        ("content", content),
        ("appId", app_id),
        ("teamId", team_id),
        ("conversationId", conversation_id),
        ("messageId", message_id),
        ("sk", sk),
    ):
        if not val:
            raise UnicomParseError(f"上游签名缺少必填字段: {name}")
    raw = (
        app_id
        + timestamp
        + team_id
        + sk
        + team_id
        + conversation_id
        + message_id
        + content
    )
    return _md5_hex(raw)


def _make_timestamp(now: Optional[datetime] = None) -> str:
    now = now or datetime.now()
    return now.strftime("%Y%m%d%H%M%S")


def _make_conversation_id() -> str:
    """建议 uuid、长度 30，保持唯一。"""
    return uuid.uuid4().hex[:30]


def _make_message_id() -> str:
    return uuid.uuid4().hex[:30]


@dataclass
class UnicomParseResult:
    """上游解析归一化结果。"""

    content: str = ""
    structured: Dict[str, Any] = field(default_factory=dict)
    raw_response: str = ""
    conversation_id: str = ""
    message_id: str = ""
    latency_ms: int = 0
    chunks: List[str] = field(default_factory=list)

    @property
    def source_info(self) -> Dict[str, Any]:
        return dict(self.structured.get("source_info", {}) or {})

    @property
    def target_info(self) -> Dict[str, Any]:
        return dict(self.structured.get("target_info", {}) or {})

    @property
    def ftp_info(self) -> Dict[str, Any]:
        return dict(self.structured.get("ftp_info", {}) or {})

    @property
    def task_base_info(self) -> Dict[str, Any]:
        return dict(self.structured.get("task_base_info", {}) or {})

    @property
    def table_structure(self) -> List[Dict[str, Any]]:
        ts = self.structured.get("table_structure") or []
        return [dict(x) for x in ts if isinstance(x, dict)]


# ----- 结构化结果抽取 -----------------------------------------------------------

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _try_parse_json(text: str) -> Optional[Any]:
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return None


def _find_first_json_object(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    # 1) markdown 代码围栏内
    m = _JSON_FENCE_RE.search(text)
    if m:
        parsed = _try_parse_json(m.group(1))
        if isinstance(parsed, dict):
            return parsed
    # 2) 粗暴匹配第一个 "{" 到最后一个 "}"
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        parsed = _try_parse_json(text[start : end + 1])
        if isinstance(parsed, dict):
            return parsed
    return None


def extract_structured_result(content: str) -> Dict[str, Any]:
    """从 data.result.content 抽取标准化参数。

    允许形如：JSON 直出、被 markdown 代码块包裹、或自然语言 + 嵌入 JSON。
    若都无法解析，返回空 dict 交由调用方走缺失补全流程。
    """
    if not isinstance(content, str):
        return {}
    obj = _find_first_json_object(content)
    if not obj:
        return {}
    normalized: Dict[str, Any] = {}
    for key in ("source_info", "target_info", "ftp_info", "task_base_info"):
        v = obj.get(key)
        if isinstance(v, dict):
            normalized[key] = v
    ts = obj.get("table_structure")
    if isinstance(ts, list):
        normalized["table_structure"] = [x for x in ts if isinstance(x, dict)]
    # 兼容大模型返回 {"data": {...}} 结构
    if not normalized and isinstance(obj.get("data"), dict):
        return extract_structured_result(json.dumps(obj["data"], ensure_ascii=False))
    return normalized


# ----- 调用客户端 -------------------------------------------------------------


class UnicomParseClient:
    """上游 AI 解析智能体 HTTP 客户端。

    同步 / 流式两种调用方式。流式以 SSE 风格解析 "data: {...}" 行。
    """

    def __init__(self, config: Optional[UnicomParseConfig] = None):
        self.config = config or UnicomParseConfig.from_env()

    def _build_payload(
        self,
        *,
        content: str,
        user_name: str,
        conversation_id: str,
        message_id: str,
        stream: bool,
    ) -> Dict[str, Any]:
        cfg = self.config
        timestamp = _make_timestamp()
        access_token = build_access_token(
            app_id=cfg.app_id,
            team_id=cfg.team_id,
            sk=cfg.sk,
            conversation_id=conversation_id,
            message_id=message_id,
            timestamp=timestamp,
            content=content,
        )
        return {
            "appId": cfg.app_id,
            "teamId": cfg.team_id,
            "conversationId": conversation_id,
            "messageId": message_id,
            "timestamp": timestamp,
            "content": content,
            "stream": bool(stream),
            "userName": user_name or "aiFind",
            "accessToken": access_token,
        }

    # ----- 同步（stream=False） -------------------------------------------------

    def invoke(
        self,
        content: str,
        *,
        user_name: str = "aiFind",
        conversation_id: Optional[str] = None,
        message_id: Optional[str] = None,
    ) -> UnicomParseResult:
        conv_id = conversation_id or _make_conversation_id()
        msg_id = message_id or _make_message_id()
        payload = self._build_payload(
            content=content,
            user_name=user_name,
            conversation_id=conv_id,
            message_id=msg_id,
            stream=False,
        )
        started = time.monotonic()
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            self.config.api_url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout_s) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            raise UnicomParseError(
                f"上游 HTTP {e.code} {e.reason}: {e.read().decode('utf-8', 'replace')[:500]}"
            ) from e
        except urllib.error.URLError as e:
            raise UnicomParseError(f"上游调用失败: {e}") from e
        latency_ms = int((time.monotonic() - started) * 1000)

        parsed_content = _extract_response_content(raw)
        return UnicomParseResult(
            content=parsed_content,
            structured=extract_structured_result(parsed_content),
            raw_response=raw,
            conversation_id=conv_id,
            message_id=msg_id,
            latency_ms=latency_ms,
            chunks=[parsed_content] if parsed_content else [],
        )

    # ----- 流式（stream=True） -------------------------------------------------

    def stream(
        self,
        content: str,
        *,
        user_name: str = "aiFind",
        conversation_id: Optional[str] = None,
        message_id: Optional[str] = None,
        on_chunk: Optional[Callable[[str], None]] = None,
    ) -> Iterator[Dict[str, Any]]:
        """逐块 yield 增量；最终一条包含 final=True 与聚合结构化结果。"""
        conv_id = conversation_id or _make_conversation_id()
        msg_id = message_id or _make_message_id()
        payload = self._build_payload(
            content=content,
            user_name=user_name,
            conversation_id=conv_id,
            message_id=msg_id,
            stream=True,
        )
        started = time.monotonic()
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            self.config.api_url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
        )
        chunks: List[str] = []
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout_s) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                    piece = _parse_sse_line(line)
                    if piece is None:
                        continue
                    chunks.append(piece)
                    if on_chunk:
                        try:
                            on_chunk(piece)
                        except Exception:  # noqa: BLE001 — 回调不影响主流程
                            pass
                    yield {
                        "type": "chunk",
                        "content": piece,
                        "conversation_id": conv_id,
                        "message_id": msg_id,
                    }
        except urllib.error.HTTPError as e:
            raise UnicomParseError(
                f"上游 HTTP {e.code} {e.reason}: {e.read().decode('utf-8', 'replace')[:500]}"
            ) from e
        except urllib.error.URLError as e:
            raise UnicomParseError(f"上游调用失败: {e}") from e

        full = "".join(chunks)
        latency_ms = int((time.monotonic() - started) * 1000)
        yield {
            "type": "final",
            "final": True,
            "content": full,
            "structured": extract_structured_result(full),
            "conversation_id": conv_id,
            "message_id": msg_id,
            "latency_ms": latency_ms,
        }


def _extract_response_content(raw: str) -> str:
    """兼容多种响应外壳，尽量抽出 data.result.content。"""
    if not raw:
        return ""
    obj = _try_parse_json(raw)
    if obj is None:
        # 某些网关会直接返回 `"k":v, ...`，保留 Java 代码中的宽松解析
        obj = _try_parse_json("{" + raw + "}")
    if not isinstance(obj, dict):
        return raw
    data = obj.get("data")
    if isinstance(data, str):
        data = _try_parse_json(data)
    if isinstance(data, dict):
        result = data.get("result")
        if isinstance(result, str):
            result = _try_parse_json(result) or result
        if isinstance(result, dict):
            content = result.get("content")
            if isinstance(content, str):
                return content
        if isinstance(result, str):
            return result
    content = obj.get("content")
    if isinstance(content, str):
        return content
    return raw


def _parse_sse_line(line: str) -> Optional[str]:
    """SSE 行解析。兼容 `data: {...}` / 纯 JSON 块 / 直接文本。"""
    line = (line or "").strip()
    if not line:
        return None
    if line.startswith("data:"):
        payload = line[5:].strip()
    else:
        payload = line
    if payload in {"[DONE]", "DONE"}:
        return None
    if payload.startswith("{") or payload.startswith("["):
        obj = _try_parse_json(payload)
        if isinstance(obj, dict):
            # 与同步一致：优先提取 data.result.content
            extracted = _extract_response_content(payload)
            return extracted or ""
    return payload


__all__ = [
    "DEFAULT_UNICOM_API_URL",
    "UnicomParseClient",
    "UnicomParseConfig",
    "UnicomParseError",
    "UnicomParseResult",
    "build_access_token",
    "extract_structured_result",
]

import datetime as _dt
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, JSON, Enum as SAEnum
from backend.database import Base

_now = _dt.datetime.utcnow


class CollectTask(Base):
    __tablename__ = "collect_tasks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    table_name = Column(String(200), nullable=False)
    task_type = Column(String(50), default="full+incremental")
    status = Column(String(30), default="pending")
    progress = Column(Integer, default=0)
    current_step = Column(Integer, default=0)
    total_steps = Column(Integer, default=6)
    cluster = Column(String(100), default="hh-fed-sub18")
    namespace = Column(String(200), default="")
    config_snapshot = Column(JSON, default=dict)
    error_message = Column(Text, default="")
    # 静态（离线 BDI）采集场景扩展字段；旧记录默认 "legacy"，保持 6 步模板兼容
    scenario = Column(String(30), default="legacy")
    stage = Column(String(40), default="")
    upstream_conv_id = Column(String(64), default="")
    downstream_task_id = Column(String(100), default="")
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now)


class FlowStep(Base):
    __tablename__ = "flow_steps"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, index=True)
    step_order = Column(Integer)
    name = Column(String(200))
    description = Column(Text, default="")
    sub_steps = Column(JSON, default=list)
    status = Column(String(30), default="pending")
    automation = Column(String(20), default="auto")
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    log = Column(Text, default="")


class ParamTemplate(Base):
    __tablename__ = "param_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    category = Column(String(50))
    table_pattern = Column(String(200), default="*")
    params = Column(JSON, default=dict)
    description = Column(Text, default="")
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class MonitorEvent(Base):
    __tablename__ = "monitor_events"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, index=True, nullable=True)
    event_type = Column(String(50))
    severity = Column(String(20), default="info")
    title = Column(String(300))
    detail = Column(Text, default="")
    source_system = Column(String(50), default="")
    resolved = Column(Integer, default=0)
    created_at = Column(DateTime, default=_now)


class KnowledgeArticle(Base):
    __tablename__ = "knowledge_articles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(300), nullable=False)
    category = Column(String(50))
    tags = Column(String(500), default="")
    content = Column(Text, nullable=False)
    source = Column(String(100), default="manual")
    views = Column(Integer, default=0)
    helpful = Column(Integer, default=0)
    created_at = Column(DateTime, default=_now)


class SystemMetric(Base):
    __tablename__ = "system_metrics"

    id = Column(Integer, primary_key=True, index=True)
    metric_name = Column(String(100))
    metric_value = Column(Float)
    unit = Column(String(30), default="")
    source_system = Column(String(50), default="")
    recorded_at = Column(DateTime, default=_now)


class ParseResult(Base):
    """上游 AI 解析智能体的解析结果落库。

    每次调用上游 API 产生一条记录；task_id 可为空，表示仅解析未绑定任务。
    """

    __tablename__ = "parse_results"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, index=True, nullable=True)
    source = Column(String(30), default="unicom")
    requirement = Column(Text, nullable=False)
    content = Column(Text, default="")
    structured = Column(JSON, default=dict)
    missing_fields = Column(JSON, default=list)
    conversation_id = Column(String(64), default="")
    message_id = Column(String(64), default="")
    latency_ms = Column(Integer, default=0)
    status = Column(String(20), default="succeeded")
    error = Column(Text, default="")
    raw_response = Column(Text, default="")
    created_at = Column(DateTime, default=_now)


class BdiTaskBinding(Base):
    """采集任务与下游 BDI 执行的绑定与状态记录。"""

    __tablename__ = "bdi_task_bindings"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, index=True)
    bdi_task_id = Column(String(100), default="")
    bdi_flow_id = Column(String(100), default="")
    bdi_mapping_id = Column(String(100), default="")
    bdi_model_id = Column(String(100), default="")
    full_status = Column(String(30), default="pending")
    last_step = Column(String(50), default="")
    execute_log = Column(JSON, default=list)
    payload = Column(JSON, default=dict)
    response = Column(JSON, default=dict)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class AgentInvocation(Base):
    """上下游智能体调用全量审计。"""

    __tablename__ = "agent_invocations"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, index=True, nullable=True)
    direction = Column(String(20), default="upstream")  # upstream / downstream
    agent = Column(String(60), default="")
    tool_name = Column(String(100), default="")
    request = Column(JSON, default=dict)
    response = Column(JSON, default=dict)
    status = Column(String(20), default="succeeded")
    error = Column(Text, default="")
    latency_ms = Column(Integer, default=0)
    created_at = Column(DateTime, default=_now)


class MissingField(Base):
    """缺失参数清单与用户补全记录。"""

    __tablename__ = "missing_fields"

    id = Column(Integer, primary_key=True, index=True)
    parse_id = Column(Integer, index=True)
    task_id = Column(Integer, index=True, nullable=True)
    field_path = Column(String(200), nullable=False)
    reason = Column(String(200), default="")
    user_value = Column(Text, default="")
    confirmed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now)

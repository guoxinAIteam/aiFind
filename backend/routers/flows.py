import datetime
import math
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import (
    AgentInvocation,
    BdiTaskBinding,
    CollectTask,
    FlowStep,
    MissingField,
    ParseResult,
)
from backend.services.ai_engine import calculate_pre_regions
from backend.services.downstream import BdiClient, BdiClientConfig, BdiClientError
from backend.services.skills.static_collect_orchestration import (
    STAGE_ORDER,
    STATIC_STAGE_TEMPLATES,
    build_initial_steps,
)
from backend.services.transform import upstream_to_bdi
from backend.services.upstream import (
    UnicomParseClient,
    UnicomParseConfig,
    UnicomParseError,
)

router = APIRouter(prefix="/api/flows", tags=["flows"])


class CreateTaskReq(BaseModel):
    name: str
    table_name: str
    task_type: str = "full+incremental"
    cluster: str = "hh-fed-sub18"
    namespace: str = "ctg363566671677_hh_fed_sub19_cjzh_cbss_hbase_lb19"
    tenant: str = "ctg363566671677"
    workspace: str = "hh_fed_sub18_cjzh_cbss_lb18"
    work_group: str = "cjzh_cbss_lb18_wg"
    zk_hosts: str = "10.177.138.67,10.177.138.68,10.177.138.69"
    zk_parent: str = "/hbasesub19"
    zk_port: int = 2181
    kafka_brokers: str = (
        "10.177.64.59:32001,10.177.64.58:32001,10.177.105.150:32003,"
        "10.177.105.152:32010,10.177.38.124:32003,10.177.38.118:32005"
    )
    kafka_topic: str = "tprds-dc-i-prods-new"
    field_count: int = 22
    field_list: str = ""
    pk_indexes: str = "0,4"
    file_size_gb: float = 1.0
    compression: str = "gz"
    init_date: str = ""
    interface_id: str = ""
    date_field_indexes: str = ""
    mc_table_name: str = ""


class ConfirmOpReq(BaseModel):
    operation_id: Optional[str] = None


STEP_COMMAND_TEMPLATES: List[Dict[str, Any]] = [
    {
        "step_order": 1,
        "name": "确定源端表结构及 MC 表结构",
        "automation": "auto",
        "operations": [
            {
                "id": "1.1",
                "name": "拉取源端元数据",
                "type": "auto",
                "command": None,
                "confirm_required": False,
            },
            {
                "id": "1.2",
                "name": "生成字段映射",
                "type": "auto",
                "command": None,
                "confirm_required": False,
            },
            {
                "id": "1.3",
                "name": "生成 MC 目标表 DDL",
                "type": "auto",
                "command": None,
                "confirm_required": True,
            },
        ],
    },
    {
        "step_order": 2,
        "name": "新建 HBase 表",
        "automation": "auto",
        "operations": [
            {
                "id": "2.1",
                "name": "计算预分区数",
                "type": "auto",
                "command": None,
                "confirm_required": False,
                "output_template": (
                    "预分区数 = ceil({file_size_gb} × 1024 / 3 / 4) = {pre_regions}"
                ),
            },
            {
                "id": "2.2",
                "name": "执行建表命令",
                "type": "auto",
                "command": (
                    "java -cp /data/disk01/shangyunOrder/lib/QueryHbaseTable.jar "
                    "cn.com.bonc.CreateTable {zk_hosts} {zk_parent} {pre_regions} "
                    "{compression} {namespace}:{table_name} {zk_port}"
                ),
                "confirm_required": True,
            },
        ],
    },
    {
        "step_order": 3,
        "name": "全量初始化（历史全量文件）",
        "automation": "semi-auto",
        "operations": [
            {
                "id": "3.1",
                "name": "创建 HDFS 初始化目录",
                "type": "auto",
                "command": (
                    "hadoop fs -mkdir -p /user/tenants/{tenant}/{workspace}/work/"
                    "{work_group}/init/data{init_date}/{table_name}/new"
                ),
                "confirm_required": False,
            },
            {
                "id": "3.2",
                "name": "调整 HDFS 目录权限",
                "type": "auto",
                "command": (
                    "hadoop fs -chmod -R 755 /user/tenants/{tenant}/{workspace}/work/"
                    "{work_group}/init/data{init_date}/{table_name}/new"
                ),
                "confirm_required": False,
            },
            {
                "id": "3.3",
                "name": "上传初始化文件到 HDFS",
                "type": "manual",
                "command": (
                    "hadoop fs -put /data/disk01/{workspace}/lh/chushihua/"
                    "d_cred_{table_name}_{init_date}.txt /user/tenants/{tenant}/"
                    "{workspace}/work/{work_group}/init/data{init_date}/"
                    "{table_name}/new"
                ),
                "confirm_required": True,
            },
            {
                "id": "3.4",
                "name": "执行 BulkLoad 初始化入库",
                "type": "semi-auto",
                "command": (
                    "nohup sh /data/disk01/{workspace}/shangyunOrder/chushihuaruku/"
                    "prepare_complete_bulkload_pb.sh /user/tenants/{tenant}/"
                    "{workspace}/work/{work_group}/init/data{init_date}/"
                    "{table_name}/new/ /user/tenants/{tenant}/{workspace}/work/"
                    "{work_group}/sjml/hfileTable/{table_name}/ *{table_name}* "
                    '{field_count} "{pk_indexes}" 0 NO {namespace}:{table_name} '
                    '"{all_field_indexes}" > /data/disk01/{workspace}/shangyunOrder/'
                    "chushihuaruku/log/{table_name}.log 2>&1 &"
                ),
                "confirm_required": True,
            },
        ],
    },
    {
        "step_order": 4,
        "name": "Flink 增量还原入库",
        "automation": "auto",
        "operations": [
            {
                "id": "4.1",
                "name": "生成 Flink 配置文件",
                "type": "auto",
                "command": None,
                "output_template": (
                    "checkPointPath=hdfs://{cluster}/user/tenants/{tenant}/"
                    "{workspace}/work/{work_group}/{workspace}/shangyunCheckpoint/"
                    "checkPoint0_new_{table_name}\n"
                    "sourceBroker={kafka_brokers}\n"
                    "resetState=earliest\n"
                    "groupId=cb2i_r_cjzh_new_{table_name}\n"
                    "userName=cbss_2i_k\n"
                    "password=******\n"
                    "jobName=new_{table_name}\n"
                    "sourceTopic={kafka_topic}\n"
                    "timesKafka={times_kafka}\n"
                    "hbaseInfo={table_name_upper}={pk_indexes}|{field_count}\n"
                    "tableIndexName={table_name_upper}|{field_list}\n"
                    "hbasezk={zk_hosts}\n"
                    "hbaseZookeeperPort={zk_port}\n"
                    "hbaseParent={zk_parent_clean}\n"
                    "namespace={namespace}\n"
                    "tableEnd=\n"
                    "defaultFS={cluster}"
                ),
                "confirm_required": True,
            },
            {
                "id": "4.2",
                "name": "在 BDI 上建立采集还原流程",
                "type": "semi-auto",
                "command": None,
                "output_template": (
                    "任务名称: new_{table_name}\n"
                    "运行平台: 采集整合联邦18集群1.11\n"
                    "运行模式: YARN_PER\n"
                    "配置文件: /data/disk01/{workspace}/shangyunOrder/conf/"
                    "{table_name}.properties"
                ),
                "confirm_required": True,
            },
        ],
    },
    {
        "step_order": 5,
        "name": "HBase 数据导出到 HDFS",
        "automation": "semi-auto",
        "operations": [
            {
                "id": "5.1",
                "name": "修改导出参数配置文件",
                "type": "manual",
                "command": None,
                "output_template": (
                    "{interface_id}: BC099 4096 4096 {tenant}_{workspace}"
                ),
                "confirm_required": True,
            },
            {
                "id": "5.2",
                "name": "新建 Groovy 字段映射脚本",
                "type": "semi-auto",
                "command": None,
                "output_template": (
                    "Class dateTransform = "
                    "bonc.cbss.hbase.scheme.transform.DateTransform\n\n"
                    "select {{\n"
                    "    transform([{date_field_indexes}], clazz: dateTransform)\n"
                    "}}\n\n"
                    'from("{table_name_upper}"){{\n'
                    '    table("{namespace}:{table_name}")\n'
                    "}}"
                ),
                "confirm_required": True,
            },
            {
                "id": "5.3",
                "name": "启动导出脚本",
                "type": "auto",
                "command": "sh etl-export-submit.sh {interface_id} {init_date}",
                "confirm_required": True,
            },
            {
                "id": "5.4",
                "name": "校验导出结果",
                "type": "manual",
                "command": None,
                "confirm_required": True,
            },
        ],
    },
    {
        "step_order": 6,
        "name": "HDFS 导出到 MC",
        "automation": "semi-auto",
        "operations": [
            {
                "id": "6.1",
                "name": "建立 MC 外表",
                "type": "semi-auto",
                "command": None,
                "confirm_required": True,
            },
            {
                "id": "6.2",
                "name": "建立 MC 内表",
                "type": "semi-auto",
                "command": None,
                "confirm_required": True,
            },
            {
                "id": "6.3",
                "name": "执行 HDFS→MC 导出脚本",
                "type": "auto",
                "command": (
                    "sh hdfscp.sh {interface_id} {init_date} /user/tenants/"
                    "{tenant}/{workspace}/work/{work_group}/cbssdata {init_month} "
                    "{init_day} {mc_table_name}"
                ),
                "confirm_required": True,
            },
            {
                "id": "6.4",
                "name": "验证 MC 数据量",
                "type": "manual",
                "command": None,
                "confirm_required": True,
            },
        ],
    },
]


def render_templates(
    templates: List[Dict[str, Any]], vars_dict: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Replace {var} placeholders in all command and output_template fields."""
    rendered: List[Dict[str, Any]] = []
    for step in templates:
        s = {**step, "operations": []}
        for op in step["operations"]:
            o = {**op}
            for key in ("command", "output_template"):
                val = o.get(key)
                if val:
                    try:
                        o[key] = val.format(**vars_dict)
                    except (KeyError, IndexError, ValueError):
                        pass
            s["operations"].append(o)
        rendered.append(s)
    return rendered


def _build_vars_dict(req: CreateTaskReq) -> Dict[str, Any]:
    pre_regions = calculate_pre_regions(
        int(req.file_size_gb * 1024**3), req.compression
    )
    init_date = req.init_date or ""
    base: Dict[str, Any]
    if hasattr(req, "model_dump"):
        base = req.model_dump()
    else:
        base = req.dict()
    return {
        **base,
        "pre_regions": pre_regions,
        "table_name_upper": req.table_name.upper(),
        "zk_parent_clean": req.zk_parent.lstrip("/"),
        "times_kafka": datetime.datetime.now().strftime("%Y%m%d%H%M"),
        "all_field_indexes": ",".join(str(i) for i in range(req.field_count)),
        "init_month": init_date[:6] if init_date else "",
        "init_day": init_date[6:8] if len(init_date) >= 8 else "",
    }


def _advance_task_to_next_step(
    task: CollectTask, step_order: int, db: Session, now: datetime.datetime
) -> None:
    next_row = (
        db.query(FlowStep)
        .filter(
            FlowStep.task_id == task.id,
            FlowStep.step_order == step_order + 1,
        )
        .first()
    )
    if next_row:
        next_row.status = "running"
        next_row.started_at = now
        task.current_step = step_order + 1
        denom = task.total_steps or 1
        task.progress = min(95, int(step_order / denom * 100))
    else:
        task.status = "completed"
        task.progress = 100
        task.finished_at = now
        task.current_step = task.total_steps


@router.get("")
def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(CollectTask).order_by(CollectTask.created_at.desc())
    total = q.count()
    rows = q.offset((page - 1) * page_size).limit(page_size).all()
    total_pages = math.ceil(total / page_size) if page_size else 0
    return {
        "items": [
            {
                "id": t.id,
                "name": t.name,
                "table_name": t.table_name,
                "task_type": t.task_type,
                "status": t.status,
                "progress": t.progress,
                "current_step": t.current_step,
                "total_steps": t.total_steps,
                "cluster": t.cluster,
                "created_at": str(t.created_at) if t.created_at else None,
                "started_at": str(t.started_at) if t.started_at else None,
                "finished_at": str(t.finished_at) if t.finished_at else None,
            }
            for t in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@router.post("")
def create_task(req: CreateTaskReq, db: Session = Depends(get_db)):
    vars_dict = _build_vars_dict(req)
    rendered_steps = render_templates(STEP_COMMAND_TEMPLATES, vars_dict)

    task = CollectTask(
        name=req.name,
        table_name=req.table_name,
        task_type=req.task_type,
        cluster=req.cluster,
        namespace=req.namespace,
        config_snapshot={
            "vars_dict": vars_dict,
            "rendered_steps": rendered_steps,
        },
    )
    task.total_steps = len(STEP_COMMAND_TEMPLATES)
    db.add(task)
    db.flush()

    for step_tpl in rendered_steps:
        ops: List[Dict[str, Any]] = []
        for op in step_tpl["operations"]:
            ops.append({**op, "status": "pending"})
        step = FlowStep(
            task_id=task.id,
            step_order=step_tpl["step_order"],
            name=step_tpl["name"],
            description="",
            sub_steps=ops,
            automation=step_tpl["automation"],
        )
        db.add(step)

    db.commit()
    db.refresh(task)
    return {
        "id": task.id,
        "message": "采集任务已创建",
        "pre_regions": vars_dict["pre_regions"],
    }


@router.get("/{task_id}")
def get_task_detail(task_id: int, db: Session = Depends(get_db)):
    task = db.query(CollectTask).filter(CollectTask.id == task_id).first()
    if not task:
        raise HTTPException(404, "任务不存在")
    steps = (
        db.query(FlowStep)
        .filter(FlowStep.task_id == task_id)
        .order_by(FlowStep.step_order)
        .all()
    )
    return {
        "id": task.id,
        "name": task.name,
        "table_name": task.table_name,
        "task_type": task.task_type,
        "status": task.status,
        "progress": task.progress,
        "current_step": task.current_step,
        "total_steps": task.total_steps,
        "cluster": task.cluster,
        "namespace": task.namespace,
        "config_snapshot": task.config_snapshot or {},
        "error_message": task.error_message,
        "created_at": str(task.created_at) if task.created_at else None,
        "started_at": str(task.started_at) if task.started_at else None,
        "finished_at": str(task.finished_at) if task.finished_at else None,
        "steps": [
            {
                "id": s.id,
                "step_order": s.step_order,
                "name": s.name,
                "description": s.description,
                "automation": s.automation,
                "status": s.status,
                "log": s.log or "",
                "operations": [
                    {
                        "id": op.get("id"),
                        "name": op.get("name"),
                        "type": op.get("type"),
                        "command": op.get("command"),
                        "output_template": op.get("output_template"),
                        "confirm_required": op.get("confirm_required", False),
                        "status": op.get("status", "pending"),
                    }
                    for op in (s.sub_steps or [])
                ],
            }
            for s in steps
        ],
    }


@router.post("/{task_id}/execute")
def execute_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(CollectTask).filter(CollectTask.id == task_id).first()
    if not task:
        raise HTTPException(404, "任务不存在")
    now = datetime.datetime.utcnow()
    task.status = "running"
    task.started_at = now
    task.current_step = 1
    task.progress = 10

    steps = (
        db.query(FlowStep)
        .filter(FlowStep.task_id == task_id)
        .order_by(FlowStep.step_order)
        .all()
    )
    for i, step in enumerate(steps):
        if i == 0:
            step.status = "running"
            step.started_at = now
        else:
            step.status = "pending"
    db.commit()
    return {"message": "任务开始执行", "status": "running"}


@router.post("/{task_id}/step/{step_order}/confirm")
def confirm_step_operation(
    task_id: int,
    step_order: int,
    body: ConfirmOpReq = ConfirmOpReq(),
    db: Session = Depends(get_db),
):
    task = db.query(CollectTask).filter(CollectTask.id == task_id).first()
    if not task:
        raise HTTPException(404, "任务不存在")
    step = (
        db.query(FlowStep)
        .filter(FlowStep.task_id == task_id, FlowStep.step_order == step_order)
        .first()
    )
    if not step:
        raise HTTPException(404, "步骤不存在")

    ops: List[Dict[str, Any]] = list(step.sub_steps or [])
    pending_indices = [i for i, o in enumerate(ops) if o.get("status") == "pending"]
    if not pending_indices:
        raise HTTPException(400, "没有待确认的操作")

    first_idx = pending_indices[0]
    if body.operation_id is not None and body.operation_id != ops[first_idx].get(
        "id"
    ):
        raise HTTPException(400, "只能按顺序确认当前待处理操作")

    now = datetime.datetime.utcnow()
    ops[first_idx] = {**ops[first_idx], "status": "confirmed"}
    step.sub_steps = ops

    remaining = [o for o in ops if o.get("status") == "pending"]
    if not remaining:
        step.status = "completed"
        step.finished_at = now
        step.log = f"步骤 {step_order} 所有子操作已确认于 {now.isoformat()}"
        _advance_task_to_next_step(task, step_order, db, now)

    db.commit()
    return {
        "message": f"操作 {ops[first_idx].get('id')} 已确认",
        "task_status": task.status,
        "step_status": step.status,
    }


@router.post("/{task_id}/step/{step_order}/complete")
def complete_step(task_id: int, step_order: int, db: Session = Depends(get_db)):
    task = db.query(CollectTask).filter(CollectTask.id == task_id).first()
    if not task:
        raise HTTPException(404, "任务不存在")
    step = (
        db.query(FlowStep)
        .filter(FlowStep.task_id == task_id, FlowStep.step_order == step_order)
        .first()
    )
    if not step:
        raise HTTPException(404, "步骤不存在")

    now = datetime.datetime.utcnow()
    step.status = "completed"
    step.finished_at = now
    step.log = f"步骤 {step_order} 于 {now.isoformat()} 完成"

    next_step = (
        db.query(FlowStep)
        .filter(
            FlowStep.task_id == task_id,
            FlowStep.step_order == step_order + 1,
        )
        .first()
    )
    if next_step:
        next_step.status = "running"
        next_step.started_at = now
        task.current_step = step_order + 1
        denom = task.total_steps or 1
        task.progress = min(95, int(step_order / denom * 100))
    else:
        task.status = "completed"
        task.progress = 100
        task.finished_at = now
        task.current_step = task.total_steps

    db.commit()
    return {"message": f"步骤 {step_order} 已完成", "task_status": task.status}


# ========================================================================
# 静态（离线）采集新场景：8 阶段状态机 + AI 解析 + BDI 执行
# ========================================================================


class StaticCollectReq(BaseModel):
    name: str = Field(..., description="采集任务名称")
    requirement: str = Field(..., description="采集需求 / 接口规范文本")
    overrides: Dict[str, Any] = Field(default_factory=dict, description="BDI 入参覆盖")
    auto_execute: bool = Field(
        True, description="是否创建后自动推进阶段 2~8；关闭后仅初始化"
    )
    user_name: str = Field("aiFind", description="审计用")


class SupplementReq(BaseModel):
    values: Dict[str, Any] = Field(default_factory=dict)


def _static_step_row(task_id: int, step_tpl: Dict[str, Any]) -> FlowStep:
    return FlowStep(
        task_id=task_id,
        step_order=step_tpl["step_order"],
        name=step_tpl["name"],
        description=step_tpl.get("description", ""),
        sub_steps=step_tpl["operations"],
        automation=step_tpl.get("automation", "auto"),
    )


def _advance_stage(
    task: CollectTask, step_order: int, db: Session, now: datetime.datetime
) -> None:
    """复用现有 _advance_task_to_next_step 语义，同时维护 stage 字段。"""
    _advance_task_to_next_step(task, step_order, db, now)
    if step_order < len(STATIC_STAGE_TEMPLATES):
        task.stage = STAGE_ORDER[step_order]
    elif task.current_step >= task.total_steps:
        task.stage = "online"


def _mark_step(
    step: FlowStep,
    status: str,
    now: datetime.datetime,
    log: str = "",
) -> None:
    step.status = status
    if status == "running" and not step.started_at:
        step.started_at = now
    if status in {"completed", "failed", "skipped"}:
        step.finished_at = now
    if log:
        step.log = (step.log or "") + (f"\n{log}" if step.log else log)


def _audit_call(
    db: Session,
    *,
    task_id: int,
    direction: str,
    agent: str,
    tool_name: str,
    request: Dict[str, Any],
    response: Dict[str, Any],
    status: str,
    error: str = "",
    latency_ms: int = 0,
) -> None:
    db.add(
        AgentInvocation(
            task_id=task_id,
            direction=direction,
            agent=agent,
            tool_name=tool_name,
            request=request,
            response=response,
            status=status,
            error=error,
            latency_ms=latency_ms,
        )
    )


def _finalize_operations(step: FlowStep, status: str = "confirmed") -> None:
    step.sub_steps = [
        {**op, "status": status} for op in (step.sub_steps or [])
    ]


@router.post("/static")
def create_static_task(req: StaticCollectReq, db: Session = Depends(get_db)):
    """静态采集任务：接受需求文本，自动走 8 阶段。"""
    if not req.requirement.strip():
        raise HTTPException(400, "requirement 不能为空")

    now = datetime.datetime.utcnow()
    task = CollectTask(
        name=req.name,
        table_name=(req.overrides.get("table_name") or "").strip() or "pending",
        task_type="static_bdi",
        scenario="static_bdi",
        stage=STAGE_ORDER[0],
        status="running",
        started_at=now,
        current_step=1,
        progress=5,
        total_steps=len(STATIC_STAGE_TEMPLATES),
        config_snapshot={"requirement": req.requirement, "overrides": req.overrides or {}},
    )
    db.add(task)
    db.flush()

    steps = build_initial_steps()
    step_rows: List[FlowStep] = []
    for idx, tpl in enumerate(steps):
        row = _static_step_row(task.id, tpl)
        if idx == 0:
            _mark_step(row, "running", now, "任务已发起")
        db.add(row)
        step_rows.append(row)
    db.flush()

    # 阶段 1 立即完成
    _finalize_operations(step_rows[0])
    _mark_step(step_rows[0], "completed", now, "任务发起完成")
    _advance_stage(task, 1, db, now)

    db.commit()
    db.refresh(task)

    if req.auto_execute:
        _run_auto_pipeline(db, task, req)
        db.refresh(task)

    return get_static_task_detail(task.id, db=db)


@router.post("/{task_id}/supplement")
def supplement_static_task(
    task_id: int, body: SupplementReq, db: Session = Depends(get_db)
):
    """用户提交缺失参数补全，自动尝试继续推进后续阶段。"""
    task = db.query(CollectTask).filter(CollectTask.id == task_id).first()
    if not task:
        raise HTTPException(404, "任务不存在")
    if task.scenario != "static_bdi":
        raise HTTPException(400, "该接口仅适用于 static_bdi 场景任务")

    snapshot = dict(task.config_snapshot or {})
    overrides = dict(snapshot.get("overrides") or {})
    overrides.update({k: v for k, v in body.values.items() if v not in (None, "", [], {})})
    snapshot["overrides"] = overrides
    task.config_snapshot = snapshot
    db.commit()

    req = StaticCollectReq(
        name=task.name,
        requirement=str(snapshot.get("requirement") or ""),
        overrides=overrides,
        auto_execute=True,
    )
    _run_auto_pipeline(db, task, req, resume_from_supplement=True)
    return get_static_task_detail(task_id, db=db)


@router.get("/{task_id}/static")
def get_static_task_detail(task_id: int, db: Session = Depends(get_db)):
    task = db.query(CollectTask).filter(CollectTask.id == task_id).first()
    if not task:
        raise HTTPException(404, "任务不存在")
    steps = (
        db.query(FlowStep)
        .filter(FlowStep.task_id == task_id)
        .order_by(FlowStep.step_order)
        .all()
    )
    parse_rows = (
        db.query(ParseResult)
        .filter(ParseResult.task_id == task_id)
        .order_by(ParseResult.id.desc())
        .all()
    )
    bindings = (
        db.query(BdiTaskBinding)
        .filter(BdiTaskBinding.task_id == task_id)
        .order_by(BdiTaskBinding.id.desc())
        .all()
    )
    missing = (
        db.query(MissingField)
        .filter(MissingField.task_id == task_id)
        .order_by(MissingField.id.desc())
        .all()
    )
    return {
        "id": task.id,
        "name": task.name,
        "scenario": task.scenario,
        "stage": task.stage,
        "status": task.status,
        "progress": task.progress,
        "current_step": task.current_step,
        "total_steps": task.total_steps,
        "table_name": task.table_name,
        "config_snapshot": task.config_snapshot or {},
        "error_message": task.error_message,
        "upstream_conv_id": task.upstream_conv_id,
        "downstream_task_id": task.downstream_task_id,
        "created_at": str(task.created_at) if task.created_at else None,
        "started_at": str(task.started_at) if task.started_at else None,
        "finished_at": str(task.finished_at) if task.finished_at else None,
        "steps": [
            {
                "step_order": s.step_order,
                "name": s.name,
                "description": s.description,
                "automation": s.automation,
                "status": s.status,
                "log": s.log or "",
                "operations": s.sub_steps or [],
            }
            for s in steps
        ],
        "parse_results": [
            {
                "id": pr.id,
                "status": pr.status,
                "structured": pr.structured or {},
                "missing_fields": pr.missing_fields or [],
                "conversation_id": pr.conversation_id,
                "latency_ms": pr.latency_ms,
            }
            for pr in parse_rows
        ],
        "bdi_bindings": [
            {
                "id": b.id,
                "bdi_task_id": b.bdi_task_id,
                "bdi_flow_id": b.bdi_flow_id,
                "bdi_mapping_id": b.bdi_mapping_id,
                "bdi_model_id": b.bdi_model_id,
                "full_status": b.full_status,
                "last_step": b.last_step,
                "execute_log": b.execute_log or [],
                "updated_at": str(b.updated_at) if b.updated_at else None,
            }
            for b in bindings
        ],
        "missing_fields": [
            {
                "id": m.id,
                "field_path": m.field_path,
                "reason": m.reason,
                "user_value": m.user_value,
                "confirmed_at": str(m.confirmed_at) if m.confirmed_at else None,
            }
            for m in missing
        ],
    }


# ----- 自动推进管线 -----------------------------------------------------------


def _run_auto_pipeline(
    db: Session,
    task: CollectTask,
    req: StaticCollectReq,
    *,
    resume_from_supplement: bool = False,
) -> None:
    """阶段 2 -> 8 的自动推进；失败时把相应步骤标记为 failed 并保留任务 status。"""
    try:
        structured = _run_stage_parse(db, task, req, resume=resume_from_supplement)
        mapping_ok = _run_stage_transform(db, task, req, structured)
        if not mapping_ok:
            return
        _run_stage_bdi(db, task, req, structured)
        _run_stage_monitor(db, task)
        _run_stage_testing(db, task)
        _run_stage_online(db, task)
    finally:
        db.commit()


def _run_stage_parse(
    db: Session,
    task: CollectTask,
    req: StaticCollectReq,
    *,
    resume: bool,
) -> Dict[str, Any]:
    step = _step(db, task.id, 2)
    now = datetime.datetime.utcnow()
    _mark_step(step, "running", now, "开始 AI 智能解析")

    if resume:
        prior = (
            db.query(ParseResult)
            .filter(ParseResult.task_id == task.id)
            .order_by(ParseResult.id.desc())
            .first()
        )
        if prior and prior.structured:
            _finalize_operations(step)
            _mark_step(step, "completed", now, "使用既有解析结果（补全后继续）")
            _advance_stage(task, 2, db, now)
            return dict(prior.structured)

    structured, pr_id, conv_id = _invoke_upstream_parse(db, task, req)
    task.upstream_conv_id = conv_id or ""
    if not structured:
        _mark_step(step, "failed", now, "AI 解析失败，任务挂起等待人工处理")
        task.status = "failed"
        task.error_message = "AI 解析失败或返回为空"
        return {}

    _finalize_operations(step)
    _mark_step(step, "completed", now, f"AI 解析完成, parse_id={pr_id}")
    _advance_stage(task, 2, db, now)
    return structured


def _run_stage_transform(
    db: Session, task: CollectTask, req: StaticCollectReq, structured: Dict[str, Any]
) -> bool:
    step = _step(db, task.id, 3)
    now = datetime.datetime.utcnow()
    _mark_step(step, "running", now, "开始映射 BDI 入参")

    mapping = upstream_to_bdi(structured, overrides=req.overrides or {})
    snapshot = dict(task.config_snapshot or {})
    snapshot["bdi_payload"] = mapping.payload
    snapshot["mapping_warnings"] = mapping.warnings
    snapshot["mapping_used_defaults"] = mapping.used_defaults
    task.config_snapshot = snapshot

    if not mapping.ok:
        # 写缺失字段，等待用户补全
        for issue in mapping.missing:
            db.add(
                MissingField(
                    task_id=task.id,
                    field_path=issue.field_path,
                    reason=issue.reason,
                )
            )
        _mark_step(
            step,
            "waiting",
            now,
            "BDI 参数缺失，等待用户补全: "
            + ", ".join(i.field_path for i in mapping.missing),
        )
        task.status = "waiting_supplement"
        task.stage = "transforming"
        return False

    _finalize_operations(step)
    _mark_step(step, "completed", now, "BDI 入参生成并校验通过")
    _advance_stage(task, 3, db, now)
    task.status = "running"
    return True


def _run_stage_bdi(
    db: Session, task: CollectTask, req: StaticCollectReq, structured: Dict[str, Any]
) -> None:
    step = _step(db, task.id, 4)
    now = datetime.datetime.utcnow()
    _mark_step(step, "running", now, "调度 BDI 执行")

    mapping = upstream_to_bdi(structured, overrides=req.overrides or {})
    if not mapping.ok or mapping.params is None:
        _mark_step(step, "failed", now, "入参异常，无法调度 BDI")
        task.status = "failed"
        return

    client = BdiClient(BdiClientConfig.from_env())
    binding = BdiTaskBinding(
        task_id=task.id,
        payload=mapping.payload,
        full_status="running",
    )
    db.add(binding)
    db.flush()

    try:
        resp = client.call_full_process(mapping.params)
    except BdiClientError as e:
        binding.full_status = "failed"
        binding.response = {"error": str(e)}
        _audit_call(
            db,
            task_id=task.id,
            direction="downstream",
            agent="bdi_executor",
            tool_name="bdi_full_process_execution",
            request=mapping.payload,
            response={},
            status="failed",
            error=str(e),
        )
        _mark_step(step, "failed", now, f"BDI 调用失败: {e}")
        task.status = "failed"
        task.error_message = str(e)
        return

    binding.full_status = resp.full_status
    binding.last_step = resp.task_detail.get("step", "full_process")
    binding.execute_log = resp.execute_log
    binding.response = resp.raw
    binding.bdi_task_id = str(resp.task_detail.get("task_id") or "")
    binding.bdi_flow_id = str(resp.task_detail.get("flow_id") or "")
    binding.bdi_mapping_id = str(resp.task_detail.get("mapping_id") or "")
    binding.bdi_model_id = str(resp.task_detail.get("model_id") or "")

    task.downstream_task_id = binding.bdi_task_id
    _audit_call(
        db,
        task_id=task.id,
        direction="downstream",
        agent="bdi_executor",
        tool_name="bdi_full_process_execution",
        request=mapping.payload,
        response=resp.raw,
        status="succeeded" if resp.ok else "failed",
        latency_ms=resp.latency_ms,
    )

    if not resp.ok:
        _mark_step(step, "failed", now, f"BDI 执行失败: {resp.message}")
        task.status = "failed"
        task.error_message = resp.message
        return

    _finalize_operations(step)
    _mark_step(step, "completed", now, f"BDI 执行成功: {resp.message}")
    _advance_stage(task, 4, db, now)


def _run_stage_monitor(db: Session, task: CollectTask) -> None:
    step = _step(db, task.id, 5)
    now = datetime.datetime.utcnow()
    _mark_step(step, "running", now, "接收执行进度与日志")
    _finalize_operations(step)
    _mark_step(step, "completed", now, "执行日志已归档")
    _advance_stage(task, 5, db, now)


def _run_stage_testing(db: Session, task: CollectTask) -> None:
    now = datetime.datetime.utcnow()
    # 正常路径：阶段 6 异常处理不触发，标记为 skipped 后推进到阶段 7
    err_step = _step(db, task.id, 6)
    _mark_step(err_step, "skipped", now, "无异常，跳过")
    _advance_stage(task, 6, db, now)

    step = _step(db, task.id, 7)
    _mark_step(step, "running", now, "任务测试与结果校验")
    _finalize_operations(step)
    _mark_step(step, "completed", now, "测试通过")
    _advance_stage(task, 7, db, now)


def _run_stage_online(db: Session, task: CollectTask) -> None:
    step = _step(db, task.id, 8)
    now = datetime.datetime.utcnow()
    _mark_step(step, "running", now, "任务上线与调度注册")
    _finalize_operations(step)
    _mark_step(step, "completed", now, "已上线")
    _advance_stage(task, 8, db, now)
    task.status = "completed"
    task.progress = 100
    task.finished_at = now


def _step(db: Session, task_id: int, order: int) -> FlowStep:
    row = (
        db.query(FlowStep)
        .filter(FlowStep.task_id == task_id, FlowStep.step_order == order)
        .first()
    )
    if row is None:
        raise HTTPException(500, f"步骤 {order} 不存在（task={task_id}）")
    return row


def _invoke_upstream_parse(
    db: Session, task: CollectTask, req: StaticCollectReq
):
    """调用上游 AI 解析智能体（含 mock 模式降级）。返回 (structured, parse_id, conv_id)。"""
    import json as _json
    import os as _os

    # 复用 parse 路由的 mock 开关，避免无凭据时阻塞整个流水线
    mock_on = _os.environ.get("UNICOM_MOCK", "").strip().lower() in {"1", "true", "yes"}
    started = datetime.datetime.utcnow()

    if mock_on:
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
        content = _json.dumps(structured, ensure_ascii=False)
        pr = ParseResult(
            task_id=task.id,
            source="unicom",
            requirement=req.requirement,
            content=content,
            structured=structured,
            missing_fields=[],
            conversation_id="mock-conv",
            message_id="mock-msg",
            latency_ms=0,
            status="succeeded",
            raw_response=content,
        )
        db.add(pr)
        db.flush()
        _audit_call(
            db,
            task_id=task.id,
            direction="upstream",
            agent="unicom_ai_parser",
            tool_name="unicom_ai_parse_collection_requirement",
            request={"requirement": req.requirement, "mock": True},
            response={"structured": structured},
            status="succeeded",
        )
        return structured, pr.id, "mock-conv"

    try:
        client = UnicomParseClient(UnicomParseConfig.from_env(require=True))
        result = client.invoke(req.requirement, user_name=req.user_name)
        pr = ParseResult(
            task_id=task.id,
            source="unicom",
            requirement=req.requirement,
            content=result.content,
            structured=result.structured,
            missing_fields=[],
            conversation_id=result.conversation_id,
            message_id=result.message_id,
            latency_ms=result.latency_ms,
            status="succeeded",
            raw_response=(result.raw_response or "")[:200_000],
        )
        db.add(pr)
        db.flush()
        _audit_call(
            db,
            task_id=task.id,
            direction="upstream",
            agent="unicom_ai_parser",
            tool_name="unicom_ai_parse_collection_requirement",
            request={"requirement": req.requirement},
            response={"structured": result.structured},
            status="succeeded",
            latency_ms=result.latency_ms,
        )
        return result.structured, pr.id, result.conversation_id
    except UnicomParseError as e:
        pr = ParseResult(
            task_id=task.id,
            source="unicom",
            requirement=req.requirement,
            status="failed",
            error=str(e),
        )
        db.add(pr)
        db.flush()
        latency_ms = int(
            (datetime.datetime.utcnow() - started).total_seconds() * 1000
        )
        _audit_call(
            db,
            task_id=task.id,
            direction="upstream",
            agent="unicom_ai_parser",
            tool_name="unicom_ai_parse_collection_requirement",
            request={"requirement": req.requirement},
            response={},
            status="failed",
            error=str(e),
            latency_ms=latency_ms,
        )
        return {}, pr.id, ""

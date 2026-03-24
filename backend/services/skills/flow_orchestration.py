"""流程编排 Skill：DAG / HBase / Flink / BulkLoad / 预分区"""
from __future__ import annotations
import datetime as _dt
import math
from typing import Any, Dict, List

from backend.services.skills import BaseSkill, hub

STEP_TEMPLATES: List[Dict[str, Any]] = [
    {
        "step_order": 1,
        "name": "确定源端表结构及 MC 表结构",
        "description": "AI 自动解析源端 Schema，推断字段映射关系",
        "automation": "auto",
        "sub_steps": ["拉取源端元数据", "生成字段映射", "生成 MC 目标表 DDL"],
    },
    {
        "step_order": 2,
        "name": "新建 HBase 表",
        "description": "基于数据量智能计算预分区数，自动生成建表命令",
        "automation": "auto",
        "sub_steps": ["计算预分区数", "生成建表命令", "执行建表"],
    },
    {
        "step_order": 3,
        "name": "全量初始化（历史全量文件）",
        "description": "自动编排 HDFS 操作链：创建目录→权限→上传→BulkLoad",
        "automation": "semi-auto",
        "sub_steps": [
            "创建 HDFS 初始化目录",
            "调整目录权限",
            "上传初始化文件到 HDFS",
            "执行 BulkLoad 初始化入库",
        ],
    },
    {
        "step_order": 4,
        "name": "Flink 增量还原入库",
        "description": "模板化生成 Flink 配置（20+ 参数自动填充），API 创建 BDI 流程",
        "automation": "auto",
        "sub_steps": ["生成 Flink 配置文件", "创建 BDI 采集还原流程"],
    },
    {
        "step_order": 5,
        "name": "HBase 数据导出到 HDFS",
        "description": "自动生成 Groovy 映射脚本，启动导出并智能校验",
        "automation": "semi-auto",
        "sub_steps": [
            "修改提交参数配置文件",
            "生成 Groovy 字段映射脚本",
            "启动导出脚本",
            "自动校验导出结果",
        ],
    },
    {
        "step_order": 6,
        "name": "HDFS 导出到 MC",
        "description": "AI 生成外表/内表 DDL，执行导出并断言校验数据量",
        "automation": "semi-auto",
        "sub_steps": [
            "生成并执行外表 DDL",
            "生成并执行内表 DDL",
            "执行 HDFS→MC 导出脚本",
            "数据量断言校验",
        ],
    },
]


def calculate_pre_regions(file_size_bytes: int, compression: str = "gz") -> int:
    size_gb = file_size_bytes / (1024 ** 3)
    region_size = 3 if compression == "gz" else 4
    replicas = 4
    return max(10, math.ceil(size_gb * 1024 / region_size / replicas))


def generate_hbase_create_cmd(
    table_name: str,
    zk_hosts: str,
    zk_parent: str,
    pre_regions: int,
    compression: str,
    namespace: str,
    zk_port: int = 2181,
) -> str:
    full_table = f"{namespace}:{table_name}"
    return (
        f"java -cp /data/disk01/shangyunOrder/lib/QueryHbaseTable.jar "
        f"cn.com.bonc.CreateTable {zk_hosts} {zk_parent} {pre_regions} "
        f"{compression} {full_table} {zk_port}"
    )


def generate_flink_config(
    table_name: str,
    field_list: List[str],
    pk_indexes: str,
    namespace: str,
    cluster: str = "hh-fed-sub18",
) -> Dict[str, str]:
    safe_name = table_name.lower()
    return {
        "checkPointPath": f"hdfs://{cluster}/user/tenants/.../shangyunCheckpoint/checkPoint0_{safe_name}",
        "sourceBroker": "10.177.64.59:32001,10.177.64.58:32001",
        "resetState": "earliest",
        "groupId": f"cb2i_r_cjzh_new_{safe_name}",
        "userName": "cbss_2i_k",
        "password": "******",
        "jobName": safe_name,
        "sourceTopic": "tprds-dc-i-prods-new",
        "timesKafka": _dt.datetime.now().strftime("%Y%m%d%H%M"),
        "setParalizem": "100",
        "hbaseInfo": f"{table_name.upper()}={pk_indexes}|{len(field_list)}",
        "tableIndexName": f"{table_name.upper()}|{','.join(field_list)}",
        "hbasezk": "10.177.138.67,10.177.138.68,10.177.138.69",
        "hbaseZookeeperPort": "2181",
        "hbaseParent": "hbasesub19",
        "namespace": namespace,
        "tableEnd": "",
        "defaultFS": cluster,
    }


def generate_bulkload_cmd(
    table_name: str,
    init_path: str,
    hfile_path: str,
    namespace: str,
    field_count: int,
    pk_index: str = "0",
    partition_index: int = 0,
    field_indexes: str = "",
) -> str:
    if not field_indexes:
        field_indexes = ",".join(str(i) for i in range(field_count))
    return (
        f"nohup sh prepare_complete_bulkload_pb.sh "
        f"{init_path}/ "
        f"{hfile_path}/{table_name}/ "
        f"*{table_name}* "
        f"{field_count} "
        f'"{pk_index}" '
        f"{partition_index} NO "
        f"{namespace}:{table_name} "
        f'"{field_indexes}" '
        f"> log/{table_name}.log 2>&1 &"
    )


def _build_dag_from_templates() -> Dict[str, Any]:
    nodes = [
        {
            "id": f"step_{t['step_order']}",
            "order": t["step_order"],
            "name": t["name"],
            "automation": t["automation"],
        }
        for t in STEP_TEMPLATES
    ]
    edges = [
        {
            "from": f"step_{STEP_TEMPLATES[i]['step_order']}",
            "to": f"step_{STEP_TEMPLATES[i + 1]['step_order']}",
        }
        for i in range(len(STEP_TEMPLATES) - 1)
    ]
    return {"nodes": nodes, "edges": edges, "templates": STEP_TEMPLATES}


class FlowOrchestrationSkill(BaseSkill):
    name = "flow_orchestration"
    version = "1.0"

    def list_actions(self) -> list[str]:
        return [
            "generate_dag",
            "generate_hbase_cmd",
            "generate_flink_config",
            "generate_bulkload_cmd",
            "calculate_regions",
        ]

    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action == "generate_dag":
            return {"dag": _build_dag_from_templates(), "task_id": params.get("task_id")}
        if action == "generate_hbase_cmd":
            cmd = generate_hbase_create_cmd(
                table_name=params["table_name"],
                zk_hosts=params.get("zk_hosts", "10.177.138.67,10.177.138.68,10.177.138.69"),
                zk_parent=params.get("zk_parent", "hbasesub19"),
                pre_regions=int(params["pre_regions"]),
                compression=params.get("compression", "gz"),
                namespace=params["namespace"],
                zk_port=int(params.get("zk_port", 2181)),
            )
            return {"command": cmd}
        if action == "generate_flink_config":
            cfg = generate_flink_config(
                table_name=params["table_name"],
                field_list=params.get("field_list", []),
                pk_indexes=params.get("pk_indexes", "0,4"),
                namespace=params["namespace"],
                cluster=params.get("cluster", "hh-fed-sub18"),
            )
            return {"config": cfg}
        if action == "generate_bulkload_cmd":
            cmd = generate_bulkload_cmd(
                table_name=params["table_name"],
                init_path=params["init_path"],
                hfile_path=params["hfile_path"],
                namespace=params["namespace"],
                field_count=int(params["field_count"]),
                pk_index=params.get("pk_index", "0"),
                partition_index=int(params.get("partition_index", 0)),
                field_indexes=params.get("field_indexes", ""),
            )
            return {"command": cmd}
        if action == "calculate_regions":
            n = calculate_pre_regions(
                int(params["file_size_bytes"]),
                params.get("compression", "gz"),
            )
            return {"pre_regions": n}
        return {"error": f"Unknown action: {action}"}


hub.register(FlowOrchestrationSkill())

import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

from docx import Document
from docx.oxml.ns import qn


@dataclass
class GlobalConfig:
    separator: Optional[str] = None
    line_ending: Optional[str] = None
    encoding: Optional[str] = None
    compression: Optional[str] = None
    upload_host: Optional[str] = None
    upload_dir: Optional[str] = None


@dataclass
class FieldDef:
    seq: int
    en_name: str
    cn_name: str
    data_type: str
    nullable: Optional[bool] = None
    remark: str = ""
    is_pk: bool = False
    is_sensitive: Optional[bool] = None
    is_province: Optional[bool] = None
    enum_values: Optional[str] = None


@dataclass
class TableDef:
    index: int
    section: Optional[str]
    table_name: str
    chinese_name: str
    file_name: Optional[str] = None
    file_prefix: Optional[str] = None
    interface_id: Optional[str] = None
    field_count: int = 0
    fields: List[FieldDef] = None  # type: ignore[assignment]
    pk_fields: List[int] = None  # type: ignore[assignment]
    date_fields: List[int] = None  # type: ignore[assignment]
    kafka_topic: Optional[str] = None
    kafka_partitions: Optional[int] = None


H4_RE = re.compile(
    r"^(?P<section>\d+(?:\.\d+){2,})\s+(?P<table>[A-Z0-9_]+)\s*(?P<cn>.*)$"
)
FILE_NAME_RE = re.compile(r"文件名[:：]\s*(?P<file>.+)$", re.I)
INTERFACE_ID_RE = re.compile(r"接口\s*id[:：]\s*(?P<id>[A-Z]\d{5})\b", re.I)
FILE_PREFIX_RE = re.compile(r"(?P<prefix>[A-Z]{2}\d{3}[A-Z]\d{5})")
UPLOAD_HOST_DIR_RE = re.compile(r"(?P<host>\d{1,3}(?:\.\d{1,3}){3}).*?(?P<dir>/\S+)")


def _cell_text(tc) -> str:
    return "".join(t.text or "" for t in tc.iter(qn("w:t"))).strip()


def _parse_nullable(val: str) -> Optional[bool]:
    v = (val or "").strip()
    if not v:
        return None
    if v in ("否", "N", "NO", "No", "no"):
        return False
    if v in ("是", "Y", "YES", "Yes", "yes"):
        return True
    return None


def _try_parse_int(s: str) -> Optional[int]:
    try:
        return int(str(s).strip())
    except Exception:
        return None


def _is_kafka_topic_table(headers: List[str]) -> bool:
    header_join = "|".join(headers)
    return "建设topic" in header_join and "分区数" in header_join


def _is_field_table(headers: List[str]) -> bool:
    header_join = "|".join(headers)
    return "字段序号" in header_join and "字段英文名" in header_join and ("字段类型" in header_join)


def _parse_field_table(rows: List[List[str]]) -> List[FieldDef]:
    # rows includes header at index 0
    headers = [c.strip() for c in rows[0]]
    col_count = len(headers)

    # Normalize header positions
    # 5列: 序号, 英文名, 中文名, 类型, 备注
    # 6列: 序号, 英文名, 类型, 中文名, 是否可空, 备注
    if col_count == 5:
        idx_seq, idx_en, idx_cn, idx_type, idx_remark = 0, 1, 2, 3, 4
        idx_nullable = None
    elif col_count == 6:
        idx_seq, idx_en, idx_type, idx_cn, idx_nullable, idx_remark = 0, 1, 2, 3, 4, 5
    else:
        # 不认识的字段表格式，直接返回空
        return []

    out: List[FieldDef] = []
    for r in rows[1:]:
        if len(r) < col_count:
            continue
        seq = _try_parse_int(r[idx_seq])
        en = (r[idx_en] or "").strip()
        cn = (r[idx_cn] or "").strip()
        dt = (r[idx_type] or "").strip()
        remark = (r[idx_remark] or "").strip()
        if seq is None or not en:
            continue
        nullable = _parse_nullable(r[idx_nullable]) if idx_nullable is not None else None
        out.append(
            FieldDef(
                seq=seq,
                en_name=en,
                cn_name=cn,
                data_type=dt,
                nullable=nullable,
                remark=remark,
                is_pk=False,
            )
        )
    return out


def _infer_date_fields(fields: List[FieldDef]) -> List[int]:
    out: List[int] = []
    for f in fields:
        if (f.data_type or "").strip().upper() == "DATE":
            out.append(f.seq)
    return out


def _extract_from_h4(text: str) -> Optional[Tuple[str, str, str]]:
    m = H4_RE.match((text or "").strip())
    if not m:
        return None
    section = (m.group("section") or "").strip()
    table_name = (m.group("table") or "").strip()
    cn = (m.group("cn") or "").strip()
    return section, table_name, cn


def _extract_meta_from_paragraph(text: str, meta: Dict[str, Any]) -> None:
    t = (text or "").strip()
    if not t:
        return

    fm = FILE_NAME_RE.search(t)
    if fm:
        file_name = fm.group("file").strip()
        meta["file_name"] = file_name
        pm = FILE_PREFIX_RE.search(file_name)
        if pm:
            meta["file_prefix"] = pm.group("prefix")
            # 从 file_prefix 中提取接口ID（形如 BC099D06002 -> D06002）
            if "interface_id" not in meta:
                maybe_id = meta["file_prefix"][-6:]
                if re.match(r"^[A-Z]\d{5}$", maybe_id):
                    meta["interface_id"] = maybe_id

    im = INTERFACE_ID_RE.search(t)
    if im:
        meta["interface_id"] = im.group("id").strip()

    # 全局上传目录（文档里是表格，段落不一定包含，但顺手支持）
    hm = UPLOAD_HOST_DIR_RE.search(t)
    if hm and ("/user/" in hm.group("dir")):
        meta["upload_host"] = hm.group("host")
        meta["upload_dir"] = hm.group("dir")


def parse_cbss_docx(path_or_file: Any) -> Dict[str, Any]:
    """
    解析 CBSS 接口规范 docx。
    关键约束：只做结构化提取，不做任何臆造/推断（除 date_fields、interface_id_from_prefix 这类确定性规则）。
    """
    doc = Document(path_or_file)
    body = doc.element.body

    global_cfg = GlobalConfig()
    tables: List[TableDef] = []

    # kafka topic mapping: 库名 -> (topic, partitions)
    kafka_by_db: Dict[str, Tuple[str, int]] = {}

    current: Optional[Dict[str, Any]] = None
    pending_meta_paragraphs: List[str] = []
    table_index = 0

    def flush_current(field_table_rows: Optional[List[List[str]]]) -> None:
        nonlocal current, pending_meta_paragraphs, table_index
        if not current:
            return
        fields: List[FieldDef] = []
        if field_table_rows:
            fields = _parse_field_table(field_table_rows)

        td = TableDef(
            index=table_index,
            section=current.get("section"),
            table_name=current.get("table_name") or "",
            chinese_name=current.get("chinese_name") or "",
            file_name=current.get("file_name"),
            file_prefix=current.get("file_prefix"),
            interface_id=current.get("interface_id"),
            field_count=len(fields),
            fields=fields,
            pk_fields=[],
            date_fields=_infer_date_fields(fields),
            kafka_topic=None,
            kafka_partitions=None,
        )
        tables.append(td)
        table_index += 1
        current = None
        pending_meta_paragraphs = []

    # Iterate document elements in order, associating each H4 with the next table
    for elem in body:
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if tag == "p":
            text = "".join(t.text or "" for t in elem.iter(qn("w:t"))).strip()
            if not text:
                continue

            # global config extraction (only if explicitly stated in paragraph)
            if "0x01" in text and "分隔" in text:
                global_cfg.separator = "0x01"
            if "0x0A" in text and ("换行" in text or "结尾" in text):
                global_cfg.line_ending = "0x0A"
            if "UTF8" in text.upper():
                global_cfg.encoding = "UTF8"
            if ".gz" in text:
                global_cfg.compression = "gz"

            h4 = _extract_from_h4(text)
            if h4:
                # start new table unit
                current = {
                    "section": h4[0],
                    "table_name": h4[1],
                    "chinese_name": h4[2],
                }
                pending_meta_paragraphs = []
                continue

            if current:
                pending_meta_paragraphs.append(text)
                for ptxt in pending_meta_paragraphs[-20:]:
                    _extract_meta_from_paragraph(ptxt, current)

        elif tag == "tbl":
            rows = elem.findall(qn("w:tr"))
            if not rows:
                continue
            first_row = rows[0]
            header_cells = first_row.findall(qn("w:tc"))
            headers = [_cell_text(c) for c in header_cells]

            # Kafka topic config table is independent and may appear anywhere
            if _is_kafka_topic_table(headers):
                # Expect columns: [归属库?, 新架构库名, RDS数, 实例ID, 建设topic, 分区数]
                for tr in rows[1:]:
                    tcs = tr.findall(qn("w:tc"))
                    cells = [_cell_text(c) for c in tcs]
                    if len(cells) < 6:
                        continue
                    db_display = cells[0].strip()
                    topic = cells[4].strip()
                    part = _try_parse_int(cells[5].strip())
                    if db_display and topic and part is not None:
                        kafka_by_db[db_display] = (topic, part)
                continue

            if current and _is_field_table(headers):
                # Parse all rows into 2d array
                table_rows: List[List[str]] = []
                for tr in rows:
                    tcs = tr.findall(qn("w:tc"))
                    table_rows.append([_cell_text(c) for c in tcs])
                flush_current(table_rows)
                continue

            # Upload directory table: (接口机, 目录名, 目录内容)
            if len(headers) == 3 and headers[0] == "接口机" and "目录名" in headers[1]:
                for tr in rows[1:2]:
                    tcs = tr.findall(qn("w:tc"))
                    cells = [_cell_text(c) for c in tcs]
                    if len(cells) >= 2:
                        global_cfg.upload_host = cells[0].strip() or global_cfg.upload_host
                        global_cfg.upload_dir = cells[1].strip() or global_cfg.upload_dir
                continue

            # Non-field table encountered after H4: ignore; keep collecting paragraphs

    # If doc ends without a field table for the last H4, flush empty
    flush_current(None)

    return {
        "global_config": asdict(global_cfg),
        "kafka_topic_map": {
            db: {"kafka_topic": topic, "kafka_partitions": part}
            for db, (topic, part) in kafka_by_db.items()
        },
        "tables": [
            {
                **{
                    k: v
                    for k, v in asdict(t).items()
                    if k not in ("fields",)
                },
                "fields": [asdict(f) for f in (t.fields or [])],
            }
            for t in tables
        ],
    }


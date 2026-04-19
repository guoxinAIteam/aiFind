"""轻量级 SQLite schema 对齐：仅新增缺失列。

`Base.metadata.create_all` 不会修改已存在表结构，因此本期为 `collect_tasks`
等表追加列时需手动 ALTER。该函数幂等，每次启动调用一次即可。
"""
from __future__ import annotations

from typing import Iterable, Tuple

from sqlalchemy import text
from sqlalchemy.engine import Engine


ADDITIONS: Tuple[Tuple[str, str, str], ...] = (
    # (table, column, sqlite_coldef_with_default)
    ("collect_tasks", "scenario", "TEXT DEFAULT 'legacy'"),
    ("collect_tasks", "stage", "TEXT DEFAULT ''"),
    ("collect_tasks", "upstream_conv_id", "TEXT DEFAULT ''"),
    ("collect_tasks", "downstream_task_id", "TEXT DEFAULT ''"),
)


def _existing_columns(engine: Engine, table: str) -> Iterable[str]:
    with engine.connect() as conn:
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return [r[1] for r in rows]


def ensure_schema(engine: Engine) -> None:
    """幂等地为已有表追加本期新增列。

    仅实现 ADD COLUMN，不处理列删除或类型变更；新表由 metadata.create_all 负责。
    """
    for table, column, coldef in ADDITIONS:
        try:
            existing = list(_existing_columns(engine, table))
        except Exception:
            continue
        if not existing:
            continue
        if column in existing:
            continue
        stmt = f"ALTER TABLE {table} ADD COLUMN {column} {coldef}"
        with engine.begin() as conn:
            conn.execute(text(stmt))

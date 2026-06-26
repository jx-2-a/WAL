"""跨模式持久记忆工具 — 所有模式（writing/planning/autonomous）可用

基于 agent_config 表实现，key 加 `mem_` 前缀避免与配置键冲突。
重启后记忆依然存在，适合保存重要的讨论结论和决策。
"""

import os
from pathlib import Path
from ..storage.database import Database


def _get_db(project_name: str) -> Database:
    base = Path(os.environ.get("WAL_PROJECTS", "projects"))
    db_path = base / project_name / "wal.db"
    db = Database(str(db_path))
    db.init_schema()
    return db


def save_agent_memory(project_name: str, key: str, value: str) -> dict:
    """保存一个 key-value 记忆条目。重启后仍存在。"""
    db = _get_db(project_name)
    with db.get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO agent_config (key, value) VALUES (?, ?)",
            (f"mem_{key}", value),
        )
    return {"key": key, "saved": True}


def get_agent_memory(project_name: str, key: str = "") -> dict:
    """读取保存的记忆。key 为空时列出所有记忆。"""
    db = _get_db(project_name)
    with db.get_conn() as conn:
        if key:
            row = conn.execute(
                "SELECT value FROM agent_config WHERE key = ?",
                (f"mem_{key}",),
            ).fetchone()
            if not row:
                return {"key": key, "found": False}
            return {"key": key, "value": row[0]}
        else:
            rows = conn.execute(
                "SELECT key, value FROM agent_config WHERE key LIKE 'mem_%'"
            ).fetchall()
            return {
                "memories": [
                    {"key": r[0][4:], "value": r[1][:200]}
                    for r in rows
                ]
            }


def delete_agent_memory(project_name: str, key: str) -> dict:
    """删除一条保存的记忆。"""
    db = _get_db(project_name)
    with db.get_conn() as conn:
        conn.execute(
            "DELETE FROM agent_config WHERE key = ?",
            (f"mem_{key}",),
        )
    return {"key": key, "deleted": True}

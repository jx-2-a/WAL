"""SQLite 通用仓库基类 — 替代 BaseRepository(YAML)

提供参数化 CRUD、JSON 序列化/反序列化、事务支持。
所有新 Repository 继承此类而非 BaseRepository。
"""

import json
import sqlite3
from pathlib import Path
from typing import Any, Optional

from .database import Database


def _json_serialize(value: Any) -> str:
    """将 Python 对象序列化为 JSON 字符串"""
    if isinstance(value, str):
        # 如果已经是 JSON 字符串，直接返回
        try:
            json.loads(value)
            return value
        except (json.JSONDecodeError, TypeError):
            pass
    return json.dumps(value, ensure_ascii=False)


def _json_deserialize(value: str) -> Any:
    """将 JSON 字符串反序列化为 Python 对象"""
    if not value:
        return value
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


class DatabaseRepository:
    """SQLite 通用仓库

    子类通过 self.db 访问 Database 实例。
    所有写入操作自动提交，查询操作只读。

    用法:
        class MyRepo(DatabaseRepository):
            def get_foo(self, foo_id):
                return self._fetch_one("SELECT * FROM foo WHERE id = ?", (foo_id,))
    """

    def __init__(self, db: Database):
        self.db = db

    # ── 基础 SQL 操作 ──────────────────────────────────────────────

    def _execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """执行写操作（INSERT/UPDATE/DELETE），自动提交"""
        with self.db.get_conn() as conn:
            cur = conn.execute(sql, params)
            conn.commit()
            return cur

    def _execute_many(self, sql: str, params_list: list[tuple]) -> sqlite3.Cursor:
        """批量执行写操作"""
        with self.db.get_conn() as conn:
            cur = conn.executemany(sql, params_list)
            conn.commit()
            return cur

    def _fetch_one(self, sql: str, params: tuple = ()) -> Optional[dict]:
        """查询单行，返回 dict 或 None"""
        with self.db.get_conn() as conn:
            cur = conn.execute(sql, params)
            row = cur.fetchone()
            return dict(row) if row else None

    def _fetch_all(self, sql: str, params: tuple = ()) -> list[dict]:
        """查询多行，返回 list[dict]"""
        with self.db.get_conn() as conn:
            cur = conn.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]

    def _fetch_column(self, sql: str, params: tuple = (), column: int = 0) -> list:
        """查询单列值"""
        with self.db.get_conn() as conn:
            cur = conn.execute(sql, params)
            return [row[column] for row in cur.fetchall()]

    def _fetch_value(self, sql: str, params: tuple = ()) -> Any:
        """查询单个标量值"""
        with self.db.get_conn() as conn:
            cur = conn.execute(sql, params)
            row = cur.fetchone()
            return row[0] if row else None

    def _insert(self, table: str, data: dict) -> str:
        """插入一行，返回 lastrowid 的字符串形式"""
        columns = list(data.keys())
        placeholders = ", ".join(["?"] * len(columns))
        values = tuple(data.values())
        sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
        with self.db.get_conn() as conn:
            cur = conn.execute(sql, values)
            conn.commit()
            return str(cur.lastrowid) if cur.lastrowid else ""

    def _insert_or_replace(self, table: str, data: dict) -> None:
        """插入或替换一行"""
        columns = list(data.keys())
        placeholders = ", ".join(["?"] * len(columns))
        values = tuple(data.values())
        sql = f"INSERT OR REPLACE INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
        self._execute(sql, values)

    def _update(self, table: str, data: dict, where: str, params: tuple = ()) -> int:
        """更新行，返回受影响行数"""
        set_clause = ", ".join(f"{k} = ?" for k in data.keys())
        values = tuple(data.values()) + params
        sql = f"UPDATE {table} SET {set_clause} WHERE {where}"
        with self.db.get_conn() as conn:
            cur = conn.execute(sql, values)
            conn.commit()
            return cur.rowcount

    def _delete(self, table: str, where: str, params: tuple = ()) -> int:
        """删除行，返回受影响行数"""
        sql = f"DELETE FROM {table} WHERE {where}"
        with self.db.get_conn() as conn:
            cur = conn.execute(sql, params)
            conn.commit()
            return cur.rowcount

    def _count(self, table: str, where: str = "1", params: tuple = ()) -> int:
        """计数"""
        return self._fetch_value(f"SELECT COUNT(*) FROM {table} WHERE {where}", params) or 0

    def _exists(self, table: str, where: str, params: tuple = ()) -> bool:
        """检查是否存在"""
        return self._count(table, where, params) > 0

    # ── JSON 帮助方法 ──────────────────────────────────────────────

    @staticmethod
    def _to_json(value: Any) -> str:
        """Python → JSON 字符串"""
        return _json_serialize(value)

    @staticmethod
    def _from_json(value: str) -> Any:
        """JSON 字符串 → Python"""
        return _json_deserialize(value)

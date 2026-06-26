"""自主模式仓库 — SQLite 版

管理 auto_decisions, agent_config 表。
提供决策记录、审批状态管理和配置持久化。
"""

import json
from datetime import datetime
from typing import Optional

from .db_repo import DatabaseRepository


class AutoRepository(DatabaseRepository):
    """自主决策仓库（SQLite）"""

    STORY_ID = "main"

    # ═══ 决策记录 ═══════════════════════════════════════════════════

    def save_decision(self, decision: dict) -> str:
        """保存决策记录，返回决策ID"""
        row = {
            "id": decision.get("id", ""),
            "story_id": self.STORY_ID,
            "timestamp": decision.get("timestamp", datetime.now().isoformat()),
            "decision_type": decision.get("decision_type", ""),
            "description": decision.get("description", ""),
            "reasoning": decision.get("reasoning", ""),
            "impact_level": decision.get("impact_level", "minor"),
            "affected_elements": self._to_json(decision.get("affected_elements", [])),
            "approved": 1 if decision.get("approved", False) else 0,
        }
        self._insert_or_replace("auto_decisions", row)
        return row["id"]

    def get_decision(self, decision_id: str) -> Optional[dict]:
        """获取单条决策"""
        row = self._fetch_one(
            "SELECT * FROM auto_decisions WHERE id = ? AND story_id = ?",
            (decision_id, self.STORY_ID),
        )
        return self._deserialize_decision(row) if row else None

    def list_decisions(self, approved: Optional[bool] = None,
                       impact_level: str = "", limit: int = 50) -> list[dict]:
        """列出决策记录，可按审批状态和影响级别过滤"""
        sql = "SELECT * FROM auto_decisions WHERE story_id = ?"
        params: list = [self.STORY_ID]

        if approved is not None:
            sql += " AND approved = ?"
            params.append(1 if approved else 0)
        if impact_level:
            sql += " AND impact_level = ?"
            params.append(impact_level)

        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        rows = self._fetch_all(sql, tuple(params))
        return [self._deserialize_decision(r) for r in rows]

    def list_pending_decisions(self, limit: int = 20) -> list[dict]:
        """列出待审批的决策（impact_level 为 moderate 及以上且未审批）"""
        rows = self._fetch_all(
            """SELECT * FROM auto_decisions
               WHERE story_id = ? AND approved = 0
                 AND impact_level IN ('moderate', 'major', 'critical')
               ORDER BY timestamp DESC LIMIT ?""",
            (self.STORY_ID, limit),
        )
        return [self._deserialize_decision(r) for r in rows]

    def approve_decision(self, decision_id: str) -> bool:
        """审批通过一条决策"""
        self._execute(
            "UPDATE auto_decisions SET approved = 1 WHERE id = ? AND story_id = ?",
            (decision_id, self.STORY_ID),
        )
        return True

    def reject_decision(self, decision_id: str) -> bool:
        """拒绝/废弃一条决策"""
        self._execute(
            "UPDATE auto_decisions SET approved = 0 WHERE id = ? AND story_id = ?",
            (decision_id, self.STORY_ID),
        )
        return True

    def get_decision_stats(self) -> dict:
        """获取决策统计"""
        row = self._fetch_one(
            """SELECT
                 COUNT(*) as total,
                 SUM(CASE WHEN approved = 1 THEN 1 ELSE 0 END) as approved_count,
                 SUM(CASE WHEN approved = 0 THEN 1 ELSE 0 END) as pending_count,
                 SUM(CASE WHEN impact_level = 'critical' AND approved = 0 THEN 1 ELSE 0 END) as critical_pending
               FROM auto_decisions WHERE story_id = ?""",
            (self.STORY_ID,),
        )
        if row:
            return {
                "total": row["total"] or 0,
                "approved_count": row["approved_count"] or 0,
                "pending_count": row["pending_count"] or 0,
                "critical_pending": row["critical_pending"] or 0,
            }
        return {"total": 0, "approved_count": 0, "pending_count": 0, "critical_pending": 0}

    def delete_decision(self, decision_id: str) -> None:
        """删除一条决策记录"""
        self._execute(
            "DELETE FROM auto_decisions WHERE id = ? AND story_id = ?",
            (decision_id, self.STORY_ID),
        )

    # ═══ Agent 配置 ═══════════════════════════════════════════════════

    def get_config(self, key: str, default: str = "") -> str:
        """读取配置项"""
        row = self._fetch_one(
            "SELECT value FROM agent_config WHERE key = ?",
            (key,),
        )
        return row["value"] if row else default

    def set_config(self, key: str, value: str) -> None:
        """写入/更新配置项"""
        self._execute(
            "INSERT OR REPLACE INTO agent_config (key, value) VALUES (?, ?)",
            (key, value),
        )

    def get_all_config(self) -> dict[str, str]:
        """读取所有配置"""
        rows = self._fetch_all("SELECT key, value FROM agent_config")
        return {r["key"]: r["value"] for r in rows}

    # ═══ 辅助 ═══════════════════════════════════════════════════════

    def _deserialize_decision(self, row: dict) -> dict:
        """反序列化决策记录"""
        if row is None:
            return {}
        result = dict(row)
        result["approved"] = bool(result.get("approved", 0))
        affected = result.get("affected_elements", "[]")
        if isinstance(affected, str):
            try:
                result["affected_elements"] = json.loads(affected)
            except json.JSONDecodeError:
                result["affected_elements"] = []
        return result

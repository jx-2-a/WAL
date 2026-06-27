"""剧情仓库 — SQLite 版

管理 plot_lines, plot_points, plot_intersections, foreshadowings 表的 CRUD。
替代原 YAML 版 PlotRepository。
"""

from typing import Optional

from .db_repo import DatabaseRepository


class PlotRepository(DatabaseRepository):
    """剧情线数据仓库（SQLite）"""

    STORY_ID = "main"

    # ═══ 剧情线 CRUD ═════════════════════════════════════════════

    def save_plot_line(self, plot_data: dict) -> None:
        data = {
            "id": plot_data.get("id", ""),
            "story_id": self.STORY_ID,
            "parent_id": plot_data.get("parent_id") or None,
            "name": plot_data.get("name", ""),
            "level": plot_data.get("level", "sub"),
            "plot_type": plot_data.get("plot_type", "sub"),
            "description": plot_data.get("description", ""),
            "theme": plot_data.get("theme", ""),
            "status": plot_data.get("status", "active"),
            "started_in_chapter": plot_data.get("started_in_chapter", 1),
            "target_chapter": plot_data.get("target_chapter", 0),
            "notes": plot_data.get("notes", ""),
        }
        self._insert_or_replace("plot_lines", data)

    def load_plot_line(self, plot_id: str) -> Optional[dict]:
        return self._fetch_one("SELECT * FROM plot_lines WHERE id = ?", (plot_id,))

    def load_all_plot_lines(self) -> dict[str, dict]:
        rows = self._fetch_all(
            "SELECT * FROM plot_lines WHERE story_id = ?", (self.STORY_ID,)
        )
        return {r["id"]: dict(r) for r in rows}

    def list_plot_lines(self, level: str = "", plot_type: str = "",
                        parent_id: str = "") -> list[dict]:
        conditions = ["story_id = ?"]
        params: list = [self.STORY_ID]

        if level:
            conditions.append("level = ?")
            params.append(level)
        if plot_type:
            conditions.append("plot_type = ?")
            params.append(plot_type)
        if parent_id:
            conditions.append("parent_id = ?")
            params.append(parent_id)
        # 空字符串 parent_id 表示查顶级
        elif parent_id == "" and not level:
            pass  # 不额外过滤

        sql = f"SELECT * FROM plot_lines WHERE {' AND '.join(conditions)} ORDER BY level, name"
        return self._fetch_all(sql, tuple(params))

    def get_children_plots(self, parent_id: str) -> list[dict]:
        return self._fetch_all(
            "SELECT * FROM plot_lines WHERE story_id = ? AND parent_id = ? ORDER BY name",
            (self.STORY_ID, parent_id),
        )

    def get_root_plots(self) -> list[dict]:
        """获取顶级剧情线（无父级）"""
        return self._fetch_all(
            "SELECT * FROM plot_lines WHERE story_id = ? AND parent_id IS NULL ORDER BY level, name",
            (self.STORY_ID,),
        )

    def delete_plot_line(self, plot_id: str) -> int:
        return self._delete("plot_lines", "id = ?", (plot_id,))

    def update_plot_field(self, plot_id: str, key: str, value) -> None:
        self._update("plot_lines", {key: value}, "id = ?", (plot_id,))

    def next_plot_number(self) -> int:
        return self._count("plot_lines", "story_id = ?", (self.STORY_ID,)) + 1

    # ═══ 情节点 CRUD ═════════════════════════════════════════════

    def save_plot_point(self, point_data: dict) -> None:
        data = {
            "id": point_data.get("id", ""),
            "plot_id": point_data.get("plot_id", ""),
            "title": point_data.get("title", ""),
            "description": point_data.get("description", ""),
            "order_index": point_data.get("order_index", 0),
            "chapter_assigned": point_data.get("chapter_assigned", 0),
            "status": point_data.get("status", "pending"),
            "prerequisites": self._to_json(point_data.get("prerequisites", [])),
            "impacts_characters": self._to_json(point_data.get("impacts_characters", [])),
            "emotional_tone": point_data.get("emotional_tone", ""),
            "estimated_words": point_data.get("estimated_words", 0),
            "notes": point_data.get("notes", ""),
        }
        self._insert_or_replace("plot_points", data)

    def load_plot_point(self, point_id: str) -> Optional[dict]:
        row = self._fetch_one("SELECT * FROM plot_points WHERE id = ?", (point_id,))
        return self._deserialize_point(row)

    def list_points_by_plot(self, plot_id: str) -> list[dict]:
        rows = self._fetch_all(
            "SELECT * FROM plot_points WHERE plot_id = ? ORDER BY order_index", (plot_id,)
        )
        return [self._deserialize_point(r) for r in rows]

    def list_points_by_chapter(self, chapter_number: int) -> list[dict]:
        rows = self._fetch_all(
            "SELECT * FROM plot_points WHERE chapter_assigned = ? ORDER BY plot_id, order_index",
            (chapter_number,),
        )
        return [self._deserialize_point(r) for r in rows]

    def delete_plot_point(self, point_id: str) -> int:
        return self._delete("plot_points", "id = ?", (point_id,))

    def delete_points_by_plot(self, plot_id: str) -> int:
        return self._delete("plot_points", "plot_id = ?", (plot_id,))

    def delete_points_by_chapter(self, chapter_number: int) -> int:
        """删除指定章节的所有情节点（用于章节重写时级联清理）"""
        return self._delete("plot_points", "chapter_assigned = ?", (chapter_number,))

    def reset_foreshadowing_chapter(self, chapter_number: int) -> dict:
        """清空与指定章节关联的伏笔引用（埋笔章号和回收章号）

        用于章节重写时——伏笔本身保留（可能是跨章的），
        但清除与本章的关联标记，避免指向不存在的章节内容。
        """
        created = self._update(
            "foreshadowings",
            {"created_at_chapter": 0},
            "created_at_chapter = ?",
            (chapter_number,),
        )
        resolved = self._update(
            "foreshadowings",
            {"resolved_at_chapter": 0},
            "resolved_at_chapter = ?",
            (chapter_number,),
        )
        return {"cleared_created": created, "cleared_resolved": resolved}

    def update_point_field(self, point_id: str, key: str, value) -> None:
        if isinstance(value, (list, dict)):
            value = self._to_json(value)
        self._update("plot_points", {key: value}, "id = ?", (point_id,))

    def _deserialize_point(self, row: Optional[dict]) -> Optional[dict]:
        if not row:
            return None
        row["prerequisites"] = self._from_json(row["prerequisites"])
        row["impacts_characters"] = self._from_json(row["impacts_characters"])
        return row

    # ═══ 剧情交汇 ═════════════════════════════════════════════════

    def save_intersection(self, inter_data: dict) -> None:
        data = {
            "id": inter_data.get("id", ""),
            "plot_a": inter_data.get("plot_a", ""),
            "plot_b": inter_data.get("plot_b", ""),
            "at_plot_point_a": inter_data.get("at_plot_point_a", ""),
            "at_plot_point_b": inter_data.get("at_plot_point_b", ""),
            "description": inter_data.get("description", ""),
            "chapter_hint": inter_data.get("chapter_hint", 0),
        }
        self._insert_or_replace("plot_intersections", data)

    def list_intersections_for_plot(self, plot_id: str) -> list[dict]:
        return self._fetch_all(
            "SELECT * FROM plot_intersections WHERE plot_a = ? OR plot_b = ?",
            (plot_id, plot_id),
        )

    def list_all_intersections(self) -> list[dict]:
        return self._fetch_all("SELECT DISTINCT * FROM plot_intersections")

    def delete_intersection(self, inter_id: str) -> int:
        return self._delete("plot_intersections", "id = ?", (inter_id,))

    # ═══ 伏笔 CRUD ═══════════════════════════════════════════════

    def save_foreshadowing(self, fw_data: dict) -> None:
        data = {
            "id": fw_data.get("id", ""),
            "story_id": self.STORY_ID,
            "description": fw_data.get("description", ""),
            "created_at_chapter": fw_data.get("created_at_chapter", 0),
            "created_at_volume": fw_data.get("created_at_volume", 0),
            "target_chapter": fw_data.get("target_chapter", 0),
            "resolved_at_chapter": fw_data.get("resolved_at_chapter", 0),
            "status": fw_data.get("status", "pending"),
            "urgency": fw_data.get("urgency", "medium"),
            "related_plot_lines": self._to_json(fw_data.get("related_plot_lines", [])),
            "related_characters": self._to_json(fw_data.get("related_characters", [])),
            "resolution_notes": fw_data.get("resolution_notes", ""),
        }
        self._insert_or_replace("foreshadowings", data)

    def load_foreshadowing(self, fw_id: str) -> Optional[dict]:
        row = self._fetch_one("SELECT * FROM foreshadowings WHERE id = ?", (fw_id,))
        return self._deserialize_foreshadowing(row)

    def list_foreshadowings(self, status: str = "") -> list[dict]:
        if status:
            rows = self._fetch_all(
                "SELECT * FROM foreshadowings WHERE story_id = ? AND status = ?",
                (self.STORY_ID, status),
            )
        else:
            rows = self._fetch_all(
                "SELECT * FROM foreshadowings WHERE story_id = ?", (self.STORY_ID,)
            )
        return [self._deserialize_foreshadowing(r) for r in rows]

    def list_dangling_foreshadowings(self) -> list[dict]:
        """未回收的伏笔"""
        return self.list_foreshadowings(status="pending") + \
               self.list_foreshadowings(status="partially_resolved")

    def delete_foreshadowing(self, fw_id: str) -> int:
        return self._delete("foreshadowings", "id = ?", (fw_id,))

    def update_foreshadowing_field(self, fw_id: str, key: str, value) -> None:
        if isinstance(value, (list, dict)):
            value = self._to_json(value)
        self._update("foreshadowings", {key: value}, "id = ?", (fw_id,))

    def get_foreshadowing_stats(self, current_chapter: int = 0) -> dict:
        """伏笔统计（用于健康检查）"""
        total = self._count("foreshadowings", "story_id = ?", (self.STORY_ID,))
        resolved = self._count(
            "foreshadowings", "story_id = ? AND status = 'resolved'", (self.STORY_ID,)
        )
        dangling = total - resolved

        # 按紧急程度分组
        critical = self._count(
            "foreshadowings", "story_id = ? AND status != 'resolved' AND urgency = 'critical'",
            (self.STORY_ID,)
        )
        high = self._count(
            "foreshadowings", "story_id = ? AND status != 'resolved' AND urgency = 'high'",
            (self.STORY_ID,)
        )

        # 长期未回收的（超过 30 章）
        old_count = 0
        if current_chapter > 0:
            old_count = self._count(
                "foreshadowings",
                "story_id = ? AND status != 'resolved' AND created_at_chapter > 0 AND ? - created_at_chapter > 30",
                (self.STORY_ID, current_chapter),
            )

        return {
            "total": total,
            "resolved": resolved,
            "dangling": dangling,
            "critical": critical,
            "high_urgency": high,
            "old_unresolved": old_count,
        }

    def next_foreshadowing_number(self) -> int:
        return self._count("foreshadowings", "story_id = ?", (self.STORY_ID,)) + 1

    def _deserialize_foreshadowing(self, row: Optional[dict]) -> Optional[dict]:
        if not row:
            return None
        row["related_plot_lines"] = self._from_json(row["related_plot_lines"])
        row["related_characters"] = self._from_json(row["related_characters"])
        return row

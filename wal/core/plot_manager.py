"""剧情管理器 — SQLite 版

主线/支线追踪、交汇、健康度检查、伏笔管理。
内部使用 SQLite 存储。
"""

from pathlib import Path
from typing import Optional

from ..models.plot import (
    PlotLine, PlotPoint, PlotIntersection,
    PlotType, PlotLevel, PlotLineStatus, PlotPointStatus,
    Foreshadowing, ForeshadowingStatus,
)
from ..storage.database import Database
from ..storage.plot_repo import PlotRepository


class PlotManager:
    """管理剧情线的创建、追踪、交汇和健康度（SQLite 后端）"""

    def __init__(self, project_dir: str):
        self.project_dir = Path(project_dir)
        self.project_dir.mkdir(parents=True, exist_ok=True)

        db_path = self.project_dir / "wal.db"
        self.db = Database(str(db_path))
        self.repo = PlotRepository(self.db)

        if not self.db.schema_exists():
            self.db.init_schema()
            if (self.project_dir / "story.yaml").exists():
                self.db.migrate_from_yaml(str(self.project_dir))

        self._ensure_story_exists()
        self._plots: dict[str, PlotLine] = {}

    def _ensure_story_exists(self) -> None:
        """确保 stories 表有主记录（FK 约束需要）"""
        conn = self.db.get_conn()
        row = conn.execute("SELECT id FROM stories WHERE id = 'main'").fetchone()
        if not row:
            from datetime import datetime
            now = datetime.now().isoformat()
            conn.execute(
                "INSERT INTO stories (id, name, author, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("main", "", "", "planning", now, now),
            )
            conn.commit()

    def load(self) -> dict[str, PlotLine]:
        """从 SQLite 加载所有剧情线"""
        self._plots = {}
        plot_rows = self.repo.load_all_plot_lines()
        for pid, prow in plot_rows.items():
            # 加载情节点
            pp_rows = self.repo.list_points_by_plot(pid)
            plot_points = [PlotPoint(**pp) for pp in pp_rows]

            # 加载交汇点
            inter_rows = self.repo.list_intersections_for_plot(pid)
            seen = set()
            intersections = []
            for inter in inter_rows:
                key = (inter["plot_a"], inter["plot_b"], inter["at_plot_point_a"], inter["at_plot_point_b"])
                if key not in seen:
                    seen.add(key)
                    intersections.append(PlotIntersection(**inter))

            prow["plot_type"] = PlotType(prow["plot_type"]) if prow["plot_type"] in ("main", "sub") else PlotType.SUB
            prow["status"] = PlotLineStatus(prow["status"]) if prow["status"] in (
                "active", "completed", "abandoned"
            ) else PlotLineStatus.ACTIVE
            level_raw = prow.get("level", prow["plot_type"].value)
            prow["level"] = PlotLevel(level_raw) if level_raw in ("main", "volume", "sub", "character_arc") else (
                PlotLevel.MAIN if prow["plot_type"] == PlotType.MAIN else PlotLevel.SUB
            )
            prow["parent_id"] = prow.get("parent_id") or ""
            prow["plot_points"] = plot_points
            prow["intersects_with"] = intersections
            self._plots[pid] = PlotLine(**prow)
        return self._plots

    def save(self) -> None:
        """保存所有剧情线到 SQLite"""
        for pl in self._plots.values():
            pl_dict = pl.model_dump(mode="json")
            plot_points = pl_dict.pop("plot_points", [])
            intersections = pl_dict.pop("intersects_with", [])
            self.repo.save_plot_line(pl_dict)
            for pp in plot_points:
                pp["plot_id"] = pl.id
                self.repo.save_plot_point(pp)
            for inter in intersections:
                self.repo.save_intersection(inter)

    # ═══ 剧情线 CRUD ═════════════════════════════════════════════

    def create_plot_line(self, name: str, plot_type: str = "sub",
                         description: str = "", theme: str = "",
                         started_in_chapter: int = 1, target_chapter: int = 0,
                         level: str = "", parent_id: str = "") -> PlotLine:
        """创建新剧情线"""
        pid = f"plot_{self.repo.next_plot_number():03d}"
        pt = PlotType(plot_type) if plot_type in ("main", "sub") else PlotType.SUB
        lv = PlotLevel(level) if level in ("main", "volume", "sub", "character_arc") else (
            PlotLevel.MAIN if plot_type == "main" else PlotLevel.SUB
        )
        pl = PlotLine(
            id=pid, name=name, plot_type=pt,
            level=lv, parent_id=parent_id,
            description=description, theme=theme,
            started_in_chapter=started_in_chapter,
            target_chapter=target_chapter,
        )
        pl_dict = pl.model_dump(mode="json")
        pl_dict["level"] = lv.value
        pl_dict["parent_id"] = parent_id or None
        self.repo.save_plot_line(pl_dict)
        self._plots[pid] = pl
        return pl

    def get_plot_line(self, plot_id: str) -> Optional[PlotLine]:
        if plot_id in self._plots:
            return self._plots[plot_id]
        prow = self.repo.load_plot_line(plot_id)
        if not prow:
            return None
        prow["plot_type"] = PlotType(prow["plot_type"]) if prow["plot_type"] in ("main", "sub") else PlotType.SUB
        prow["status"] = PlotLineStatus(prow["status"]) if prow["status"] in (
            "active", "completed", "abandoned"
        ) else PlotLineStatus.ACTIVE
        level_raw = prow.get("level", prow["plot_type"].value)
        prow["level"] = PlotLevel(level_raw) if level_raw in ("main", "volume", "sub", "character_arc") else (
            PlotLevel.MAIN if prow["plot_type"] == PlotType.MAIN else PlotLevel.SUB
        )
        prow["parent_id"] = prow.get("parent_id") or ""
        pp_rows = self.repo.list_points_by_plot(plot_id)
        prow["plot_points"] = [PlotPoint(**pp) for pp in pp_rows]
        inter_rows = self.repo.list_intersections_for_plot(plot_id)
        prow["intersects_with"] = [PlotIntersection(**i) for i in inter_rows]
        pl = PlotLine(**prow)
        self._plots[plot_id] = pl
        return pl

    def list_plot_lines(self, plot_type: str | None = None,
                        level: str | None = None) -> list[PlotLine]:
        """列出剧情线"""
        self.load()
        result = list(self._plots.values())
        if plot_type:
            result = [p for p in result if p.plot_type.value == plot_type]
        if level:
            result = [p for p in result if getattr(p, 'level', p.plot_type.value) == level]
        return result

    def delete_plot_line(self, plot_id: str) -> bool:
        if plot_id in self._plots:
            del self._plots[plot_id]
        return self.repo.delete_plot_line(plot_id) > 0

    def update_plot_line(self, plot_id: str, **kwargs) -> dict:
        """更新剧情线属性（name, description, theme, status, target_chapter 等）"""
        self.load()
        pl = self._plots.get(plot_id)
        if not pl:
            raise ValueError(f"Plot line '{plot_id}' not found")
        for key, value in kwargs.items():
            if hasattr(pl, key) and key != "plot_points":
                setattr(pl, key, value)
                self.repo.update_plot_field(plot_id, key, value)
        return {
            "id": pl.id, "name": pl.name, "plot_type": pl.plot_type.value,
            "status": pl.status.value if hasattr(pl.status, 'value') else str(pl.status),
        }

    def update_foreshadowing(self, fw_id: str, **kwargs) -> dict:
        """更新伏笔属性（description, urgency, target_chapter, related_plot_lines 等）"""
        from ..models.plot import Foreshadowing
        fw = self.repo.load_foreshadowing(fw_id)
        if not fw:
            raise ValueError(f"Foreshadowing '{fw_id}' not found")
        changes = []
        for key, value in kwargs.items():
            if key in ("id", "story_id", "created_at_chapter", "resolved_at_chapter", "status"):
                continue  # 受保护字段，通过专门工具修改
            if key in Foreshadowing.model_fields:
                self.repo.update_foreshadowing_field(fw_id, key, value)
                changes.append(key)
        return {"updated": True, "fw_id": fw_id, "changes": changes}

    def get_plot_tree(self) -> list[dict]:
        """获取剧情层级树"""
        self.load()
        roots = [p for p in self._plots.values() if not getattr(p, 'parent_id', '')]
        def build_node(pl):
            children = [p for p in self._plots.values()
                       if getattr(p, 'parent_id', '') == pl.id]
            return {
                "id": pl.id, "name": pl.name,
                "level": getattr(pl, 'level', pl.plot_type.value),
                "plot_type": pl.plot_type.value,
                "status": pl.status.value,
                "progress": pl.progress_percent(),
                "children": [build_node(c) for c in children],
            }
        return [build_node(r) for r in roots]

    # ═══ 情节点管理 ═════════════════════════════════════════════

    def add_plot_point(self, plot_id: str, title: str, description: str = "",
                       chapter_assigned: int = 0, emotional_tone: str = "",
                       prerequisites: list[str] | None = None,
                       impacts_characters: list[str] | None = None,
                       estimated_words: int = 0) -> PlotPoint:
        pl = self.get_plot_line(plot_id)
        if not pl:
            raise ValueError(f"Plot line '{plot_id}' not found")
        pp = PlotPoint(
            id=f"{plot_id}_pp{len(pl.plot_points)+1:03d}",
            title=title, description=description,
            order_index=len(pl.plot_points) + 1,
            chapter_assigned=chapter_assigned,
            emotional_tone=emotional_tone,
            prerequisites=prerequisites or [],
            impacts_characters=impacts_characters or [],
            estimated_words=estimated_words,
        )
        pp_dict = pp.model_dump(mode="json")
        pp_dict["plot_id"] = plot_id
        self.repo.save_plot_point(pp_dict)
        pl.plot_points.append(pp)
        return pp

    def update_plot_point_status(self, plot_id: str, point_id: str,
                                 status: str) -> PlotPoint:
        pp = self._get_plot_point(plot_id, point_id)
        pp.status = PlotPointStatus(status)
        self.repo.update_point_field(point_id, "status", status)
        return pp

    def assign_plot_point(self, plot_id: str, point_id: str, chapter: int) -> PlotPoint:
        pp = self._get_plot_point(plot_id, point_id)
        pp.chapter_assigned = chapter
        self.repo.update_point_field(point_id, "chapter_assigned", chapter)
        return pp

    def _get_plot_point(self, plot_id: str, point_id: str) -> PlotPoint:
        pl = self.get_plot_line(plot_id)
        if not pl:
            raise ValueError(f"Plot line '{plot_id}' not found")
        for pp in pl.plot_points:
            if pp.id == point_id:
                return pp
        raise ValueError(f"Plot point '{point_id}' not found")

    # ═══ 剧情追踪 ═══════════════════════════════════════════════

    def track_plot_progress(self) -> list[dict]:
        self.load()
        report = []
        for pl in self._plots.values():
            report.append({
                "id": pl.id, "name": pl.name,
                "type": pl.plot_type.value,
                "level": getattr(pl, 'level', pl.plot_type.value),
                "status": pl.status.value,
                "total_points": len(pl.plot_points),
                "done_points": sum(1 for p in pl.plot_points if p.status == PlotPointStatus.DONE),
                "progress_percent": pl.progress_percent(),
                "dangling": pl.dangling(),
            })
        return report

    def find_dangling_plots(self) -> list[PlotLine]:
        self.load()
        return [pl for pl in self._plots.values() if pl.dangling()]

    def get_chapter_plot_summary(self, chapter_number: int) -> dict:
        self.load()
        summary = {"main_plots": [], "sub_plots": [], "plot_points": []}
        for pl in self._plots.values():
            for pp in pl.plot_points:
                if pp.chapter_assigned == chapter_number:
                    entry = {
                        "plot_id": pl.id, "plot_name": pl.name,
                        "plot_type": pl.plot_type.value,
                        "point_id": pp.id, "point_title": pp.title,
                        "point_status": pp.status.value,
                        "emotional_tone": pp.emotional_tone,
                    }
                    summary["plot_points"].append(entry)
                    if pl.plot_type == PlotType.MAIN:
                        summary["main_plots"].append(entry)
                    else:
                        summary["sub_plots"].append(entry)
        return summary

    # ═══ 剧情交汇 ═══════════════════════════════════════════════

    def add_intersection(self, plot_a: str, plot_b: str,
                         at_point_a: str, at_point_b: str,
                         description: str = "", chapter_hint: int = 0) -> PlotIntersection:
        intersection = PlotIntersection(
            plot_a=plot_a, plot_b=plot_b,
            at_plot_point_a=at_point_a, at_plot_point_b=at_point_b,
            description=description, chapter_hint=chapter_hint,
        )
        inter_dict = intersection.model_dump(mode="json")
        inter_dict["id"] = f"inter_{plot_a}_{plot_b}"
        self.repo.save_intersection(inter_dict)

        for pid in (plot_a, plot_b):
            pl = self.get_plot_line(pid)
            if pl:
                pl.intersects_with.append(intersection)
        return intersection

    def list_intersections(self) -> list[PlotIntersection]:
        rows = self.repo.list_all_intersections()
        return [PlotIntersection(**r) for r in rows]

    # ═══ 健康度检查 ═════════════════════════════════════════════

    def plot_interweave_check(self) -> dict:
        self.load()
        result = {"healthy": True, "warnings": [], "metrics": {}, "suggestions": []}

        main_plots = [p for p in self._plots.values() if p.plot_type == PlotType.MAIN]
        sub_plots = [p for p in self._plots.values() if p.plot_type == PlotType.SUB]

        result["metrics"] = {
            "total_plots": len(self._plots),
            "main_plots": len(main_plots),
            "sub_plots": len(sub_plots),
            "completed_plots": sum(1 for p in self._plots.values() if p.status == PlotLineStatus.COMPLETED),
            "dangling_plots": len(self.find_dangling_plots()),
            "total_intersections": len(self.list_intersections()),
        }

        if not main_plots:
            result["healthy"] = False
            result["warnings"].append("没有主线！请至少设置一条主线剧情。")
        if len(sub_plots) == 0:
            result["warnings"].append("没有支线。建议添加支线丰富剧情层次。")

        for sp in sub_plots:
            has_main_inter = any(
                inter.plot_a in [mp.id for mp in main_plots] or
                inter.plot_b in [mp.id for mp in main_plots]
                for inter in sp.intersects_with
            )
            if not has_main_inter:
                result["warnings"].append(f"支线 '{sp.name}' 未与主线交汇！")
                result["healthy"] = False

        unassigned = []
        for pl in self._plots.values():
            for pp in pl.plot_points:
                if pp.chapter_assigned == 0 and pp.status != PlotPointStatus.DONE:
                    unassigned.append(f"  [{pl.name}] {pp.title}")
        if unassigned:
            msg = f"有 {len(unassigned)} 个情节点未分配章节：\n" + "\n".join(unassigned[:10])
            if len(unassigned) > 10:
                msg += f"\n  ... 还有 {len(unassigned)-10} 个"
            result["warnings"].append(msg)

        if result["metrics"]["dangling_plots"] > 3:
            result["suggestions"].append("未收束支线较多，建议按优先级逐步收束。")
        if result["metrics"]["total_intersections"] == 0 and len(sub_plots) > 0:
            result["suggestions"].append("支线与主线之间没有设置交汇点，建议在关键章节安排交汇。")

        return result

    # ═══ 伏笔管理 ═══════════════════════════════════════════════

    def add_foreshadowing(self, description: str, created_at_chapter: int = 0,
                          target_chapter: int = 0, urgency: str = "medium",
                          related_plot_lines: list[str] | None = None,
                          related_characters: list[str] | None = None,
                          created_at_volume: int = 0, notes: str = "") -> Foreshadowing:
        """添加伏笔"""
        fw_id = f"fw_{self.repo.next_foreshadowing_number():03d}"
        fw = Foreshadowing(
            id=fw_id, description=description,
            created_at_chapter=created_at_chapter,
            created_at_volume=created_at_volume,
            target_chapter=target_chapter,
            urgency=urgency,
            status=ForeshadowingStatus.PENDING,
            related_plot_lines=related_plot_lines or [],
            related_characters=related_characters or [],
            notes=notes,
        )
        fw_dict = fw.model_dump(mode="json")
        fw_dict["status"] = fw.status.value
        self.repo.save_foreshadowing(fw_dict)
        return fw

    def get_foreshadowing(self, fw_id: str) -> Optional[Foreshadowing]:
        """获取单个伏笔"""
        row = self.repo.load_foreshadowing(fw_id)
        if not row:
            return None
        return self._row_to_foreshadowing(row)

    def list_foreshadowings(self, status: str = "") -> list[Foreshadowing]:
        """列出伏笔（可按状态过滤）"""
        rows = self.repo.list_foreshadowings(status)
        return [self._row_to_foreshadowing(r) for r in rows]

    def list_dangling_foreshadowings(self) -> list[Foreshadowing]:
        """列出未回收的伏笔"""
        rows = self.repo.list_dangling_foreshadowings()
        return [self._row_to_foreshadowing(r) for r in rows]

    def resolve_foreshadowing(self, fw_id: str, chapter_number: int,
                              notes: str = "") -> Optional[Foreshadowing]:
        """回收伏笔"""
        self.repo.update_foreshadowing_field(fw_id, "status", "resolved")
        self.repo.update_foreshadowing_field(fw_id, "resolved_at_chapter", chapter_number)
        if notes:
            self.repo.update_foreshadowing_field(fw_id, "resolution_notes", notes)
        row = self.repo.load_foreshadowing(fw_id)
        return self._row_to_foreshadowing(row) if row else None

    def check_foreshadowing_health(self, current_chapter: int = 0) -> dict:
        """伏笔健康检查"""
        stats = self.repo.get_foreshadowing_stats(current_chapter)
        warnings = []
        if stats["critical"] > 0:
            warnings.append(f"有 {stats['critical']} 个紧急伏笔待回收！")
        if stats["old_unresolved"] > 0:
            warnings.append(
                f"有 {stats['old_unresolved']} 个伏笔已埋超过30章，建议近期回收。"
            )
        return {
            "healthy": len(warnings) == 0,
            "stats": stats,
            "warnings": warnings,
        }

    def _row_to_foreshadowing(self, row: dict) -> Foreshadowing:
        """将 DB 行转换为 Foreshadowing 模型"""
        status_raw = row.get("status", "pending")
        status = ForeshadowingStatus(status_raw) if status_raw in (
            "pending", "partially_resolved", "resolved", "abandoned"
        ) else ForeshadowingStatus.PENDING
        return Foreshadowing(
            id=row.get("id", ""),
            story_id=row.get("story_id", "main"),
            description=row.get("description", ""),
            created_at_chapter=row.get("created_at_chapter", 0),
            created_at_volume=row.get("created_at_volume", 0),
            target_chapter=row.get("target_chapter", 0),
            resolved_at_chapter=row.get("resolved_at_chapter", 0),
            status=status,
            urgency=row.get("urgency", "medium"),
            related_plot_lines=row.get("related_plot_lines", []),
            related_characters=row.get("related_characters", []),
            resolution_notes=row.get("resolution_notes", ""),
            notes=row.get("notes", ""),
        )

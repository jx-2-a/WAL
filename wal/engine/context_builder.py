"""上下文组装器 — 为写作会话组装完整上下文"""

from pathlib import Path
from typing import Optional

from ..core.story_manager import StoryManager
from ..core.plot_manager import PlotManager
from ..core.char_manager import CharacterManager
from ..core.world_manager import WorldManager


class ContextBuilder:
    """为目标章节组装写作所需的完整上下文"""

    def __init__(self, story_manager: StoryManager, plot_manager: PlotManager,
                 char_manager: CharacterManager, world_manager: WorldManager):
        self.story = story_manager
        self.plot = plot_manager
        self.char = char_manager
        self.world = world_manager

    def build_writing_context(self, chapter_number: int) -> dict:
        """为目标章节组装写作上下文"""
        story = self.story.get_story()
        if not story:
            return {"error": "No story loaded"}

        chapter = self.story.get_chapter(chapter_number)
        if not chapter:
            return {"error": f"Chapter {chapter_number} not found"}

        # 本章剧情
        chapter_plots = self._build_chapter_plots(chapter_number)

        # 本章角色
        chapter_characters = self._build_chapter_characters(chapter)

        # 前一章摘要
        prev_summary = self._get_prev_chapter_summary(chapter_number)

        # 未收束支线提醒
        dangling = self.plot.find_dangling_plots()

        # 世界观
        world_summary = self.world.get_world_summary()

        return {
            "story_name": story.name,
            "story_summary": story.summary,
            "chapter_number": chapter_number,
            "chapter_title": chapter.title,
            "chapter_summary": chapter.summary,
            "target_words": chapter.word_count_target,
            "prev_chapter_summary": prev_summary,
            "chapter_plots": chapter_plots,
            "characters": chapter_characters,
            "dangling_plots": [
                {"name": dp.name, "description": dp.description, "progress": dp.progress_percent()}
                for dp in dangling
            ],
            "world_summary": world_summary,
            "scenes": [
                {"title": s.title, "location": s.location_id,
                 "time": s.time_point, "characters": s.characters_present}
                for s in chapter.scenes
            ],
            "plot_health": self.plot.plot_interweave_check(),
        }

    def _build_chapter_plots(self, chapter_number: int) -> list[dict]:
        """构建本章需要推进的剧情线列表"""
        summary = self.plot.get_chapter_plot_summary(chapter_number)
        result = []
        for pp in summary["plot_points"]:
            result.append({
                "plot_id": pp["plot_id"],
                "name": pp["plot_name"],
                "type": pp["plot_type"],
                "point_title": pp["point_title"],
                "task": f"推进情节点「{pp['point_title']}」",
                "emotional_tone": pp["emotional_tone"],
                "status": pp["point_status"],
            })
        return result

    def _build_chapter_characters(self, chapter) -> list[dict]:
        """构建本章出场角色档案"""
        result = []
        for scene in chapter.scenes:
            for char_id in scene.characters_present:
                char = self.char.get_character(char_id)
                if char:
                    result.append({
                        "id": char.id,
                        "name": char.name,
                        "role": char.role,
                        "description": f"{char.personality_traits} | {char.background_story[:100]}",
                        "motivation": char.motivation,
                        "current_state": char.arc_progress or "无特殊变化",
                    })
        # 去重
        seen = set()
        unique = []
        for r in result:
            if r["id"] not in seen:
                seen.add(r["id"])
                unique.append(r)
        return unique

    def _get_prev_chapter_summary(self, chapter_number: int) -> str:
        """获取前一章摘要"""
        if chapter_number <= 1:
            return "这是第一章，没有前一章。"
        prev = self.story.get_chapter(chapter_number - 1)
        if prev and prev.summary:
            return f"第{chapter_number-1}章《{prev.title}》摘要：{prev.summary}"
        return f"第{chapter_number-1}章暂无摘要。"

    def build_volume_context(self, volume_id: str) -> dict:
        """为指定卷组装写作上下文（卷级视角）"""
        ctx = self.story.get_volume_context(volume_id)
        if "error" in ctx:
            return ctx

        story = self.story.get_story()
        ctx["story_name"] = story.name if story else ""
        ctx["story_summary"] = story.summary if story else ""

        # 卷内各章的剧情摘要
        chapter_plots = {}
        for ch_info in ctx.get("chapters", []):
            summary = self.plot.get_chapter_plot_summary(ch_info["number"])
            chapter_plots[ch_info["number"]] = summary

        ctx["chapter_plots"] = chapter_plots

        # 卷级伏笔检查
        foreshadowing_health = self.plot.check_foreshadowing_health()
        ctx["foreshadowing_health"] = foreshadowing_health

        # 世界观（精简）
        ctx["world_summary"] = self.world.get_world_summary()

        return ctx

    def build_compact_volume_context(self, volume_id: str) -> str:
        """构建卷级精简上下文文本"""
        ctx = self.build_volume_context(volume_id)
        if "error" in ctx:
            return ctx["error"]

        lines = [
            f"你正在写作小说《{ctx.get('story_name', '')}》。",
            f"故事简介：{ctx.get('story_summary', '')}",
            "",
            f"=== 第{ctx.get('volume_number', '?')}卷《{ctx.get('volume_title', '?')}》 ===",
            f"卷主题：{ctx.get('theme', '（未设定）')}",
            f"卷摘要：{ctx.get('summary', '（暂无）')}",
            f"进度：{ctx.get('done_chapters', 0)}/{ctx.get('chapter_count', 0)} 章完成",
            f"总字数：{ctx.get('total_words', 0)} 字",
            "",
        ]

        if ctx.get("chapters"):
            lines.append("## 卷内章节")
            for ch in ctx["chapters"]:
                lines.append(f"- 第{ch['number']}章《{ch['title']}》[{ch['status']}] "
                           f"{ch['words']}字")
                if ch.get("summary"):
                    lines.append(f"  {ch['summary'][:80]}")
            lines.append("")

        fw = ctx.get("foreshadowing_health", {})
        if fw.get("warnings"):
            lines.append("## ⚠️ 伏笔提醒")
            for w in fw["warnings"]:
                lines.append(f"- {w}")
            lines.append("")

        return "\n".join(lines)

    def build_compact_context(self, chapter_number: int) -> str:
        """构建精简上下文文本（适合作为 system prompt）"""
        ctx = self.build_writing_context(chapter_number)
        if "error" in ctx:
            return ctx["error"]

        lines = [
            f"你正在写作小说《{ctx['story_name']}》。",
            f"故事简介：{ctx['story_summary']}",
            "",
            f"=== 第{ctx['chapter_number']}章《{ctx['chapter_title']}》 ===",
            f"本章摘要：{ctx['chapter_summary']}",
            f"字数目标：{ctx['target_words']}字",
            f"前一章：{ctx['prev_chapter_summary']}",
            "",
        ]

        # 剧情任务
        if ctx["chapter_plots"]:
            lines.append("## 本章剧情任务")
            for pp in ctx["chapter_plots"]:
                lines.append(f"- [{pp['type']}] {pp['name']}: {pp['task']}")
            lines.append("")

        # 出场角色
        if ctx["characters"]:
            lines.append("## 出场角色")
            for char in ctx["characters"]:
                lines.append(f"- {char['name']}（{char['role']}）：{char['motivation']}")
            lines.append("")

        # 未完成支线
        if ctx["dangling_plots"]:
            lines.append("## ⚠️ 未收束的支线（请在合适时机推进）")
            for dp in ctx["dangling_plots"]:
                lines.append(f"- {dp['name']}（完成度：{dp['progress']}%）")

        # 场景规划
        if ctx["scenes"]:
            lines.append("\n## 本章场景规划")
            for s in ctx["scenes"]:
                lines.append(f"- {s['title']} | 地点：{s['location']} | 时间：{s['time']}")

        return "\n".join(lines)

    def build_full_context(self, chapter_number: int | None = None,
                           volume_id: str | None = None) -> dict:
        """统一上下文入口 — 构建最完整的写作上下文

        根据参数自动选择章节级或卷级上下文，并聚合所有子系统数据：
        故事管理 + 剧情 + 角色快照 + 伏笔 + 世界观 + FTS5 关键词索引

        Args:
            chapter_number: 章节号（章节级上下文）
            volume_id: 卷ID（卷级上下文）

        Returns:
            包含所有子系统数据的完整上下文字典
        """
        story = self.story.get_story()
        if not story:
            return {"error": "No story loaded"}

        result = {
            "story_name": story.name,
            "story_summary": story.summary,
            "story_genre": getattr(story, "genre", ""),
            "story_status": getattr(story, "status", ""),
        }

        # 章节级上下文
        if chapter_number is not None:
            ch_context = self.build_writing_context(chapter_number)
            if "error" not in ch_context:
                result.update(ch_context)

        # 卷级上下文
        if volume_id:
            vol_context = self.build_volume_context(volume_id)
            if "error" not in vol_context:
                result["volume_context"] = vol_context

        # 剧情完整状态
        try:
            result["plot_tree"] = self.plot.get_plot_tree()
            result["dangling_plots"] = [
                {"name": dp.name, "description": dp.description,
                 "progress": dp.progress_percent(), "level": getattr(dp, "level", "sub")}
                for dp in self.plot.find_dangling_plots()
            ]
            result["foreshadowing_health"] = self.plot.check_foreshadowing_health()
            result["plot_interweave"] = self.plot.plot_interweave_check()
        except Exception:
            result["plot_tree"] = []
            result["dangling_plots"] = []
            result["foreshadowing_health"] = {}
            result["plot_interweave"] = {}

        # 角色概要
        try:
            all_chars = self.char.list_characters()
            result["character_count"] = len(all_chars)
            result["characters_summary"] = [
                {"id": c.id, "name": c.name, "role": c.role,
                 "arc_progress": getattr(c, "arc_progress", "")}
                for c in all_chars[:30]  # 最多 30 个角色概要
            ]
        except Exception:
            result["character_count"] = 0
            result["characters_summary"] = []

        # 世界观概要
        try:
            result["world_summary"] = self.world.get_world_summary()
        except Exception:
            result["world_summary"] = ""

        # 全文搜索关键词索引（从索引管理器获取）
        try:
            project_dir = str(getattr(self.story, "project_dir", ""))
            if project_dir:
                from ..core.index_manager import IndexManager
                im = IndexManager(project_dir)
                keywords = im.list_keywords()[:20]
                result["top_keywords"] = keywords
        except Exception:
            result["top_keywords"] = []

        return result

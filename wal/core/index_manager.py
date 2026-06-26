"""索引管理器 — FTS5 全文搜索、关键词索引、里程碑、快速回顾

基于 SQLite FTS5 虚拟表 + content_index 表。
提供百万字级快速检索能力。
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from ..storage.database import Database
from ..storage.index_repo import IndexRepository
from ..storage.story_repo import StoryRepository


class IndexManager:
    """内容索引与全文搜索管理器"""

    def __init__(self, project_dir: str):
        self.project_dir = Path(project_dir)
        self.project_dir.mkdir(parents=True, exist_ok=True)

        db_path = self.project_dir / "wal.db"
        self.db = Database(str(db_path))
        self.repo = IndexRepository(self.db)
        self.story_repo = StoryRepository(self.db)

        if not self.db.schema_exists():
            self.db.init_schema()

        self._ensure_story_exists()

    def _ensure_story_exists(self) -> None:
        conn = self.db.get_conn()
        row = conn.execute("SELECT id FROM stories WHERE id = 'main'").fetchone()
        if not row:
            now = datetime.now().isoformat()
            conn.execute(
                "INSERT INTO stories (id, name, author, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("main", "", "", "planning", now, now),
            )
            conn.commit()

    # ═══ FTS5 全文搜索 ═══════════════════════════════════════════

    def search(self, query: str, limit: int = 20) -> list[dict]:
        """FTS5 全文搜索 — 搜索所有已索引场景

        返回匹配场景的高亮片段、所属章节、出场角色等。
        支持 FTS5 查询语法：'word1 AND word2', 'word*', 等。
        """
        return self.repo.search_fulltext(query, limit)

    def search_chapter_range(self, start_ch: int, end_ch: int,
                             keyword: str = "", limit: int = 30) -> list[dict]:
        """在章节范围内全文搜索

        Args:
            start_ch: 起始章节号
            end_ch: 结束章节号
            keyword: 搜索关键词（支持 FTS5 语法）
            limit: 最大返回条数

        Example:
            search_chapter_range(30, 40, "叶凡 AND 突破") → 30-40章中关于叶凡突破的片段
        """
        return self.repo.search_chapter_range(start_ch, end_ch, keyword, limit)

    # ═══ 自动索引 ═════════════════════════════════════════════════

    def auto_index_chapter(self, chapter_number: int) -> dict:
        """自动索引一个章节：将场景内容写入 FTS5 + 提取关键词

        返回索引统计。
        """
        # 获取章节
        chapters = self.story_repo.list_chapters()
        chapter = None
        for ch in chapters:
            if ch.get("number") == chapter_number:
                chapter = ch
                break

        if not chapter:
            return {"error": f"Chapter {chapter_number} not found"}

        ch_id = chapter["id"]
        ch_title = chapter.get("title", "")
        ch_summary = chapter.get("summary", "")

        # 获取场景
        scenes = self.story_repo.list_scenes_by_chapter(ch_id)
        indexed_count = 0
        characters_seen = set()
        locations_seen = set()

        for sc in scenes:
            content = sc.get("content", "")
            if not content:
                continue

            chars_present_raw = sc.get("characters_present", "")
            location = sc.get("location_id", "")
            plot_adv = sc.get("plot_advancements", "")

            # 确保字段是字符串（DB 反序列化后可能是 list）
            if isinstance(chars_present_raw, list):
                chars_present_str = ", ".join(chars_present_raw)
            else:
                chars_present_str = str(chars_present_raw) if chars_present_raw else ""
            if isinstance(plot_adv, list):
                plot_adv_str = ", ".join(plot_adv)
            else:
                plot_adv_str = str(plot_adv) if plot_adv else ""

            # 索引到 FTS5
            self.repo.index_scene(
                chapter_id=ch_id,
                chapter_title=ch_title,
                chapter_summary=ch_summary,
                scene_id=sc["id"],
                scene_title=sc.get("title", ""),
                content=content,
                characters_present=chars_present_str,
                location=str(location) if location else "",
                plot_references=plot_adv_str,
            )
            indexed_count += 1

            # 收集角色和地点
            if chars_present_raw:
                if isinstance(chars_present_raw, list):
                    for c in chars_present_raw:
                        c = str(c).strip()
                        if c:
                            characters_seen.add(c)
                else:
                    for c in str(chars_present_raw).split(","):
                        c = c.strip()
                        if c:
                            characters_seen.add(c)
            if location:
                locations_seen.add(str(location).strip())

        # 更新关键词索引（角色名、地点名）
        from ..core.char_manager import CharacterManager
        cm = CharacterManager(str(self.project_dir))
        cm.load()

        for char_name in characters_seen:
            self._index_keyword(char_name, "character", chapter_number)

        for loc_name in locations_seen:
            self._index_keyword(loc_name, "location", chapter_number)

        # 索引章节本身
        if ch_title:
            self._index_keyword(ch_title, "chapter", chapter_number)

        return {
            "chapter_number": chapter_number,
            "chapter_title": ch_title,
            "scenes_indexed": indexed_count,
            "characters_found": sorted(characters_seen),
            "locations_found": sorted(locations_seen),
        }

    def rebuild_all_indexes(self) -> dict:
        """全量重建 FTS5 索引"""
        count = self.repo.rebuild_fts_index()
        return {"fts_scenes_rebuilt": count}

    def _index_keyword(self, keyword: str, category: str,
                       chapter_number: int, summary: str = "",
                       importance: str = "medium") -> str:
        """内部：索引单个关键词"""
        import json
        existing = self.repo.load_index_entry(keyword, category)
        if existing:
            refs = existing.get("chapter_references", [])
            if chapter_number not in refs:
                refs.append(chapter_number)
                refs.sort()
            entry_id = existing["id"]
            summary_context = existing.get("summary_context", summary or existing.get("summary_context", ""))
        else:
            entry_id = f"idx_{category}_{keyword}"
            refs = [chapter_number]
            summary_context = summary or ""

        self.repo.save_index_entry({
            "id": entry_id,
            "keyword": keyword,
            "category": category,
            "chapter_references": refs,
            "summary_context": summary_context,
            "first_appearance_chapter": refs[0],
            "last_appearance_chapter": refs[-1],
            "importance": importance,
        })
        return entry_id

    # ═══ 章节摘要生成 ═════════════════════════════════════════════

    def generate_chapter_summary(self, chapter_number: int) -> dict:
        """为一章生成结构化摘要

        从已索引数据、章节元数据组装，不需要 LLM。
        包含：字数统计、出场角色、涉及地点、剧情推进点。
        """
        chapters = self.story_repo.list_chapters()
        chapter = None
        for ch in chapters:
            if ch.get("number") == chapter_number:
                chapter = ch
                break

        if not chapter:
            return {"error": f"Chapter {chapter_number} not found"}

        ch_id = chapter["id"]
        scenes = self.story_repo.list_scenes_by_chapter(ch_id)

        total_words = 0
        all_characters = set()
        all_locations = set()
        scene_summaries = []

        for sc in scenes:
            content = sc.get("content", "")
            total_words += len(content)
            chars = sc.get("characters_present", "")
            if chars:
                if isinstance(chars, list):
                    for c in chars:
                        c = str(c).strip()
                        if c:
                            all_characters.add(c)
                else:
                    for c in str(chars).split(","):
                        c = c.strip()
                        if c:
                            all_characters.add(c)
            loc = sc.get("location_id", "")
            if loc:
                all_locations.add(str(loc).strip())
            scene_summaries.append({
                "title": sc.get("title", ""),
                "word_count": len(content),
                "time_point": sc.get("time_point", ""),
                "location": loc,
            })

        # 获取该章的索引条目
        index_entries = self.repo.get_entries_by_chapter(chapter_number)

        # 获取该章的剧情点
        from ..core.plot_manager import PlotManager
        pm = PlotManager(str(self.project_dir))
        pm.load()
        plot_summary = pm.get_chapter_plot_summary(chapter_number)

        return {
            "chapter_number": chapter_number,
            "chapter_title": chapter.get("title", ""),
            "chapter_summary": chapter.get("summary", ""),
            "word_count_actual": total_words,
            "word_count_target": chapter.get("word_count_target", 0),
            "scene_count": len(scenes),
            "scenes": scene_summaries,
            "characters": sorted(all_characters),
            "locations": sorted(all_locations),
            "plot_points": plot_summary.get("plot_points", []),
            "index_entries": [
                {"keyword": e["keyword"], "category": e["category"]}
                for e in index_entries
            ],
        }

    # ═══ 快速回顾 ═════════════════════════════════════════════════

    def quick_review(self, start_ch: int, end_ch: int,
                     topic: str = "") -> dict:
        """快速回顾某段章节范围的内容

        Args:
            start_ch: 起始章节
            end_ch: 结束章节
            topic: 回顾主题（可选，用于关键词过滤）

        Returns:
            章节摘要列表 + FTS5 搜索结果（如有 topic）
        """
        chapters = self.story_repo.list_chapters()
        range_chapters = [ch for ch in chapters
                         if start_ch <= ch.get("number", 0) <= end_ch]
        range_chapters.sort(key=lambda c: c.get("number", 0))

        chapter_summaries = []
        total_words = 0

        for ch in range_chapters:
            ch_id = ch["id"]
            scenes = self.story_repo.list_scenes_by_chapter(ch_id)
            ch_words = sum(len(s.get("content", "")) for s in scenes)
            total_words += ch_words
            chapter_summaries.append({
                "number": ch.get("number", 0),
                "title": ch.get("title", ""),
                "summary": ch.get("summary", ""),
                "status": ch.get("status", ""),
                "word_count": ch_words,
                "scene_count": len(scenes),
            })

        result = {
            "range": f"第{start_ch}章 - 第{end_ch}章",
            "chapter_count": len(range_chapters),
            "total_words": total_words,
            "chapters": chapter_summaries,
        }

        # 如果有指定主题，进行全文搜索
        if topic:
            fts_results = self.search_chapter_range(start_ch, end_ch, topic, limit=15)
            result["topic"] = topic
            result["fts_matches"] = [
                {
                    "chapter_title": r.get("chapter_title", ""),
                    "scene_title": r.get("scene_title", ""),
                    "snippet": r.get("snippet", ""),
                }
                for r in fts_results
            ]
            result["match_count"] = len(fts_results)

        return result

    # ═══ 里程碑 ═══════════════════════════════════════════════════

    def create_milestone(self, name: str, chapter_number: int,
                         volume_number: int = 0,
                         story_state_summary: str = "",
                         character_states: dict | None = None,
                         plot_states: dict | None = None,
                         unresolved_foreshadowings: list[str] | None = None,
                         total_words_at_point: int = 0) -> dict:
        """创建故事里程碑

        在关键节点（如卷完成、重大转折）保存快照，
        方便日后回溯故事发展轨迹。
        """
        ms_id = f"ms_{chapter_number:04d}"
        ms_data = {
            "id": ms_id,
            "name": name,
            "chapter_number": chapter_number,
            "volume_number": volume_number,
            "story_state_summary": story_state_summary,
            "character_states": character_states or {},
            "plot_states": plot_states or {},
            "unresolved_foreshadowings": unresolved_foreshadowings or [],
            "total_words_at_point": total_words_at_point,
            "created_at": datetime.now().isoformat(),
        }
        self.repo.save_milestone(ms_data)
        return ms_data

    def auto_create_milestone(self, chapter_number: int) -> dict:
        """自动创建里程碑 — 从当前状态快照

        收集当前角色状态、剧情状态、伏笔状态。
        """
        from ..core.char_manager import CharacterManager
        from ..core.plot_manager import PlotManager

        # 章节信息
        chapters = self.story_repo.list_chapters()
        chapter = None
        total_words = 0
        for ch in chapters:
            ch_id = ch["id"]
            scenes = self.story_repo.list_scenes_by_chapter(ch_id)
            ch_words = sum(len(s.get("content", "")) for s in scenes)
            total_words += ch_words
            if ch.get("number") == chapter_number:
                chapter = ch

        if not chapter:
            return {"error": f"Chapter {chapter_number} not found"}

        # 角色状态
        cm = CharacterManager(str(self.project_dir))
        cm.load()
        character_states = {}
        for char in cm.list_characters():
            character_states[char.name] = {
                "role": char.role,
                "arc_progress": char.arc_progress,
                "motivation": char.motivation,
            }

        # 剧情状态
        pm = PlotManager(str(self.project_dir))
        pm.load()
        plot_states = {}
        for pl in pm.list_plot_lines():
            plot_states[pl.name] = {
                "status": pl.status.value,
                "progress": pl.progress_percent(),
                "level": pl.level.value,
            }

        # 伏笔状态
        fw_health = pm.check_foreshadowing_health(current_chapter=chapter_number)
        dangling_fws = pm.list_dangling_foreshadowings()
        unresolved = [f"{fw.id}: {fw.description[:50]}" for fw in dangling_fws[:10]]

        return self.create_milestone(
            name=f"第{chapter_number}章《{chapter.get('title', '')}》",
            chapter_number=chapter_number,
            story_state_summary=f"自动里程碑 — 第{chapter_number}章完成",
            character_states=character_states,
            plot_states=plot_states,
            unresolved_foreshadowings=unresolved,
            total_words_at_point=total_words,
        )

    def list_milestones(self) -> list[dict]:
        """列出所有里程碑"""
        return self.repo.list_milestones()

    def get_milestone(self, ms_id: str) -> Optional[dict]:
        """获取单个里程碑"""
        return self.repo.load_milestone(ms_id)

    def get_latest_milestone(self) -> Optional[dict]:
        """获取最近的里程碑"""
        return self.repo.get_latest_milestone()

    # ═══ 关键词索引 ═══════════════════════════════════════════════

    def add_keyword(self, keyword: str, category: str,
                    chapter_number: int = 0, summary: str = "",
                    importance: str = "medium") -> dict:
        """手动添加关键词索引"""
        entry_id = self._index_keyword(keyword, category, chapter_number,
                                       summary, importance)
        return {"id": entry_id, "keyword": keyword, "category": category}

    def search_by_keyword(self, keyword: str) -> list[dict]:
        """按关键词搜索索引"""
        return self.repo.search_by_keyword(keyword)

    def list_keywords(self, category: str = "") -> list[dict]:
        """列出所有关键词索引"""
        return self.repo.list_index_entries(category)

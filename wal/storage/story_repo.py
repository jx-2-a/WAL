"""故事仓库 — SQLite 版

管理 stories, parts, volumes, chapters, scenes 表的 CRUD。
替代原 YAML 版 StoryRepository。
"""

import json
from datetime import datetime
from typing import Optional

from .db_repo import DatabaseRepository


class StoryRepository(DatabaseRepository):
    """故事结构数据仓库（SQLite）"""

    STORY_ID = "main"

    # ═══ 故事元数据 ═══════════════════════════════════════════════

    def save_story(self, story_data: dict) -> None:
        """保存/更新故事元数据"""
        data = {
            "id": self.STORY_ID,
            "name": story_data.get("name", ""),
            "author": story_data.get("author", ""),
            "summary": story_data.get("summary", ""),
            "genre": story_data.get("genre", ""),
            "tags": self._to_json(story_data.get("tags", [])),
            "status": story_data.get("status", "planning"),
            "created_at": story_data.get("created_at", ""),
            "updated_at": story_data.get("updated_at", datetime.now().isoformat()),
            "notes": story_data.get("notes", ""),
            "style": story_data.get("style", ""),
        }
        self._insert_or_replace("stories", data)

    def load_story(self) -> Optional[dict]:
        """加载故事元数据"""
        row = self._fetch_one("SELECT * FROM stories WHERE id = ?", (self.STORY_ID,))
        if not row:
            return None
        row["tags"] = self._from_json(row["tags"])
        return row

    def story_exists(self) -> bool:
        return self._exists("stories", "id = ?", (self.STORY_ID,))

    def update_story_field(self, key: str, value) -> None:
        self._update("stories", {key: value, "updated_at": datetime.now().isoformat()},
                     "id = ?", (self.STORY_ID,))

    # ═══ 部/篇 ═══════════════════════════════════════════════════

    def save_part(self, part_data: dict) -> None:
        self._insert_or_replace("parts", {
            "id": part_data.get("id", ""),
            "story_id": self.STORY_ID,
            "number": part_data.get("number", 0),
            "title": part_data.get("title", ""),
            "summary": part_data.get("summary", ""),
            "notes": part_data.get("notes", ""),
        })

    def load_part(self, part_id: str) -> Optional[dict]:
        return self._fetch_one("SELECT * FROM parts WHERE id = ?", (part_id,))

    def list_parts(self) -> list[dict]:
        return self._fetch_all(
            "SELECT * FROM parts WHERE story_id = ? ORDER BY number", (self.STORY_ID,)
        )

    def delete_part(self, part_id: str) -> int:
        return self._delete("parts", "id = ?", (part_id,))

    def next_part_number(self) -> int:
        return self._count("parts", "story_id = ?", (self.STORY_ID,)) + 1

    # ═══ 卷 ═══════════════════════════════════════════════════════

    def save_volume(self, volume_data: dict) -> None:
        self._insert_or_replace("volumes", {
            "id": volume_data.get("id", ""),
            "part_id": volume_data.get("part_id") or None,
            "story_id": self.STORY_ID,
            "number": volume_data.get("number", 0),
            "title": volume_data.get("title", ""),
            "summary": volume_data.get("summary", ""),
            "theme": volume_data.get("theme", ""),
            "status": volume_data.get("status", "planning"),
            "notes": volume_data.get("notes", ""),
        })

    def load_volume(self, volume_id: str) -> Optional[dict]:
        return self._fetch_one("SELECT * FROM volumes WHERE id = ?", (volume_id,))

    def get_volume_by_number(self, number: int, part_id: str = "") -> Optional[dict]:
        if part_id:
            return self._fetch_one(
                "SELECT * FROM volumes WHERE story_id = ? AND number = ? AND part_id = ?",
                (self.STORY_ID, number, part_id),
            )
        return self._fetch_one(
            "SELECT * FROM volumes WHERE story_id = ? AND number = ?",
            (self.STORY_ID, number),
        )

    def list_volumes(self, part_id: str = "") -> list[dict]:
        if part_id:
            return self._fetch_all(
                "SELECT * FROM volumes WHERE story_id = ? AND part_id = ? ORDER BY number",
                (self.STORY_ID, part_id),
            )
        return self._fetch_all(
            "SELECT * FROM volumes WHERE story_id = ? ORDER BY number", (self.STORY_ID,)
        )

    def delete_volume(self, volume_id: str) -> int:
        return self._delete("volumes", "id = ?", (volume_id,))

    def update_volume_field(self, volume_id: str, key: str, value) -> None:
        """更新卷的单个字段"""
        if isinstance(value, (list, dict)):
            import json
            value = json.dumps(value, ensure_ascii=False)
        self._update("volumes", {key: value}, "id = ?", (volume_id,))

    def next_volume_number(self, part_id: str = "") -> int:
        if part_id:
            return self._count("volumes", "story_id = ? AND part_id = ?",
                               (self.STORY_ID, part_id)) + 1
        return self._count("volumes", "story_id = ?", (self.STORY_ID,)) + 1

    # ═══ 章节 ═════════════════════════════════════════════════════

    def save_chapter(self, chapter_data: dict) -> None:
        data = {
            "id": chapter_data.get("id", f"ch_{chapter_data.get('number', 0):04d}"),
            "volume_id": chapter_data.get("volume_id") or None,
            "story_id": self.STORY_ID,
            "number": chapter_data.get("number", 0),
            "title": chapter_data.get("title", ""),
            "status": chapter_data.get("status", "draft"),
            "summary": chapter_data.get("summary", ""),
            "word_count_target": chapter_data.get("word_count_target", 3000),
            "actual_word_count": chapter_data.get("actual_word_count", 0),
            "plot_points_involved": self._to_json(chapter_data.get("plot_points_involved", [])),
            "character_appearances": self._to_json(chapter_data.get("character_appearances", {})),
            "notes": chapter_data.get("notes", ""),
        }
        self._insert_or_replace("chapters", data)

    def load_chapter(self, chapter_id: str) -> Optional[dict]:
        row = self._fetch_one("SELECT * FROM chapters WHERE id = ?", (chapter_id,))
        return self._deserialize_chapter(row)

    def load_chapter_by_number(self, number: int, volume_id: str = "") -> Optional[dict]:
        if volume_id:
            row = self._fetch_one(
                "SELECT * FROM chapters WHERE story_id = ? AND number = ? AND volume_id = ?",
                (self.STORY_ID, number, volume_id),
            )
        else:
            row = self._fetch_one(
                "SELECT * FROM chapters WHERE story_id = ? AND number = ?",
                (self.STORY_ID, number),
            )
        return self._deserialize_chapter(row)

    def list_chapters(self, volume_id: str = "") -> list[dict]:
        if volume_id:
            rows = self._fetch_all(
                "SELECT * FROM chapters WHERE story_id = ? AND volume_id = ? ORDER BY number",
                (self.STORY_ID, volume_id),
            )
        else:
            rows = self._fetch_all(
                "SELECT * FROM chapters WHERE story_id = ? ORDER BY number", (self.STORY_ID,)
            )
        return [self._deserialize_chapter(r) for r in rows]

    def list_chapter_numbers(self, volume_id: str = "") -> list[int]:
        if volume_id:
            return self._fetch_column(
                "SELECT number FROM chapters WHERE story_id = ? AND volume_id = ? ORDER BY number",
                (self.STORY_ID, volume_id),
            )
        return self._fetch_column(
            "SELECT number FROM chapters WHERE story_id = ? ORDER BY number", (self.STORY_ID,)
        )

    def delete_chapter(self, chapter_id: str) -> int:
        return self._delete("chapters", "id = ?", (chapter_id,))

    def delete_chapter_by_number(self, number: int) -> int:
        return self._delete("chapters", "story_id = ? AND number = ?", (self.STORY_ID, number))

    def next_chapter_number(self, volume_id: str = "") -> int:
        if volume_id:
            return self._count("chapters", "story_id = ? AND volume_id = ?",
                               (self.STORY_ID, volume_id)) + 1
        return self._count("chapters", "story_id = ?", (self.STORY_ID,)) + 1

    def update_chapter_field(self, chapter_id: str, key: str, value) -> None:
        self._update("chapters", {key: value}, "id = ?", (chapter_id,))
        # 同时更新故事的 updated_at
        self.update_story_field("updated_at", datetime.now().isoformat())

    def _deserialize_chapter(self, row: Optional[dict]) -> Optional[dict]:
        if not row:
            return None
        row["plot_points_involved"] = self._from_json(row["plot_points_involved"])
        row["character_appearances"] = self._from_json(row["character_appearances"])
        return row

    # ═══ 场景 ═════════════════════════════════════════════════════

    def save_scene(self, scene_data: dict) -> None:
        data = {
            "id": scene_data.get("id", ""),
            "chapter_id": scene_data.get("chapter_id", ""),
            "scene_index": scene_data.get("scene_index", 0),
            "title": scene_data.get("title", ""),
            "location_id": scene_data.get("location_id", ""),
            "time_point": scene_data.get("time_point", ""),
            "characters_present": self._to_json(scene_data.get("characters_present", [])),
            "content": scene_data.get("content", ""),
            "plot_advancements": self._to_json(scene_data.get("plot_advancements", [])),
            "notes": scene_data.get("notes", ""),
            "word_count": scene_data.get("word_count", 0),
        }
        self._insert_or_replace("scenes", data)

    def load_scene(self, scene_id: str) -> Optional[dict]:
        row = self._fetch_one("SELECT * FROM scenes WHERE id = ?", (scene_id,))
        return self._deserialize_scene(row)

    def list_scenes_by_chapter(self, chapter_id: str) -> list[dict]:
        rows = self._fetch_all(
            "SELECT * FROM scenes WHERE chapter_id = ? ORDER BY scene_index", (chapter_id,)
        )
        return [self._deserialize_scene(r) for r in rows]

    def delete_scene(self, scene_id: str) -> int:
        return self._delete("scenes", "id = ?", (scene_id,))

    def delete_scenes_by_chapter(self, chapter_id: str) -> int:
        return self._delete("scenes", "chapter_id = ?", (chapter_id,))

    def update_scene_content(self, scene_id: str, content: str) -> None:
        word_count = len(content)
        self._update("scenes", {"content": content, "word_count": word_count},
                     "id = ?", (scene_id,))
        self.update_story_field("updated_at", datetime.now().isoformat())

    def next_scene_index(self, chapter_id: str) -> int:
        return self._count("scenes", "chapter_id = ?", (chapter_id,))

    def _deserialize_scene(self, row: Optional[dict]) -> Optional[dict]:
        if not row:
            return None
        row["characters_present"] = self._from_json(row["characters_present"])
        row["plot_advancements"] = self._from_json(row["plot_advancements"])
        return row

    # ═══ FTS5 全文索引 ═══════════════════════════════════════════

    def index_scene_for_fts(self, chapter_id: str, chapter_title: str,
                            chapter_summary: str, scene_id: str, scene_title: str,
                            content: str, characters: str, location: str,
                            plot_refs: str) -> None:
        """将场景内容加入 FTS5 全文搜索索引"""
        self._execute(
            """INSERT OR REPLACE INTO content_fts (chapter_id, chapter_title, chapter_summary,
               scene_id, scene_title, scene_content, characters_present, locations, plot_references)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (chapter_id, chapter_title, chapter_summary, scene_id, scene_title,
             content, characters, location, plot_refs),
        )

    def remove_scene_from_fts(self, scene_id: str) -> None:
        """从 FTS5 索引中移除场景"""
        self._execute(
            "DELETE FROM content_fts WHERE scene_id = ?", (scene_id,)
        )

    def search_fts(self, query: str, limit: int = 20) -> list[dict]:
        """全文搜索，返回匹配的场景"""
        rows = self._fetch_all(
            """SELECT chapter_id, chapter_title, chapter_summary, scene_id, scene_title,
               snippet(content_fts, 2, '<b>', '</b>', '...', 40) AS snippet,
               characters_present, locations
               FROM content_fts WHERE content_fts MATCH ? LIMIT ?""",
            (query, limit),
        )
        return [dict(r) for r in rows]

    # ═══ 聚合查询 ═════════════════════════════════════════════════

    def get_total_words(self) -> int:
        return self._fetch_value(
            "SELECT COALESCE(SUM(actual_word_count), 0) FROM chapters WHERE story_id = ?",
            (self.STORY_ID,),
        ) or 0

    def get_chapter_count_by_status(self, status: str) -> int:
        return self._count("chapters", "story_id = ? AND status = ?", (self.STORY_ID, status))

    def get_story_stats(self) -> dict:
        """获取故事统计信息"""
        total = self._count("chapters", "story_id = ?", (self.STORY_ID,))
        done = self.get_chapter_count_by_status("done")
        writing = self.get_chapter_count_by_status("writing")
        total_words = self.get_total_words()
        return {
            "total_chapters": total,
            "done_chapters": done,
            "writing_chapters": writing,
            "total_words": total_words,
            "progress_percent": round(done / total * 100, 1) if total > 0 else 0.0,
        }

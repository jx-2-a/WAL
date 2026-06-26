"""索引仓库 — SQLite 版

管理 content_index, content_fts(FTS5), milestones 表。
提供全文搜索、关键词索引、里程碑快照。
"""

from datetime import datetime
from typing import Optional

from .db_repo import DatabaseRepository


class IndexRepository(DatabaseRepository):
    """内容索引与搜索仓库（SQLite + FTS5）"""

    STORY_ID = "main"

    # ═══ 关键词索引 ═══════════════════════════════════════════════

    def save_index_entry(self, entry: dict) -> None:
        data = {
            "id": entry.get("id", ""),
            "story_id": self.STORY_ID,
            "keyword": entry.get("keyword", ""),
            "category": entry.get("category", ""),
            "chapter_references": self._to_json(entry.get("chapter_references", [])),
            "volume_references": self._to_json(entry.get("volume_references", [])),
            "summary_context": entry.get("summary_context", ""),
            "first_appearance_chapter": entry.get("first_appearance_chapter", 0),
            "last_appearance_chapter": entry.get("last_appearance_chapter", 0),
            "importance": entry.get("importance", "medium"),
        }
        self._insert_or_replace("content_index", data)

    def load_index_entry(self, keyword: str, category: str = "") -> Optional[dict]:
        if category:
            row = self._fetch_one(
                "SELECT * FROM content_index WHERE story_id = ? AND keyword = ? AND category = ?",
                (self.STORY_ID, keyword, category),
            )
        else:
            row = self._fetch_one(
                "SELECT * FROM content_index WHERE story_id = ? AND keyword = ?",
                (self.STORY_ID, keyword),
            )
        return self._deserialize_entry(row)

    def search_by_keyword(self, keyword: str) -> list[dict]:
        rows = self._fetch_all(
            "SELECT * FROM content_index WHERE story_id = ? AND keyword LIKE ?",
            (self.STORY_ID, f"%{keyword}%"),
        )
        return [self._deserialize_entry(r) for r in rows]

    def search_by_category(self, category: str) -> list[dict]:
        rows = self._fetch_all(
            "SELECT * FROM content_index WHERE story_id = ? AND category = ?",
            (self.STORY_ID, category),
        )
        return [self._deserialize_entry(r) for r in rows]

    def list_index_entries(self, category: str = "") -> list[dict]:
        if category:
            rows = self._fetch_all(
                "SELECT * FROM content_index WHERE story_id = ? AND category = ? ORDER BY importance DESC, keyword",
                (self.STORY_ID, category),
            )
        else:
            rows = self._fetch_all(
                "SELECT * FROM content_index WHERE story_id = ? ORDER BY category, importance DESC, keyword",
                (self.STORY_ID,),
            )
        return [self._deserialize_entry(r) for r in rows]

    def get_entries_by_chapter(self, chapter_number: int) -> list[dict]:
        """获取某章涉及的所有索引条目"""
        rows = self._fetch_all(
            "SELECT * FROM content_index WHERE story_id = ?",
            (self.STORY_ID,),
        )
        result = []
        for r in rows:
            entry = self._deserialize_entry(r)
            if entry and chapter_number in entry.get("chapter_references", []):
                result.append(entry)
        return result

    def delete_index_entry(self, entry_id: str) -> int:
        return self._delete("content_index", "id = ?", (entry_id,))

    def update_chapter_reference(self, keyword: str, chapter_number: int) -> None:
        """更新某关键词的章节引用（追加新章节号）"""
        entry = self.load_index_entry(keyword)
        if entry:
            refs = entry.get("chapter_references", [])
            if chapter_number not in refs:
                refs.append(chapter_number)
                refs.sort()
            self._update(
                "content_index",
                {
                    "chapter_references": self._to_json(refs),
                    "last_appearance_chapter": chapter_number,
                },
                "id = ?", (entry["id"],),
            )

    def _deserialize_entry(self, row: Optional[dict]) -> Optional[dict]:
        if not row:
            return None
        row["chapter_references"] = self._from_json(row["chapter_references"])
        row["volume_references"] = self._from_json(row["volume_references"])
        return row

    # ═══ FTS5 全文搜索 ══════════════════════════════════════════

    def search_fulltext(self, query: str, limit: int = 20) -> list[dict]:
        """FTS5 全文搜索，返回匹配的场景及高亮片段"""
        # 使用 FTS5 snippet 函数生成高亮片段
        rows = self._fetch_all(
            """SELECT
                chapter_id, chapter_title, chapter_summary,
                scene_id, scene_title,
                snippet(content_fts, 2, '<b>', '</b>', '...', 50) AS snippet,
                characters_present, locations
               FROM content_fts
               WHERE content_fts MATCH ?
               ORDER BY rank
               LIMIT ?""",
            (query, limit),
        )
        return [dict(r) for r in rows]

    def search_chapter_range(self, start_ch: int, end_ch: int,
                             query: str = "", limit: int = 30) -> list[dict]:
        """在指定章节范围内全文搜索"""
        if query:
            rows = self._fetch_all(
                """SELECT
                    chapter_id, chapter_title, chapter_summary,
                    scene_id, scene_title,
                    snippet(content_fts, 2, '<b>', '</b>', '...', 50) AS snippet,
                    characters_present, locations
                   FROM content_fts
                   WHERE content_fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (query, limit),
            )
        else:
            # 无查询词时返回范围内所有已索引场景
            rows = self._fetch_all(
                """SELECT
                    chapter_id, chapter_title, chapter_summary,
                    scene_id, scene_title,
                    scene_content AS snippet,
                    characters_present, locations
                   FROM content_fts
                   LIMIT ?""",
                (limit,),
            )
        # 按章节号过滤（从 chapter_id 中提取）
        result = []
        for r in rows:
            ch_id = r["chapter_id"]
            # chapter_id 格式: ch_0001
            try:
                ch_num = int(ch_id.replace("ch_", ""))
                if start_ch <= ch_num <= end_ch:
                    result.append(dict(r))
            except (ValueError, AttributeError):
                pass
        return result[:limit]

    def index_scene(self, chapter_id: str, chapter_title: str, chapter_summary: str,
                    scene_id: str, scene_title: str, content: str,
                    characters_present: str = "", location: str = "",
                    plot_references: str = "") -> None:
        """索引一个场景到 FTS5"""
        self._execute(
            """INSERT OR REPLACE INTO content_fts
               (chapter_id, chapter_title, chapter_summary, scene_id, scene_title,
                scene_content, characters_present, locations, plot_references)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (chapter_id, chapter_title, chapter_summary, scene_id, scene_title,
             content, characters_present, location, plot_references),
        )

    def remove_scene_index(self, scene_id: str) -> None:
        """从 FTS5 中移除场景"""
        self._execute("DELETE FROM content_fts WHERE scene_id = ?", (scene_id,))

    def rebuild_fts_index(self) -> int:
        """全量重建 FTS5 索引（从 scenes 表）"""
        count = 0
        scenes = self._fetch_all(
            """SELECT s.id AS scene_id, s.content, s.title AS scene_title,
                      s.characters_present, s.location_id,
                      s.plot_advancements,
                      c.id AS chapter_id, c.title AS chapter_title, c.summary AS chapter_summary
               FROM scenes s
               JOIN chapters c ON s.chapter_id = c.id
               WHERE c.story_id = ?""",
            (self.STORY_ID,),
        )
        for sc in scenes:
            if sc.get("content"):
                self.index_scene(
                    chapter_id=sc["chapter_id"],
                    chapter_title=sc["chapter_title"] or "",
                    chapter_summary=sc["chapter_summary"] or "",
                    scene_id=sc["scene_id"],
                    scene_title=sc["scene_title"] or "",
                    content=sc["content"],
                    characters_present=sc["characters_present"] or "",
                    location=sc["location_id"] or "",
                    plot_references=sc["plot_advancements"] or "",
                )
                count += 1
        return count

    # ═══ 里程碑 ═══════════════════════════════════════════════════

    def save_milestone(self, ms_data: dict) -> None:
        data = {
            "id": ms_data.get("id", ""),
            "story_id": self.STORY_ID,
            "name": ms_data.get("name", ""),
            "chapter_number": ms_data.get("chapter_number", 0),
            "volume_number": ms_data.get("volume_number", 0),
            "story_state_summary": ms_data.get("story_state_summary", ""),
            "character_states": self._to_json(ms_data.get("character_states", {})),
            "plot_states": self._to_json(ms_data.get("plot_states", {})),
            "unresolved_foreshadowings": self._to_json(
                ms_data.get("unresolved_foreshadowings", [])
            ),
            "total_words_at_point": ms_data.get("total_words_at_point", 0),
            "created_at": ms_data.get("created_at", datetime.now().isoformat()),
        }
        self._insert_or_replace("milestones", data)

    def load_milestone(self, ms_id: str) -> Optional[dict]:
        row = self._fetch_one("SELECT * FROM milestones WHERE id = ?", (ms_id,))
        return self._deserialize_milestone(row)

    def list_milestones(self) -> list[dict]:
        rows = self._fetch_all(
            "SELECT * FROM milestones WHERE story_id = ? ORDER BY chapter_number",
            (self.STORY_ID,),
        )
        return [self._deserialize_milestone(r) for r in rows]

    def get_latest_milestone(self) -> Optional[dict]:
        row = self._fetch_one(
            "SELECT * FROM milestones WHERE story_id = ? ORDER BY chapter_number DESC LIMIT 1",
            (self.STORY_ID,),
        )
        return self._deserialize_milestone(row)

    def delete_milestone(self, ms_id: str) -> int:
        return self._delete("milestones", "id = ?", (ms_id,))

    def _deserialize_milestone(self, row: Optional[dict]) -> Optional[dict]:
        if not row:
            return None
        for field in ("character_states", "plot_states", "unresolved_foreshadowings"):
            row[field] = self._from_json(row[field])
        return row

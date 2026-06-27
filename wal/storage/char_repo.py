"""角色仓库 — SQLite 版

管理 characters, relationships, character_snapshots 表的 CRUD。
替代原 YAML 版 CharacterRepository。
"""

from datetime import datetime
from typing import Optional

from .db_repo import DatabaseRepository


class CharacterRepository(DatabaseRepository):
    """角色数据仓库（SQLite）"""

    STORY_ID = "main"

    # ═══ 角色 CRUD ═══════════════════════════════════════════════

    def save_character(self, char_data: dict) -> None:
        """保存/更新单个角色"""
        data = {
            "id": char_data.get("id", ""),
            "story_id": self.STORY_ID,
            "name": char_data.get("name", ""),
            "aliases": self._to_json(char_data.get("aliases", [])),
            "role": char_data.get("role", "supporting"),
            "gender": char_data.get("gender", ""),
            "age": char_data.get("age", ""),
            "appearance": char_data.get("appearance", ""),
            "personality_traits": self._to_json(char_data.get("personality_traits", [])),
            "background_story": char_data.get("background_story", ""),
            "motivation": char_data.get("motivation", ""),
            "arc_description": char_data.get("arc_description", ""),
            "arc_progress": char_data.get("arc_progress", ""),
            "abilities": self._to_json(char_data.get("abilities", [])),
            "weaknesses": self._to_json(char_data.get("weaknesses", [])),
            "first_appearance": char_data.get("first_appearance", ""),
            "notes": char_data.get("notes", ""),
        }
        self._insert_or_replace("characters", data)

    def load_character(self, char_id: str) -> Optional[dict]:
        row = self._fetch_one("SELECT * FROM characters WHERE id = ?", (char_id,))
        return self._deserialize_character(row)

    def load_all_characters(self) -> dict[str, dict]:
        """加载所有角色，返回 {id: dict}"""
        rows = self._fetch_all(
            "SELECT * FROM characters WHERE story_id = ?", (self.STORY_ID,)
        )
        return {r["id"]: self._deserialize_character(r) for r in rows}

    def list_characters(self, role: str = "") -> list[dict]:
        if role:
            rows = self._fetch_all(
                "SELECT * FROM characters WHERE story_id = ? AND role = ?",
                (self.STORY_ID, role),
            )
        else:
            rows = self._fetch_all(
                "SELECT * FROM characters WHERE story_id = ?", (self.STORY_ID,)
            )
        return [self._deserialize_character(r) for r in rows]

    def find_character_by_name(self, name: str) -> Optional[dict]:
        row = self._fetch_one(
            "SELECT * FROM characters WHERE story_id = ? AND name = ?",
            (self.STORY_ID, name),
        )
        return self._deserialize_character(row)

    def delete_character(self, char_id: str) -> int:
        return self._delete("characters", "id = ?", (char_id,))

    def update_character_field(self, char_id: str, key: str, value) -> None:
        if isinstance(value, (list, dict)):
            value = self._to_json(value)
        self._update("characters", {key: value}, "id = ?", (char_id,))

    def next_character_number(self) -> int:
        return self._count("characters", "story_id = ?", (self.STORY_ID,)) + 1

    def _deserialize_character(self, row: Optional[dict]) -> Optional[dict]:
        if not row:
            return None
        for field in ("aliases", "personality_traits", "abilities", "weaknesses"):
            row[field] = self._from_json(row[field])
        return row

    # ═══ 关系 CRUD ═══════════════════════════════════════════════

    def save_relationship(self, rel_data: dict) -> None:
        data = {
            "id": rel_data.get("id", ""),
            "story_id": self.STORY_ID,
            "character_a": rel_data.get("character_a", ""),
            "character_b": rel_data.get("character_b", ""),
            "rel_type": rel_data.get("rel_type", "other"),
            "description": rel_data.get("description", ""),
            "dynamics": rel_data.get("dynamics", ""),
            "history": rel_data.get("history", ""),
        }
        self._insert_or_replace("relationships", data)

    def load_relationships_for(self, char_id: str) -> list[dict]:
        """获取某个角色的所有关系"""
        rows = self._fetch_all(
            "SELECT * FROM relationships WHERE character_a = ? OR character_b = ?",
            (char_id, char_id),
        )
        return [dict(r) for r in rows]

    def load_relationship_between(self, char_a: str, char_b: str) -> Optional[dict]:
        row = self._fetch_one(
            """SELECT * FROM relationships
               WHERE (character_a = ? AND character_b = ?)
                  OR (character_a = ? AND character_b = ?)""",
            (char_a, char_b, char_b, char_a),
        )
        return dict(row) if row else None

    def delete_relationship(self, rel_id: str) -> int:
        return self._delete("relationships", "id = ?", (rel_id,))

    def delete_relationships_for(self, char_id: str) -> int:
        return self._delete("relationships",
                            "character_a = ? OR character_b = ?", (char_id, char_id))

    # ═══ 角色快照 ═══════════════════════════════════════════════

    def save_snapshot(self, snap_data: dict) -> None:
        data = {
            "id": snap_data.get("id", ""),
            "character_id": snap_data.get("character_id", ""),
            "chapter_number": snap_data.get("chapter_number", 0),
            "chapter_title": snap_data.get("chapter_title", ""),
            "arc_progress": snap_data.get("arc_progress", ""),
            "personality_changes": snap_data.get("personality_changes", ""),
            "appearance_changes": snap_data.get("appearance_changes", ""),
            "new_abilities": self._to_json(snap_data.get("new_abilities", [])),
            "lost_abilities": self._to_json(snap_data.get("lost_abilities", [])),
            "key_relationships_changed": self._to_json(
                snap_data.get("key_relationships_changed", {})
            ),
            "internal_state": snap_data.get("internal_state", ""),
            "summary": snap_data.get("summary", ""),
            "created_at": snap_data.get("created_at", datetime.now().isoformat()),
        }
        self._insert_or_replace("character_snapshots", data)

    def load_snapshots(self, char_id: str) -> list[dict]:
        rows = self._fetch_all(
            "SELECT * FROM character_snapshots WHERE character_id = ? ORDER BY chapter_number",
            (char_id,),
        )
        return [self._deserialize_snapshot(r) for r in rows]

    def load_snapshot_at_chapter(self, char_id: str, chapter_number: int) -> Optional[dict]:
        """获取角色在指定章节的最近快照"""
        row = self._fetch_one(
            """SELECT * FROM character_snapshots
               WHERE character_id = ? AND chapter_number <= ?
               ORDER BY chapter_number DESC LIMIT 1""",
            (char_id, chapter_number),
        )
        return self._deserialize_snapshot(row)

    def delete_snapshots_for(self, char_id: str) -> int:
        return self._delete("character_snapshots", "character_id = ?", (char_id,))

    def delete_snapshots_by_chapter(self, chapter_number: int) -> int:
        """删除指定章节的所有角色快照（用于章节重写时级联清理）"""
        return self._delete("character_snapshots", "chapter_number = ?", (chapter_number,))

    def _deserialize_snapshot(self, row: Optional[dict]) -> Optional[dict]:
        if not row:
            return None
        for field in ("new_abilities", "lost_abilities", "key_relationships_changed"):
            row[field] = self._from_json(row[field])
        return row

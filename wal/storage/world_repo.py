"""世界观仓库 — SQLite 版

管理 world_settings, world_rules, locations, timeline_events 表的 CRUD。
替代原 WorldManager 内嵌的 YAML 操作。
"""

from typing import Optional

from .db_repo import DatabaseRepository


class WorldRepository(DatabaseRepository):
    """世界观数据仓库（SQLite）"""

    STORY_ID = "main"
    WORLD_ID = "world"

    # ═══ 世界观设定 ═══════════════════════════════════════════════

    def save_world_setting(self, world_data: dict) -> None:
        data = {
            "id": self.WORLD_ID,
            "story_id": self.STORY_ID,
            "world_name": world_data.get("world_name", ""),
            "description": world_data.get("description", ""),
            "magic_system": world_data.get("magic_system", ""),
            "technology_level": world_data.get("technology_level", ""),
            "social_structure": world_data.get("social_structure", ""),
            "history": world_data.get("history", ""),
            "races": self._to_json(world_data.get("races", [])),
            "factions": self._to_json(world_data.get("factions", [])),
            "notes": world_data.get("notes", ""),
        }
        self._insert_or_replace("world_settings", data)

    def load_world_setting(self) -> Optional[dict]:
        row = self._fetch_one("SELECT * FROM world_settings WHERE id = ?", (self.WORLD_ID,))
        return self._deserialize_world(row)

    def world_exists(self) -> bool:
        return self._exists("world_settings", "id = ?", (self.WORLD_ID,))

    def _deserialize_world(self, row: Optional[dict]) -> Optional[dict]:
        if not row:
            return None
        row["races"] = self._from_json(row["races"])
        row["factions"] = self._from_json(row["factions"])
        return row

    # ═══ 世界规则 ═══════════════════════════════════════════════

    def save_world_rule(self, rule_data: dict) -> None:
        data = {
            "id": rule_data.get("id", ""),
            "world_id": self.WORLD_ID,
            "name": rule_data.get("name", ""),
            "description": rule_data.get("description", ""),
            "category": rule_data.get("category", ""),
        }
        self._insert_or_replace("world_rules", data)

    def list_world_rules(self, category: str = "") -> list[dict]:
        if category:
            return self._fetch_all(
                "SELECT * FROM world_rules WHERE world_id = ? AND category = ?",
                (self.WORLD_ID, category),
            )
        return self._fetch_all(
            "SELECT * FROM world_rules WHERE world_id = ?", (self.WORLD_ID,)
        )

    def delete_world_rule(self, rule_id: str) -> int:
        return self._delete("world_rules", "id = ?", (rule_id,))

    def count_rules(self) -> int:
        return self._count("world_rules", "world_id = ?", (self.WORLD_ID,))

    # ═══ 地点 ═══════════════════════════════════════════════════

    def save_location(self, loc_data: dict) -> None:
        data = {
            "id": loc_data.get("id", ""),
            "story_id": self.STORY_ID,
            "name": loc_data.get("name", ""),
            "description": loc_data.get("description", ""),
            "location_type": loc_data.get("location_type", ""),
            "parent_location": loc_data.get("parent_location", ""),
            "atmosphere": loc_data.get("atmosphere", ""),
            "notable_features": self._to_json(loc_data.get("notable_features", [])),
            "related_characters": self._to_json(loc_data.get("related_characters", [])),
        }
        self._insert_or_replace("locations", data)

    def load_location(self, loc_id: str) -> Optional[dict]:
        row = self._fetch_one("SELECT * FROM locations WHERE id = ?", (loc_id,))
        return self._deserialize_location(row)

    def list_locations(self, location_type: str = "") -> list[dict]:
        if location_type:
            rows = self._fetch_all(
                "SELECT * FROM locations WHERE story_id = ? AND location_type = ?",
                (self.STORY_ID, location_type),
            )
        else:
            rows = self._fetch_all(
                "SELECT * FROM locations WHERE story_id = ?", (self.STORY_ID,)
            )
        return [self._deserialize_location(r) for r in rows]

    def get_child_locations(self, parent_id: str) -> list[dict]:
        rows = self._fetch_all(
            "SELECT * FROM locations WHERE parent_location = ?", (parent_id,)
        )
        return [self._deserialize_location(r) for r in rows]

    def delete_location(self, loc_id: str) -> int:
        return self._delete("locations", "id = ?", (loc_id,))

    def count_locations(self) -> int:
        return self._count("locations", "story_id = ?", (self.STORY_ID,))

    def next_location_number(self) -> int:
        return self._count("locations", "story_id = ?", (self.STORY_ID,)) + 1

    def _deserialize_location(self, row: Optional[dict]) -> Optional[dict]:
        if not row:
            return None
        row["notable_features"] = self._from_json(row["notable_features"])
        row["related_characters"] = self._from_json(row["related_characters"])
        return row

    # ═══ 时间线 ═══════════════════════════════════════════════════

    def save_timeline_event(self, event_data: dict) -> None:
        data = {
            "id": event_data.get("id", ""),
            "story_id": self.STORY_ID,
            "title": event_data.get("title", ""),
            "description": event_data.get("description", ""),
            "time_point": event_data.get("time_point", ""),
            "related_chapters": self._to_json(event_data.get("related_chapters", [])),
            "related_characters": self._to_json(event_data.get("related_characters", [])),
            "is_backstory": 1 if event_data.get("is_backstory") else 0,
            "causes": self._to_json(event_data.get("causes", [])),
            "effects": self._to_json(event_data.get("effects", [])),
        }
        self._insert_or_replace("timeline_events", data)

    def load_timeline_event(self, event_id: str) -> Optional[dict]:
        row = self._fetch_one("SELECT * FROM timeline_events WHERE id = ?", (event_id,))
        return self._deserialize_event(row)

    def list_timeline_events(self, is_backstory: bool | None = None) -> list[dict]:
        if is_backstory is not None:
            rows = self._fetch_all(
                "SELECT * FROM timeline_events WHERE story_id = ? AND is_backstory = ? ORDER BY time_point",
                (self.STORY_ID, 1 if is_backstory else 0),
            )
        else:
            rows = self._fetch_all(
                "SELECT * FROM timeline_events WHERE story_id = ? ORDER BY time_point",
                (self.STORY_ID,),
            )
        return [self._deserialize_event(r) for r in rows]

    def delete_timeline_event(self, event_id: str) -> int:
        return self._delete("timeline_events", "id = ?", (event_id,))

    def count_timeline_events(self) -> int:
        return self._count("timeline_events", "story_id = ?", (self.STORY_ID,))

    def next_event_number(self) -> int:
        return self._count("timeline_events", "story_id = ?", (self.STORY_ID,)) + 1

    def _deserialize_event(self, row: Optional[dict]) -> Optional[dict]:
        if not row:
            return None
        row["related_chapters"] = self._from_json(row["related_chapters"])
        row["related_characters"] = self._from_json(row["related_characters"])
        row["causes"] = self._from_json(row["causes"])
        row["effects"] = self._from_json(row["effects"])
        row["is_backstory"] = bool(row["is_backstory"])
        return row

    # ═══ 聚合查询 ═════════════════════════════════════════════════

    def get_world_summary_data(self) -> dict:
        """获取世界观概览所需的所有数据"""
        world = self.load_world_setting()
        return {
            "world": world,
            "rule_count": self.count_rules(),
            "location_count": self.count_locations(),
            "timeline_count": self.count_timeline_events(),
        }

"""世界观管理器 — SQLite 版

地点、设定、时间线管理。内部使用 SQLite 存储。
"""

from pathlib import Path
from typing import Optional

from ..models.world import Location, WorldSetting, WorldRule, TimelineEvent
from ..storage.database import Database
from ..storage.world_repo import WorldRepository


class WorldManager:
    """管理世界构建要素（SQLite 后端）"""

    def __init__(self, project_dir: str):
        self.project_dir = Path(project_dir)
        self.project_dir.mkdir(parents=True, exist_ok=True)

        db_path = self.project_dir / "wal.db"
        self.db = Database(str(db_path))
        self.repo = WorldRepository(self.db)

        if not self.db.schema_exists():
            self.db.init_schema()
            if (self.project_dir / "story.yaml").exists():
                self.db.migrate_from_yaml(str(self.project_dir))

        self._world: Optional[WorldSetting] = None
        self._locations: dict[str, Location] = {}
        self._timeline: list[TimelineEvent] = []

    def load(self) -> None:
        """从 SQLite 加载世界观数据"""
        world_data = self.repo.load_world_setting()
        if world_data:
            rules_rows = self.repo.list_world_rules()
            world_data["rules"] = [WorldRule(**r) for r in rules_rows]
            self._world = WorldSetting(**world_data)

        loc_rows = self.repo.list_locations()
        self._locations = {l["id"]: Location(**l) for l in loc_rows}

        tl_rows = self.repo.list_timeline_events()
        self._timeline = [TimelineEvent(**t) for t in tl_rows]

    def save(self) -> None:
        """保存世界观数据到 SQLite"""
        if self._world:
            world_dict = self._world.model_dump(mode="json")
            rules = world_dict.pop("rules", [])
            self.repo.save_world_setting(world_dict)
            for rule in rules:
                if isinstance(rule, dict):
                    rule["id"] = rule.get("id", f"rule_{rule.get('name', '')}")
                else:
                    rule_dict = rule.model_dump(mode="json")
                    rule_dict["id"] = rule_dict.get("id", f"rule_{rule_dict.get('name', '')}")
                    rule = rule_dict
                self.repo.save_world_rule(rule)
        for loc in self._locations.values():
            self.repo.save_location(loc.model_dump(mode="json"))
        for event in self._timeline:
            self.repo.save_timeline_event(event.model_dump(mode="json"))

    # ═══ 世界观设定 ═════════════════════════════════════════════

    def set_world(self, world_name: str, description: str = "",
                  magic_system: str = "", technology_level: str = "",
                  social_structure: str = "", history: str = "",
                  races: list[str] | None = None,
                  factions: list[str] | None = None) -> WorldSetting:
        self._world = WorldSetting(
            world_name=world_name, description=description,
            magic_system=magic_system, technology_level=technology_level,
            social_structure=social_structure, history=history,
            races=races or [], factions=factions or [],
        )
        self.repo.save_world_setting(self._world.model_dump(mode="json"))
        return self._world

    def get_world(self) -> Optional[WorldSetting]:
        if self._world is None:
            world_data = self.repo.load_world_setting()
            if world_data:
                rules_rows = self.repo.list_world_rules()
                world_data["rules"] = [WorldRule(**r) for r in rules_rows]
                self._world = WorldSetting(**world_data)
        return self._world

    def add_world_rule(self, name: str, description: str, category: str) -> WorldRule:
        if not self._world:
            self.get_world()
        if not self._world:
            raise ValueError("尚未设定世界观")
        rule = WorldRule(name=name, description=description, category=category)
        rule_id = f"rule_{name}"
        self.repo.save_world_rule({
            "id": rule_id, "name": name, "description": description, "category": category,
        })
        self._world.rules.append(rule)
        return rule

    def get_world_summary(self) -> str:
        summary = self.repo.get_world_summary_data()
        w = summary.get("world")
        if not w:
            return "世界观未设定"
        lines = [
            f"## {w.get('world_name', '')}",
            f"概述：{w.get('description', '')}",
            f"科技水平：{w.get('technology_level', '')}",
            f"力量体系：{w.get('magic_system', '')}",
            f"社会结构：{w.get('social_structure', '')}",
            f"种族：{', '.join(w.get('races', [])) if w.get('races') else '（未设定）'}",
            f"势力：{', '.join(w.get('factions', [])) if w.get('factions') else '（未设定）'}",
            f"规则数：{summary.get('rule_count', 0)}",
            f"地点数：{summary.get('location_count', 0)}",
            f"时间线事件数：{summary.get('timeline_count', 0)}",
        ]
        return "\n".join(lines)

    # ═══ 地点 ═══════════════════════════════════════════════════

    def add_location(self, name: str, description: str = "", location_type: str = "",
                     parent_location: str = "", atmosphere: str = "",
                     notable_features: list[str] | None = None,
                     related_characters: list[str] | None = None) -> Location:
        lid = f"loc_{self.repo.next_location_number():03d}"
        loc = Location(
            id=lid, name=name, description=description,
            location_type=location_type, parent_location=parent_location,
            atmosphere=atmosphere,
            notable_features=notable_features or [],
            related_characters=related_characters or [],
        )
        self.repo.save_location(loc.model_dump(mode="json"))
        self._locations[lid] = loc
        return loc

    def get_location(self, loc_id: str) -> Optional[Location]:
        if loc_id in self._locations:
            return self._locations[loc_id]
        loc_data = self.repo.load_location(loc_id)
        if loc_data:
            loc = Location(**loc_data)
            self._locations[loc_id] = loc
            return loc
        return None

    def list_locations(self, location_type: str | None = None) -> list[Location]:
        rows = self.repo.list_locations(location_type or "")
        return [Location(**r) for r in rows]

    # ═══ 时间线 ═══════════════════════════════════════════════════

    def add_timeline_event(self, title: str, description: str = "",
                           time_point: str = "",
                           related_chapters: list[int] | None = None,
                           related_characters: list[str] | None = None,
                           is_backstory: bool = False,
                           causes: list[str] | None = None,
                           effects: list[str] | None = None) -> TimelineEvent:
        tid = f"tl_{self.repo.next_event_number():03d}"
        event = TimelineEvent(
            id=tid, title=title, description=description,
            time_point=time_point,
            related_chapters=related_chapters or [],
            related_characters=related_characters or [],
            is_backstory=is_backstory,
            causes=causes or [], effects=effects or [],
        )
        self.repo.save_timeline_event(event.model_dump(mode="json"))
        self._timeline.append(event)
        return event

    def list_timeline(self) -> list[TimelineEvent]:
        rows = self.repo.list_timeline_events()
        return [TimelineEvent(**r) for r in rows]

    def get_backstory_events(self) -> list[TimelineEvent]:
        rows = self.repo.list_timeline_events(is_backstory=True)
        return [TimelineEvent(**r) for r in rows]

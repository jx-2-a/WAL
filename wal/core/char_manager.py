"""角色管理器 — SQLite 版

管理所有角色、关系、快照。内部使用 SQLite 存储。
"""

from pathlib import Path
from typing import Optional

from ..models.character import Character, Relationship, RelationType, CharacterSnapshot
from ..storage.database import Database
from ..storage.char_repo import CharacterRepository


class CharacterManager:
    """管理所有角色及其关系（SQLite 后端）"""

    def __init__(self, project_dir: str):
        self.project_dir = Path(project_dir)
        self.project_dir.mkdir(parents=True, exist_ok=True)

        db_path = self.project_dir / "wal.db"
        self.db = Database(str(db_path))
        self.repo = CharacterRepository(self.db)

        # 自动初始化
        if not self.db.schema_exists():
            self.db.init_schema()
            if (self.project_dir / "story.yaml").exists():
                self.db.migrate_from_yaml(str(self.project_dir))

        self._ensure_story_exists()
        self._characters: dict[str, Character] = {}

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

    def load(self) -> dict[str, Character]:
        """从 SQLite 加载所有角色"""
        self._characters = {}
        char_rows = self.repo.load_all_characters()
        for cid, cdata in char_rows.items():
            # 加载关系
            rel_rows = self.repo.load_relationships_for(cid)
            relationships = {}
            for rel in rel_rows:
                # 确定对方 ID
                other_id = rel["character_b"] if rel["character_a"] == cid else rel["character_a"]
                relationships[other_id] = Relationship(
                    character_a=rel["character_a"],
                    character_b=rel["character_b"],
                    rel_type=RelationType(rel["rel_type"]) if rel["rel_type"] in [
                        r.value for r in RelationType
                    ] else RelationType.OTHER,
                    description=rel.get("description", ""),
                    dynamics=rel.get("dynamics", ""),
                    history=rel.get("history", ""),
                )
            cdata["relationships"] = relationships
            self._characters[cid] = Character(**cdata)
        return self._characters

    def save(self) -> None:
        """保存所有角色到 SQLite"""
        for char in self._characters.values():
            char_dict = char.model_dump(mode="json")
            # 关系和快照单独存储
            relationships = char_dict.pop("relationships", {})
            self.repo.save_character(char_dict)
            # 保存关系
            for target_id, rel in relationships.items():
                if isinstance(rel, dict):
                    rel_data = rel
                else:
                    rel_data = rel.model_dump(mode="json") if hasattr(rel, "model_dump") else rel
                rel_data["id"] = f"rel_{char.id}_{target_id}"
                if not rel_data.get("character_a"):
                    rel_data["character_a"] = char.id
                if not rel_data.get("character_b"):
                    rel_data["character_b"] = target_id
                self.repo.save_relationship(rel_data)

    # ═══ 角色 CRUD ═══════════════════════════════════════════════

    def create_character(self, name: str, role: str = "supporting",
                         **kwargs) -> Character:
        """创建新角色"""
        cid = kwargs.pop("id", None) or f"char_{self.repo.next_character_number():03d}"
        char = Character(id=cid, name=name, role=role, **kwargs)
        char_dict = char.model_dump(mode="json")
        relationships = char_dict.pop("relationships", {})
        self.repo.save_character(char_dict)
        # 恢复关系用于内存缓存
        char_dict["relationships"] = relationships
        self._characters[cid] = char
        return char

    def get_character(self, char_id: str) -> Optional[Character]:
        """获取角色（优先内存，回退到 DB）"""
        if char_id in self._characters:
            return self._characters[char_id]
        # 从 DB 加载
        cdata = self.repo.load_character(char_id)
        if not cdata:
            return None
        rel_rows = self.repo.load_relationships_for(char_id)
        relationships = {}
        for rel in rel_rows:
            other_id = rel["character_b"] if rel["character_a"] == char_id else rel["character_a"]
            relationships[other_id] = Relationship(
                character_a=rel["character_a"], character_b=rel["character_b"],
                rel_type=RelationType(rel["rel_type"]) if rel["rel_type"] in [
                    r.value for r in RelationType
                ] else RelationType.OTHER,
                description=rel.get("description", ""),
                dynamics=rel.get("dynamics", ""),
                history=rel.get("history", ""),
            )
        cdata["relationships"] = relationships
        char = Character(**cdata)
        self._characters[char_id] = char
        return char

    def list_characters(self, role: str | None = None) -> list[Character]:
        """列出角色，可按角色类型过滤"""
        rows = self.repo.list_characters(role or "")
        result = []
        for r in rows:
            if r["id"] in self._characters:
                result.append(self._characters[r["id"]])
            else:
                r["relationships"] = {}
                char = Character(**r)
                self._characters[r["id"]] = char
                result.append(char)
        return result

    def update_character(self, char_id: str, **kwargs) -> Character:
        """更新角色属性"""
        char = self.get_character(char_id)
        if not char:
            raise ValueError(f"Character '{char_id}' not found")
        for key, value in kwargs.items():
            if hasattr(char, key):
                setattr(char, key, value)
                if key not in ("relationships", "snapshots"):
                    if isinstance(value, (list, dict)):
                        self.repo.update_character_field(char_id, key, value)
                    else:
                        self.repo.update_character_field(char_id, key, value)
        return char

    def delete_character(self, char_id: str) -> bool:
        if char_id in self._characters:
            del self._characters[char_id]
        self.repo.delete_relationships_for(char_id)
        return self.repo.delete_character(char_id) > 0

    # ═══ 关系管理 ═══════════════════════════════════════════════

    def add_relationship(self, char_a: str, char_b: str, rel_type: str,
                         description: str = "", dynamics: str = "",
                         history: str = "") -> Relationship:
        """在两个角色之间添加关系"""
        ca = self.get_character(char_a)
        cb = self.get_character(char_b)
        if not ca or not cb:
            raise ValueError("Both characters must exist")

        rt = RelationType(rel_type) if rel_type in [r.value for r in RelationType] else RelationType.OTHER
        rel = Relationship(
            character_a=char_a, character_b=char_b,
            rel_type=rt, description=description,
            dynamics=dynamics, history=history,
        )

        # 保存到 SQLite
        rel_id = f"rel_{char_a}_{char_b}"
        self.repo.save_relationship({
            "id": rel_id, "character_a": char_a, "character_b": char_b,
            "rel_type": rel_type, "description": description,
            "dynamics": dynamics, "history": history,
        })

        # 更新内存
        ca.relationships[char_b] = rel
        cb.relationships[char_a] = rel
        return rel

    def get_relationships(self, char_id: str) -> dict[str, Relationship]:
        char = self.get_character(char_id)
        return char.relationships if char else {}

    def get_relation_between(self, char_a: str, char_b: str) -> Optional[Relationship]:
        ca = self.get_character(char_a)
        if ca:
            return ca.relationships.get(char_b)
        return None

    # ═══ 角色弧光 ═══════════════════════════════════════════════

    def get_character_arc(self, char_id: str) -> dict:
        char = self.get_character(char_id)
        if not char:
            return {}
        return {
            "name": char.name,
            "arc_description": char.arc_description,
            "arc_progress": char.arc_progress,
            "motivation": char.motivation,
            "first_appearance": char.first_appearance,
        }

    def update_arc_progress(self, char_id: str, progress: str) -> Character:
        return self.update_character(char_id, arc_progress=progress)

    # ═══ 一致性检查 ═════════════════════════════════════════════

    def check_character_consistency(self, char_id: str) -> dict:
        char = self.get_character(char_id)
        if not char:
            return {"error": f"Character '{char_id}' not found"}
        issues = []
        warnings = []
        if char.role == "protagonist":
            if not char.background_story:
                issues.append("主角缺少背景故事")
            if not char.motivation:
                issues.append("主角缺少核心动机")
            if not char.arc_description:
                warnings.append("主角未设置弧光描述")
            if not char.weaknesses:
                warnings.append("主角缺少弱点，可能过于完美")
        if char.arc_description and not char.arc_progress:
            warnings.append("有弧光描述但未记录进度")
        if char.relationships and not char.background_story:
            warnings.append("有关联关系但缺少背景故事")
        return {
            "character": char.name, "role": char.role,
            "issues": issues, "warnings": warnings, "ok": len(issues) == 0,
        }

    def check_all_consistency(self) -> list[dict]:
        self.load()
        return [self.check_character_consistency(cid) for cid in self._characters]

    # ═══ 角色快照 ═══════════════════════════════════════════════

    def create_snapshot(self, char_id: str, chapter_number: int,
                        chapter_title: str = "", arc_progress: str = "",
                        personality_changes: str = "", appearance_changes: str = "",
                        new_abilities: list[str] | None = None,
                        lost_abilities: list[str] | None = None,
                        key_relationships_changed: dict[str, str] | None = None,
                        internal_state: str = "", summary: str = "") -> CharacterSnapshot:
        """创建角色在指定章节的状态快照"""
        from datetime import datetime
        snap_id = f"snap_{char_id}_{chapter_number}"
        snap = CharacterSnapshot(
            id=snap_id,
            character_id=char_id,
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            arc_progress=arc_progress,
            personality_changes=personality_changes,
            appearance_changes=appearance_changes,
            new_abilities=new_abilities or [],
            lost_abilities=lost_abilities or [],
            key_relationships_changed=key_relationships_changed or {},
            internal_state=internal_state,
            summary=summary,
            created_at=datetime.now().isoformat(),
        )
        snap_dict = snap.model_dump(mode="json")
        snap_dict["new_abilities"] = snap.new_abilities
        snap_dict["lost_abilities"] = snap.lost_abilities
        snap_dict["key_relationships_changed"] = snap.key_relationships_changed
        self.repo.save_snapshot(snap_dict)
        # 更新内存中的角色
        if char_id in self._characters:
            self._characters[char_id].snapshots.append(snap)
            self._characters[char_id].arc_progress = arc_progress or self._characters[char_id].arc_progress
        return snap

    def get_character_at_chapter(self, char_id: str, chapter_number: int) -> Optional[CharacterSnapshot]:
        """获取角色在指定章节的最近快照"""
        row = self.repo.load_snapshot_at_chapter(char_id, chapter_number)
        return self._row_to_snapshot(row) if row else None

    def get_character_evolution(self, char_id: str) -> dict:
        """获取角色演变历程"""
        char = self.get_character(char_id)
        if not char:
            return {"error": f"Character '{char_id}' not found"}
        rows = self.repo.load_snapshots(char_id)
        snapshots = [self._row_to_snapshot(r) for r in rows]
        evolution_points = []
        for snap in snapshots:
            evolution_points.append({
                "chapter": snap.chapter_number,
                "chapter_title": snap.chapter_title,
                "arc_progress": snap.arc_progress,
                "changes": snap.personality_changes,
                "summary": snap.summary,
            })
        return {
            "name": char.name,
            "role": char.role,
            "arc_description": char.arc_description,
            "current_arc_progress": char.arc_progress,
            "snapshot_count": len(snapshots),
            "evolution": evolution_points,
        }

    def _row_to_snapshot(self, row: dict) -> CharacterSnapshot:
        """将 DB 行转换为 CharacterSnapshot 模型"""
        return CharacterSnapshot(
            id=row.get("id", ""),
            character_id=row.get("character_id", ""),
            chapter_number=row.get("chapter_number", 0),
            chapter_title=row.get("chapter_title", ""),
            arc_progress=row.get("arc_progress", ""),
            personality_changes=row.get("personality_changes", ""),
            appearance_changes=row.get("appearance_changes", ""),
            new_abilities=row.get("new_abilities", []),
            lost_abilities=row.get("lost_abilities", []),
            key_relationships_changed=row.get("key_relationships_changed", {}),
            internal_state=row.get("internal_state", ""),
            summary=row.get("summary", ""),
            created_at=row.get("created_at", ""),
        )

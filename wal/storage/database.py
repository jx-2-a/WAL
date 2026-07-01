"""SQLite 数据库管理器 — 架构初始化、连接管理、YAML 迁移

替代原有的 YAML 文件级存储，提供：
- 17 张核心表 + 1 个 FTS5 虚拟表
- 连接池管理（WAL 模式，支持并发读）
- 从 YAML 项目目录迁移数据
- 外键约束 + 性能索引
"""

import json
import os
import sqlite3
from pathlib import Path
from typing import Optional


# ── 完整数据库架构 DDL ──────────────────────────────────────────────

SCHEMA_DDL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ═══ 故事结构 ═══

CREATE TABLE IF NOT EXISTS stories (
    id TEXT PRIMARY KEY DEFAULT 'main',
    name TEXT NOT NULL DEFAULT '',
    author TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    genre TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'planning',
    created_at TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    style TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS parts (
    id TEXT PRIMARY KEY,
    story_id TEXT NOT NULL DEFAULT 'main',
    number INTEGER NOT NULL DEFAULT 0,
    title TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (story_id) REFERENCES stories(id)
);
CREATE INDEX IF NOT EXISTS idx_parts_story ON parts(story_id);

CREATE TABLE IF NOT EXISTS volumes (
    id TEXT PRIMARY KEY,
    part_id TEXT DEFAULT NULL,
    story_id TEXT NOT NULL DEFAULT 'main',
    number INTEGER NOT NULL DEFAULT 0,
    title TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    theme TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'planning',
    notes TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (story_id) REFERENCES stories(id)
);
CREATE INDEX IF NOT EXISTS idx_volumes_story ON volumes(story_id);
CREATE INDEX IF NOT EXISTS idx_volumes_part ON volumes(part_id);

CREATE TABLE IF NOT EXISTS chapters (
    id TEXT PRIMARY KEY,
    volume_id TEXT DEFAULT NULL,
    story_id TEXT NOT NULL DEFAULT 'main',
    number INTEGER NOT NULL DEFAULT 0,
    title TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft',
    summary TEXT NOT NULL DEFAULT '',
    word_count_target INTEGER NOT NULL DEFAULT 3000,
    actual_word_count INTEGER NOT NULL DEFAULT 0,
    plot_points_involved TEXT NOT NULL DEFAULT '[]',
    character_appearances TEXT NOT NULL DEFAULT '{}',
    notes TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (story_id) REFERENCES stories(id)
);
CREATE INDEX IF NOT EXISTS idx_chapters_story ON chapters(story_id, number);
CREATE INDEX IF NOT EXISTS idx_chapters_volume ON chapters(volume_id);

CREATE TABLE IF NOT EXISTS scenes (
    id TEXT PRIMARY KEY,
    chapter_id TEXT NOT NULL DEFAULT '',
    scene_index INTEGER NOT NULL DEFAULT 0,
    title TEXT NOT NULL DEFAULT '',
    location_id TEXT NOT NULL DEFAULT '',
    time_point TEXT NOT NULL DEFAULT '',
    characters_present TEXT NOT NULL DEFAULT '[]',
    content TEXT NOT NULL DEFAULT '',
    plot_advancements TEXT NOT NULL DEFAULT '[]',
    notes TEXT NOT NULL DEFAULT '',
    word_count INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_scenes_chapter ON scenes(chapter_id, scene_index);

-- ═══ 角色 ═══

CREATE TABLE IF NOT EXISTS characters (
    id TEXT PRIMARY KEY,
    story_id TEXT NOT NULL DEFAULT 'main',
    name TEXT NOT NULL DEFAULT '',
    aliases TEXT NOT NULL DEFAULT '[]',
    role TEXT NOT NULL DEFAULT 'supporting',
    gender TEXT NOT NULL DEFAULT '',
    age TEXT NOT NULL DEFAULT '',
    appearance TEXT NOT NULL DEFAULT '',
    personality_traits TEXT NOT NULL DEFAULT '[]',
    background_story TEXT NOT NULL DEFAULT '',
    motivation TEXT NOT NULL DEFAULT '',
    arc_description TEXT NOT NULL DEFAULT '',
    arc_progress TEXT NOT NULL DEFAULT '',
    abilities TEXT NOT NULL DEFAULT '[]',
    weaknesses TEXT NOT NULL DEFAULT '[]',
    first_appearance TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (story_id) REFERENCES stories(id)
);
CREATE INDEX IF NOT EXISTS idx_characters_story ON characters(story_id);

CREATE TABLE IF NOT EXISTS relationships (
    id TEXT PRIMARY KEY,
    story_id TEXT NOT NULL DEFAULT 'main',
    character_a TEXT NOT NULL DEFAULT '',
    character_b TEXT NOT NULL DEFAULT '',
    rel_type TEXT NOT NULL DEFAULT 'other',
    description TEXT NOT NULL DEFAULT '',
    dynamics TEXT NOT NULL DEFAULT '',
    history TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (story_id) REFERENCES stories(id),
    FOREIGN KEY (character_a) REFERENCES characters(id) ON DELETE CASCADE,
    FOREIGN KEY (character_b) REFERENCES characters(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_rel_a ON relationships(character_a);
CREATE INDEX IF NOT EXISTS idx_rel_b ON relationships(character_b);

CREATE TABLE IF NOT EXISTS character_snapshots (
    id TEXT PRIMARY KEY,
    character_id TEXT NOT NULL DEFAULT '',
    chapter_number INTEGER NOT NULL DEFAULT 0,
    chapter_title TEXT NOT NULL DEFAULT '',
    arc_progress TEXT NOT NULL DEFAULT '',
    personality_changes TEXT NOT NULL DEFAULT '',
    appearance_changes TEXT NOT NULL DEFAULT '',
    new_abilities TEXT NOT NULL DEFAULT '[]',
    lost_abilities TEXT NOT NULL DEFAULT '[]',
    key_relationships_changed TEXT NOT NULL DEFAULT '{}',
    internal_state TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_snapshots_char ON character_snapshots(character_id, chapter_number);

-- ═══ 剧情 ═══

CREATE TABLE IF NOT EXISTS plot_lines (
    id TEXT PRIMARY KEY,
    story_id TEXT NOT NULL DEFAULT 'main',
    parent_id TEXT DEFAULT NULL,
    name TEXT NOT NULL DEFAULT '',
    level TEXT NOT NULL DEFAULT 'sub',
    plot_type TEXT NOT NULL DEFAULT 'sub',
    description TEXT NOT NULL DEFAULT '',
    theme TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    started_in_chapter INTEGER NOT NULL DEFAULT 1,
    target_chapter INTEGER NOT NULL DEFAULT 0,
    notes TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (story_id) REFERENCES stories(id)
);
CREATE INDEX IF NOT EXISTS idx_plots_story ON plot_lines(story_id);
CREATE INDEX IF NOT EXISTS idx_plots_parent ON plot_lines(parent_id);
CREATE INDEX IF NOT EXISTS idx_plots_level ON plot_lines(level);

CREATE TABLE IF NOT EXISTS plot_points (
    id TEXT PRIMARY KEY,
    plot_id TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    order_index INTEGER NOT NULL DEFAULT 0,
    chapter_assigned INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    prerequisites TEXT NOT NULL DEFAULT '[]',
    impacts_characters TEXT NOT NULL DEFAULT '[]',
    emotional_tone TEXT NOT NULL DEFAULT '',
    estimated_words INTEGER NOT NULL DEFAULT 0,
    notes TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (plot_id) REFERENCES plot_lines(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_points_plot ON plot_points(plot_id);
CREATE INDEX IF NOT EXISTS idx_points_chapter ON plot_points(chapter_assigned);

CREATE TABLE IF NOT EXISTS plot_intersections (
    id TEXT PRIMARY KEY,
    plot_a TEXT NOT NULL DEFAULT '',
    plot_b TEXT NOT NULL DEFAULT '',
    at_plot_point_a TEXT NOT NULL DEFAULT '',
    at_plot_point_b TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    chapter_hint INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (plot_a) REFERENCES plot_lines(id) ON DELETE CASCADE,
    FOREIGN KEY (plot_b) REFERENCES plot_lines(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_intersect_a ON plot_intersections(plot_a);
CREATE INDEX IF NOT EXISTS idx_intersect_b ON plot_intersections(plot_b);

CREATE TABLE IF NOT EXISTS foreshadowings (
    id TEXT PRIMARY KEY,
    story_id TEXT NOT NULL DEFAULT 'main',
    description TEXT NOT NULL DEFAULT '',
    created_at_chapter INTEGER NOT NULL DEFAULT 0,
    created_at_volume INTEGER NOT NULL DEFAULT 0,
    target_chapter INTEGER NOT NULL DEFAULT 0,
    resolved_at_chapter INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    urgency TEXT NOT NULL DEFAULT 'medium',
    related_plot_lines TEXT NOT NULL DEFAULT '[]',
    related_characters TEXT NOT NULL DEFAULT '[]',
    resolution_notes TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (story_id) REFERENCES stories(id)
);
CREATE INDEX IF NOT EXISTS idx_foreshadow_story ON foreshadowings(story_id);
CREATE INDEX IF NOT EXISTS idx_foreshadow_status ON foreshadowings(status);

-- ═══ 世界观 ═══

CREATE TABLE IF NOT EXISTS world_settings (
    id TEXT PRIMARY KEY DEFAULT 'world',
    story_id TEXT NOT NULL DEFAULT 'main' UNIQUE,
    world_name TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    magic_system TEXT NOT NULL DEFAULT '',
    technology_level TEXT NOT NULL DEFAULT '',
    social_structure TEXT NOT NULL DEFAULT '',
    history TEXT NOT NULL DEFAULT '',
    races TEXT NOT NULL DEFAULT '[]',
    factions TEXT NOT NULL DEFAULT '[]',
    notes TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (story_id) REFERENCES stories(id)
);

CREATE TABLE IF NOT EXISTS world_rules (
    id TEXT PRIMARY KEY,
    world_id TEXT NOT NULL DEFAULT 'world',
    name TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (world_id) REFERENCES world_settings(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS locations (
    id TEXT PRIMARY KEY,
    story_id TEXT NOT NULL DEFAULT 'main',
    name TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    location_type TEXT NOT NULL DEFAULT '',
    parent_location TEXT NOT NULL DEFAULT '',
    atmosphere TEXT NOT NULL DEFAULT '',
    notable_features TEXT NOT NULL DEFAULT '[]',
    related_characters TEXT NOT NULL DEFAULT '[]',
    FOREIGN KEY (story_id) REFERENCES stories(id)
);
CREATE INDEX IF NOT EXISTS idx_loc_story ON locations(story_id);

CREATE TABLE IF NOT EXISTS timeline_events (
    id TEXT PRIMARY KEY,
    story_id TEXT NOT NULL DEFAULT 'main',
    title TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    time_point TEXT NOT NULL DEFAULT '',
    related_chapters TEXT NOT NULL DEFAULT '[]',
    related_characters TEXT NOT NULL DEFAULT '[]',
    is_backstory INTEGER NOT NULL DEFAULT 0,
    causes TEXT NOT NULL DEFAULT '[]',
    effects TEXT NOT NULL DEFAULT '[]',
    FOREIGN KEY (story_id) REFERENCES stories(id)
);
CREATE INDEX IF NOT EXISTS idx_tl_story ON timeline_events(story_id);

-- ═══ 索引与搜索 ═══

CREATE TABLE IF NOT EXISTS content_index (
    id TEXT PRIMARY KEY,
    story_id TEXT NOT NULL DEFAULT 'main',
    keyword TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    chapter_references TEXT NOT NULL DEFAULT '[]',
    volume_references TEXT NOT NULL DEFAULT '[]',
    summary_context TEXT NOT NULL DEFAULT '',
    first_appearance_chapter INTEGER NOT NULL DEFAULT 0,
    last_appearance_chapter INTEGER NOT NULL DEFAULT 0,
    importance TEXT NOT NULL DEFAULT 'medium',
    FOREIGN KEY (story_id) REFERENCES stories(id)
);
CREATE INDEX IF NOT EXISTS idx_cindex_story ON content_index(story_id);
CREATE INDEX IF NOT EXISTS idx_cindex_keyword ON content_index(story_id, keyword);
CREATE INDEX IF NOT EXISTS idx_cindex_category ON content_index(story_id, category);

-- FTS5 全文搜索（外部内容表模式）
CREATE VIRTUAL TABLE IF NOT EXISTS content_fts USING fts5(
    chapter_id,
    chapter_title,
    chapter_summary,
    scene_id,
    scene_title,
    scene_content,
    characters_present,
    locations,
    plot_references,
    content='',
    content_rowid='rowid',
    tokenize='unicode61 remove_diacritics 1'
);

-- ═══ 里程碑 ═══

CREATE TABLE IF NOT EXISTS milestones (
    id TEXT PRIMARY KEY,
    story_id TEXT NOT NULL DEFAULT 'main',
    name TEXT NOT NULL DEFAULT '',
    chapter_number INTEGER NOT NULL DEFAULT 0,
    volume_number INTEGER NOT NULL DEFAULT 0,
    story_state_summary TEXT NOT NULL DEFAULT '',
    character_states TEXT NOT NULL DEFAULT '{}',
    plot_states TEXT NOT NULL DEFAULT '{}',
    unresolved_foreshadowings TEXT NOT NULL DEFAULT '[]',
    total_words_at_point INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (story_id) REFERENCES stories(id)
);
CREATE INDEX IF NOT EXISTS idx_milestones_story ON milestones(story_id);

-- ═══ 自主模式 ═══

CREATE TABLE IF NOT EXISTS auto_decisions (
    id TEXT PRIMARY KEY,
    story_id TEXT NOT NULL DEFAULT 'main',
    timestamp TEXT NOT NULL DEFAULT '',
    decision_type TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    reasoning TEXT NOT NULL DEFAULT '',
    impact_level TEXT NOT NULL DEFAULT 'minor',
    affected_elements TEXT NOT NULL DEFAULT '[]',
    approved INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (story_id) REFERENCES stories(id)
);
CREATE INDEX IF NOT EXISTS idx_auto_story ON auto_decisions(story_id);

-- ═══ 规划笔记 ═══

CREATE TABLE IF NOT EXISTS planning_notes (
    id TEXT PRIMARY KEY,
    story_id TEXT NOT NULL DEFAULT 'main',
    title TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL DEFAULT '',
    decisions TEXT NOT NULL DEFAULT '',
    related_tools TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (story_id) REFERENCES stories(id)
);
CREATE INDEX IF NOT EXISTS idx_planotes_story ON planning_notes(story_id);
CREATE INDEX IF NOT EXISTS idx_planotes_category ON planning_notes(category);

-- ═══ 自定义文档 ═══

CREATE TABLE IF NOT EXISTS custom_documents (
    id TEXT PRIMARY KEY,
    story_id TEXT NOT NULL DEFAULT 'main',
    title TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (story_id) REFERENCES stories(id)
);
CREATE INDEX IF NOT EXISTS idx_customdocs_story ON custom_documents(story_id);
CREATE INDEX IF NOT EXISTS idx_customdocs_category ON custom_documents(category);

-- ═══ Agent 配置 ═══

CREATE TABLE IF NOT EXISTS agent_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);
"""

# ── 插入默认配置 ───────────────────────────────────────────────────

DEFAULT_CONFIG_DDL = """
INSERT OR IGNORE INTO agent_config (key, value) VALUES
    ('quiet_mode', 'false'),
    ('autonomy_level', 'suggest_only'),
    ('max_context_tokens', '90000'),
    ('window_rounds', '12');
"""


class Database:
    """SQLite 数据库管理器

    用法:
        db = Database("projects/修仙传奇/wal.db")
        db.init_schema()
        with db.get_conn() as conn:
            conn.execute("SELECT * FROM chapters WHERE story_id = ?", ("main",))
    """

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def get_conn(self) -> sqlite3.Connection:
        """获取数据库连接（WAL 模式，外键启用）"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def init_schema(self) -> None:
        """初始化所有表和索引（幂等 — 使用 IF NOT EXISTS）"""
        with self.get_conn() as conn:
            conn.executescript(SCHEMA_DDL)
            conn.executescript(DEFAULT_CONFIG_DDL)
            # 增量迁移：为新版本添加缺失的列
            self._migrate_columns(conn)

    def schema_exists(self) -> bool:
        """检查数据库是否已初始化"""
        if not self.db_path.exists():
            return False
        try:
            with self.get_conn() as conn:
                cur = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='stories'"
                )
                return cur.fetchone() is not None
        except Exception:
            return False

    @staticmethod
    def _migrate_columns(conn: sqlite3.Connection) -> None:
        """增量迁移：为旧版本数据库添加缺失的列"""
        # 检查 stories 表是否有 style 列
        cur = conn.execute("PRAGMA table_info(stories)")
        columns = {row[1] for row in cur.fetchall()}
        if "style" not in columns:
            conn.execute("ALTER TABLE stories ADD COLUMN style TEXT NOT NULL DEFAULT ''")

    # ── YAML 迁移 ──────────────────────────────────────────────────

    def migrate_from_yaml(self, project_dir: str) -> dict:
        """从 YAML 项目目录迁移数据到 SQLite

        Returns:
            {"migrated": [...], "skipped": [...], "errors": [...]}
        """
        import yaml

        report = {"migrated": [], "skipped": [], "errors": []}
        base = Path(project_dir)

        self.init_schema()

        # 1. story.yaml → stories + chapters + scenes
        story_file = base / "story.yaml"
        if story_file.exists():
            try:
                with open(story_file, "r", encoding="utf-8") as f:
                    story_data = yaml.safe_load(f) or {}
                self._migrate_story(story_data, report)
            except Exception as e:
                report["errors"].append(f"story.yaml: {e}")

        # 2. characters.yaml → characters + relationships
        char_file = base / "characters.yaml"
        if char_file.exists():
            try:
                with open(char_file, "r", encoding="utf-8") as f:
                    char_data = yaml.safe_load(f) or {}
                self._migrate_characters(char_data, report)
            except Exception as e:
                report["errors"].append(f"characters.yaml: {e}")

        # 3. plot_lines.yaml → plot_lines + plot_points + intersections
        plot_file = base / "plot_lines.yaml"
        if plot_file.exists():
            try:
                with open(plot_file, "r", encoding="utf-8") as f:
                    plot_data = yaml.safe_load(f) or {}
                self._migrate_plots(plot_data, report)
            except Exception as e:
                report["errors"].append(f"plot_lines.yaml: {e}")

        # 4. world.yaml → world_settings + world_rules
        world_file = base / "world.yaml"
        if world_file.exists():
            try:
                with open(world_file, "r", encoding="utf-8") as f:
                    world_data = yaml.safe_load(f) or {}
                self._migrate_world(world_data, report)
            except Exception as e:
                report["errors"].append(f"world.yaml: {e}")

        # 5. locations.yaml → locations
        loc_file = base / "locations.yaml"
        if loc_file.exists():
            try:
                with open(loc_file, "r", encoding="utf-8") as f:
                    loc_data = yaml.safe_load(f) or {}
                self._migrate_locations(loc_data, report)
            except Exception as e:
                report["errors"].append(f"locations.yaml: {e}")

        # 6. timeline.yaml → timeline_events
        tl_file = base / "timeline.yaml"
        if tl_file.exists():
            try:
                with open(tl_file, "r", encoding="utf-8") as f:
                    tl_data = yaml.safe_load(f) or []
                self._migrate_timeline(tl_data, report)
            except Exception as e:
                report["errors"].append(f"timeline.yaml: {e}")

        return report

    def _migrate_story(self, data: dict, report: dict) -> None:
        """迁移故事数据"""
        story_id = "main"
        with self.get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO stories (id, name, author, summary, genre, tags, status, created_at, updated_at, notes, style)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    story_id,
                    data.get("name", ""),
                    data.get("author", ""),
                    data.get("summary", ""),
                    data.get("genre", ""),
                    json.dumps(data.get("tags", []), ensure_ascii=False),
                    data.get("status", "planning"),
                    data.get("created_at", ""),
                    data.get("updated_at", ""),
                    data.get("notes", ""),
                    data.get("style", ""),
                ),
            )

            for ch in data.get("chapters", []):
                ch_number = ch.get("number", 0)
                ch_id = f"ch_{ch_number:04d}"
                conn.execute(
                    """INSERT OR REPLACE INTO chapters (id, volume_id, story_id, number, title, status, summary,
                       word_count_target, actual_word_count, plot_points_involved, character_appearances, notes)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        ch_id, None, story_id, ch_number,
                        ch.get("title", ""), ch.get("status", "draft"),
                        ch.get("summary", ""), ch.get("word_count_target", 3000),
                        ch.get("actual_word_count", 0),
                        json.dumps(ch.get("plot_points_involved", []), ensure_ascii=False),
                        json.dumps(ch.get("character_appearances", {}), ensure_ascii=False),
                        ch.get("notes", ""),
                    ),
                )

                for si, sc in enumerate(ch.get("scenes", [])):
                    sc_id = sc.get("id", f"sc_ch{ch_number}_{si+1:02d}")
                    conn.execute(
                        """INSERT OR REPLACE INTO scenes (id, chapter_id, scene_index, title, location_id,
                           time_point, characters_present, content, plot_advancements, notes, word_count)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            sc_id, ch_id, si,
                            sc.get("title", ""), sc.get("location_id", ""),
                            sc.get("time_point", ""),
                            json.dumps(sc.get("characters_present", []), ensure_ascii=False),
                            sc.get("content", ""),
                            json.dumps(sc.get("plot_advancements", []), ensure_ascii=False),
                            sc.get("notes", ""), sc.get("word_count", 0),
                        ),
                    )

                    # 构建 FTS5 索引
                    if sc.get("content"):
                        try:
                            conn.execute(
                                """INSERT INTO content_fts (chapter_id, chapter_title, chapter_summary,
                                   scene_id, scene_title, scene_content, characters_present, locations, plot_references)
                                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                                (
                                    ch_id, ch.get("title", ""), ch.get("summary", ""),
                                    sc_id, sc.get("title", ""), sc.get("content", ""),
                                    ", ".join(sc.get("characters_present", [])),
                                    sc.get("location_id", ""),
                                    ", ".join(sc.get("plot_advancements", [])),
                                ),
                            )
                        except Exception:
                            pass  # FTS 索引失败不阻塞迁移

        report["migrated"].append("story")

    def _migrate_characters(self, data: dict, report: dict) -> None:
        """迁移角色数据（两阶段：先角色，后关系）"""
        story_id = "main"
        seen_ids = set()
        char_ids = []  # 记录成功插入的角色 ID
        relationships_to_insert = []  # 延迟插入的关系

        with self.get_conn() as conn:
            # 第一遍：插入所有角色
            for char_id, char_data in data.items():
                char_name = char_data.get("name", "")
                dedup_key = f"{char_name}_{char_data.get('role', '')}"
                if dedup_key in seen_ids:
                    continue
                seen_ids.add(dedup_key)

                conn.execute(
                    """INSERT OR REPLACE INTO characters (id, story_id, name, aliases, role, gender, age,
                       appearance, personality_traits, background_story, motivation, arc_description,
                       arc_progress, abilities, weaknesses, first_appearance, notes)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        char_id, story_id, char_name,
                        json.dumps(char_data.get("aliases", []), ensure_ascii=False),
                        char_data.get("role", "supporting"),
                        char_data.get("gender", ""), char_data.get("age", ""),
                        char_data.get("appearance", ""),
                        json.dumps(char_data.get("personality_traits", []), ensure_ascii=False),
                        char_data.get("background_story", ""),
                        char_data.get("motivation", ""),
                        char_data.get("arc_description", ""),
                        char_data.get("arc_progress", ""),
                        json.dumps(char_data.get("abilities", []), ensure_ascii=False),
                        json.dumps(char_data.get("weaknesses", []), ensure_ascii=False),
                        char_data.get("first_appearance", ""),
                        char_data.get("notes", ""),
                    ),
                )
                char_ids.append(char_id)

                # 收集关系，稍后插入
                for rel_target, rel_data in char_data.get("relationships", {}).items():
                    relationships_to_insert.append((char_id, rel_target, rel_data))

            # 第二遍：插入关系（仅当双方角色都存在）
            valid_char_ids = set(char_ids)
            for char_id, rel_target, rel_data in relationships_to_insert:
                if char_id not in valid_char_ids or rel_target not in valid_char_ids:
                    continue  # 跳过引用不存在角色的关系
                rel_id = f"rel_{char_id}_{rel_target}"
                try:
                    conn.execute(
                        """INSERT OR REPLACE INTO relationships (id, story_id, character_a, character_b,
                           rel_type, description, dynamics, history)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            rel_id, story_id, char_id, rel_target,
                            rel_data.get("rel_type", "other"),
                            rel_data.get("description", ""),
                            rel_data.get("dynamics", ""),
                            rel_data.get("history", ""),
                        ),
                    )
                except Exception:
                    pass  # 跳过损坏的关系引用

        report["migrated"].append("characters")

    def _migrate_plots(self, data: dict, report: dict) -> None:
        """迁移剧情线数据（两阶段：先剧情线+情节点，后交汇点）"""
        story_id = "main"
        seen_names = set()
        plot_ids = []
        intersections_to_insert = []

        with self.get_conn() as conn:
            # 第一遍：插入所有剧情线和情节点
            for plot_id, plot_data in data.items():
                plot_name = plot_data.get("name", "")
                if plot_name in seen_names:
                    continue
                seen_names.add(plot_name)

                pt = plot_data.get("plot_type", "sub")
                conn.execute(
                    """INSERT OR REPLACE INTO plot_lines (id, story_id, parent_id, name, level, plot_type,
                       description, theme, status, started_in_chapter, target_chapter, notes)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        plot_id, story_id, None, plot_name,
                        "main" if pt == "main" else "sub",
                        pt,
                        plot_data.get("description", ""),
                        plot_data.get("theme", ""),
                        plot_data.get("status", "active"),
                        plot_data.get("started_in_chapter", 1),
                        plot_data.get("target_chapter", 0),
                        plot_data.get("notes", ""),
                    ),
                )
                plot_ids.append(plot_id)

                # 情节点
                for pp in plot_data.get("plot_points", []):
                    pp_id = pp.get("id", "")
                    if pp_id:
                        conn.execute(
                            """INSERT OR REPLACE INTO plot_points (id, plot_id, title, description,
                               order_index, chapter_assigned, status, prerequisites, impacts_characters,
                               emotional_tone, estimated_words, notes)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (
                                pp_id, plot_id,
                                pp.get("title", ""), pp.get("description", ""),
                                pp.get("order_index", 0), pp.get("chapter_assigned", 0),
                                pp.get("status", "pending"),
                                json.dumps(pp.get("prerequisites", []), ensure_ascii=False),
                                json.dumps(pp.get("impacts_characters", []), ensure_ascii=False),
                                pp.get("emotional_tone", ""),
                                pp.get("estimated_words", 0),
                                pp.get("notes", ""),
                            ),
                        )

                # 收集交汇点，稍后插入
                for inter in plot_data.get("intersects_with", []):
                    intersections_to_insert.append((plot_id, inter))

            # 第二遍：插入交汇点（仅当双方剧情线都存在）
            valid_plot_ids = set(plot_ids)
            for plot_id, inter in intersections_to_insert:
                plot_a = inter.get("plot_a", plot_id)
                plot_b = inter.get("plot_b", "")
                if plot_a not in valid_plot_ids and plot_b not in valid_plot_ids:
                    continue  # 跳过引用不存在剧情线的交汇
                inter_id = f"inter_{plot_id}_{plot_b}"
                try:
                    conn.execute(
                        """INSERT OR REPLACE INTO plot_intersections (id, plot_a, plot_b,
                           at_plot_point_a, at_plot_point_b, description, chapter_hint)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (
                            inter_id, plot_a, plot_b,
                            inter.get("at_plot_point_a", ""),
                            inter.get("at_plot_point_b", ""),
                            inter.get("description", ""),
                            inter.get("chapter_hint", 0),
                        ),
                    )
                except Exception:
                    pass  # 跳过损坏的交汇引用

        report["migrated"].append("plot_lines")

    def _migrate_world(self, data: dict, report: dict) -> None:
        """迁移世界观数据"""
        story_id = "main"
        world_id = "world"
        with self.get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO world_settings (id, story_id, world_name, description,
                   magic_system, technology_level, social_structure, history, races, factions, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    world_id, story_id,
                    data.get("world_name", ""), data.get("description", ""),
                    data.get("magic_system", ""), data.get("technology_level", ""),
                    data.get("social_structure", ""), data.get("history", ""),
                    json.dumps(data.get("races", []), ensure_ascii=False),
                    json.dumps(data.get("factions", []), ensure_ascii=False),
                    data.get("notes", ""),
                ),
            ) if data.get("world_name") else None

            for rule in data.get("rules", []):
                rule_id = f"rule_{rule.get('name', '')}"
                conn.execute(
                    """INSERT OR REPLACE INTO world_rules (id, world_id, name, description, category)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        rule_id, world_id,
                        rule.get("name", ""), rule.get("description", ""),
                        rule.get("category", ""),
                    ),
                )

        report["migrated"].append("world")

    def _migrate_locations(self, data: dict, report: dict) -> None:
        """迁移地点数据"""
        story_id = "main"
        with self.get_conn() as conn:
            for loc_id, loc_data in data.items():
                conn.execute(
                    """INSERT OR REPLACE INTO locations (id, story_id, name, description,
                       location_type, parent_location, atmosphere, notable_features, related_characters)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        loc_id, story_id,
                        loc_data.get("name", ""), loc_data.get("description", ""),
                        loc_data.get("location_type", ""), loc_data.get("parent_location", ""),
                        loc_data.get("atmosphere", ""),
                        json.dumps(loc_data.get("notable_features", []), ensure_ascii=False),
                        json.dumps(loc_data.get("related_characters", []), ensure_ascii=False),
                    ),
                )
        report["migrated"].append("locations")

    def _migrate_timeline(self, data: list, report: dict) -> None:
        """迁移时间线数据"""
        story_id = "main"
        with self.get_conn() as conn:
            for event in data:
                conn.execute(
                    """INSERT OR REPLACE INTO timeline_events (id, story_id, title, description,
                       time_point, related_chapters, related_characters, is_backstory, causes, effects)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        event.get("id", ""), story_id,
                        event.get("title", ""), event.get("description", ""),
                        event.get("time_point", ""),
                        json.dumps(event.get("related_chapters", []), ensure_ascii=False),
                        json.dumps(event.get("related_characters", []), ensure_ascii=False),
                        1 if event.get("is_backstory") else 0,
                        json.dumps(event.get("causes", []), ensure_ascii=False),
                        json.dumps(event.get("effects", []), ensure_ascii=False),
                    ),
                )
        report["migrated"].append("timeline")

    # ── 导出为 YAML（备份用）───────────────────────────────────────

    def export_to_yaml(self, project_dir: str) -> dict:
        """将 SQLite 数据导出回 YAML 文件

        Returns:
            {"exported": [...], "errors": [...]}
        """
        import yaml

        report = {"exported": [], "errors": []}
        base = Path(project_dir)
        base.mkdir(parents=True, exist_ok=True)

        with self.get_conn() as conn:
            # story + chapters + scenes → story.yaml
            try:
                story_row = conn.execute("SELECT * FROM stories WHERE id = 'main'").fetchone()
                if story_row:
                    story_dict = dict(story_row)
                    story_dict["tags"] = json.loads(story_dict["tags"])
                    del story_dict["id"]

                    # 加载章节
                    chapters_rows = conn.execute(
                        "SELECT * FROM chapters WHERE story_id = 'main' ORDER BY number"
                    ).fetchall()
                    chapters_list = []
                    for ch in chapters_rows:
                        ch_dict = dict(ch)
                        ch_dict["plot_points_involved"] = json.loads(ch_dict["plot_points_involved"])
                        ch_dict["character_appearances"] = json.loads(ch_dict["character_appearances"])
                        del ch_dict["id"]; del ch_dict["story_id"]; del ch_dict["volume_id"]

                        # 加载场景
                        scenes_rows = conn.execute(
                            "SELECT * FROM scenes WHERE chapter_id = ? ORDER BY scene_index",
                            (ch["id"],)
                        ).fetchall()
                        scenes_list = []
                        for sc in scenes_rows:
                            sc_dict = dict(sc)
                            sc_dict["characters_present"] = json.loads(sc_dict["characters_present"])
                            sc_dict["plot_advancements"] = json.loads(sc_dict["plot_advancements"])
                            del sc_dict["chapter_id"]
                            scenes_list.append(sc_dict)
                        ch_dict["scenes"] = scenes_list
                        chapters_list.append(ch_dict)
                    story_dict["chapters"] = chapters_list

                    with open(base / "story.yaml", "w", encoding="utf-8") as f:
                        yaml.dump(story_dict, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
                    report["exported"].append("story.yaml")
            except Exception as e:
                report["errors"].append(f"story.yaml export: {e}")

            # characters → characters.yaml
            try:
                char_rows = conn.execute("SELECT * FROM characters WHERE story_id = 'main'").fetchall()
                char_dict = {}
                for c in char_rows:
                    cd = dict(c)
                    # 加载关系
                    rel_rows = conn.execute(
                        "SELECT * FROM relationships WHERE character_a = ?", (cd["id"],)
                    ).fetchall()
                    rels = {}
                    for r in rel_rows:
                        rd = dict(r)
                        del rd["id"]; del rd["story_id"]
                        rels[rd["character_b"]] = rd
                    cd["relationships"] = rels
                    # 解析 JSON 字段
                    for f in ("aliases", "personality_traits", "abilities", "weaknesses"):
                        cd[f] = json.loads(cd[f])
                    del cd["story_id"]
                    char_dict[cd["id"]] = cd
                if char_dict:
                    with open(base / "characters.yaml", "w", encoding="utf-8") as f:
                        yaml.dump(char_dict, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
                    report["exported"].append("characters.yaml")
            except Exception as e:
                report["errors"].append(f"characters.yaml export: {e}")

            # plot_lines → plot_lines.yaml
            try:
                plot_rows = conn.execute("SELECT * FROM plot_lines WHERE story_id = 'main'").fetchall()
                plot_dict = {}
                for p in plot_rows:
                    pdict = dict(p)
                    # 情节点
                    pp_rows = conn.execute(
                        "SELECT * FROM plot_points WHERE plot_id = ? ORDER BY order_index",
                        (pdict["id"],)
                    ).fetchall()
                    pp_list = []
                    for pp in pp_rows:
                        ppd = dict(pp)
                        ppd["prerequisites"] = json.loads(ppd["prerequisites"])
                        ppd["impacts_characters"] = json.loads(ppd["impacts_characters"])
                        del ppd["plot_id"]
                        pp_list.append(ppd)
                    pdict["plot_points"] = pp_list

                    # 交汇点
                    inter_rows = conn.execute(
                        "SELECT * FROM plot_intersections WHERE plot_a = ? OR plot_b = ?",
                        (pdict["id"], pdict["id"])
                    ).fetchall()
                    inter_list = []
                    seen = set()
                    for inter in inter_rows:
                        idict = dict(inter)
                        key = (idict["plot_a"], idict["plot_b"])
                        if key not in seen:
                            seen.add(key)
                            inter_list.append(idict)
                    pdict["intersects_with"] = inter_list
                    del pdict["story_id"]
                    plot_dict[pdict["id"]] = pdict
                if plot_dict:
                    with open(base / "plot_lines.yaml", "w", encoding="utf-8") as f:
                        yaml.dump(plot_dict, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
                    report["exported"].append("plot_lines.yaml")
            except Exception as e:
                report["errors"].append(f"plot_lines.yaml export: {e}")

        return report

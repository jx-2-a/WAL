"""SQLite 数据库管理器 — 连接管理、Schema 初始化

提供：
- 17 张核心表 + 1 个 FTS5 虚拟表
- 连接池管理（WAL 模式，支持并发读）
- 外键约束 + 性能索引
"""

import json
import os
import sqlite3
from pathlib import Path
from typing import Optional


def _as_str_list(value) -> list[str]:
    """把 DB 里的 JSON 列表 / 逗号串 / 原值统一转成 str 列表（FTS 重建用）"""
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [str(x) for x in value]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(x) for x in parsed]
        except (json.JSONDecodeError, TypeError):
            pass
        return [value]
    return [str(value)]


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

-- FTS5 全文搜索（普通表 + unicode61 + 中文逐字预分词）
-- 注：不再用 contentless(content='')——contentless 下 snippet() 恒 NULL
-- 且 INSERT OR REPLACE 语义不靠谱；中文检索靠 fts_util.fts_prepare 在
-- 写入前把连续汉字拆成逐字 token（unicode61 不切中文词，否则搜不到）。
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

-- ═══ 防跑偏：铁律引擎 ═══

CREATE TABLE IF NOT EXISTS iron_laws (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    keywords TEXT NOT NULL DEFAULT '[]',
    forbidden_volumes TEXT NOT NULL DEFAULT '[]',
    only_in_volume INTEGER NOT NULL DEFAULT 0,
    severity TEXT NOT NULL DEFAULT 'warning',
    note TEXT NOT NULL DEFAULT ''
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
            # 旧版 contentless FTS 表 → 先 DROP，随后由 SCHEMA_DDL 按新式重建
            fts_rebuilt = self._prepare_fts_schema(conn)
            conn.executescript(SCHEMA_DDL)
            conn.executescript(DEFAULT_CONFIG_DDL)
            # 增量迁移：为新版本添加缺失的列
            self._migrate_columns(conn)
            # FTS 迁移后从 scenes 回灌索引；或索引为空但库里有正文时兜底重建
            if fts_rebuilt or self._fts_needs_rebuild(conn):
                self._rebuild_fts(conn)

    def _prepare_fts_schema(self, conn: sqlite3.Connection) -> bool:
        """检测旧版 contentless FTS 表并 DROP，返回是否需重建索引

        旧表特征：声明里有 `content_rowid`（contentless 专属标记）。
        新表是普通 FTS5 表，不含该标记。
        """
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='content_fts'"
        ).fetchone()
        if not row:
            return False
        sql = row[0] or ""
        if "content_rowid" in sql:
            conn.execute("DROP TABLE content_fts")
            return True
        return False

    def _fts_needs_rebuild(self, conn: sqlite3.Connection) -> bool:
        """FTS 索引为空但库里有正文 → 需要重建（迁移中断/手工清空后自愈）"""
        try:
            n = conn.execute("SELECT count(*) FROM content_fts").fetchone()[0]
            if n > 0:
                return False
            has_scenes = conn.execute(
                "SELECT count(*) FROM scenes s JOIN chapters c ON s.chapter_id = c.id "
                "WHERE c.story_id = 'main' AND length(trim(s.content)) > 0"
            ).fetchone()[0]
            return has_scenes > 0
        except Exception:
            return False

    def _rebuild_fts(self, conn: sqlite3.Connection) -> int:
        """全量重建 FTS 索引：从 scenes JOIN chapters 回灌，中文逐字预分词"""
        from .fts_util import fts_prepare

        rows = conn.execute(
            """SELECT s.id AS scene_id, s.title AS scene_title, s.content,
                      s.characters_present, s.location_id, s.plot_advancements,
                      c.id AS chapter_id, c.title AS chapter_title, c.summary AS chapter_summary
               FROM scenes s JOIN chapters c ON s.chapter_id = c.id
               WHERE c.story_id = 'main'"""
        ).fetchall()
        conn.execute("DELETE FROM content_fts")
        count = 0
        for r in rows:
            content = r["content"] or ""
            if not content.strip():
                continue
            chars = _as_str_list(r["characters_present"])
            plots = _as_str_list(r["plot_advancements"])
            conn.execute(
                """INSERT INTO content_fts
                   (chapter_id, chapter_title, chapter_summary, scene_id, scene_title,
                    scene_content, characters_present, locations, plot_references)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (r["chapter_id"], r["chapter_title"] or "", r["chapter_summary"] or "",
                 r["scene_id"], r["scene_title"] or "", fts_prepare(content),
                 ", ".join(chars), r["location_id"] or "", ", ".join(plots)),
            )
            count += 1
        conn.commit()
        return count

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

        # chapters.anchor — 章节锚点（防跑偏：本章应写什么）
        cur = conn.execute("PRAGMA table_info(chapters)")
        columns = {row[1] for row in cur.fetchall()}
        if "anchor" not in columns:
            conn.execute("ALTER TABLE chapters ADD COLUMN anchor TEXT NOT NULL DEFAULT ''")

        # volumes.chapter_start / chapter_end — 卷范围锁（防跑偏：卷含哪几章）
        cur = conn.execute("PRAGMA table_info(volumes)")
        columns = {row[1] for row in cur.fetchall()}
        if "chapter_start" not in columns:
            conn.execute("ALTER TABLE volumes ADD COLUMN chapter_start INTEGER NOT NULL DEFAULT 0")
        if "chapter_end" not in columns:
            conn.execute("ALTER TABLE volumes ADD COLUMN chapter_end INTEGER NOT NULL DEFAULT 0")


"""Agent 工具函数 — 供 AI Agent 调用的结构化接口

这些工具函数封装了对故事管理系统的访问，Agent 可以通过它们：
- 查看故事全貌和状态
- 获取特定章节的写作上下文
- 管理角色和剧情线
- 写入和更新内容
"""

import os
from pathlib import Path
from typing import Optional

from wal.core import StoryManager, PlotManager, CharacterManager, WorldManager
from wal.engine.context_builder import ContextBuilder
from wal.engine.prompts import PromptBuilder


def _get_project_path(name: str) -> str:
    base = Path(os.environ.get("WAL_PROJECTS", "projects"))
    return str(base / name)


def _init_managers(project_name: str):
    """初始化所有管理器"""
    proj = _get_project_path(project_name)
    sm = StoryManager(proj)
    sm.load_story()
    pm = PlotManager(proj)
    pm.load()
    cm = CharacterManager(proj)
    cm.load()
    wm = WorldManager(proj)
    wm.load()
    cb = ContextBuilder(sm, pm, cm, wm)
    return sm, pm, cm, wm, cb


# ============================================================
# Agent 可调用的工具函数
# ============================================================

def get_story_status(project_name: str) -> dict:
    """查看故事全貌 — 章节数、完成度、总字数"""
    proj = _get_project_path(project_name)
    sm = StoryManager(proj)
    sm.load_story()
    return sm.get_story_status()


def get_chapter_context(project_name: str, chapter_number: int) -> dict:
    """获取某个章节的完整写作上下文（剧情、角色、支线提醒）"""
    sm, pm, cm, wm, cb = _init_managers(project_name)
    return cb.build_writing_context(chapter_number)


def get_chapter_context_text(project_name: str, chapter_number: int) -> str:
    """获取精简版写作上下文（纯文本，适合直接粘贴给 LLM）"""
    sm, pm, cm, wm, cb = _init_managers(project_name)
    return cb.build_compact_context(chapter_number)


def list_dangling_plots(project_name: str) -> list[dict]:
    """列出所有未收束的支线"""
    proj = _get_project_path(project_name)
    pm = PlotManager(proj)
    pm.load()
    dangling = pm.find_dangling_plots()
    return [{"id": p.id, "name": p.name, "description": p.description,
             "progress": p.progress_percent(), "type": p.plot_type.value}
            for p in dangling]


def list_characters(project_name: str, role: str | None = None) -> list[dict]:
    """列出所有角色（可按类型过滤）"""
    proj = _get_project_path(project_name)
    cm = CharacterManager(proj)
    cm.load()
    chars = cm.list_characters(role)
    return [{"id": c.id, "name": c.name, "role": c.role,
             "motivation": c.motivation, "first_appearance": c.first_appearance}
            for c in chars]


def get_character(project_name: str, char_id: str) -> dict | None:
    """获取单个角色的完整档案"""
    proj = _get_project_path(project_name)
    cm = CharacterManager(proj)
    cm.load()
    char = cm.get_character(char_id)
    if not char:
        return None
    return char.model_dump(mode="json")


def list_plot_lines(project_name: str) -> list[dict]:
    """列出所有剧情线及完成进度"""
    proj = _get_project_path(project_name)
    pm = PlotManager(proj)
    pm.load()
    return pm.track_plot_progress()


def plot_health_check(project_name: str) -> dict:
    """主线支线健康度检查"""
    proj = _get_project_path(project_name)
    pm = PlotManager(proj)
    pm.load()
    return pm.plot_interweave_check()


def write_scene_content(project_name: str, chapter_number: int,
                        scene_index: int, content: str) -> dict:
    """将撰写好的场景正文写入指定章节"""
    proj = _get_project_path(project_name)
    sm = StoryManager(proj)
    sm.load_story()
    scene = sm.update_scene_content(chapter_number, scene_index, content)
    return {"id": scene.id, "title": scene.title, "word_count": scene.word_count}


def update_plot_point(project_name: str, plot_id: str, point_id: str,
                      status: str) -> dict:
    """更新情节点状态 (pending / in_progress / done)"""
    proj = _get_project_path(project_name)
    pm = PlotManager(proj)
    pm.load()
    pp = pm.update_plot_point_status(plot_id, point_id, status)
    return {"id": pp.id, "title": pp.title, "status": pp.status.value}


def suggest_next_scene(project_name: str, chapter_number: int) -> str:
    """基于当前剧情状态，给出下一场景建议（供 Agent 决策用）"""
    sm, pm, cm, wm, cb = _init_managers(project_name)
    ctx = cb.build_writing_context(chapter_number)

    lines = ["=== 下一场景建议 ===", ""]

    # 检查场景规划中还有哪些未写
    chapter = sm.get_chapter(chapter_number)
    if chapter:
        unwritten = [s for s in chapter.scenes if not s.content]
        if unwritten:
            lines.append(f"本章还有 {len(unwritten)} 个场景待写：")
            for s in unwritten:
                lines.append(f"  - {s.title} [{s.time_point}] @{s.location_id}")

    # 检查未完成的剧情任务
    pending_plots = [pp for pp in ctx.get("chapter_plots", [])
                     if pp.get("status") != "done"]
    if pending_plots:
        lines.append(f"\n待推进的剧情任务（{len(pending_plots)}个）：")
        for pp in pending_plots:
            lines.append(f"  - [{pp['type']}] {pp['name']}: {pp['task']}")

    # 未收束支线
    if ctx.get("dangling_plots"):
        lines.append("\n未收束支线提醒：")
        for dp in ctx["dangling_plots"]:
            lines.append(f"  - {dp['name']}（进度 {dp['progress']}%）")

    if len(lines) == 2:
        lines.append("本章场景均已规划，按顺序撰写即可。")

    return "\n".join(lines)


def export_outline(project_name: str) -> str:
    """导出故事大纲"""
    proj = _get_project_path(project_name)
    sm = StoryManager(proj)
    sm.load_story()
    return sm.export_outline()


def get_volume_context(project_name: str, volume_id: str) -> dict:
    """获取卷的完整写作上下文"""
    sm, pm, cm, wm, cb = _init_managers(project_name)
    return cb.build_volume_context(volume_id)


def list_volumes(project_name: str, part_id: str = "") -> list[dict]:
    """列出所有卷"""
    proj = _get_project_path(project_name)
    sm = StoryManager(proj)
    sm.load_story()
    volumes = sm.list_volumes(part_id)
    story_stats = sm.get_story_status()
    result = []
    for v in volumes:
        # 获取卷统计
        ch_count = len(v.chapters) if v.chapters else 0
        done_count = sum(1 for c in v.chapters if c.status == "done") if v.chapters else 0
        result.append({
            "id": v.id,
            "number": v.number,
            "title": v.title,
            "theme": v.theme,
            "summary": v.summary[:120] if v.summary else "",
            "status": v.status,
            "chapter_count": ch_count,
            "done_chapters": done_count,
            "part_id": v.part_id,
        })
    return result


def character_relationship_map(project_name: str) -> list[dict]:
    """获取所有角色关系图谱"""
    proj = _get_project_path(project_name)
    cm = CharacterManager(proj)
    cm.load()
    result = []
    for char in cm.list_characters():
        for other_id, rel in char.relationships.items():
            other = cm.get_character(other_id)
            result.append({
                "from": char.name,
                "to": other.name if other else other_id,
                "type": rel.rel_type.value,
                "description": rel.description,
                "dynamics": rel.dynamics,
            })
    return result


def get_plot_tree(project_name: str) -> list[dict]:
    """获取剧情层级树（主线→卷主线→支线→角色弧光）"""
    proj = _get_project_path(project_name)
    pm = PlotManager(proj)
    pm.load()
    return pm.get_plot_tree()


def add_foreshadowing(project_name: str, description: str,
                      created_at_chapter: int = 0, target_chapter: int = 0,
                      urgency: str = "medium",
                      related_plot_lines: list[str] | None = None,
                      related_characters: list[str] | None = None,
                      notes: str = "") -> dict:
    """添加新伏笔"""
    proj = _get_project_path(project_name)
    pm = PlotManager(proj)
    pm.load()
    fw = pm.add_foreshadowing(
        description=description,
        created_at_chapter=created_at_chapter,
        target_chapter=target_chapter,
        urgency=urgency,
        related_plot_lines=related_plot_lines or [],
        related_characters=related_characters or [],
        notes=notes,
    )
    return fw.model_dump(mode="json")


def resolve_foreshadowing(project_name: str, fw_id: str,
                          chapter_number: int, notes: str = "") -> dict:
    """回收伏笔"""
    proj = _get_project_path(project_name)
    pm = PlotManager(proj)
    pm.load()
    fw = pm.resolve_foreshadowing(fw_id, chapter_number, notes)
    return fw.model_dump(mode="json") if fw else {"error": f"Foreshadowing '{fw_id}' not found"}


def check_foreshadowing_health(project_name: str,
                               current_chapter: int = 0) -> dict:
    """伏笔健康检查"""
    proj = _get_project_path(project_name)
    pm = PlotManager(proj)
    pm.load()
    return pm.check_foreshadowing_health(current_chapter)


def create_character_snapshot(project_name: str, char_id: str,
                               chapter_number: int, chapter_title: str = "",
                               arc_progress: str = "", personality_changes: str = "",
                               new_abilities: list[str] | None = None,
                               internal_state: str = "", summary: str = "") -> dict:
    """创建角色状态快照"""
    proj = _get_project_path(project_name)
    cm = CharacterManager(proj)
    cm.load()
    snap = cm.create_snapshot(
        char_id=char_id,
        chapter_number=chapter_number,
        chapter_title=chapter_title,
        arc_progress=arc_progress,
        personality_changes=personality_changes,
        new_abilities=new_abilities or [],
        internal_state=internal_state,
        summary=summary,
    )
    return snap.model_dump(mode="json")


def get_character_evolution(project_name: str, char_id: str) -> dict:
    """获取角色演变历程"""
    proj = _get_project_path(project_name)
    cm = CharacterManager(proj)
    cm.load()
    return cm.get_character_evolution(char_id)


def search_story_index(project_name: str, query: str, limit: int = 20) -> list[dict]:
    """FTS5 全文搜索"""
    proj = _get_project_path(project_name)
    from wal.core.index import IndexManager
    im = IndexManager(proj)
    return im.search(query, limit)


def generate_chapter_summary(project_name: str, chapter_number: int) -> dict:
    """生成章节结构化摘要"""
    proj = _get_project_path(project_name)
    from wal.core.index import IndexManager
    im = IndexManager(proj)
    return im.generate_chapter_summary(chapter_number)


def quick_review(project_name: str, start_chapter: int, end_chapter: int,
                 topic: str = "") -> dict:
    """快速回顾章节范围"""
    proj = _get_project_path(project_name)
    from wal.core.index import IndexManager
    im = IndexManager(proj)
    return im.quick_review(start_chapter, end_chapter, topic)


def export_chapter_content(project_name: str, chapter_number: int = 0,
                            start_chapter: int = 0, end_chapter: int = 0,
                            volume_number: int = 0, full_novel: bool = False,
                            fmt: str = "markdown") -> dict:
    """导出章节/卷/全书"""
    proj = _get_project_path(project_name)
    sm = StoryManager(proj)
    sm.load_story()

    if full_novel:
        content = sm.export_full_novel(fmt)
        return {
            "type": "full_novel",
            "format": fmt,
            "content_preview": content[:500],
            "total_chars": len(content),
            "full_content": content,
        }
    elif volume_number > 0:
        content = sm.export_volume(volume_number, fmt)
        return {
            "type": "volume",
            "volume_number": volume_number,
            "format": fmt,
            "content_preview": content[:500],
            "total_chars": len(content),
            "full_content": content,
        }
    elif start_chapter > 0 and end_chapter > 0:
        results = sm.batch_export(start_chapter, end_chapter, fmt)
        return {
            "type": "batch",
            "range": f"第{start_chapter}章-第{end_chapter}章",
            "format": fmt,
            "chapter_count": len(results),
            "content_preview": "\n\n---\n\n".join(
                v[:200] for v in list(results.values())[:3]
            ),
            "full_content": "\n\n---\n\n".join(results.values()),
        }
    elif chapter_number > 0:
        exporters = {
            "markdown": sm.export_chapter_markdown,
            "html": sm.export_chapter_html,
            "plain": sm.export_chapter_plain,
        }
        exporter = exporters.get(fmt, sm.export_chapter_markdown)
        content = exporter(chapter_number)
        return {
            "type": "chapter",
            "chapter_number": chapter_number,
            "format": fmt,
            "content_preview": content[:500],
            "total_chars": len(content),
            "full_content": content,
        }
    else:
        return {"error": "请指定 chapter_number、start_chapter/end_chapter、volume_number 或 full_novel=true"}


def export_novel_files(project_name: str, output_dir: str = "",
                        mode: str = "volume", fmt: str = "plain",
                        structure: str = "full") -> dict:
    """导出正文为文档文件，按卷分文件夹组织

    将已写的场景正文导出为可读的文档文件，组织方式：

    - mode="volume"（推荐）：每卷一个子文件夹，卷内每章一个文件
      例：output/《小说名》/第1卷_初入江湖/第01章_楔子.txt
    - mode="chapter"：所有章节放在同一文件夹下（适合章节少的作品）
    - mode="single"：全书合并为单个文件（总集，适合出书/打印/投稿）
    - mode="auto"：自动判断（≤30章用chapter，>30章用volume）

    支持格式：plain(.txt) / markdown(.md) / html(.html) / docx(.docx)
    docx 格式自带中文排版，不含章节摘要（纯读者版）。
    structure="flat" 可跳过卷标题直接输出章节。

    Args:
        project_name: 项目名称
        output_dir: 输出根目录（默认为 projects/<项目名>/export/）
        mode: 组织方式 — volume / chapter / single / auto
        fmt: 导出格式 — plain / markdown / html / docx
        structure: 内部结构（仅 mode="single" 时生效）— full / flat

    Returns:
        导出结果，含 output_dir、chapters_exported、total_words、目录结构等
    """
    proj = _get_project_path(project_name)
    if not output_dir:
        output_dir = str(Path(proj) / "export")
    sm = StoryManager(proj)
    sm.load_story()
    return sm.export_novel_files(output_dir, mode=mode, fmt=fmt, structure=structure)


# ============================================================
# 章节管理工具（增删改）
# ============================================================

def delete_chapter(project_name: str, chapter_number: int) -> dict:
    """删除指定章节及其所有场景

    会同时清理 FTS 全文索引中的场景内容。
    删除后章节序号不变（其他章节不受影响，旧序号保留空洞）。

    Args:
        project_name: 项目名称
        chapter_number: 要删除的章节号

    Returns:
        {"deleted": True, "chapter_number": N, "chapter_id": "ch_XXXX"}
        或 {"error": "..."}
    """
    proj = _get_project_path(project_name)
    sm = StoryManager(proj)
    sm.load_story()
    return sm.delete_chapter(chapter_number)


def set_chapter_status(project_name: str, chapter_number: int,
                        status: str) -> dict:
    """更新章节状态

    Args:
        project_name: 项目名称
        chapter_number: 章节号
        status: 状态 — draft（草稿）/ writing（写作中）/ done（完成）

    Returns:
        更新后的章节信息
    """
    proj = _get_project_path(project_name)
    sm = StoryManager(proj)
    sm.load_story()
    ch = sm.set_chapter_status(chapter_number, status)
    if not ch:
        return {"error": f"第{chapter_number}章不存在"}
    return {
        "chapter_number": ch.number,
        "title": ch.title,
        "status": ch.status,
        "word_count": ch.actual_word_count,
    }


def update_chapter_info(project_name: str, chapter_number: int,
                         title: str = "", summary: str = "",
                         notes: str = "", word_count_target: int = 0) -> dict:
    """更新章节元信息（标题、摘要、备注、目标字数）

    只更新传入的非空字段。
    """
    proj = _get_project_path(project_name)
    sm = StoryManager(proj)
    sm.load_story()
    kwargs = {}
    if title:
        kwargs["title"] = title
    if summary:
        kwargs["summary"] = summary
    if notes:
        kwargs["notes"] = notes
    if word_count_target > 0:
        kwargs["word_count_target"] = word_count_target
    if not kwargs:
        return {"error": "没有需要更新的字段"}
    ch = sm.update_chapter(chapter_number, **kwargs)
    if not ch:
        return {"error": f"第{chapter_number}章不存在"}
    return {
        "chapter_number": ch.number,
        "title": ch.title,
        "summary": ch.summary,
        "status": ch.status,
        "word_count": ch.actual_word_count,
    }


def add_volume_tool(project_name: str, title: str, part_id: str = "",
                     summary: str = "", theme: str = "") -> dict:
    """添加新卷

    Args:
        project_name: 项目名称
        title: 卷标题
        part_id: 所属部ID（可选）
        summary: 卷摘要
        theme: 卷主题

    Returns:
        新卷信息
    """
    proj = _get_project_path(project_name)
    sm = StoryManager(proj)
    sm.load_story()
    vol = sm.add_volume(title=title, part_id=part_id, summary=summary,
                        theme=theme)
    return {
        "volume_id": vol.id,
        "number": vol.number,
        "title": vol.title,
        "theme": vol.theme,
        "part_id": vol.part_id,
    }


def delete_volume_tool(project_name: str, volume_id: str) -> dict:
    """删除指定卷及其所有章节和场景

    会同时清理卷下所有章节、场景内容和 FTS 索引。
    用于清理空卷或误创建的卷。

    Args:
        project_name: 项目名称
        volume_id: 卷ID（如 vol_001）

    Returns:
        {"deleted": True, "volume_id": "vol_001"} 或 {"error": "..."}
    """
    proj = _get_project_path(project_name)
    sm = StoryManager(proj)
    sm.load_story()
    return sm.delete_volume(volume_id)


def delete_plot_line_tool(project_name: str, plot_id: str) -> dict:
    """删除指定剧情线及其下所有情节点

    用于清理重复、错误或废弃的剧情线。

    Args:
        project_name: 项目名称
        plot_id: 剧情线ID（如 plot_001）

    Returns:
        {"deleted": True, "plot_id": "plot_001"} 或 {"error": "..."}
    """
    proj = _get_project_path(project_name)
    pm = PlotManager(proj)
    pm.load()
    # 检查是否存在
    existing = pm.get_plot_line(plot_id)
    if not existing:
        return {"error": f"剧情线 {plot_id} 不存在"}
    name = getattr(existing, 'name', '')
    ok = pm.delete_plot_line(plot_id)
    if ok:
        return {"deleted": True, "plot_id": plot_id, "name": name}
    return {"error": f"删除剧情线 {plot_id} 失败"}


def delete_character_tool(project_name: str, char_id: str) -> dict:
    """删除指定角色及其所有关系

    会同时清理角色关联的所有人际关系记录。

    Args:
        project_name: 项目名称
        char_id: 角色ID（如 char_001）或角色名

    Returns:
        {"deleted": True, "char_id": "char_001"} 或 {"error": "..."}
    """
    proj = _get_project_path(project_name)
    cm = CharacterManager(proj)
    cm.load()
    # 支持按名字查找
    char = cm.get_character(char_id)
    if not char:
        # 尝试按名字搜索
        all_chars = cm.list_characters()
        for c in all_chars:
            if getattr(c, 'name', '') == char_id:
                char = c
                char_id = getattr(c, 'id', char_id)
                break
    if not char:
        return {"error": f"角色 {char_id} 不存在"}
    name = getattr(char, 'name', char_id)
    ok = cm.delete_character(char_id)
    if ok:
        return {"deleted": True, "char_id": char_id, "name": name}
    return {"error": f"删除角色 {char_id} 失败"}


def update_volume_tool(project_name: str, volume_id: str,
                       title: str = "", summary: str = "",
                       theme: str = "", status: str = "",
                       notes: str = "") -> dict:
    """更新卷信息（标题、摘要、主题、状态等）"""
    proj = _get_project_path(project_name)
    sm = StoryManager(proj)
    sm.load_story()
    updates = {}
    if title:
        updates["title"] = title
    if summary:
        updates["summary"] = summary
    if theme:
        updates["theme"] = theme
    if status:
        updates["status"] = status
    if notes:
        updates["notes"] = notes
    if not updates:
        return {"error": "没有提供要更新的字段"}
    vol = sm.update_volume(volume_id, **updates)
    return {"updated": True, "volume_id": volume_id, "changes": list(updates.keys())}


def update_plot_line_tool(project_name: str, plot_id: str,
                           name: str = "", description: str = "",
                           theme: str = "", status: str = "",
                           target_chapter: int = 0) -> dict:
    """更新剧情线属性（名称、描述、主题、状态、目标章节等）"""
    proj = _get_project_path(project_name)
    pm = PlotManager(proj)
    pm.load()
    updates = {}
    if name:
        updates["name"] = name
    if description:
        updates["description"] = description
    if theme:
        updates["theme"] = theme
    if status:
        updates["status"] = status
    if target_chapter:
        updates["target_chapter"] = target_chapter
    if not updates:
        return {"error": "没有提供要更新的字段"}
    result = pm.update_plot_line(plot_id, **updates)
    result["updated"] = True
    return result


def update_foreshadowing_tool(project_name: str, fw_id: str,
                               description: str = "",
                               urgency: str = "",
                               target_chapter: int = 0,
                               resolution_notes: str = "") -> dict:
    """更新伏笔属性（描述、紧急度、计划回收章节等）"""
    proj = _get_project_path(project_name)
    pm = PlotManager(proj)
    pm.load()
    updates = {}
    if description:
        updates["description"] = description
    if urgency:
        updates["urgency"] = urgency
    if target_chapter:
        updates["target_chapter"] = target_chapter
    if resolution_notes:
        updates["resolution_notes"] = resolution_notes
    if not updates:
        return {"error": "没有提供要更新的字段"}
    return pm.update_foreshadowing(fw_id, **updates)


def get_chapter_artifacts(project_name: str, chapter_number: int) -> dict:
    """查看指定章节关联的所有状态数据（重写前检查）

    列出该章的全部：角色快照、剧情情节点、伏笔引用、场景数。
    用于重写章节前了解哪些状态会被级联清理影响。

    Args:
        project_name: 项目名称
        chapter_number: 章节号

    Returns:
        {"chapter_number": N, "snapshots": [...], "plot_points": [...],
         "foreshadowings": [...], "scene_count": N}
    """
    proj = _get_project_path(project_name)
    from wal.storage.character import CharacterRepository
    from wal.storage.plot import PlotRepository
    from wal.storage.story import StoryRepository
    from wal.storage.connection import Database

    db_path = Path(proj) / "wal.db"
    db = Database(str(db_path))

    # 角色快照
    char_repo = CharacterRepository(db)
    # snapshots are stored by chapter_number, we need to query
    all_snaps = char_repo._fetch_all(
        "SELECT id, character_id, chapter_title, arc_progress, personality_changes "
        "FROM character_snapshots WHERE chapter_number = ?",
        (chapter_number,),
    )
    snapshots = [dict(s) for s in (all_snaps or [])]

    # 情节点
    plot_repo = PlotRepository(db)
    plot_points = plot_repo.list_points_by_chapter(chapter_number)

    # 伏笔引用
    fores = plot_repo._fetch_all(
        "SELECT id, description, status, created_at_chapter, resolved_at_chapter "
        "FROM foreshadowings WHERE created_at_chapter = ? OR resolved_at_chapter = ?",
        (chapter_number, chapter_number),
    )
    foreshadowings = [dict(f) for f in (fores or [])]

    # 场景数
    story_repo = StoryRepository(db)
    ch_id = f"ch_{chapter_number:04d}"
    scenes = story_repo.list_scenes_by_chapter(ch_id)

    return {
        "chapter_number": chapter_number,
        "snapshots": snapshots,
        "plot_points": plot_points,
        "foreshadowings": foreshadowings,
        "scene_count": len(scenes),
    }


def delete_scene_tool(project_name: str, chapter_number: int,
                       scene_index: int) -> dict:
    """删除指定场景"""
    proj = _get_project_path(project_name)
    sm = StoryManager(proj)
    sm.load_story()
    ch_id = f"ch_{chapter_number:04d}"
    scenes = sm.repo.list_scenes_by_chapter(ch_id)
    if scene_index < 0 or scene_index >= len(scenes):
        return {"error": f"场景索引 {scene_index} 超出范围（0-{len(scenes)-1}）"}
    scene_id = scenes[scene_index]["id"]
    sm.repo.remove_scene_from_fts(scene_id)
    deleted = sm.repo.delete_scene(scene_id)
    if deleted:
        sm._recalc_chapter_word_count(ch_id)
        return {"deleted": True, "chapter_number": chapter_number,
                "scene_index": scene_index, "scene_id": scene_id}
    return {"error": "删除失败"}


# ============================================================
# 通用文件读取工具
# ============================================================

def read_file(path: str, encoding: str = "utf-8",
              start_line: int = 0, line_limit: int = 0) -> str:
    """读取指定路径的文件内容（仅限文本文件）

    Args:
        path: 文件的绝对路径或相对路径
        encoding: 文件编码，默认 utf-8
        start_line: 起始行号（从1开始），0 表示从第1行开始
        line_limit: 最多读取行数，0 表示不限制

    Returns:
        文件内容字符串，或错误信息
    """
    from pathlib import Path

    file_path = Path(path)

    # 路径规范化
    if not file_path.is_absolute():
        file_path = Path.cwd() / file_path

    try:
        file_path = file_path.resolve()
    except Exception:
        return f"[Error] 无法解析路径：{path}"

    # 检查文件是否存在
    if not file_path.exists():
        return f"[Error] 文件不存在：{file_path}"

    # 检查是否为目录
    if file_path.is_dir():
        return f"[Error] 指定路径是一个目录，而非文件：{file_path}\n目录内容：\n" + \
               "\n".join(f"  {'[DIR]' if p.is_dir() else '[FILE]'} {p.name}"
                         for p in sorted(file_path.iterdir())[:50])

    # 检查文件大小（超过 10MB 警告）
    try:
        size_mb = file_path.stat().st_size / (1024 * 1024)
        if size_mb > 10:
            return f"[Error] 文件过大（{size_mb:.1f} MB），超过 10 MB 限制。请使用 start_line/line_limit 分段读取"
    except Exception:
        pass

    # 读取文件
    try:
        with open(file_path, "r", encoding=encoding) as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        # 尝试常见编码
        for fallback_enc in ["gbk", "gb2312", "latin-1"]:
            try:
                with open(file_path, "r", encoding=fallback_enc) as f:
                    lines = f.readlines()
                encoding = fallback_enc  # 记录实际使用的编码
                break
            except (UnicodeDecodeError, LookupError):
                continue
        else:
            return f"[Error] 无法解码文件 {file_path.name}，尝试了 utf-8 / gbk / gb2312 / latin-1 均失败。文件可能是二进制格式"
    except PermissionError:
        return f"[Error] 没有权限读取文件：{file_path}"
    except Exception as e:
        return f"[Error] 读取文件失败：{e}"

    total_lines = len(lines)

    # 行范围处理
    if start_line > 0:
        start_idx = start_line - 1
    else:
        start_idx = 0

    if line_limit > 0:
        end_idx = min(start_idx + line_limit, total_lines)
    else:
        end_idx = total_lines

    # 边界检查
    if start_idx >= total_lines:
        return f"[Error] 起始行 {start_line} 超出文件总行数 {total_lines}"

    selected = lines[start_idx:end_idx]

    # 行号格式化
    result_lines = []
    for i, line in enumerate(selected, start=start_idx + 1):
        result_lines.append(f"{i:6d}|{line.rstrip()}")

    result = "\n".join(result_lines)

    # 添加摘要头
    header = f"# 文件：{file_path.name}\n"
    header += f"# 路径：{file_path}\n"
    header += f"# 编码：{encoding} | 总行数：{total_lines}\n"
    if start_line > 0 or line_limit > 0:
        actual_start = start_idx + 1
        actual_end = actual_start + len(selected) - 1
        header += f"# 读取范围：第 {actual_start}-{actual_end} 行（共 {len(selected)} 行）\n"
    else:
        header += f"# 已读取全部 {len(selected)} 行\n"
    header += f"{'─' * 60}\n"

    return header + result


# ============================================================
# 防跑偏与章节移动工具（P0/P1/P2 全清单）
# ============================================================

def get_writing_mandate(project_name: str, volume_number: int = 0,
                        current_chapter: int = 0) -> dict:
    """获取写作指令：当前卷 + 章节范围锁 + 铁律 + 骨架锚点 + 必读设定文档

    这是自主模式写正文前的**必读指令**。进入自主模式时系统提示词会自动注入
    一份，主动调用可获得完整版并确认当前卷。

    Args:
        volume_number: 指定卷号（0=自动定位当前卷）
        current_chapter: 指定当前章（用于提取本章锚点）
    """
    from wal.core.mandate import MandateBuilder
    proj = _get_project_path(project_name)
    mb = MandateBuilder(proj)
    mandate = mb.build(volume_number=volume_number, current_chapter=current_chapter)
    # 确认当前卷
    vol = mandate.get("volume") or {}
    if vol and vol.get("number"):
        mb.set_config("auto_current_volume", str(vol["number"]))
    formatted = mb.format(mandate)
    return {
        "current_volume": (vol or {}).get("number", 0),
        "range_lock": mandate.get("range_lock"),
        "iron_laws": mandate.get("iron_laws"),
        "chapter_anchor": mandate.get("chapter"),
        "mandatory_docs": [{"doc_id": d["id"], "title": d["title"]}
                           for d in mandate.get("mandatory_docs", [])],
        "formatted": formatted,
    }


def set_current_volume(project_name: str, volume_number: int) -> dict:
    """声明当前写作卷，建立范围锁。写章超出该卷范围时需显式调用本工具确认进入下一卷"""
    from wal.core.mandate import MandateBuilder
    from wal.core import StoryManager
    proj = _get_project_path(project_name)
    mb = MandateBuilder(proj)
    sm = StoryManager(proj)
    sm.load_story()
    vol_row = sm.repo.get_volume_by_number(volume_number)
    if not vol_row:
        return {"error": f"卷 {volume_number} 不存在"}
    mb.set_config("auto_current_volume", str(volume_number))
    return {
        "current_volume": volume_number,
        "volume_title": vol_row.get("title", ""),
        "range_lock": {
            "chapter_start": int(vol_row.get("chapter_start") or 0),
            "chapter_end": int(vol_row.get("chapter_end") or 0),
        },
        "message": f"当前卷已切换为第{volume_number}卷，超出范围前需显式再次调用本工具放行",
    }


def set_volume_range(project_name: str, volume_number: int,
                     start_chapter: int, end_chapter: int) -> dict:
    """声明卷的章节范围（范围锁）。例：卷三=50~72 → set_volume_range(3, 50, 72)"""
    proj = _get_project_path(project_name)
    sm = StoryManager(proj)
    sm.load_story()
    return sm.set_volume_range(volume_number, start_chapter, end_chapter)


def list_volume_ranges(project_name: str) -> list[dict]:
    """列出所有卷及其章节范围锁"""
    proj = _get_project_path(project_name)
    sm = StoryManager(proj)
    sm.load_story()
    return sm.list_volume_ranges()


def add_iron_law(project_name: str, name: str, keywords: list[str],
                 forbidden_volumes: list[int] | None = None,
                 only_in_volume: int = 0, severity: str = "warning",
                 note: str = "") -> dict:
    """新增铁律。keywords 命中且落在禁止范围即报违规。

    例：「万山之祖传承」只在卷五出现 → add_iron_law(name='万山之祖传承',
    keywords=['万山之祖', '传承', '接替'], only_in_volume=5)
    """
    from wal.core.iron_law import IronLawManager
    proj = _get_project_path(project_name)
    im = IronLawManager(proj)
    return im.add_iron_law(name, keywords, forbidden_volumes, only_in_volume, severity, note)


def list_iron_laws(project_name: str) -> list[dict]:
    """列出全部铁律"""
    from wal.core.iron_law import IronLawManager
    proj = _get_project_path(project_name)
    return IronLawManager(proj).list_iron_laws()


def delete_iron_law(project_name: str, law_id: str) -> dict:
    """删除一条铁律"""
    from wal.core.iron_law import IronLawManager
    proj = _get_project_path(project_name)
    return IronLawManager(proj).delete_iron_law(law_id)


def check_iron_law(project_name: str, chapter_number: int) -> dict:
    """扫描指定章节正文是否命中铁律违规（写后检查/写前自查）"""
    from wal.core.iron_law import IronLawManager
    proj = _get_project_path(project_name)
    im = IronLawManager(proj)
    violations = im.scan_chapter(chapter_number)
    return {
        "chapter_number": chapter_number,
        "violations": violations,
        "violation_count": len(violations),
        "clean": len(violations) == 0,
    }


def set_chapter_anchor(project_name: str, chapter_number: int,
                       anchor: str) -> dict:
    """设置章节锚点（本章应写什么）。check_chapter_alignment 的对照依据"""
    proj = _get_project_path(project_name)
    sm = StoryManager(proj)
    sm.load_story()
    return sm.set_chapter_anchor(chapter_number, anchor)


def set_auto_mandatory_docs(project_name: str, doc_ids: list[str]) -> dict:
    """配置自主模式启动必读文档（按顺序注入写作指令）"""
    from wal.core.mandate import MandateBuilder
    import json as _json
    proj = _get_project_path(project_name)
    mb = MandateBuilder(proj)
    mb.set_config("auto_mandatory_docs",
                  _json.dumps(list(doc_ids), ensure_ascii=False))
    return {"mandatory_docs": list(doc_ids), "saved": True}


def move_chapter(project_name: str, from_number: int, to_number: int) -> dict:
    """移动章节：把章节改到新章节号，级联迁移所有引用（场景/索引/快照/情节点/伏笔）"""
    proj = _get_project_path(project_name)
    sm = StoryManager(proj)
    sm.load_story()
    return sm.move_chapter(from_number, to_number)


def renumber_chapters(project_name: str, start_at: int = 1,
                      new_start: int = 1) -> dict:
    """批量重排章节号：从 start_at 起的章节顺延为 new_start 起（删除章节留空洞时用）"""
    proj = _get_project_path(project_name)
    sm = StoryManager(proj)
    sm.load_story()
    return sm.renumber_chapters(start_at, new_start)


def assign_chapter_to_volume(project_name: str, chapter_number: int,
                             volume_number: int) -> dict:
    """把指定章节挂到指定卷下"""
    proj = _get_project_path(project_name)
    sm = StoryManager(proj)
    sm.load_story()
    return sm.assign_chapter_to_volume(chapter_number, volume_number)


def assign_chapters_to_volume(project_name: str, volume_number: int,
                              start: int, end: int) -> dict:
    """批量把 start~end 章挂到指定卷（一次修完历史遗留的未挂卷章节）"""
    proj = _get_project_path(project_name)
    sm = StoryManager(proj)
    sm.load_story()
    return sm.assign_chapters_to_volume(volume_number, start, end)


def add_plot_point(project_name: str, plot_id: str, title: str,
                   chapter_assigned: int = 0, description: str = "",
                   emotional_tone: str = "", impacts_characters: list[str] | None = None,
                   estimated_words: int = 0) -> dict:
    """向剧情线添加情节点，可绑定到指定章节"""
    proj = _get_project_path(project_name)
    pm = PlotManager(proj)
    pm.load()
    pp = pm.add_plot_point(
        plot_id=plot_id, title=title, description=description,
        chapter_assigned=chapter_assigned, emotional_tone=emotional_tone,
        impacts_characters=impacts_characters or [], estimated_words=estimated_words,
    )
    return {"id": pp.id, "plot_id": plot_id, "title": pp.title,
            "chapter_assigned": pp.chapter_assigned, "status": pp.status.value}


def assign_plot_point_to_chapter(project_name: str, plot_id: str,
                                 point_id: str, chapter: int) -> dict:
    """把情节点绑定到指定章节（进度绑定）"""
    proj = _get_project_path(project_name)
    pm = PlotManager(proj)
    pm.load()
    pp = pm.assign_plot_point(plot_id, point_id, chapter)
    return {"id": pp.id, "plot_id": plot_id, "title": pp.title,
            "chapter_assigned": pp.chapter_assigned}


def bind_plot_points_to_chapter(project_name: str, plot_id: str,
                                chapter: int, point_ids: list[str]) -> dict:
    """批量把剧情线的多个情节点绑定到指定章节"""
    proj = _get_project_path(project_name)
    pm = PlotManager(proj)
    pm.load()
    return pm.bind_plot_points_to_chapter(plot_id, chapter, point_ids)


def auto_advance_plot(project_name: str, chapter_number: int) -> dict:
    """章节完成后自动推进：把绑定到该章的情节点标记为完成，剧情线进度自动上涨"""
    proj = _get_project_path(project_name)
    pm = PlotManager(proj)
    pm.load()
    return pm.auto_advance_plot(chapter_number)


def check_chapter_alignment(project_name: str, chapter_number: int) -> dict:
    """写后对照：本章实际内容 vs 锚点（规划）。锚点关键内容缺失即报告偏离

    关键词级匹配（不再整句精确匹配）：在锚点里做贪心最长子串匹配，
    覆盖率 = 锚点中被正文覆盖的汉字数 / 锚点总汉字数。
    覆盖率 ≥ 40% 且 ≥2 个关键词命中即判对齐——文学正文几乎不可能整句
    复现锚点短语，逐字覆盖才是可靠信号；锚点与正文的已知差异（刻意省略
    的人名、改名地点、近义改写）只降低少量覆盖率，不会导致误报。未覆盖
    的锚点内容列入 missing_events 供人工核对。
    """
    proj = _get_project_path(project_name)
    sm = StoryManager(proj)
    sm.load_story()
    ch = sm.get_chapter(chapter_number)
    if not ch:
        return {"error": f"第{chapter_number}章不存在"}
    anchor = getattr(ch, "anchor", "") or ch.summary or ""
    content = "\n".join(sc.content for sc in ch.scenes if sc.content.strip())
    if not anchor:
        return {
            "chapter_number": chapter_number,
            "title": ch.title,
            "aligned": None,
            "message": "本章无锚点，无法对照。可用 set_chapter_anchor 设置，或从骨架文档导入后重查",
        }
    coverage, matched_chars, total_chars, found, missing = _match_anchor_to_content(
        anchor, content)
    # 关键词级判定：覆盖率达标（≥40%）且至少 2 个独立关键词命中 → 对齐。
    # 刻意省略的人名/改名地点/近义改写只降少量覆盖率，不会触发误报；
    # 完全没写的锚点内容会列在 missing_events 供人工核对。
    aligned = coverage >= _ALIGN_THRESHOLD and len(found) >= _ALIGN_MIN_MATCHES
    return {
        "chapter_number": chapter_number,
        "title": ch.title,
        "aligned": aligned,
        "coverage": round(coverage, 2),
        "matched_chars": matched_chars,
        "anchor_chars": total_chars,
        "anchor": anchor[:200],
        "found_events": found,
        "missing_events": missing,
        "content_words": len(content),
        "message": (
            f"对齐：正文覆盖锚点关键词 {len(found)} 处/{matched_chars} 字"
            f"（覆盖率 {coverage:.0%} ≥ 40%）"
            if aligned else
            f"偏离：正文仅覆盖锚点 {matched_chars}/{total_chars} 字"
            f"（覆盖率 {coverage:.0%} < 40%），以下锚点内容未见："
            f"{'、'.join(missing[:6]) or '无'}"
        ),
    }


_ALIGN_THRESHOLD = 0.4
_ALIGN_MIN_MATCHES = 2


def _is_cjk(ch: str) -> bool:
    """是否汉字（CJK 基本区 + 扩展A + 兼容表意文字）"""
    return ('一' <= ch <= '鿿') or ('㐀' <= ch <= '䶿') or ('豈' <= ch <= '﫿')


def _match_anchor_to_content(anchor: str, content: str,
                             max_match: int = 12, min_match: int = 2) -> tuple:
    """贪心最长子串匹配：量锚点在正文里的覆盖（无需分词器）

    从锚点每个汉字位置出发找「正文里存在的最长子串」，命中则跳过；
    连续命中段合并为 found 片段；未覆盖的 ≥2 字汉字段归为 missing。

    Returns:
        (coverage, matched_chars, total_chars, found, missing)
        - coverage: 命中汉字数 / 锚点汉字数（0~1）
        - found: 命中的锚点片段（合并连续段，去重）
        - missing: 未覆盖的锚点汉字段（≥2 字连续）
    """
    n = len(anchor)
    i = 0
    matched_chars = 0
    spans: list[tuple[int, int]] = []
    while i < n:
        ch = anchor[i]
        if not _is_cjk(ch):
            i += 1
            continue
        best = 0
        for L in range(min(max_match, n - i), 0, -1):
            if anchor[i:i + L] in content:
                best = L
                break
        if best >= min_match:
            matched_chars += best
            spans.append((i, i + best))
            i += best
        else:
            i += 1
    # 合并连续命中的 span
    merged: list[tuple[int, int]] = []
    for s, e in spans:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    found: list[str] = []
    for s, e in merged:
        txt = anchor[s:e].strip("*").strip()
        if txt and txt not in found:
            found.append(txt)
    # 未覆盖的锚点汉字段
    covered = [False] * n
    for s, e in spans:
        for k in range(s, e):
            covered[k] = True
    missing: list[str] = []
    cur = ""
    for k in range(n):
        if not _is_cjk(anchor[k]):
            if len(cur) >= 2:
                missing.append(cur)
            cur = ""
        elif not covered[k]:
            cur += anchor[k]
        else:
            if len(cur) >= 2:
                missing.append(cur)
            cur = ""
    if len(cur) >= 2:
        missing.append(cur)
    # 分母 = 锚点全部汉字数（与匹配位置无关，避免命中段内部字被漏算）
    total_chars = sum(1 for c in anchor if _is_cjk(c))
    coverage = matched_chars / total_chars if total_chars else 0.0
    return coverage, matched_chars, total_chars, found[:20], missing[:20]


def global_replace(project_name: str, old: str, new: str,
                   in_titles: bool = False, in_summaries: bool = False) -> dict:
    """全书查找替换：改设定/人名时不用一章章翻。默认只替换场景正文"""
    proj = _get_project_path(project_name)
    sm = StoryManager(proj)
    sm.load_story()
    return sm.global_replace(old, new, in_titles=in_titles, in_summaries=in_summaries)


def merge_scenes(project_name: str, chapter: int,
                 scene_a: int, scene_b: int) -> dict:
    """合并章内两个场景：内容并入 scene_a，删除 scene_b"""
    proj = _get_project_path(project_name)
    sm = StoryManager(proj)
    sm.load_story()
    return sm.merge_scenes(chapter, scene_a, scene_b)


def split_scene(project_name: str, chapter: int,
                scene_index: int, split_at: int) -> dict:
    """按字符位置拆分场景为两个场景"""
    proj = _get_project_path(project_name)
    sm = StoryManager(proj)
    sm.load_story()
    return sm.split_scene(chapter, scene_index, split_at)


def story_timeline(project_name: str) -> dict:
    """故事内时间轴：各章场景的 time_point + timeline_events 表"""
    proj = _get_project_path(project_name)
    sm = StoryManager(proj)
    sm.load_story()
    return sm.story_timeline()

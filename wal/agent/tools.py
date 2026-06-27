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

from ..core import StoryManager, PlotManager, CharacterManager, WorldManager
from ..engine.context_builder import ContextBuilder
from ..engine.prompt_builder import PromptBuilder


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
    from ..core.index_manager import IndexManager
    im = IndexManager(proj)
    return im.search(query, limit)


def generate_chapter_summary(project_name: str, chapter_number: int) -> dict:
    """生成章节结构化摘要"""
    proj = _get_project_path(project_name)
    from ..core.index_manager import IndexManager
    im = IndexManager(proj)
    return im.generate_chapter_summary(chapter_number)


def quick_review(project_name: str, start_chapter: int, end_chapter: int,
                 topic: str = "") -> dict:
    """快速回顾章节范围"""
    proj = _get_project_path(project_name)
    from ..core.index_manager import IndexManager
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


def export_yaml_backup(project_name: str) -> dict:
    """导出 SQLite 数据到 YAML 文件备份

    将 wal.db 中的所有故事数据导出为 YAML 文件：
    - story.yaml (故事 + 章节 + 场景)
    - characters.yaml (角色 + 关系)
    - plot_lines.yaml (剧情线 + 情节点 + 交汇)

    原 YAML 文件会被覆盖。导出后可通过 CLI init 时指定 --yaml 读取。
    """
    proj = _get_project_path(project_name)
    try:
        from ..storage.database import Database
        db_path = str(Path(proj) / "wal.db")
        db = Database(db_path)
        result = db.export_to_yaml(proj)
        return {
            "status": "ok" if not result.get("errors") else "partial",
            "exported": result.get("exported", []),
            "errors": result.get("errors", []),
            "message": f"已导出 {len(result.get('exported', []))} 个 YAML 文件到 {proj}",
        }
    except FileNotFoundError:
        return {"error": f"数据库文件不存在：{proj}/wal.db"}
    except Exception as e:
        return {"error": f"YAML 导出失败：{e}"}


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
    name = existing.get("name", "") or getattr(existing, 'name', '')
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
    from ..storage.char_repo import CharacterRepository
    from ..storage.plot_repo import PlotRepository
    from ..storage.story_repo import StoryRepository
    from ..storage.database import Database

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

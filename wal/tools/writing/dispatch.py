"""execute_tool() — writing tool dispatch"""

import json
from typing import Any

# ---- Schema definitions ----
from .schemas import TOOL_DEFINITIONS

# ---- Implementation functions ----
from .implementations import *
from wal.tools.shared.memory import save_agent_memory, get_agent_memory, delete_agent_memory


def execute_tool(tool_name: str, arguments: dict, project_name: str) -> str:
    """执行工具调用，返回结果字符串

    根据 tool_name 从 wal.agent.tools 中找到对应函数并调用。
    """
    import os
    from .implementations import (
        get_story_status,
        get_chapter_context_text,
        list_dangling_plots,
        list_characters,
        get_character,
        list_plot_lines,
        plot_health_check,
        write_scene_content,
        update_plot_point,
        suggest_next_scene,
        export_outline,
        character_relationship_map,
        get_volume_context,
        list_volumes,
        get_plot_tree,
        add_foreshadowing,
        resolve_foreshadowing,
        check_foreshadowing_health,
        create_character_snapshot,
        get_character_evolution,
        search_story_index,
        generate_chapter_summary,
        quick_review,
        export_chapter_content,
        export_novel_files,
        delete_chapter,
        set_chapter_status,
        update_chapter_info,
        add_volume_tool,
        delete_volume_tool,
        update_volume_tool,
        delete_plot_line_tool,
        update_plot_line_tool,
        delete_character_tool,
        update_foreshadowing_tool,
        get_chapter_artifacts,
        delete_scene_tool,
    )
    from wal.tools.shared.memory import save_agent_memory, get_agent_memory
    from wal.core import StoryManager, CharacterManager

    proj_path = str(Path(os.environ.get("WAL_PROJECTS", "projects")) / project_name)

    # 工具→函数映射
    tool_map = {
        "get_story_status": lambda: get_story_status(project_name),
        "get_chapter_context": lambda: get_chapter_context_text(project_name, arguments["chapter"]),
        "list_dangling_plots": lambda: list_dangling_plots(project_name),
        "list_characters": lambda: list_characters(project_name, arguments.get("role")),
        "get_character": lambda: get_character(project_name, arguments["char_id"]),
        "list_plot_lines": lambda: list_plot_lines(project_name),
        "plot_health_check": lambda: plot_health_check(project_name),
        "write_scene_content": lambda: write_scene_content(
            project_name,
            arguments["chapter"],
            arguments["scene_index"],
            arguments["content"],
        ),
        "update_plot_point": lambda: update_plot_point(
            project_name,
            arguments["plot_id"],
            arguments["point_id"],
            arguments["status"],
        ),
        "suggest_next_scene": lambda: suggest_next_scene(project_name, arguments["chapter"]),
        "export_outline": lambda: export_outline(project_name),
        "character_relationship_map": lambda: character_relationship_map(project_name),
        "get_volume_context": lambda: get_volume_context(project_name, arguments["volume_id"]),
        "list_volumes": lambda: list_volumes(project_name, arguments.get("part_id", "")),
        "get_plot_tree": lambda: get_plot_tree(project_name),
        "add_foreshadowing": lambda: add_foreshadowing(
            project_name,
            arguments["description"],
            arguments.get("created_at_chapter", 0),
            arguments.get("target_chapter", 0),
            arguments.get("urgency", "medium"),
            arguments.get("related_plot_lines", []),
            arguments.get("related_characters", []),
            arguments.get("notes", ""),
        ),
        "resolve_foreshadowing": lambda: resolve_foreshadowing(
            project_name,
            arguments["fw_id"],
            arguments["chapter_number"],
            arguments.get("notes", ""),
        ),
        "update_foreshadowing": lambda: update_foreshadowing_tool(
            project_name,
            arguments["fw_id"],
            arguments.get("description", ""),
            arguments.get("urgency", ""),
            arguments.get("target_chapter", 0),
            arguments.get("resolution_notes", ""),
        ),
        "check_foreshadowing_health": lambda: check_foreshadowing_health(
            project_name,
            arguments.get("current_chapter", 0),
        ),
        "create_character_snapshot": lambda: create_character_snapshot(
            project_name,
            arguments["char_id"],
            arguments["chapter_number"],
            arguments.get("chapter_title", ""),
            arguments.get("arc_progress", ""),
            arguments.get("personality_changes", ""),
            arguments.get("new_abilities", []),
            arguments.get("internal_state", ""),
            arguments.get("summary", ""),
        ),
        "get_character_evolution": lambda: get_character_evolution(
            project_name,
            arguments["char_id"],
        ),
        "search_story_index": lambda: search_story_index(
            project_name,
            arguments["query"],
            arguments.get("limit", 20),
        ),
        "generate_chapter_summary": lambda: generate_chapter_summary(
            project_name,
            arguments["chapter_number"],
        ),
        "quick_review": lambda: quick_review(
            project_name,
            arguments["start_chapter"],
            arguments["end_chapter"],
            arguments.get("topic", ""),
        ),
        "export_chapter": lambda: export_chapter_content(
            project_name,
            arguments.get("chapter_number", 0),
            arguments.get("start_chapter", 0),
            arguments.get("end_chapter", 0),
            arguments.get("volume_number", 0),
            arguments.get("full_novel", False),
            arguments.get("format", "markdown"),
        ),
        # Extra tools defined inline
        "add_chapter": lambda: _add_chapter(project_name, arguments),
        "add_character": lambda: _add_character(project_name, arguments),
        "update_character": lambda: _update_character(project_name, arguments),
        "get_chapter_artifacts": lambda: get_chapter_artifacts(
            project_name,
            arguments["chapter_number"],
        ),
        "export_novel_files": lambda: export_novel_files(
            project_name,
            arguments.get("output_dir", ""),
            arguments.get("mode", "volume"),
            arguments.get("format", "plain"),
            arguments.get("structure", "full"),
        ),
        "delete_chapter": lambda: delete_chapter(
            project_name,
            arguments["chapter_number"],
        ),
        "set_chapter_status": lambda: set_chapter_status(
            project_name,
            arguments["chapter_number"],
            arguments["status"],
        ),
        "update_chapter_info": lambda: update_chapter_info(
            project_name,
            arguments["chapter_number"],
            arguments.get("title", ""),
            arguments.get("summary", ""),
            arguments.get("notes", ""),
            arguments.get("word_count_target", 0),
        ),
        "add_volume": lambda: add_volume_tool(
            project_name,
            arguments["title"],
            arguments.get("part_id", ""),
            arguments.get("summary", ""),
            arguments.get("theme", ""),
        ),
        "delete_volume": lambda: delete_volume_tool(
            project_name,
            arguments["volume_id"],
        ),
        "update_volume": lambda: update_volume_tool(
            project_name,
            arguments["volume_id"],
            arguments.get("title", ""),
            arguments.get("summary", ""),
            arguments.get("theme", ""),
            arguments.get("status", ""),
            arguments.get("notes", ""),
        ),
        "delete_plot_line": lambda: delete_plot_line_tool(
            project_name,
            arguments["plot_id"],
        ),
        "update_plot_line": lambda: update_plot_line_tool(
            project_name,
            arguments["plot_id"],
            arguments.get("name", ""),
            arguments.get("description", ""),
            arguments.get("theme", ""),
            arguments.get("status", ""),
            arguments.get("target_chapter", 0),
        ),
        "delete_character": lambda: delete_character_tool(
            project_name,
            arguments["char_id"],
        ),
        "delete_scene": lambda: delete_scene_tool(
            project_name,
            arguments["chapter_number"],
            arguments["scene_index"],
        ),
        # 跨模式工具（预分派在 core.py 处理，不会到这里，但保留映射以防回退）
        "switch_mode": lambda: f"[Internal] switch_mode is handled by AgentLoop pre-dispatch",
        # 持久记忆工具
        "save_agent_memory": lambda: save_agent_memory(
            project_name,
            arguments["key"],
            arguments["value"],
        ),
        "get_agent_memory": lambda: get_agent_memory(
            project_name,
            arguments.get("key", ""),
        ),
        # 新增工具：剧情线、故事信息、角色关系、自定义文档
        "add_plot_line": lambda: _add_plot_line(project_name, arguments),
        "update_story_info": lambda: _update_story_info(project_name, arguments),
        "set_writing_style": lambda: _set_writing_style(project_name, arguments),
        "add_character_relationship": lambda: _add_character_relationship(project_name, arguments),
        "add_custom_document": lambda: _add_custom_document(project_name, arguments),
        "get_custom_document": lambda: _get_custom_document(project_name, arguments),
        "list_custom_documents": lambda: _list_custom_documents(project_name, arguments),
        "update_custom_document": lambda: _update_custom_document(project_name, arguments),
        "delete_custom_document": lambda: _delete_custom_document(project_name, arguments),
    }

    func = tool_map.get(tool_name)
    if not func:
        return f"[Error] Unknown tool: {tool_name}"

    try:
        result = func()
        # 格式化输出
        if isinstance(result, (dict, list)):
            return json.dumps(result, ensure_ascii=False, indent=2)
        return str(result)
    except Exception as e:
        return f"[Tool Error] {tool_name}: {e}"


def _add_chapter(project_name: str, args: dict) -> dict:
    """内部：添加章节"""
    import os
    from pathlib import Path
    from wal.core import StoryManager

    proj_path = str(Path(os.environ.get("WAL_PROJECTS", "projects")) / project_name)
    sm = StoryManager(proj_path)
    sm.load_story()
    ch = sm.add_chapter(
        title=args["title"],
        summary=args.get("summary", ""),
        word_count_target=args.get("word_count_target", 3000),
        volume_id=args.get("volume_id", ""),
        volume_number=args.get("volume_number", 0),
        chapter_number=args.get("chapter_number", 0),
    )
    return {"number": ch.number, "title": ch.title, "status": ch.status}


def _add_character(project_name: str, args: dict) -> dict:
    """内部：添加角色"""
    import os
    from pathlib import Path
    from wal.core import CharacterManager

    proj_path = str(Path(os.environ.get("WAL_PROJECTS", "projects")) / project_name)
    cm = CharacterManager(proj_path)
    cm.load()

    traits = args.get("personality_traits", "")
    traits_list = [t.strip() for t in traits.split(",") if t.strip()] if traits else []

    c = cm.create_character(
        name=args["name"],
        role=args.get("role", "supporting"),
        background_story=args.get("background_story", ""),
        motivation=args.get("motivation", ""),
        personality_traits=traits_list,
    )
    return {"id": c.id, "name": c.name, "role": c.role}


def _update_character(project_name: str, args: dict) -> dict:
    """内部：更新角色档案"""
    import os
    from pathlib import Path
    from wal.core import CharacterManager

    proj_path = str(Path(os.environ.get("WAL_PROJECTS", "projects")) / project_name)
    cm = CharacterManager(proj_path)
    cm.load()

    char_id = args["char_id"]
    # 支持按名字查找
    char = cm.get_character(char_id)
    if not char:
        all_chars = cm.list_characters()
        for c in all_chars:
            if getattr(c, 'name', '') == char_id:
                char = c
                char_id = getattr(c, 'id', char_id)
                break
    if not char:
        return {"error": f"角色 '{args['char_id']}' 不存在"}

    # 收集要更新的字段
    updates = {}
    field_map = {
        "personality_traits": "personality_traits",
        "motivation": "motivation",
        "appearance": "appearance",
        "age": "age",
        "background_story": "background_story",
        "arc_progress": "arc_progress",
        "notes": "notes",
    }
    for arg_key, model_key in field_map.items():
        if arg_key in args and args[arg_key]:
            if arg_key == "personality_traits":
                # 逗号分隔 → list
                updates[model_key] = [t.strip() for t in args[arg_key].split(",") if t.strip()]
            else:
                updates[model_key] = args[arg_key]

    if not updates:
        return {"error": "没有提供要更新的字段", "hint": "至少传一个可更新字段"}

    cm.update_character(char_id, **updates)
    # 重新读取返回最新状态
    updated = cm.get_character(char_id)
    return {
        "updated": True,
        "char_id": char_id,
        "name": getattr(updated, 'name', ''),
        "changes": list(updates.keys()),
    }


def _add_plot_line(project_name: str, args: dict) -> dict:
    """内部：创建剧情线"""
    import os
    from pathlib import Path
    from wal.core import PlotManager

    proj_path = str(Path(os.environ.get("WAL_PROJECTS", "projects")) / project_name)
    pm = PlotManager(proj_path)
    pm.load()
    pl = pm.create_plot_line(
        name=args["name"],
        plot_type=args.get("plot_type", "sub"),
        description=args.get("description", ""),
        theme=args.get("theme", ""),
        started_in_chapter=args.get("started_in_chapter", 1),
        target_chapter=args.get("target_chapter", 0),
        level=args.get("level", ""),
        parent_id=args.get("parent_id", ""),
    )
    return {
        "id": pl.id, "name": pl.name,
        "plot_type": pl.plot_type.value if hasattr(pl.plot_type, 'value') else str(pl.plot_type),
        "level": pl.level.value if hasattr(pl.level, 'value') else str(pl.level),
        "status": pl.status.value if hasattr(pl.status, 'value') else str(pl.status),
    }


def _update_story_info(project_name: str, args: dict) -> dict:
    """内部：更新故事信息"""
    import os
    from pathlib import Path
    from wal.core import StoryManager
    from wal.models.story import StoryStatus

    proj_path = str(Path(os.environ.get("WAL_PROJECTS", "projects")) / project_name)
    sm = StoryManager(proj_path)
    sm.load_story()

    updates = {}
    for key in ("name", "author", "summary", "genre", "notes", "style"):
        val = args.get(key, "")
        if val:
            updates[key] = val

    # status 需转为 StoryStatus 枚举
    status_str = args.get("status", "")
    if status_str:
        status_map = {
            "planning": StoryStatus.PLANNING,
            "writing": StoryStatus.WRITING,
            "completed": StoryStatus.COMPLETED,
            "paused": StoryStatus.PAUSED,
            "done": StoryStatus.COMPLETED,  # alias
        }
        if status_str in status_map:
            updates["status"] = status_map[status_str]

    tags_str = args.get("tags", "")
    if tags_str:
        tags_list = [t.strip() for t in tags_str.split(",") if t.strip()]
        updates["tags"] = tags_list

    if updates:
        sm.update_story(**updates)

    story = sm.get_story()
    return {
        "name": story.name,
        "author": story.author,
        "summary": story.summary,
        "genre": story.genre,
        "style": story.style,
        "tags": story.tags,
        "status": story.status.value if hasattr(story.status, 'value') else str(story.status),
    }


def _set_writing_style(project_name: str, args: dict) -> dict:
    """内部：设置或查看写作风格"""
    import os
    from pathlib import Path
    from wal.core import StoryManager

    proj_path = str(Path(os.environ.get("WAL_PROJECTS", "projects")) / project_name)
    sm = StoryManager(proj_path)
    sm.load_story()

    style = args.get("style", "").strip() if args.get("style") else ""

    if style:
        # 设置模式
        sm.update_story(style=style)
        return {"action": "set", "style": style,
                "message": f"写作风格已更新为：{style}"}
    else:
        # 读取模式
        story = sm.get_story()
        current = story.style if story and story.style else ""
        if current:
            return {"action": "get", "style": current,
                    "message": f"当前写作风格：{current}"}
        else:
            return {"action": "get", "style": "",
                    "message": "尚未设定写作风格。你可以用 set_writing_style 设定，如：文风简洁有力，多用短句"}


def _add_character_relationship(project_name: str, args: dict) -> dict:
    """内部：添加角色关系"""
    import os
    from pathlib import Path
    from wal.core import CharacterManager

    proj_path = str(Path(os.environ.get("WAL_PROJECTS", "projects")) / project_name)
    cm = CharacterManager(proj_path)
    cm.load()

    # 支持按名称或ID查找角色
    char_a = _resolve_character_id(cm, args["char_a"])
    char_b = _resolve_character_id(cm, args["char_b"])

    rel = cm.add_relationship(
        char_a=char_a,
        char_b=char_b,
        rel_type=args["rel_type"],
        description=args.get("description", ""),
        dynamics=args.get("dynamics", ""),
        history=args.get("history", ""),
    )
    return {
        "char_a": rel.character_a, "char_b": rel.character_b,
        "rel_type": rel.rel_type.value if hasattr(rel.rel_type, 'value') else str(rel.rel_type),
        "description": rel.description,
    }


def _resolve_character_id(cm, name_or_id: str) -> str:
    """按ID或名称解析角色ID。若传入的是ID（char_xxx格式），直接返回；否则按名称模糊搜索。"""
    # 已是标准ID格式
    if name_or_id.startswith("char_"):
        char = cm.get_character(name_or_id)
        if char:
            return name_or_id
        raise ValueError(f"角色 {name_or_id} 不存在")

    # 按名称搜索
    matches = []
    for cid, char in cm._characters.items():
        if name_or_id in char.name or name_or_id in (char.aliases or []):
            matches.append(cid)
    if len(matches) == 1:
        return matches[0]
    elif len(matches) == 0:
        raise ValueError(f"未找到名为 '{name_or_id}' 的角色，请先用 list_characters 查看或 add_character 创建")
    else:
        raise ValueError(f"找到多个匹配 '{name_or_id}' 的角色：{matches}，请使用角色ID精确指定")


def _add_custom_document(project_name: str, args: dict) -> dict:
    """内部：创建自定义文档"""
    import os, sqlite3, uuid
    from pathlib import Path
    from datetime import datetime

    proj_path = Path(os.environ.get("WAL_PROJECTS", "projects")) / project_name
    db_path = proj_path / "wal.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    doc_id = f"cd_{uuid.uuid4().hex[:8]}"
    now = datetime.now().isoformat()
    tags_str = args.get("tags", "")
    tags = [t.strip() for t in tags_str.split(",") if t.strip()]

    conn.execute(
        """INSERT INTO custom_documents (id, story_id, title, category, content, tags, created_at, updated_at)
           VALUES (?, 'main', ?, ?, ?, ?, ?, ?)""",
        (doc_id, args["title"], args.get("category", ""), args.get("content", ""),
         json.dumps(tags, ensure_ascii=False), now, now),
    )
    conn.commit()
    conn.close()
    return {"doc_id": doc_id, "title": args["title"], "category": args.get("category", "")}


def _get_custom_document(project_name: str, args: dict) -> dict:
    """内部：获取自定义文档"""
    import os, sqlite3
    from pathlib import Path

    proj_path = Path(os.environ.get("WAL_PROJECTS", "projects")) / project_name
    db_path = proj_path / "wal.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    row = conn.execute(
        "SELECT * FROM custom_documents WHERE id = ? AND story_id = 'main'",
        (args["doc_id"],),
    ).fetchone()
    conn.close()

    if not row:
        return {"error": f"文档 {args['doc_id']} 不存在"}
    return {
        "doc_id": row["id"], "title": row["title"], "category": row["category"],
        "content": row["content"], "tags": json.loads(row["tags"]),
        "created_at": row["created_at"], "updated_at": row["updated_at"],
    }


def _list_custom_documents(project_name: str, args: dict) -> list:
    """内部：列出自定义文档摘要"""
    import os, sqlite3
    from pathlib import Path

    proj_path = Path(os.environ.get("WAL_PROJECTS", "projects")) / project_name
    db_path = proj_path / "wal.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    category = args.get("category", "")
    limit = args.get("limit", 20)

    if category:
        rows = conn.execute(
            "SELECT id, title, category, content, tags, created_at, updated_at "
            "FROM custom_documents WHERE story_id = 'main' AND category = ? "
            "ORDER BY updated_at DESC LIMIT ?",
            (category, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, title, category, content, tags, created_at, updated_at "
            "FROM custom_documents WHERE story_id = 'main' "
            "ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    conn.close()

    results = []
    for row in rows:
        content = row["content"] or ""
        results.append({
            "doc_id": row["id"],
            "title": row["title"],
            "category": row["category"],
            "preview": content[:100] + ("..." if len(content) > 100 else ""),
            "tags": json.loads(row["tags"]),
            "updated_at": row["updated_at"],
        })
    return results


def _update_custom_document(project_name: str, args: dict) -> dict:
    """内部：更新自定义文档"""
    import os, sqlite3
    from pathlib import Path
    from datetime import datetime

    proj_path = Path(os.environ.get("WAL_PROJECTS", "projects")) / project_name
    db_path = proj_path / "wal.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # 检查文档存在
    existing = conn.execute(
        "SELECT * FROM custom_documents WHERE id = ? AND story_id = 'main'",
        (args["doc_id"],),
    ).fetchone()
    if not existing:
        conn.close()
        return {"error": f"文档 {args['doc_id']} 不存在"}

    updates = {}
    for key in ("title", "category", "content"):
        val = args.get(key, "")
        if val:
            updates[key] = val

    tags_str = args.get("tags", "")
    if tags_str:
        tags_list = [t.strip() for t in tags_str.split(",") if t.strip()]
        updates["tags"] = json.dumps(tags_list, ensure_ascii=False)

    if updates:
        updates["updated_at"] = datetime.now().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [args["doc_id"]]
        conn.execute(
            f"UPDATE custom_documents SET {set_clause} WHERE id = ?",
            values,
        )
        conn.commit()

    row = conn.execute(
        "SELECT * FROM custom_documents WHERE id = ?", (args["doc_id"],),
    ).fetchone()
    conn.close()
    return {
        "doc_id": row["id"], "title": row["title"], "category": row["category"],
        "content": row["content"], "tags": json.loads(row["tags"]),
        "updated_at": row["updated_at"],
    }


def _delete_custom_document(project_name: str, args: dict) -> dict:
    """内部：删除自定义文档"""
    import os, sqlite3
    from pathlib import Path

    proj_path = Path(os.environ.get("WAL_PROJECTS", "projects")) / project_name
    db_path = proj_path / "wal.db"
    conn = sqlite3.connect(str(db_path))

    conn.execute(
        "DELETE FROM custom_documents WHERE id = ? AND story_id = 'main'",
        (args["doc_id"],),
    )
    deleted = conn.total_changes > 0
    conn.commit()
    conn.close()

    if deleted:
        return {"deleted": True, "doc_id": args["doc_id"]}
    return {"error": f"文档 {args['doc_id']} 不存在"}

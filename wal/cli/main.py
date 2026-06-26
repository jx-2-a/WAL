"""WAL CLI — 小说写作助手命令行入口"""

import argparse
import sys
import os
from pathlib import Path

from ..core import StoryManager, PlotManager, CharacterManager, WorldManager, IndexManager
from ..engine import ContextBuilder, PromptBuilder, LLMClient


def get_project_path(name: str) -> str:
    """获取项目目录路径"""
    base = Path(os.environ.get("WAL_PROJECTS", "projects"))
    return str(base / name)


def cmd_init(args):
    """初始化新故事项目"""
    proj_path = get_project_path(args.name)
    sm = StoryManager(proj_path)

    if sm.repo.story_exists() and not args.force:
        print(f"项目 '{args.name}' 已存在。使用 --force 覆盖。")
        return

    sm.create_story(args.name, args.author, args.summary, genre=args.genre, tags=args.tags)
    print(f"故事项目 '{args.name}' 创建成功！")
    print(f"  路径：{proj_path}")
    print(f"  类型：{args.genre}")


def cmd_status(args):
    """查看故事状态"""
    proj_path = get_project_path(args.name)
    sm = StoryManager(proj_path)
    sm.load_story()

    status = sm.get_story_status()
    if status.get("status") == "no story loaded":
        print("未找到故事项目。")
        return

    print(f"《{status['name']}》")
    print(f"  状态：{status['status']}")
    print(f"  章节：{status['done_chapters']}/{status['total_chapters']} 完成 ({status['progress_percent']}%)")
    print(f"  总字数：{status['total_words']}")


def cmd_outline(args):
    """导出大纲"""
    proj_path = get_project_path(args.name)
    sm = StoryManager(proj_path)
    sm.load_story()

    outline = sm.export_outline()
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(outline)
        print(f"大纲已导出到 {args.output}")
    else:
        print(outline)


def cmd_chapter_add(args):
    """添加章节"""
    proj_path = get_project_path(args.name)
    sm = StoryManager(proj_path)
    sm.load_story()

    ch = sm.add_chapter(args.title, word_count_target=args.words,
                        summary=args.summary or "", notes=args.notes or "",
                        volume_number=args.volume or 0)
    vol_info = f"（第{args.volume}卷）" if args.volume else ""
    print(f"第{ch.number}章「{ch.title}」{vol_info}已添加。")


def cmd_volume_add(args):
    """添加卷"""
    proj_path = get_project_path(args.name)
    sm = StoryManager(proj_path)
    sm.load_story()

    vol = sm.add_volume(args.title, part_id=args.part or "",
                        summary=args.summary or "", theme=args.theme or "",
                        notes=args.notes or "")
    part_info = f"（第{args.part}部）" if args.part else ""
    print(f"第{vol.number}卷「{vol.title}」{part_info}已添加（ID: {vol.id}）")


def cmd_volume_list(args):
    """列出卷"""
    proj_path = get_project_path(args.name)
    sm = StoryManager(proj_path)
    sm.load_story()

    vols = sm.list_volumes(args.part or "")
    if not vols:
        print("暂无卷。")
        return

    for v in vols:
        ch_count = len(v.chapters) if v.chapters else 0
        done = sum(1 for c in v.chapters if c.status == "done") if v.chapters else 0
        status_icon = {"planning": "📋", "writing": "✍️", "completed": "✅"}.get(v.status, "")
        print(f"{status_icon} 第{v.number}卷《{v.title}》")
        print(f"   主题：{v.theme or '（未设定）'}  |  章节：{done}/{ch_count}")


def cmd_part_add(args):
    """添加部"""
    proj_path = get_project_path(args.name)
    sm = StoryManager(proj_path)
    sm.load_story()

    part = sm.add_part(args.title, summary=args.summary or "", notes=args.notes or "")
    print(f"第{part.number}部「{part.title}」已添加（ID: {part.id}）")


def cmd_plot_list(args):
    """列出剧情线"""
    proj_path = get_project_path(args.name)
    pm = PlotManager(proj_path)
    pm.load()

    plots = pm.list_plot_lines(args.type or None)
    if not plots:
        print("暂无剧情线。")
        return

    for pl in plots:
        progress = pl.progress_percent()
        bar = "█" * int(progress / 10) + "░" * (10 - int(progress / 10))
        tag = "主线" if pl.plot_type.value == "main" else "支线"
        print(f"[{tag}] {pl.name}  {bar} {progress}%")


def cmd_plot_add(args):
    """添加剧情线"""
    proj_path = get_project_path(args.name)
    pm = PlotManager(proj_path)
    pm.load()

    pl = pm.create_plot_line(args.title, plot_type=args.type or "sub",
                             description=args.desc or "", theme=args.theme or "")
    print(f"剧情线 '{pl.name}' ({args.type}) 已创建，ID: {pl.id}")


def cmd_plot_point_add(args):
    """添加情节点"""
    proj_path = get_project_path(args.name)
    pm = PlotManager(proj_path)
    pm.load()

    pp = pm.add_plot_point(args.plot_id, args.title, description=args.desc or "",
                           chapter_assigned=args.chapter or 0,
                           emotional_tone=args.tone or "")
    print(f"情节点 '{pp.title}' 已添加到 {args.plot_id}（第{args.chapter}章）")


def cmd_plot_check(args):
    """剧情健康度检查"""
    proj_path = get_project_path(args.name)
    pm = PlotManager(proj_path)
    pm.load()

    result = pm.plot_interweave_check()
    print(f"剧情健康度：{'OK' if result['healthy'] else '需关注'}")
    print(f"  主线：{result['metrics']['main_plots']} 条")
    print(f"  支线：{result['metrics']['sub_plots']} 条")
    print(f"  已收束：{result['metrics']['completed_plots']} 条")
    print(f"  未收束：{result['metrics']['dangling_plots']} 条")
    print(f"  交汇点：{result['metrics']['total_intersections']} 个")

    if result["warnings"]:
        print("\n警告：")
        for w in result["warnings"]:
            print(f"  ! {w}")
    if result["suggestions"]:
        print("\n建议：")
        for s in result["suggestions"]:
            print(f"  > {s}")


def cmd_plot_tree(args):
    """剧情层级树"""
    proj_path = get_project_path(args.name)
    pm = PlotManager(proj_path)
    pm.load()

    tree = pm.get_plot_tree()

    def print_node(node, indent=0):
        prefix = "  " * indent + ("└─ " if indent > 0 else "")
        level_tag = {
            "main": "主线", "volume": "卷线",
            "sub": "支线", "character_arc": "角色弧",
        }.get(node["level"], node["level"])
        status_icon = {"active": "○", "completed": "●", "abandoned": "✕"}.get(node["status"], "")
        print(f"{prefix}{status_icon}[{level_tag}] {node['name']} ({node['progress']}%)")
        for child in node.get("children", []):
            print_node(child, indent + 1)

    if not tree:
        print("暂无剧情线。先用 plot-add 添加剧情线。")
        return

    print("=== 剧情层级树 ===\n")
    for root in tree:
        print_node(root)


def cmd_foreshadowing_add(args):
    """添加伏笔"""
    proj_path = get_project_path(args.name)
    pm = PlotManager(proj_path)
    pm.load()

    fw = pm.add_foreshadowing(
        description=args.description,
        created_at_chapter=args.chapter or 0,
        target_chapter=args.target or 0,
        urgency=args.urgency or "medium",
        related_plot_lines=args.plots or [],
        related_characters=args.characters or [],
        notes=args.notes or "",
    )
    print(f"伏笔已添加（ID: {fw.id}）")
    print(f"  描述：{fw.description[:60]}...")
    print(f"  紧急程度：{fw.urgency}  |  计划回收：第{fw.target_chapter}章")


def cmd_foreshadowing_list(args):
    """列出伏笔"""
    proj_path = get_project_path(args.name)
    pm = PlotManager(proj_path)
    pm.load()

    fws = pm.list_foreshadowings(args.status or "")
    if not fws:
        print("暂无伏笔。")
        return

    for fw in fws:
        status_icon = {
            "pending": "[待回收]", "partially_resolved": "[部分回收]",
            "resolved": "[已回收]", "abandoned": "[已废弃]",
        }.get(fw.status.value, "")
        urgency_tag = {"low": "低", "medium": "中", "high": "高", "critical": "!!紧急!!"}.get(fw.urgency, "")
        print(f"{status_icon} {fw.id}  {urgency_tag}")
        print(f"  {fw.description[:80]}")
        if fw.created_at_chapter:
            ch_info = f"第{fw.created_at_chapter}章埋"
            if fw.resolved_at_chapter:
                ch_info += f" → 第{fw.resolved_at_chapter}章回收"
            elif fw.target_chapter:
                ch_info += f" → 计划第{fw.target_chapter}章回收"
            print(f"  {ch_info}")


def cmd_foreshadowing_resolve(args):
    """回收伏笔"""
    proj_path = get_project_path(args.name)
    pm = PlotManager(proj_path)
    pm.load()

    fw = pm.resolve_foreshadowing(args.fw_id, args.chapter, args.notes or "")
    if fw:
        print(f"伏笔 {args.fw_id} 已在第{args.chapter}章回收。")
    else:
        print(f"伏笔 {args.fw_id} 未找到。")


def cmd_char_snapshot(args):
    """创建角色快照"""
    proj_path = get_project_path(args.name)
    cm = CharacterManager(proj_path)
    cm.load()

    snap = cm.create_snapshot(
        char_id=args.char_id,
        chapter_number=args.chapter,
        chapter_title=args.chapter_title or "",
        arc_progress=args.arc_progress or "",
        personality_changes=args.personality or "",
        new_abilities=args.abilities or [],
        internal_state=args.state or "",
        summary=args.summary or "",
    )
    print(f"快照已创建：{snap.id}")
    print(f"  角色：{args.char_id}  |  第{snap.chapter_number}章")
    if snap.arc_progress:
        print(f"  弧光进度：{snap.arc_progress}")
    if snap.personality_changes:
        print(f"  性格变化：{snap.personality_changes}")


def cmd_index_search(args):
    """全文搜索"""
    proj_path = get_project_path(args.name)
    im = IndexManager(proj_path)

    results = im.search(args.query, limit=args.limit or 20)
    if not results:
        print(f"未找到与 '{args.query}' 相关的内容。")
        print("提示：先用 wal index-chapter <章节号> 索引章节内容。")
        return

    print(f"=== 搜索 '{args.query}' 共 {len(results)} 条结果 ===\n")
    for i, r in enumerate(results, 1):
        print(f"{i}. [{r.get('chapter_title', '')}] {r.get('scene_title', '')}")
        snippet = r.get("snippet", "")
        # 清理 FTS5 高亮标记
        snippet = snippet.replace("<b>", "**").replace("</b>", "**")
        print(f"   {snippet[:120]}")
        chars = r.get("characters_present", "")
        if chars:
            print(f"   出场：{chars}")
        print()


def cmd_index_chapter(args):
    """索引章节"""
    proj_path = get_project_path(args.name)
    im = IndexManager(proj_path)

    result = im.auto_index_chapter(args.chapter)
    if "error" in result:
        print(f"错误：{result['error']}")
    else:
        print(f"第{result['chapter_number']}章《{result['chapter_title']}》索引完成")
        print(f"  场景数：{result['scenes_indexed']}")
        if result.get("characters_found"):
            print(f"  角色：{', '.join(result['characters_found'][:10])}")
        if result.get("locations_found"):
            print(f"  地点：{', '.join(result['locations_found'][:10])}")


def cmd_milestone(args):
    """创建里程碑"""
    proj_path = get_project_path(args.name)
    im = IndexManager(proj_path)

    if args.auto:
        ms = im.auto_create_milestone(args.chapter)
    else:
        ms = im.create_milestone(
            name=args.title or f"第{args.chapter}章里程碑",
            chapter_number=args.chapter,
            story_state_summary=args.summary or "",
        )

    if "error" in ms:
        print(f"错误：{ms['error']}")
    else:
        print(f"里程碑已创建：{ms['name']}")
        print(f"  章节：第{ms['chapter_number']}章")
        if ms.get("total_words_at_point"):
            print(f"  累计字数：{ms['total_words_at_point']}")
        if ms.get("character_states"):
            char_count = len(ms["character_states"])
            print(f"  角色状态：{char_count} 个")


def cmd_review(args):
    """快速回顾"""
    proj_path = get_project_path(args.name)
    im = IndexManager(proj_path)

    result = im.quick_review(args.start, args.end, topic=args.topic or "")
    print(f"=== 回顾 {result['range']} ===")
    print(f"共 {result['chapter_count']} 章，{result['total_words']} 字\n")

    for ch in result.get("chapters", []):
        status_icon = {"done": "[完成]", "writing": "[写作中]", "planning": "[规划]"}.get(ch["status"], "")
        print(f"{status_icon} 第{ch['number']}章《{ch['title']}》")
        if ch["summary"]:
            print(f"  {ch['summary'][:100]}")
        print(f"  {ch['word_count']} 字 | {ch['scene_count']} 个场景")

    if result.get("fts_matches"):
        print(f"\n--- 主题 '{result['topic']}' 匹配 ({result['match_count']} 条) ---")
        for m in result["fts_matches"][:10]:
            snippet = m["snippet"].replace("<b>", "**").replace("</b>", "**")
            print(f"  [{m['chapter_title']}] {snippet[:100]}")


def cmd_export(args):
    """导出章节/卷/全书"""
    import os
    proj_path = get_project_path(args.name)
    sm = StoryManager(proj_path)
    sm.load_story()

    fmt = args.format or "plain"
    output_dir = args.output or "."
    ext_map = {"markdown": ".md", "html": ".html", "plain": ".txt", "docx": ".docx"}
    ext = ext_map.get(fmt, ".txt")

    # --to-files 模式：按卷/章/单文件分层导出到磁盘
    if getattr(args, 'to_files', False):
        split_mode = getattr(args, 'split', 'volume')
        structure = getattr(args, 'structure', 'full')
        result = sm.export_novel_files(output_dir, mode=split_mode, fmt=fmt, structure=structure)
        print(result.get("structure", ""))
        print(f"\n格式：{fmt} | 组织方式：{result['mode']}")
        print(f"已导出 {result['chapters_exported']}/{result['total_chapters']} 章")
        print(f"总字数：{result['total_words']} | 输出目录：{result['output_dir']}")
        return

    if args.full:
        # 全书导出
        if fmt == "docx":
            fpath = os.path.join(output_dir, f"novel_full{ext}")
            sm.export_full_novel_docx(fpath)
            fsize = os.path.getsize(fpath)
            print(f"全书已导出到 {fpath}（{fsize} 字节）")
        else:
            content = sm.export_full_novel(fmt)
            fpath = os.path.join(output_dir, f"novel_full{ext}")
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"全书已导出到 {fpath}（{len(content)} 字符）")

    elif args.volume:
        # 卷导出
        if fmt == "docx":
            vol_doc = sm.export_volume_docx(args.volume)
            fpath = os.path.join(output_dir, f"volume_{args.volume:02d}{ext}")
            vol_doc.save(fpath)
            fsize = os.path.getsize(fpath)
            print(f"第{args.volume}卷已导出到 {fpath}（{fsize} 字节）")
        else:
            content = sm.export_volume(args.volume, fmt)
            fpath = os.path.join(output_dir, f"volume_{args.volume:02d}{ext}")
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"第{args.volume}卷已导出到 {fpath}（{len(content)} 字符）")

    elif args.chapters:
        # 批量/单章导出
        ch_range = args.chapters
        if "-" in ch_range:
            parts_ch = ch_range.split("-")
            start = int(parts_ch[0])
            end = int(parts_ch[1])
        else:
            start = end = int(ch_range)

        if fmt == "docx":
            if start == end:
                ch_doc = sm.export_chapter_docx(start)
                fpath = os.path.join(output_dir, f"ch_{start:04d}{ext}")
                ch_doc.save(fpath)
                fsize = os.path.getsize(fpath)
                print(f"第{start}章已导出到 {fpath}（{fsize} 字节）")
            else:
                # 批量 docx：每个章节独立文件
                results = sm.batch_export(start, end, "plain", output_dir)
                # batch_export 不支持 docx 直接用，改用循环
                count = 0
                for ch_num in range(start, end + 1):
                    ch_doc = sm.export_chapter_docx(ch_num)
                    ch_title = ""
                    ch = sm.get_chapter(ch_num)
                    if ch:
                        ch_title = ch.title
                    safe_ch = sm._safe_filename(f"第{ch_num:02d}章_{ch_title}")
                    fpath = os.path.join(output_dir, f"{safe_ch[:60]}{ext}")
                    ch_doc.save(fpath)
                    count += 1
                print(f"已导出 {count} 章到 {output_dir}")
        else:
            if start == end:
                exporters = {
                    "markdown": sm.export_chapter_markdown,
                    "html": sm.export_chapter_html,
                    "plain": sm.export_chapter_plain,
                }
                exporter = exporters.get(fmt, sm.export_chapter_plain)
                content = exporter(start)
                fpath = os.path.join(output_dir, f"ch_{start:04d}{ext}")
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"第{start}章已导出到 {fpath}（{len(content)} 字符）")
            else:
                results = sm.batch_export(start, end, fmt, output_dir)
                print(f"已导出 {len(results)} 章到 {output_dir}")
                for ch_num, fpath in results.items():
                    print(f"  第{ch_num}章 → {fpath}")

    else:
        print("请指定 --chapters、--volume、--full 或 --to-files。")


def cmd_char_list(args):
    """列出角色"""
    proj_path = get_project_path(args.name)
    cm = CharacterManager(proj_path)
    cm.load()

    chars = cm.list_characters(args.role or None)
    if not chars:
        print("暂无角色。")
        return

    for c in chars:
        role_tag = {"protagonist": "主角", "antagonist": "反派",
                    "supporting": "配角", "minor": "次要"}.get(c.role, c.role)
        print(f"[{role_tag}] {c.name}  |  {c.motivation[:30] if c.motivation else '（暂无动机）'}")


def cmd_char_add(args):
    """添加角色"""
    proj_path = get_project_path(args.name)
    cm = CharacterManager(proj_path)
    cm.load()

    c = cm.create_character(args.name, role=args.role or "supporting",
                            background_story=args.bg or "", motivation=args.motivation or "")
    print(f"角色 '{c.name}' ({args.role}) 已创建，ID: {c.id}")


def cmd_char_check(args):
    """角色一致性检查"""
    proj_path = get_project_path(args.name)
    cm = CharacterManager(proj_path)
    cm.load()

    results = cm.check_all_consistency()
    for r in results:
        status = "OK" if r["ok"] else "需修复"
        print(f"\n{r['character']} ({r['role']}): {status}")
        for issue in r["issues"]:
            print(f"  !! {issue}")
        for warn in r["warnings"]:
            print(f"  ? {warn}")


def cmd_write_context(args):
    """生成写作上下文"""
    proj_path = get_project_path(args.name)
    sm = StoryManager(proj_path)
    sm.load_story()
    pm = PlotManager(proj_path)
    pm.load()
    cm = CharacterManager(proj_path)
    cm.load()
    wm = WorldManager(proj_path)
    wm.load()

    cb = ContextBuilder(sm, pm, cm, wm)
    context = cb.build_compact_context(args.chapter)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(context)
        print(f"写作上下文已导出到 {args.output}")
    else:
        print(context)


def main():
    parser = argparse.ArgumentParser(
        prog="wal",
        description="WAL — 小说写作 Agent 助手",
    )
    sub = parser.add_subparsers(dest="command", help="可用命令")

    # init
    p_init = sub.add_parser("init", help="初始化新故事")
    p_init.add_argument("name", help="故事名称")
    p_init.add_argument("--author", default="", help="作者")
    p_init.add_argument("--summary", default="", help="故事梗概")
    p_init.add_argument("--genre", default="", help="类型")
    p_init.add_argument("--tags", nargs="*", default=[], help="标签")
    p_init.add_argument("--force", action="store_true", help="强制覆盖")

    # status
    p_status = sub.add_parser("status", help="查看故事状态")
    p_status.add_argument("name", help="故事名称")

    # outline
    p_outline = sub.add_parser("outline", help="导出大纲")
    p_outline.add_argument("name", help="故事名称")
    p_outline.add_argument("-o", "--output", help="输出文件")

    # chapter add
    p_ch_add = sub.add_parser("chapter-add", help="添加章节")
    p_ch_add.add_argument("name", help="故事名称")
    p_ch_add.add_argument("title", help="章节标题")
    p_ch_add.add_argument("--words", type=int, default=3000, help="目标字数")
    p_ch_add.add_argument("--summary", help="章节摘要")
    p_ch_add.add_argument("--notes", help="备注")
    p_ch_add.add_argument("--volume", type=int, default=0, help="所属卷序号")

    # volume add
    p_vol_add = sub.add_parser("volume-add", help="添加卷")
    p_vol_add.add_argument("name", help="故事名称")
    p_vol_add.add_argument("title", help="卷标题")
    p_vol_add.add_argument("--part", help="所属部ID")
    p_vol_add.add_argument("--summary", help="卷摘要")
    p_vol_add.add_argument("--theme", help="卷主题")
    p_vol_add.add_argument("--notes", help="备注")

    # volume list
    p_vol_list = sub.add_parser("volume-list", help="列出所有卷")
    p_vol_list.add_argument("name", help="故事名称")
    p_vol_list.add_argument("--part", help="按部过滤")

    # part add
    p_part_add = sub.add_parser("part-add", help="添加部/篇")
    p_part_add.add_argument("name", help="故事名称")
    p_part_add.add_argument("title", help="部标题")
    p_part_add.add_argument("--summary", help="部摘要")
    p_part_add.add_argument("--notes", help="备注")

    # plot list
    p_pl = sub.add_parser("plot-list", help="列出剧情线")
    p_pl.add_argument("name", help="故事名称")
    p_pl.add_argument("--type", choices=["main", "sub"], help="过滤类型")

    # plot add
    p_pl_add = sub.add_parser("plot-add", help="添加剧情线")
    p_pl_add.add_argument("name", help="故事名称")
    p_pl_add.add_argument("title", help="剧情线名称")
    p_pl_add.add_argument("--type", choices=["main", "sub"], default="sub", help="主线/支线")
    p_pl_add.add_argument("--desc", help="描述")
    p_pl_add.add_argument("--theme", help="主题")

    # plot point add
    p_pp = sub.add_parser("plot-point-add", help="添加情节点")
    p_pp.add_argument("name", help="故事名称")
    p_pp.add_argument("plot_id", help="剧情线ID")
    p_pp.add_argument("title", help="情节点标题")
    p_pp.add_argument("--desc", help="描述")
    p_pp.add_argument("--chapter", type=int, default=0, help="分配章节")
    p_pp.add_argument("--tone", help="情绪基调")

    # plot tree
    p_ptree = sub.add_parser("plot-tree", help="剧情层级树状图")
    p_ptree.add_argument("name", help="故事名称")

    # plot check
    p_check = sub.add_parser("plot-check", help="剧情健康度检查")
    p_check.add_argument("name", help="故事名称")

    # foreshadowing add
    p_fw_add = sub.add_parser("foreshadowing-add", help="添加伏笔")
    p_fw_add.add_argument("name", help="故事名称")
    p_fw_add.add_argument("description", help="伏笔描述")
    p_fw_add.add_argument("--chapter", type=int, default=0, help="埋设章节")
    p_fw_add.add_argument("--target", type=int, default=0, help="计划回收章节")
    p_fw_add.add_argument("--urgency", choices=["low", "medium", "high", "critical"], default="medium", help="紧急程度")
    p_fw_add.add_argument("--plots", nargs="*", default=[], help="关联剧情线ID")
    p_fw_add.add_argument("--characters", nargs="*", default=[], help="关联角色ID")
    p_fw_add.add_argument("--notes", help="备注")

    # foreshadowing list
    p_fw_list = sub.add_parser("foreshadowing-list", help="列出伏笔")
    p_fw_list.add_argument("name", help="故事名称")
    p_fw_list.add_argument("--status", choices=["pending", "partially_resolved", "resolved", "abandoned"], help="按状态过滤")

    # foreshadowing resolve
    p_fw_resolve = sub.add_parser("foreshadowing-resolve", help="回收伏笔")
    p_fw_resolve.add_argument("name", help="故事名称")
    p_fw_resolve.add_argument("fw_id", help="伏笔ID")
    p_fw_resolve.add_argument("chapter", type=int, help="回收章节号")
    p_fw_resolve.add_argument("--notes", help="回收说明")

    # char snapshot
    p_cs = sub.add_parser("char-snapshot", help="创建角色快照")
    p_cs.add_argument("name", help="故事名称")
    p_cs.add_argument("char_id", help="角色ID")
    p_cs.add_argument("chapter", type=int, help="章节号")
    p_cs.add_argument("--chapter-title", help="章节标题")
    p_cs.add_argument("--arc-progress", help="弧光进度")
    p_cs.add_argument("--personality", help="性格变化")
    p_cs.add_argument("--abilities", nargs="*", default=[], help="新能力")
    p_cs.add_argument("--state", help="内心状态")
    p_cs.add_argument("--summary", help="角色总结")

    # index search
    p_is = sub.add_parser("index-search", help="全文搜索")
    p_is.add_argument("name", help="故事名称")
    p_is.add_argument("query", help="搜索关键词")
    p_is.add_argument("--limit", type=int, default=20, help="结果数量上限")

    # index chapter
    p_ic = sub.add_parser("index-chapter", help="索引章节到FTS5")
    p_ic.add_argument("name", help="故事名称")
    p_ic.add_argument("chapter", type=int, help="章节号")

    # milestone
    p_ms = sub.add_parser("milestone", help="创建里程碑")
    p_ms.add_argument("name", help="故事名称")
    p_ms.add_argument("chapter", type=int, help="章节号")
    p_ms.add_argument("--title", help="里程碑名称")
    p_ms.add_argument("--summary", help="故事状态摘要")
    p_ms.add_argument("--auto", action="store_true", help="自动收集当前状态")

    # review
    p_rv = sub.add_parser("review", help="快速回顾章节范围")
    p_rv.add_argument("name", help="故事名称")
    p_rv.add_argument("start", type=int, help="起始章节")
    p_rv.add_argument("end", type=int, help="结束章节")
    p_rv.add_argument("--topic", help="回顾主题/关键词")

    # export
    p_exp = sub.add_parser("export", help="导出章节/卷/全书")
    p_exp.add_argument("name", help="故事名称")
    p_exp.add_argument("--chapters", help="章节范围，如 '5' 或 '1-10'")
    p_exp.add_argument("--volume", type=int, help="卷序号")
    p_exp.add_argument("--full", action="store_true", help="导出全书")
    p_exp.add_argument("--format", choices=["markdown", "html", "plain", "docx"], default="plain", help="导出格式：plain/markdown/html/docx（默认 plain 纯文本）")
    p_exp.add_argument("--output", "-o", help="输出目录")
    p_exp.add_argument("--to-files", action="store_true", help="按卷分文件夹导出为独立文件（推荐）")
    p_exp.add_argument("--split", choices=["volume", "chapter", "single", "auto"], default="volume", help="文件分层方式：volume=按卷分文件夹（默认），chapter=平铺，single=全书合并为单文件（总集），auto=自动")
    p_exp.add_argument("--structure", choices=["full", "flat"], default="full", help="内部结构（仅 --split single 时生效）：full=含部/卷标题，flat=纯章节排列")

    # char list
    p_cl = sub.add_parser("char-list", help="列出角色")
    p_cl.add_argument("name", help="故事名称")
    p_cl.add_argument("--role", choices=["protagonist", "antagonist", "supporting", "minor"], help="过滤角色类型")

    # char add
    p_ca = sub.add_parser("char-add", help="添加角色")
    p_ca.add_argument("name", help="故事名称")
    p_ca.add_argument("char_name", help="角色名")
    p_ca.add_argument("--role", default="supporting", help="角色类型")
    p_ca.add_argument("--bg", help="背景故事")
    p_ca.add_argument("--motivation", help="核心动机")

    # char check
    p_cc = sub.add_parser("char-check", help="角色一致性检查")
    p_cc.add_argument("name", help="故事名称")

    # write context
    p_wc = sub.add_parser("write-context", help="生成写作上下文")
    p_wc.add_argument("name", help="故事名称")
    p_wc.add_argument("chapter", type=int, help="章节号")
    p_wc.add_argument("-o", "--output", help="输出到文件")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    commands = {
        "init": cmd_init,
        "status": cmd_status,
        "outline": cmd_outline,
        "chapter-add": cmd_chapter_add,
        "volume-add": cmd_volume_add,
        "volume-list": cmd_volume_list,
        "part-add": cmd_part_add,
        "plot-list": cmd_plot_list,
        "plot-add": cmd_plot_add,
        "plot-point-add": cmd_plot_point_add,
        "plot-tree": cmd_plot_tree,
        "plot-check": cmd_plot_check,
        "foreshadowing-add": cmd_foreshadowing_add,
        "foreshadowing-list": cmd_foreshadowing_list,
        "foreshadowing-resolve": cmd_foreshadowing_resolve,
        "char-snapshot": cmd_char_snapshot,
        "index-search": cmd_index_search,
        "index-chapter": cmd_index_chapter,
        "milestone": cmd_milestone,
        "review": cmd_review,
        "export": cmd_export,
        "char-list": cmd_char_list,
        "char-add": cmd_char_add,
        "char-check": cmd_char_check,
        "write-context": cmd_write_context,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()

"""Plan 模式工具函数 — 供 AI Agent 在规划/创意讨论模式下调用

这些工具聚焦于分析和创意：
- 分析剧情结构、节奏、主题一致性
- 构思角色弧光、剧情转折、冲突升级
- 检测剧情漏洞、世界观扩展方向
- 持久化保存分析笔记（planning_notes 表）
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional


def _get_project_path(name: str) -> str:
    base = Path(os.environ.get("WAL_PROJECTS", "projects"))
    return str(base / name)


def _init_managers(project_name: str):
    """初始化管理器用于只读分析"""
    from ..core import StoryManager, PlotManager, CharacterManager

    proj = _get_project_path(project_name)
    sm = StoryManager(proj)
    sm.load_story()
    pm = PlotManager(proj)
    pm.load()
    cm = CharacterManager(proj)
    cm.load()
    return sm, pm, cm


# ============================================================
# Plan 模式工具 — 8 个分析/创意工具
# ============================================================

def suggest_plot_direction(project_name: str, context: str = "",
                           count: int = 3) -> dict:
    """基于当前剧情状态，建议剧情发展方向

    分析当前主线进度、支线状态、未收束伏笔、角色弧光阶段，
    然后给出 count 个可选的发展方向。
    """
    sm, pm, cm = _init_managers(project_name)

    # 收集当前状态
    story_status = sm.get_story_status()
    all_plots = pm.track_plot_progress()
    plot_tree = pm.get_plot_tree()
    dangling = pm.find_dangling_plots()
    fw_health = pm.check_foreshadowing_health(
        story_status.get("total_chapters", 0)
    )

    # 分析主线
    main_plots = [p for p in all_plots if p.get("type") == "main"]
    sub_plots = [p for p in all_plots if p.get("type") != "main"]

    # 当前章节进度
    total_ch = story_status.get("total_chapters", 0)
    done_ch = story_status.get("done_chapters", 0)

    # 收集角色信息
    all_chars = cm.list_characters()
    chars_summary = [
        {"name": c.name, "role": c.role, "first_ch": c.first_appearance}
        for c in all_chars
    ]

    analysis = {
        "story_name": story_status.get("name", ""),
        "current_state": {
            "total_chapters": total_ch,
            "done_chapters": done_ch,
            "progress_pct": story_status.get("progress_percent", 0),
            "total_words": story_status.get("total_words", 0),
            "story_status": story_status.get("status", ""),
        },
        "plot_structure": {
            "main_plot_count": len(main_plots),
            "sub_plot_count": len(sub_plots),
            "main_plots": [{"name": p["name"], "progress": p.get("progress_percent", 0)}
                           for p in main_plots],
            "dangling_plots": [{"name": p.name, "progress": p.progress_percent()}
                               for p in dangling[:5]],
        },
        "foreshadowing": {
            "total": fw_health.get("total_foreshadowings", 0),
            "resolved": fw_health.get("resolved", 0),
            "pending_urgent": fw_health.get("pending_urgent", 0),
            "long_pending": fw_health.get("long_pending", 0),
        },
        "characters": {
            "total": len(chars_summary),
            "protagonists": [c["name"] for c in chars_summary if c["role"] == "protagonist"],
            "antagonists": [c["name"] for c in chars_summary if c["role"] == "antagonist"],
        },
        "context": context,
    }

    return analysis


def brainstorm_character_arc(project_name: str, char_id: str = "",
                              char_name: str = "", focus: str = "") -> dict:
    """为指定角色构思弧光发展方向

    分析角色的当前状态、已记录的演变历程、与其他角色的关系，
    提供弧光发展建议（成长/堕落/救赎/觉醒等方向）。
    """
    sm, pm, cm = _init_managers(project_name)

    # 查找角色
    char = None
    if char_id:
        char = cm.get_character(char_id)
    elif char_name:
        for c in cm.list_characters():
            if c.name == char_name:
                char = c
                char_id = c.id
                break

    if not char:
        return {"error": f"角色未找到: char_id={char_id}, char_name={char_name}"}

    # 获取角色演变历程
    evolution = cm.get_character_evolution(char_id)

    # 获取角色关系
    relationships = []
    for other_id, rel in char.relationships.items():
        other = cm.get_character(other_id)
        relationships.append({
            "with": other.name if other else other_id,
            "type": rel.rel_type.value,
            "description": rel.description,
            "dynamics": rel.dynamics,
        })

    # 角色当前状态摘要
    current_state = {
        "name": char.name,
        "role": char.role,
        "motivation": char.motivation,
        "background": char.background_story[:200] if char.background_story else "",
        "personality": char.personality_traits,
        "abilities": char.abilities,
        "weaknesses": char.weaknesses,
        "first_appearance": char.first_appearance,
        "last_appearance": char.first_appearance,  # model doesn't track last_appearance separately
    }

    analysis = {
        "character_id": char.id,
        "character_name": char.name,
        "current_state": current_state,
        "relationships": relationships,
        "evolution_snapshots": evolution.get("snapshots", []),
        "evolution_summary": evolution.get("summary", ""),
        "focus": focus,
        "arc_directions": [
            "成长弧 (Growth): 从弱小到强大，克服内在缺陷",
            "堕落弧 (Fall): 从光明到黑暗，被欲望或环境吞噬",
            "救赎弧 (Redemption): 犯下错误→承受后果→寻求救赎",
            "觉醒弧 (Awakening): 从无知/迷茫到觉悟/清醒",
            "悲剧弧 (Tragedy): 因不可调和的性格缺陷走向毁灭",
            "传承弧 (Mentorship): 从被引导者成长为引导者",
        ],
    }

    return analysis


def analyze_plot_holes(project_name: str, deep: bool = False) -> dict:
    """分析剧情漏洞和逻辑不一致

    检查：
    - 角色的行为是否与其性格/动机一致
    - 伏笔是否回收
    - 剧情线是否有逻辑断裂
    - 时间线是否有冲突
    - 角色能力/设定是否前后矛盾
    """
    sm, pm, cm = _init_managers(project_name)

    issues = []

    # 1. 检查未收束支线
    dangling = pm.find_dangling_plots()
    if dangling:
        issues.append({
            "type": "dangling_plots",
            "severity": "medium",
            "count": len(dangling),
            "details": [
                {"name": p.name, "progress": p.progress_percent(),
                 "description": p.description[:100]}
                for p in dangling
            ],
            "suggestion": "未收束支线过多可能导致读者感觉故事不完整",
        })

    # 2. 健康检查
    health = pm.plot_interweave_check()
    if health.get("warnings"):
        for w in health["warnings"]:
            issues.append({
                "type": "plot_health",
                "severity": "medium",
                "detail": w,
            })

    # 3. 检查伏笔健康
    fw_health = pm.check_foreshadowing_health(
        sm.get_story_status().get("total_chapters", 0)
    )
    if fw_health.get("dangling_count", 0) > 0:
        issues.append({
            "type": "unresolved_foreshadowing",
            "severity": "high" if fw_health.get("dangling_count", 0) > 5 else "medium",
            "count": fw_health.get("dangling_count", 0),
            "detail": f"还有 {fw_health.get('dangling_count', 0)} 个伏笔未回收",
        })

    # 4. 检查角色一致性
    consistency = cm.check_all_consistency()
    for r in consistency:
        if not r.get("ok", True):
            issues.append({
                "type": "character_consistency",
                "severity": "high",
                "character": r["character"],
                "role": r.get("role", ""),
                "issues": r.get("issues", []),
            })

    # 5. 检查章节覆盖（角色是否长期未出场）
    total_ch = sm.get_story_status().get("total_chapters", 0)
    for c in cm.list_characters():
        last_app_raw = getattr(c, 'last_appearance', c.first_appearance)
        if last_app_raw and total_ch > 0:
            # first_appearance/last_appearance 是字符串，提取数字
            try:
                last_app_num = int(last_app_raw) if str(last_app_raw).isdigit() else int(''.join(filter(str.isdigit, str(last_app_raw))) or '0')
            except (ValueError, TypeError):
                last_app_num = 0
            if last_app_num <= 0:
                continue
            gap = total_ch - last_app_num
            if gap > 20 and c.role in ("protagonist", "antagonist"):
                issues.append({
                    "type": "character_absence",
                    "severity": "medium",
                    "character": c.name,
                    "role": c.role,
                    "detail": f"{c.name} 已 {gap} 章未出场（最后出场：第{last_app}章）",
                })

    analysis = {
        "story_name": sm.get_story_status().get("name", ""),
        "total_chapters": total_ch,
        "total_issues": len(issues),
        "severity_high": len([i for i in issues if i.get("severity") == "high"]),
        "severity_medium": len([i for i in issues if i.get("severity") == "medium"]),
        "issues": issues,
    }

    if deep:
        # 深度模式：额外检查
        analysis["deep_analysis_note"] = (
            "深度模式已启用。建议逐章检查：时间连续性、角色动机一致性、"
            "能力设定前后一致、世界规则遵守情况。"
        )

    return analysis


def propose_plot_twist(project_name: str, context: str = "",
                        twist_type: str = "") -> dict:
    """基于当前剧情状态，构思剧情转折

    转折类型：
    - revelation: 身份/真相揭露
    - betrayal: 背叛
    - sacrifice: 牺牲
    - unexpected_ally: 意外盟友
    - hidden_enemy: 隐藏敌人
    - power_shift: 力量格局变化
    - moral_dilemma: 道德困境
    """
    sm, pm, cm = _init_managers(project_name)

    # 收集数据
    all_plots = pm.track_plot_progress()
    chars = cm.list_characters()
    fws = pm.list_foreshadowings("pending")

    # 关键角色
    protagonists = [c for c in chars if c.role == "protagonist"]
    antagonists = [c for c in chars if c.role == "antagonist"]
    supporting = [c for c in chars if c.role == "supporting"]

    # 当前进度
    story_status = sm.get_story_status()
    current_chapter = story_status.get("total_chapters", 0)

    analysis = {
        "story_name": story_status.get("name", ""),
        "current_chapter": current_chapter,
        "twist_type_requested": twist_type or "any",
        "context": context,
        "available_elements": {
            "protagonists": [c.name for c in protagonists],
            "antagonists": [c.name for c in antagonists],
            "key_supporting": [c.name for c in supporting[:5]],
            "active_plots": [
                {"name": p["name"], "type": p["type"], "progress": p.get("progress_percent", 0)}
                for p in all_plots if p.get("progress_percent", 0) < 100
            ][:5],
            "pending_foreshadowings": [
                {"description": f.description[:80], "urgency": f.urgency,
                 "target_chapter": f.target_chapter}
                for f in fws[:5]
            ],
        },
        "twist_categories": {
            "revelation": "身份/真相揭露 — 某个角色的真实身份或过去被揭示",
            "betrayal": "背叛 — 信任的人突然背叛，改变力量格局",
            "sacrifice": "牺牲 — 重要角色为更大利益做出牺牲",
            "unexpected_ally": "意外盟友 — 曾经的对手成为盟友",
            "hidden_enemy": "隐藏敌人 — 身边亲近的人竟是幕后黑手",
            "power_shift": "力量格局变化 — 世界规则/权力结构发生根本改变",
            "moral_dilemma": "道德困境 — 主角面临没有正确答案的艰难选择",
        },
    }

    return analysis


def evaluate_pacing(project_name: str, start_chapter: int = 0,
                     end_chapter: int = 0) -> dict:
    """评估故事节奏

    分析：
    - 每章字数分布（是否波动过大）
    - 高潮/过渡章节的比例
    - 剧情推进速度（每章推进了多少个情节点）
    - 角色出场频率分布
    - 叙事密度（场景数/章节字数比）
    """
    sm, pm, cm = _init_managers(project_name)

    story = sm.get_story()
    if not story or not story.chapters:
        return {"error": "没有章节数据"}

    chapters = story.chapters
    if start_chapter > 0:
        chapters = [c for c in chapters if c.number >= start_chapter]
    if end_chapter > 0:
        chapters = [c for c in chapters if c.number <= end_chapter]

    if not chapters:
        return {"error": "指定范围无章节"}

    # 字数分布
    word_counts = []
    for ch in chapters:
        wc = 0
        if ch.scenes:
            for s in ch.scenes:
                wc += s.word_count if hasattr(s, 'word_count') else (len(s.content) if hasattr(s, 'content') and s.content else 0)
        word_counts.append({"chapter": ch.number, "title": ch.title, "words": wc})

    words_list = [w["words"] for w in word_counts]
    if words_list:
        avg_words = sum(words_list) / len(words_list)
        max_words = max(words_list)
        min_words = min(words_list)
    else:
        avg_words = max_words = min_words = 0

    # 节奏分析
    pacing_issues = []
    if len(words_list) >= 2:
        for i, w in enumerate(words_list):
            if i > 0 and avg_words > 0:
                variation = abs(w - words_list[i - 1]) / avg_words
                if variation > 0.5:
                    pacing_issues.append({
                        "chapter": word_counts[i]["chapter"],
                        "title": word_counts[i]["title"],
                        "words": w,
                        "previous_words": words_list[i - 1],
                        "variation_pct": round(variation * 100),
                        "issue": "字数波动过大" if w > words_list[i - 1] else "字数骤降",
                    })

    # 统计情节推进
    plot_points_done = 0
    plot_points_total = 0
    for plot in pm.track_plot_progress():
        plot_points_total += plot.get("total_points", 0)
        plot_points_done += plot.get("done_points", 0)

    plot_completion_rate = (plot_points_done / plot_points_total * 100) if plot_points_total > 0 else 0

    # 平均每章推进情节点数
    done_chapters = len([c for c in chapters if c.status == "done"])
    avg_points_per_chapter = plot_points_done / done_chapters if done_chapters > 0 else 0

    analysis = {
        "story_name": sm.get_story_status().get("name", ""),
        "range": f"第{chapters[0].number}章-第{chapters[-1].number}章",
        "chapter_count": len(chapters),
        "word_distribution": {
            "average": round(avg_words),
            "max": max_words,
            "min": min_words,
            "consistency": "良好" if min_words > avg_words * 0.3 else "波动较大",
            "per_chapter": word_counts[:20],  # 最多显示20章
        },
        "plot_progress": {
            "total_points": plot_points_total,
            "done_points": plot_points_done,
            "completion_rate": round(plot_completion_rate, 1),
            "avg_points_per_chapter": round(avg_points_per_chapter, 2),
        },
        "pacing_issues": pacing_issues,
        "assessment": {
            "overall": (
                "节奏均匀" if len(pacing_issues) <= len(chapters) * 0.2
                else "节奏有波动" if len(pacing_issues) <= len(chapters) * 0.5
                else "节奏波动大，建议调整"
            ),
            "advice": (
                "可以考虑在长篇章节后安排过渡章节，保持读者阅读体验。"
                if len(pacing_issues) > 0
                else "当前节奏控制良好。"
            ),
        },
    }

    return analysis


def suggest_conflict_escalation(project_name: str, conflict_type: str = "",
                                 chapter_number: int = 0) -> dict:
    """建议冲突升级方案

    冲突类型：
    - character_vs_character: 角色冲突
    - character_vs_society: 角色 vs 社会/组织
    - character_vs_nature: 角色 vs 自然/环境
    - character_vs_self: 内在冲突
    - character_vs_fate: 角色 vs 命运/天道
    - character_vs_technology: 角色 vs 科技/系统
    """
    sm, pm, cm = _init_managers(project_name)

    plots = pm.track_plot_progress()
    chars = cm.list_characters()

    # 角色关系
    relationships = []
    for c in chars:
        for other_id, rel in c.relationships.items():
            other = cm.get_character(other_id)
            if other:
                relationships.append({
                    "from": c.name,
                    "from_role": c.role,
                    "to": other.name,
                    "to_role": other.role,
                    "type": rel.rel_type.value,
                    "description": rel.description,
                    "dynamics": rel.dynamics,
                })

    # 识别冲突关系
    conflict_relationships = [
        r for r in relationships
        if r["type"] in ("enemy", "rival", "nemesis")
        or r["from_role"] == "antagonist" or r["to_role"] == "antagonist"
    ]

    analysis = {
        "story_name": sm.get_story_status().get("name", ""),
        "conflict_type_requested": conflict_type or "all",
        "chapter_number": chapter_number,
        "current_conflicts": {
            "conflict_relationships": conflict_relationships,
            "protagonist_vs_antagonist": (
                "有明确对抗关系" if conflict_relationships else "对抗关系不明确"
            ),
        },
        "escalation_dimensions": [
            "个人层面：冲突从言语→行动→不可逆伤害逐步升级",
            "范围层面：从两人冲突→波及团队→影响世界格局",
            "情感层面：从理性分歧→情绪对抗→仇怨→不死不休",
            "代价层面：从小损失→牺牲→不可挽回的代价",
            "道德层面：从是非分明→灰色地带→正邪模糊",
        ],
        "escalation_techniques": {
            "character_vs_character": [
                "添加新的利益冲突点（资源、地位、理念）",
                "揭示隐藏的过往恩怨",
                "让第三方卷入，扩大冲突范围",
                "设置'只能活一个'的零和博弈",
            ],
            "character_vs_society": [
                "让制度/规则对主角施加更严厉的限制",
                "引入公众舆论压力",
                "安排主角的盟友因社会压力背叛",
                "让主角发现更大的制度性黑幕",
            ],
            "character_vs_self": [
                "让主角面临两个核心价值观的冲突",
                "设置'做正确的事'vs'保护重要的人'的两难",
                "让主角发现自己的过去是建立在谎言上",
                "引入成瘾/执念等内在困扰的升级",
            ],
            "character_vs_fate": [
                "让预言/命运的迹象越来越明显且不可逃避",
                "让主角为改变命运付出的代价越来越大",
                "揭示命运背后有更高意志在操纵",
            ],
        },
        "escalation_safety": {
            "note": "冲突升级应保证逻辑自洽，避免为冲突而冲突。每次升级都应有铺垫，让读者感觉'不可避免'而非'强行制造'。"
        },
    }

    return analysis


def brainstorm_world_building(project_name: str, aspect: str = "",
                               chapter_number: int = 0) -> dict:
    """构思世界观扩展方向

    分析当前世界设定的完整度，建议扩展方向：
    - 地理/地图扩展
    - 历史/传说/神话层
    - 社会结构/政治体系
    - 魔法/科技体系
    - 种族/文明
    - 经济/贸易
    """
    sm, pm, cm = _init_managers(project_name)

    from ..core import WorldManager
    wm = WorldManager(_get_project_path(project_name))
    wm.load()

    # 收集世界设定
    world = wm.get_world()
    locations = wm.get_world_summary() if hasattr(wm, 'get_world_summary') else ""
    rules = world.rules if world else []
    timeline_events = []  # WorldManager may not have get_all_events

    analysis = {
        "story_name": sm.get_story_status().get("name", ""),
        "aspect_requested": aspect or "all",
        "chapter_number": chapter_number,
        "current_world_state": {
            "world_name": world.world_name if world else "",
            "magic_system": world.magic_system[:200] if world and world.magic_system else "",
            "technology_level": world.technology_level[:200] if world and world.technology_level else "",
            "social_structure": world.social_structure[:200] if world and world.social_structure else "",
            "history": world.history[:200] if world and world.history else "",
            "location_count": len(world.locations) if world and world.locations else 0,
            "rule_count": len(world.rules) if world and world.rules else 0,
            "timeline_event_count": len(timeline_events),
        },
        "expansion_dimensions": {
            "geography": "扩展地图 — 新区域、隐藏地点、禁地、秘境",
            "history": "丰富历史 — 上古战争、文明兴衰、创世神话、隐藏纪元",
            "society": "社会结构 — 阶级/门派/家族/联盟、权力博弈、文化习俗",
            "magic_tech": "体系深化 — 力量等级/修炼体系、技术限制/代价、失传技艺",
            "races": "种族/文明 — 异族、古族、混血、非人智慧种族",
            "economy": "经济体系 — 资源分布、货币/贸易、稀缺物资争夺",
            "religion": "信仰体系 — 神祇、教会、教义冲突、无神论者",
            "ecology": "生态系统 — 灵兽/魔兽、天材地宝、环境与修炼的关系",
        },
        "prompts": {
            "geography": "如果把故事舞台扩大3倍，会自然出现哪些新地点？",
            "history": "当前世界最黑暗的一段历史是什么？为什么被掩盖了？",
            "society": "谁是这个世界的真正掌权者？表面和实际的权力结构有什么不同？",
            "magic_tech": "如果有人打破了力量体系的基本规则，会引发什么连锁反应？",
            "races": "如果主角遇到一个完全不了解人类习俗的智慧种族，会发生什么？",
        },
    }

    return analysis


def analyze_theme_consistency(project_name: str,
                               theme: str = "") -> dict:
    """分析主题一致性

    检查：
    - 各卷/章节是否围绕核心主题展开
    - 角色弧光是否与主题呼应
    - 是否有偏离主题的支线
    - 象征/意象的使用是否一致
    """
    sm, pm, cm = _init_managers(project_name)

    story = sm.get_story()
    if not story:
        return {"error": "故事未加载"}

    story_status = sm.get_story_status()

    # 卷主题
    volumes = sm.list_volumes()
    vol_themes = [
        {"number": v.number, "title": v.title, "theme": v.theme or "(未设定)"}
        for v in volumes
    ]

    # 角色弧光
    character_themes = []
    for c in cm.list_characters():
        evolution = cm.get_character_evolution(c.id)
        snapshots = evolution.get("snapshots", [])
        if snapshots:
            character_themes.append({
                "name": c.name,
                "role": c.role,
                "motivation": c.motivation,
                "snapshot_count": len(snapshots),
                "has_arc": any(
                    s.get("arc_progress") for s in snapshots
                    if isinstance(s, dict)
                ),
            })

    # 检查主题偏离
    theme_issues = []
    for v in volumes:
        if not v.theme:
            theme_issues.append({
                "type": "missing_volume_theme",
                "volume": v.number,
                "title": v.title,
                "issue": f"第{v.number}卷《{v.title}》未设定主题",
            })

    chars_without_motivation = [c for c in cm.list_characters()
                                if not c.motivation and c.role in ("protagonist", "antagonist")]
    if chars_without_motivation:
        theme_issues.append({
            "type": "missing_character_motivation",
            "characters": [c.name for c in chars_without_motivation],
            "issue": "核心角色缺少动机描述，主题表达将缺少载体",
        })

    # 剧情线主题
    all_plots = pm.track_plot_progress()
    plot_themes = [
        {"name": p["name"], "type": p["type"], "theme": p.get("theme", "(未设定)")}
        for p in all_plots
    ]

    analysis = {
        "story_name": story_status.get("name", ""),
        "story_theme": story.theme if hasattr(story, 'theme') and story.theme else "(未设定)",
        "requested_theme": theme,
        "chapters": story_status.get("total_chapters", 0),
        "volume_themes": vol_themes,
        "plot_themes": plot_themes,
        "character_themes": character_themes,
        "theme_issues": theme_issues,
        "overall_assessment": {
            "volumes_with_theme": len([v for v in vol_themes if v["theme"] != "(未设定)"]),
            "total_volumes": len(vol_themes),
            "issue_count": len(theme_issues),
        },
        "analysis_guide": {
            "step1": "检查核心主题是否在每一卷中有所体现",
            "step2": "确认主要角色的弧光是否服务于核心主题",
            "step3": "识别偏离主题的支线，决定是否调整或删除",
            "step4": "检查象征/意象的使用是否有始有终",
            "step5": "确保结局（如已规划）是主题的自然归宿",
        },
    }

    if theme:
        analysis["theme_focus"] = f"以「{theme}」为核心主题进行分析"

    return analysis


# ============================================================
# 规划笔记持久化（planning_notes 表 CRUD）
# ============================================================

def add_planning_note(project_name: str, title: str, category: str = "",
                      content: str = "", decisions: str = "",
                      related_tools: list[str] | None = None) -> dict:
    """保存一条规划分析笔记到数据库。

    规划模式下分析完成后应调用此工具持久化结论，
    避免对话压缩后分析结果丢失。

    Args:
        title: 笔记标题（如"第3卷节奏分析"）
        category: 分类标签（plot/character/world/pacing/theme/general）
        content: 分析正文
        decisions: 已做出的决策/结论
        related_tools: 关联的分析工具名列表
    """
    from ..storage.database import Database

    proj_path = _get_project_path(project_name)
    db = Database(str(Path(proj_path) / "wal.db"))
    db.init_schema()

    note_id = f"pn_{uuid.uuid4().hex[:8]}"
    now = datetime.now().isoformat()

    with db.get_conn() as conn:
        conn.execute(
            """INSERT INTO planning_notes (id, story_id, title, category,
               content, decisions, related_tools, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (note_id, "main", title, category, content, decisions,
             json.dumps(related_tools or [], ensure_ascii=False), now),
        )

    return {"id": note_id, "title": title, "category": category, "created_at": now}


def list_planning_notes(project_name: str, category: str = "",
                        limit: int = 20) -> list[dict]:
    """列出已保存的规划笔记摘要。

    Args:
        category: 可选，按分类过滤
        limit: 返回条数上限
    """
    from ..storage.database import Database

    proj_path = _get_project_path(project_name)
    db = Database(str(Path(proj_path) / "wal.db"))
    db.init_schema()

    with db.get_conn() as conn:
        if category:
            rows = conn.execute(
                "SELECT id, title, category, SUBSTR(content, 1, 150) as snippet, "
                "created_at FROM planning_notes "
                "WHERE story_id = 'main' AND category = ? ORDER BY created_at DESC LIMIT ?",
                (category, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, title, category, SUBSTR(content, 1, 150) as snippet, "
                "created_at FROM planning_notes "
                "WHERE story_id = 'main' ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [dict(r) for r in rows]


def get_planning_note(project_name: str, note_id: str) -> dict:
    """获取一条规划笔记的完整内容。

    Args:
        note_id: 笔记 ID（如 pn_a1b2c3d4）
    """
    from ..storage.database import Database

    proj_path = _get_project_path(project_name)
    db = Database(str(Path(proj_path) / "wal.db"))

    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM planning_notes WHERE id = ? AND story_id = 'main'",
            (note_id,),
        ).fetchone()

    if not row:
        return {"error": f"笔记 '{note_id}' 未找到"}

    result = dict(row)
    try:
        result["related_tools"] = json.loads(result.get("related_tools", "[]"))
    except (json.JSONDecodeError, TypeError):
        result["related_tools"] = []
    return result

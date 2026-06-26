"""Prompt 构建器 — 使用 Jinja2 模板渲染"""

from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, BaseLoader, Template


# 内置模板（当外部模板文件不存在时使用）
BUILTIN_TEMPLATES = {
    "novel_continue.j2": """你是一位专业的小说作家，正在续写小说《{{ story_name }}》。

## 故事背景
{{ story_summary }}

## 世界观
{{ world_summary }}

## 当前进度
{{ chapter_context }}

## 本章出场角色
{% for char in characters %}
- **{{ char.name }}**（{{ char.role }}）：{{ char.description }}
  动机：{{ char.motivation }}
  当前状态：{{ char.current_state }}
{% endfor %}

## 本章剧情任务
{% for plot in chapter_plots %}
- [{{ plot.type }}] {{ plot.name }}: {{ plot.task }}
{% endfor %}

## 写作要求
{{ writing_instructions | default("请续写本章内容，注意：") }}
1. 保持角色性格一致
2. 推进各剧情线的情节点
3. 注意场景之间的过渡
4. 字数目标：{{ target_words }}字

请开始写作：
""",

    "scene_draft.j2": """为以下场景撰写草稿：

## 场景信息
- 标题：{{ scene_title }}
- 地点：{{ location }}
- 时间：{{ time_point }}
- 出场角色：{{ characters_present }}
- 情绪基调：{{ emotional_tone }}

## 场景上下文
{{ context }}

## 本场景需要推进的剧情
{{ plot_advancements }}

请撰写本场景内容（约{{ target_words }}字）：
""",

    "plot_review.j2": """请审查以下小说内容的剧情一致性：

## 当前剧情线状态
{% for pl in plot_lines %}
### {{ pl.name }}（{{ pl.type }}）
完成度：{{ pl.progress }}%
未完成情节点：
{% for pp in pl.pending_points %}
  - {{ pp.title }}（安排在第{{ pp.chapter }}章）
{% endfor %}
{% endfor %}

## 最新章节内容
{{ recent_content }}

## 审查要点
1. 剧情逻辑是否连贯
2. 角色行为是否符合设定
3. 主线支线推进是否合理
4. 是否有未解决的伏笔需要处理

请给出审查意见：
""",

    "character_dialogue.j2": """审查以下角色对话，检查是否符合角色性格：

## 角色档案
{% for char in characters %}
- **{{ char.name }}**：{{ char.personality }}
  说话风格：{{ char.speech_style | default("未设定") }}
{% endfor %}

## 对话内容
{{ dialogue }}

请分析：
1. 对话是否符合角色性格
2. 语气是否一致
3. 改进建议
""",
}


class PromptBuilder:
    """管理 Prompt 模板并渲染"""

    def __init__(self, template_dir: str | None = None):
        if template_dir and Path(template_dir).exists():
            self.env = Environment(loader=FileSystemLoader(template_dir))
        else:
            self.env = Environment(loader=BaseLoader())
        self._cache: dict[str, Template] = {}

    def _get_template(self, name: str) -> Template:
        """获取模板（优先文件，回退到内置）"""
        if name not in self._cache:
            try:
                self._cache[name] = self.env.get_template(name)
            except Exception:
                source = BUILTIN_TEMPLATES.get(name, "")
                self._cache[name] = self.env.from_string(source)
        return self._cache[name]

    def render(self, template_name: str, **kwargs) -> str:
        """渲染模板"""
        template = self._get_template(template_name)
        return template.render(**kwargs)

    def build_continue_prompt(self, **kwargs) -> str:
        """构建续写提示词"""
        return self.render("novel_continue.j2", **kwargs)

    def build_scene_prompt(self, **kwargs) -> str:
        """构建场景草稿提示词"""
        return self.render("scene_draft.j2", **kwargs)

    def build_review_prompt(self, **kwargs) -> str:
        """构建剧情审查提示词"""
        return self.render("plot_review.j2", **kwargs)

    def build_dialogue_review_prompt(self, **kwargs) -> str:
        """构建角色对话审查提示词"""
        return self.render("character_dialogue.j2", **kwargs)

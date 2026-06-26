"""故事、章节、场景数据模型 — 支持 部(Part)/卷(Volume)/章(Chapter) 三级结构"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class StoryStatus(str, Enum):
    PLANNING = "planning"
    WRITING = "writing"
    COMPLETED = "completed"
    PAUSED = "paused"


class Scene(BaseModel):
    """场景"""
    id: str = Field(default="", description="场景唯一ID")
    title: str = Field(default="", description="场景标题")
    location_id: str = Field(default="", description="发生地点ID")
    time_point: str = Field(default="", description="故事内时间点描述")
    characters_present: list[str] = Field(default_factory=list, description="出场角色ID列表")
    content: str = Field(default="", description="场景正文")
    plot_advancements: list[str] = Field(default_factory=list, description="推进的情节点ID")
    notes: str = Field(default="", description="作者备注")
    word_count: int = Field(default=0, description="字数")


class Chapter(BaseModel):
    """章节"""
    id: str = Field(default="", description="章节唯一ID（如 ch_0001）")
    volume_id: str = Field(default="", description="所属卷ID")
    number: int = Field(default=0, description="章节序号")
    title: str = Field(default="", description="章节标题")
    status: str = Field(default="draft", description="状态: draft/writing/done")
    summary: str = Field(default="", description="本章摘要")
    word_count_target: int = Field(default=3000, description="目标字数")
    scenes: list[Scene] = Field(default_factory=list, description="场景列表")
    plot_points_involved: list[str] = Field(default_factory=list, description="涉及的情节点ID")
    character_appearances: dict[str, str] = Field(
        default_factory=dict, description="角色ID → 本章作用"
    )
    notes: str = Field(default="", description="章节备注")
    actual_word_count: int = Field(default=0, description="实际字数")


class Volume(BaseModel):
    """卷 — 章节的上级容器"""
    id: str = Field(default="", description="卷唯一ID（如 vol_001）")
    part_id: str = Field(default="", description="所属部ID，顶级卷为空")
    number: int = Field(default=0, description="卷序号（可跨部连续或部内独立）")
    title: str = Field(default="", description="卷标题")
    summary: str = Field(default="", description="卷摘要")
    theme: str = Field(default="", description="卷主题")
    status: str = Field(default="planning", description="状态: planning/writing/completed")
    notes: str = Field(default="", description="备注")
    chapters: list[Chapter] = Field(default_factory=list, description="包含的章节")


class Part(BaseModel):
    """部/篇 — 卷的上级容器，最大层级"""
    id: str = Field(default="", description="部唯一ID（如 part_001）")
    number: int = Field(default=0, description="部序号")
    title: str = Field(default="", description="部标题")
    summary: str = Field(default="", description="部摘要")
    notes: str = Field(default="", description="备注")
    volumes: list[Volume] = Field(default_factory=list, description="包含的卷")


class Story(BaseModel):
    """故事 — 顶级模型"""
    name: str = Field(default="", description="故事名称")
    author: str = Field(default="", description="作者")
    summary: str = Field(default="", description="故事梗概")
    genre: str = Field(default="", description="类型/流派")
    tags: list[str] = Field(default_factory=list, description="标签")
    status: StoryStatus = Field(default=StoryStatus.PLANNING, description="故事状态")
    parts: list[Part] = Field(default_factory=list, description="部/篇列表（三级结构顶层）")
    chapters: list[Chapter] = Field(default_factory=list, description="章节列表（向后兼容，优先使用 parts→volumes→chapters）")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="创建时间")
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="更新时间")
    notes: str = Field(default="", description="全局备注")

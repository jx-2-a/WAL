"""世界观、地点、时间线模型"""

from typing import Optional

from pydantic import BaseModel, Field


class Location(BaseModel):
    """地点"""
    id: str = Field(default="", description="地点唯一ID")
    name: str = Field(default="", description="地点名称")
    description: str = Field(default="", description="地点描述")
    location_type: str = Field(default="", description="类型: city/building/room/wilderness/realm/dungeon")
    parent_location: str = Field(default="", description="上级地点ID（层级结构）")
    atmosphere: str = Field(default="", description="氛围描述")
    notable_features: list[str] = Field(default_factory=list, description="显著特征")
    related_characters: list[str] = Field(default_factory=list, description="关联角色ID")


class WorldRule(BaseModel):
    """世界规则"""
    name: str = Field(default="", description="规则名称")
    description: str = Field(default="", description="规则描述")
    category: str = Field(default="", description="分类: magic/technology/social/nature/law")


class WorldSetting(BaseModel):
    """世界观设定"""
    world_name: str = Field(default="", description="世界名称")
    description: str = Field(default="", description="世界概述")
    magic_system: str = Field(default="", description="魔法/力量体系")
    technology_level: str = Field(default="", description="科技水平")
    social_structure: str = Field(default="", description="社会结构")
    history: str = Field(default="", description="世界历史")
    races: list[str] = Field(default_factory=list, description="种族列表")
    factions: list[str] = Field(default_factory=list, description="势力列表")
    rules: list[WorldRule] = Field(default_factory=list, description="世界规则")
    locations: list[Location] = Field(default_factory=list, description="地点列表")
    notes: str = Field(default="", description="备注")


class TimelineEvent(BaseModel):
    """故事时间线事件"""
    id: str = Field(default="", description="事件唯一ID")
    title: str = Field(default="", description="事件标题")
    description: str = Field(default="", description="事件描述")
    time_point: str = Field(default="", description="故事内时间点（如：'第一章前三年'）")
    related_chapters: list[int] = Field(default_factory=list, description="关联章节序号")
    related_characters: list[str] = Field(default_factory=list, description="关联角色ID")
    is_backstory: bool = Field(default=False, description="是否前史/回忆")
    causes: list[str] = Field(default_factory=list, description="前因事件ID")
    effects: list[str] = Field(default_factory=list, description="后果事件ID")

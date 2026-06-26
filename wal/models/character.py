"""角色与关系模型"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RelationType(str, Enum):
    FRIEND = "friend"
    ENEMY = "enemy"
    LOVER = "lover"
    FAMILY = "family"
    RIVAL = "rival"
    MENTOR = "mentor"
    COLLEAGUE = "colleague"
    STRANGER = "stranger"
    OTHER = "other"


class Relationship(BaseModel):
    """角色关系"""
    character_a: str = Field(default="", description="角色A的ID")
    character_b: str = Field(default="", description="角色B的ID")
    rel_type: RelationType = Field(default=RelationType.OTHER, description="关系类型")
    description: str = Field(default="", description="关系描述")
    dynamics: str = Field(default="", description="关系动态变化（如何演变）")
    history: str = Field(default="", description="关系历史")


class CharacterSnapshot(BaseModel):
    """角色快照 — 在指定章节的角色状态记录"""
    id: str = Field(default="", description="快照唯一ID（如 snap_char_001_5）")
    character_id: str = Field(default="", description="所属角色ID")
    chapter_number: int = Field(default=0, description="章节号")
    chapter_title: str = Field(default="", description="章节标题")
    arc_progress: str = Field(default="", description="弧光进度描述")
    personality_changes: str = Field(default="", description="性格变化（如'变得更多疑'）")
    appearance_changes: str = Field(default="", description="外貌变化")
    new_abilities: list[str] = Field(default_factory=list, description="新获得的能力/技能")
    lost_abilities: list[str] = Field(default_factory=list, description="失去的能力/技能")
    key_relationships_changed: dict[str, str] = Field(
        default_factory=dict, description="关系变化，key=对方角色名, value=变化描述"
    )
    internal_state: str = Field(default="", description="内心状态描述")
    summary: str = Field(default="", description="本章角色总结")
    created_at: str = Field(default="", description="创建时间")


class Character(BaseModel):
    """角色"""
    id: str = Field(default="", description="角色唯一ID")
    name: str = Field(default="", description="角色姓名")
    aliases: list[str] = Field(default_factory=list, description="别名/称号")
    role: str = Field(default="supporting", description="角色定位: protagonist/antagonist/supporting/minor")
    gender: str = Field(default="", description="性别")
    age: str = Field(default="", description="年龄（可为范围或描述）")
    appearance: str = Field(default="", description="外貌描述")
    personality_traits: list[str] = Field(default_factory=list, description="性格特征")
    background_story: str = Field(default="", description="背景故事")
    motivation: str = Field(default="", description="核心动机")
    arc_description: str = Field(default="", description="角色弧光描述（从状态A到状态B）")
    arc_progress: str = Field(default="", description="弧光当前进度")
    abilities: list[str] = Field(default_factory=list, description="能力/技能")
    weaknesses: list[str] = Field(default_factory=list, description="弱点/缺陷")
    relationships: dict[str, Relationship] = Field(
        default_factory=dict, description="与其他角色关系，key=对方角色ID"
    )
    snapshots: list[CharacterSnapshot] = Field(
        default_factory=list, description="角色快照列表（按章节）"
    )
    first_appearance: str = Field(default="", description="首次出场章节")
    notes: str = Field(default="", description="备注")

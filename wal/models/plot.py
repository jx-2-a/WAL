"""剧情线、情节点、交汇点模型"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PlotType(str, Enum):
    MAIN = "main"
    SUB = "sub"


class PlotLevel(str, Enum):
    """剧情层级 — 主线/卷主线/支线/角色弧光"""
    MAIN = "main"
    VOLUME = "volume"
    SUB = "sub"
    CHARACTER_ARC = "character_arc"


class PlotLineStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class PlotPointStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class ForeshadowingStatus(str, Enum):
    """伏笔状态"""
    PENDING = "pending"
    PARTIALLY_RESOLVED = "partially_resolved"
    RESOLVED = "resolved"
    ABANDONED = "abandoned"


class PlotIntersection(BaseModel):
    """剧情交汇点 — 两条剧情线在何处交汇"""
    plot_a: str = Field(default="", description="剧情线A ID")
    plot_b: str = Field(default="", description="剧情线B ID")
    at_plot_point_a: str = Field(default="", description="剧情线A的哪个情节点发生交汇")
    at_plot_point_b: str = Field(default="", description="剧情线B的哪个情节点发生交汇")
    description: str = Field(default="", description="交汇方式描述")
    chapter_hint: int = Field(default=0, description="建议在第几章发生交汇")


class PlotPoint(BaseModel):
    """情节点 — 剧情线上的一个节点"""
    id: str = Field(default="", description="情节点唯一ID")
    title: str = Field(default="", description="情节点标题")
    description: str = Field(default="", description="情节点详细描述")
    order_index: int = Field(default=0, description="在剧情线中的序号")
    chapter_assigned: int = Field(default=0, description="分配到的章节号")
    status: PlotPointStatus = Field(default=PlotPointStatus.PENDING, description="完成状态")
    prerequisites: list[str] = Field(default_factory=list, description="前置情节点ID列表")
    impacts_characters: list[str] = Field(default_factory=list, description="影响到的角色ID")
    emotional_tone: str = Field(default="", description="情绪基调: 紧张/温馨/悲伤/激昂/悬疑/轻松")
    estimated_words: int = Field(default=0, description="预计占用字数")
    notes: str = Field(default="", description="备注")


class PlotLine(BaseModel):
    """剧情线 — 主线或支线，支持层级嵌套"""
    id: str = Field(default="", description="剧情线唯一ID")
    name: str = Field(default="", description="剧情线名称")
    plot_type: PlotType = Field(default=PlotType.SUB, description="主线/支线")
    level: PlotLevel = Field(default=PlotLevel.SUB, description="剧情层级：main/volume/sub/character_arc")
    parent_id: str = Field(default="", description="父剧情线ID（空表示顶级）")
    description: str = Field(default="", description="剧情线简述")
    theme: str = Field(default="", description="主题")
    plot_points: list[PlotPoint] = Field(default_factory=list, description="情节点列表（有序）")
    status: PlotLineStatus = Field(default=PlotLineStatus.ACTIVE, description="剧情线状态")
    intersects_with: list[PlotIntersection] = Field(
        default_factory=list, description="与其他剧情线的交汇点"
    )
    started_in_chapter: int = Field(default=1, description="起始章节")
    target_chapter: int = Field(default=0, description="计划收束章节")
    notes: str = Field(default="", description="备注")

    def progress_percent(self) -> float:
        """计算剧情线完成百分比"""
        if not self.plot_points:
            return 100.0 if self.status == PlotLineStatus.COMPLETED else 0.0
        done = sum(1 for p in self.plot_points if p.status == PlotPointStatus.DONE)
        return round(done / len(self.plot_points) * 100, 1)

    def dangling(self) -> bool:
        """是否未收束（活跃但情节点未全部完成）"""
        return self.status == PlotLineStatus.ACTIVE and self.progress_percent() < 100.0


class Foreshadowing(BaseModel):
    """伏笔 — 在故事中提前埋下的线索或暗示"""
    id: str = Field(default="", description="伏笔唯一ID（如 fw_001）")
    story_id: str = Field(default="main", description="所属故事ID")
    description: str = Field(default="", description="伏笔描述")
    created_at_chapter: int = Field(default=0, description="埋设章节号")
    created_at_volume: int = Field(default=0, description="埋设卷号")
    target_chapter: int = Field(default=0, description="计划回收章节号")
    resolved_at_chapter: int = Field(default=0, description="实际回收章节号")
    status: ForeshadowingStatus = Field(
        default=ForeshadowingStatus.PENDING, description="状态：pending/partially_resolved/resolved/abandoned"
    )
    urgency: str = Field(default="medium", description="紧急程度：low/medium/high/critical")
    related_plot_lines: list[str] = Field(default_factory=list, description="关联剧情线ID")
    related_characters: list[str] = Field(default_factory=list, description="关联角色ID")
    resolution_notes: str = Field(default="", description="回收说明")
    notes: str = Field(default="", description="备注")

    def is_resolved(self) -> bool:
        return self.status == ForeshadowingStatus.RESOLVED

    def is_dangling(self) -> bool:
        return self.status in (ForeshadowingStatus.PENDING, ForeshadowingStatus.PARTIALLY_RESOLVED)

    def age_in_chapters(self, current_chapter: int) -> int:
        """伏笔已埋的章节数"""
        if self.created_at_chapter > 0 and current_chapter > 0:
            return current_chapter - self.created_at_chapter
        return 0

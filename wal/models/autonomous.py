"""自主模式模型 — 自主决策、检查点、自治等级"""

from enum import Enum

from pydantic import BaseModel, Field


class AutonomyLevel(str, Enum):
    """自主等级

    - SUGGEST_ONLY: 只提建议，不执行任何修改
    - AUTO_MINOR: 可自动执行小修改（情节点状态更新、快照创建）
    - AUTO_MODERATE: 可自动写场景内容、添加角色/章节
    - FULL_AUTO: 完全自主，包括批量写作和剧情推进
    """
    SUGGEST_ONLY = "suggest_only"
    AUTO_MINOR = "auto_minor"
    AUTO_MODERATE = "auto_moderate"
    FULL_AUTO = "full_auto"


class DecisionImpact(str, Enum):
    """决策影响级别"""
    MINOR = "minor"             # 微小改动（状态更新、索引）
    MODERATE = "moderate"        # 中等改动（场景内容、角色快照）
    MAJOR = "major"              # 重大改动（新增章节、角色关系变化）
    CRITICAL = "critical"        # 关键改动（剧情线变更、卷结构调整）


class AutoDecision(BaseModel):
    """自主决策记录

    每次 Agent 做出自主决策时，都会记录一条决策。
    根据 autonomy_level，某些决策需要用户审批后才执行。
    """
    id: str = Field(default="", description="决策唯一ID，如 ad_001")
    story_id: str = Field(default="main", description="所属故事ID")
    timestamp: str = Field(default="", description="决策时间（ISO 格式）")
    decision_type: str = Field(default="", description="决策类型：write_scene / update_status / add_chapter / ...")
    description: str = Field(default="", description="决策描述")
    reasoning: str = Field(default="", description="决策推理过程")
    impact_level: DecisionImpact = Field(default=DecisionImpact.MINOR, description="影响级别")
    affected_elements: list[str] = Field(default_factory=list, description="受影响的元素ID列表")
    approved: bool = Field(default=False, description="是否已审批")

    def approval_required(self, current_level: "AutonomyLevel") -> bool:
        """根据当前自主等级判断是否需要审批"""
        level_map = {
            AutonomyLevel.SUGGEST_ONLY: [DecisionImpact.MINOR, DecisionImpact.MODERATE, DecisionImpact.MAJOR, DecisionImpact.CRITICAL],
            AutonomyLevel.AUTO_MINOR: [DecisionImpact.MODERATE, DecisionImpact.MAJOR, DecisionImpact.CRITICAL],
            AutonomyLevel.AUTO_MODERATE: [DecisionImpact.MAJOR, DecisionImpact.CRITICAL],
            AutonomyLevel.FULL_AUTO: [DecisionImpact.CRITICAL],
        }
        return self.impact_level in level_map.get(current_level, [])


class Checkpoint(BaseModel):
    """数据库检查点

    检查点是 wal.db 文件的副本，存储在 checkpoints/ 子目录下。
    """
    label: str = Field(default="", description="检查点标签")
    filename: str = Field(default="", description="db 文件名，如 checkpoints/chk_001.db")
    created_at: str = Field(default="", description="创建时间")
    chapter_number: int = Field(default=0, description="创建时的章节号")
    description: str = Field(default="", description="检查点描述")


class AutonomousState(BaseModel):
    """自主模式运行状态"""
    is_running: bool = Field(default=False, description="是否正在自主运行")
    level: AutonomyLevel = Field(default=AutonomyLevel.SUGGEST_ONLY, description="当前自主等级")
    direction: str = Field(default="", description="自主写作方向/目标")
    session_start_chapter: int = Field(default=0, description="本次自主会话开始的章节号")
    chapters_written: int = Field(default=0, description="已写入的章节数")
    decisions_total: int = Field(default=0, description="总决策数")
    decisions_approved: int = Field(default=0, description="已审批决策数")
    last_decision_at: str = Field(default="", description="最后一次决策时间")

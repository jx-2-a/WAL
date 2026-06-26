"""自主模式工具函数 — 供 AI Agent 在自主模式下调用

10 个工具：检查点管理、自主等级、决策审批、会话控制
"""

import os
from pathlib import Path
from typing import Optional


def _get_project_path(name: str) -> str:
    base = Path(os.environ.get("WAL_PROJECTS", "projects"))
    return str(base / name)


def _get_auto_manager(project_name: str):
    """初始化 AutoManager"""
    from ..core.auto_manager import AutoManager
    proj = _get_project_path(project_name)
    return AutoManager(proj)


# ============================================================
# 自主模式工具 — 10 个
# ============================================================

def set_autonomy_level(project_name: str, level: str) -> dict:
    """设置自主等级"""
    from ..models.autonomous import AutonomyLevel
    am = _get_auto_manager(project_name)
    try:
        al = AutonomyLevel(level)
    except ValueError:
        valid = [e.value for e in AutonomyLevel]
        return {"error": f"无效的自主等级 '{level}'，有效值: {valid}"}
    return am.set_level(al)


def set_direction(project_name: str, direction: str) -> dict:
    """设置自主写作方向/目标"""
    am = _get_auto_manager(project_name)
    return am.set_direction(direction)


def start_auto_session(project_name: str, direction: str = "",
                       chapter_start: int = 0) -> dict:
    """开始自主会话"""
    am = _get_auto_manager(project_name)
    return am.start_auto_session(direction=direction, chapter_start=chapter_start)


def end_auto_session(project_name: str) -> dict:
    """结束自主会话"""
    am = _get_auto_manager(project_name)
    return am.end_auto_session()


def create_checkpoint(project_name: str, label: str,
                      description: str = "",
                      chapter_number: int = 0) -> dict:
    """创建数据库检查点"""
    am = _get_auto_manager(project_name)
    return am.create_checkpoint(label, description=description,
                                chapter_number=chapter_number)


def rollback_to_checkpoint(project_name: str, label: str) -> dict:
    """回滚到指定检查点"""
    am = _get_auto_manager(project_name)
    return am.rollback_to_checkpoint(label)


def list_checkpoints(project_name: str) -> list[dict]:
    """列出所有检查点"""
    am = _get_auto_manager(project_name)
    return am.list_checkpoints()


def approve_decision(project_name: str, decision_id: str) -> dict:
    """审批通过一条自主决策"""
    am = _get_auto_manager(project_name)
    return am.approve_decision(decision_id)


def reject_decision(project_name: str, decision_id: str) -> dict:
    """拒绝一条自主决策"""
    am = _get_auto_manager(project_name)
    return am.reject_decision(decision_id)


def get_auto_status(project_name: str) -> dict:
    """获取自主模式当前状态"""
    am = _get_auto_manager(project_name)
    status = am.get_status()

    # 附加待审批决策
    pending = am.list_pending_decisions()
    status["pending_decisions_list"] = pending[:10]

    # 检查点数量
    checkpoints = am.list_checkpoints()
    status["checkpoint_count"] = len(checkpoints)

    return status

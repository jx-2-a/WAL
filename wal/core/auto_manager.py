"""自主模式管理器 — 检查点、自主等级、决策审批

AutoManager 封装了自主模式的所有业务逻辑：
- 检查点（数据库快照）：创建、回滚、列出、删除
- 自主等级：设置和读取 autonomy_level
- 决策管理：记录决策、审批/拒绝、统计
- 自主会话：开始/结束、状态追踪
"""

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..models.autonomous import (
    AutonomyLevel, AutoDecision, DecisionImpact,
    AutonomousState, Checkpoint,
)
from ..storage.auto_repo import AutoRepository
from ..storage.database import Database


class AutoManager:
    """自主模式管理器"""

    def __init__(self, project_dir: str):
        self.project_dir = Path(project_dir)
        self.project_dir.mkdir(parents=True, exist_ok=True)

        db_path = self.project_dir / "wal.db"
        self.db = Database(str(db_path))
        self.repo = AutoRepository(self.db)

        # 检查点目录
        self.checkpoints_dir = self.project_dir / "checkpoints"
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

    # ═══ 检查点系统 ═════════════════════════════════════════════════

    def create_checkpoint(self, label: str, description: str = "",
                          chapter_number: int = 0) -> dict:
        """创建数据库检查点 — 复制 wal.db 到 checkpoints/ 目录"""
        src = self.project_dir / "wal.db"
        if not src.exists():
            return {"error": "数据库文件不存在，无法创建检查点"}

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_label = "".join(c for c in label if c.isalnum() or c in "_-")
        filename = f"chk_{timestamp}_{safe_label}.db"
        dst = self.checkpoints_dir / filename

        shutil.copy2(str(src), str(dst))

        checkpoint = {
            "label": label,
            "filename": f"checkpoints/{filename}",
            "created_at": datetime.now().isoformat(),
            "chapter_number": chapter_number,
            "description": description,
        }

        # 持久化检查点元数据
        self.repo.set_config(
            f"checkpoint_{label}",
            f"{checkpoint['created_at']}|{checkpoint['filename']}|{chapter_number}|{description}"
        )

        return checkpoint

    def rollback_to_checkpoint(self, label: str) -> dict:
        """回滚到指定检查点 — 用检查点文件覆盖当前 wal.db"""
        # 查找检查点文件
        checkpoints = self._scan_checkpoints()
        target = None
        for cp in checkpoints:
            if cp["label"] == label:
                target = cp
                break

        if not target:
            return {"error": f"检查点 '{label}' 未找到"}

        src = self.project_dir / target["filename"]
        if not src.exists():
            return {"error": f"检查点文件不存在: {target['filename']}"}

        dst = self.project_dir / "wal.db"

        # 先创建一个自动检查点作为回退
        auto_label = f"auto_before_rollback_to_{label}"
        self.create_checkpoint(auto_label, f"回滚到 {label} 之前自动保存")

        # 执行回滚
        shutil.copy2(str(src), str(dst))

        return {
            "rolled_back_to": label,
            "checkpoint_file": target["filename"],
            "auto_backup": f"checkpoints/chk_*_auto_before_rollback_to_{label}.db",
        }

    def list_checkpoints(self) -> list[dict]:
        """列出所有检查点"""
        return self._scan_checkpoints()

    def delete_checkpoint(self, label: str) -> dict:
        """删除指定检查点"""
        checkpoints = self._scan_checkpoints()
        for cp in checkpoints:
            if cp["label"] == label:
                path = self.project_dir / cp["filename"]
                if path.exists():
                    os.remove(str(path))
                self.repo.set_config(f"checkpoint_{label}", "")
                return {"deleted": label, "filename": cp["filename"]}
        return {"error": f"检查点 '{label}' 未找到"}

    def _scan_checkpoints(self) -> list[dict]:
        """扫描 checkpoints/ 目录和配置中的检查点"""
        result = []

        # 从配置中读取
        all_config = self.repo.get_all_config()
        for key, value in all_config.items():
            if key.startswith("checkpoint_") and value:
                parts = value.split("|", 3)
                if len(parts) >= 2:
                    label = key[len("checkpoint_"):]
                    cp = {
                        "label": label,
                        "created_at": parts[0],
                        "filename": parts[1],
                        "chapter_number": int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0,
                        "description": parts[3] if len(parts) > 3 else "",
                    }
                    # 验证文件存在
                    if (self.project_dir / cp["filename"]).exists():
                        result.append(cp)

        # 按时间倒序
        result.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return result

    # ═══ 自主等级 ═══════════════════════════════════════════════════

    def set_level(self, level: AutonomyLevel) -> dict:
        """设置自主等级"""
        self.repo.set_config("autonomy_level", level.value)
        return {"autonomy_level": level.value}

    def get_level(self) -> AutonomyLevel:
        """获取当前自主等级"""
        value = self.repo.get_config("autonomy_level", "suggest_only")
        try:
            return AutonomyLevel(value)
        except ValueError:
            return AutonomyLevel.SUGGEST_ONLY

    # ═══ 自主方向 ═══════════════════════════════════════════════════

    def set_direction(self, direction: str) -> dict:
        """设置自主写作方向/目标"""
        self.repo.set_config("auto_direction", direction)
        return {"direction": direction}

    def get_direction(self) -> str:
        """获取自主写作方向"""
        return self.repo.get_config("auto_direction", "")

    # ═══ 决策管理 ═══════════════════════════════════════════════════

    def record_decision(self, decision_type: str, description: str,
                        reasoning: str = "",
                        impact_level: DecisionImpact = DecisionImpact.MINOR,
                        affected_elements: list[str] | None = None) -> AutoDecision:
        """记录一条自主决策"""
        now = datetime.now().isoformat()

        # 生成决策ID
        stats = self.repo.get_decision_stats()
        count = stats["total"] + 1
        decision_id = f"ad_{count:04d}"

        decision = AutoDecision(
            id=decision_id,
            timestamp=now,
            decision_type=decision_type,
            description=description,
            reasoning=reasoning,
            impact_level=impact_level,
            affected_elements=affected_elements or [],
            approved=False,
        )

        self.repo.save_decision(decision.model_dump(mode="json"))
        return decision

    def approve_decision(self, decision_id: str) -> dict:
        """审批通过决策"""
        decision = self.repo.get_decision(decision_id)
        if not decision:
            return {"error": f"决策 '{decision_id}' 未找到"}

        self.repo.approve_decision(decision_id)
        return {"decision_id": decision_id, "approved": True}

    def reject_decision(self, decision_id: str) -> dict:
        """拒绝决策"""
        decision = self.repo.get_decision(decision_id)
        if not decision:
            return {"error": f"决策 '{decision_id}' 未找到"}

        self.repo.reject_decision(decision_id)
        return {"decision_id": decision_id, "approved": False}

    def list_pending_decisions(self) -> list[dict]:
        """列出待审批的决策"""
        return self.repo.list_pending_decisions()

    def get_decision_stats(self) -> dict:
        """获取决策统计"""
        return self.repo.get_decision_stats()

    def recent_decisions(self, limit: int = 20) -> list[dict]:
        """获取最近的决策"""
        return self.repo.list_decisions(limit=limit)

    # ═══ 自主会话 ═══════════════════════════════════════════════════

    def start_auto_session(self, direction: str = "",
                           chapter_start: int = 0) -> dict:
        """开始自主会话"""
        self.repo.set_config("auto_running", "true")
        self.repo.set_config("auto_session_chapter", str(chapter_start))
        self.repo.set_config("auto_chapters_written", "0")
        if direction:
            self.set_direction(direction)

        return {
            "status": "started",
            "autonomy_level": self.get_level().value,
            "direction": self.get_direction(),
            "chapter_start": chapter_start,
        }

    def end_auto_session(self) -> dict:
        """结束自主会话"""
        stats = self.repo.get_decision_stats()
        direction = self.get_direction()

        # 重置会话状态
        self.repo.set_config("auto_running", "false")
        self.repo.set_config("auto_session_chapter", "0")
        self.repo.set_config("auto_chapters_written", "0")

        return {
            "status": "ended",
            "decisions_total": stats["total"],
            "decisions_approved": stats["approved_count"],
            "direction": direction,
        }

    def get_status(self) -> dict:
        """获取自主模式当前状态"""
        level = self.get_level()
        is_running = self.repo.get_config("auto_running", "false") == "true"
        direction = self.get_direction()
        stats = self.repo.get_decision_stats()

        session_chapter = self.repo.get_config("auto_session_chapter", "0")
        chapters_written = self.repo.get_config("auto_chapters_written", "0")

        return {
            "is_running": is_running,
            "autonomy_level": level.value,
            "direction": direction,
            "session_start_chapter": int(session_chapter) if session_chapter.isdigit() else 0,
            "chapters_written": int(chapters_written) if chapters_written.isdigit() else 0,
            "decisions_total": stats["total"],
            "decisions_approved": stats["approved_count"],
            "pending_decisions": stats["pending_count"],
            "critical_pending": stats["critical_pending"],
        }

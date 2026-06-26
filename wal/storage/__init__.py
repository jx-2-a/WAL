"""WAL 存储层 — SQLite 为主，YAML 为备份

核心类:
- Database: SQLite 数据库连接管理 + 架构初始化
- DatabaseRepository: SQLite 通用仓库基类
- StoryRepository / CharacterRepository / PlotRepository / WorldRepository: 业务仓库
- IndexRepository: FTS5 全文搜索 + 索引
- AutoRepository: 自主模式决策日志 + Agent 配置 + 检查点

已弃用（保留用于 YAML 导入/导出）:
- BaseRepository: 原 YAML 文件级存储基类
"""

from .database import Database
from .db_repo import DatabaseRepository
from .story_repo import StoryRepository
from .char_repo import CharacterRepository
from .plot_repo import PlotRepository
from .world_repo import WorldRepository
from .index_repo import IndexRepository
from .auto_repo import AutoRepository

# 保留原 YAML 基类，标记为弃用（用于迁移和导出）
from .repo import BaseRepository  # noqa: F401 — deprecated, kept for YAML import/export

__all__ = [
    "Database",
    "DatabaseRepository",
    "StoryRepository",
    "CharacterRepository",
    "PlotRepository",
    "WorldRepository",
    "IndexRepository",
    "AutoRepository",
    "BaseRepository",  # deprecated
]

"""WAL 存储层 — SQLite 持久化

核心类:
- Database: SQLite 数据库连接管理 + 架构初始化
- DatabaseRepository: SQLite 通用仓库基类
- StoryRepository / CharacterRepository / PlotRepository / WorldRepository: 业务仓库
- IndexRepository: FTS5 全文搜索 + 索引
- AutoRepository: 自主模式决策日志 + Agent 配置 + 检查点
"""

from .connection import Database
from .base import DatabaseRepository
from .story import StoryRepository
from .character import CharacterRepository
from .plot import PlotRepository
from .world import WorldRepository
from .index import IndexRepository
from .autonomous import AutoRepository

__all__ = [
    "Database",
    "DatabaseRepository",
    "StoryRepository",
    "CharacterRepository",
    "PlotRepository",
    "WorldRepository",
    "IndexRepository",
    "AutoRepository",
]

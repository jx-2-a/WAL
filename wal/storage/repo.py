"""基础仓库接口"""

import os
from pathlib import Path
from typing import Optional, TypeVar

import yaml

T = TypeVar("T")


class BaseRepository:
    """YAML 文件持久化的基础仓库"""

    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _filepath(self, filename: str) -> Path:
        return self.base_dir / filename

    def _read_yaml(self, filename: str) -> Optional[dict]:
        """读取 YAML 文件，返回字典或 None"""
        filepath = self._filepath(filename)
        if not filepath.exists():
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if data else {}

    def _write_yaml(self, filename: str, data: dict) -> None:
        """将字典写入 YAML 文件"""
        filepath = self._filepath(filename)
        with open(filepath, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    def _exists(self, filename: str) -> bool:
        return self._filepath(filename).exists()

    def _delete(self, filename: str) -> None:
        filepath = self._filepath(filename)
        if filepath.exists():
            filepath.unlink()

    def _list_files(self, pattern: str = "*.yaml") -> list[str]:
        """列出匹配的文件名"""
        return [p.name for p in self.base_dir.glob(pattern)]

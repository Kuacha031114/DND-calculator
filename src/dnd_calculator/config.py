"""v3 配置位置、原子保存与损坏恢复。"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

CONFIG_VERSION = 1


def user_config_dir(platform: str | None = None, environ: Mapping[str, str] | None = None) -> Path:
    platform = platform or sys.platform
    environ = environ or os.environ
    if platform == "win32":
        base = Path(environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "池中社" / "DND战斗计算器"
    if platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "池中社 DND战斗计算器"
    base = Path(environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "chizhong-dnd-calculator"


@dataclass(frozen=True)
class ConfigLoadResult:
    data: dict[str, Any]
    warning: str = ""


class ConfigStore:
    def __init__(self, directory: Path | None = None):
        self.directory = directory or user_config_dir()
        self.path = self.directory / "config-v3.json"

    def load(self) -> ConfigLoadResult:
        if not self.path.exists():
            return ConfigLoadResult({"config_version": CONFIG_VERSION})
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, dict):
                raise ValueError("配置根节点不是对象")
            if data.get("config_version") != CONFIG_VERSION:
                return ConfigLoadResult(
                    {"config_version": CONFIG_VERSION},
                    "配置版本不受支持，已使用 v3 默认设置。",
                )
            return ConfigLoadResult(data)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = self.path.with_name(f"config-v3.corrupt-{stamp}.json")
            warning = f"配置损坏，已恢复默认设置：{exc}"
            try:
                self.path.replace(backup)
                warning += f"；原文件已备份为 {backup.name}"
            except OSError as backup_error:
                warning += f"；备份失败：{backup_error}"
            return ConfigLoadResult({"config_version": CONFIG_VERSION}, warning)

    def save(self, data: Mapping[str, Any]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        payload = dict(data)
        payload["config_version"] = CONFIG_VERSION
        temporary = self.path.with_suffix(".tmp")
        try:
            with temporary.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        except Exception:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise

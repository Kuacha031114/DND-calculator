"""Tkinter 高级工作台的组件边界与宿主接口。"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Mapping
from typing import Any

from .engine import RulesEngine
from .quick import QuickAttackRequest


class AdvancedWorkspace(tk.Frame):
    """承载高级工作台，并把根应用依赖收敛为稳定的内部接口。"""

    def __init__(
        self,
        master: tk.Misc,
        *,
        engine: RulesEngine,
        config: Mapping[str, Any],
        background: str,
        build: Callable[[tk.Frame], None],
        append_quick: Callable[[QuickAttackRequest], None],
        export_state: Callable[[], dict[str, Any]],
        on_status: Callable[[str], None],
    ) -> None:
        super().__init__(master, bg=background)
        self.engine = engine
        self.initial_config = config
        self._append_quick = append_quick
        self._export_state = export_state
        self._on_status = on_status
        build(self)

    def append_quick(self, request: QuickAttackRequest) -> None:
        self._append_quick(request)

    def export_state(self) -> dict[str, Any]:
        return self._export_state()

    def set_status(self, message: str) -> None:
        self._on_status(message)

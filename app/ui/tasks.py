"""后台任务线程，避免图像处理阻塞界面。"""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QThread, Signal


class TaskWorker(QThread):
    progress = Signal(int, int, str)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, func: Callable[[Callable[[int, int, str], None]], Any], parent=None) -> None:
        super().__init__(parent)
        self._func = func

    def run(self) -> None:  # noqa: D401
        try:
            result = self._func(self._emit_progress)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return
        self.done.emit(result)

    def _emit_progress(self, current: int, total: int, text: str) -> None:
        self.progress.emit(current, total, text)

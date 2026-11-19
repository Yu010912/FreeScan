"""FreeScan 应用入口。"""
from __future__ import annotations

import ctypes
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from app import __version__
from app.core.projects import ProjectLibrary
from app.core.theme import build_qss, theme_manager
from app.ui.icons import app_icon
from app.ui.main_window import MainWindow


def main() -> int:
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Yu010912.FreeScan")
        except Exception:  # noqa: BLE001
            pass

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("FreeScan")
    app.setApplicationDisplayName("FreeScan")
    app.setOrganizationName("Yu010912")
    app.setOrganizationDomain("github.com/Yu010912")
    app.setApplicationVersion(__version__)

    font = QFont("Microsoft YaHei UI")
    font.setPointSize(9)
    app.setFont(font)
    app.setStyleSheet(build_qss(theme_manager.tokens))
    app.setWindowIcon(
        app_icon(theme_manager.tokens.primary_fill, theme_manager.tokens.on_primary)
    )

    library = ProjectLibrary()
    window = MainWindow(library)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

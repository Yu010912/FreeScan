"""项目列表首页。"""
from __future__ import annotations

from typing import List

from PySide6.QtCore import QSize, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.projects import Project, ProjectLibrary
from ..core.theme import theme_manager
from .icons import render_icon
from .widgets import AddProjectCard, FlowLayout, ProjectCard


class FlowContainer(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.flow = FlowLayout(self, margin=0, spacing=18)
        self.setAttribute(Qt.WA_StyledBackground, False)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self.layout():
            height = self.layout().heightForWidth(self.width())
            if height > 0 and self.minimumHeight() != height:
                self.setMinimumHeight(height)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self.layout().heightForWidth(width)

    def sizeHint(self) -> QSize:  # noqa: N802
        width = self.width() or 900
        return QSize(width, self.layout().heightForWidth(width))


class HomePage(QWidget):
    new_project = Signal()
    open_project = Signal(str)
    rename_project = Signal(object)
    delete_project = Signal(object)

    def __init__(self, library: ProjectLibrary, parent=None) -> None:
        super().__init__(parent)
        self.library = library
        self._projects: List[Project] = []
        tokens = theme_manager.tokens

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 30, 36, 24)
        layout.setSpacing(22)

        header = QHBoxLayout()
        header.setSpacing(12)
        text_col = QVBoxLayout()
        text_col.setSpacing(4)
        self.title = QLabel("我的项目")
        self.title.setObjectName("H1")
        text_col.addWidget(self.title)
        self.subtitle = QLabel("")
        self.subtitle.setObjectName("Subtitle")
        text_col.addWidget(self.subtitle)
        header.addLayout(text_col, 1)

        self.library_button = QPushButton("项目库")
        self.library_button.setObjectName("Ghost")
        self.library_button.setFixedHeight(38)
        self.library_button.setCursor(Qt.PointingHandCursor)
        self.library_button.setIcon(render_icon("folder", tokens.text_secondary, 16))
        self.library_button.setIconSize(QSize(16, 16))
        self.library_button.clicked.connect(self._open_library)
        header.addWidget(self.library_button, 0, Qt.AlignVCenter)

        self.new_button = QPushButton("新建项目")
        self.new_button.setObjectName("Primary")
        self.new_button.setFixedHeight(40)
        self.new_button.setCursor(Qt.PointingHandCursor)
        self.new_button.setIcon(render_icon("plus", tokens.on_primary, 16))
        self.new_button.setIconSize(QSize(16, 16))
        self.new_button.clicked.connect(lambda: self.new_project.emit())
        header.addWidget(self.new_button, 0, Qt.AlignVCenter)
        layout.addLayout(header)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        # 空状态
        empty_wrapper = QWidget()
        empty_layout = QVBoxLayout(empty_wrapper)
        empty_layout.setContentsMargins(0, 8, 0, 24)
        self.empty_panel = QFrame()
        self.empty_panel.setObjectName("EmptyPanel")
        self.empty_panel.setMinimumHeight(360)
        self.empty_panel.setMaximumWidth(780)
        empty_inner = QVBoxLayout(self.empty_panel)
        empty_inner.setContentsMargins(40, 48, 40, 48)
        empty_inner.setSpacing(14)
        empty_inner.setAlignment(Qt.AlignCenter)

        self.empty_icon_frame = QFrame()
        self.empty_icon_frame.setObjectName("IconCircle")
        self.empty_icon_frame.setFixedSize(66, 66)
        self.empty_icon_frame.setStyleSheet(
            f"QFrame#IconCircle {{ background-color: {tokens.primary_soft}; border-radius: 33px; }}"
        )
        icon_layout = QVBoxLayout(self.empty_icon_frame)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        self.empty_icon = QLabel()
        self.empty_icon.setPixmap(render_icon("scan", tokens.primary, 30))
        self.empty_icon.setAlignment(Qt.AlignCenter)
        icon_layout.addWidget(self.empty_icon)
        empty_inner.addWidget(self.empty_icon_frame, 0, Qt.AlignHCenter)

        empty_title = QLabel("开始你的第一次扫描")
        empty_title.setObjectName("EmptyTitle")
        empty_title.setAlignment(Qt.AlignCenter)
        empty_inner.addWidget(empty_title)

        empty_hint = QLabel(
            "导入照片后会自动识别纸张边缘、校正透视并去除阴影，\n输出高清无损的 PNG 或 PDF 文档。"
        )
        empty_hint.setObjectName("EmptyHint")
        empty_hint.setAlignment(Qt.AlignCenter)
        empty_inner.addWidget(empty_hint)

        formats = QLabel("PNG · JPG · HEIF · TIFF · WEBP")
        formats.setObjectName("Meta")
        formats.setAlignment(Qt.AlignCenter)
        empty_inner.addWidget(formats)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        buttons.addStretch(1)
        create = QPushButton("新建项目")
        create.setObjectName("Primary")
        create.setFixedHeight(40)
        create.setCursor(Qt.PointingHandCursor)
        create.setIcon(render_icon("plus", tokens.on_primary, 16))
        create.setIconSize(QSize(16, 16))
        create.clicked.connect(lambda: self.new_project.emit())
        buttons.addWidget(create)
        buttons.addStretch(1)
        empty_inner.addLayout(buttons)

        empty_layout.addStretch(1)
        empty_layout.addWidget(self.empty_panel, 0, Qt.AlignHCenter)
        empty_layout.addStretch(1)
        self.stack.addWidget(empty_wrapper)

        # 项目网格
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.container = FlowContainer()
        self.flow = self.container.flow
        self.scroll.setWidget(self.container)
        self.scroll.viewport().setStyleSheet("background: transparent;")
        self.stack.addWidget(self.scroll)

    def _open_library(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.library.root)))

    def set_projects(self, projects: List[Project]) -> None:
        self._projects = projects
        total_pages = sum(project.page_count for project in projects)
        if projects:
            self.subtitle.setText(
                f"把照片扫描成干净、清晰的无损文档 · 共 {len(projects)} 个项目 / {total_pages} 页"
            )
        else:
            self.subtitle.setText("把照片扫描成干净、清晰的无损文档")

        while self.flow.count():
            item = self.flow.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        if not projects:
            self.stack.setCurrentIndex(0)
            return

        self.stack.setCurrentIndex(1)
        add_card = AddProjectCard()
        add_card.clicked.connect(lambda: self.new_project.emit())
        self.flow.addWidget(add_card)
        for project in projects:
            card = ProjectCard(project)
            card.open_requested.connect(lambda item: self.open_project.emit(item.id))
            card.rename_requested.connect(self.rename_project)
            card.delete_requested.connect(self.delete_project)
            self.flow.addWidget(card)

        self.container.adjustSize()
        self.container.setMinimumHeight(
            max(0, self.flow.heightForWidth(max(1, self.container.width())))
        )
        self.container.updateGeometry()

    def refresh_theme(self) -> None:
        tokens = theme_manager.tokens
        self.library_button.setIcon(render_icon("folder", tokens.text_secondary, 16))
        self.new_button.setIcon(render_icon("plus", tokens.on_primary, 16))
        self.empty_icon.setPixmap(render_icon("scan", tokens.primary, 30))
        self.empty_icon_frame.setStyleSheet(
            f"QFrame#IconCircle {{ background-color: {tokens.primary_soft}; border-radius: 33px; }}"
        )
        for index in range(self.flow.count()):
            widget = self.flow.itemAt(index).widget()
            if isinstance(widget, ProjectCard):
                widget.refresh_theme()
            elif isinstance(widget, AddProjectCard):
                widget.refresh_theme()

"""主窗口：侧边栏导航、项目切换、主题切换与全局提示。"""
from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtCore import QByteArray, QEasingCurve, QPropertyAnimation, QSize, Qt
from PySide6.QtGui import QCloseEvent, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.config import load_settings, save_settings
from ..core.projects import Project, ProjectLibrary
from ..core.theme import build_qss, theme_manager
from .dialogs import AboutDialog, ConfirmDialog, TextInputDialog
from .home_page import HomePage
from .icons import app_icon, logo_pixmap, render_icon
from .scanner_page import ScannerPage
from .widgets import SidebarItem, ThemeToggle, Toast


class MainWindow(QMainWindow):
    def __init__(self, library: ProjectLibrary) -> None:
        super().__init__()
        self.library = library
        self.scanner: Optional[ScannerPage] = None
        self.sidebar_items: Dict[str, SidebarItem] = {}
        self._projects: List[Project] = []

        self.setWindowTitle("FreeScan — 智能图片扫描")
        self.setMinimumSize(1140, 700)
        self.resize(1380, 870)
        self.setWindowIcon(
            app_icon(theme_manager.tokens.primary_fill, theme_manager.tokens.on_primary)
        )
        self._restore_geometry()

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_sidebar())

        self.stack = QStackedWidget()
        self.home = HomePage(library)
        self.home.new_project.connect(self.new_project)
        self.home.open_project.connect(self.open_project)
        self.home.rename_project.connect(self.rename_project)
        self.home.delete_project.connect(self.delete_project)
        self.stack.addWidget(self.home)
        layout.addWidget(self.stack, 1)

        self.toast = Toast(self)

        theme_manager.changed.connect(self._on_theme_changed)
        self.theme_toggle.toggled.connect(self._on_toggle_theme)

        self._shortcuts = [
            QShortcut(QKeySequence("Ctrl+N"), self),
            QShortcut(QKeySequence("Ctrl+O"), self),
        ]
        self._shortcuts[0].activated.connect(self.new_project)
        self._shortcuts[1].activated.connect(self._shortcut_import)

        self.refresh_projects()
        self._center_on_screen()

    # ---------- 侧边栏 ----------
    def _build_sidebar(self) -> QWidget:
        tokens = theme_manager.tokens
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(240)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 18, 16, 14)
        layout.setSpacing(12)

        brand = QHBoxLayout()
        brand.setSpacing(10)
        self.logo_label = QLabel()
        self.logo_label.setFixedSize(38, 38)
        self.logo_label.setPixmap(logo_pixmap(38, tokens.primary_fill, tokens.on_primary))
        brand.addWidget(self.logo_label)
        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        name = QLabel("FreeScan")
        name.setObjectName("BrandName")
        brand_text.addWidget(name)
        tagline = QLabel("智能扫描 · 无损导出")
        tagline.setObjectName("BrandSub")
        brand_text.addWidget(tagline)
        brand.addLayout(brand_text, 1)
        layout.addLayout(brand)
        layout.addSpacing(4)

        self.new_button = QPushButton("新建项目")
        self.new_button.setObjectName("Primary")
        self.new_button.setFixedHeight(38)
        self.new_button.setCursor(Qt.PointingHandCursor)
        self.new_button.setIcon(render_icon("plus", tokens.on_primary, 16))
        self.new_button.setIconSize(QSize(16, 16))
        self.new_button.clicked.connect(self.new_project)
        layout.addWidget(self.new_button)

        section_row = QHBoxLayout()
        section_title = QLabel("项目")
        section_title.setObjectName("SectionTitle")
        section_row.addWidget(section_title)
        section_row.addStretch(1)
        self.project_count_label = QLabel("0")
        self.project_count_label.setObjectName("Meta")
        section_row.addWidget(self.project_count_label)
        layout.addLayout(section_row)

        self.sidebar_scroll = QScrollArea()
        self.sidebar_scroll.setWidgetResizable(True)
        self.sidebar_scroll.setFrameShape(QFrame.NoFrame)
        self.sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.sidebar_scroll.viewport().setStyleSheet("background: transparent;")
        self.sidebar_content = QWidget()
        self.sidebar_layout = QVBoxLayout(self.sidebar_content)
        self.sidebar_layout.setContentsMargins(0, 0, 0, 0)
        self.sidebar_layout.setSpacing(4)
        self.sidebar_layout.setAlignment(Qt.AlignTop)
        self.sidebar_scroll.setWidget(self.sidebar_content)
        layout.addWidget(self.sidebar_scroll, 1)

        appearance = QFrame()
        appearance.setObjectName("Panel")
        appearance_layout = QHBoxLayout(appearance)
        appearance_layout.setContentsMargins(10, 7, 10, 7)
        appearance_layout.setSpacing(8)
        self.theme_icon_label = make_theme_icon_label(tokens.text_muted)
        appearance_layout.addWidget(self.theme_icon_label)
        appearance_text = QVBoxLayout()
        appearance_text.setSpacing(0)
        label = QLabel("深色模式")
        label.setStyleSheet("font-size: 12px; font-weight: 600;")
        appearance_text.addWidget(label)
        hint = QLabel("切换浅色 / 深色主题")
        hint.setObjectName("Meta")
        appearance_text.addWidget(hint)
        appearance_layout.addLayout(appearance_text, 1)
        self.theme_toggle = ThemeToggle()
        appearance_layout.addWidget(self.theme_toggle)
        layout.addWidget(appearance)
        self.appearance_frame = appearance

        self.about_button = QPushButton("关于与许可")
        self.about_button.setObjectName("Ghost")
        self.about_button.setFixedHeight(34)
        self.about_button.setCursor(Qt.PointingHandCursor)
        self.about_button.setIcon(render_icon("info", tokens.text_secondary, 15))
        self.about_button.setIconSize(QSize(15, 15))
        self.about_button.clicked.connect(self.show_about)
        layout.addWidget(self.about_button)

        credit = QLabel("© 2026 Yu010912 · CC BY-NC 4.0")
        credit.setObjectName("Meta")
        credit.setAlignment(Qt.AlignCenter)
        credit.setToolTip("仅供非商业用途，使用请标注作者来源")
        layout.addWidget(credit)
        return sidebar

    # ---------- 项目 ----------
    def refresh_projects(self, select_id: Optional[str] = None) -> None:
        try:
            self._projects = self.library.list_projects()
        except Exception as exc:  # noqa: BLE001
            self.toast.show_message(f"读取项目库失败：{exc}", "error")
            self._projects = []
        self.home.set_projects(self._projects)
        self._rebuild_sidebar(select_id)
        self.project_count_label.setText(str(len(self._projects)))

    def _rebuild_sidebar(self, select_id: Optional[str] = None) -> None:
        while self.sidebar_layout.count():
            item = self.sidebar_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.sidebar_items.clear()

        home_item = SidebarItem("__home__", "我的项目", "全部扫描项目", "layers")
        home_item.clicked.connect(self._on_sidebar_clicked)
        self.sidebar_layout.addWidget(home_item)
        self.sidebar_items["__home__"] = home_item

        for project in self._projects:
            subtitle = f"{project.page_count} 页 · {format_short_time(project.updated_at)}"
            item = SidebarItem(project.id, project.name, subtitle, "file-text")
            item.set_count(project.page_count)
            item.clicked.connect(self._on_sidebar_clicked)
            self.sidebar_layout.addWidget(item)
            self.sidebar_items[project.id] = item

        current = select_id
        if current is None and self.scanner is not None:
            current = self.scanner.project.id
        if current is None:
            current = "__home__"
        for item_id, item in self.sidebar_items.items():
            item.set_selected(item_id == current)

    def _on_sidebar_clicked(self, item_id: str) -> None:
        if item_id == "__home__":
            self.show_home()
        else:
            self.open_project(item_id)

    def new_project(self) -> None:
        default_name = f"扫描项目 {len(self._projects) + 1}"
        dialog = TextInputDialog(
            "新建项目",
            "为这个扫描项目起一个名字，之后可以随时修改。",
            default_name,
            "例如：合同扫描件",
            "创建项目",
            self,
        )
        if dialog.exec() == TextInputDialog.Accepted:
            try:
                project = self.library.create(dialog.value())
            except Exception as exc:  # noqa: BLE001
                self.toast.show_message(f"创建项目失败：{exc}", "error")
                return
            self.refresh_projects(select_id=project.id)
            self.open_project(project.id)
            self.toast.show_message("项目已创建，导入图片开始扫描", "success")

    def open_project(self, project_id: str) -> None:
        if self.scanner is not None and self.scanner.project.id == project_id:
            return
        project = self.library.get(project_id)
        if project is None:
            self.toast.show_message("项目不存在或已被删除", "error")
            self.refresh_projects()
            return

        if self.scanner is not None:
            old = self.scanner
            self.stack.removeWidget(old)
            old.deleteLater()
            self.scanner = None

        scanner = ScannerPage(self.library, project)
        scanner.back_requested.connect(self.show_home)
        scanner.project_changed.connect(self._on_project_changed)
        scanner.delete_project_requested.connect(self.delete_project)
        scanner.notify.connect(self._show_toast)
        self.scanner = scanner
        self.stack.addWidget(scanner)
        self.stack.setCurrentWidget(scanner)
        self._fade_in(scanner)
        self.setWindowTitle(f"{project.name} — FreeScan")
        self._rebuild_sidebar(select_id=project.id)

    def show_home(self) -> None:
        if self.scanner is not None:
            scanner = self.scanner
            self.scanner = None
            self.stack.setCurrentWidget(self.home)
            self.stack.removeWidget(scanner)
            scanner.deleteLater()
        self.setWindowTitle("FreeScan — 智能图片扫描")
        self.refresh_projects()
        self._fade_in(self.home)

    def _on_project_changed(self) -> None:
        self.refresh_projects()
        if self.scanner is not None:
            self.setWindowTitle(f"{self.scanner.project.name} — FreeScan")

    def rename_project(self, project: Project) -> None:
        dialog = TextInputDialog(
            "重命名项目",
            "修改后会立即保存到项目文件。",
            project.name,
            "项目名称",
            "保存",
            self,
        )
        if dialog.exec() != TextInputDialog.Accepted:
            return
        self.library.rename(project, dialog.value())
        self.refresh_projects()
        if self.scanner is not None and self.scanner.project.id == project.id:
            self.scanner.title_edit.setText(project.name)
            self.setWindowTitle(f"{project.name} — FreeScan")

    def delete_project(self, project: Project) -> None:
        dialog = ConfirmDialog(
            "删除项目",
            f"确定删除「{project.name}」吗？项目中的 {project.page_count} 页扫描稿和原图都会被永久删除。",
            "删除项目",
            self,
        )
        if dialog.exec() != ConfirmDialog.Accepted:
            return
        if self.scanner is not None and self.scanner.project.id == project.id:
            self.show_home()
        self.library.delete(project)
        self.refresh_projects()
        self.toast.show_message("项目已删除", "success")

    def show_about(self) -> None:
        dialog = AboutDialog(str(self.library.root), self)
        dialog.exec()

    # ---------- 主题 ----------
    def _on_toggle_theme(self, dark: bool) -> None:
        theme_manager.set_dark(dark)

    def _on_theme_changed(self, dark: bool) -> None:
        self.apply_theme()

    def apply_theme(self) -> None:
        tokens = theme_manager.tokens
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(build_qss(tokens))
        self.theme_toggle.blockSignals(True)
        self.theme_toggle.setChecked(tokens.dark)
        self.theme_toggle.blockSignals(False)
        self.theme_icon_label.setPixmap(render_icon("moon", tokens.text_muted, 16))
        self.logo_label.setPixmap(logo_pixmap(38, tokens.primary_fill, tokens.on_primary))
        self.new_button.setIcon(render_icon("plus", tokens.on_primary, 16))
        self.about_button.setIcon(render_icon("info", tokens.text_secondary, 15))
        self.setWindowIcon(app_icon(tokens.primary_fill, tokens.on_primary))
        self.refresh_projects()
        if self.scanner is not None:
            self.scanner.refresh_theme()
        self.toast.hide()
        self.update()

    # ---------- 其他 ----------
    def _show_toast(self, message: str, kind: str = "success") -> None:
        self.toast.show_message(message, kind)

    def _shortcut_import(self) -> None:
        if self.scanner is not None:
            self.scanner.choose_files()

    def _fade_in(self, widget: QWidget) -> None:
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", widget)
        animation.setDuration(220)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.OutCubic)

        def cleanup() -> None:
            if widget.graphicsEffect() is effect:
                widget.setGraphicsEffect(None)

        animation.finished.connect(cleanup)
        animation.start(QPropertyAnimation.DeleteWhenStopped)
        widget._fade_animation = animation  # type: ignore[attr-defined]

    def _restore_geometry(self) -> None:
        data = load_settings().get("window_geometry")
        if data:
            try:
                self.restoreGeometry(QByteArray.fromBase64(str(data).encode("ascii")))
            except Exception:  # noqa: BLE001
                pass

    def _center_on_screen(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        max_size = QSize(int(available.width() * 0.94), int(available.height() * 0.94))
        if max_size.width() > 0 and max_size.height() > 0:
            self.resize(self.size().boundedTo(max_size))
        frame = self.frameGeometry()
        frame.moveCenter(available.center())
        self.move(frame.topLeft())

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self.scanner is not None and self.scanner.is_busy():
            self.toast.show_message("正在处理任务，请稍候再关闭", "error")
            event.ignore()
            return
        settings = load_settings()
        settings["window_geometry"] = bytes(self.saveGeometry().toBase64()).decode("ascii")
        save_settings(settings)
        super().closeEvent(event)


def format_short_time(iso_text: str) -> str:
    try:
        import time as _time

        stamp = _time.strptime(iso_text, "%Y-%m-%dT%H:%M:%S")
        return _time.strftime("%m-%d %H:%M", stamp)
    except Exception:  # noqa: BLE001
        return ""


def make_theme_icon_label(color: str) -> QLabel:
    label = QLabel()
    label.setPixmap(render_icon("moon", color, 16))
    label.setFixedSize(16, 16)
    return label

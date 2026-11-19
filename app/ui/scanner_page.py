"""扫描工作台：页面列表、预览、智能处理与导出。"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import QEvent, QPoint, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..core import imaging
from ..core.config import load_settings, update_setting
from ..core.projects import Page, Project, ProjectLibrary
from ..core.theme import theme_manager
from .dialogs import AdjustDialog, ConfirmDialog, ExportDialog, TextInputDialog
from .icons import render_icon
from .preview import PreviewCanvas
from .tasks import TaskWorker
from .widgets import (
    ElidedLabel,
    ModeOption,
    PageThumb,
    ProgressDialog,
    ToggleCheck,
    divider,
    load_pixmap,
    make_icon_label,
)

IMAGE_FILTER = (
    "图片文件 (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp *.heic *.heif);;所有文件 (*.*)"
)
MODE_TEXT = {"original": "原图", "enhance": "增强", "bw": "黑白"}


class ScannerPage(QWidget):
    back_requested = Signal()
    project_changed = Signal()
    delete_project_requested = Signal(object)
    notify = Signal(str, str)

    def __init__(self, library: ProjectLibrary, project: Project, parent=None) -> None:
        super().__init__(parent)
        self.library = library
        self.project = project
        self.selected_id: Optional[str] = project.pages[0].id if project.pages else None
        self.checked_ids = set()
        self._thumb_widgets: Dict[str, PageThumb] = {}
        self._worker: Optional[TaskWorker] = None
        self._compare_pixmap = None
        self._icon_refs = []
        self._compare_active = False
        self.setAcceptDrops(True)

        tokens = theme_manager.tokens
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 14, 20, 16)
        root.setSpacing(14)

        # ---------- 顶部栏 ----------
        top = QHBoxLayout()
        top.setSpacing(8)
        self.back_button = self._icon_button("arrow-left", "返回项目列表", self._go_back, 34)
        top.addWidget(self.back_button)

        self.title_edit = QLineEdit(project.name)
        self.title_edit.setObjectName("PageTitle")
        self.title_edit.setMaxLength(80)
        self.title_edit.setToolTip("点击修改项目名称")
        self.title_edit.editingFinished.connect(self._commit_title)
        self.title_edit.textChanged.connect(self._resize_title_edit)
        top.addWidget(self.title_edit)
        self._resize_title_edit()

        self.count_badge = QLabel("0 页")
        self.count_badge.setObjectName("CountBadge")
        top.addWidget(self.count_badge)

        self.project_menu_button = self._icon_button("more", "项目菜单", self._show_project_menu, 30)
        top.addWidget(self.project_menu_button)
        top.addStretch(1)

        self.import_button = QPushButton("导入图片")
        self.import_button.setObjectName("Secondary")
        self.import_button.setFixedHeight(38)
        self.import_button.setCursor(Qt.PointingHandCursor)
        self.import_button.setIcon(render_icon("upload", tokens.text, 16))
        self.import_button.setIconSize(QSize(16, 16))
        self.import_button.setToolTip("导入 PNG / JPG / HEIF 等图片（Ctrl+O）")
        self.import_button.clicked.connect(self._choose_files)
        self._icon_refs.append((self.import_button, "upload", 16, "text"))
        top.addWidget(self.import_button)

        self.export_button = QPushButton("导出 ▾")
        self.export_button.setObjectName("Primary")
        self.export_button.setFixedHeight(38)
        self.export_button.setCursor(Qt.PointingHandCursor)
        self.export_button.setToolTip("导出无损图片或多页 PDF")
        self.export_button.setIcon(render_icon("download", tokens.on_primary, 16))
        self.export_button.setIconSize(QSize(16, 16))
        self.export_button.clicked.connect(self._show_export_menu)
        self._icon_refs.append((self.export_button, "download", 16, "on_primary"))
        top.addWidget(self.export_button)
        root.addLayout(top)

        # ---------- 主体 ----------
        self.body_stack = QStackedWidget()
        root.addWidget(self.body_stack, 1)
        self.body_stack.addWidget(self._build_empty_state())
        self.body_stack.addWidget(self._build_workspace())

        self._refresh_all()

    # ---------- UI 构建 ----------
    def _build_empty_state(self) -> QWidget:
        tokens = theme_manager.tokens
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 10, 0, 10)

        panel = QFrame()
        panel.setObjectName("EmptyPanel")
        panel.setMinimumHeight(380)
        panel.setMaximumWidth(780)
        inner = QVBoxLayout(panel)
        inner.setContentsMargins(40, 48, 40, 48)
        inner.setSpacing(14)
        inner.setAlignment(Qt.AlignCenter)

        self.empty_icon_frame = QFrame()
        self.empty_icon_frame.setObjectName("IconCircle")
        self.empty_icon_frame.setFixedSize(68, 68)
        self.empty_icon_frame.setStyleSheet(
            f"QFrame#IconCircle {{ background-color: {tokens.primary_soft}; border-radius: 34px; }}"
        )
        icon_layout = QVBoxLayout(self.empty_icon_frame)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        self.empty_icon = QLabel()
        self.empty_icon.setPixmap(render_icon("scan", tokens.primary, 30))
        self.empty_icon.setAlignment(Qt.AlignCenter)
        icon_layout.addWidget(self.empty_icon)
        inner.addWidget(self.empty_icon_frame, 0, Qt.AlignHCenter)

        title = QLabel("导入照片，生成高清扫描件")
        title.setObjectName("EmptyTitle")
        title.setAlignment(Qt.AlignCenter)
        inner.addWidget(title)

        hint = QLabel(
            "自动识别纸张边缘、校正透视角度，并消除阴影与光照不均。\n"
            "导出 PNG / TIFF / PDF 时保留全部原始像素，不做二次压缩。"
        )
        hint.setObjectName("EmptyHint")
        hint.setAlignment(Qt.AlignCenter)
        inner.addWidget(hint)

        formats = QLabel("支持 PNG · JPG · HEIF · TIFF · WEBP")
        formats.setObjectName("Meta")
        formats.setAlignment(Qt.AlignCenter)
        inner.addWidget(formats)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        button_row.addStretch(1)
        choose = QPushButton("选择图片导入")
        choose.setObjectName("Primary")
        choose.setFixedHeight(40)
        choose.setCursor(Qt.PointingHandCursor)
        choose.setIcon(render_icon("image-plus", tokens.on_primary, 16))
        choose.setIconSize(QSize(16, 16))
        choose.clicked.connect(self._choose_files)
        self._icon_refs.append((choose, "image-plus", 16, "on_primary"))
        button_row.addWidget(choose)
        button_row.addStretch(1)
        inner.addLayout(button_row)

        drag_hint = QLabel("也可以将图片直接拖拽到窗口")
        drag_hint.setObjectName("Meta")
        drag_hint.setAlignment(Qt.AlignCenter)
        inner.addWidget(drag_hint)

        layout.addStretch(1)
        layout.addWidget(panel, 0, Qt.AlignHCenter)
        layout.addStretch(1)
        return wrapper

    def _build_workspace(self) -> QWidget:
        tokens = theme_manager.tokens
        workspace = QWidget()
        layout = QHBoxLayout(workspace)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        # 页面列表
        filmstrip = QFrame()
        filmstrip.setObjectName("Filmstrip")
        filmstrip.setFixedWidth(176)
        film_layout = QVBoxLayout(filmstrip)
        film_layout.setContentsMargins(10, 10, 10, 10)
        film_layout.setSpacing(8)

        film_header = QHBoxLayout()
        film_header.setSpacing(6)
        film_title = QLabel("页面")
        film_title.setObjectName("SectionTitle")
        film_header.addWidget(film_title)
        self.page_badge = QLabel("0")
        self.page_badge.setObjectName("CountBadge")
        film_header.addWidget(self.page_badge)
        film_header.addStretch(1)
        select_label = QLabel("全选")
        select_label.setObjectName("Meta")
        select_label.setToolTip("全选页面用于批量导出或删除")
        film_header.addWidget(select_label)
        self.select_all = ToggleCheck()
        self.select_all.setToolTip("全选页面用于批量导出或删除")
        self.select_all.toggled.connect(self._toggle_select_all)
        film_header.addWidget(self.select_all)
        film_layout.addLayout(film_header)

        self.film_scroll = QScrollArea()
        self.film_scroll.setWidgetResizable(True)
        self.film_scroll.setFrameShape(QFrame.NoFrame)
        self.film_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.film_scroll.viewport().setStyleSheet("background: transparent;")
        self.film_content = QWidget()
        self.film_layout = QVBoxLayout(self.film_content)
        self.film_layout.setContentsMargins(0, 2, 0, 2)
        self.film_layout.setSpacing(10)
        self.film_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.film_scroll.setWidget(self.film_content)
        film_layout.addWidget(self.film_scroll, 1)

        self.batch_delete_button = QPushButton("删除选中")
        self.batch_delete_button.setObjectName("DangerGhost")
        self.batch_delete_button.setFixedHeight(32)
        self.batch_delete_button.setCursor(Qt.PointingHandCursor)
        self.batch_delete_button.setIcon(render_icon("trash", tokens.danger, 14))
        self.batch_delete_button.setIconSize(QSize(14, 14))
        self.batch_delete_button.clicked.connect(self._delete_checked)
        self.batch_delete_button.setVisible(False)
        film_layout.addWidget(self.batch_delete_button)
        layout.addWidget(filmstrip)

        # 预览
        self.preview_wrap = QWidget()
        preview_layout = QVBoxLayout(self.preview_wrap)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        self.preview = PreviewCanvas()
        self.preview.set_bottom_reserve(58)
        self.preview.zoom_changed.connect(self._on_zoom_changed)
        preview_layout.addWidget(self.preview)
        self.preview_wrap.installEventFilter(self)
        layout.addWidget(self.preview_wrap, 1)

        self.toolbar = QFrame(self.preview_wrap)
        self.toolbar.setObjectName("Toolbar")
        self.toolbar.setFixedHeight(46)
        shadow = QGraphicsDropShadowEffect(self.toolbar)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 60 if tokens.dark else 32))
        self.toolbar.setGraphicsEffect(shadow)
        tool_layout = QHBoxLayout(self.toolbar)
        tool_layout.setContentsMargins(7, 4, 7, 4)
        tool_layout.setSpacing(3)

        tool_layout.addWidget(self._tool_button("zoom-out", "缩小", self.preview.zoom_out))
        self.zoom_label = QLabel("100%")
        self.zoom_label.setObjectName("ZoomValue")
        self.zoom_label.setAlignment(Qt.AlignCenter)
        self.zoom_label.setFixedWidth(42)
        tool_layout.addWidget(self.zoom_label)
        tool_layout.addWidget(self._tool_button("zoom-in", "放大", self.preview.zoom_in))
        tool_layout.addWidget(self._tool_button("fit", "适应窗口（双击预览也可）", self.preview.fit_view))
        tool_layout.addWidget(self._v_divider())
        tool_layout.addWidget(self._tool_button("rotate-ccw", "向左旋转", lambda: self._rotate(-90)))
        tool_layout.addWidget(self._tool_button("rotate-cw", "向右旋转", lambda: self._rotate(90)))
        tool_layout.addWidget(self._v_divider())
        self.compare_button = QPushButton("按住对比原图")
        self.compare_button.setObjectName("Ghost")
        self.compare_button.setFixedHeight(32)
        self.compare_button.setCursor(Qt.PointingHandCursor)
        self.compare_button.setIcon(render_icon("eye", tokens.text_secondary, 15))
        self.compare_button.setIconSize(QSize(15, 15))
        self.compare_button.setToolTip("按住查看未处理的原始照片")
        self.compare_button.pressed.connect(self._show_original)
        self.compare_button.released.connect(self._hide_original)
        self._icon_refs.append((self.compare_button, "eye", 15, "text_secondary"))
        tool_layout.addWidget(self.compare_button)

        # 检查器
        inspector = QFrame()
        inspector.setObjectName("Inspector")
        inspector.setFixedWidth(272)
        insp_layout = QVBoxLayout(inspector)
        insp_layout.setContentsMargins(16, 16, 16, 16)
        insp_layout.setSpacing(9)

        head = QHBoxLayout()
        head.setSpacing(6)
        head.addWidget(make_icon_label("sparkles", tokens.primary, 15))
        head_title = QLabel("智能处理")
        head_title.setStyleSheet("font-size: 13px; font-weight: 700;")
        head.addWidget(head_title)
        head.addStretch(1)
        auto_badge = QLabel("AUTO")
        auto_badge.setObjectName("Badge")
        head.addWidget(auto_badge)
        insp_layout.addLayout(head)

        self.mode_options: Dict[str, ModeOption] = {}
        mode_specs = [
            ("original", "原图", "仅裁剪校正", "image"),
            ("enhance", "增强", "去阴影 · 提亮", "sparkles"),
            ("bw", "黑白", "文字更锐利", "contrast"),
        ]
        for mode, title, hint, icon_name in mode_specs:
            option = ModeOption(mode, title, hint, icon_name)
            option.clicked.connect(self._set_mode)
            self.mode_options[mode] = option
            insp_layout.addWidget(option)

        self.adjust_button = QPushButton("调整扫描参数")
        self.adjust_button.setObjectName("Secondary")
        self.adjust_button.setFixedHeight(34)
        self.adjust_button.setCursor(Qt.PointingHandCursor)
        self.adjust_button.setIcon(render_icon("sliders", tokens.text, 14))
        self.adjust_button.setIconSize(QSize(14, 14))
        self.adjust_button.setToolTip("调整阴影、提白、墨色、亮度、对比度与边缘内缩")
        self.adjust_button.clicked.connect(self._open_adjustments)
        self._icon_refs.append((self.adjust_button, "sliders", 14, "text"))
        insp_layout.addWidget(self.adjust_button)

        insp_layout.addWidget(divider())
        page_section = QLabel("页面操作")
        page_section.setObjectName("SectionTitle")
        insp_layout.addWidget(page_section)
        action_row = QHBoxLayout()
        action_row.setSpacing(6)
        rotate_left = QPushButton("左转")
        rotate_left.setObjectName("Secondary")
        rotate_left.setFixedHeight(34)
        rotate_left.setCursor(Qt.PointingHandCursor)
        rotate_left.setIcon(render_icon("rotate-ccw", tokens.text, 14))
        rotate_left.setIconSize(QSize(14, 14))
        rotate_left.clicked.connect(lambda: self._rotate(-90))
        self._icon_refs.append((rotate_left, "rotate-ccw", 14, "text"))
        action_row.addWidget(rotate_left, 1)

        rotate_right = QPushButton("右转")
        rotate_right.setObjectName("Secondary")
        rotate_right.setFixedHeight(34)
        rotate_right.setCursor(Qt.PointingHandCursor)
        rotate_right.setIcon(render_icon("rotate-cw", tokens.text, 14))
        rotate_right.setIconSize(QSize(14, 14))
        rotate_right.clicked.connect(lambda: self._rotate(90))
        self._icon_refs.append((rotate_right, "rotate-cw", 14, "text"))
        action_row.addWidget(rotate_right, 1)

        self.delete_button = QPushButton("删除")
        self.delete_button.setObjectName("DangerGhost")
        self.delete_button.setFixedHeight(34)
        self.delete_button.setCursor(Qt.PointingHandCursor)
        self.delete_button.setIcon(render_icon("trash", tokens.danger, 14))
        self.delete_button.setIconSize(QSize(14, 14))
        self.delete_button.clicked.connect(self._delete_page)
        self._icon_refs.append((self.delete_button, "trash", 14, "danger"))
        action_row.addWidget(self.delete_button, 1)
        insp_layout.addLayout(action_row)

        order_row = QHBoxLayout()
        order_row.setSpacing(6)
        self.move_up_button = QPushButton("上移")
        self.move_up_button.setObjectName("Secondary")
        self.move_up_button.setFixedHeight(34)
        self.move_up_button.setCursor(Qt.PointingHandCursor)
        self.move_up_button.setIcon(render_icon("chevron-up", tokens.text, 14))
        self.move_up_button.setIconSize(QSize(14, 14))
        self.move_up_button.setToolTip("将此页在 PDF / 导出顺序中上移")
        self.move_up_button.clicked.connect(lambda: self._move_page(-1))
        self._icon_refs.append((self.move_up_button, "chevron-up", 14, "text"))
        order_row.addWidget(self.move_up_button, 1)

        self.move_down_button = QPushButton("下移")
        self.move_down_button.setObjectName("Secondary")
        self.move_down_button.setFixedHeight(34)
        self.move_down_button.setCursor(Qt.PointingHandCursor)
        self.move_down_button.setIcon(render_icon("chevron-down", tokens.text, 14))
        self.move_down_button.setIconSize(QSize(14, 14))
        self.move_down_button.setToolTip("将此页在 PDF / 导出顺序中下移")
        self.move_down_button.clicked.connect(lambda: self._move_page(1))
        self._icon_refs.append((self.move_down_button, "chevron-down", 14, "text"))
        order_row.addWidget(self.move_down_button, 1)
        insp_layout.addLayout(order_row)

        insp_layout.addWidget(divider())
        info_section = QLabel("文件信息")
        info_section.setObjectName("SectionTitle")
        insp_layout.addWidget(info_section)

        self.info_labels: Dict[str, QLabel] = {}
        for key in ("页面尺寸", "存储格式", "原始文件", "创建时间"):
            row = QHBoxLayout()
            row.setSpacing(6)
            key_label = QLabel(key)
            key_label.setObjectName("InfoKey")
            key_label.setFixedWidth(52)
            row.addWidget(key_label)
            value = ElidedLabel("—", tokens.text_secondary)
            value.setStyleSheet("font-size: 11px;")
            value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row.addWidget(value, 1)
            self.info_labels[key] = value
            insp_layout.addLayout(row)

        insp_layout.addStretch(1)

        self.tip_card = QFrame()
        self.tip_card.setObjectName("TipCard")
        self.tip_card.setStyleSheet(
            f"QFrame#TipCard {{ background-color: {tokens.surface_alt}; "
            f"border: 1px solid {tokens.border}; border-radius: 10px; }}"
        )
        tip_layout = QHBoxLayout(self.tip_card)
        tip_layout.setContentsMargins(10, 9, 10, 9)
        tip_layout.setSpacing(7)
        tip_layout.addWidget(make_icon_label("info", tokens.text_muted, 14), 0, Qt.AlignTop)
        tip_label = QLabel("导出 PNG / TIFF / PDF 均保留全部像素，不做二次压缩。")
        tip_label.setObjectName("Meta")
        tip_label.setWordWrap(True)
        tip_layout.addWidget(tip_label, 1)
        insp_layout.addWidget(self.tip_card)

        layout.addWidget(inspector)
        return workspace

    def _icon_button(self, icon_name: str, tooltip: str, callback, size: int = 30) -> QPushButton:
        tokens = theme_manager.tokens
        button = QPushButton()
        button.setObjectName("IconBtn")
        button.setFixedSize(size, size)
        button.setCursor(Qt.PointingHandCursor)
        button.setToolTip(tooltip)
        button.setIcon(render_icon(icon_name, tokens.text_secondary, 17))
        button.setIconSize(QSize(17, 17))
        button.clicked.connect(callback)
        self._icon_refs.append((button, icon_name, 17, "text_secondary"))
        return button

    def _tool_button(self, icon_name: str, tooltip: str, callback) -> QPushButton:
        button = self._icon_button(icon_name, tooltip, callback, 30)
        button.setObjectName("ToolBtn")
        button.setIconSize(QSize(16, 16))
        return button

    def _v_divider(self) -> QFrame:
        line = QFrame()
        line.setObjectName("VDivider")
        line.setFixedSize(1, 20)
        return line

    # ---------- 事件 ----------
    def eventFilter(self, obj, event):  # noqa: N802
        if obj is self.preview_wrap and event.type() == QEvent.Resize and hasattr(self, "toolbar"):
            self._position_toolbar()
        return super().eventFilter(obj, event)

    def _position_toolbar(self) -> None:
        self.toolbar.adjustSize()
        width = self.toolbar.width()
        x = max(8, (self.preview_wrap.width() - width) // 2)
        y = max(8, self.preview_wrap.height() - self.toolbar.height() - 12)
        self.toolbar.move(x, y)
        self.toolbar.raise_()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        QTimer.singleShot(0, self._position_toolbar)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile() and imaging.is_supported(url.toLocalFile()):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802
        files = [
            url.toLocalFile()
            for url in event.mimeData().urls()
            if url.isLocalFile() and imaging.is_supported(url.toLocalFile())
        ]
        if files:
            event.acceptProposedAction()
            self.import_files(files)

    # ---------- 数据刷新 ----------
    def _current_page(self) -> Optional[Page]:
        for page in self.project.pages:
            if page.id == self.selected_id:
                return page
        return self.project.pages[0] if self.project.pages else None

    def _refresh_all(self) -> None:
        has_pages = bool(self.project.pages)
        self.count_badge.setText(f"{len(self.project.pages)} 页")
        self.body_stack.setCurrentIndex(1 if has_pages else 0)
        self.export_button.setEnabled(has_pages)
        self.export_button.setIcon(
            render_icon(
                "download",
                theme_manager.tokens.on_primary if has_pages else theme_manager.tokens.text_muted,
                16,
            )
        )
        if not has_pages:
            self.selected_id = None
            self.checked_ids.clear()
            self.preview.clear()
            self.zoom_label.setText("100%")
            if hasattr(self, "batch_delete_button"):
                self._update_batch_delete()
            return
        if self.selected_id not in {page.id for page in self.project.pages}:
            self.selected_id = self.project.pages[0].id
        self._rebuild_filmstrip()
        self._load_preview()
        self._update_inspector()
        self._update_batch_delete()

    def _rebuild_filmstrip(self) -> None:
        while self.film_layout.count():
            item = self.film_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._thumb_widgets.clear()

        for index, page in enumerate(self.project.pages, start=1):
            thumb = PageThumb(page, index)
            thumb.set_thumb_path(str(self.project.root / page.thumb))
            thumb.set_checked(page.id in self.checked_ids)
            thumb.set_selected(page.id == self.selected_id)
            thumb.clicked.connect(self._select_page)
            thumb.checked_changed.connect(self._on_checked)
            self.film_layout.addWidget(thumb, 0, Qt.AlignHCenter)
            self._thumb_widgets[page.id] = thumb

        self.page_badge.setText(str(len(self.project.pages)))
        all_checked = bool(self.project.pages) and len(self.checked_ids) == len(self.project.pages)
        self.select_all.blockSignals(True)
        self.select_all.setChecked(all_checked)
        self.select_all.blockSignals(False)

    def _load_preview(self) -> None:
        page = self._current_page()
        if page is None:
            self.preview.clear()
            return
        pixmap = load_pixmap(str(self.project.root / page.processed), page.rotation)
        self.preview.set_pixmap(pixmap)
        self._compare_pixmap = None
        self._compare_active = False
        self.compare_button.setText("按住对比原图")

    def _update_inspector(self) -> None:
        page = self._current_page()
        if page is None:
            return
        for mode, option in self.mode_options.items():
            option.set_selected(mode == page.mode)

        width, height = page.width, page.height
        if page.rotation % 180 == 90:
            width, height = height, width
        self.info_labels["页面尺寸"].setText(f"{width:,} × {height:,} px")
        dpi = int(round(float(page.dpi or imaging.OUTPUT_DPI)))
        self.info_labels["存储格式"].setText(f"PNG · {dpi} DPI")
        self.info_labels["原始文件"].setText(page.original_name or "—")
        try:
            stamp = time.strptime(page.created_at, "%Y-%m-%dT%H:%M:%S")
            self.info_labels["创建时间"].setText(time.strftime("%Y-%m-%d %H:%M", stamp))
        except Exception:  # noqa: BLE001
            self.info_labels["创建时间"].setText("—")
        self.delete_button.setEnabled(True)
        index = self.project.pages.index(page)
        self.move_up_button.setEnabled(index > 0)
        self.move_down_button.setEnabled(index < len(self.project.pages) - 1)

    def _select_page(self, page_id: str) -> None:
        self.selected_id = page_id
        for pid, thumb in self._thumb_widgets.items():
            thumb.set_selected(pid == page_id)
        self._load_preview()
        self._update_inspector()

    def _on_checked(self, page_id: str, checked: bool) -> None:
        if checked:
            self.checked_ids.add(page_id)
        else:
            self.checked_ids.discard(page_id)
        all_checked = bool(self.project.pages) and len(self.checked_ids) == len(self.project.pages)
        self.select_all.blockSignals(True)
        self.select_all.setChecked(all_checked)
        self.select_all.blockSignals(False)
        self._update_batch_delete()

    def _toggle_select_all(self, checked: bool) -> None:
        self.checked_ids = {page.id for page in self.project.pages} if checked else set()
        for thumb in self._thumb_widgets.values():
            thumb.set_checked(checked)
        self._update_batch_delete()

    def _update_batch_delete(self) -> None:
        if not hasattr(self, "batch_delete_button"):
            return
        count = len(self.checked_ids)
        self.batch_delete_button.setText(f"删除选中 ({count})" if count else "删除选中")
        self.batch_delete_button.setVisible(count > 0)

    def _on_zoom_changed(self, percent: int) -> None:
        self.zoom_label.setText(f"{percent}%")

    # ---------- 操作 ----------
    def _commit_title(self) -> None:
        name = self.title_edit.text().strip()
        if not name:
            self.title_edit.setText(self.project.name)
            return
        if name != self.project.name:
            self.library.rename(self.project, name)
            self.project_changed.emit()

    def _resize_title_edit(self) -> None:
        metrics = self.title_edit.fontMetrics()
        width = metrics.horizontalAdvance(self.title_edit.text() or "项目名称") + 38
        self.title_edit.setFixedWidth(max(150, min(360, width)))

    def _go_back(self) -> None:
        self._commit_title()
        self.back_requested.emit()

    def _show_project_menu(self) -> None:
        tokens = theme_manager.tokens
        menu = QMenu(self)
        rename_action = menu.addAction(render_icon("pen", tokens.text, 15), "重命名项目")
        folder_action = menu.addAction(render_icon("folder", tokens.text, 15), "在资源管理器中打开")
        menu.addSeparator()
        delete_action = menu.addAction(render_icon("trash", tokens.danger, 15), "删除项目")
        chosen = menu.exec(
            self.project_menu_button.mapToGlobal(
                QPoint(-120, self.project_menu_button.height() + 4)
            )
        )
        if chosen == rename_action:
            self._rename_project()
        elif chosen == folder_action:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.project.root)))
        elif chosen == delete_action:
            self.delete_project_requested.emit(self.project)

    def _rename_project(self) -> None:
        dialog = TextInputDialog(
            "重命名项目",
            "修改后会立即保存。",
            self.project.name,
            "项目名称",
            "保存",
            self.window(),
        )
        if dialog.exec() != TextInputDialog.Accepted:
            return
        self.library.rename(self.project, dialog.value())
        self.title_edit.setText(self.project.name)
        self.project_changed.emit()
        self.notify.emit("项目已重命名", "success")

    def _move_page(self, delta: int) -> None:
        page = self._current_page()
        if page is None:
            return
        index = self.project.pages.index(page)
        target = index + delta
        if target < 0 or target >= len(self.project.pages):
            return
        ids = [item.id for item in self.project.pages]
        ids[index], ids[target] = ids[target], ids[index]
        self.library.reorder(self.project, ids)
        self.selected_id = page.id
        self._refresh_all()
        self.notify.emit("已调整页面顺序", "success")

    def _delete_checked(self) -> None:
        pages = [page for page in self.project.pages if page.id in self.checked_ids]
        if not pages:
            return
        dialog = ConfirmDialog(
            "删除选中页面",
            f"确定删除选中的 {len(pages)} 页吗？原始图片与处理结果都会从项目中移除，此操作不可撤销。",
            "删除选中",
            self.window(),
        )
        if dialog.exec() != ConfirmDialog.Accepted:
            return
        remaining_ids = [page.id for page in self.project.pages if page.id not in self.checked_ids]
        self.library.remove_pages(self.project, pages)
        self.checked_ids.clear()
        if self.selected_id not in remaining_ids:
            self.selected_id = remaining_ids[0] if remaining_ids else None
        self._refresh_all()
        self.project_changed.emit()
        self.notify.emit(f"已删除 {len(pages)} 页", "success")

    def _open_adjustments(self) -> None:
        page = self._current_page()
        if page is None:
            return
        dialog = AdjustDialog(page.adjustments, self.window())
        if dialog.exec() != AdjustDialog.Accepted:
            return
        options = dialog.values()
        project = self.project

        def job(progress):
            progress(0, 1, "正在应用扫描参数")
            self.library.reprocess(project, page, page.mode, options)
            progress(1, 1, "完成")
            return page

        progress_dialog = ProgressDialog(
            "正在应用扫描参数",
            "重新计算光照、纸张白度与墨色曲线…",
            self.window(),
        )
        progress_dialog.set_indeterminate()

        def finished(result):
            thumb = self._thumb_widgets.get(result.id)
            if thumb is not None:
                thumb.reload_image()
            self._load_preview()
            self._update_inspector()
            self.notify.emit("扫描参数已应用", "success")

        self._start_task(job, progress_dialog, finished, "参数应用失败")

    def _choose_files(self) -> None:
        last_dir = load_settings().get("last_import_dir") or str(Path.home())
        files, _ = QFileDialog.getOpenFileNames(self, "选择要扫描的图片", last_dir, IMAGE_FILTER)
        if files:
            update_setting("last_import_dir", str(Path(files[0]).parent))
            self.import_files(files)

    def choose_files(self) -> None:
        self._choose_files()

    def show_export_menu(self) -> None:
        self._show_export_menu()

    def is_busy(self) -> bool:
        return self._worker is not None

    def import_files(self, paths: List[str]) -> None:
        paths = [path for path in paths if imaging.is_supported(path)]
        if not paths:
            self.notify.emit("没有可导入的图片格式", "error")
            return
        project = self.project

        def job(progress):
            added = []
            failures = []
            total = len(paths)
            for index, path in enumerate(paths, start=1):
                progress(index - 1, total, f"正在扫描 {os.path.basename(path)}")
                try:
                    page = self.library.add_page(project, path, imaging.MODE_ENHANCE)
                    added.append(page)
                except Exception as exc:  # noqa: BLE001
                    failures.append((os.path.basename(path), str(exc)))
                progress(index, total, f"已完成 {index} / {total}")
            if not added:
                message = failures[0][1] if failures else "没有可导入的图片"
                raise RuntimeError(message)
            return added, failures

        dialog = ProgressDialog(
            "正在进行智能扫描",
            "自动识别边缘、校正透视并消除阴影，请稍候…",
            self.window(),
        )
        dialog.set_progress(0, len(paths))

        def finished(result):
            added, failures = result
            self.selected_id = added[0].id
            self.checked_ids.clear()
            self._refresh_all()
            self.project_changed.emit()
            if failures:
                self.notify.emit(
                    f"已导入 {len(added)} 页，{len(failures)} 张图片读取失败", "error"
                )
            else:
                self.notify.emit(f"已导入 {len(added)} 页并完成智能扫描", "success")

        self._start_task(job, dialog, finished, "导入失败")

    def _set_mode(self, mode: str) -> None:
        page = self._current_page()
        if page is None or page.mode == mode:
            return
        project = self.project

        def job(progress):
            progress(0, 1, f"正在应用「{MODE_TEXT.get(mode, mode)}」处理")
            self.library.reprocess(project, page, mode)
            progress(1, 1, "完成")
            return page

        dialog = ProgressDialog("正在重新处理", "去除阴影并重建清晰画面…", self.window())
        dialog.set_indeterminate()

        def finished(result):
            thumb = self._thumb_widgets.get(result.id)
            if thumb is not None:
                thumb.mode_label.setText(MODE_TEXT.get(mode, mode))
                thumb.reload_image()
            self._load_preview()
            self._update_inspector()
            self.notify.emit(f"已应用「{MODE_TEXT.get(mode, mode)}」模式", "success")

        self._start_task(job, dialog, finished, "处理失败")

    def _rotate(self, delta: int) -> None:
        page = self._current_page()
        if page is None:
            return
        self.library.rotate(self.project, page, delta)
        thumb = self._thumb_widgets.get(page.id)
        if thumb is not None:
            thumb.reload_image()
        self._load_preview()
        self._update_inspector()

    def _delete_page(self) -> None:
        page = self._current_page()
        if page is None:
            return
        index = self.project.pages.index(page) + 1
        dialog = ConfirmDialog(
            "删除页面",
            f"确定删除第 {index} 页吗？原始图片与处理结果都会从项目中移除，此操作不可撤销。",
            "删除页面",
            self.window(),
        )
        if dialog.exec() != ConfirmDialog.Accepted:
            return
        self.library.remove_page(self.project, page)
        self.checked_ids.discard(page.id)
        if self.project.pages:
            self.selected_id = self.project.pages[min(index - 1, len(self.project.pages) - 1)].id
        else:
            self.selected_id = None
        self._refresh_all()
        self.project_changed.emit()
        self.notify.emit("已删除页面", "success")

    # ---------- 对比原图 ----------
    def _show_original(self) -> None:
        page = self._current_page()
        if page is None:
            return
        if self._compare_pixmap is None:
            self._compare_pixmap = load_pixmap(str(self.project.root / page.source), page.rotation)
        if self._compare_pixmap.isNull():
            return
        self._compare_active = True
        self.compare_button.setText("正在查看原图")
        self.preview.set_pixmap(self._compare_pixmap, reset_view=False)

    def _hide_original(self) -> None:
        page = self._current_page()
        if page is None or not self._compare_active:
            return
        self._compare_active = False
        self.compare_button.setText("按住对比原图")
        pixmap = load_pixmap(str(self.project.root / page.processed), page.rotation)
        self.preview.set_pixmap(pixmap, reset_view=False)

    # ---------- 导出 ----------
    def _show_export_menu(self) -> None:
        if not self.project.pages:
            return
        tokens = theme_manager.tokens
        menu = QMenu(self)
        images_action = menu.addAction(
            render_icon("image", tokens.text, 15), "导出图片（PNG / TIFF 无损）"
        )
        pdf_action = menu.addAction(
            render_icon("file-text", tokens.text, 15), "导出多页 PDF"
        )
        chosen = menu.exec(
            self.export_button.mapToGlobal(QPoint(0, self.export_button.height() + 6))
        )
        if chosen == images_action:
            self._open_export("images")
        elif chosen == pdf_action:
            self._open_export("pdf")

    def _open_export(self, mode: str) -> None:
        selected = [page for page in self.project.pages if page.id in self.checked_ids]
        dialog = ExportDialog(
            mode,
            self.project.name,
            len(self.project.pages),
            len(selected),
            self.window(),
        )
        if dialog.exec() != ExportDialog.Accepted:
            return
        pages = selected if dialog.scope == "selected" and selected else list(self.project.pages)
        destination = dialog.destination()
        image_format = dialog.image_format()
        project = self.project
        library = self.library

        if mode == "images":
            def job(progress):
                return library.export_images(project, pages, destination, image_format, progress)

            title, subtitle = "正在导出图片", "以无损格式写入 PNG / TIFF 文件…"
        else:
            def job(progress):
                return library.export_pdf(project, pages, destination, 300, progress)

            title, subtitle = "正在导出 PDF", "以无损方式嵌入原图并生成多页文档…"

        dialog = ProgressDialog(title, subtitle, self.window())
        dialog.set_progress(0, len(pages))

        def finished(result):
            label = "PDF" if mode == "pdf" else image_format
            self.notify.emit(f"已导出 {len(pages)} 页 · {label}", "success")

        self._start_task(job, dialog, finished, "导出失败")

    # ---------- 后台任务 ----------
    def _start_task(self, job, dialog: ProgressDialog, on_done, error_title: str) -> None:
        if self._worker is not None:
            return
        worker = TaskWorker(job, self)
        self._worker = worker
        worker.progress.connect(dialog.set_progress)
        worker.done.connect(lambda result: self._task_done(dialog, result, on_done))
        worker.failed.connect(lambda message: self._task_failed(dialog, error_title, message))
        dialog.show()
        QTimer.singleShot(60, worker.start)

    def _task_done(self, dialog: ProgressDialog, result, callback) -> None:
        dialog.finish()
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()
        try:
            callback(result)
        except Exception as exc:  # noqa: BLE001
            self.notify.emit(f"刷新界面失败：{exc}", "error")

    def _task_failed(self, dialog: ProgressDialog, title: str, message: str) -> None:
        dialog.finish()
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()
        self.notify.emit(f"{title}：{message}", "error")

    # ---------- 主题 ----------
    def refresh_theme(self) -> None:
        tokens = theme_manager.tokens
        for button, icon_name, size, color_attr in self._icon_refs:
            if button is self.export_button and not button.isEnabled():
                color = tokens.text_muted
            else:
                color = getattr(tokens, color_attr)
            button.setIcon(render_icon(icon_name, color, size))
        for option in self.mode_options.values():
            option.refresh_theme()
        for thumb in self._thumb_widgets.values():
            thumb.refresh_theme()
            thumb.update()
        self.empty_icon.setPixmap(render_icon("scan", tokens.primary, 30))
        self.batch_delete_button.setIcon(render_icon("trash", tokens.danger, 14))
        self.empty_icon_frame.setStyleSheet(
            f"QFrame#IconCircle {{ background-color: {tokens.primary_soft}; border-radius: 34px; }}"
        )
        self.tip_card.setStyleSheet(
            f"QFrame#TipCard {{ background-color: {tokens.surface_alt}; "
            f"border: 1px solid {tokens.border}; border-radius: 10px; }}"
        )
        for label in self.info_labels.values():
            label.set_color(tokens.text_secondary)
        if self.compare_button.isDown():
            self.compare_button.setText("正在查看原图")
        else:
            self.compare_button.setText("按住对比原图")
        self.preview.update()

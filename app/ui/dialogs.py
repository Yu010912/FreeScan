"""自定义无边框对话框：新建/重命名、确认、导出、关于。"""
from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
)

from .. import __github__, __version__
from ..core.imaging import DEFAULT_OPTIONS, normalize_options
from ..core.theme import theme_manager
from .icons import logo_pixmap, render_icon
from .widgets import ElidedLabel, divider, make_icon_label


class FramelessDialog(QDialog):
    def __init__(self, title: str, width: int = 480, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self._width = width
        self._tokens = theme_manager.tokens

        self.card = QFrame(self)
        self.card.setObjectName("Card")
        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 95 if self._tokens.dark else 50))
        self.card.setGraphicsEffect(shadow)

        self.body = QVBoxLayout(self.card)
        self.body.setContentsMargins(24, 20, 24, 20)
        self.body.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(10)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("DialogTitle")
        header.addWidget(self.title_label, 1)
        self.close_button = QPushButton()
        self.close_button.setObjectName("IconBtn")
        self.close_button.setFixedSize(30, 30)
        self.close_button.setCursor(Qt.PointingHandCursor)
        self.close_button.setIcon(render_icon("x", self._tokens.text_muted, 16))
        self.close_button.setIconSize(QSize(16, 16))
        self.close_button.clicked.connect(self.reject)
        header.addWidget(self.close_button, 0, Qt.AlignTop)
        self.body.addLayout(header)

    def add_subtitle(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("Subtitle")
        label.setWordWrap(True)
        self.body.addWidget(label)
        return label

    def finalize(self, height: int) -> None:
        self.setFixedSize(self._width, height)
        self.card.setGeometry(12, 12, self._width - 24, height - 24)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        screen = QGuiApplication.primaryScreen()
        parent = self.parentWidget()
        if parent:
            center = parent.mapToGlobal(parent.rect().center())
        elif screen:
            center = screen.availableGeometry().center()
        else:
            return
        self.move(center - self.rect().center())


class TextInputDialog(FramelessDialog):
    def __init__(
        self,
        title: str,
        subtitle: str,
        initial: str = "",
        placeholder: str = "",
        confirm_text: str = "确定",
        parent=None,
    ) -> None:
        super().__init__(title, 460, parent)
        self.add_subtitle(subtitle)

        self.input = QLineEdit()
        self.input.setText(initial)
        self.input.setPlaceholderText(placeholder)
        self.input.setFixedHeight(40)
        self.input.setStyleSheet("font-size: 13px; padding: 6px 12px;")
        self.input.selectAll()
        self.body.addWidget(self.input)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet(f"color: {self._tokens.danger}; font-size: 11px;")
        self.error_label.setVisible(False)
        self.body.addWidget(self.error_label)

        self.body.addStretch(1)
        footer = QHBoxLayout()
        footer.addStretch(1)
        cancel = QPushButton("取消")
        cancel.setObjectName("Secondary")
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        footer.addWidget(cancel)
        self.confirm = QPushButton(confirm_text)
        self.confirm.setObjectName("Primary")
        self.confirm.setCursor(Qt.PointingHandCursor)
        self.confirm.setDefault(True)
        self.confirm.clicked.connect(self._accept)
        footer.addWidget(self.confirm)
        self.body.addLayout(footer)

        self.input.returnPressed.connect(self._accept)
        self.finalize(276)
        self.input.setFocus()

    def _accept(self) -> None:
        if not self.input.text().strip():
            self.error_label.setText("名称不能为空")
            self.error_label.setVisible(True)
            self.input.setFocus()
            return
        self.accept()

    def value(self) -> str:
        return self.input.text().strip()


class ConfirmDialog(FramelessDialog):
    def __init__(self, title: str, message: str, confirm_text: str = "删除", parent=None) -> None:
        super().__init__(title, 440, parent)
        subtitle = QLabel(message)
        subtitle.setObjectName("Subtitle")
        subtitle.setWordWrap(True)
        self.body.addWidget(subtitle)
        self.body.addStretch(1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        cancel = QPushButton("取消")
        cancel.setObjectName("Secondary")
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        footer.addWidget(cancel)
        self.confirm = QPushButton(confirm_text)
        self.confirm.setCursor(Qt.PointingHandCursor)
        confirm_color = "#FFFFFF" if not self._tokens.dark else "#2A0B0B"
        self.confirm.setStyleSheet(
            "QPushButton {"
            f"background-color: {self._tokens.danger};"
            f"color: {confirm_color};"
            "border: none; border-radius: 10px; min-height: 38px;"
            "padding: 0 16px; font-weight: 600;"
            "}"
        )
        self.confirm.clicked.connect(self.accept)
        footer.addWidget(self.confirm)
        self.body.addLayout(footer)
        self.finalize(238)


def _segment(options: List[Tuple[str, str]], checked: str = "") -> Tuple[QFrame, dict]:
    tokens = theme_manager.tokens
    frame = QFrame()
    frame.setObjectName("SegmentWrap")
    frame.setStyleSheet(
        f"QFrame#SegmentWrap {{ background-color: {tokens.surface_alt}; border-radius: 10px; }}"
    )
    layout = QHBoxLayout(frame)
    layout.setContentsMargins(3, 3, 3, 3)
    layout.setSpacing(3)
    group = QButtonGroup(frame)
    group.setExclusive(True)
    buttons = {}
    for value, label in options:
        button = QPushButton(label)
        button.setObjectName("Segment")
        button.setCheckable(True)
        button.setCursor(Qt.PointingHandCursor)
        if value == checked:
            button.setChecked(True)
        group.addButton(button)
        layout.addWidget(button, 1)
        buttons[value] = button
    return frame, buttons


class ExportDialog(FramelessDialog):
    def __init__(
        self,
        mode: str,
        project_name: str,
        page_count: int,
        selected_count: int,
        parent=None,
    ) -> None:
        title = "导出图片" if mode == "images" else "导出 PDF"
        super().__init__(title, 520, parent)
        self.mode = mode
        self.page_count = page_count
        self.selected_count = selected_count

        subtitle = (
            "逐页导出为无损图片，像素与原扫描稿完全一致。"
            if mode == "images"
            else "将全部扫描页合并为一份多页 PDF，无损嵌入原图。"
        )
        self.add_subtitle(subtitle)
        self.body.addWidget(divider())

        scope_label = QLabel("导出范围")
        scope_label.setObjectName("SectionTitle")
        self.body.addWidget(scope_label)
        self.scope_frame, self.scope_buttons = _segment(
            [
                ("all", f"全部页面 · {page_count}"),
                ("selected", f"已选页面 · {selected_count}"),
            ],
            "all",
        )
        self.body.addWidget(self.scope_frame)
        if selected_count <= 0:
            self.scope_buttons["selected"].setEnabled(False)
        self.scope = "all"

        self.format_buttons = {}
        if mode == "images":
            format_label = QLabel("图片格式")
            format_label.setObjectName("SectionTitle")
            self.body.addWidget(format_label)
            self.format_frame, self.format_buttons = _segment(
                [("PNG", "PNG · 无损"), ("TIFF", "TIFF · 无损")], "PNG"
            )
            self.body.addWidget(self.format_frame)
        else:
            info = QLabel("页面：A4 自动横竖版 · 原生像素 · 无损嵌入")
            info.setObjectName("Meta")
            self.body.addWidget(info)

        path_label = QLabel("输出位置")
        path_label.setObjectName("SectionTitle")
        self.body.addWidget(path_label)

        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        self.path_input = QLineEdit()
        self.path_input.setFixedHeight(36)
        path_row.addWidget(self.path_input, 1)
        browse = QPushButton("浏览")
        browse.setObjectName("Secondary")
        browse.setFixedHeight(36)
        browse.setCursor(Qt.PointingHandCursor)
        browse.clicked.connect(self._browse)
        path_row.addWidget(browse)
        self.body.addLayout(path_row)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet(f"color: {self._tokens.danger}; font-size: 11px;")
        self.error_label.setVisible(False)
        self.body.addWidget(self.error_label)

        hint = QLabel(
            "PNG / TIFF 均为无损格式，不会对像素重新编码。"
            if mode == "images"
            else "PDF 以 FlateDecode 无损压缩写入像素，不做 JPEG 重编码。"
        )
        hint.setObjectName("Meta")
        hint.setWordWrap(True)
        self.body.addWidget(hint)

        self.body.addStretch(1)
        footer = QHBoxLayout()
        footer.addStretch(1)
        cancel = QPushButton("取消")
        cancel.setObjectName("Secondary")
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        footer.addWidget(cancel)
        self.confirm = QPushButton("开始导出")
        self.confirm.setObjectName("Primary")
        self.confirm.setCursor(Qt.PointingHandCursor)
        self.confirm.setDefault(True)
        self.confirm.clicked.connect(self._accept)
        footer.addWidget(self.confirm)
        self.body.addLayout(footer)

        self._set_default_path(project_name)
        self.finalize(486 if mode == "images" else 440)

    def _set_default_path(self, project_name: str) -> None:
        safe = project_name.strip() or "FreeScan"
        documents = Path.home() / "Documents"
        if not documents.exists():
            documents = Path.home()
        if self.mode == "images":
            self.path_input.setText(str(documents / "FreeScan 导出" / safe))
        else:
            self.path_input.setText(str(documents / f"{safe}.pdf"))

    def _browse(self) -> None:
        current = self.path_input.text().strip()
        if self.mode == "images":
            folder = QFileDialog.getExistingDirectory(self, "选择导出文件夹", current or str(Path.home()))
            if folder:
                self.path_input.setText(folder)
        else:
            path, _ = QFileDialog.getSaveFileName(
                self,
                "保存 PDF",
                current or str(Path.home() / "扫描文档.pdf"),
                "PDF 文件 (*.pdf)",
            )
            if path:
                if not path.lower().endswith(".pdf"):
                    path += ".pdf"
                self.path_input.setText(path)

    def _accept(self) -> None:
        self.scope = (
            "selected" if self.scope_buttons.get("selected") and self.scope_buttons["selected"].isChecked() else "all"
        )
        path_text = self.path_input.text().strip()
        if not path_text:
            self.error_label.setText("请选择输出位置")
            self.error_label.setVisible(True)
            return
        if self.mode == "images":
            folder = Path(path_text)
            try:
                folder.mkdir(parents=True, exist_ok=True)
            except OSError:
                self.error_label.setText("无法创建输出文件夹，请检查路径权限")
                self.error_label.setVisible(True)
                return
        else:
            if not path_text.lower().endswith(".pdf"):
                path_text += ".pdf"
                self.path_input.setText(path_text)
            folder = Path(path_text).parent
            try:
                folder.mkdir(parents=True, exist_ok=True)
            except OSError:
                self.error_label.setText("无法创建输出目录，请检查路径权限")
                self.error_label.setVisible(True)
                return
        self.accept()

    def destination(self) -> Path:
        return Path(self.path_input.text().strip())

    def image_format(self) -> str:
        if self.format_buttons and self.format_buttons["TIFF"].isChecked():
            return "TIFF"
        return "PNG"


class AdjustDialog(FramelessDialog):
    """扫描参数滑条对话框。"""

    _SPECS = [
        ("shadow", "阴影去除", 0, 100, "抑制阴影与光照不均", "%"),
        ("whiten", "纸张提白", 0, 100, "让纸张背景更接近纯白", "%"),
        ("ink", "墨色加深", 0, 100, "让文字更黑、更清晰", "%"),
        ("brightness", "亮度", -50, 50, "整体提亮或压暗", ""),
        ("contrast", "对比度", -50, 50, "增强文字与纸张的反差", ""),
        ("inset", "边缘内缩", 0, 200, "0.00% - 2.00%，避免纸张外背景", "%"),
    ]

    def __init__(self, options=None, parent=None) -> None:
        super().__init__("扫描参数", 560, parent)
        self.add_subtitle("调整后会对当前页面重新处理；数值越大，对应效果越强。")
        self.body.addWidget(divider())

        current = normalize_options(options)
        self._sliders = {}
        for key, label, minimum, maximum, hint, suffix in self._SPECS:
            row = QHBoxLayout()
            row.setSpacing(10)
            name = QLabel(label)
            name.setObjectName("SliderName")
            name.setFixedWidth(76)
            name.setToolTip(hint)
            row.addWidget(name)

            slider = QSlider(Qt.Horizontal)
            slider.setRange(minimum, maximum)
            slider.setToolTip(hint)
            if key == "inset":
                slider.setValue(int(round(current[key] * 100)))
            else:
                slider.setValue(int(round(current[key])))
            row.addWidget(slider, 1)

            value_label = QLabel("")
            value_label.setObjectName("SliderValue")
            value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            value_label.setFixedWidth(58)
            row.addWidget(value_label)

            def update_value(value, label_widget=value_label, key_name=key, unit=suffix):
                if key_name == "inset":
                    label_widget.setText(f"{value / 100:.2f}%")
                elif unit:
                    label_widget.setText(f"{value}{unit}")
                elif value > 0:
                    label_widget.setText(f"+{value}")
                else:
                    label_widget.setText(str(value))

            slider.valueChanged.connect(update_value)
            update_value(slider.value())
            self.body.addLayout(row)
            self._sliders[key] = slider

        note = QLabel("提示：这些参数会随页面保存，导出时保留处理后的像素。")
        note.setObjectName("Meta")
        note.setWordWrap(True)
        self.body.addWidget(note)
        self.body.addStretch(1)

        footer = QHBoxLayout()
        reset = QPushButton("恢复默认")
        reset.setObjectName("Ghost")
        reset.setCursor(Qt.PointingHandCursor)
        reset.clicked.connect(self._reset)
        footer.addWidget(reset)
        footer.addStretch(1)
        cancel = QPushButton("取消")
        cancel.setObjectName("Secondary")
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        footer.addWidget(cancel)
        apply_button = QPushButton("应用参数")
        apply_button.setObjectName("Primary")
        apply_button.setCursor(Qt.PointingHandCursor)
        apply_button.clicked.connect(self.accept)
        footer.addWidget(apply_button)
        self.body.addLayout(footer)
        self.finalize(460)

    def _reset(self) -> None:
        for key, slider in self._sliders.items():
            value = DEFAULT_OPTIONS[key]
            if key == "inset":
                value = int(round(value * 100))
            slider.setValue(int(value))

    def values(self) -> dict:
        result = {}
        for key, slider in self._sliders.items():
            value = slider.value()
            result[key] = value / 100.0 if key == "inset" else float(value)
        return normalize_options(result)


class AboutDialog(FramelessDialog):
    def __init__(self, library_path: str, parent=None) -> None:
        super().__init__("关于 FreeScan", 540, parent)
        tokens = self._tokens
        self.title_label.setVisible(False)
        self.close_button.setVisible(False)

        top = QHBoxLayout()
        top.setSpacing(16)
        logo = QLabel()
        logo.setPixmap(logo_pixmap(54, tokens.primary_fill, tokens.on_primary))
        logo.setFixedSize(54, 54)
        top.addWidget(logo, 0, Qt.AlignTop)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        name = QLabel("FreeScan")
        name.setStyleSheet("font-size: 23px; font-weight: 700;")
        title_col.addWidget(name)
        tagline = QLabel("本地运行的智能图片扫描工具")
        tagline.setObjectName("Subtitle")
        title_col.addWidget(tagline)
        version = QLabel(f"版本 {__version__} · 免费非商用")
        version.setObjectName("Meta")
        title_col.addWidget(version)
        top.addLayout(title_col, 1)

        close = QPushButton()
        close.setObjectName("IconBtn")
        close.setFixedSize(30, 30)
        close.setCursor(Qt.PointingHandCursor)
        close.setIcon(render_icon("x", tokens.text_muted, 16))
        close.setIconSize(QSize(16, 16))
        close.clicked.connect(self.reject)
        top.addWidget(close, 0, Qt.AlignTop)
        self.body.addLayout(top)
        self.body.addWidget(divider())

        info_grid = QVBoxLayout()
        info_grid.setSpacing(8)
        info_grid.addLayout(self._info_row("作者", "Yu010912", "pen"))
        info_grid.addLayout(
            self._link_row("邮箱", "2206394025@qq.com", "mail", "mailto:2206394025@qq.com")
        )
        info_grid.addLayout(
            self._link_row(
                "GitHub",
                __github__.replace("https://", ""),
                "github",
                __github__,
            )
        )
        self.body.addLayout(info_grid)
        self.body.addWidget(divider())

        license_card = QFrame()
        license_card.setObjectName("Panel")
        license_card.setStyleSheet(
            f"QFrame#Panel {{ background-color: {tokens.surface_alt}; "
            f"border: 1px solid {tokens.border}; border-radius: 12px; }}"
        )
        license_layout = QVBoxLayout(license_card)
        license_layout.setContentsMargins(14, 12, 14, 12)
        license_layout.setSpacing(5)
        license_title = QLabel("许可协议 · CC BY-NC 4.0")
        license_title.setStyleSheet("font-size: 12px; font-weight: 700;")
        license_layout.addWidget(license_title)
        license_text = QLabel(
            "本软件仅供非商业用途使用。复制、分发或修改时，必须保留作者署名并注明来源"
            "（Yu010912 / FreeScan）。不得用于任何商业目的。"
        )
        license_text.setWordWrap(True)
        license_text.setStyleSheet(f"font-size: 11px; color: {tokens.text_secondary};")
        license_layout.addWidget(license_text)
        self.body.addWidget(license_card)

        tech = QLabel("技术栈：PySide6 · OpenCV · Pillow · pillow-heif · 自研无损 PDF 写入")
        tech.setObjectName("Meta")
        tech.setWordWrap(True)
        self.body.addWidget(tech)

        self.body.addStretch(1)
        footer = QHBoxLayout()
        path_label = ElidedLabel(f"项目库：{library_path}", tokens.text_muted)
        path_label.setStyleSheet("font-size: 11px;")
        path_label.setToolTip(library_path)
        footer.addWidget(path_label, 1)
        open_folder = QPushButton("打开项目库")
        open_folder.setObjectName("Ghost")
        open_folder.setCursor(Qt.PointingHandCursor)
        open_folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(library_path)))
        footer.addWidget(open_folder)
        close_button = QPushButton("关闭")
        close_button.setObjectName("Primary")
        close_button.setCursor(Qt.PointingHandCursor)
        close_button.clicked.connect(self.accept)
        footer.addWidget(close_button)
        self.body.addLayout(footer)

        self.finalize(492)

    def _info_row(self, key: str, value: str, icon_name: str) -> QHBoxLayout:
        tokens = self._tokens
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(make_icon_label(icon_name, tokens.text_muted, 15), 0, Qt.AlignVCenter)
        key_label = QLabel(key)
        key_label.setObjectName("InfoKey")
        key_label.setFixedWidth(48)
        row.addWidget(key_label)
        value_label = QLabel(value)
        value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        value_label.setStyleSheet(f"font-size: 12px; color: {tokens.text};")
        row.addWidget(value_label, 1)
        return row

    def _link_row(self, key: str, value: str, icon_name: str, url: str) -> QHBoxLayout:
        tokens = self._tokens
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(make_icon_label(icon_name, tokens.text_muted, 15), 0, Qt.AlignVCenter)
        key_label = QLabel(key)
        key_label.setObjectName("InfoKey")
        key_label.setFixedWidth(48)
        row.addWidget(key_label)
        link = QLabel(
            f'<a href="{url}" style="color:{tokens.primary}; text-decoration:none;">{value}</a>'
        )
        link.setOpenExternalLinks(True)
        link.setTextInteractionFlags(Qt.TextBrowserInteraction)
        link.setStyleSheet("font-size: 12px;")
        row.addWidget(link, 1)
        return row

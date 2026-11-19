"""自绘 UI 组件：卡片、缩略图、开关、提示条、进度框等。"""
from __future__ import annotations

import time
from typing import Optional

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    Property,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFontMetrics,
    QImage,
    QImageReader,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPixmap,
    QTransform,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLayout,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from PIL import Image

from ..core.theme import ThemeManager, theme_manager
from .icons import render_icon


def _tokens():
    return theme_manager.tokens


def make_icon_label(name: str, color: str, size: int = 18) -> QLabel:
    label = QLabel()
    label.setPixmap(render_icon(name, color, size))
    label.setFixedSize(size, size)
    label.setAttribute(Qt.WA_TransparentForMouseEvents)
    return label


def divider() -> QFrame:
    line = QFrame()
    line.setObjectName("Divider")
    line.setFixedHeight(1)
    return line


def load_pixmap(path: str, rotation: int = 0, max_edge: int = 0) -> QPixmap:
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    if max_edge > 0:
        size = reader.size()
        if size.isValid() and max(size.width(), size.height()) > max_edge:
            reader.setScaledSize(size.scaled(max_edge, max_edge, Qt.KeepAspectRatio))
    image = reader.read()
    if image.isNull():
        try:
            from PIL.ImageQt import ImageQt

            from ..core import imaging

            pil_image = imaging.load_image(str(path))
            if max_edge > 0 and max(pil_image.size) > max_edge:
                pil_image.thumbnail((max_edge, max_edge), Image.LANCZOS)
            image = QImage(ImageQt(pil_image)).copy()
        except Exception:  # noqa: BLE001
            return QPixmap()
    pixmap = QPixmap.fromImage(image)
    if rotation % 360:
        pixmap = pixmap.transformed(QTransform().rotate(rotation), Qt.SmoothTransformation)
    return pixmap


def relative_time(iso_text: str) -> str:
    try:
        moment = time.strptime(iso_text, "%Y-%m-%dT%H:%M:%S")
    except Exception:  # noqa: BLE001
        return ""
    stamp = time.mktime(moment)
    now = time.time()
    delta = max(0.0, now - stamp)
    if delta < 60:
        return "刚刚"
    if delta < 3600:
        return f"{int(delta // 60)} 分钟前"
    if delta < 86400:
        return f"{int(delta // 3600)} 小时前"
    if delta < 86400 * 2:
        return "昨天"
    if delta < 86400 * 7:
        return f"{int(delta // 86400)} 天前"
    return time.strftime("%Y-%m-%d", moment)


class ElidedLabel(QLabel):
    """超出宽度自动省略的标签。"""

    def __init__(self, text: str = "", color: str = "", parent=None) -> None:
        super().__init__(text, parent)
        self._color = color
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def set_color(self, color: str) -> None:
        self._color = color
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.TextAntialiasing)
        metrics = QFontMetrics(self.font())
        text = metrics.elidedText(self.text(), Qt.ElideRight, max(0, self.width()))
        color = QColor(self._color) if self._color else self.palette().color(QPalette.WindowText)
        painter.setPen(color)
        painter.drawText(self.rect(), int(self.alignment()), text)


class ThumbnailView(QWidget):
    """圆角缩略图，支持 contain / cover 两种绘制方式。"""

    def __init__(
        self,
        radius: int = 8,
        cover: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._radius = radius
        self._cover = cover
        self._cover_anchor = "center"
        self._pixmap = QPixmap()
        self._placeholder = "image"
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def set_cover_anchor(self, anchor: str) -> None:
        self._cover_anchor = anchor
        self.update()

    def set_image(self, path: str, rotation: int = 0) -> None:
        self._pixmap = load_pixmap(path, rotation)
        self.update()

    def set_placeholder(self, icon_name: str = "image") -> None:
        self._pixmap = QPixmap()
        self._placeholder = icon_name
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        tokens = _tokens()

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        clip = QPainterPath()
        clip.addRoundedRect(rect, self._radius, self._radius)
        painter.fillPath(clip, QColor(tokens.surface_alt))

        if not self._pixmap.isNull():
            painter.save()
            painter.setClipPath(clip)
            target = self._target_rect(rect)
            painter.drawPixmap(target, self._pixmap, QRectF(self._pixmap.rect()))
            painter.restore()
            painter.setPen(QPen(QColor(tokens.border), 1))
            painter.drawPath(clip)
        else:
            icon = render_icon(self._placeholder, tokens.text_muted, 26)
            size = 26
            painter.drawPixmap(
                QRectF(
                    rect.center().x() - size / 2,
                    rect.center().y() - size / 2,
                    size,
                    size,
                ),
                icon,
                QRectF(icon.rect()),
            )

    def _target_rect(self, rect: QRectF) -> QRectF:
        pixmap = self._pixmap
        pw = max(1.0, float(pixmap.width()))
        ph = max(1.0, float(pixmap.height()))
        ratio = (max if self._cover else min)(rect.width() / pw, rect.height() / ph)
        width = pw * ratio
        height = ph * ratio
        if self._cover and self._cover_anchor == "top":
            y = rect.y()
        else:
            y = rect.y() + (rect.height() - height) / 2
        return QRectF(
            rect.x() + (rect.width() - width) / 2,
            y,
            width,
            height,
        )


class FlowLayout(QLayout):
    """自动换行的流式布局。"""

    def __init__(self, parent=None, margin: int = 0, spacing: int = 18) -> None:
        super().__init__(parent)
        self._items = []
        self._spacing = spacing
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item) -> None:  # noqa: N802
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):  # noqa: N802
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int):  # noqa: N802
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):  # noqa: N802
        return Qt.Orientations(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        margins = self.contentsMargins()
        effective = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x = effective.x()
        y = effective.y()
        line_height = 0

        for item in self._items:
            widget = item.widget()
            if widget is not None and widget.isHidden():
                continue
            hint = item.sizeHint()
            if widget is not None:
                minimum = widget.minimumSize()
                hint = QSize(max(hint.width(), minimum.width()), max(hint.height(), minimum.height()))
            next_x = x + hint.width() + self._spacing
            if next_x - self._spacing > effective.right() and line_height > 0:
                x = effective.x()
                y = y + line_height + self._spacing
                next_x = x + hint.width() + self._spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y() + margins.bottom()


class ProjectCard(QFrame):
    open_requested = Signal(object)
    rename_requested = Signal(object)
    delete_requested = Signal(object)

    def __init__(self, project, parent=None) -> None:
        super().__init__(parent)
        self.project = project
        self.setObjectName("ProjectCard")
        self.setFixedSize(296, 238)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)

        tokens = _tokens()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 12)
        layout.setSpacing(8)

        self.thumb = ThumbnailView(radius=10, cover=True)
        self.thumb.set_cover_anchor("top")
        self.thumb.setFixedHeight(150)
        cover = project.cover_path()
        if cover:
            self.thumb.set_image(str(cover))
        else:
            self.thumb.set_placeholder("file-text")
        layout.addWidget(self.thumb)

        row = QHBoxLayout()
        row.setContentsMargins(4, 0, 2, 0)
        row.setSpacing(4)
        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)

        self.title = ElidedLabel(project.name, tokens.text)
        self.title.setStyleSheet("font-size: 14px; font-weight: 600;")
        text_col.addWidget(self.title)

        meta = f"{project.page_count} 页 · {relative_time(project.updated_at)}"
        self.meta = QLabel(meta)
        self.meta.setObjectName("Meta")
        text_col.addWidget(self.meta)
        row.addLayout(text_col, 1)

        self.menu_button = QPushButton()
        self.menu_button.setObjectName("MenuBtn")
        self.menu_button.setFixedSize(26, 26)
        self.menu_button.setCursor(Qt.PointingHandCursor)
        self.menu_button.setIconSize(QSize(16, 16))
        self.menu_button.setIcon(render_icon("more", tokens.text_muted, 16))
        self.menu_button.clicked.connect(self._show_menu)
        row.addWidget(self.menu_button, 0, Qt.AlignTop)
        layout.addLayout(row)

    def _show_menu(self) -> None:
        from PySide6.QtWidgets import QMenu

        tokens = _tokens()
        menu = QMenu(self)
        open_action = menu.addAction(render_icon("folder", tokens.text, 15), "打开项目")
        rename_action = menu.addAction(render_icon("pen", tokens.text, 15), "重命名")
        menu.addSeparator()
        delete_action = menu.addAction(render_icon("trash", tokens.danger, 15), "删除项目")
        chosen = menu.exec(self.menu_button.mapToGlobal(QPoint(-10, self.menu_button.height() + 4)))
        if chosen == open_action:
            self.open_requested.emit(self.project)
        elif chosen == rename_action:
            self.rename_requested.emit(self.project)
        elif chosen == delete_action:
            self.delete_requested.emit(self.project)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton and self.rect().contains(event.pos()):
            self.open_requested.emit(self.project)
        super().mouseReleaseEvent(event)

    def refresh_theme(self) -> None:
        tokens = _tokens()
        self.title.set_color(tokens.text)
        self.menu_button.setIcon(render_icon("more", tokens.text_muted, 16))
        cover = self.project.cover_path()
        if cover:
            self.thumb.set_image(str(cover))
        else:
            self.thumb.set_placeholder("file-text")
        self.thumb.update()


class AddProjectCard(QFrame):
    clicked = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("AddCard")
        self.setFixedSize(296, 238)
        self.setCursor(Qt.PointingHandCursor)
        tokens = _tokens()

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(10)
        self.icon_label = make_icon_label("plus", tokens.primary, 26)
        self.icon_label.setFixedSize(44, 44)
        self.icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.icon_label, 0, Qt.AlignHCenter)
        title = QLabel("新建项目")
        title.setStyleSheet("font-size: 14px; font-weight: 600;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        hint = QLabel("导入图片，自动扫描为高清文档")
        hint.setObjectName("EmptyHint")
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def refresh_theme(self) -> None:
        self.icon_label.setPixmap(render_icon("plus", _tokens().primary, 26))


class SidebarItem(QFrame):
    clicked = Signal(str)

    def __init__(self, item_id: str, title: str, subtitle: str = "", icon_name: str = "folder", parent=None) -> None:
        super().__init__(parent)
        self.item_id = item_id
        self._icon_name = icon_name
        self.setObjectName("SidebarItem")
        self.setFixedHeight(44)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self._selected = False

        tokens = _tokens()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(9, 0, 9, 0)
        layout.setSpacing(9)

        self.icon_label = make_icon_label(icon_name, tokens.text_secondary, 16)
        layout.addWidget(self.icon_label)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(0)
        self.title_label = ElidedLabel(title, tokens.text)
        self.title_label.setStyleSheet("font-size: 12px; font-weight: 600;")
        text_col.addWidget(self.title_label)
        self.subtitle_label = ElidedLabel(subtitle, tokens.text_muted)
        self.subtitle_label.setStyleSheet("font-size: 10px;")
        self.subtitle_label.setVisible(bool(subtitle))
        text_col.addWidget(self.subtitle_label)
        layout.addLayout(text_col, 1)

        self.count_label = QLabel("")
        self.count_label.setObjectName("CountBadge")
        self.count_label.setVisible(False)
        layout.addWidget(self.count_label, 0, Qt.AlignVCenter)

    def set_selected(self, selected: bool) -> None:
        if self._selected == selected:
            return
        self._selected = selected
        self.setProperty("selected", "true" if selected else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        self.icon_label.setPixmap(
            render_icon(self._icon_name, _tokens().primary if selected else _tokens().text_secondary, 16)
        )

    def set_count(self, count: int) -> None:
        self.count_label.setText(str(count))
        self.count_label.setVisible(count > 0)

    def set_subtitle(self, text: str) -> None:
        self.subtitle_label.setText(text)
        self.subtitle_label.setVisible(bool(text))

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.item_id)
        super().mouseReleaseEvent(event)

    def refresh_theme(self) -> None:
        tokens = _tokens()
        self.title_label.set_color(tokens.text)
        self.subtitle_label.set_color(tokens.text_muted)
        self.icon_label.setPixmap(
            render_icon(self._icon_name, tokens.primary if self._selected else tokens.text_secondary, 16)
        )


class ThemeToggle(QAbstractButton):
    """浅色 / 深色主题切换开关（带滑动动画）。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(theme_manager.dark)
        self.setFixedSize(58, 30)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("切换浅色 / 深色主题")
        self._knob = 1.0 if theme_manager.dark else 0.0
        self._animation = QPropertyAnimation(self, b"knob", self)
        self._animation.setDuration(190)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._animate)

    def _get_knob(self) -> float:
        return self._knob

    def _set_knob(self, value: float) -> None:
        self._knob = float(value)
        self.update()

    knob = Property(float, _get_knob, _set_knob)

    def _animate(self, checked: bool) -> None:
        self._animation.stop()
        self._animation.setStartValue(self._knob)
        self._animation.setEndValue(1.0 if checked else 0.0)
        self._animation.start()

    def sync(self) -> None:
        self.blockSignals(True)
        self.setChecked(theme_manager.dark)
        self.blockSignals(False)
        self._animation.stop()
        self._knob = 1.0 if theme_manager.dark else 0.0
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        tokens = _tokens()

        track = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        painter.setBrush(QColor(tokens.primary_soft if self.isChecked() else tokens.surface_alt))
        painter.setPen(QPen(QColor(tokens.border), 1))
        painter.drawRoundedRect(track, 14.5, 14.5)

        knob_size = 24.0
        travel = self.width() - knob_size - 6.0
        x = 3.0 + travel * self._knob
        knob_rect = QRectF(x, 3.0, knob_size, knob_size)

        shadow = QColor(0, 0, 0, 28 if tokens.dark else 22)
        painter.setPen(Qt.NoPen)
        painter.setBrush(shadow)
        painter.drawEllipse(knob_rect.translated(0, 1))
        painter.setBrush(QColor(tokens.primary_fill if self.isChecked() else tokens.surface))
        painter.setPen(
            QPen(QColor(tokens.primary_fill_hover if self.isChecked() else tokens.border_strong), 1)
        )
        painter.drawEllipse(knob_rect)

        icon_name = "moon" if self.isChecked() else "sun"
        icon_color = tokens.on_primary if self.isChecked() else tokens.accent
        icon = render_icon(icon_name, icon_color, 13)
        painter.drawPixmap(
            QRectF(knob_rect.center().x() - 6.5, knob_rect.center().y() - 6.5, 13, 13),
            icon,
            QRectF(icon.rect()),
        )


class ToggleCheck(QAbstractButton):
    """自绘复选框。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(18, 18)
        self.setCursor(Qt.PointingHandCursor)
        self._hover = False

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        tokens = _tokens()
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        if self.isChecked():
            painter.setBrush(QColor(tokens.primary_fill))
            painter.setPen(QPen(QColor(tokens.primary_fill), 1))
            painter.drawRoundedRect(rect, 5, 5)
            icon = render_icon("check", tokens.on_primary, 12, stroke=2.6)
            painter.drawPixmap(QRectF(3, 3, 12, 12), icon, QRectF(icon.rect()))
        else:
            painter.setBrush(QColor(tokens.surface))
            pen = QPen(QColor(tokens.primary if self._hover else tokens.border_strong), 1.3)
            painter.setPen(pen)
            painter.drawRoundedRect(rect, 5, 5)
        if self.isChecked():
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(tokens.primary_fill), 1))
            painter.drawRoundedRect(rect, 5, 5)


class Spinner(QWidget):
    def __init__(self, size: int = 36, parent=None) -> None:
        super().__init__(parent)
        self._angle = 0
        self.setFixedSize(size, size)
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

    def start(self) -> None:
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _tick(self) -> None:
        self._angle = (self._angle + 7) % 360
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        tokens = _tokens()
        rect = QRectF(self.rect()).adjusted(3, 3, -3, -3)
        track = QPen(QColor(tokens.border), 3)
        track.setCapStyle(Qt.RoundCap)
        painter.setPen(track)
        painter.drawArc(rect, 0, 360 * 16)
        pen = QPen(QColor(tokens.primary), 3)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawArc(rect, -self._angle * 16, 110 * 16)


class PageThumb(QFrame):
    clicked = Signal(str)
    checked_changed = Signal(str, bool)

    def __init__(self, page, index: int, parent=None) -> None:
        super().__init__(parent)
        self.page = page
        self.page_id = page.id
        self.setObjectName("PageThumb")
        self.setFixedSize(148, 178)
        self.setCursor(Qt.PointingHandCursor)
        self.setProperty("selected", "false")
        self.setAttribute(Qt.WA_Hover, True)

        tokens = _tokens()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 6)
        layout.setSpacing(4)

        self.thumb = ThumbnailView(radius=7)
        self.thumb.setFixedHeight(132)
        layout.addWidget(self.thumb)

        self.reload_image()

        footer = QHBoxLayout()
        footer.setContentsMargins(4, 0, 4, 0)
        footer.setSpacing(4)
        self.index_label = QLabel(f"{index:02d}")
        self.index_label.setStyleSheet(
            "font-size: 10px; font-weight: 600;"
        )
        self.index_label.setObjectName("MetaStrong")
        footer.addWidget(self.index_label)
        footer.addStretch(1)
        self.mode_label = QLabel({"original": "原图", "enhance": "增强", "bw": "黑白"}.get(page.mode, "增强"))
        self.mode_label.setObjectName("Meta")
        footer.addWidget(self.mode_label)
        layout.addLayout(footer)

        self.checkbox = ToggleCheck(self.thumb)
        self.checkbox.move(6, 6)
        self.checkbox.toggled.connect(lambda value: self.checked_changed.emit(self.page_id, value))

    def reload_image(self) -> None:
        self.thumb.set_image(self._thumb_path(), self.page.rotation)

    def _thumb_path(self) -> str:
        # 缩略图路径由父级在创建时注入
        return getattr(self, "_thumb_abs", "")

    def set_thumb_path(self, path: str) -> None:
        self._thumb_abs = path
        self.reload_image()

    def set_index(self, index: int) -> None:
        self.index_label.setText(f"{index:02d}")

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", "true" if selected else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def set_checked(self, checked: bool) -> None:
        self.checkbox.setChecked(checked)

    def is_checked(self) -> bool:
        return self.checkbox.isChecked()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton and not self.checkbox.geometry().contains(
            self.thumb.mapFrom(self, event.pos())
        ):
            self.clicked.emit(self.page_id)
        super().mouseReleaseEvent(event)

    def refresh_theme(self) -> None:
        self.reload_image()


class Toast(QFrame):
    """底部居中浮层提示。"""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setObjectName("Toast")
        self.setVisible(False)
        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(0.0)
        self.setGraphicsEffect(self._effect)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 16, 10)
        layout.setSpacing(9)
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(16, 16)
        layout.addWidget(self.icon_label)
        self.text_label = QLabel()
        self.text_label.setStyleSheet("font-size: 12px; font-weight: 500;")
        self.text_label.setMaximumWidth(460)
        self.text_label.setWordWrap(False)
        layout.addWidget(self.text_label)

        self._fade_in = QPropertyAnimation(self._effect, b"opacity", self)
        self._fade_in.setDuration(160)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_out = QPropertyAnimation(self._effect, b"opacity", self)
        self._fade_out.setDuration(240)
        self._fade_out.finished.connect(self.hide)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._start_hide)

        parent.installEventFilter(self)

    def eventFilter(self, obj, event):  # noqa: N802
        if obj is self.parentWidget() and event.type() == QEvent.Resize and self.isVisible():
            self.reposition()
        return super().eventFilter(obj, event)

    def show_message(self, text: str, kind: str = "success", duration: int = 2800) -> None:
        tokens = _tokens()
        color = tokens.primary if kind == "success" else tokens.danger
        icon_name = "check" if kind == "success" else "alert-circle"
        self.icon_label.setPixmap(render_icon(icon_name, color, 16))
        self.text_label.setText(text)
        self.setStyleSheet(
            "QFrame#Toast {"
            f"background-color: {tokens.surface};"
            f"border: 1px solid {tokens.border};"
            "border-radius: 12px;"
            "}"
            f"QLabel {{ color: {tokens.text}; }}"
        )
        self.adjustSize()
        self.reposition()
        self.show()
        self.raise_()
        self._timer.stop()
        self._fade_out.stop()
        self._fade_in.stop()
        self._effect.setOpacity(0.0)
        self._fade_in.start()
        self._timer.start(duration)

    def reposition(self) -> None:
        parent = self.parentWidget()
        if not parent:
            return
        self.adjustSize()
        x = max(16, (parent.width() - self.width()) // 2)
        y = parent.height() - self.height() - 26
        self.move(x, y)

    def _start_hide(self) -> None:
        self._fade_out.stop()
        self._fade_out.setStartValue(self._effect.opacity())
        self._fade_out.setEndValue(0.0)
        self._fade_out.start()


class ProgressDialog(QDialog):
    """无边框进度对话框，用于导入扫描与导出。"""

    def __init__(self, title: str, subtitle: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedSize(420, 188)
        self._allow_close = False

        tokens = _tokens()
        card = QFrame(self)
        card.setObjectName("Card")
        card.setGeometry(10, 10, self.width() - 20, self.height() - 20)
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(38)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 90 if tokens.dark else 55))
        card.setGraphicsEffect(shadow)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)

        top = QHBoxLayout()
        top.setSpacing(14)
        self.spinner = Spinner(38)
        top.addWidget(self.spinner, 0, Qt.AlignTop)
        text_col = QVBoxLayout()
        text_col.setSpacing(3)
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-size: 15px; font-weight: 700;")
        text_col.addWidget(self.title_label)
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("Meta")
        self.subtitle_label.setWordWrap(True)
        text_col.addWidget(self.subtitle_label)
        top.addLayout(text_col, 1)
        layout.addLayout(top)

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.percent_label = QLabel("0%")
        self.percent_label.setObjectName("Meta")
        self.percent_label.setAlignment(Qt.AlignRight)
        layout.addWidget(self.percent_label)
        layout.addStretch(1)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.spinner.start()
        parent = self.parentWidget()
        if parent:
            center = parent.mapToGlobal(parent.rect().center())
            self.move(center - self.rect().center())

    def closeEvent(self, event) -> None:  # noqa: N802
        if not self._allow_close:
            event.ignore()
            return
        self.spinner.stop()
        super().closeEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key_Escape:
            event.ignore()
            return
        super().keyPressEvent(event)

    def set_progress(self, current: int, total: int, text: str = "") -> None:
        total = max(1, total)
        percent = int(current * 100 / total)
        self.progress.setValue(percent)
        self.percent_label.setText(f"{percent}%")
        if text:
            self.subtitle_label.setText(text)

    def set_indeterminate(self) -> None:
        self.progress.setRange(0, 0)
        self.percent_label.setText("")

    def finish(self) -> None:
        self._allow_close = True
        self.spinner.stop()
        self.close()


class ModeOption(QFrame):
    clicked = Signal(str)

    def __init__(self, mode: str, title: str, hint: str, icon_name: str, parent=None) -> None:
        super().__init__(parent)
        self.mode = mode
        self._icon_name = icon_name
        self.setObjectName("ModeOption")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(52)
        self.setProperty("selected", "false")

        tokens = _tokens()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(9)

        self.icon_label = make_icon_label(icon_name, tokens.text_secondary, 18)
        layout.addWidget(self.icon_label)

        text_col = QVBoxLayout()
        text_col.setSpacing(0)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("ModeTitle")
        text_col.addWidget(self.title_label)
        self.hint_label = QLabel(hint)
        self.hint_label.setObjectName("ModeHint")
        text_col.addWidget(self.hint_label)
        layout.addLayout(text_col, 1)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", "true" if selected else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        self.icon_label.setPixmap(
            render_icon(self._icon_name, _tokens().primary if selected else _tokens().text_secondary, 18)
        )

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.mode)
        super().mouseReleaseEvent(event)

    def refresh_theme(self) -> None:
        tokens = _tokens()
        selected = self.property("selected") == "true"
        self.icon_label.setPixmap(
            render_icon(self._icon_name, tokens.primary if selected else tokens.text_secondary, 18)
        )

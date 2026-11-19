"""可缩放 / 平移的文档预览画布。"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPointF, QRectF, QSizeF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from ..core.theme import theme_manager
from .icons import render_icon


class PreviewCanvas(QWidget):
    zoom_changed = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._pixmap = QPixmap()
        self._image_size = QSizeF(0, 0)
        self._scale = 1.0
        self._fit_scale = 1.0
        self._offset = QPointF(0, 0)
        self._dragging = False
        self._drag_origin = QPointF()
        self._offset_origin = QPointF(0, 0)
        self._bottom_reserve = 0.0
        self.setMouseTracking(True)
        self.setCursor(Qt.ArrowCursor)
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)

    def set_bottom_reserve(self, value: float) -> None:
        self._bottom_reserve = float(value)
        self.update()

    # ---------- 数据 ----------
    def set_pixmap(self, pixmap: QPixmap, reset_view: bool = True) -> None:
        self._pixmap = pixmap
        dpr = pixmap.devicePixelRatio() or 1.0
        self._image_size = QSizeF(pixmap.width() / dpr, pixmap.height() / dpr)
        if reset_view:
            self.fit_view()
        else:
            self.update()

    def clear(self) -> None:
        self._pixmap = QPixmap()
        self._image_size = QSizeF(0, 0)
        self.update()

    def has_image(self) -> bool:
        return not self._pixmap.isNull()

    # ---------- 视图 ----------
    def _padding(self) -> float:
        return 34.0

    def fit_view(self) -> None:
        if self._image_size.isEmpty():
            self._scale = 1.0
            self._offset = QPointF(0, 0)
            self.update()
            return
        available_w = max(1.0, self.width() - self._padding() * 2)
        available_h = max(1.0, self.height() - self._padding() * 2 - self._bottom_reserve)
        self._fit_scale = min(available_w / self._image_size.width(), available_h / self._image_size.height())
        self._fit_scale = max(0.02, self._fit_scale)
        self._scale = self._fit_scale
        self._center_image()
        self.zoom_changed.emit(int(round(self._scale * 100)))
        self.update()

    def _center_image(self) -> None:
        self._offset = QPointF(
            (self.width() - self._image_size.width() * self._scale) / 2,
            (self.height() - self._image_size.height() * self._scale) / 2,
        )

    def zoom_in(self) -> None:
        self._zoom_at(1.2, QPointF(self.width() / 2, self.height() / 2))

    def zoom_out(self) -> None:
        self._zoom_at(1 / 1.2, QPointF(self.width() / 2, self.height() / 2))

    def _zoom_at(self, factor: float, anchor: QPointF) -> None:
        if self._image_size.isEmpty():
            return
        new_scale = max(0.02, min(8.0, self._scale * factor))
        if abs(new_scale - self._scale) < 1e-6:
            return
        image_point = (anchor - self._offset) / self._scale
        self._scale = new_scale
        self._offset = anchor - image_point * self._scale
        self.zoom_changed.emit(int(round(self._scale * 100)))
        self._clamp_offset()
        self.update()

    def _clamp_offset(self) -> None:
        image_w = self._image_size.width() * self._scale
        image_h = self._image_size.height() * self._scale
        margin = 90.0
        min_x = min(margin - image_w, (self.width() - image_w) / 2)
        max_x = max(self.width() - margin, (self.width() - image_w) / 2)
        min_y = min(margin - image_h, (self.height() - image_h) / 2)
        max_y = max(self.height() - margin, (self.height() - image_h) / 2)
        x = min(max(self._offset.x(), min_x), max_x)
        y = min(max(self._offset.y(), min_y), max_y)
        self._offset = QPointF(x, y)

    # ---------- 事件 ----------
    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self.has_image():
            self.fit_view()

    def wheelEvent(self, event) -> None:  # noqa: N802
        if not self.has_image():
            return
        steps = event.angleDelta().y() / 120.0
        if steps == 0:
            return
        self._zoom_at(1.14 ** steps, QPointF(event.position()))
        event.accept()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton and self.has_image():
            self._dragging = True
            self._drag_origin = QPointF(event.position())
            self._offset_origin = QPointF(self._offset)
            self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._dragging:
            delta = QPointF(event.position()) - self._drag_origin
            self._offset = self._offset_origin + delta
            self._clamp_offset()
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._dragging = False
            self.setCursor(Qt.OpenHandCursor if self.has_image() else Qt.ArrowCursor)
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.fit_view()
        super().mouseDoubleClickEvent(event)

    def enterEvent(self, event) -> None:  # noqa: N802
        if self.has_image():
            self.setCursor(Qt.OpenHandCursor)
        super().enterEvent(event)

    # ---------- 绘制 ----------
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        tokens = theme_manager.tokens

        outer = QRectF(self.rect())
        clip = QPainterPath()
        clip.addRoundedRect(outer.adjusted(0.5, 0.5, -0.5, -0.5), 14, 14)
        painter.fillPath(clip, QColor(tokens.canvas))

        painter.save()
        painter.setClipPath(clip)
        self._paint_dots(painter, outer, QColor(tokens.canvas_dot))
        painter.restore()

        painter.setPen(QPen(QColor(tokens.border), 1))
        painter.drawPath(clip)

        if self._pixmap.isNull():
            icon = render_icon("image-plus", tokens.text_muted, 34)
            painter.drawPixmap(
                QRectF(outer.center().x() - 17, outer.center().y() - 34, 34, 34),
                icon,
                QRectF(icon.rect()),
            )
            painter.setPen(QColor(tokens.text_muted))
            font = painter.font()
            font.setPixelSize(12)
            painter.setFont(font)
            painter.drawText(
                QRectF(0, outer.center().y() + 8, outer.width(), 24),
                Qt.AlignHCenter | Qt.AlignTop,
                "导入图片后在此预览",
            )
            return

        image_rect = QRectF(
            self._offset,
            QSizeF(
                self._image_size.width() * self._scale,
                self._image_size.height() * self._scale,
            ),
        )

        painter.save()
        painter.setClipPath(clip)
        shadow = QColor(0, 0, 0, 26 if tokens.dark else 18)
        for step in range(8, 0, -1):
            painter.setBrush(shadow)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(image_rect.adjusted(-step, -step + 5, step, step + 5), 4, 4)

        image_clip = QPainterPath()
        image_clip.addRoundedRect(image_rect, 3, 3)
        painter.setClipPath(image_clip)
        painter.drawPixmap(image_rect, self._pixmap, QRectF(self._pixmap.rect()))
        painter.restore()

        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(tokens.border_strong), 1))
        painter.drawRoundedRect(image_rect, 3, 3)

    def _paint_dots(self, painter: QPainter, rect: QRectF, color: QColor) -> None:
        spacing = 24
        radius = 1.1
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        y = rect.top() + 12
        while y < rect.bottom():
            x = rect.left() + 12
            while x < rect.right():
                painter.drawEllipse(QPointF(x, y), radius, radius)
                x += spacing
            y += spacing

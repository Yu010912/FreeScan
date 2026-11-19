"""内联 SVG 图标（Lucide 风格），按主题色实时渲染。"""
from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_ICONS = {
    "scan": (
        '<path d="M3 7V5a2 2 0 0 1 2-2h2"/>'
        '<path d="M17 3h2a2 2 0 0 1 2 2v2"/>'
        '<path d="M21 17v2a2 2 0 0 1-2 2h-2"/>'
        '<path d="M7 21H5a2 2 0 0 1-2-2v-2"/>'
        '<path d="M7 12h10"/>'
    ),
    "folder": (
        '<path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9'
        'A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>'
    ),
    "folder-plus": (
        '<path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9'
        'A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>'
        '<path d="M12 10v6"/><path d="M9 13h6"/>'
    ),
    "plus": '<path d="M5 12h14"/><path d="M12 5v14"/>',
    "sun": (
        '<circle cx="12" cy="12" r="4"/>'
        '<path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/>'
        '<path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/>'
        '<path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>'
    ),
    "moon": '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
    "upload": (
        '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
        '<path d="m17 8-5-5-5 5"/><path d="M12 3v12"/>'
    ),
    "download": (
        '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
        '<path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>'
    ),
    "image": (
        '<rect width="18" height="18" x="3" y="3" rx="2" ry="2"/>'
        '<circle cx="9" cy="9" r="2"/>'
        '<path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>'
    ),
    "image-plus": (
        '<path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7"/>'
        '<path d="M16 5h6"/><path d="M19 2v6"/>'
        '<path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>'
        '<circle cx="9" cy="9" r="2"/>'
    ),
    "file-text": (
        '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
        '<path d="M14 2v6h6"/><path d="M8 13h8"/><path d="M8 17h5"/>'
    ),
    "trash": (
        '<path d="M3 6h18"/>'
        '<path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>'
        '<path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>'
        '<path d="M10 11v6"/><path d="M14 11v6"/>'
    ),
    "rotate-ccw": '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/>',
    "rotate-cw": '<path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/>',
    "zoom-in": (
        '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>'
        '<path d="M11 8v6"/><path d="M8 11h6"/>'
    ),
    "zoom-out": (
        '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>'
        '<path d="M8 11h6"/>'
    ),
    "fit": (
        '<path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M21 8V5a2 2 0 0 0-2-2h-3"/>'
        '<path d="M3 16v3a2 2 0 0 0 2 2h3"/><path d="M16 21h3a2 2 0 0 0 2-2v-3"/>'
    ),
    "eye": (
        '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"/>'
        '<circle cx="12" cy="12" r="3"/>'
    ),
    "chevron-left": '<path d="m15 18-6-6 6-6"/>',
    "chevron-right": '<path d="m9 18 6-6-6-6"/>',
    "chevron-up": '<path d="m18 15-6-6-6 6"/>',
    "chevron-down": '<path d="m6 9 6 6 6-6"/>',
    "arrow-left": '<path d="m12 19-7-7 7-7"/><path d="M19 12H5"/>',
    "more": (
        '<circle cx="5" cy="12" r="1.6" fill="{color}" stroke="none"/>'
        '<circle cx="12" cy="12" r="1.6" fill="{color}" stroke="none"/>'
        '<circle cx="19" cy="12" r="1.6" fill="{color}" stroke="none"/>'
    ),
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "x": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "sparkles": (
        '<path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21'
        'l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/>'
        '<path d="M19 3v4"/><path d="M21 5h-4"/>'
    ),
    "github": (
        '<path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 5-2 5-5.5.08-1.25-.27-2.48-1-3.5'
        '.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2'
        'c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 2 5.5 5 5.5'
        '-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4"/>'
        '<path d="M9 18c-4.51 2-5-2-7-2"/>'
    ),
    "mail": (
        '<rect width="20" height="16" x="2" y="4" rx="2"/>'
        '<path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>'
    ),
    "hard-drive": (
        '<path d="M22 12H2"/>'
        '<path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89'
        'A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11Z"/>'
        '<path d="M6 16h.01"/><path d="M10 16h.01"/>'
    ),
    "alert-circle": (
        '<circle cx="12" cy="12" r="9"/><path d="M12 8v4"/><path d="M12 16h.01"/>'
    ),
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 16v-5"/><path d="M12 8h.01"/>',
    "external-link": (
        '<path d="M15 3h6v6"/><path d="M10 14 21 3"/>'
        '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>'
    ),
    "pen": '<path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/>',
    "layers": (
        '<path d="m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91'
        'a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z"/>'
        '<path d="m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65"/>'
        '<path d="m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65"/>'
    ),
    "check-square": (
        '<rect width="18" height="18" x="3" y="3" rx="4"/>'
        '<path d="m9 12 2 2 4-4"/>'
    ),
    "maximize": (
        '<path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M21 8V5a2 2 0 0 0-2-2h-3"/>'
        '<path d="M3 16v3a2 2 0 0 0 2 2h3"/><path d="M16 21h3a2 2 0 0 0 2-2v-3"/>'
    ),
    "sliders": (
        '<path d="M4 21v-7"/><path d="M4 10V3"/><path d="M12 21v-9"/>'
        '<path d="M12 8V3"/><path d="M20 21v-5"/><path d="M20 12V3"/>'
        '<path d="M1 14h6"/><path d="M9 8h6"/><path d="M17 16h6"/>'
    ),
    "type": '<path d="M4 7V4h16v3"/><path d="M9 20h6"/><path d="M12 4v16"/>',
    "contrast": (
        '<circle cx="12" cy="12" r="9"/><path d="M12 3v18"/>'
    ),
    "loader": '<path d="M21 12a9 9 0 1 1-6.2-8.6"/>',
}


@lru_cache(maxsize=512)
def render_icon(name: str, color: str, size: int = 20, stroke: float = 1.8) -> QPixmap:
    body = _ICONS.get(name, _ICONS["info"]).replace("{color}", color)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" '
        f'stroke-linejoin="round">{body}</svg>'
    )
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    ratio = 2.0
    image = QImage(int(size * ratio), int(size * ratio), QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter)
    painter.end()
    pixmap = QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(ratio)
    return pixmap


def icon(name: str, color: str, size: int = 20) -> QIcon:
    return QIcon(render_icon(name, color, size))


def logo_pixmap(size: int, background: str, foreground: str) -> QPixmap:
    """绘制 FreeScan 品牌图标：圆角方块 + 扫描框。"""
    ratio = 2.0
    image = QImage(int(size * ratio), int(size * ratio), QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)

    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor, QPainterPath, QPen

    rect = QRectF(0, 0, size * ratio, size * ratio)
    path = QPainterPath()
    path.addRoundedRect(rect, size * ratio * 0.28, size * ratio * 0.28)
    painter.fillPath(path, QColor(background))

    pen = QPen(QColor(foreground))
    pen.setWidthF(size * ratio * 0.085)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    pad = size * ratio * 0.29
    corner = size * ratio * 0.16
    inner = rect.adjusted(pad, pad, -pad, -pad)
    painter.drawLine(inner.left(), inner.top() + corner, inner.left(), inner.top())
    painter.drawLine(inner.left(), inner.top(), inner.left() + corner, inner.top())
    painter.drawLine(inner.right() - corner, inner.top(), inner.right(), inner.top())
    painter.drawLine(inner.right(), inner.top(), inner.right(), inner.top() + corner)
    painter.drawLine(inner.left(), inner.bottom() - corner, inner.left(), inner.bottom())
    painter.drawLine(inner.left(), inner.bottom(), inner.left() + corner, inner.bottom())
    painter.drawLine(inner.right() - corner, inner.bottom(), inner.right(), inner.bottom())
    painter.drawLine(inner.right(), inner.bottom(), inner.right(), inner.bottom() - corner)

    scan_pen = QPen(QColor(foreground))
    scan_pen.setWidthF(size * ratio * 0.075)
    scan_pen.setCapStyle(Qt.RoundCap)
    painter.setPen(scan_pen)
    painter.drawLine(
        QRectF(inner).left() + size * ratio * 0.14,
        inner.center().y(),
        inner.right() - size * ratio * 0.14,
        inner.center().y(),
    )
    painter.end()

    pixmap = QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(ratio)
    return pixmap


def app_icon(background: str = "#0F766E", foreground: str = "#FFFFFF") -> QIcon:
    result = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        result.addPixmap(logo_pixmap(size, background, foreground))
    return result

"""设计令牌与浅色/深色主题。

色彩体系来自 ui-ux-pro-max 设计系统：Flat / Minimalism，
青绿主色（#0D9488 系）搭配中性纸感背景，强调清晰层级与克制留白。
"""
from __future__ import annotations

from dataclasses import dataclass
from string import Template

from PySide6.QtCore import QObject, Signal

from .config import load_settings, update_setting


@dataclass(frozen=True)
class Tokens:
    dark: bool
    window: str
    sidebar: str
    surface: str
    surface_alt: str
    surface_hover: str
    border: str
    border_strong: str
    text: str
    text_secondary: str
    text_muted: str
    primary: str
    primary_fill: str
    primary_fill_hover: str
    primary_fill_pressed: str
    primary_hover: str
    primary_pressed: str
    primary_bright: str
    primary_soft: str
    on_primary: str
    accent: str
    danger: str
    danger_soft: str
    canvas: str
    canvas_dot: str
    shadow: str
    segment_active: str


LIGHT = Tokens(
    dark=False,
    window="#F8FBFA",
    sidebar="#FDFEFE",
    surface="#FFFFFF",
    surface_alt="#F4F9F7",
    surface_hover="#EBF5F1",
    border="#E6F0EC",
    border_strong="#D3E4DE",
    text="#26433D",
    text_secondary="#58746D",
    text_muted="#5F7A73",
    primary="#137A70",
    primary_fill="#5BCBBE",
    primary_fill_hover="#4CBBAE",
    primary_fill_pressed="#3FA99D",
    primary_hover="#0F6A61",
    primary_pressed="#0C5A52",
    primary_bright="#14B8A6",
    primary_soft="#E7F7F3",
    on_primary="#063B35",
    accent="#D99A4E",
    danger="#DC5F5F",
    danger_soft="#FDEEEE",
    canvas="#F0F7F4",
    canvas_dot="#E2EDE8",
    shadow="rgba(23, 62, 53, 0.07)",
    segment_active="#FFFFFF",
)

DARK = Tokens(
    dark=True,
    window="#111C18",
    sidebar="#14201C",
    surface="#192621",
    surface_alt="#1F2E28",
    surface_hover="#273A33",
    border="#2C4038",
    border_strong="#3B564C",
    text="#E6F2EE",
    text_secondary="#B2C8C0",
    text_muted="#8EA79F",
    primary="#7DE8D8",
    primary_fill="#46D3C2",
    primary_fill_hover="#65E2D3",
    primary_fill_pressed="#8CF2E5",
    primary_hover="#65E2D3",
    primary_pressed="#8CF2E5",
    primary_bright="#2DD4BF",
    primary_soft="#1A3A32",
    on_primary="#052E28",
    accent="#EFC98B",
    danger="#F09B9B",
    danger_soft="#3A2323",
    canvas="#121F1A",
    canvas_dot="#24362F",
    shadow="rgba(0, 0, 0, 0.42)",
    segment_active="#24443B",
)


_QSS = Template(
    """
QWidget {
    color: $text;
    font-size: 13px;
}
QMainWindow, QWidget#Root, QDialog {
    background-color: $window;
}
QWidget#Content {
    background-color: transparent;
}
QFrame#Sidebar {
    background-color: $sidebar;
    border-right: 1px solid $border;
}
QFrame#Header {
    background-color: transparent;
}
QFrame#Card, QFrame#ProjectCard {
    background-color: $surface;
    border: 1px solid $border;
    border-radius: 16px;
}
QFrame#ProjectCard:hover {
    border: 1px solid $primary;
}
QFrame#AddCard {
    background-color: transparent;
    border: 1px dashed $border_strong;
    border-radius: 16px;
}
QFrame#AddCard:hover {
    border: 1px dashed $primary;
    background-color: $primary_soft;
}
QFrame#Filmstrip, QFrame#Inspector, QFrame#Panel {
    background-color: $surface;
    border: 1px solid $border;
    border-radius: 14px;
}
QFrame#Toolbar {
    background-color: $surface;
    border: 1px solid $border;
    border-radius: 12px;
}
QFrame#PageThumb {
    background-color: $surface_alt;
    border: 2px solid transparent;
    border-radius: 10px;
}
QFrame#PageThumb:hover {
    border: 2px solid $border_strong;
}
QFrame#PageThumb[selected="true"] {
    border: 2px solid $primary;
    background-color: $primary_soft;
}
QFrame#SidebarItem {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 10px;
}
QFrame#SidebarItem:hover {
    background-color: $surface_hover;
}
QFrame#SidebarItem[selected="true"] {
    background-color: $primary_soft;
    border: 1px solid rgba(20, 184, 166, 0.30);
}
QFrame#ModeOption {
    background-color: $surface;
    border: 1px solid $border;
    border-radius: 11px;
}
QFrame#ModeOption:hover {
    border: 1px solid $border_strong;
    background-color: $surface_hover;
}
QFrame#ModeOption[selected="true"] {
    background-color: $primary_soft;
    border: 2px solid $primary;
}
QFrame#ModeOption[selected="true"] QLabel#ModeTitle {
    color: $primary;
}
QFrame#EmptyPanel {
    background-color: $surface;
    border: 1px dashed $border_strong;
    border-radius: 18px;
}
QFrame#Divider {
    background-color: $border;
    max-height: 1px;
    min-height: 1px;
    border: none;
}
QFrame#VDivider {
    background-color: $border;
    max-width: 1px;
    min-width: 1px;
    border: none;
}
QLabel {
    background: transparent;
}
QLabel#BrandName {
    font-size: 17px;
    font-weight: 700;
}
QLabel#BrandSub {
    font-size: 10px;
    color: $text_muted;
}
QLabel#H1 {
    font-size: 26px;
    font-weight: 700;
}
QLabel#Subtitle {
    font-size: 13px;
    color: $text_muted;
}
QLabel#SectionTitle {
    font-size: 12px;
    font-weight: 700;
    color: $text_muted;
}
QLabel#Meta {
    font-size: 11px;
    color: $text_muted;
}
QLabel#MetaStrong {
    font-size: 12px;
    color: $text_secondary;
}
QLabel#CardTitle {
    font-size: 14px;
    font-weight: 600;
}
QLabel#ModeTitle {
    font-size: 12px;
    font-weight: 600;
}
QLabel#ModeHint {
    font-size: 10px;
    color: $text_muted;
}
QLabel#EmptyTitle {
    font-size: 17px;
    font-weight: 600;
}
QLabel#EmptyHint {
    font-size: 12px;
    color: $text_muted;
}
QLabel#InfoKey {
    font-size: 11px;
    color: $text_muted;
}
QLabel#InfoValue {
    font-size: 11px;
    color: $text_secondary;
}
QLabel#ZoomValue {
    font-size: 11px;
    color: $text_secondary;
}
QLabel#Badge {
    background-color: $primary_soft;
    color: $primary;
    border-radius: 8px;
    padding: 2px 8px;
    font-size: 10px;
    font-weight: 600;
}
QLabel#CountBadge {
    background-color: $surface_alt;
    color: $text_secondary;
    border-radius: 8px;
    padding: 2px 7px;
    font-size: 10px;
    font-weight: 600;
}
QLabel#Link {
    color: $primary;
    font-size: 12px;
}
QLabel#Link:hover {
    color: $primary_hover;
}
QLabel#DialogTitle {
    font-size: 20px;
    font-weight: 700;
}
QPushButton {
    background-color: $surface;
    color: $text;
    border: 1px solid $border_strong;
    border-radius: 9px;
    padding: 0 14px;
    min-height: 34px;
    font-size: 13px;
}
QPushButton:hover {
    background-color: $surface_hover;
}
QPushButton:pressed {
    background-color: $surface_alt;
}
QPushButton:disabled {
    color: $text_muted;
    background-color: $surface_alt;
    border-color: $border;
}
QPushButton#Primary {
    background-color: $primary_fill;
    color: $on_primary;
    border: 1px solid transparent;
    border-radius: 10px;
    min-height: 38px;
    padding: 0 16px;
    font-weight: 600;
}
QPushButton#Primary:hover {
    background-color: $primary_fill_hover;
}
QPushButton#Primary:pressed {
    background-color: $primary_fill_pressed;
}
QPushButton#Primary:disabled {
    background-color: $surface_alt;
    color: $text_muted;
    border: 1px solid $border;
}
QPushButton#Secondary {
    background-color: $surface;
    color: $text;
    border: 1px solid $border_strong;
    border-radius: 10px;
    min-height: 38px;
    padding: 0 14px;
    font-weight: 600;
}
QPushButton#Secondary:hover {
    border-color: $primary;
    background-color: $surface_hover;
}
QPushButton#Ghost {
    background-color: transparent;
    color: $text_secondary;
    border: 1px solid transparent;
    border-radius: 9px;
    min-height: 34px;
    padding: 0 10px;
}
QPushButton#Ghost:hover {
    background-color: $surface_hover;
    color: $text;
}
QPushButton#DangerGhost {
    background-color: transparent;
    color: $danger;
    border: 1px solid transparent;
    border-radius: 9px;
    min-height: 34px;
    padding: 0 10px;
}
QPushButton#DangerGhost:hover {
    background-color: $danger_soft;
}
QPushButton#IconBtn, QToolButton#IconBtn {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 0;
    min-height: 0;
}
QPushButton#IconBtn:hover, QToolButton#IconBtn:hover {
    background-color: $surface_hover;
}
QPushButton#IconBtn:pressed, QToolButton#IconBtn:pressed {
    background-color: $surface_alt;
}
QPushButton#ToolBtn {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 0;
    min-height: 0;
}
QPushButton#ToolBtn:hover {
    background-color: $surface_hover;
}
QPushButton#ToolBtn:pressed {
    background-color: $surface_alt;
}
QPushButton#MenuBtn {
    background-color: transparent;
    border: none;
    border-radius: 6px;
    padding: 0;
    min-height: 0;
}
QPushButton#MenuBtn:hover {
    background-color: $surface_hover;
}
QPushButton#Segment {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    min-height: 28px;
    padding: 0 12px;
    color: $text_secondary;
    font-weight: 600;
    font-size: 12px;
}
QPushButton#Segment:hover {
    background-color: $surface_hover;
    color: $text;
}
QPushButton#Segment:checked {
    background-color: $segment_active;
    color: $primary;
    border: 1px solid $border;
}
QPushButton#Segment:disabled {
    color: $text_muted;
    background-color: transparent;
}
QPushButton#LinkBtn {
    background: transparent;
    border: none;
    color: $primary;
    padding: 0;
    min-height: 0;
    font-size: 12px;
}
QPushButton#LinkBtn:hover {
    color: $primary_hover;
}
QLineEdit {
    background-color: $surface;
    color: $text;
    border: 1px solid $border;
    border-radius: 9px;
    padding: 6px 11px;
    selection-background-color: $primary_soft;
    selection-color: $text;
}
QLineEdit:focus {
    border: 1px solid $primary;
}
QLineEdit#PageTitle {
    background-color: transparent;
    border: 1px solid transparent;
    font-size: 19px;
    font-weight: 600;
    padding: 3px 8px;
    border-radius: 8px;
}
QLineEdit#PageTitle:hover {
    background-color: $surface_hover;
}
QLineEdit#PageTitle:focus {
    background-color: $surface;
    border: 1px solid $primary;
}
QScrollArea {
    background: transparent;
    border: none;
}
QScrollArea > QWidget > QWidget {
    background: transparent;
}
QAbstractScrollArea::corner {
    background: transparent;
}
QScrollBar:vertical {
    background: transparent;
    width: 9px;
    margin: 2px 2px 2px 1px;
}
QScrollBar::handle:vertical {
    background: $border_strong;
    border-radius: 4px;
    min-height: 28px;
}
QScrollBar::handle:vertical:hover {
    background: $text_muted;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
    background: transparent;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
QScrollBar:horizontal {
    background: transparent;
    height: 9px;
    margin: 1px 2px 2px 2px;
}
QScrollBar::handle:horizontal {
    background: $border_strong;
    border-radius: 4px;
    min-width: 28px;
}
QScrollBar::handle:horizontal:hover {
    background: $text_muted;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
    background: transparent;
}
QMenu {
    background-color: $surface;
    border: 1px solid $border;
    border-radius: 8px;
    padding: 5px;
}
QMenu::item {
    padding: 7px 26px 7px 12px;
    border-radius: 6px;
    font-size: 12px;
}
QMenu::item:selected {
    background-color: $surface_hover;
}
QMenu::item:disabled {
    color: $text_muted;
}
QMenu::separator {
    height: 1px;
    background: $border;
    margin: 4px 8px;
}
QToolTip {
    background-color: $surface;
    color: $text;
    border: 1px solid $border;
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 11px;
}
QProgressBar {
    background-color: $surface_alt;
    border: none;
    border-radius: 4px;
    height: 7px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background-color: $primary;
    border-radius: 4px;
}
QRadioButton, QCheckBox {
    font-size: 12px;
    spacing: 7px;
}
QRadioButton::indicator {
    width: 16px;
    height: 16px;
}
QSlider::groove:horizontal {
    height: 4px;
    background-color: $surface_alt;
    border-radius: 2px;
}
QSlider::sub-page:horizontal {
    background-color: $primary;
    border-radius: 2px;
}
QSlider::add-page:horizontal {
    background-color: $surface_alt;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background-color: $surface;
    border: 2px solid $primary;
    width: 14px;
    height: 14px;
    margin: -6px 0;
    border-radius: 9px;
}
QSlider::handle:horizontal:hover {
    background-color: $primary_soft;
}
QLabel#SliderName {
    font-size: 12px;
    color: $text_secondary;
}
QLabel#SliderValue {
    font-size: 11px;
    color: $text_muted;
}
QDialog QLabel {
    color: $text;
}
QMessageBox {
    background-color: $surface;
}
QMessageBox QLabel {
    color: $text;
    font-size: 13px;
}
"""
)


def build_qss(tokens: Tokens) -> str:
    values = {key: getattr(tokens, key) for key in tokens.__dataclass_fields__}
    values = {key: str(value) for key, value in values.items()}
    return _QSS.substitute(values)


class ThemeManager(QObject):
    changed = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        settings = load_settings()
        self._dark = bool(settings.get("dark_mode", False))

    @property
    def dark(self) -> bool:
        return self._dark

    @property
    def tokens(self) -> Tokens:
        return DARK if self._dark else LIGHT

    def set_dark(self, dark: bool, persist: bool = True) -> None:
        dark = bool(dark)
        if dark == self._dark:
            return
        self._dark = dark
        if persist:
            update_setting("dark_mode", dark)
        self.changed.emit(dark)

    def toggle(self) -> None:
        self.set_dark(not self._dark)


theme_manager = ThemeManager()

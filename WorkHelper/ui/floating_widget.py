from __future__ import annotations

import os
import webbrowser
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QEventLoop, QEasingCurve, QPoint, QRect, QSize, QTimer, QVariantAnimation, Qt
from PyQt6.QtGui import QColor, QCursor, QFontMetrics, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QScrollBar,
    QStackedLayout,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QGraphicsDropShadowEffect,
)

from app import config
from app.date_tools import render_date_template
from ui.common import bump_usage, show_modern_warning
from ui.tab_launcher import launcher_display_emoji, launcher_favicon_pixmap, launcher_icon_mode


CATEGORY_ORDER = [
    ("text", "텍스트", "📝"),
    ("snippet", "스니펫", "⌘"),
    ("date", "날짜보고양식", "📅"),
    ("site", "사이트", "🌐"),
    ("file", "파일", "📄"),
    ("folder", "폴더", "📁"),
    ("cheat", "컨닝페이퍼", "🧾"),
    ("memo", "메모", "🗒"),
    ("emoji", "이모지", "😊"),
]

WIDGET_THEMES = {
    "light": {
        "name": "밝은 테마",
        "panel": "rgba(255, 255, 255, 188)",
        "panel2": "rgba(236, 244, 255, 132)",
        "edge": "rgba(255, 255, 255, 215)",
        "shine": "rgba(255, 255, 255, 95)",
        "shadow": "rgba(52, 74, 115, 62)",
        "text": "#1F2937",
        "muted": "#4B5563",
        "icon_bg": "rgba(255, 255, 255, 112)",
        "hover": "rgba(255, 255, 255, 178)",
    },
    "dark": {
        "name": "어두운 테마",
        "panel": "rgba(26, 32, 44, 204)",
        "panel2": "rgba(10, 15, 24, 152)",
        "edge": "rgba(255, 255, 255, 62)",
        "shine": "rgba(255, 255, 255, 38)",
        "shadow": "rgba(0, 0, 0, 135)",
        "text": "#F9FAFB",
        "muted": "#D1D5DB",
        "icon_bg": "rgba(255, 255, 255, 34)",
        "hover": "rgba(255, 255, 255, 72)",
    },
    "glass": {
        "name": "미러 글래스",
        "panel": "rgba(245, 251, 255, 174)",
        "panel2": "rgba(196, 217, 238, 104)",
        "edge": "rgba(255, 255, 255, 230)",
        "shine": "rgba(255, 255, 255, 120)",
        "shadow": "rgba(44, 67, 104, 72)",
        "text": "#0F172A",
        "muted": "#334155",
        "icon_bg": "rgba(255, 255, 255, 124)",
        "hover": "rgba(255, 255, 255, 196)",
    },
    "mint": {
        "name": "민트",
        "panel": "rgba(232, 255, 248, 178)",
        "panel2": "rgba(186, 233, 219, 108)",
        "edge": "rgba(255, 255, 255, 218)",
        "shine": "rgba(255, 255, 255, 94)",
        "shadow": "rgba(32, 96, 82, 62)",
        "text": "#12332C",
        "muted": "#315C51",
        "icon_bg": "rgba(255, 255, 255, 116)",
        "hover": "rgba(255, 255, 255, 182)",
    },
    "rose": {
        "name": "로즈",
        "panel": "rgba(255, 241, 247, 182)",
        "panel2": "rgba(245, 203, 218, 108)",
        "edge": "rgba(255, 255, 255, 220)",
        "shine": "rgba(255, 255, 255, 92)",
        "shadow": "rgba(124, 45, 74, 58)",
        "text": "#3A1824",
        "muted": "#6F3B4F",
        "icon_bg": "rgba(255, 255, 255, 118)",
        "hover": "rgba(255, 255, 255, 186)",
    },
}


def hex_to_rgba(hex_color: str, opacity: int) -> str:
    if str(hex_color or "").strip().startswith("rgba"):
        raw = str(hex_color or "").strip()
        parts = raw[raw.find("(") + 1 : raw.rfind(")")].split(",")
        if len(parts) == 4:
            try:
                r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
                base_alpha = int(parts[3])
                alpha = int(base_alpha * (max(20, min(100, opacity)) / 100))
                return f"rgba({r}, {g}, {b}, {alpha})"
            except ValueError:
                return raw
        return raw
    raw = str(hex_color or "").strip().lstrip("#")
    if len(raw) != 6:
        raw = "F7FAFF"
    try:
        r = int(raw[0:2], 16)
        g = int(raw[2:4], 16)
        b = int(raw[4:6], 16)
    except ValueError:
        r, g, b = 247, 250, 255
    alpha = int(255 * (max(20, min(100, opacity)) / 100))
    return f"rgba({r}, {g}, {b}, {alpha})"


def css_color_to_qcolor(value: str) -> QColor:
    raw = str(value or "").strip()
    if raw.startswith("rgba"):
        parts = raw[raw.find("(") + 1 : raw.rfind(")")].split(",")
        if len(parts) == 4:
            try:
                return QColor(int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3]))
            except ValueError:
                pass
    color = QColor(raw)
    return color if color.isValid() else QColor(0, 0, 0, 70)


class DockIconButton(QToolButton):
    def __init__(self, icon_text: str, tooltip: str, base_size: int, shape: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.base_size = base_size
        self.shape = shape
        self.setText(icon_text)
        self.setToolTip(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(base_size, base_size)
        self.setIconSize(QSize(max(24, base_size - 6), max(24, base_size - 6)))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(120)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._resize_to)

    def enterEvent(self, event) -> None:
        self._animate_to(int(self.base_size * 1.32))
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._animate_to(self.base_size)
        super().leaveEvent(event)

    def _animate_to(self, value: int) -> None:
        self._anim.stop()
        self._anim.setStartValue(self.width())
        self._anim.setEndValue(value)
        self._anim.start()

    def _resize_to(self, value) -> None:
        size = int(value)
        self.setFixedSize(size, size)
        self.setIconSize(QSize(max(24, size - 6), max(24, size - 6)))

    def mouseReleaseEvent(self, event) -> None:
        owner = self.window()
        if event.button() == Qt.MouseButton.BackButton and hasattr(owner, "go_back"):
            owner.go_back()
            return
        super().mouseReleaseEvent(event)


class DockItem(QWidget):
    def __init__(
        self,
        icon_text: str,
        label: str,
        tooltip: str,
        callback: Callable,
        icon_size: int,
        shape: str,
        icon: QIcon | None = None,
        popup_enabled: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.full_label = str(label)
        self.label_width = max(68, icon_size + 28)
        self._marquee_offset = 0
        self.setObjectName("floatingDockItem")
        self.setProperty("dockState", "normal")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        item_width = max(78, int(icon_size * 1.44), self.label_width + 4)
        item_height = max(78, int(icon_size * 1.32) + 34)
        self.setFixedSize(item_width, item_height)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        tooltip_text = tooltip if popup_enabled else ""
        self.button = DockIconButton(icon_text, tooltip_text, icon_size, shape, self)
        if icon is not None and not icon.isNull():
            self.button.setIcon(icon)
            self.button.setText("")
            self.button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.button.clicked.connect(callback)
        self.label = QLabel(label)
        self.label.setObjectName("floatingDockLabel")
        self.label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.label.setWordWrap(False)
        self.label.setToolTip(tooltip_text)
        self.label.setFixedWidth(self.label_width)
        layout.addWidget(self.label, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.button, 0, Qt.AlignmentFlag.AlignHCenter)
        self.marquee_timer = QTimer(self)
        self.marquee_timer.timeout.connect(self._advance_marquee)
        self.set_normal_label()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.BackButton:
            owner = self.window()
            if hasattr(owner, "go_back"):
                owner.go_back()
                return
        if event.button() == Qt.MouseButton.LeftButton:
            self.button.click()
            return
        super().mouseReleaseEvent(event)

    def enterEvent(self, event) -> None:
        owner = self.window()
        if hasattr(owner, "set_hovered_item"):
            owner.set_hovered_item(self)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        owner = self.window()
        if hasattr(owner, "clear_hovered_item"):
            owner.clear_hovered_item(self)
        super().leaveEvent(event)

    def set_normal_label(self) -> None:
        self.stop_marquee()
        metrics = QFontMetrics(self.label.font())
        self.label.setFixedWidth(self.label_width)
        self.label.setText(metrics.elidedText(self.full_label, Qt.TextElideMode.ElideRight, self.label_width))

    def set_hover_label(self) -> None:
        self.start_marquee()

    def start_marquee(self) -> None:
        metrics = QFontMetrics(self.label.font())
        if metrics.horizontalAdvance(self.full_label) <= self.label_width:
            self.label.setText(self.full_label)
            return
        if not self.marquee_timer.isActive():
            self._marquee_offset = 0
            self.marquee_timer.start(120)
        self._advance_marquee()

    def stop_marquee(self) -> None:
        if self.marquee_timer.isActive():
            self.marquee_timer.stop()
        self._marquee_offset = 0

    def _advance_marquee(self) -> None:
        text = f"{self.full_label}   "
        if not text.strip():
            return
        offset = self._marquee_offset % len(text)
        self.label.setText(text[offset:] + text[:offset])
        self._marquee_offset = offset + 1


class FloatingWidget(QFrame):
    def __init__(self, main) -> None:
        super().__init__(None)
        self.main = main
        self.current_category: str | None = None
        self._shown = False
        self._animating = False
        self._settings: dict = {}
        self._pending_hover_item: DockItem | None = None
        self._active_hover_item: DockItem | None = None
        self._preview_pinned = False
        self._scroll_position = 0.0
        self._scroll_velocity = 0.0
        self.setWindowTitle("6PM Floating Widget")
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setStyleSheet("background: transparent; border: 0;")

        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(12, 12, 12, 12)
        self.root.setSpacing(0)
        self.panel = QWidget()
        self.panel.setObjectName("floatingDockPanel")
        self.panel_layout = QVBoxLayout(self.panel)
        self.panel_layout.setContentsMargins(14, 8, 14, 8)
        self.panel_layout.setSpacing(2)
        self.header = QWidget(self.panel)
        self.header.setObjectName("floatingDockHeader")
        self.header_layout = QStackedLayout(self.header)
        self.header_layout.setContentsMargins(0, 0, 0, 0)
        self.back_button = QToolButton(self.header)
        self.back_button.setObjectName("floatingDockBackButton")
        self.back_button.setText("‹ 이전")
        self.back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_button.clicked.connect(lambda checked=False: self._open_category(None))
        self.hover_text = QLabel(self.panel)
        self.hover_text.setObjectName("floatingDockHoverText")
        self.hover_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hover_text.setWordWrap(False)
        self.hover_text.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.hover_text.setFixedHeight(0)
        self.header_layout.addWidget(self.back_button)
        self.header_layout.addWidget(self.hover_text)
        self.header_layout.setAlignment(self.back_button, Qt.AlignmentFlag.AlignCenter)
        self.header_layout.setAlignment(self.hover_text, Qt.AlignmentFlag.AlignCenter)
        self.scroll = QScrollArea()
        self.scroll.setObjectName("floatingDockScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.viewport().setObjectName("floatingDockViewport")
        self.scroll.viewport().setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.content = QWidget()
        self.content.setObjectName("floatingDockContent")
        self.items_layout = QHBoxLayout(self.content)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(6)
        self.scroll.setWidget(self.content)
        self.panel_layout.addWidget(self.header, 0)
        self.panel_layout.addWidget(self.scroll, 1)
        self.root.addWidget(self.panel, 1)

        self.watch_timer = QTimer(self)
        self.watch_timer.timeout.connect(self._watch_mouse)
        self.watch_timer.start(35)
        self.scroll_timer = QTimer(self)
        self.scroll_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.scroll_timer.timeout.connect(self._auto_scroll)
        self.scroll_timer.start(16)
        self.hover_timer = QTimer(self)
        self.hover_timer.setSingleShot(True)
        self.hover_timer.timeout.connect(self._apply_pending_hover)
        self.clear_hover_timer = QTimer(self)
        self.clear_hover_timer.setSingleShot(True)
        self.clear_hover_timer.timeout.connect(self._reset_hover_state)
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self._hide_panel)
        self.animation = QVariantAnimation(self)
        self.animation.valueChanged.connect(self._set_geometry_from_value)
        self.animation.finished.connect(self._finish_animation)
        self.apply_settings()

    def apply_settings(self) -> None:
        self._preview_pinned = False
        self._settings = dict(self.main.settings)
        enabled = bool(self._settings.get("floating_widget_enabled", True))
        self.current_category = None
        self._rebuild()
        self._apply_style()
        self._sync_hover_row()
        if enabled:
            self._move_hidden()
            self.show()
        else:
            self.hide()

    def refresh(self) -> None:
        self._preview_pinned = False
        self._settings = dict(self.main.settings)
        self._rebuild()
        self._apply_style()
        self._sync_hover_row()

    def preview_settings(self) -> None:
        self._preview_pinned = True
        self._settings = dict(self.main.settings)
        self.current_category = None
        self._rebuild()
        self._apply_style()
        self._sync_hover_row()
        self.animation.stop()
        self.hide_timer.stop()
        if bool(self._settings.get("floating_widget_enabled", True)):
            self.setGeometry(self._visible_geometry())
            self._shown = True
            self._animating = False
            self.show()
            self.raise_()
        else:
            self._shown = False
            self.hide()

    def _edge(self) -> str:
        return str(self._settings.get("floating_widget_edge", "top") or "top")

    def _panel_size(self) -> int:
        raw = max(130, min(280, int(self._settings.get("floating_widget_panel_size", 160) or 160)))
        return max(raw, self._minimum_panel_size())

    def _panel_width(self) -> int:
        return max(260, min(1400, int(self._settings.get("floating_widget_panel_width", 860) or 860)))

    def _raw_icon_size(self) -> int:
        return int(self._settings.get("floating_widget_icon_size", 50) or 50)

    def _icon_size(self) -> int:
        return max(36, min(128, self._raw_icon_size()))

    def _hover_row_height(self) -> int:
        return 16

    def _dock_item_height(self) -> int:
        icon_size = self._icon_size()
        return max(78, int(icon_size * 1.32) + 34)

    def _minimum_panel_size(self) -> int:
        spacing = 3
        return 14 + self._hover_row_height() + spacing + self._dock_item_height()

    def _sync_hover_row(self) -> None:
        height = self._hover_row_height()
        self.header.setFixedHeight(height)
        self.hover_text.setFixedHeight(height)
        self.back_button.setFixedHeight(height)
        if height:
            self._show_header_back_button()
            self.header.show()
        else:
            self.header.hide()

    def _speed(self) -> int:
        return max(60, min(900, int(self._settings.get("floating_widget_speed", 80) or 80)))

    def _theme(self) -> dict:
        key = str(self._settings.get("floating_widget_theme", "dark") or "dark")
        return WIDGET_THEMES.get(key, WIDGET_THEMES["light"])

    def _shape(self) -> str:
        return "square"

    def _screen_index(self) -> int:
        screens = QApplication.screens()
        if not screens:
            return 0
        value = int(self._settings.get("floating_widget_monitor", 1) or 1)
        return max(0, min(len(screens) - 1, value - 1))

    def go_back(self) -> None:
        if self.current_category:
            self._open_category(None)

    def _show_header_back_button(self) -> None:
        if self.current_category:
            self.hover_text.clear()
            self.header_layout.setCurrentWidget(self.back_button)
        else:
            self.hover_text.clear()
            self.header_layout.setCurrentWidget(self.hover_text)

    def set_hovered_item(self, hovered: QWidget) -> None:
        if not isinstance(hovered, DockItem):
            return
        if self.clear_hover_timer.isActive():
            self.clear_hover_timer.stop()
        self._pending_hover_item = hovered
        self._apply_pending_hover()

    def _apply_pending_hover(self) -> None:
        hovered = self._pending_hover_item
        if hovered is None or hovered.parent() is not self.content or not hovered.underMouse():
            return
        self._active_hover_item = hovered
        for item in self._dock_items():
            item.setProperty("dockState", "active" if item is hovered else "dim")
            if item is hovered:
                item.set_hover_label()
                item.label.show()
            else:
                item.stop_marquee()
                item.label.clear()
            self._refresh_item_style(item)
        self._show_hover_text(hovered)

    def clear_hovered_item(self, hovered: QWidget | None = None) -> None:
        if hovered is not None and hovered.underMouse():
            return
        if self.hover_timer.isActive():
            self.hover_timer.stop()
        self._pending_hover_item = None
        self._reset_hover_state()

    def _reset_hover_state(self) -> None:
        if any(item.underMouse() for item in self._dock_items()):
            return
        self._active_hover_item = None
        if self._hover_row_height():
            self._show_header_back_button()
        else:
            self.header.hide()
        for item in self._dock_items():
            item.setProperty("dockState", "normal")
            item.stop_marquee()
            item.set_normal_label()
            item.label.show()
            self._refresh_item_style(item)

    def _clear_hover_state_now(self) -> None:
        self.hover_timer.stop()
        self.clear_hover_timer.stop()
        self._pending_hover_item = None
        self._active_hover_item = None
        if hasattr(self, "hover_text"):
            self.hover_text.clear()
        if hasattr(self, "back_button"):
            self._show_header_back_button()
        for item in self._dock_items():
            item.stop_marquee()
            item.setProperty("dockState", "normal")

    def _show_hover_text(self, item: DockItem) -> None:
        metrics = QFontMetrics(self.hover_text.font())
        max_width = max(90, self.panel.width() - 28)
        self.hover_text.setText(metrics.elidedText(item.full_label, Qt.TextElideMode.ElideRight, max_width))
        self.header_layout.setCurrentWidget(self.hover_text)

    def _dock_items(self) -> list[DockItem]:
        return [child for child in self.content.findChildren(DockItem) if child.parent() is self.content]

    def _refresh_item_style(self, item: DockItem) -> None:
        item.style().unpolish(item)
        item.style().polish(item)
        item.label.style().unpolish(item.label)
        item.label.style().polish(item.label)
        item.button.style().unpolish(item.button)
        item.button.style().polish(item.button)

    def _is_vertical(self) -> bool:
        return self._edge() in {"left", "right"}

    def _screen_rect(self) -> QRect:
        screens = QApplication.screens()
        screen = screens[self._screen_index()] if screens else QApplication.primaryScreen()
        return screen.geometry() if screen else QRect(0, 0, 1280, 720)

    def _visible_geometry(self) -> QRect:
        area = self._screen_rect()
        size = self._panel_size()
        if self._is_vertical():
            cell = max(78, int(self._icon_size() * 1.44))
            width = max(70, cell + 28)
            height = min(max(160, self._content_extent() + 28), area.height() - 80)
            y = area.top() + max(0, (area.height() - height) // 2)
            x = area.left() if self._edge() == "left" else area.right() - width + 1
            return QRect(x, y, width, height)
        width = min(max(260, self._content_extent() + 40), area.width() - 80)
        width = min(self._panel_width(), area.width() - 80)
        height = size
        x = area.left() + max(0, (area.width() - width) // 2)
        y = area.top() if self._edge() == "top" else area.bottom() - height + 1
        return QRect(x, y, width, height)

    def _visible_item_count(self) -> int:
        if self.current_category:
            return len(self._items_for_category(self.current_category))
        return len(self._category_order())

    def _content_extent(self) -> int:
        items = self._dock_items() if hasattr(self, "content") else []
        if items:
            if self._is_vertical():
                return sum(item.height() for item in items)
            return sum(item.width() for item in items)
        count = max(1, self._visible_item_count())
        cell = max(96, int(self._icon_size() * 1.9))
        return count * cell

    def _hidden_geometry(self) -> QRect:
        geo = self._visible_geometry()
        sliver = 3
        edge = self._edge()
        if edge == "top":
            geo.moveTop(geo.top() - geo.height() + sliver)
        elif edge == "bottom":
            geo.moveTop(geo.top() + geo.height() - sliver)
        elif edge == "left":
            geo.moveLeft(geo.left() - geo.width() + sliver)
        elif edge == "right":
            geo.moveLeft(geo.left() + geo.width() - sliver)
        return geo

    def _move_hidden(self) -> None:
        self._shown = False
        self.setGeometry(self._hidden_geometry())

    def _is_at_trigger_edge(self, pos: QPoint, area: QRect, edge: str) -> bool:
        if edge == "top":
            return area.left() <= pos.x() <= area.right() and 0 <= pos.y() - area.top() <= 1
        if edge == "bottom":
            return area.left() <= pos.x() <= area.right() and 0 <= area.bottom() - pos.y() <= 1
        if edge == "left":
            return area.top() <= pos.y() <= area.bottom() and 0 <= pos.x() - area.left() <= 1
        if edge == "right":
            return area.top() <= pos.y() <= area.bottom() and 0 <= area.right() - pos.x() <= 1
        return False

    def _is_inside_active_panel(self, pos: QPoint) -> bool:
        if not (self._shown or self._animating):
            return False
        return self.geometry().adjusted(-6, -6, 6, 6).contains(pos)

    def _watch_mouse(self) -> None:
        if not bool(self._settings.get("floating_widget_enabled", True)):
            return
        pos = QCursor.pos()
        edge = self._edge()
        area = self._screen_rect()
        near = self._is_at_trigger_edge(pos, area, edge)
        inside = self._is_inside_active_panel(pos)
        if near:
            if self.hide_timer.isActive():
                self.hide_timer.stop()
            self._show_panel()
        elif inside:
            if self.hide_timer.isActive():
                self.hide_timer.stop()
        elif self._shown and not self._preview_pinned:
            if not self.hide_timer.isActive():
                self.hide_timer.start(650)

    def _show_panel(self) -> None:
        if self._shown or self._animating:
            return
        self._animate(self.geometry(), self._visible_geometry(), True)

    def _hide_panel(self) -> None:
        if not self._shown or self._animating:
            return
        if self.underMouse():
            return
        self.clear_hovered_item()
        self.current_category = None
        self._rebuild()
        self._animate(self.geometry(), self._hidden_geometry(), False)

    def _animate(self, start: QRect, end: QRect, shown: bool) -> None:
        self.show()
        self._target_shown = shown
        self._animating = True
        self.animation.stop()
        self.animation.setDuration(self._speed())
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.setStartValue(start)
        self.animation.setEndValue(end)
        self.animation.start()

    def _set_geometry_from_value(self, value) -> None:
        if isinstance(value, QRect):
            self.setGeometry(value)

    def _finish_animation(self) -> None:
        self._shown = bool(getattr(self, "_target_shown", False))
        self._animating = False

    def _apply_style(self) -> None:
        opacity = max(20, min(100, int(self._settings.get("floating_widget_opacity", 77) or 77)))
        theme = self._theme()
        panel = hex_to_rgba(theme["panel"], opacity)
        panel2 = hex_to_rgba(theme["panel2"], opacity)
        shine = hex_to_rgba(theme.get("shine", "rgba(255, 255, 255, 92)"), min(100, opacity + 10))
        edge = hex_to_rgba(theme.get("edge", "rgba(255, 255, 255, 160)"), min(100, opacity + 8))
        hover = hex_to_rgba(theme["hover"], opacity)
        radius = max(24, min(42, self._panel_size() // 3))
        button_radius = self._icon_size() if self._shape() == "round" else 12
        icon_font_size = max(20, int(self._icon_size() * 0.52))
        shadow = QGraphicsDropShadowEffect(self.panel)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 8)
        shadow.setColor(css_color_to_qcolor(theme.get("shadow", "rgba(0, 0, 0, 70)")))
        self.panel.setGraphicsEffect(shadow)
        self.setWindowOpacity(1.0)
        self.setStyleSheet(
            f"""
            FloatingWidget, QFrame {{
                background: transparent;
                border: 0;
                font-family: "Malgun Gothic", "맑은 고딕", sans-serif;
                font-size: 8pt;
            }}
            QWidget#floatingDockPanel {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 {shine},
                    stop:.34 {panel},
                    stop:.76 {panel2},
                    stop:1 {panel});
                border: 1px solid {edge};
                border-radius: {radius}px;
            }}
            QScrollArea#floatingDockScroll,
            QWidget#floatingDockViewport,
            QScrollArea#floatingDockScroll > QWidget,
            QScrollArea#floatingDockScroll > QWidget > QWidget,
            QWidget#floatingDockContent,
            QWidget#floatingDockItem {{
                background: transparent;
                border: 0;
            }}
            QWidget#floatingDockHeader {{
                background: transparent;
                border: 0;
            }}
            QToolButton {{
                background-color: transparent;
                color: {theme["text"]};
                border: 0;
                border-radius: {button_radius}px;
                font-weight: 900;
                font-size: {icon_font_size}px;
                padding: 0;
            }}
            QToolButton:hover {{
                background: {hover};
                border: 0;
            }}
            QWidget#floatingDockItem[dockState="dim"] QToolButton {{
                color: rgba(148, 163, 184, 115);
                background: transparent;
                border: 0;
            }}
            QWidget#floatingDockItem[dockState="active"] QToolButton {{
                color: {theme["text"]};
                background-color: {hover};
                border: 0;
            }}
            QToolButton#floatingDockBackButton {{
                color: {theme["text"]};
                background: transparent;
                border: 0;
                border-radius: 0;
                font-size: 8pt;
                font-weight: 900;
                padding: 0;
            }}
            QToolButton#floatingDockBackButton:hover {{
                background: transparent;
            }}
            QLabel#floatingDockLabel {{
                color: {theme["muted"]};
                background: transparent;
                border: 0;
                font-size: 8pt;
                font-weight: 700;
                line-height: 110%;
            }}
            QWidget#floatingDockItem[dockState="dim"] QLabel#floatingDockLabel {{
                color: transparent;
            }}
            QWidget#floatingDockItem[dockState="active"] QLabel#floatingDockLabel {{
                color: {theme["text"]};
                font-weight: 900;
            }}
            QLabel#floatingDockHoverText {{
                color: {theme["text"]};
                background: transparent;
                border-radius: 0;
                border: 0;
                font-size: 8pt;
                font-weight: 900;
                padding: 0;
            }}
            """
        )

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.BackButton:
            self.go_back()
            return
        super().mouseReleaseEvent(event)

    def _rebuild(self) -> None:
        self._clear_hover_state_now()
        self._scroll_position = 0.0
        self._scroll_velocity = 0.0
        self.scroll.hide()
        self.scroll.setUpdatesEnabled(False)
        try:
            old_content = self.scroll.takeWidget() if hasattr(self, "scroll") else getattr(self, "content", None)
            if old_content is not None:
                old_content.hide()
                old_content.setParent(None)
                old_content.deleteLater()
            self.content = QWidget()
            self.content.setObjectName("floatingDockContent")
            if self._is_vertical():
                layout = QVBoxLayout(self.content)
                align = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
            else:
                layout = QHBoxLayout(self.content)
                align = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            layout.setAlignment(align)
            self.items_layout = layout
            self.scroll.setWidget(self.content)
            self.scroll.viewport().update()
            self.items_layout.addStretch(1)
            if self.current_category:
                for label, detail, callback, icon_text, icon in self._items_for_category(self.current_category):
                    self._add_item(icon_text, label, detail, callback, icon)
            else:
                for key, label, icon_text in self._category_order():
                    self._add_item(icon_text, label, label, lambda checked=False, value=key: self._open_category(value))
            self.items_layout.addStretch(1)
        finally:
            self.scroll.setUpdatesEnabled(True)
            self.scroll.show()
            self._show_header_back_button()
            self.scroll.viewport().repaint()
            self.panel.repaint()
            self.repaint()
            QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)

    def _category_order(self) -> list[tuple[str, str, str]]:
        enabled = self._settings.get("floating_widget_categories")
        if not isinstance(enabled, list):
            enabled = [key for key, _label, _icon in CATEGORY_ORDER]
        enabled_set = {str(key) for key in enabled}
        categories = [category for category in CATEGORY_ORDER if category[0] in enabled_set]
        return categories or CATEGORY_ORDER[:]

    def _add_back_button(self) -> None:
        self._add_item("‹", "분류", "분류로 돌아가기", lambda checked=False: self._open_category(None))

    def _add_item(
        self,
        icon_text: str,
        label: str,
        tooltip: str,
        callback: Callable,
        icon: QIcon | None = None,
    ) -> None:
        rendered_icon = icon if self._raw_icon_size() >= 33 else None
        popup_enabled = bool(self._settings.get("floating_widget_show_hover_text", True))
        item = DockItem(icon_text, label, tooltip, callback, self._icon_size(), self._shape(), rendered_icon, popup_enabled, self.content)
        self.items_layout.addWidget(item, 0, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)

    def _open_category(self, key: str | None) -> None:
        if self.current_category == key:
            return
        self.current_category = key
        self._rebuild()
        self._apply_style()
        if self._shown:
            self.setGeometry(self._visible_geometry())

    def _ordered(self, collection: str) -> list[tuple[int, dict]]:
        items = list(self.main.data.get(collection, []))
        return sorted(enumerate(items), key=lambda pair: (int(pair[1].get("sort_order", pair[0]) or 0), pair[0]))

    def _items_for_category(self, key: str) -> list[tuple[str, str, Callable, str, QIcon | None]]:
        if key == "text":
            return [self._text_item(item, "📝") for _idx, item in self._ordered("phrases")]
        if key == "snippet":
            return [self._text_item(item, "⌘") for _idx, item in self._ordered("snippets")]
        if key == "date":
            return [self._title_item(item) for _idx, item in self._ordered("title_templates")]
        if key in {"site", "file", "folder"}:
            return [self._launcher_item(item) for _idx, item in self._ordered("launchers") if self._launcher_type(item) == key]
        if key == "cheat":
            return [self._cheat_item(item) for _idx, item in self._ordered("images")]
        if key == "memo":
            return [self._memo_item(item) for _idx, item in self._ordered("memos")]
        if key == "emoji":
            return [(emoji, emoji, lambda checked=False, value=emoji: self._copy_emoji(value), emoji, None) for emoji in self._emoji_items()]
        return []

    def _label(self, value: str, fallback: str) -> str:
        text = str(value or fallback).strip() or fallback
        return text

    def _text_item(self, item: dict, icon_text: str) -> tuple[str, str, Callable, str, QIcon | None]:
        label = self._label(item.get("name") or item.get("text"), "텍스트")
        tooltip = str(item.get("name") or item.get("text") or label)
        return label, tooltip, lambda checked=False, value=item: self._copy_text_item(value, "text"), icon_text, None

    def _title_item(self, item: dict) -> tuple[str, str, Callable, str, QIcon | None]:
        label = self._label(item.get("name") or item.get("template"), "날짜")
        return label, str(item.get("template", "")), lambda checked=False, value=item: self._copy_title_item(value), "📅", None

    def _launcher_type(self, item: dict) -> str:
        value = str(item.get("type") or "site")
        return value if value in {"site", "file", "folder"} else "site"

    def _launcher_item(self, item: dict) -> tuple[str, str, Callable, str, QIcon | None]:
        item_type = self._launcher_type(item)
        label = self._label(item.get("name") or item.get("url") or item.get("path"), "열기")
        detail = str(item.get("url") or item.get("path") or label)
        icon_text = launcher_display_emoji(item)
        icon = self._site_icon(item) if item_type == "site" and launcher_icon_mode(item) == "auto" else None
        return label, detail, lambda checked=False, value=item: self._open_launcher(value), icon_text, icon

    def _site_icon(self, item: dict) -> QIcon | None:
        pixmap = launcher_favicon_pixmap(item)
        return QIcon(pixmap) if not pixmap.isNull() else None

    def _cheat_item(self, item: dict) -> tuple[str, str, Callable, str, QIcon | None]:
        label = self._label(item.get("name"), "자료")
        return label, str(item.get("path", "")), lambda checked=False, value=item: self._open_image(value), "🧾", None

    def _memo_item(self, item: dict) -> tuple[str, str, Callable, str, QIcon | None]:
        label = self._label(item.get("title") or item.get("content"), "메모")
        return label, str(item.get("content", "")), lambda checked=False, value=item: self._copy_memo(value), "🗒", None

    def _emoji_items(self) -> list[str]:
        favorites = list(self.main.settings.get("favorite_emojis", []))
        recent = list(self.main.settings.get("recent_emojis", []))
        usage = self.main.settings.get("emoji_usage", {})
        used = sorted(usage, key=lambda emoji: int(usage.get(emoji, 0)), reverse=True)
        defaults = list("😀😄😊😍👍👏🙏💡⭐✅🔥🎉📌")
        result: list[str] = []
        for emoji in favorites + recent + used + defaults:
            if emoji and emoji not in result:
                result.append(emoji)
        return result

    def _copy_text_item(self, item: dict, field: str) -> None:
        bump_usage(item)
        self.main.app.clipboard().setText(str(item.get(field, "")))
        self.main.save_usage_data()

    def _copy_title_item(self, item: dict) -> None:
        bump_usage(item)
        text = render_date_template(item.get("template", ""), business_days=bool(item.get("business_days", False)))
        self.main.app.clipboard().setText(text)
        self.main.save_usage_data()

    def _open_launcher(self, item: dict) -> None:
        try:
            bump_usage(item)
            if self._launcher_type(item) == "site":
                webbrowser.open(str(item.get("url", "")))
            else:
                path = str(item.get("path", ""))
                if not path or not Path(path).exists():
                    show_modern_warning(self.main, "실행 실패", f"경로를 찾을 수 없습니다.\n{path}")
                    return
                os.startfile(path)
            self.main.save_usage_data()
        except Exception as exc:
            show_modern_warning(self.main, "실행 실패", str(exc))

    def _open_image(self, item: dict) -> None:
        image_tab = self.main.tabs[4] if len(self.main.tabs) > 4 else None
        if image_tab is not None and hasattr(image_tab, "view_image"):
            image_tab.view_image(item)

    def _copy_memo(self, item: dict) -> None:
        bump_usage(item)
        self.main.app.clipboard().setText(str(item.get("content", "")))
        self.main.save_usage_data()

    def _copy_emoji(self, emoji: str) -> None:
        self.main.app.clipboard().setText(emoji)
        usage = self.main.settings.setdefault("emoji_usage", {})
        usage[emoji] = int(usage.get(emoji, 0)) + 1
        config.save_settings(self.main.settings)

    def _auto_scroll(self) -> None:
        if not self._shown:
            self._scroll_velocity = 0.0
            return
        pos = self.mapFromGlobal(QCursor.pos())
        if not self.rect().contains(pos):
            self._scroll_velocity = 0.0
            return
        bar: QScrollBar = self.scroll.verticalScrollBar() if self._is_vertical() else self.scroll.horizontalScrollBar()
        if bar.maximum() <= 0:
            self._scroll_velocity = 0.0
            return
        axis_pos = pos.y() if self._is_vertical() else pos.x()
        axis_size = max(1, self.height() if self._is_vertical() else self.width())
        center = axis_size / 2
        half = max(1.0, axis_size / 2)
        normalized = (axis_pos - center) / half
        dead_zone = 0.22
        distance = abs(normalized)
        if distance <= dead_zone:
            target_velocity = 0.0
        else:
            strength = min(1.0, (distance - dead_zone) / (1.0 - dead_zone))
            max_step = 24.0
            target_velocity = (1 if normalized > 0 else -1) * max_step * (strength ** 1.65)
        self._scroll_velocity += (target_velocity - self._scroll_velocity) * 0.28
        if abs(self._scroll_velocity) < 0.08:
            self._scroll_velocity = 0.0
            self._scroll_position = float(bar.value())
            return
        if abs(self._scroll_position - bar.value()) > 2:
            self._scroll_position = float(bar.value())
        self._scroll_position = max(0.0, min(float(bar.maximum()), self._scroll_position + self._scroll_velocity))
        bar.setValue(int(round(self._scroll_position)))

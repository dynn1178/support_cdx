from __future__ import annotations

import random
import subprocess
import sys
from datetime import date as py_date, datetime, time as dt_time, timedelta
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt6.QtCore import QDate, QDateTime, QEasingCurve, QMimeData, QPoint, QPropertyAnimation, QRect, QRectF, QSize, QTime, QTimer, Qt
from PyQt6.QtGui import QCursor, QDrag, QTextCharFormat, QColor, QPainter, QPen, QPolygon
from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QApplication,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizeGrip,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from app import config
from app.utils import new_id, now_iso, short_preview
from ui.common import (
    CARD_ACTION_ICON_SIZE,
    CARD_ACTION_ROW_MARGIN_X,
    CARD_ACTION_ROW_MARGIN_Y,
    CARD_ACTION_ROW_SPACING,
    BOTTOM_ACTION_HEIGHT,
    CORNER_CONTROL_HEIGHT,
    CORNER_SEARCH_WIDTH,
    GRID_PANEL_MARGINS,
    PRIORITY_STYLES,
    GridPanel,
    SortControls,
    add_card_actions,
    add_card_status_label,
    add_favorite_badge_to_card,
    apply_manual_reorder,
    apply_modern_dialog_style,
    ask_modern_question,
    bottom_action_bar,
    bump_usage,
    confirm_delete,
    fit_combo_to_contents,
    make_card,
    make_icon_button,
    normalize_todo_groups,
    remove_favorite_badge_from_card,
    set_card_action_widget,
    set_corner_button_policy,
    show_card_status,
    show_modern_info,
    show_topmost_modern_info,
    show_modern_warning,
)
from ui.groups import (
    GROUP_SCOPE_MEMO,
    GroupDialog,
    count_group_contents,
    create_group,
    delete_group,
    group_by_id,
    group_id,
    groups_in,
    item_group_id,
    make_back_card,
    make_breadcrumb_label,
    make_group_card,
    show_move_to_group_menu,
    toggle_group_favorite,
    update_breadcrumb_label,
    valid_group_id,
)


MEMO_BOTTOM_ACTION_STYLE = (
    "QPushButton {"
    "background: #FFFFFF; border: 1px solid #D1D5DB; border-radius: 6px;"
    "padding: 6px 12px; color: #1F2433; font-weight: 700;"
    f"min-height: {BOTTOM_ACTION_HEIGHT - 8}px;"
    "}"
    "QPushButton:hover { background: #EEF4FF; border-color: #3B6CF5; }"
    "QPushButton:pressed { background: #F8FAFC; }"
    "QPushButton:disabled { background: #E5E7EB; color: #94A3B8; border: 1px solid #CBD5E1; }"
)


MEMO_COLORS = {
    "노랑": "#FFF9C4",
    "하늘": "#DFF3FF",
    "연두": "#E5F8D2",
    "분홍": "#FFE1EA",
    "흰색": "#FFFFFF",
}

MEMO_COLOR_LIST = list(MEMO_COLORS.keys())

MEMO_INDEX_EMOJIS = [
    "📝", "⭐", "📌", "🔥", "✅", "💡", "⚡", "🎯", "📋", "🔖",
    "💬", "📣", "❤️", "😊", "🎨", "🧰", "⚙️", "🔒", "💼", "📊",
    "🏠", "📅", "☕", "🎁", "🎬", "🎵", "🎮", "🚀", "💻", "🔑",
]

_INDEX_COLORS_CYCLE = [
    "노랑", "하늘", "연두", "분홍", "흰색",
    "하늘", "연두", "노랑", "분홍", "하늘",
]


class _MemoIconPickerDialog(QDialog):
    def __init__(self, current_icon: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("아이콘 선택")
        self.setModal(True)
        apply_modern_dialog_style(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(10)

        input_row = QHBoxLayout()
        input_row.setContentsMargins(0, 0, 0, 0)
        input_row.setSpacing(8)
        input_row.addWidget(QLabel("직접 입력:"))
        self._input = QLineEdit(current_icon or "")
        self._input.setMaxLength(3)
        self._input.setPlaceholderText("이모지 또는 2-3글자")
        self._input.setFixedWidth(120)
        input_row.addWidget(self._input)
        input_row.addStretch(1)
        clear_btn = QPushButton("초기화")
        clear_btn.clicked.connect(lambda: self._input.clear())
        input_row.addWidget(clear_btn)
        layout.addLayout(input_row)

        grid_lbl = QLabel("이모지 빠른 선택:")
        layout.addWidget(grid_lbl)

        emoji_widget = QWidget()
        grid = QGridLayout(emoji_widget)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(4)
        cols = 10
        for idx, emoji in enumerate(MEMO_INDEX_EMOJIS):
            btn = QPushButton(emoji)
            btn.setFixedSize(28, 26)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { background: transparent; border: 1px solid rgba(148,163,184,60);"
                " border-radius: 5px; font-size: 11pt; padding: 0; margin: 0; }"
                "QPushButton:hover { background: rgba(148,163,184,30); }"
                "QPushButton:pressed { background: rgba(59,108,245,40); }"
            )
            btn.clicked.connect(lambda checked=False, e=emoji: self._select(e))
            grid.addWidget(btn, idx // cols, idx % cols)
        layout.addWidget(emoji_widget)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("확인")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setMinimumWidth(340)

    def _select(self, emoji: str) -> None:
        self._input.setText(emoji)

    def result_icon(self) -> str:
        return self._input.text().strip()[:3]


WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]
REPEAT_LABELS = {"daily": "매일", "weekly": "매주", "monthly": "매월", "yearly": "매년", "weekday": "매주"}

_GROUP_HDR_COLORS = ["#3B6CF5", "#2EA672", "#F59E0B"]  # 그룹 헤더 색상 (1~3번)

_TIME_BTN_STYLE = (
    "QPushButton { background: #FFFFFF; border: 1px solid #D1D5DB; color: #374151; "
    "border-radius: 4px; padding: 0 4px; min-width: 42px; }"
    "QPushButton:hover { background: #F3F4F6; border-color: #9CA3AF; }"
    "QPushButton:pressed { background: #E5E7EB; }"
)

_TIMER_VALUE_STYLE = (
    "QSpinBox#timerTextValue { background: transparent; border: 0; color: #111827; "
    "padding: 0; font-size: 10pt; }"
    "QSpinBox#timerTextValue:focus { background: transparent; border: 0; }"
    "QSpinBox#timerTextValue::up-button, QSpinBox#timerTextValue::down-button { "
    "width: 0; height: 0; border: 0; }"
)

_TIMER_COMPACT_COMBO_STYLE = (
    "QComboBox#timerCompactCombo { background: transparent; background-color: transparent; border: 1px solid #D1D5DB; "
    "border-radius: 5px; padding: 1px 8px; min-height: 16px; color: #111827; }"
    "QComboBox#timerCompactCombo:focus { border-color: #3B6CF5; }"
    "QComboBox#timerCompactCombo::drop-down { border: 0; width: 0; }"
    "QComboBox#timerCompactCombo::down-arrow { image: none; width: 0; height: 0; }"
    "QComboBox#timerCompactCombo QAbstractItemView { padding: 2px; }"
)


def memo_card_preview(text: str, limit: int = 160, max_lines: int = 2) -> str:
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        return ""
    preview = "\n".join(lines[:max_lines])
    if len(lines) > max_lines:
        preview += " ..."
    if len(preview) <= limit:
        return preview
    return preview[: limit - 1].rstrip() + "..."


def display_datetime(value: str, repeat: str = "none") -> str:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return value.replace("T", " ")
    text = f"{parsed:%Y-%m-%d} {WEEKDAYS[parsed.weekday()]}요일 {parsed:%H:%M}"
    repeat_label = REPEAT_LABELS.get(repeat)
    return f"{text} ({repeat_label})" if repeat_label else text


class CornerGrip(QSizeGrip):
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(47, 42, 20, 75)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        points = [
            self.rect().bottomRight(),
            self.rect().bottomLeft() + QPoint(self.width() // 2, 0),
            self.rect().topRight() + QPoint(0, self.height() // 2),
        ]
        painter.drawPolygon(QPolygon(points))
        painter.setPen(QPen(QColor(255, 255, 255, 130), 1))
        painter.drawLine(self.width() - 12, self.height() - 3, self.width() - 3, self.height() - 12)


class StickyMemoDialog(QDialog):
    SNAP_DISTANCE = 16
    COMPACT_WIDTH = 260
    COMPACT_HEIGHT = 24

    def __init__(self, memo: dict, main=None, on_saved=None) -> None:
        super().__init__()
        self.memo = memo
        self.main = main
        self.on_saved = on_saved
        self.drag_position: QPoint | None = None
        self.compact = bool(memo.get("sticker_compact", False))
        self.normal_geometry = None
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.persist)
        self.setWindowTitle(memo.get("title", "메모"))
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        if memo.get("always_on_top", True):
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.drag_bar = QLabel("")
        self.drag_bar.setFixedHeight(12)
        self.drag_bar.setContentsMargins(8, 0, 6, 0)
        self.drag_bar.mousePressEvent = self.drag_bar_mouse_press
        self.drag_bar.mouseMoveEvent = self.drag_bar_mouse_move
        self.drag_bar.mouseReleaseEvent = self.drag_bar_mouse_release
        self.drag_bar.mouseDoubleClickEvent = self.drag_bar_mouse_double_click
        layout.addWidget(self.drag_bar)
        self.text = QTextEdit()
        self.text.setPlainText(memo.get("content", ""))
        self.text.textChanged.connect(self.schedule_save)
        self.text.textChanged.connect(self.update_drag_bar_text)
        layout.addWidget(self.text, 1)
        controls = QHBoxLayout()
        controls.setContentsMargins(6, 2, 6, 4)
        controls.setSpacing(3)
        self.always_on_top = QCheckBox("항상 위")
        self.always_on_top.setChecked(bool(memo.get("always_on_top", True)))
        self.always_on_top.toggled.connect(self.toggle_always_on_top)
        self.color = QComboBox()
        self.color.addItems(list(MEMO_COLORS))
        self.color.setCurrentText(memo.get("background", "노랑") if memo.get("background", "노랑") in MEMO_COLORS else "노랑")
        self.color.currentTextChanged.connect(self.apply_color)
        self.color.currentTextChanged.connect(self.schedule_save)
        self.color.setFixedWidth(58)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(40, 100)
        self.slider.setValue(int(memo.get("opacity", 95)))
        self.slider.setFixedWidth(64)
        self.slider.valueChanged.connect(lambda value: self.setWindowOpacity(value / 100))
        self.slider.valueChanged.connect(self.schedule_save)
        self.icon_btn = QPushButton(self._get_icon_text())
        self.icon_btn.setObjectName("stickyMemoIconButton")
        self.icon_btn.setFixedSize(36, 24)
        self.icon_btn.setToolTip("아이콘 변경 (인덱스 카드 표시 문자)")
        self.icon_btn.clicked.connect(self._open_icon_picker)
        self.close_button = QPushButton("×")
        self.close_button.setFixedSize(26, 22)
        self.close_button.clicked.connect(self.accept)
        self.grip = CornerGrip(self)
        self.grip.setFixedSize(18, 18)
        controls.addWidget(self.always_on_top)
        controls.addWidget(self.color)
        controls.addWidget(self.icon_btn)
        controls.addStretch(1)
        controls.addWidget(self.slider)
        controls.addWidget(self.close_button)
        controls.addWidget(self.grip)
        layout.addLayout(controls)
        self.apply_color()
        self.setWindowOpacity(self.slider.value() / 100)
        self.set_controls_visible(False)
        self.resize(int(memo.get("width", 300)), int(memo.get("height", 240)))
        if "x" in memo and "y" in memo:
            self.move(int(memo.get("x", 0)), int(memo.get("y", 0)))
        else:
            self.move_default_position()
        self.memo["sticker_open"] = True
        self.update_drag_bar_text()
        if self.compact:
            # 위치 재계산 없이 compact 시각 상태만 직접 적용 (apply_compact_state 호출 시 위치 drift 발생 방지)
            self.text.hide()
            self.set_controls_visible(False)
            self.drag_bar.setFixedHeight(22)
            self.setFixedSize(self.COMPACT_WIDTH, self.COMPACT_HEIGHT)
            self.update_drag_bar_text()

    def apply_color(self, *_args) -> None:
        color = MEMO_COLORS.get(self.color.currentText(), "#FFF9C4")
        self.setStyleSheet(
            f"""
            QDialog {{ background: {color}; border: 1px solid #B8B08A; }}
            QLabel {{ background: rgba(0,0,0,22); }}
            QTextEdit {{ background: transparent; border: 0; color: #2F2A14; padding: 6px; }}
            QPushButton {{ background: transparent; border: 0; color: #2F2A14; font-weight: 900; padding: 0; font-size: 15pt; }}
            QPushButton#stickyMemoIconButton {{ font-size: 11pt; padding: 0 1px 1px 1px; min-width: 36px; min-height: 24px; }}
            QCheckBox, QComboBox {{ background: transparent; color: #2F2A14; border: 0; }}
            QComboBox::drop-down {{ border: 0; width: 0; }}
            QSlider {{ background: transparent; }}
            QSlider::groove:horizontal {{ height: 3px; background: rgba(47,42,20,70); border-radius: 2px; }}
            QSlider::handle:horizontal {{ background: #2F2A14; width: 8px; margin: -4px 0; border-radius: 4px; }}
            """
        )

    def toggle_always_on_top(self, checked: bool) -> None:
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, checked)
        self.show()
        self.schedule_save()

    def schedule_save(self, *_args) -> None:
        self.save_timer.start(400)

    def reload_from_memo(self) -> None:
        """Refresh visible fields after the backing memo was edited elsewhere."""
        if self.save_timer.isActive():
            self.save_timer.stop()
        content = str(self.memo.get("content", ""))
        if self.text.toPlainText() != content:
            self.text.blockSignals(True)
            self.text.setPlainText(content)
            self.text.blockSignals(False)
        background = self.memo.get("background", MEMO_COLOR_LIST[0])
        if background in MEMO_COLORS and self.color.currentText() != background:
            self.color.blockSignals(True)
            self.color.setCurrentText(background)
            self.color.blockSignals(False)
            self.apply_color()
        always_on_top = bool(self.memo.get("always_on_top", True))
        if self.always_on_top.isChecked() != always_on_top:
            self.always_on_top.blockSignals(True)
            self.always_on_top.setChecked(always_on_top)
            self.always_on_top.blockSignals(False)
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, always_on_top)
            self.show()
        if "opacity" in self.memo:
            opacity = int(self.memo.get("opacity", 95) or 95)
            if self.slider.value() != opacity:
                self.slider.blockSignals(True)
                self.slider.setValue(opacity)
                self.slider.blockSignals(False)
                self.setWindowOpacity(opacity / 100)
        self.setWindowTitle(self.memo.get("title", "메모"))
        self.icon_btn.setText(self._get_icon_text() or "🗒")
        self.update_drag_bar_text()

    def first_line(self) -> str:
        for line in self.text.toPlainText().splitlines():
            line = line.strip()
            if line:
                return line
        return self.memo.get("title", "메모")

    def update_drag_bar_text(self) -> None:
        self.drag_bar.setText(self.first_line() if self.compact else "")

    def move_default_position(self) -> None:
        screen = QApplication.screenAt(self.pos()) or QApplication.primaryScreen()
        if not screen:
            return
        area = screen.availableGeometry()
        margin = 18
        self.move(area.right() - self.width() - margin + 1, area.top() + margin)

    def _get_icon_text(self) -> str:
        custom = str(self.memo.get("index_icon") or "").strip()
        if not custom:
            return "◇"
        if custom:
            return custom
        content = self.text.toPlainText() if hasattr(self, "text") else str(self.memo.get("content") or "")
        for line in content.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped[:3]
        title = str(self.memo.get("title") or "")
        if not title:
            return "◇"
        return title[:3] if title else "📝"

    def _get_icon_text(self) -> str:
        custom = str(self.memo.get("index_icon") or "").strip()
        if custom:
            return custom
        content = self.text.toPlainText() if hasattr(self, "text") else str(self.memo.get("content") or "")
        for line in content.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped[:3]
        title = str(self.memo.get("title") or "")
        return title[:3] if title else "◇"

    def _open_icon_picker(self) -> None:
        dialog = _MemoIconPickerDialog(str(self.memo.get("index_icon") or ""), self)
        if dialog.exec() == dialog.DialogCode.Accepted:
            icon = dialog.result_icon()
            self.memo["index_icon"] = icon if icon else None
            self.icon_btn.setText(self._get_icon_text() or "📝")
            self.schedule_save()

    def set_controls_visible(self, visible: bool) -> None:
        self.slider.setVisible(visible)
        self.close_button.setVisible(visible)
        self.always_on_top.setVisible(visible)
        self.color.setVisible(visible)
        self.icon_btn.setVisible(visible)
        self.grip.setVisible(visible)

    def enterEvent(self, event) -> None:
        if not self.compact:
            self.set_controls_visible(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        QTimer.singleShot(180, self.hide_controls_if_idle)
        super().leaveEvent(event)

    def hide_controls_if_idle(self) -> None:
        if self.compact:
            self.set_controls_visible(False)
            return
        if self.underMouse() or self.color.view().isVisible() or self.color.hasFocus():
            return
        self.set_controls_visible(False)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() <= self.drag_bar.height() + 4:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def drag_bar_mouse_press(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self.drag_position and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
        super().mouseMoveEvent(event)

    def drag_bar_mouse_move(self, event) -> None:
        if self.drag_position and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self.drag_position = None
        self.snap_to_neighbors()
        self.schedule_save()
        super().mouseReleaseEvent(event)

    def drag_bar_mouse_release(self, event) -> None:
        self.drag_position = None
        self.snap_to_neighbors()
        self.schedule_save()
        event.accept()

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() <= self.drag_bar.height() + 4:
            self.toggle_compact()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def drag_bar_mouse_double_click(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_compact()
        event.accept()

    def toggle_compact(self) -> None:
        self.compact = not self.compact
        self.apply_compact_state(save=True)

    def apply_compact_state(self, save: bool = True) -> None:
        # 현재 스티커 위치 기준으로 화면 사분면을 계산해 앵커 꼭지점을 결정한다.
        # 우측 상단 → 우상단 기준, 좌측 하단 → 좌하단 기준으로 접기/펼치기 후 위치를 보정한다.
        screen = QApplication.screenAt(self.geometry().center()) or QApplication.primaryScreen()
        screen_rect = screen.availableGeometry() if screen else self.geometry()
        geo = self.geometry()
        anchor_right = geo.left() > screen_rect.center().x()
        anchor_bottom = geo.top() > screen_rect.center().y()

        if self.compact:
            if self.normal_geometry is None:
                self.normal_geometry = self.geometry()
            self.memo["normal_width"] = self.normal_geometry.width()
            self.memo["normal_height"] = self.normal_geometry.height()
            self.text.hide()
            self.set_controls_visible(False)
            self.drag_bar.setFixedHeight(22)
            new_w, new_h = self.COMPACT_WIDTH, self.COMPACT_HEIGHT
            self.setFixedSize(new_w, new_h)
            new_x = geo.right() - new_w + 1 if anchor_right else geo.left()
            new_y = geo.bottom() - new_h + 1 if anchor_bottom else geo.top()
            self.move(new_x, new_y)
        else:
            self.setMinimumWidth(0)
            self.setMaximumWidth(16777215)
            self.setMaximumHeight(16777215)
            self.setMinimumHeight(80)
            self.drag_bar.setFixedHeight(12)
            self.text.show()
            new_w = int(self.memo.get("normal_width", self.memo.get("width", 300)) or 300)
            new_h = max(120, int(self.memo.get("normal_height", self.memo.get("height", 240)) or 240))
            self.resize(new_w, new_h)
            new_x = geo.right() - new_w + 1 if anchor_right else geo.left()
            new_y = geo.bottom() - new_h + 1 if anchor_bottom else geo.top()
            self.move(new_x, new_y)
            self.normal_geometry = self.geometry()
        self.update_drag_bar_text()
        if save:
            self.schedule_save()

    def other_stickers(self) -> list["StickyMemoDialog"]:
        if self.main is None or len(getattr(self.main, "tabs", [])) <= 6:
            return []
        memo_tab = self.main.tabs[6]
        windows = getattr(memo_tab, "sticky_windows", {})
        return [dialog for dialog in windows.values() if dialog is not self and dialog.isVisible()]

    def snap_to_neighbors(self) -> None:
        rect = self.geometry()
        new_x = rect.x()
        new_y = rect.y()
        for other in self.other_stickers():
            target = other.geometry()
            if abs(rect.left() - target.right() - 1) <= self.SNAP_DISTANCE:
                new_x = target.right() + 1
            elif abs(rect.right() - target.left() + 1) <= self.SNAP_DISTANCE:
                new_x = target.left() - rect.width()
            elif abs(rect.left() - target.left()) <= self.SNAP_DISTANCE:
                new_x = target.left()
            elif abs(rect.right() - target.right()) <= self.SNAP_DISTANCE:
                new_x = target.right() - rect.width() + 1

            if abs(rect.top() - target.bottom() - 1) <= self.SNAP_DISTANCE:
                new_y = target.bottom() + 1
            elif abs(rect.bottom() - target.top() + 1) <= self.SNAP_DISTANCE:
                new_y = target.top() - rect.height()
            elif abs(rect.top() - target.top()) <= self.SNAP_DISTANCE:
                new_y = target.top()
            elif abs(rect.bottom() - target.bottom()) <= self.SNAP_DISTANCE:
                new_y = target.bottom() - rect.height() + 1
        if new_x != rect.x() or new_y != rect.y():
            self.move(new_x, new_y)

    def persist(self) -> None:
        self.memo["content"] = self.text.toPlainText()
        self.update_drag_bar_text()
        self.memo["always_on_top"] = self.always_on_top.isChecked()
        self.memo["background"] = self.color.currentText()
        self.memo["opacity"] = self.slider.value()
        self.memo["sticker_compact"] = self.compact
        if self.compact:
            self.memo["normal_width"] = int(self.memo.get("normal_width", self.width()))
            self.memo["normal_height"] = int(self.memo.get("normal_height", self.memo.get("height", 240)) or 240)
        else:
            self.memo["width"] = self.width()
            self.memo["height"] = self.height()
            self.memo["normal_width"] = self.width()
            self.memo["normal_height"] = self.height()
        self.memo["x"] = self.x()
        self.memo["y"] = self.y()
        self.memo["sticker_open"] = bool(self.memo.get("sticker_open", self.isVisible()))
        self.memo["updated_at"] = now_iso()
        if self.main is not None:
            config.save_template(self.main.template_index, self.main.data)
        if self.on_saved:
            self.on_saved()

    def accept(self) -> None:
        self.memo["sticker_open"] = False
        self.persist()
        super().accept()

    def closeEvent(self, event) -> None:
        self.persist()
        super().closeEvent(event)


class MemoIndexFace(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._background = QColor("#FFF9C4")
        self._border = QColor("#B8B08A")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def set_colors(self, background: str, border: str = "#B8B08A") -> None:
        bg = QColor(background)
        bd = QColor(border)
        self._background = bg if bg.isValid() else QColor("#FFF9C4")
        self._border = bd if bd.isValid() else QColor("#B8B08A")
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(self._border, 1.0))
        painter.setBrush(self._background)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.drawRoundedRect(rect, 8.0, 8.0)
        super().paintEvent(event)


class MemoIndexCard(QWidget):
    """인덱스 형태 메모 카드. 화면 좌/우 가장자리에 세로로 배열되며 마우스 오버 시 확대 표시됨."""

    COMPACT_W = 40
    COMPACT_H = 40
    COMPACT_GAP = 2
    EXPANDED_W = 300
    SLOT_SWITCH_DEADZONE = 2
    LINE_H = 21      # 9pt 기본 폰트 행간 + 여유
    CTRL_H = 24      # 자연 높이 기준 컨트롤 행 (계산용)
    MAX_LINES = 10
    _hover_manager_timer: QTimer | None = None

    _currently_expanded: "MemoIndexCard | None" = None  # 현재 열린 카드
    _all_cards: "list[MemoIndexCard]" = []              # 모든 카드 레지스트리

    def __init__(self, memo: dict, main=None, on_saved=None) -> None:
        super().__init__()
        self.memo = memo
        self.main = main
        self.on_saved = on_saved
        self._expanded = False
        self._base_x: int | None = None
        self._base_y: int | None = None
        self._anim_cb = None
        self._hover_regions: list[QRect] = []
        self._last_mouse_y: int | None = None
        self._expanded_h_cache: tuple[str, int] | None = None

        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.persist)

        _flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if memo.get("always_on_top", True):
            _flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(_flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setObjectName("memoIndexCard")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # --- 접힌 면 (compact) ---
        self._compact_face = MemoIndexFace()
        self._compact_face.setObjectName("memoIndexFace")
        cl = QVBoxLayout(self._compact_face)
        cl.setContentsMargins(2, 3, 2, 3)
        cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_lbl = QLabel()
        self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_lbl.setWordWrap(True)
        cl.addWidget(self._icon_lbl)
        outer.addWidget(self._compact_face)

        # 아이콘 페이드 효과
        self._icon_effect = QGraphicsOpacityEffect()
        self._icon_effect.setOpacity(1.0)
        self._icon_lbl.setGraphicsEffect(self._icon_effect)
        self._icon_fade = QPropertyAnimation(self._icon_effect, b"opacity")
        self._icon_fade.setDuration(80)
        self._icon_fade.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._icon_fade.finished.connect(self._on_icon_fade_done)
        self._icon_fade_phase: str | None = None
        self._icon_pending: str | None = None
        self._icon_timer = QTimer(self)
        self._icon_timer.setSingleShot(True)
        self._icon_timer.timeout.connect(self._do_icon_transition)

        # --- 펼쳐진 면 (expanded) ---
        self._expanded_face = MemoIndexFace()
        self._expanded_face.setObjectName("memoIndexFace")
        el = QVBoxLayout(self._expanded_face)
        el.setContentsMargins(6, 5, 6, 5)
        el.setSpacing(2)

        self._color = QComboBox()
        self._color.addItems(MEMO_COLOR_LIST)
        bg = memo.get("background", "노랑")
        self._color.setCurrentText(bg if bg in MEMO_COLORS else "노랑")
        self._color.setFixedWidth(58)
        self._color.setVisible(False)
        self._color.currentTextChanged.connect(self._apply_color)
        self._color.currentTextChanged.connect(self.schedule_save)

        self._icon_pick_btn = QPushButton()
        self._icon_pick_btn.setObjectName("memoIndexIconButton")
        self._icon_pick_btn.setFixedSize(34, 22)
        self._icon_pick_btn.setToolTip("아이콘 변경")
        self._icon_pick_btn.setVisible(False)
        self._icon_pick_btn.clicked.connect(self._open_icon_picker)

        close_btn = QPushButton("×")
        close_btn.setFixedSize(22, 22)
        close_btn.clicked.connect(self.accept)

        self._text = QTextEdit()
        self._text.setPlainText(memo.get("content", ""))
        self._text.textChanged.connect(self.schedule_save)
        self._text.textChanged.connect(self._update_icon)
        self._text.textChanged.connect(self._invalidate_expanded_height)

        self._always_on_top_chk = QCheckBox("항상 위")
        self._always_on_top_chk.setObjectName("memoIndexBottomControl")
        self._always_on_top_chk.setChecked(bool(memo.get("always_on_top", True)))
        self._always_on_top_chk.setVisible(False)
        self._always_on_top_chk.toggled.connect(self._toggle_always_on_top)

        AV = Qt.AlignmentFlag.AlignVCenter
        ctrl_row = QHBoxLayout()
        ctrl_row.setContentsMargins(0, 0, 0, 0)
        ctrl_row.setSpacing(4)
        ctrl_row.addWidget(self._icon_pick_btn, 0, AV)
        ctrl_row.addStretch(1)
        ctrl_row.addWidget(self._color, 0, AV)
        ctrl_row.addStretch(1)
        ctrl_row.addWidget(close_btn, 0, AV)
        ctrl_row.addWidget(self._always_on_top_chk, 0, AV)

        el.addWidget(self._text, 1)
        el.addLayout(ctrl_row)

        self._expanded_face.hide()
        outer.addWidget(self._expanded_face)

        # 애니메이션
        self._anim = QPropertyAnimation(self, b"geometry")
        self._anim.setDuration(100)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.finished.connect(self._on_anim_done)

        # 슬롯 전환 타이머 (위아래 마우스 이동 시 순차 확장)
        self._switch_target: MemoIndexCard | None = None
        self._switch_timer = QTimer(self)
        self._switch_timer.setSingleShot(True)
        self._switch_timer.setInterval(200)  # 200ms debounce — 너무 빠른 전환 방지
        self._switch_timer.timeout.connect(self._execute_switch)
        self._switch_timer.setInterval(70)

        self._hover_watch_timer = QTimer(self)
        self._hover_watch_timer.setInterval(80)
        self._hover_watch_timer.timeout.connect(self._watch_hover_state)

        self._update_icon()
        self._apply_color()
        self._compute_expanded_h()
        self.setFixedSize(self.COMPACT_W, self.COMPACT_H)
        self._apply_rounded_mask()
        memo["sticker_open"] = True
        MemoIndexCard._all_cards.append(self)
        MemoIndexCard._ensure_hover_manager()

    # ── 아이콘 ──────────────────────────────────────────────────────

    @staticmethod
    def _truncate_index_text(text: str) -> str:
        """한글 포함 시 최대 2자, 그 외 최대 3자."""
        has_hangul = any(0xAC00 <= ord(c) <= 0xD7A3 for c in text)
        return text[: 2 if has_hangul else 3]

    def _get_index_text(self) -> str:
        """인덱스 라벨용 텍스트. 커스텀 아이콘 우선, 없으면 내용 첫 글자."""
        custom = str(self.memo.get("index_icon") or "").strip()
        if custom:
            return self._truncate_index_text(custom)
        content = self._text.toPlainText() if hasattr(self, "_text") else str(self.memo.get("content") or "")
        for line in content.splitlines():
            stripped = line.strip()
            if stripped:
                return self._truncate_index_text(stripped)
        title = str(self.memo.get("title") or "")
        return self._truncate_index_text(title) if title else ""

    def _get_button_text(self) -> str:
        """확장 카드 아이콘 버튼용 텍스트. 미지정 시 ❓."""
        custom = str(self.memo.get("index_icon") or "").strip()
        return custom if custom else "❓"

    def _get_button_text(self) -> str:
        custom = str(self.memo.get("index_icon") or "").strip()
        return custom if custom else "◇"

    @classmethod
    def _ensure_hover_manager(cls) -> None:
        timer = cls._hover_manager_timer
        if timer is None:
            timer = QTimer()
            timer.setInterval(50)
            timer.timeout.connect(cls._manage_hover_state)
            cls._hover_manager_timer = timer
        if not timer.isActive():
            timer.start()

    @classmethod
    def _stop_hover_manager_if_unused(cls) -> None:
        if any(card.isVisible() for card in cls._all_cards):
            return
        timer = cls._hover_manager_timer
        if timer is not None:
            timer.stop()

    @classmethod
    def _card_at_global_slot(cls, pos: QPoint) -> "MemoIndexCard | None":
        for card in cls._all_cards:
            if not card.isVisible() or card._base_x is None or card._base_y is None:
                continue
            slot = QRect(card._base_x, card._base_y, card.COMPACT_W, card.COMPACT_H)
            if slot.adjusted(0, card.SLOT_SWITCH_DEADZONE, 0, -card.SLOT_SWITCH_DEADZONE).contains(pos):
                return card
        return None

    @classmethod
    def _manage_hover_state(cls) -> None:
        visible_cards = [card for card in cls._all_cards if card.isVisible()]
        if not visible_cards:
            cls._stop_hover_manager_if_unused()
            return
        pos = QCursor.pos()
        slot_card = cls._card_at_global_slot(pos)
        if slot_card is not None:
            if not slot_card._expanded:
                slot_card._do_expand()
            slot_card.raise_()
            return
        expanded = cls._currently_expanded
        if expanded is not None and expanded.isVisible() and expanded._expanded:
            if expanded._cursor_in_hover_regions():
                return
            expanded._do_collapse()

    def _update_icon(self) -> None:
        self._icon_timer.start(400)

    def _do_icon_transition(self) -> None:
        if hasattr(self, "_icon_pick_btn"):
            self._icon_pick_btn.setText(self._get_button_text())
        idx_txt = self._get_index_text()
        if self._icon_lbl.text() == idx_txt:
            return
        self._icon_pending = idx_txt
        if self._icon_fade_phase is not None:
            self._icon_lbl.setText(idx_txt)
            return
        self._icon_fade_phase = "out"
        self._icon_fade.stop()
        self._icon_fade.setStartValue(1.0)
        self._icon_fade.setEndValue(0.0)
        self._icon_fade.start()

    def _on_icon_fade_done(self) -> None:
        if self._icon_fade_phase == "out":
            if self._icon_pending is not None:
                self._icon_lbl.setText(self._icon_pending)
                self._icon_pending = None
            self._icon_fade_phase = "in"
            self._icon_fade.setStartValue(0.0)
            self._icon_fade.setEndValue(1.0)
            self._icon_fade.start()
        else:
            self._icon_fade_phase = None

    def _open_icon_picker(self) -> None:
        dialog = _MemoIconPickerDialog(str(self.memo.get("index_icon") or ""), self)
        if dialog.exec() == dialog.DialogCode.Accepted:
            icon = dialog.result_icon()
            self.memo["index_icon"] = icon if icon else None
            self._icon_timer.stop()
            self._do_icon_transition()
            self.schedule_save()

    # ── 색상 ──────────────────────────────────────────────────────

    def _apply_color(self, *_args) -> None:
        color = MEMO_COLORS.get(self._color.currentText(), "#FFF9C4")
        self._compact_face.set_colors(color)
        self._expanded_face.set_colors(color)
        self.setStyleSheet(f"""
            QWidget#memoIndexCard {{ background: transparent; border: 0; }}
            QWidget#memoIndexFace {{ background: transparent; border: 0; }}
            QWidget#memoIndexFace QWidget {{ background: transparent; border: 0; }}
            QLabel {{ background: transparent; color: #2F2A14; font-size: 9pt; font-weight: bold; border: 0; }}
            QPushButton {{ background: transparent; border: 0; color: #2F2A14; font-weight: 900; font-size: 9pt; }}
            QPushButton:hover {{ background: rgba(47,42,20,15); border-radius: 4px; }}
            QPushButton#memoIndexIconButton {{ font-size: 9pt; padding: 0 1px 1px 1px; min-width: 34px; min-height: 22px; max-width: 34px; max-height: 22px; }}
            QComboBox {{ background: transparent; border: 0; color: #2F2A14; font-size: 9pt; }}
            QComboBox::drop-down {{ border: 0; width: 0; }}
            QTextEdit {{ background: transparent; border: 0; color: #2F2A14; padding: 3px; }}
            QCheckBox {{ background: transparent; color: #2F2A14; border: 0; font-size: 9pt; }}
            QCheckBox::indicator {{ width: 12px; height: 12px; }}
        """)
        self.memo["background"] = self._color.currentText()

    def _apply_rounded_mask(self) -> None:
        self.clearMask()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_rounded_mask()

    # ── 항상 위 토글 ────────────────────────────────────────────────

    def _toggle_always_on_top(self, checked: bool) -> None:
        self.memo["always_on_top"] = checked
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if checked:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()
        self.schedule_save()

    def reload_from_memo(self) -> None:
        """Refresh visible fields after the backing memo was edited elsewhere."""
        if self.save_timer.isActive():
            self.save_timer.stop()
        content = str(self.memo.get("content", ""))
        if self._text.toPlainText() != content:
            self._text.blockSignals(True)
            self._text.setPlainText(content)
            self._text.blockSignals(False)
            self._invalidate_expanded_height()
            self._update_icon()
        background = self.memo.get("background", MEMO_COLOR_LIST[0])
        if background in MEMO_COLORS and self._color.currentText() != background:
            self._color.blockSignals(True)
            self._color.setCurrentText(background)
            self._color.blockSignals(False)
            self._apply_color()
        always_on_top = bool(self.memo.get("always_on_top", True))
        if self._always_on_top_chk.isChecked() != always_on_top:
            self._always_on_top_chk.blockSignals(True)
            self._always_on_top_chk.setChecked(always_on_top)
            self._always_on_top_chk.blockSignals(False)
            flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
            if always_on_top:
                flags |= Qt.WindowType.WindowStaysOnTopHint
            self.setWindowFlags(flags)
            self.show()
        self._do_icon_transition()
        if self._expanded:
            self._do_expand()

    # ── 위치 지정 ──────────────────────────────────────────────────

    def set_position(self, x: int, y: int) -> None:
        """정렬 시 이 카드의 compact 기준 위치를 설정한다."""
        self.reset_compact_geometry()
        self._base_x = x
        self._base_y = y
        self.memo["index_x"] = x
        self.memo["index_y"] = y
        self._hover_regions = [QRect(x, y, self.COMPACT_W, self.COMPACT_H)]
        self.move(x, y)
        self.reset_compact_geometry()

    def reset_compact_geometry(self) -> None:
        """Return to the exact compact card size after screen/layout changes."""
        self._anim.stop()
        self._expanded = False
        if MemoIndexCard._currently_expanded is self:
            MemoIndexCard._currently_expanded = None
        self._set_hover_controls_visible(False)
        self._expanded_face.hide()
        self._compact_face.show()
        self.setFixedSize(self.COMPACT_W, self.COMPACT_H)
        if self._base_x is not None and self._base_y is not None:
            self.move(self._base_x, self._base_y)
            self._hover_regions = [QRect(self._base_x, self._base_y, self.COMPACT_W, self.COMPACT_H)]
        self._apply_rounded_mask()

    def _side(self) -> str:
        return str((getattr(self.main, "settings", {}) if self.main else {}).get("sticky_memo_index_side", "right") or "right")

    # ── 확대/축소 ──────────────────────────────────────────────────

    def _invalidate_expanded_height(self) -> None:
        self._expanded_h_cache = None

    def _compute_expanded_h(self) -> int:
        content = self._text.toPlainText()
        if self._expanded_h_cache is not None and self._expanded_h_cache[0] == content:
            return self._expanded_h_cache[1]
        lines = max(1, content.count("\n") + 1) if content.strip() else 1
        if lines <= self.MAX_LINES:
            self._text.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            text_h = lines * self.LINE_H + 10   # +10: QTextEdit 상하 패딩
        else:
            self._text.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            text_h = self.MAX_LINES * self.LINE_H + 10
        # el: top(5) + text + spacing(2) + ctrl_row + bottom(5)
        height = max(70, 5 + text_h + 2 + self.CTRL_H + 5)
        self._expanded_h_cache = (content, height)
        return height

    def enterEvent(self, event) -> None:
        if not self._expanded:
            self._do_expand()
        else:
            self._set_hover_controls_visible(self._cursor_in_expanded_region())
        super().enterEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if not self._expanded:
            self._do_expand()
        else:
            self._set_hover_controls_visible(self._cursor_in_expanded_region())
            global_y = int(event.globalPosition().y())
            previous_y = self._last_mouse_y
            self._last_mouse_y = global_y
            self._check_slot_switch(global_y, moving_down=previous_y is not None and global_y > previous_y)
        super().mouseMoveEvent(event)

    def _check_slot_switch(self, global_y: int, moving_down: bool = False) -> None:
        for card in MemoIndexCard._all_cards:
            if card is self or not card.isVisible() or card._base_y is None:
                continue
            slot_top = card._base_y + self.SLOT_SWITCH_DEADZONE
            slot_bot = card._base_y + self.COMPACT_H - self.SLOT_SWITCH_DEADZONE
            if slot_top <= global_y <= slot_bot:
                if self._switch_target is not card:
                    self._switch_target = card
                    if moving_down:
                        self._switch_timer.stop()
                        self._execute_switch()
                    else:
                        self._switch_timer.start()
                return
        if self._switch_target is not None:
            self._switch_target = None
            self._switch_timer.stop()

    def _execute_switch(self) -> None:
        target = self._switch_target
        self._switch_target = None
        if target is not None and target.isVisible() and not target._expanded:
            target._do_expand()
            target.raise_()

    def leaveEvent(self, event) -> None:
        self._switch_timer.stop()
        self._switch_target = None
        self._last_mouse_y = None
        if not self._expanded:
            QTimer.singleShot(120, self._collapse_if_idle)
        super().leaveEvent(event)

    def _set_hover_controls_visible(self, visible: bool) -> None:
        if not getattr(self, "_expanded", False):
            visible = False
        for widget in (getattr(self, "_icon_pick_btn", None), getattr(self, "_color", None), getattr(self, "_always_on_top_chk", None)):
            if widget is not None:
                widget.setVisible(visible)

    def _collapse_if_idle(self) -> None:
        if self._expanded and not self._is_editing_active() and not self._cursor_in_hover_regions():
            self._do_collapse()

    def _is_editing_active(self) -> bool:
        focused = QApplication.focusWidget()
        while focused is not None:
            if focused is self:
                return True
            focused = focused.parentWidget()
        return False

    def _cursor_in_hover_regions(self) -> bool:
        if self._is_editing_active():
            return True
        if self.underMouse():
            return True
        pos = QCursor.pos()
        local_pos = self.mapFromGlobal(pos)
        if self.rect().adjusted(-8, -8, 8, 8).contains(local_pos):
            return True
        widget = QApplication.widgetAt(pos)
        while widget is not None:
            if widget is self:
                return True
            widget = widget.parentWidget()
        if self.frameGeometry().adjusted(-8, -8, 8, 8).contains(pos):
            return True
        return any(region.adjusted(-8, -8, 8, 8).contains(pos) for region in self._hover_regions)

    def _cursor_in_expanded_region(self) -> bool:
        if not self._expanded:
            return False
        pos = QCursor.pos()
        widget = QApplication.widgetAt(pos)
        while widget is not None:
            if widget is self:
                return True
            widget = widget.parentWidget()
        return self.frameGeometry().adjusted(-4, -4, 4, 4).contains(pos)

    def _card_at_cursor_slot(self, pos: QPoint) -> "MemoIndexCard | None":
        for card in MemoIndexCard._all_cards:
            if not card.isVisible() or card._base_x is None or card._base_y is None:
                continue
            slot = QRect(card._base_x, card._base_y, self.COMPACT_W, self.COMPACT_H)
            if slot.adjusted(0, self.SLOT_SWITCH_DEADZONE, 0, -self.SLOT_SWITCH_DEADZONE).contains(pos):
                return card
        return None

    def _watch_hover_state(self) -> None:
        if not self._expanded:
            self._hover_watch_timer.stop()
            return
        if self._is_editing_active():
            self._set_hover_controls_visible(self._cursor_in_expanded_region())
            return
        pos = QCursor.pos()
        slot_card = self._card_at_cursor_slot(pos)
        if slot_card is not None:
            if slot_card is not self:
                slot_card._do_expand()
                slot_card.raise_()
            return
        if self._cursor_in_hover_regions():
            self._set_hover_controls_visible(self._cursor_in_expanded_region())
            global_y = pos.y()
            previous_y = self._last_mouse_y
            self._last_mouse_y = global_y
            self._check_slot_switch(global_y, moving_down=previous_y is not None and global_y > previous_y)
            return
        self._do_collapse()

    def _do_expand(self) -> None:
        prev = MemoIndexCard._currently_expanded
        if prev is not None and prev is not self and prev._expanded:
            prev._do_collapse()
        MemoIndexCard._currently_expanded = self

        self._expanded = True
        self._last_mouse_y = QCursor.pos().y()

        w = self.EXPANDED_W
        h = self._compute_expanded_h()
        side = self._side()

        base_x = self._base_x if self._base_x is not None else self.x()
        base_y = self._base_y if self._base_y is not None else self.y()

        # Expanded card appears in the adjacent inner column, leaving the
        # compact slot visually empty so other index cards are not obscured.
        if side == "right":
            new_x = base_x - w        # expanded right edge = compact left edge
        else:
            new_x = base_x + self.COMPACT_W  # expanded left edge = compact right edge

        new_y = base_y

        ref_point = QPoint(base_x + self.COMPACT_W // 2, base_y + self.COMPACT_H // 2)
        screen = QApplication.screenAt(ref_point) or QApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            if new_y + h > area.bottom():
                new_y = max(area.top(), area.bottom() - h)

        compact_rect = QRect(base_x, base_y, self.COMPACT_W, self.COMPACT_H)
        end_rect = QRect(new_x, new_y, w, h)
        self._hover_regions = [compact_rect, end_rect]

        self._anim_cb = None
        self._anim.stop()
        self.setMinimumSize(0, 0)
        self.setMaximumSize(16777215, 16777215)
        # Switch directly to the final geometry while painting is paused.
        self.setUpdatesEnabled(False)
        self.setGeometry(end_rect)
        self.setFixedSize(w, h)
        self._compact_face.hide()
        self._expanded_face.show()
        self._set_hover_controls_visible(self._cursor_in_expanded_region())
        # Re-lock after face switch — overrides any layout-triggered resize
        self.setGeometry(end_rect)
        self.setUpdatesEnabled(True)
        self.update()
        self.raise_()
        MemoIndexCard._ensure_hover_manager()

    def _do_collapse(self) -> None:
        self._hover_watch_timer.stop()
        self._switch_timer.stop()
        self._switch_target = None
        self._last_mouse_y = None
        self._expanded = False
        geo = self.geometry()
        side = self._side()
        base_y = self._base_y if self._base_y is not None else geo.top()
        base_x = self._base_x if self._base_x is not None else (
            geo.right() - self.COMPACT_W + 1 if side == "right" else geo.left()
        )

        def _on_done() -> None:
            self._set_hover_controls_visible(False)
            self._expanded_face.hide()
            self._compact_face.show()
            self.setFixedSize(self.COMPACT_W, self.COMPACT_H)
            self.move(base_x, base_y)
            self._hover_regions = [QRect(base_x, base_y, self.COMPACT_W, self.COMPACT_H)]
            if MemoIndexCard._currently_expanded is self:
                MemoIndexCard._currently_expanded = None

        self._anim.stop()
        _on_done()

    def _on_anim_done(self) -> None:
        if self._anim_cb is not None:
            cb = self._anim_cb
            self._anim_cb = None
            cb()

    # ── 저장/닫기 ──────────────────────────────────────────────────

    def schedule_save(self, *_args) -> None:
        self.save_timer.start(400)

    def persist(self) -> None:
        self.memo["content"] = self._text.toPlainText()
        self.memo["background"] = self._color.currentText()
        self.memo["always_on_top"] = self._always_on_top_chk.isChecked()
        self.memo["sticker_open"] = self.isVisible()
        self.memo["x"] = self.x()
        self.memo["y"] = self.y()
        self.memo["updated_at"] = now_iso()
        if self.main is not None:
            config.save_template(self.main.template_index, self.main.data)
        if self.on_saved:
            self.on_saved()

    def accept(self) -> None:
        self.memo["sticker_open"] = False
        self.close()

    def closeEvent(self, event) -> None:
        try:
            MemoIndexCard._all_cards.remove(self)
        except ValueError:
            pass
        if MemoIndexCard._currently_expanded is self:
            MemoIndexCard._currently_expanded = None
        if hasattr(self, "_hover_watch_timer"):
            self._hover_watch_timer.stop()
        if hasattr(self, "_switch_timer"):
            self._switch_timer.stop()
        MemoIndexCard._stop_hover_manager_if_unused()
        if hasattr(self, "save_timer") and self.save_timer.isActive():
            self.save_timer.stop()
            self.persist()
        else:
            self.persist()
        super().closeEvent(event)

    # isVisible / raise_ / activateWindow 은 QWidget 에 이미 존재


class MemoDialog(QDialog):
    def __init__(self, memo: dict | None = None) -> None:
        super().__init__()
        self.setWindowTitle("메모")
        apply_modern_dialog_style(self)
        self.memo = memo or {}
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._memo_option_rows: list[QWidget] = []
        self.title = QLineEdit(self.memo.get("title", ""))
        self.content = QTextEdit()
        self.content.setPlainText(self.memo.get("content", ""))
        self.pinned = QCheckBox("즐겨찾기")
        self.pinned.setToolTip("체크하면 메모 탭 목록에서 이 메모가 먼저 표시되고 별표가 표시됩니다.")
        self.pinned.setChecked(bool(self.memo.get("favorite", self.memo.get("pinned"))))
        self.always_on_top = QCheckBox("스티커 항상 위")
        self.always_on_top.setChecked(bool(self.memo.get("always_on_top", True)))
        self.open_as_sticker = QCheckBox("스티커로 띄우기")
        self.open_as_sticker.setChecked(False)
        self.background = QComboBox()
        self.background.addItems(list(MEMO_COLORS))
        _is_new = not self.memo.get("id")
        _bg_default = self.memo.get("background") or (random.choice(MEMO_COLOR_LIST) if _is_new else "노랑")
        self.background.setCurrentText(_bg_default if _bg_default in MEMO_COLORS else "노랑")
        form.addRow("제목", self.title)
        form.addRow("내용", self.content)
        form.addRow("배경색", self.background)
        form.addRow(self.open_as_sticker)
        form.addRow(self.pinned)
        form.addRow(self.always_on_top)
        for option in (self.pinned, self.always_on_top):
            label = form.labelForField(option)
            if label is not None:
                label.hide()
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("확인")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def value(self) -> dict:
        data = dict(self.memo)
        if not data.get("id"):
            data["id"] = new_id("mm")
            data["created_at"] = now_iso()
            data["sort_order"] = 0
            data["usage_count"] = 0
        data.update(
            {
                "title": self.title.text().strip(),
                "content": self.content.toPlainText(),
                "favorite": self.pinned.isChecked(),
                "pinned": self.pinned.isChecked(),
                "always_on_top": self.always_on_top.isChecked(),
                "background": self.background.currentText(),
                "_open_sticker_after_save": self.open_as_sticker.isChecked(),
                "updated_at": now_iso(),
            }
        )
        return data


class ScheduleDialog(QDialog):
    def __init__(self, schedule: dict | None = None) -> None:
        super().__init__()
        self.setWindowTitle("일정")
        apply_modern_dialog_style(self)
        self.schedule = schedule or {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(12)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.title = QLineEdit(self.schedule.get("title", ""))
        self.priority = QComboBox()
        self.priority.addItems(["상", "중", "하"])
        self.priority.setCurrentText(self.schedule.get("priority", "하") if self.schedule.get("priority", "하") in {"상", "중", "하"} else "하")
        fit_combo_to_contents(self.priority, 88)
        current = QDateTime.fromString(self.schedule.get("datetime", ""), Qt.DateFormat.ISODate)
        if not current.isValid():
            current = QDateTime.currentDateTime()
        self.date = QDateEdit()
        self.date.setCalendarPopup(True)
        self.date.setDate(current.date())
        self.date.setMinimumWidth(150)
        self.date.dateChanged.connect(lambda _date: self.update_notify_label())
        calendar = self.date.calendarWidget()
        today_format = QTextCharFormat()
        today_format.setBackground(QColor("#FFF3B0"))
        today_format.setForeground(QColor("#111827"))
        today_format.setFontWeight(700)
        calendar.setDateTextFormat(QDateTime.currentDateTime().date(), today_format)
        self.selected_time = current.time()
        self.time_label = QLabel()
        self.time_label.setObjectName("cardTitle")
        self.time_label.setMinimumWidth(52)
        self.update_time_label()
        datetime_row = QHBoxLayout()
        datetime_row.setContentsMargins(0, 0, 0, 0)
        datetime_row.setSpacing(6)
        datetime_row.addWidget(self.date)
        datetime_row.addWidget(self.time_label)
        datetime_row.addStretch(1)
        datetime_widget = QWidget()
        datetime_widget.setLayout(datetime_row)
        quick_time_row = QHBoxLayout()
        quick_time_row.setContentsMargins(0, 0, 0, 0)
        quick_time_row.setSpacing(4)
        for hour in range(9, 19):
            btn = QPushButton(str(hour))
            btn.setFixedSize(42, 28)
            btn.setStyleSheet(_TIME_BTN_STYLE)
            btn.clicked.connect(lambda checked=False, value=hour: self.set_time_hour(value))
            quick_time_row.addWidget(btn)
        quick_time_row.addStretch(1)
        time_adjust_row = QHBoxLayout()
        time_adjust_row.setContentsMargins(0, 0, 0, 0)
        time_adjust_row.setSpacing(4)
        for label, minutes in [("-10m", -10), ("+10m", 10), ("-30m", -30), ("+30m", 30)]:
            btn = QPushButton(label)
            btn.setFixedHeight(28)
            btn.setStyleSheet(_TIME_BTN_STYLE)
            btn.clicked.connect(lambda checked=False, value=minutes: self.adjust_time(value))
            time_adjust_row.addWidget(btn)
        time_adjust_row.addStretch(1)
        quick_time_widget = QWidget()
        quick_time_layout = QVBoxLayout(quick_time_widget)
        quick_time_layout.setContentsMargins(0, 0, 0, 0)
        quick_time_layout.setSpacing(4)
        quick_time_layout.addLayout(quick_time_row)
        quick_time_layout.addLayout(time_adjust_row)
        self.repeat = QComboBox()
        self.repeat.addItems(["없음", "매일", "매주", "매월"])
        self.repeat.setMinimumWidth(110)
        self.repeat.view().setMinimumWidth(110)
        repeat_map = {"none": "없음", "daily": "매일", "weekly": "매주", "monthly": "매월"}
        self.repeat.setCurrentIndex(max(self.repeat.findText(repeat_map.get(self.schedule.get("repeat", "none"), "없음")), 0))
        self.notify = QSpinBox()
        self.notify.setRange(0, 10080)
        self.notify.setValue(int(self.schedule.get("notify_before_minutes", 30)))
        self.notify.valueChanged.connect(lambda _value: self.update_notify_label())
        self.notify.setVisible(False)
        self.notify_at_label = QLabel()
        self.notify_at_label.setObjectName("cardTitle")
        self.notify_at_label.setMinimumWidth(142)
        notify_row = QHBoxLayout()
        notify_row.setContentsMargins(0, 0, 0, 0)
        notify_row.setSpacing(6)
        notify_row.addWidget(self.notify_at_label)
        for label, minutes in [("정각", 0), ("5분 전", 5), ("10분 전", 10), ("30분 전", 30), ("1시간 전", 60)]:
            btn = QPushButton(label)
            btn.setFixedHeight(28)
            btn.setStyleSheet(_TIME_BTN_STYLE)
            btn.clicked.connect(lambda checked=False, value=minutes: self.notify.setValue(value))
            notify_row.addWidget(btn)
        prev_9 = QPushButton("전일 9시")
        prev_9.setFixedHeight(28)
        prev_9.setStyleSheet(_TIME_BTN_STYLE)
        prev_18 = QPushButton("전일 6시")
        prev_18.setFixedHeight(28)
        prev_18.setStyleSheet(_TIME_BTN_STYLE)
        prev_9.clicked.connect(lambda: self.set_previous_day_notify(9))
        prev_18.clicked.connect(lambda: self.set_previous_day_notify(18))
        notify_row.addWidget(prev_9)
        notify_row.addWidget(prev_18)
        notify_widget = QWidget()
        notify_widget.setLayout(notify_row)
        self.update_notify_label()
        self.memo = QTextEdit()
        self.memo.setPlainText(self.schedule.get("memo", ""))
        form.addRow("제목", self.title)
        form.addRow("중요도", self.priority)
        form.addRow("일시", datetime_widget)
        form.addRow("시간 선택", quick_time_widget)
        form.addRow("반복", self.repeat)
        form.addRow("알림", notify_widget)
        form.addRow("메모", self.memo)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("확인")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_datetime(self) -> datetime:
        return datetime.combine(self.date.date().toPyDate(), self.selected_time.toPyTime())

    def notify_datetime(self) -> datetime:
        return self.selected_datetime() - timedelta(minutes=self.notify.value())

    def update_notify_label(self) -> None:
        if not hasattr(self, "notify_at_label"):
            return
        self.notify_at_label.setText(self.notify_datetime().strftime("%Y-%m-%d %H:%M"))

    def set_time_hour(self, hour: int) -> None:
        self.selected_time = QTime(hour, 0)
        self.update_time_label()
        self.update_notify_label()

    def adjust_time(self, minutes: int) -> None:
        self.selected_time = self.selected_time.addSecs(minutes * 60)
        self.update_time_label()
        self.update_notify_label()

    def update_time_label(self) -> None:
        hour = self.selected_time.hour()
        minute = self.selected_time.minute()
        self.time_label.setText(f"{hour}:{minute:02d}")

    def set_previous_day_notify(self, hour: int) -> None:
        target = self.selected_datetime()
        notify_at = datetime.combine(target.date() - timedelta(days=1), dt_time(hour, 0))
        self.notify.setValue(max(0, int((target - notify_at).total_seconds() // 60)))
        self.update_notify_label()

    def value(self) -> dict:
        data = dict(self.schedule)
        if not data.get("id"):
            data["id"] = new_id("sc")
            data["created_at"] = now_iso()
            data["sort_order"] = 0
            data["usage_count"] = 0
        date_time = QDateTime(self.date.date(), self.selected_time)
        data.update(
            {
                "title": self.title.text().strip(),
                "priority": self.priority.currentText() or "하",
                "datetime": date_time.toString(Qt.DateFormat.ISODate),
                "repeat": {"없음": "none", "매일": "daily", "매주": "weekly", "매월": "monthly"}.get(self.repeat.currentText(), "none"),
                "notify_before_minutes": self.notify.value(),
                "memo": self.memo.toPlainText(),
            }
        )
        return data


class MemoListTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        self.sticky_windows: dict[str, StickyMemoDialog | MemoIndexCard] = {}
        self._recently_closed_sticker_keys: list[str] = []
        self.group_id = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText("검색...")
        self.search.setFixedWidth(140)
        self.search.setFixedHeight(26)
        self.search.setStyleSheet("QLineEdit { padding: 1px 6px; font-size: 9pt; }")
        self.search.textChanged.connect(self.refresh)
        self.sort_controls = SortControls(self.refresh)
        corner = QWidget()
        corner_layout = QHBoxLayout(corner)
        corner_layout.setContentsMargins(0, 0, 4, 0)
        corner_layout.setSpacing(4)
        corner_layout.addWidget(self.search)
        corner_layout.addWidget(self.sort_controls)
        self.tabs = QTabWidget()
        self.tabs.setCornerWidget(corner, Qt.Corner.TopRightCorner)
        add_btn = QPushButton("+ 메모")
        add_btn.clicked.connect(lambda: self.edit_memo())
        group_btn = QPushButton("+ 그룹 생성")
        group_btn.clicked.connect(self.create_group_clicked)
        expand_btn = QPushButton("모두 펼치기")
        expand_btn.clicked.connect(self.expand_all_stickers)
        collapse_btn = QPushButton("모두 접기")
        collapse_btn.clicked.connect(self.collapse_all_stickers)
        arrange_btn = QPushButton("정렬")
        arrange_btn.clicked.connect(self.arrange_compact_stickers)
        self.expand_btn = expand_btn
        self.collapse_btn = collapse_btn
        self.arrange_btn = arrange_btn
        sticker_toggle_btn = QPushButton("★ 열기/닫기")
        sticker_toggle_btn.clicked.connect(self.toggle_pinned_stickers)
        close_all_btn = QPushButton("열기/닫기")
        close_all_btn.clicked.connect(self.toggle_recent_stickers)
        for button in (expand_btn, collapse_btn, arrange_btn, sticker_toggle_btn, close_all_btn, group_btn, add_btn):
            button.setFixedHeight(30)
            button.setStyleSheet(MEMO_BOTTOM_ACTION_STYLE)
        self.grid = GridPanel(columns=2)
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)
        # 탭(메뉴 줄) 아래에 그룹 경로(브레드크럼) 표시
        self.breadcrumb = make_breadcrumb_label(self.enter_group)
        page_layout.addWidget(self.breadcrumb)
        page_layout.addWidget(self.grid, 1)
        page_layout.addLayout(bottom_action_bar(expand_btn, collapse_btn, arrange_btn, sticker_toggle_btn, close_all_btn, group_btn, add_btn))
        self.tabs.addTab(page, "메모")
        layout.addWidget(self.tabs, 1)
        self._sync_index_action_buttons()

    def _ordered_memos(self, source_items: list[dict] | None = None) -> list[dict]:
        items = source_items if source_items is not None else self.main.data.get("memos", [])
        memos = self.sort_controls.sort_items(items, lambda item: item.get("title") or item.get("content", ""))
        if not self.sort_controls.is_manual():
            memos = sorted(memos, key=lambda item: not self.is_favorite_memo(item))
        return memos

    def _sync_index_action_buttons(self) -> None:
        is_index = self._display_mode() == "index"
        for button in (getattr(self, "expand_btn", None), getattr(self, "collapse_btn", None), getattr(self, "arrange_btn", None)):
            if button is not None:
                button.setEnabled(not is_index)
                button.setFixedHeight(BOTTOM_ACTION_HEIGHT)
                button.setStyleSheet(MEMO_BOTTOM_ACTION_STYLE)

    def refresh(self) -> None:
        cards = []
        q = self.search.text().strip().lower()
        searching = bool(q)
        data = self.main.data
        self.group_id = valid_group_id(data, GROUP_SCOPE_MEMO, self.group_id)
        source_items = data.get("memos", [])
        memos = self._ordered_memos(source_items)
        self._sync_index_action_buttons()
        offset = 0
        meta: list[tuple[str, object]] = []
        if not searching:
            if self.group_id:
                current = group_by_id(data, self.group_id)
                cards.append(make_back_card(self.go_back_group, 96))
                meta.append(("target", str(current.get("parent_id") or "") if current else ""))
            for group in groups_in(data, GROUP_SCOPE_MEMO, self.group_id):
                cards.append(self._make_memo_group_card(group))
                meta.append(("target", group_id(group)))
            offset = len(cards)
        visible_memos = []
        for memo in memos:
            if q and q not in (memo.get("title", "") + " " + memo.get("content", "")).lower():
                continue
            if not searching and item_group_id(memo) != self.group_id:
                continue
            card = make_card(
                memo.get("title", "(제목 없음)"),
                memo_card_preview(memo.get("content", ""), 160, max_lines=3),
                card_height=96,
                subtitle_max_lines=3,
                dense=True,
                v_center=True,
            )
            self.add_memo_actions(card, memo)
            visible_memos.append(memo)
            cards.append(card)
            meta.append(("item", memo))
        callback = (lambda old, new, off=offset: self.reorder_items(source_items, visible_memos, old - off, new - off)) if self.sort_controls.is_manual() else None
        drop_handler = self._make_drop_handler(meta) if not searching else None
        self.grid.add_cards(cards, on_reorder=callback, on_drop=drop_handler)
        self.refresh_breadcrumb()
        if self._display_mode() == "index":
            self._arrange_index_cards()

    # --- 그룹(폴더) -----------------------------------------------------

    def _make_drop_handler(self, meta: list[tuple[str, object]]):
        """메모 카드를 그룹/뒤로가기 카드 위에 드롭하면 해당 그룹으로 이동."""

        def handle(old_index: int, new_index: int) -> bool:
            if not (0 <= old_index < len(meta) and 0 <= new_index < len(meta)):
                return False
            src_kind, src_value = meta[old_index]
            dst_kind, dst_value = meta[new_index]
            if src_kind != "item" or dst_kind != "target":
                return False
            src_value["group_id"] = dst_value
            self.main.save_data()
            return True

        return handle

    def refresh_breadcrumb(self) -> None:
        update_breadcrumb_label(self.breadcrumb, self.main.data, self.group_id)

    def enter_group(self, gid: str) -> None:
        self.group_id = gid
        self.refresh()

    def go_back_group(self) -> None:
        current = group_by_id(self.main.data, self.group_id)
        self.enter_group(str(current.get("parent_id") or "") if current else "")

    def create_group_clicked(self) -> None:
        dialog = GroupDialog()
        while dialog.exec() == dialog.DialogCode.Accepted:
            value = dialog.value()
            if not value.get("name"):
                show_modern_warning(dialog, "입력 확인", "그룹명을 입력해주세요.")
                continue
            create_group(self.main.data, GROUP_SCOPE_MEMO, self.group_id, value["name"], value["icon"])
            self.main.save_data()
            return

    def edit_group(self, group: dict) -> None:
        dialog = GroupDialog(group)
        while dialog.exec() == dialog.DialogCode.Accepted:
            value = dialog.value()
            if not value.get("name"):
                show_modern_warning(dialog, "입력 확인", "그룹명을 입력해주세요.")
                continue
            group["name"] = value["name"]
            group["icon"] = value["icon"]
            self.main.save_data()
            return

    def delete_group_clicked(self, group: dict) -> None:
        if not confirm_delete(self, "선택한 그룹을 삭제할까요?\n그룹 안의 메모와 하위 그룹은 상위 경로로 이동합니다."):
            return
        delete_group(self.main.data, group, [self.main.data.get("memos", [])])
        self.main.save_data()

    def toggle_group_favorite_clicked(self, group: dict, card: QWidget, button) -> None:
        toggle_group_favorite(group, card, button)
        QTimer.singleShot(0, self.main.save_data)

    def move_memo_to_group(self, memo: dict) -> None:
        show_move_to_group_menu(self, self.main.data, GROUP_SCOPE_MEMO, memo, self.main.save_data)

    def _make_memo_group_card(self, group: dict) -> QWidget:
        subtitle = count_group_contents(
            self.main.data, GROUP_SCOPE_MEMO, group_id(group), self.main.data.get("memos", [])
        )
        return make_group_card(
            group,
            subtitle,
            on_open=lambda g=group: self.enter_group(group_id(g)),
            on_favorite=self.toggle_group_favorite_clicked,
            on_edit=self.edit_group,
            on_delete=self.delete_group_clicked,
            card_height=96,
        )

    def is_favorite_memo(self, memo: dict) -> bool:
        return bool(memo.get("favorite", memo.get("pinned")))

    def style_memo_favorite_button(self, button, memo: dict) -> None:
        color = "#F5B301" if self.is_favorite_memo(memo) else "#A3A8B3"
        button.setText("★")
        button.setStyleSheet(
            f'QToolButton#iconButton {{ color: {color}; font-family: "Segoe UI Symbol", "Malgun Gothic"; font-size: 13pt; font-weight: 900; padding: 0 0 2px 0; '
            f"min-width: 24px; max-width: 24px; min-height: 24px; max-height: 24px; }}"
            f"QToolButton#iconButton:hover {{ color: {color}; background: transparent; }}"
        )

    def add_memo_actions(self, card: QWidget, memo: dict) -> None:
        add_card_status_label(card)
        if self.is_favorite_memo(memo):
            add_favorite_badge_to_card(card)
        action_page = QWidget()
        action_page.setObjectName("cardActionBar")
        row = QHBoxLayout(action_page)
        row.setContentsMargins(CARD_ACTION_ROW_MARGIN_X, CARD_ACTION_ROW_MARGIN_Y, CARD_ACTION_ROW_MARGIN_X, CARD_ACTION_ROW_MARGIN_Y)
        row.setSpacing(CARD_ACTION_ROW_SPACING)
        row.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        _sz = QSize(CARD_ACTION_ICON_SIZE, CARD_ACTION_ICON_SIZE)
        pin = make_icon_button("pin", "즐겨찾기", lambda checked=False, value=memo, c=card: self.toggle_pin(value, c, pin), size=_sz)
        self.style_memo_favorite_button(pin, memo)
        row.addWidget(pin)
        row.addWidget(make_icon_button("sticker", "스티커", lambda checked=False, value=memo: self.show_sticker(value), size=_sz))
        row.addWidget(make_icon_button("📂", "그룹으로 이동", lambda checked=False, value=memo: self.move_memo_to_group(value), size=_sz))
        row.addWidget(make_icon_button("edit", "수정", lambda checked=False, value=memo: self.edit_memo(value), size=_sz))
        row.addWidget(make_icon_button("delete", "삭제", lambda checked=False, value=memo: self.delete_memo(value), True, size=_sz))
        set_card_action_widget(card, action_page)

    def toggle_pin(self, memo: dict, card: QWidget | None = None, button: QWidget | None = None) -> None:
        memo["favorite"] = not self.is_favorite_memo(memo)
        memo["pinned"] = bool(memo["favorite"])
        if button is not None:
            self.style_memo_favorite_button(button, memo)
        if card is not None:
            if self.is_favorite_memo(memo):
                add_favorite_badge_to_card(card)
            else:
                remove_favorite_badge_from_card(card)
            show_card_status(card, "즐겨찾기 등록!" if self.is_favorite_memo(memo) else "즐겨찾기 해제!")
        self.main.save_data()

    def reorder_items(self, source: list[dict], visible: list[dict], old: int, new: int) -> None:
        apply_manual_reorder(source, visible, old, new)
        self.main.save_data()
        if self._display_mode() == "index":
            self._arrange_index_cards()

    def memo_key(self, memo: dict) -> str:
        return str(memo.get("id") or id(memo))

    def memo_by_key(self, memo_key: str) -> dict | None:
        for memo in self.main.data.get("memos", []):
            if self.memo_key(memo) == memo_key:
                return memo
        return None

    def _display_mode(self) -> str:
        return str(getattr(self.main, "settings", {}).get("sticky_memo_display_mode", "floating") or "floating")

    def show_sticker(self, memo: dict, track_usage: bool = True, raise_window: bool = True, toggle_existing: bool = True) -> None:
        if self._display_mode() == "index":
            self._show_index_card(memo, track_usage=track_usage, raise_window=raise_window, toggle_existing=toggle_existing)
            return
        key = self.memo_key(memo)
        dialog = self.sticky_windows.get(key)
        if dialog is not None and dialog.isVisible():
            if toggle_existing:
                dialog.accept()
                return
            if raise_window:
                dialog.raise_()
                dialog.activateWindow()
            return
        if track_usage:
            bump_usage(memo)
            self.main.save_usage_data()
        dialog = StickyMemoDialog(memo, self.main, self.refresh)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.destroyed.connect(lambda _obj=None, memo_key=key: self.forget_sticker(memo_key))
        self.sticky_windows[key] = dialog
        dialog.show()
        if raise_window:
            dialog.raise_()

    def _show_index_card(self, memo: dict, track_usage: bool = True, raise_window: bool = True, toggle_existing: bool = True) -> None:
        key = self.memo_key(memo)
        card = self.sticky_windows.get(key)
        if card is not None and card.isVisible():
            if toggle_existing:
                card.accept()
                return
            if raise_window:
                card.raise_()
            return
        if track_usage:
            bump_usage(memo)
            self.main.save_usage_data()
        card = MemoIndexCard(memo, self.main, self.refresh)
        card.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        card.destroyed.connect(lambda _obj=None, memo_key=key: self.forget_sticker(memo_key))
        self.sticky_windows[key] = card
        # 초기 배치: 지정 모니터 지정 면의 Y 슬롯에 놓기
        settings = getattr(self.main, "settings", {})
        screens = QApplication.screens()
        mon = max(0, min(len(screens) - 1, int(settings.get("sticky_memo_arrange_monitor", 1) or 1) - 1))
        screen = screens[mon] if screens else QApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            side = str(settings.get("sticky_memo_index_side", "right") or "right")
            start_pct = int(settings.get("sticky_memo_index_start_y", 0) or 0)
            start_y = area.top() + int(area.height() * start_pct / 100)
            open_cards = [d for k2, d in self.sticky_windows.items() if d is not card and isinstance(d, MemoIndexCard) and d.isVisible()]
            slot_y = start_y + len(open_cards) * (MemoIndexCard.COMPACT_H + MemoIndexCard.COMPACT_GAP)
            card_x = area.right() - MemoIndexCard.COMPACT_W if side == "right" else area.left()
            card.set_position(card_x, slot_y)
        card.show()
        if raise_window:
            card.raise_()
        self._arrange_index_cards()

    def forget_sticker(self, memo_key: str) -> None:
        self.sticky_windows.pop(memo_key, None)

    def visible_stickers(self) -> list:
        return [dialog for dialog in self.sticky_windows.values() if dialog.isVisible()]

    def expand_all_stickers(self) -> None:
        for dialog in self.visible_stickers():
            if isinstance(dialog, StickyMemoDialog) and dialog.compact:
                dialog.compact = False
                dialog.apply_compact_state(save=False)
                dialog.raise_()
                dialog.persist()

    def collapse_all_stickers(self) -> None:
        for dialog in self.visible_stickers():
            if isinstance(dialog, StickyMemoDialog) and not dialog.compact:
                dialog.compact = True
                dialog.apply_compact_state(save=False)
                dialog.persist()

    def toggle_recent_stickers(self) -> None:
        visible = self.visible_stickers()
        if visible:
            self._recently_closed_sticker_keys = [
                key for key, dialog in self.sticky_windows.items()
                if dialog in visible and dialog.isVisible()
            ]
            for dialog in visible:
                dialog.accept()
            return
        if not self._recently_closed_sticker_keys:
            return
        keys = list(self._recently_closed_sticker_keys)
        self._recently_closed_sticker_keys = []
        for memo_key in keys:
            memo = self.memo_by_key(memo_key)
            if memo is not None:
                self.show_sticker(memo, track_usage=False, raise_window=False, toggle_existing=False)

    def close_all_stickers(self) -> None:
        self._recently_closed_sticker_keys = []
        for dialog in self.visible_stickers():
            dialog.accept()

    def reopen_stickers_for_mode(self) -> None:
        visible_keys = [
            key for key, dialog in list(self.sticky_windows.items())
            if dialog.isVisible()
        ]
        if not visible_keys:
            return
        for dialog in list(self.sticky_windows.values()):
            if dialog.isVisible():
                dialog.accept()
        QApplication.processEvents()
        for key in visible_keys:
            memo = self.memo_by_key(key)
            if memo is not None:
                self.show_sticker(memo, track_usage=False, raise_window=False, toggle_existing=False)

    def toggle_pinned_stickers(self) -> None:
        memos = self.main.data.get("memos", [])
        pinned = [memo for memo in memos if self.is_favorite_memo(memo)]
        if not pinned:
            return
        open_keys = {key for key, dlg in self.sticky_windows.items() if dlg.isVisible()}
        any_open = any(self.memo_key(m) in open_keys for m in pinned)
        if any_open:
            for memo in pinned:
                key = self.memo_key(memo)
                dialog = self.sticky_windows.get(key)
                if dialog is not None and dialog.isVisible():
                    dialog.accept()
        else:
            for memo in pinned:
                self.show_sticker(memo, track_usage=False, raise_window=False, toggle_existing=False)

    def arrange_compact_stickers(self) -> None:
        if self._display_mode() == "index":
            self._arrange_index_cards()
            return
        stickers = [d for d in self.visible_stickers() if isinstance(d, StickyMemoDialog)]
        if not stickers:
            return
        settings = getattr(self.main, "settings", {})
        screens = QApplication.screens()
        monitor_index = int(settings.get("sticky_memo_arrange_monitor", 1) or 1)
        screen = screens[max(0, min(len(screens) - 1, monitor_index - 1))] if screens else None
        screen = screen or QApplication.screenAt(stickers[0].pos()) or QApplication.primaryScreen()
        if not screen:
            return
        area = screen.availableGeometry()
        margin = 18
        gap = 0
        corner = str(settings.get("sticky_memo_arrange_corner", "top_right") or "top_right")
        top_anchor = corner in {"top_right", "top_left"}
        right_anchor = corner in {"top_right", "bottom_right"}
        y = area.top() + margin if top_anchor else area.bottom() - margin + 1
        for dialog in stickers:
            x = area.right() - dialog.width() - margin + 1 if right_anchor else area.left() + margin
            if top_anchor:
                if y + dialog.height() > area.bottom() - margin + 1:
                    y = area.top() + margin
                place_y = y
            else:
                if y - dialog.height() < area.top() + margin:
                    y = area.bottom() - margin + 1
                place_y = y - dialog.height()
            dialog.move(x, place_y)
            y = dialog.geometry().bottom() + 1 + gap if top_anchor else dialog.geometry().top() - gap
            dialog.raise_()
            dialog.persist()

    def _arrange_index_cards(self) -> None:
        cards = [d for d in self.visible_stickers() if isinstance(d, MemoIndexCard)]
        if not cards:
            return
        order = {self.memo_key(memo): idx for idx, memo in enumerate(self._ordered_memos())}
        cards.sort(key=lambda card: order.get(self.memo_key(card.memo), len(order)))
        settings = getattr(self.main, "settings", {})
        screens = QApplication.screens()
        mon = max(0, min(len(screens) - 1, int(settings.get("sticky_memo_arrange_monitor", 1) or 1) - 1))
        screen = screens[mon] if screens else None
        screen = screen or QApplication.screenAt(cards[0].pos()) or QApplication.primaryScreen()
        if not screen:
            return
        area = screen.availableGeometry()
        side = str(settings.get("sticky_memo_index_side", "right") or "right")
        start_pct = int(settings.get("sticky_memo_index_start_y", 0) or 0)
        start_y = area.top() + int(area.height() * start_pct / 100)
        card_x = area.right() - MemoIndexCard.COMPACT_W if side == "right" else area.left()
        y = start_y
        for card in cards:
            if hasattr(card, "reset_compact_geometry"):
                card.reset_compact_geometry()
            card.set_position(card_x, y)
            y += MemoIndexCard.COMPACT_H + MemoIndexCard.COMPACT_GAP
            card.raise_()
        if self.main is not None:
            config.save_template(self.main.template_index, self.main.data)

    def _sync_open_sticker(self, memo: dict) -> None:
        dialog = self.sticky_windows.get(self.memo_key(memo))
        if dialog is not None and dialog.isVisible() and hasattr(dialog, "reload_from_memo"):
            dialog.reload_from_memo()

    def edit_memo(self, memo: dict | None = None) -> None:
        dialog = MemoDialog(memo)
        while dialog.exec() == dialog.DialogCode.Accepted:
            value = dialog.value()
            if not value.get("title"):
                show_modern_warning(dialog, "입력 확인", "이름을 지정해주세요.")
                continue
            open_sticker = bool(value.pop("_open_sticker_after_save", False))
            items = self.main.data.setdefault("memos", [])
            if memo in items:
                memo.clear()
                memo.update(value)
                saved_memo = memo
            else:
                value["sort_order"] = len(items)
                # 새 메모는 현재 열려 있는 그룹(폴더)에 등록한다.
                value.setdefault("group_id", self.group_id)
                items.append(value)
                saved_memo = value
            self.main.save_data()
            self._sync_open_sticker(saved_memo)
            self.refresh()
            if open_sticker:
                self.show_sticker(saved_memo, track_usage=False, raise_window=True, toggle_existing=False)
            return

    def delete_memo(self, memo: dict) -> None:
        if not confirm_delete(self, "선택한 메모를 삭제할까요?"):
            return
        key = self.memo_key(memo)
        dialog = self.sticky_windows.get(key)
        if dialog is not None and dialog.isVisible():
            dialog.accept()
        self.sticky_windows.pop(key, None)
        self.main.data.get("memos", []).remove(memo)
        self.main.save_data()
        self.refresh()


class ScheduleListTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText("검색...")
        self.search.setFixedWidth(120)
        self.search.setFixedHeight(26)
        self.search.setStyleSheet("QLineEdit { padding: 1px 6px; font-size: 9pt; }")
        self.search.textChanged.connect(self.refresh)
        self.sort_controls = SortControls(
            self.refresh,
            modes=[("등록", "created"), ("기한", "deadline"), ("중요도", "priority")],
        )
        corner = QWidget()
        corner_layout = QHBoxLayout(corner)
        corner_layout.setContentsMargins(0, 0, 4, 0)
        corner_layout.setSpacing(4)
        corner_layout.addWidget(self.search)
        corner_layout.addWidget(self.sort_controls)
        self.tabs = QTabWidget()
        self.tabs.setCornerWidget(corner, Qt.Corner.TopRightCorner)
        add_btn = QPushButton("+ 일정")
        add_btn.clicked.connect(lambda: self.edit_schedule())
        self.grid = GridPanel(columns=2)
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(self.grid, 1)
        page_layout.addLayout(bottom_action_bar(add_btn))
        self.tabs.addTab(page, "일정 알림")
        layout.addWidget(self.tabs, 1)

    def refresh(self) -> None:
        cards = []
        q = self.search.text().strip().lower()
        source_items = self.main.data.get("schedules", [])
        visible_items = self.sort_controls.sort_items(source_items, lambda item: item.get("title") or item.get("memo", ""))
        for schedule in visible_items:
            if q and q not in (schedule.get("title", "") + " " + schedule.get("memo", "")).lower():
                continue
            subtitle = f"{display_datetime(schedule.get('datetime', ''), schedule.get('repeat', 'none'))}\n{short_preview(schedule.get('memo', ''), 120)}"
            card = make_card(schedule.get("title", "(제목 없음)"), subtitle, card_size="c")
            add_card_actions(
                card,
                [
                    ("edit", "수정", lambda checked=False, value=schedule: self.edit_schedule(value), False),
                    ("delete", "삭제", lambda checked=False, value=schedule: self.delete_schedule(value), True),
                ],
            )
            cards.append(card)
        callback = (lambda old, new: self.reorder_items(source_items, visible_items, old, new)) if self.sort_controls.is_manual() else None
        self.grid.add_cards(cards, on_reorder=callback)

    def reorder_items(self, source: list[dict], visible: list[dict], old: int, new: int) -> None:
        apply_manual_reorder(source, visible, old, new)
        self.main.save_data()

    def edit_schedule(self, schedule: dict | None = None) -> None:
        dialog = ScheduleDialog(schedule)
        while dialog.exec() == dialog.DialogCode.Accepted:
            value = dialog.value()
            if not value.get("title"):
                show_modern_warning(dialog, "입력 확인", "이름을 지정해주세요.")
                continue
            items = self.main.data.setdefault("schedules", [])
            if schedule in items:
                items[items.index(schedule)] = value
            else:
                value["sort_order"] = len(items)
                items.append(value)
            self.main.save_data()
            return

    def delete_schedule(self, schedule: dict) -> None:
        if not confirm_delete(self, "선택한 일정을 삭제할까요?"):
            return
        self.main.data.get("schedules", []).remove(schedule)
        self.main.save_data()


# 그룹 관리 다이얼로그

class _GroupManagerDialog(QDialog):
    """할 일 그룹 이름 설정 (최대 3개)."""

    def __init__(self, parent: QWidget, groups: list[object]) -> None:
        super().__init__(parent)
        self.setWindowTitle("그룹 관리")
        self.setModal(True)
        apply_modern_dialog_style(self)
        normalized = normalize_todo_groups(groups)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)
        title_lbl = QLabel("그룹 이름 설정 (최대 3개)")
        layout.addWidget(title_lbl)
        self._edits: list[QLineEdit] = []
        for i in range(3):
            row = QHBoxLayout()
            lbl = QLabel(f"그룹 {i + 1}")
            lbl.setFixedWidth(50)
            edit = QLineEdit(normalized[i] if i < len(normalized) else "")
            edit.setPlaceholderText(f"그룹 {i + 1}")
            self._edits.append(edit)
            row.addWidget(lbl)
            row.addWidget(edit)
            layout.addLayout(row)
        hint = QLabel("비워두면 해당 그룹은 숨겨집니다.")
        hint.setStyleSheet("color:#9CA3AF;font-size:9pt;")
        layout.addWidget(hint)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.reject)
        ok_btn = QPushButton("저장")
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)
        self.resize(310, 230)

    def result_groups(self) -> list[str]:
        """비어있는 칸은 제외하고 그룹명만 반환."""
        return [edit.text().strip() for edit in self._edits if edit.text().strip()]


# 할 일 다이얼로그

class TodoDialog(QDialog):
    """할 일 등록/수정 다이얼로그."""

    def __init__(self, item: dict | None = None, groups: list[str] | None = None) -> None:
        super().__init__()
        self.setWindowTitle("할 일")
        apply_modern_dialog_style(self)
        self.item = item or {}
        _groups = normalize_todo_groups(groups or ["그룹 1", "그룹 2", "그룹 3"])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(10)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(8)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # 제목
        self.title_edit = QLineEdit(self.item.get("title", ""))

        # 그룹
        self.group_combo = QComboBox()
        self.group_combo.addItems(_groups)
        fit_combo_to_contents(self.group_combo, 140)
        cur_group = self.item.get("group", "")
        if cur_group in _groups:
            self.group_combo.setCurrentText(cur_group)

        self.priority_combo = QComboBox()
        self.priority_combo.addItems(["상", "중", "하"])
        self.priority_combo.setCurrentText(self.item.get("priority", "하") if self.item.get("priority", "하") in {"상", "중", "하"} else "하")
        fit_combo_to_contents(self.priority_combo, 88)

        # 일정 시간
        current = QDateTime.fromString(self.item.get("datetime", ""), Qt.DateFormat.ISODate)
        if not current.isValid():
            current = QDateTime.currentDateTime()
        self.alarm_date = QDateEdit()
        self.alarm_date.setCalendarPopup(True)
        self.alarm_date.setDate(current.date())
        self.alarm_date.setMinimumWidth(140)
        self.alarm_date.dateChanged.connect(lambda _: self._update_notify_label())
        cal = self.alarm_date.calendarWidget()
        today_fmt = QTextCharFormat()
        today_fmt.setBackground(QColor("#FFF3B0"))
        today_fmt.setForeground(QColor("#111827"))
        today_fmt.setFontWeight(700)
        cal.setDateTextFormat(QDate.currentDate(), today_fmt)
        self.selected_time = current.time()
        self.time_label = QLabel()
        self.time_label.setObjectName("cardTitle")
        self.time_label.setMinimumWidth(48)
        self._update_time_label()
        dt_row = QHBoxLayout()
        dt_row.setContentsMargins(0, 0, 0, 0)
        dt_row.setSpacing(6)
        dt_row.addWidget(self.alarm_date)
        dt_row.addWidget(self.time_label)
        dt_row.addStretch(1)
        dt_widget = QWidget()
        dt_widget.setLayout(dt_row)

        # 시간 선택
        q_row1 = QHBoxLayout()
        q_row1.setContentsMargins(0, 0, 0, 0)
        q_row1.setSpacing(3)
        for h in range(9, 19):
            b = QPushButton(str(h))
            b.setFixedSize(34, 28)
            b.setStyleSheet(_TIME_BTN_STYLE)
            b.clicked.connect(lambda c=False, v=h: self._set_hour(v))
            q_row1.addWidget(b)
        q_row1.addStretch(1)
        q_row2 = QHBoxLayout()
        q_row2.setContentsMargins(0, 0, 0, 0)
        q_row2.setSpacing(3)
        for lbl, mins in [("-10분", -10), ("+10분", 10), ("-30분", -30), ("+30분", 30)]:
            b = QPushButton(lbl)
            b.setFixedHeight(28)
            b.setStyleSheet(_TIME_BTN_STYLE)
            b.clicked.connect(lambda c=False, m=mins: self._adjust(m))
            q_row2.addWidget(b)
        q_row2.addStretch(1)
        time_widget = QWidget()
        tvl = QVBoxLayout(time_widget)
        tvl.setContentsMargins(0, 0, 0, 0)
        tvl.setSpacing(3)
        tvl.addLayout(q_row1)
        tvl.addLayout(q_row2)

        # 반복
        self.repeat_combo = QComboBox()
        self.repeat_combo.addItems(["없음", "매일", "매주", "매월", "매년"])
        fit_combo_to_contents(self.repeat_combo, 140)
        _rmap = {"none": "없음", "daily": "매일", "weekly": "매주", "monthly": "매월",
                 "yearly": "매년", "weekday": "매주"}
        self.repeat_combo.setCurrentText(_rmap.get(self.item.get("repeat", "none"), "없음"))
        self.repeat_combo.currentTextChanged.connect(self._on_repeat_changed)

        # 매주 반복 요일 선택
        weekday_widget = QWidget()
        wd_layout = QHBoxLayout(weekday_widget)
        wd_layout.setContentsMargins(0, 0, 0, 0)
        wd_layout.setSpacing(4)
        self._weekday_checks: list[QCheckBox] = []
        saved_wd = self.item.get("repeat_weekdays", [])
        if self.item.get("repeat") == "weekly" and not saved_wd:
            saved_wd = [current.date().dayOfWeek() - 1]
        for i, day_name in enumerate(WEEKDAYS):
            cb = QCheckBox(day_name)
            cb.setChecked(i in saved_wd)
            self._weekday_checks.append(cb)
            wd_layout.addWidget(cb)
        wd_layout.addStretch(1)
        self._weekday_widget = weekday_widget
        self._weekday_widget.setVisible(self.item.get("repeat", "none") in {"weekly", "weekday"})

        # 알림
        self.notify = QSpinBox()
        self.notify.setRange(0, 10080)
        self.notify.setValue(int(self.item.get("notify_before_minutes", 30)))
        self.notify.valueChanged.connect(lambda _: self._update_notify_label())
        self.notify.setVisible(False)
        self.notify_at_label = QLabel()
        self.notify_at_label.setObjectName("cardTitle")
        self.notify_at_label.setMinimumWidth(130)
        self._update_notify_label()
        n_row = QHBoxLayout()
        n_row.setContentsMargins(0, 0, 0, 0)
        n_row.setSpacing(4)
        n_row.addWidget(self.notify_at_label)
        for lbl, mins in [("정각", 0), ("5분 전", 5), ("10분 전", 10), ("30분 전", 30), ("1시간 전", 60)]:
            b = QPushButton(lbl)
            b.setFixedHeight(28)
            b.setStyleSheet(_TIME_BTN_STYLE)
            b.clicked.connect(lambda c=False, m=mins: self.notify.setValue(m))
            n_row.addWidget(b)
        p9 = QPushButton("전일 9시")
        p9.setFixedHeight(28)
        p9.setStyleSheet(_TIME_BTN_STYLE)
        p9.clicked.connect(lambda: self._prev_day(9))
        p18 = QPushButton("전일 6시")
        p18.setFixedHeight(28)
        p18.setStyleSheet(_TIME_BTN_STYLE)
        p18.clicked.connect(lambda: self._prev_day(18))
        n_row.addWidget(p9)
        n_row.addWidget(p18)
        n_row.addStretch(1)
        notify_widget = QWidget()
        notify_widget.setLayout(n_row)

        # 메모
        self.memo_edit = QTextEdit()
        self.memo_edit.setPlainText(self.item.get("memo", ""))
        self.memo_edit.setFixedHeight(60)

        form.addRow("제목", self.title_edit)
        form.addRow("그룹", self.group_combo)
        form.addRow("중요도", self.priority_combo)
        form.addRow("일정 시간", dt_widget)
        form.addRow("시간 선택", time_widget)
        form.addRow("반복", self.repeat_combo)
        form.addRow("", self._weekday_widget)
        form.addRow("알림", notify_widget)
        form.addRow("메모", self.memo_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("확인")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_repeat_changed(self, text: str) -> None:
        self._weekday_widget.setVisible(text == "매주")

    def _selected_dt(self) -> datetime:
        return datetime.combine(self.alarm_date.date().toPyDate(), self.selected_time.toPyTime())

    def _update_notify_label(self) -> None:
        if hasattr(self, "notify_at_label"):
            notify_at = self._selected_dt() - timedelta(minutes=self.notify.value())
            self.notify_at_label.setText(notify_at.strftime("%Y-%m-%d %H:%M"))

    def _set_hour(self, hour: int) -> None:
        self.selected_time = QTime(hour, 0)
        self._update_time_label()
        self._update_notify_label()

    def _adjust(self, minutes: int) -> None:
        self.selected_time = self.selected_time.addSecs(minutes * 60)
        self._update_time_label()
        self._update_notify_label()

    def _update_time_label(self) -> None:
        self.time_label.setText(f"{self.selected_time.hour()}:{self.selected_time.minute():02d}")

    def _prev_day(self, hour: int) -> None:
        target = self._selected_dt()
        na = datetime.combine(target.date() - timedelta(days=1), dt_time(hour, 0))
        self.notify.setValue(max(0, int((target - na).total_seconds() // 60)))
        self._update_notify_label()

    def value(self) -> dict:
        data = dict(self.item)
        if not data.get("id"):
            data["id"] = new_id("sc")
            data["created_at"] = now_iso()
            data["sort_order"] = 0
            data["usage_count"] = 0
        alarm_dt = QDateTime(self.alarm_date.date(), self.selected_time)
        _repeat_map = {"없음": "none", "매일": "daily", "매주": "weekly", "매월": "monthly",
                       "매년": "yearly"}
        repeat_val = _repeat_map.get(self.repeat_combo.currentText(), "none")
        data.update({
            "title": self.title_edit.text().strip(),
            "group": self.group_combo.currentText(),
            "priority": self.priority_combo.currentText() or "하",
            "deadline": self.alarm_date.date().toString("yyyy-MM-dd"),
            "datetime": alarm_dt.toString(Qt.DateFormat.ISODate),
            "notify_before_minutes": self.notify.value(),
            "repeat": repeat_val,
            "memo": self.memo_edit.toPlainText(),
            "last_notified_at": data.get("last_notified_at", ""),
        })
        if repeat_val == "weekly":
            weekdays = [i for i, cb in enumerate(self._weekday_checks) if cb.isChecked()]
            data["repeat_weekdays"] = weekdays or [alarm_dt.date().dayOfWeek() - 1]
        else:
            data.pop("repeat_weekdays", None)
        data.setdefault("completed", False)
        data.setdefault("completed_at", None)
        return data


# 완료 항목 다이얼로그

class CompletedItemsDialog(QDialog):
    """완료된 할 일 목록. 체크 해제로 복원 가능."""

    def __init__(self, parent: QWidget, completed: list[dict], on_uncomplete=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("완료 항목")
        self.setModal(True)
        apply_modern_dialog_style(self)
        self.changed = False
        self.on_uncomplete = on_uncomplete
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        hdr = QLabel(f"완료된 항목 ({len(completed)}개)")
        hdr.setObjectName("cardTitle")
        layout.addWidget(hdr)
        if not completed:
            empty = QLabel("완료된 항목이 없습니다.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(empty)
        else:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            content = QWidget()
            cl = QVBoxLayout(content)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(3)
            for item in sorted(completed, key=lambda x: x.get("completed_at", ""), reverse=True):
                row = QWidget()
                row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
                row.setFixedHeight(36)
                rl = QHBoxLayout(row)
                rl.setContentsMargins(6, 3, 6, 3)
                rl.setSpacing(8)
                cb = QCheckBox()
                cb.setChecked(True)
                cb.toggled.connect(lambda checked, i=item, r=row: self._handle_toggle(i, checked, r))
                rl.addWidget(cb)
                priority = item.get("priority", "하") or "하"
                p_colors = {"상": ("#FEE2E2", "#DC2626"), "중": ("#DBEAFE", "#1D4ED8"), "하": ("#F3F4F6", "#6B7280")}
                p_bg, p_fg = p_colors.get(priority, p_colors["하"])
                p_lbl = QLabel(priority)
                p_lbl.setFixedSize(22, 18)
                p_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                p_lbl.setStyleSheet(f"background:{p_bg};color:{p_fg};border-radius:3px;font-size:8pt;font-weight:800;")
                rl.addWidget(p_lbl)
                grp = item.get("group", "")
                if grp:
                    g_lbl = QLabel(grp[:5])
                    g_lbl.setFixedHeight(18)
                    g_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    g_lbl.setStyleSheet("background:#9CA3AF;color:white;border-radius:3px;font-size:8pt;font-weight:700;padding:0 4px;")
                    rl.addWidget(g_lbl)
                title_lbl = QLabel(item.get("title", "(제목 없음)"))
                title_lbl.setStyleSheet("text-decoration:line-through;color:#9CA3AF;")
                rl.addWidget(title_lbl, 1)
                at = item.get("completed_at", "")
                if at:
                    at_lbl = QLabel(at[:10])
                    at_lbl.setStyleSheet("color:#9CA3AF;font-size:9pt;")
                    rl.addWidget(at_lbl)
                cl.addWidget(row)
            cl.addStretch(1)
            scroll.setWidget(content)
            scroll.setFixedHeight(min(560, max(180, len(completed) * 38 + 16)))
            layout.addWidget(scroll)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
        self.resize(560, min(680, max(260, len(completed) * 38 + 130)))

    def _handle_toggle(self, item: dict, checked: bool, row: QWidget) -> None:
        if not checked and self.on_uncomplete:
            self.on_uncomplete(item)
            self.changed = True
            row.setStyleSheet("QWidget{background:#F0FDF4;border-radius:4px;}")
            for i in range(row.layout().count()):
                w = row.layout().itemAt(i).widget()
                if isinstance(w, QLabel) and "line-through" in (w.styleSheet() or ""):
                    w.setStyleSheet("color:#15803D;")


# 할 일(Todo) + 타이머 탭

class TodoListTab(QWidget):
    """그룹별 칸반 컬럼 + 타이머 탭."""

    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        self._sort_mode = "created"
        self._sort_asc = True
        self._timer_mode = "duration"
        # 타이머 상태
        self._countdown = 0
        self._timer_running = False
        self._countdown_qTimer_obj = QTimer(self)
        self._countdown_qTimer_obj.setInterval(1000)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._tab_widget = QTabWidget()

        # 코너 컨트롤
        self.search = QLineEdit()
        self.search.setPlaceholderText("검색...")
        self.search.setFixedWidth(CORNER_SEARCH_WIDTH)
        self.search.setFixedHeight(CORNER_CONTROL_HEIGHT)
        self.search.setStyleSheet("QLineEdit{padding:1px 6px;font-size:9pt;}")
        self.search.textChanged.connect(self.refresh)

        self.grp_btn = QPushButton("그룹 관리")
        set_corner_button_policy(self.grp_btn, 92)
        self.grp_btn.clicked.connect(self._manage_groups)

        self.sort_controls = SortControls(
            self._on_sort_changed,
            modes=[("등록", "created"), ("기한", "deadline"), ("중요도", "priority"), ("수동", "manual")],
            default_order="asc",
        )
        self.sort_combo = self.sort_controls.mode
        self.order_combo = self.sort_controls.order

        corner = QWidget()
        cl = QHBoxLayout(corner)
        cl.setContentsMargins(0, 0, 4, 0)
        cl.setSpacing(4)
        cl.addWidget(self.search)
        cl.addWidget(self.grp_btn)
        cl.addWidget(self.sort_controls)
        self._tab_widget.setCornerWidget(corner, Qt.Corner.TopRightCorner)
        self._tab_widget.currentChanged.connect(self._on_tab_changed)

        # To Do 탭
        self._todo_page = QWidget()
        self._build_todo_page()
        self._tab_widget.addTab(self._todo_page, "To Do")

        # 타이머 탭
        self._timer_page = QWidget()
        self._build_timer_page()
        self._tab_widget.addTab(self._timer_page, "타이머")

        outer.addWidget(self._tab_widget)

    def _on_tab_changed(self, index: int) -> None:
        todo_visible = index == 0
        for widget in (self.search, self.grp_btn, self.sort_controls):
            widget.setVisible(todo_visible)

    # To Do 탭



    def _build_todo_page(self) -> None:
        layout = QVBoxLayout(self._todo_page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(8, GRID_PANEL_MARGINS[1], 8, 8)
        content_layout.setSpacing(6)

        # 컬럼 컨테이너
        self._cols_container = QWidget()
        self._cols_hbox = QHBoxLayout(self._cols_container)
        self._cols_hbox.setContentsMargins(0, 0, 0, 0)
        self._cols_hbox.setSpacing(6)
        content_layout.addWidget(self._cols_container, 1)
        layout.addWidget(content, 1)

        comp_btn = QPushButton("완료 항목 보기")
        comp_btn.clicked.connect(self.show_completed_items)
        clear_btn = QPushButton("완료 항목 지우기")
        clear_btn.clicked.connect(self.clear_completed_items)
        add_btn = QPushButton("할 일 등록")
        add_btn.clicked.connect(lambda: self.edit_item())
        layout.addLayout(bottom_action_bar(comp_btn, clear_btn, add_btn))
    def _get_groups(self) -> list[str]:
        return normalize_todo_groups(self.main.data.get("todo_groups", ["그룹 1", "그룹 2", "그룹 3"]))

    def _get_group_meta(self) -> list[str]:
        return normalize_todo_groups(self.main.data.get("todo_groups", ["그룹 1", "그룹 2", "그룹 3"]))

    def _item_group(self, item: dict, groups: list[str]) -> str:
        g = item.get("group", "") or item.get("priority", "")
        return g if g in groups else groups[0]

    def _on_sort_changed(self) -> None:
        self._sort_mode = self.sort_combo.currentData() or "created"
        self._sort_asc = self.order_combo.currentData() == "asc"
        self.refresh()

    def _sorted_items(self, items: list[dict]) -> list[dict]:
        reverse = not self._sort_asc
        if self._sort_mode == "deadline":
            def dl_key(item: dict) -> str:
                return item.get("deadline") or item.get("datetime", "")[:10] or "9999-99-99"
            return sorted(items, key=dl_key, reverse=reverse)
        if self._sort_mode == "priority":
            ranks = {"상": 0, "중": 1, "하": 2, "": 2}
            return sorted(items, key=lambda x: (ranks.get(str(x.get("priority", "하") or "하"), 2), x.get("created_at", "")), reverse=reverse)
        if self._sort_mode == "manual":
            return sorted(items, key=lambda x: int(x.get("sort_order", 0) or 0))
        return sorted(items, key=lambda x: x.get("created_at", ""), reverse=reverse)

    def _manage_groups(self) -> None:
        current = self.main.data.get("todo_groups", ["그룹 1", "그룹 2", "그룹 3"])
        dlg = _GroupManagerDialog(self, current)
        if dlg.exec() == dlg.DialogCode.Accepted:
            new_groups = dlg.result_groups()
            self.main.data["todo_groups"] = new_groups
            self.main.save_data()
            self.refresh()

    # 리프레시

    def refresh(self) -> None:
        # 기존 컬럼 삭제
        while self._cols_hbox.count():
            child = self._cols_hbox.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        q = self.search.text().strip().lower()
        groups = self._get_group_meta()
        pending = [i for i in self.main.data.get("schedules", []) if not i.get("completed", False)]

        for g_idx, group_name in enumerate(groups):
            g_items = [i for i in pending if self._item_group(i, groups) == group_name]
            if q:
                g_items = [i for i in g_items if q in (i.get("title", "") + " " + i.get("memo", "")).lower()]
            g_items = self._sorted_items(g_items)
            col = self._make_col_widget(g_idx, group_name, g_items)
            self._cols_hbox.addWidget(col, 1)

    # 컬럼 위젯

    def _make_col_widget(self, idx: int, name: str, items: list[dict]) -> QWidget:
        col = QWidget()
        col.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        col.setAcceptDrops(True)
        col._todo_group_name = name
        col.dragEnterEvent = lambda event: self._todo_col_drag_enter(event)
        col.dragMoveEvent = lambda event: self._todo_col_drag_enter(event)
        col.dropEvent = lambda event, group=name: self._todo_col_drop(event, group)
        cl = QVBoxLayout(col)
        cl.setContentsMargins(4, 4, 4, 4)
        cl.setSpacing(4)

        hdr = QLabel(f"  {name}  ({len(items)})")
        hdr.setFixedHeight(30)
        hdr.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        hdr.setStyleSheet("background:#F8FAFC;color:#111827;border:1px solid #E5E7EB;border-radius:5px;font-weight:700;padding:0 8px;")
        cl.addWidget(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        il = QVBoxLayout(content)
        il.setContentsMargins(0, 0, 0, 0)
        il.setSpacing(3)
        for item in items:
            il.addWidget(self._make_card(item))
        if not items:
            e = QLabel("할 일 없음")
            e.setAlignment(Qt.AlignmentFlag.AlignCenter)
            e.setStyleSheet("color:#9CA3AF;font-size:9pt;padding:14px;")
            il.addWidget(e)
        il.addStretch(1)
        scroll.setWidget(content)
        cl.addWidget(scroll, 1)

        return col

    def _todo_card_mouse_press(self, card: QWidget, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            card._drag_start_pos = event.position().toPoint()

    def _todo_card_mouse_move(self, card: QWidget, event) -> None:
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        start = getattr(card, "_drag_start_pos", None)
        if start is None:
            return
        if (event.position().toPoint() - start).manhattanLength() < QApplication.startDragDistance():
            return
        item = getattr(card, "_todo_item", None)
        if not item:
            return
        drag = QDrag(card)
        mime = QMimeData()
        mime.setText(str(item.get("id", "")))
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.MoveAction)

    def _todo_col_drag_enter(self, event) -> None:
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def _todo_col_drop(self, event, group: str) -> None:
        item_id = event.mimeData().text()
        for item in self.main.data.get("schedules", []):
            if item.get("id") == item_id:
                item["group"] = group
                item["sort_order"] = self._next_group_sort_order(group)
                item["updated_at"] = now_iso()
                self.main.save_data()
                self.refresh()
                event.acceptProposedAction()
                return

    def _next_group_sort_order(self, group: str) -> int:
        items = [
            item for item in self.main.data.get("schedules", [])
            if not item.get("completed") and item.get("group") == group
        ]
        if not items:
            return 0
        return max(int(item.get("sort_order", 0) or 0) for item in items) + 1

    # 카드

    def _make_card(self, item: dict) -> QWidget:
        card = QWidget()
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card.setObjectName("todoCard")
        card.setFixedHeight(40)
        card.setCursor(Qt.CursorShape.OpenHandCursor)
        card._todo_item = item
        card.mousePressEvent = lambda event, c=card: self._todo_card_mouse_press(c, event)
        card.mouseMoveEvent = lambda event, c=card: self._todo_card_mouse_move(c, event)
        h = QHBoxLayout(card)
        h.setContentsMargins(6, 2, 6, 2)
        h.setSpacing(6)

        cb = QCheckBox()
        cb.setChecked(False)
        cb.toggled.connect(lambda checked, i=item: self._on_check(i, checked))
        h.addWidget(cb)

        priority = item.get("priority", "하") or "하"

        title_lbl = QLabel(item.get("title", "(제목 없음)"))
        title_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        title_lbl.setMinimumWidth(0)
        h.addWidget(title_lbl, 1)

        # D-day 배지 (일정 시간 기반)
        dt_str = item.get("datetime", "")
        if dt_str:
            try:
                dt = datetime.fromisoformat(dt_str)
                today = datetime.now().date()
                days_left = (dt.date() - today).days
                if days_left < 0:
                    dl_text, dl_color = f"D+{-days_left}", "#DC2626"
                elif days_left == 0:
                    dl_text, dl_color = "오늘", "#D97706"
                elif days_left <= 3:
                    dl_text, dl_color = f"D-{days_left}", "#D97706"
                else:
                    dl_text, dl_color = dt.strftime("%m/%d"), "#6B7280"
                dl_lbl = QLabel(dl_text)
                dl_lbl.setStyleSheet(f"color:{dl_color};font-size:9pt;font-weight:700;")
                dl_lbl.setFixedWidth(38)
                dl_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                h.addWidget(dl_lbl)
            except Exception:
                pass

        action_page = QWidget()
        action_row = QHBoxLayout(action_page)
        action_row.setContentsMargins(CARD_ACTION_ROW_MARGIN_X, CARD_ACTION_ROW_MARGIN_Y, CARD_ACTION_ROW_MARGIN_X, CARD_ACTION_ROW_MARGIN_Y)
        action_row.setSpacing(CARD_ACTION_ROW_SPACING)
        action_row.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        icon_size = QSize(CARD_ACTION_ICON_SIZE, CARD_ACTION_ICON_SIZE)
        action_row.addWidget(make_icon_button("edit", "수정", lambda c=False, i=item: self.edit_item(i), size=icon_size))
        action_row.addWidget(make_icon_button("delete", "삭제", lambda c=False, i=item: self.delete_item(i), True, size=icon_size))
        set_card_action_widget(card, action_page)
        if priority in {"상", "중"}:
            style = PRIORITY_STYLES[priority]
            card.setStyleSheet(
                f"QWidget#todoCard{{border-radius:5px;border:1px solid {style['border']};"
                f"background:{style['background']};}}"
            )
        else:
            card.setStyleSheet("QWidget#todoCard{border-radius:5px;border:1px solid #E5E7EB;}")
        return card

    # CRUD

    def _on_check(self, item: dict, checked: bool) -> None:
        if checked:
            item["completed"] = True
            item["completed_at"] = now_iso()
            self.main.save_data()

    def edit_item(self, item: dict | None = None, group: str = "") -> None:
        groups = self._get_groups()
        dialog = TodoDialog(item, groups=groups)
        if group and not item and group in groups:
            dialog.group_combo.setCurrentText(group)
        while dialog.exec() == dialog.DialogCode.Accepted:
            value = dialog.value()
            if not value.get("title"):
                show_modern_warning(dialog, "입력 확인", "제목을 입력해주세요.")
                continue
            items = self.main.data.setdefault("schedules", [])
            if item in items:
                items[items.index(item)] = value
            else:
                value["sort_order"] = len(items)
                items.append(value)
            self.main.save_data()
            return

    def delete_item(self, item: dict) -> None:
        if not confirm_delete(self, "선택한 항목을 삭제할까요?"):
            return
        self.main.data.get("schedules", []).remove(item)
        self.main.save_data()

    def show_completed_items(self) -> None:
        completed = [i for i in self.main.data.get("schedules", []) if i.get("completed")]
        dlg = CompletedItemsDialog(self, completed, on_uncomplete=lambda i: self._uncomplete_item(i))
        dlg.exec()
        if dlg.changed:
            self.main.save_data()

    def _uncomplete_item(self, item: dict) -> None:
        item["completed"] = False
        item["completed_at"] = None

    def clear_completed_items(self) -> None:
        completed = [i for i in self.main.data.get("schedules", []) if i.get("completed")]
        if not completed:
            show_modern_warning(self, "완료 항목 없음", "완료된 항목이 없습니다.")
            return
        if ask_modern_question(
            self, "완료 항목 삭제",
            f"완료된 항목 {len(completed)}개를 영구 삭제합니다.\n복구할 수 없습니다. 계속하시겠습니까?",
            accent="#DC2626", yes_text="삭제", no_text="취소",
        ):
            self.main.data["schedules"] = [
                i for i in self.main.data.get("schedules", []) if not i.get("completed")
            ]
            self.main.save_data()

    # 타이머 탭



    def _build_timer_page(self) -> None:
        layout = QVBoxLayout(self._timer_page)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        # 지속시간 입력 섹션
        self._timer_dur_section = QWidget()
        self._timer_dur_section.setMinimumWidth(300)
        self._timer_dur_section.setObjectName("timerPanel")
        dur_layout = QVBoxLayout(self._timer_dur_section)
        dur_layout.setContentsMargins(10, 10, 10, 12)
        dur_layout.setSpacing(8)
        dur_title = QLabel("시간 설정")
        dur_title.setObjectName("cardTitle")
        dur_layout.addWidget(dur_title)

        spin_row = QHBoxLayout()
        spin_row.setSpacing(3)
        self._t_h = QSpinBox()
        self._t_h.setRange(0, 23)
        self._t_m = QSpinBox()
        self._t_m.setRange(0, 59)
        self._t_s = QSpinBox()
        self._t_s.setRange(0, 59)
        for spin in (self._t_h, self._t_m, self._t_s):
            spin.setObjectName("timerTextValue")
            spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
            spin.setFrame(False)
            spin.setFixedWidth(26)
            spin.setFixedHeight(22)
            spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
            spin.setStyleSheet(_TIMER_VALUE_STYLE)
        for w, label in ((self._t_h, "시간"), (self._t_m, "분"), (self._t_s, "초")):
            spin_row.addWidget(w)
            unit = QLabel(label)
            unit.setObjectName("mutedText")
            spin_row.addWidget(unit)
        spin_row.addStretch(1)
        dur_layout.addLayout(spin_row)

        preset_row = QHBoxLayout()
        preset_row.setSpacing(4)
        for label, mins in [("5분", 5), ("10분", 10), ("15분", 15), ("30분", 30), ("1시간", 60), ("2시간", 120)]:
            b = QPushButton(label)
            b.setFixedHeight(28)
            b.setMinimumWidth(42)
            b.setStyleSheet(_TIME_BTN_STYLE)
            b.clicked.connect(lambda c=False, m=mins: self._timer_preset(m))
            preset_row.addWidget(b)
        preset_row.addStretch(1)
        dur_layout.addLayout(preset_row)
        self._timer_duration_start_btn = QPushButton("시작")
        self._timer_duration_start_btn.setFixedHeight(32)
        self._timer_duration_start_btn.clicked.connect(self._start_duration_timer)
        dur_layout.addWidget(self._timer_duration_start_btn)

        # 특정 시간 입력 섹션
        self._timer_exact_section = QWidget()
        self._timer_exact_section.setMinimumWidth(250)
        self._timer_exact_section.setObjectName("timerPanel")
        exact_form = QFormLayout(self._timer_exact_section)
        exact_form.setContentsMargins(10, 10, 10, 12)
        exact_form.setHorizontalSpacing(10)
        exact_form.setVerticalSpacing(7)
        exact_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        exact_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        exact_form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        exact_title = QLabel("특정 시간")
        exact_title.setObjectName("cardTitle")
        exact_form.addRow(exact_title)

        self._exact_timer_date = QDateEdit()
        self._exact_timer_date.setCalendarPopup(True)
        self._exact_timer_date.setDate(QDate.currentDate())
        self._exact_timer_date.setMinimumWidth(154)
        self._exact_timer_date.setFixedHeight(28)
        ecal = self._exact_timer_date.calendarWidget()
        efmt = QTextCharFormat()
        efmt.setBackground(QColor("#FFF3B0"))
        efmt.setForeground(QColor("#111827"))
        efmt.setFontWeight(700)
        ecal.setDateTextFormat(QDate.currentDate(), efmt)

        self._exact_timer_hour = QComboBox()
        self._exact_timer_hour.setObjectName("timerCompactCombo")
        for h in range(24):
            self._exact_timer_hour.addItem(f"{h:02d}시")
        self._exact_timer_hour.setCurrentIndex(datetime.now().hour)
        fit_combo_to_contents(self._exact_timer_hour, 72)
        self._exact_timer_hour.setFixedHeight(24)
        self._exact_timer_hour.setStyleSheet(_TIMER_COMPACT_COMBO_STYLE)

        self._exact_timer_min = QComboBox()
        self._exact_timer_min.setObjectName("timerCompactCombo")
        for m in range(0, 60, 10):
            self._exact_timer_min.addItem(f"{m:02d}분")
        fit_combo_to_contents(self._exact_timer_min, 72)
        self._exact_timer_min.setFixedHeight(24)
        self._exact_timer_min.setStyleSheet(_TIMER_COMPACT_COMBO_STYLE)

        exact_time_row = QHBoxLayout()
        exact_time_row.setContentsMargins(0, 0, 0, 0)
        exact_time_row.setSpacing(6)
        exact_time_row.addWidget(self._exact_timer_hour)
        exact_time_row.addWidget(self._exact_timer_min)
        exact_time_row.addStretch(1)
        exact_time_widget = QWidget()
        exact_time_widget.setObjectName("timerExactTimeField")
        exact_time_widget.setLayout(exact_time_row)
        exact_time_widget.setFixedHeight(26)
        exact_time_widget.setStyleSheet("QWidget#timerExactTimeField { background: transparent; }")

        exact_form.addRow("날짜", self._exact_timer_date)
        exact_form.addRow("시간", exact_time_widget)
        self._timer_exact_start_btn = QPushButton("시작")
        self._timer_exact_start_btn.setFixedHeight(30)
        self._timer_exact_start_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._timer_exact_start_btn.clicked.connect(self._start_exact_timer)
        exact_form.addRow(self._timer_exact_start_btn)

        timer_inputs = QHBoxLayout()
        timer_inputs.setSpacing(10)
        timer_inputs.addWidget(self._timer_dur_section, 1)
        timer_inputs.addWidget(self._timer_exact_section, 1)
        layout.addLayout(timer_inputs)

        # 카운트다운 디스플레이
        self._timer_display = QLabel("00:00:00")
        self._timer_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._timer_display.setStyleSheet("font-size:32pt;font-weight:900;letter-spacing:3px;padding:8px;")
        layout.addWidget(self._timer_display)

        # 완료 후 작업
        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        self._timer_action = QComboBox()
        self._timer_action.addItems(["알림", "컴퓨터 종료", "프로그램 시작", "프로그램 종료"])
        fit_combo_to_contents(self._timer_action, 140)
        self._timer_action.currentIndexChanged.connect(self._on_timer_action_changed)

        self._timer_msg = QLineEdit()
        self._timer_msg.setPlaceholderText("알림 메시지 (선택)...")

        prog_widget = QWidget()
        prog_hl = QHBoxLayout(prog_widget)
        prog_hl.setContentsMargins(0, 0, 0, 0)
        self._timer_prog = QLineEdit()
        self._timer_prog.setPlaceholderText("경로 또는 프로세스 이름 (.exe)")
        browse_btn = QPushButton("찾아보기")
        browse_btn.setFixedHeight(28)
        browse_btn.clicked.connect(self._browse_program)
        prog_hl.addWidget(self._timer_prog)
        prog_hl.addWidget(browse_btn)

        form.addRow("완료 후 작업", self._timer_action)
        self._timer_msg_lbl = QLabel("알림 메시지")
        form.addRow(self._timer_msg_lbl, self._timer_msg)
        self._timer_prog_lbl = QLabel("프로그램")
        form.addRow(self._timer_prog_lbl, prog_widget)
        self._timer_prog_widget = prog_widget
        layout.addLayout(form)
        self._on_timer_action_changed(0)

        # 제어 버튼
        ctrl_row = QHBoxLayout()
        ctrl_row.addStretch(1)
        self._timer_reset_btn = QPushButton("초기화")
        self._timer_reset_btn.setFixedHeight(36)
        self._timer_reset_btn.clicked.connect(self._timer_reset)
        ctrl_row.addWidget(self._timer_reset_btn)
        ctrl_row.addStretch(1)
        layout.addLayout(ctrl_row)

        self._timer_status = QLabel("")
        self._timer_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._timer_status.setStyleSheet("color:#9CA3AF;font-size:9pt;")
        layout.addWidget(self._timer_status)
        layout.addStretch(1)

        # QTimer 연결
        self._countdown_qTimer_obj.timeout.connect(self._timer_tick)
        self._timer_active_mode = ""
        self._timer_page.setStyleSheet(
            """
            QWidget#timerPanel {
                border: 1px solid #E5E7EB;
                border-radius: 6px;
                background: rgba(255,255,255,0.55);
            }
            QWidget#timerPanel QComboBox#timerCompactCombo QAbstractItemView {
                background: rgba(255,255,255,0.55);
                border: 1px solid #E5E7EB;
            }
            QWidget#timerPanel QWidget#timerExactTimeField {
                background: transparent;
            }
            """
        )

    # 타이머 헬퍼

    def _timer_preset(self, minutes: int) -> None:
        self._t_h.setValue(minutes // 60)
        self._t_m.setValue(minutes % 60)
        self._t_s.setValue(0)

    def _on_timer_action_changed(self, index: int) -> None:
        action = self._timer_action.currentText()
        is_prog = action in ("프로그램 시작", "프로그램 종료")
        is_notify = action == "알림"
        self._timer_msg.setVisible(is_notify)
        self._timer_msg_lbl.setVisible(is_notify)
        self._timer_prog_widget.setVisible(is_prog)
        self._timer_prog_lbl.setVisible(is_prog)

    def _browse_program(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "프로그램 선택", "", "실행 파일 (*.exe);;모든 파일 (*)")
        if path:
            self._timer_prog.setText(path)

    def _start_duration_timer(self) -> None:
        if self._timer_running and self._timer_active_mode == "duration":
            self._pause_timer()
            return
        if self._countdown > 0 and self._timer_active_mode == "duration":
            self._resume_timer("duration")
            return
        h = self._t_h.value()
        m = self._t_m.value()
        s = self._t_s.value()
        seconds = h * 3600 + m * 60 + s
        if seconds == 0:
            show_modern_warning(self._timer_page, "설정 오류", "타이머 시간을 설정해주세요.")
            return
        self._start_timer(seconds, "duration")

    def _start_exact_timer(self) -> None:
        if self._timer_running and self._timer_active_mode == "exact":
            self._pause_timer()
            return
        if self._countdown > 0 and self._timer_active_mode == "exact":
            self._resume_timer("exact")
            return
        minute_val = int(self._exact_timer_min.currentText().replace("분", ""))
        target = datetime.combine(
            self._exact_timer_date.date().toPyDate(),
            dt_time(self._exact_timer_hour.currentIndex(), minute_val)
        )
        seconds = int((target - datetime.now()).total_seconds())
        if seconds <= 0:
            show_modern_warning(self._timer_page, "설정 오류", "지정 시간이 현재 시간보다 이전입니다.")
            return
        self._start_timer(seconds, "exact")

    def _start_timer(self, seconds: int, mode: str) -> None:
        if self._timer_running or self._countdown > 0:
            self._timer_reset()
        self._countdown = seconds
        self._timer_active_mode = mode
        self._resume_timer(mode)

    def start_quick_timer(self, seconds: int, note: str = "", label: str = "") -> None:
        if seconds <= 0:
            return
        self._timer_msg.setText(note)
        self._timer_status.setText(f"{label} 시작" if label else "빠른 작업에서 시작")
        self._start_timer(seconds, "duration")
        self._tab_widget.setCurrentWidget(self._timer_page)

    def _pause_timer(self) -> None:
        self._countdown_qTimer_obj.stop()
        self._timer_running = False
        self._timer_status.setText("일시정지")
        self._update_timer_buttons(paused=True)

    def _resume_timer(self, mode: str) -> None:
        self._timer_active_mode = mode
        self._countdown_qTimer_obj.start()
        self._timer_running = True
        self._timer_status.setText("실행 중...")
        self._update_timer_buttons()

    def _update_timer_buttons(self, paused: bool = False) -> None:
        self._timer_duration_start_btn.setText("시작")
        self._timer_exact_start_btn.setText("시작")
        if self._timer_active_mode == "duration":
            self._timer_duration_start_btn.setText("재시작" if paused else "일시정지")
        elif self._timer_active_mode == "exact":
            self._timer_exact_start_btn.setText("재시작" if paused else "일시정지")

    def _timer_toggle(self) -> None:
        if self._timer_running:
            self._pause_timer()
        else:
            if self._countdown == 0:
                if self._timer_mode == "exact":
                    minute_val = int(self._exact_timer_min.currentText().replace("분", ""))
                    target = datetime.combine(
                        self._exact_timer_date.date().toPyDate(),
                        dt_time(self._exact_timer_hour.currentIndex(), minute_val)
                    )
                    secs = int((target - datetime.now()).total_seconds())
                    if secs <= 0:
                        show_modern_warning(self._timer_page, "설정 오류", "지정 시간이 현재 시간보다 이전입니다.")
                        return
                    self._countdown = secs
                else:
                    h = self._t_h.value()
                    m = self._t_m.value()
                    s = self._t_s.value()
                    self._countdown = h * 3600 + m * 60 + s
                    if self._countdown == 0:
                        show_modern_warning(self._timer_page, "설정 오류", "타이머 시간을 설정해주세요.")
                        return
            self._resume_timer(self._timer_mode)

    def _timer_reset(self) -> None:
        self._countdown_qTimer_obj.stop()
        self._timer_running = False
        self._countdown = 0
        self._timer_active_mode = ""
        self._timer_display.setText("00:00:00")
        self._timer_duration_start_btn.setText("시작")
        self._timer_exact_start_btn.setText("시작")
        self._timer_status.setText("")

    def _timer_tick(self) -> None:
        if self._countdown > 0:
            self._countdown -= 1
            h = self._countdown // 3600
            m = (self._countdown % 3600) // 60
            s = self._countdown % 60
            self._timer_display.setText(f"{h:02d}:{m:02d}:{s:02d}")
        else:
            self._countdown_qTimer_obj.stop()
            self._timer_running = False
            self._update_timer_buttons(paused=True)
            self._timer_duration_start_btn.setText("시작")
            self._timer_exact_start_btn.setText("시작")
            self._timer_status.setText("완료!")
            self._execute_timer_action()
            self._timer_active_mode = ""

    def _execute_timer_action(self) -> None:
        from ui.common import flash_taskbar
        flash_taskbar(self.main)
        action = self._timer_action.currentText()
        if action == "알림":
            msg = self._timer_msg.text().strip() or "타이머가 완료되었습니다!"
            show_topmost_modern_info(self.main, "타이머 완료", msg)
        elif action == "컴퓨터 종료":
            if ask_modern_question(self.main, "컴퓨터 종료",
                                   "컴퓨터를 종료하시겠습니까?\n(60초 후 자동 종료)", yes_text="종료", no_text="취소"):
                try:
                    subprocess.run(["shutdown", "/s", "/t", "60"], check=False)
                except Exception as exc:
                    show_modern_warning(self.main, "오류", str(exc))
        elif action == "프로그램 시작":
            path = self._timer_prog.text().strip()
            if path:
                try:
                    subprocess.Popen([path])
                    show_modern_info(self.main, "타이머 완료", f"프로그램 시작:\n{path}")
                except Exception as exc:
                    show_modern_warning(self.main, "실행 오류", str(exc))
        elif action == "프로그램 종료":
            name = self._timer_prog.text().strip()
            if name:
                try:
                    subprocess.run(["taskkill", "/F", "/IM", name], capture_output=True, check=False)
                    show_modern_info(self.main, "타이머 완료", f"프로그램 종료:\n{name}")
                except Exception as exc:
                    show_modern_warning(self.main, "종료 오류", str(exc))

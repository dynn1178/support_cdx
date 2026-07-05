"""스티커 메모 창과 인덱스 메모 카드 (tab_memo.py에서 분리).
"""

from __future__ import annotations

import random
import subprocess
import sys
from datetime import date as py_date, datetime, time as dt_time, timedelta
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt6.QtCore import QDate, QDateTime, QEasingCurve, QEvent, QMimeData, QPoint, QPropertyAnimation, QRect, QRectF, QSize, QTime, QTimer, Qt
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
        """인덱스 아이콘 텍스트. 커스텀 아이콘 → 내용 첫 줄 → 제목 순 폴백."""
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
        memo_tab = getattr(self.main, "memo_tab", None)
        if memo_tab is None:
            return []
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
    DRAG_HANDLE_H = 14
    MAX_LINES = 10
    _hover_manager_timer: QTimer | None = None

    _currently_expanded: "MemoIndexCard | None" = None  # 현재 열린 카드
    _all_cards: "list[MemoIndexCard]" = []              # 모든 카드 레지스트리
    _drag_active: "MemoIndexCard | None" = None         # 순서 변경 드래그 중인 카드

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

        # 드래그 핸들 — 세로로 끌어 인덱스 순서를 바꾼다.
        self._drag_handle = QLabel("≡")
        self._drag_handle.setObjectName("memoIndexDragHandle")
        self._drag_handle.setToolTip("드래그하여 인덱스 순서 변경")
        self._drag_handle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._drag_handle.setFixedHeight(self.DRAG_HANDLE_H)
        self._drag_handle.setCursor(Qt.CursorShape.OpenHandCursor)
        self._drag_handle.mousePressEvent = self._drag_handle_press
        self._drag_handle.mouseMoveEvent = self._drag_handle_move
        self._drag_handle.mouseReleaseEvent = self._drag_handle_release
        self._drag_offset = QPoint()
        el.addWidget(self._drag_handle)

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
        """확장 카드 아이콘 버튼용 텍스트. 미지정 시 ◇."""
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
        if cls._drag_active is not None:
            return  # 순서 변경 드래그 중에는 확장/축소를 건드리지 않는다
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

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.DevicePixelRatioChange:
            QTimer.singleShot(0, self.resync_after_screen_change)
            # 화면 신호가 누락돼도 카드가 감지한 DPR 변경으로 전역 복구(재생성)를
            # 예약한다. 디바운스 타이머라 여러 카드가 동시에 불러도 1회만 실행된다.
            if self.main is not None and hasattr(self.main, "queue_screen_layout_changed"):
                self.main.queue_screen_layout_changed()

    def resync_after_screen_change(self) -> None:
        # 모니터 배율/연결 구성이 바뀌면 프레임리스 고정 크기 창이 이전 배율의
        # 물리 크기로 렌더링된 채 남는다(MainWindow._resync_geometry_after_dpi_change
        # 와 동일한 Windows 동작). 실제 WM_MOVE 왕복만이 새 DPI 기준 재계산을
        # 강제하므로, 접힌 상태로 되돌린 뒤 이동 왕복을 재생한다.
        if not self.isVisible():
            return
        self.reset_compact_geometry()
        pos = self.pos()
        self.move(pos.x() + 1, pos.y())
        # self 를 부모로 둔 타이머라 카드가 먼저 닫혀도 콜백이 살아남지 않는다.
        restore = QTimer(self)
        restore.setSingleShot(True)
        restore.timeout.connect(lambda pos=pos: self.move(pos))
        restore.timeout.connect(restore.deleteLater)
        restore.start(0)

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
        # el: top(5) + handle + spacing(2) + text + spacing(2) + ctrl_row + bottom(5)
        height = max(70, 5 + self.DRAG_HANDLE_H + 2 + text_h + 2 + self.CTRL_H + 5)
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
        if MemoIndexCard._drag_active is not None:
            return
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

    # ── 순서 변경 드래그 ────────────────────────────────────────────

    def _drag_handle_press(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        MemoIndexCard._drag_active = self
        self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        self._drag_handle.setCursor(Qt.CursorShape.ClosedHandCursor)
        self.raise_()

    def _drag_handle_move(self, event) -> None:
        if MemoIndexCard._drag_active is not self:
            return
        target_y = int(event.globalPosition().y()) - self._drag_offset.y()
        self.move(self.x(), target_y)  # 세로 이동만 허용

    def _drag_handle_release(self, event) -> None:
        if MemoIndexCard._drag_active is not self:
            return
        MemoIndexCard._drag_active = None
        self._drag_handle.setCursor(Qt.CursorShape.OpenHandCursor)
        memo_tab = getattr(self.main, "memo_tab", None)
        if memo_tab is not None and hasattr(memo_tab, "commit_index_card_order"):
            memo_tab.commit_index_card_order(self)
        else:
            self.reset_compact_geometry()

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



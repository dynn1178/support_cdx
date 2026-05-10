from __future__ import annotations

from datetime import datetime, time as dt_time, timedelta

from PyQt6.QtCore import QDate, QDateTime, QPoint, QTime, QTimer, Qt
from PyQt6.QtGui import QTextCharFormat, QColor, QPainter, QPen, QPolygon
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
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
from ui.common import GridPanel, SortControls, add_card_actions, apply_manual_reorder, apply_modern_dialog_style, ask_modern_question, bump_usage, make_card, make_icon_button, show_modern_info, show_modern_warning


MEMO_COLORS = {
    "노랑": "#FFF9C4",
    "하늘": "#DFF3FF",
    "연두": "#E5F8D2",
    "분홍": "#FFE1EA",
    "흰색": "#FFFFFF",
}


WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]
REPEAT_LABELS = {"daily": "매일", "weekly": "매주", "monthly": "매월"}

PRIORITY_COLORS = {
    "상": {"bg": "#FFE4E4", "border": "#F87171", "badge_bg": "#F87171", "dot": "#DC2626"},
    "중": {"bg": "#EFF3FF", "border": "#818CF8", "badge_bg": "#818CF8", "dot": "#4338CA"},
    "하": {"bg": None, "border": None, "badge_bg": "#9CA3AF", "dot": "#9CA3AF"},
}
PRIORITY_ORDER = {"상": 0, "중": 1, "하": 2}


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
    def __init__(self, memo: dict, main=None, on_saved=None) -> None:
        super().__init__()
        self.memo = memo
        self.main = main
        self.on_saved = on_saved
        self.drag_position: QPoint | None = None
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
        layout.addWidget(self.drag_bar)
        self.text = QTextEdit(memo.get("content", ""))
        self.text.textChanged.connect(self.schedule_save)
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
        self.close_button = QPushButton("×")
        self.close_button.setFixedSize(26, 22)
        self.close_button.clicked.connect(self.accept)
        self.grip = CornerGrip(self)
        self.grip.setFixedSize(18, 18)
        controls.addWidget(self.always_on_top)
        controls.addWidget(self.color)
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
        self.memo["sticker_open"] = True

    def apply_color(self, *_args) -> None:
        color = MEMO_COLORS.get(self.color.currentText(), "#FFF9C4")
        self.setStyleSheet(
            f"""
            QDialog {{ background: {color}; border: 1px solid #B8B08A; }}
            QLabel {{ background: rgba(0,0,0,22); }}
            QTextEdit {{ background: transparent; border: 0; color: #2F2A14; padding: 6px; }}
            QPushButton {{ background: transparent; border: 0; color: #2F2A14; font-weight: 900; padding: 0; font-size: 15pt; }}
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

    def set_controls_visible(self, visible: bool) -> None:
        self.slider.setVisible(visible)
        self.close_button.setVisible(visible)
        self.always_on_top.setVisible(visible)
        self.color.setVisible(visible)
        self.grip.setVisible(visible)

    def enterEvent(self, event) -> None:
        self.set_controls_visible(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        QTimer.singleShot(180, self.hide_controls_if_idle)
        super().leaveEvent(event)

    def hide_controls_if_idle(self) -> None:
        if self.underMouse() or self.color.view().isVisible() or self.color.hasFocus():
            return
        self.set_controls_visible(False)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() <= self.drag_bar.height() + 4:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self.drag_position and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self.drag_position = None
        self.schedule_save()
        super().mouseReleaseEvent(event)

    def persist(self) -> None:
        self.memo["content"] = self.text.toPlainText()
        self.memo["always_on_top"] = self.always_on_top.isChecked()
        self.memo["background"] = self.color.currentText()
        self.memo["opacity"] = self.slider.value()
        self.memo["width"] = self.width()
        self.memo["height"] = self.height()
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


class MemoDialog(QDialog):
    def __init__(self, memo: dict | None = None) -> None:
        super().__init__()
        self.setWindowTitle("메모")
        apply_modern_dialog_style(self)
        self.memo = memo or {}
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.title = QLineEdit(self.memo.get("title", ""))
        self.content = QTextEdit(self.memo.get("content", ""))
        self.pinned = QCheckBox("메모 목록 상단에 고정")
        self.pinned.setToolTip("체크하면 메모 탭 목록에서 이 메모가 위쪽에 먼저 표시됩니다.")
        self.pinned.setChecked(bool(self.memo.get("pinned")))
        self.always_on_top = QCheckBox("스티커 항상 위")
        self.always_on_top.setChecked(bool(self.memo.get("always_on_top", True)))
        self.background = QComboBox()
        self.background.addItems(list(MEMO_COLORS))
        self.background.setCurrentText(self.memo.get("background", "노랑") if self.memo.get("background", "노랑") in MEMO_COLORS else "노랑")
        form.addRow("제목", self.title)
        form.addRow("내용", self.content)
        form.addRow("목록 옵션", self.pinned)
        form.addRow("스티커 옵션", self.always_on_top)
        form.addRow("배경색", self.background)
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
                "pinned": self.pinned.isChecked(),
                "always_on_top": self.always_on_top.isChecked(),
                "background": self.background.currentText(),
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
            btn.setFixedSize(42, 32)
            btn.clicked.connect(lambda checked=False, value=hour: self.set_time_hour(value))
            quick_time_row.addWidget(btn)
        quick_time_row.addStretch(1)
        time_adjust_row = QHBoxLayout()
        time_adjust_row.setContentsMargins(0, 0, 0, 0)
        time_adjust_row.setSpacing(4)
        for label, minutes in [("-10m", -10), ("+10m", 10), ("-30m", -30), ("+30m", 30)]:
            btn = QPushButton(label)
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
            btn.clicked.connect(lambda checked=False, value=minutes: self.notify.setValue(value))
            notify_row.addWidget(btn)
        prev_9 = QPushButton("전일 9시")
        prev_18 = QPushButton("전일 6시")
        prev_9.clicked.connect(lambda: self.set_previous_day_notify(9))
        prev_18.clicked.connect(lambda: self.set_previous_day_notify(18))
        notify_row.addWidget(prev_9)
        notify_row.addWidget(prev_18)
        notify_widget = QWidget()
        notify_widget.setLayout(notify_row)
        self.update_notify_label()
        self.memo = QTextEdit(self.schedule.get("memo", ""))
        form.addRow("제목", self.title)
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
        self.sticky_windows: list[StickyMemoDialog] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText("검색...")
        self.search.setFixedWidth(120)
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
        self.grid = GridPanel(columns=2)
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(self.grid, 1)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(add_btn)
        page_layout.addLayout(bottom)
        self.tabs.addTab(page, "메모")
        layout.addWidget(self.tabs, 1)

    def refresh(self) -> None:
        cards = []
        q = self.search.text().strip().lower()
        source_items = self.main.data.get("memos", [])
        memos = self.sort_controls.sort_items(source_items, lambda item: item.get("title") or item.get("content", ""))
        if not self.sort_controls.is_manual():
            memos = sorted(memos, key=lambda item: not item.get("pinned"))
        for memo in memos:
            if q and q not in (memo.get("title", "") + " " + memo.get("content", "")).lower():
                continue
            card = make_card(memo.get("title", "(제목 없음)"), short_preview(memo.get("content", ""), 160), card_size="b")
            self.add_memo_actions(card, memo)
            cards.append(card)
        callback = (lambda old, new: self.reorder_items(source_items, memos, old, new)) if self.sort_controls.is_manual() else None
        self.grid.add_cards(cards, on_reorder=callback)

    def add_memo_actions(self, card: QWidget, memo: dict) -> None:
        row = QHBoxLayout()
        row.setContentsMargins(0, 2, 0, 0)
        row.addStretch(1)
        pin = make_icon_button("pin", "목록 상단 고정/해제", lambda checked=False, value=memo: self.toggle_pin(value, pin))
        if memo.get("pinned"):
            pin.setStyleSheet("QToolButton#iconButton { color: #F5B301; font-size: 13pt; font-weight: 900; }")
        row.addWidget(pin)
        row.addWidget(make_icon_button("sticker", "스티커", lambda checked=False, value=memo: self.show_sticker(value)))
        row.addWidget(make_icon_button("edit", "수정", lambda checked=False, value=memo: self.edit_memo(value)))
        row.addWidget(make_icon_button("delete", "삭제", lambda checked=False, value=memo: self.delete_memo(value), True))
        card.layout().addLayout(row)

    def toggle_pin(self, memo: dict, button: QWidget | None = None) -> None:
        memo["pinned"] = not bool(memo.get("pinned"))
        if button is not None:
            color = "#F5B301" if memo.get("pinned") else "#A3A8B3"
            button.setStyleSheet(f"QToolButton#iconButton {{ color: {color}; font-size: 13pt; font-weight: 900; }}")
        self.main.save_data()

    def reorder_items(self, source: list[dict], visible: list[dict], old: int, new: int) -> None:
        apply_manual_reorder(source, visible, old, new)
        self.main.save_data()

    def show_sticker(self, memo: dict, track_usage: bool = True, raise_window: bool = True) -> None:
        if track_usage:
            bump_usage(memo)
            self.main.save_usage_data()
        dialog = StickyMemoDialog(memo, self.main, self.refresh)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.destroyed.connect(lambda _obj=None, dlg=dialog: self.forget_sticker(dlg))
        self.sticky_windows.append(dialog)
        dialog.show()
        if raise_window:
            dialog.raise_()

    def forget_sticker(self, dialog: StickyMemoDialog) -> None:
        if dialog in self.sticky_windows:
            self.sticky_windows.remove(dialog)

    def edit_memo(self, memo: dict | None = None) -> None:
        dialog = MemoDialog(memo)
        while dialog.exec() == dialog.DialogCode.Accepted:
            value = dialog.value()
            if not value.get("title"):
                show_modern_warning(dialog, "입력 확인", "이름을 지정해주세요.")
                continue
            items = self.main.data.setdefault("memos", [])
            if memo in items:
                items[items.index(memo)] = value
            else:
                value["sort_order"] = len(items)
                items.append(value)
            self.main.save_data()
            return

    def delete_memo(self, memo: dict) -> None:
        self.main.data.get("memos", []).remove(memo)
        self.main.save_data()


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
        self.sort_controls = SortControls(self.refresh)
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
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(add_btn)
        page_layout.addLayout(bottom)
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
        self.main.data.get("schedules", []).remove(schedule)
        self.main.save_data()


# ── 할 일 다이얼로그 ─────────────────────────────────────────────────────────

class TodoDialog(QDialog):
    """할 일 등록/수정 다이얼로그 (우선순위·마감기한·알림 포함)."""

    def __init__(self, item: dict | None = None) -> None:
        super().__init__()
        self.setWindowTitle("할 일")
        apply_modern_dialog_style(self)
        self.item = item or {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(12)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # 제목
        self.title_edit = QLineEdit(self.item.get("title", ""))

        # 우선순위
        self.priority_combo = QComboBox()
        self.priority_combo.addItems(["하", "중", "상"])
        self.priority_combo.setCurrentText(self.item.get("priority", "하"))
        self.priority_combo.setMinimumWidth(100)

        # 마감기한
        deadline_str = self.item.get("deadline", "")
        if not deadline_str:
            dt_str = self.item.get("datetime", "")
            if dt_str:
                deadline_str = dt_str[:10]
        self.deadline_edit = QDateEdit()
        self.deadline_edit.setCalendarPopup(True)
        self.deadline_edit.setMinimumWidth(150)
        dl_date = QDate.fromString(deadline_str, "yyyy-MM-dd") if deadline_str else QDate()
        self.deadline_edit.setDate(dl_date if dl_date.isValid() else QDate.currentDate())

        # 알림 날짜/시간
        current = QDateTime.fromString(self.item.get("datetime", ""), Qt.DateFormat.ISODate)
        if not current.isValid():
            current = QDateTime.currentDateTime()
        self.alarm_date = QDateEdit()
        self.alarm_date.setCalendarPopup(True)
        self.alarm_date.setDate(current.date())
        self.alarm_date.setMinimumWidth(150)
        self.alarm_date.dateChanged.connect(lambda _: self.update_notify_label())

        self.selected_time = current.time()
        self.time_label = QLabel()
        self.time_label.setObjectName("cardTitle")
        self.time_label.setMinimumWidth(52)
        self.update_time_label()

        dt_row = QHBoxLayout()
        dt_row.setContentsMargins(0, 0, 0, 0)
        dt_row.setSpacing(6)
        dt_row.addWidget(self.alarm_date)
        dt_row.addWidget(self.time_label)
        dt_row.addStretch(1)
        dt_widget = QWidget()
        dt_widget.setLayout(dt_row)

        # 시간 빠른선택
        quick_time_row = QHBoxLayout()
        quick_time_row.setContentsMargins(0, 0, 0, 0)
        quick_time_row.setSpacing(4)
        for hour in range(9, 19):
            btn = QPushButton(str(hour))
            btn.setFixedSize(42, 32)
            btn.clicked.connect(lambda checked=False, h=hour: self.set_time_hour(h))
            quick_time_row.addWidget(btn)
        quick_time_row.addStretch(1)
        time_adj_row = QHBoxLayout()
        time_adj_row.setContentsMargins(0, 0, 0, 0)
        time_adj_row.setSpacing(4)
        for lbl, mins in [("-10m", -10), ("+10m", 10), ("-30m", -30), ("+30m", 30)]:
            btn = QPushButton(lbl)
            btn.clicked.connect(lambda checked=False, m=mins: self.adjust_time(m))
            time_adj_row.addWidget(btn)
        time_adj_row.addStretch(1)
        qt_widget = QWidget()
        qtl = QVBoxLayout(qt_widget)
        qtl.setContentsMargins(0, 0, 0, 0)
        qtl.setSpacing(4)
        qtl.addLayout(quick_time_row)
        qtl.addLayout(time_adj_row)

        # 알림 설정
        self.notify = QSpinBox()
        self.notify.setRange(0, 10080)
        self.notify.setValue(int(self.item.get("notify_before_minutes", 30)))
        self.notify.valueChanged.connect(lambda _: self.update_notify_label())
        self.notify.setVisible(False)
        self.notify_at_label = QLabel()
        self.notify_at_label.setObjectName("cardTitle")
        self.notify_at_label.setMinimumWidth(142)
        self.update_notify_label()
        notify_row = QHBoxLayout()
        notify_row.setContentsMargins(0, 0, 0, 0)
        notify_row.setSpacing(6)
        notify_row.addWidget(self.notify_at_label)
        for lbl, mins in [("정각", 0), ("5분 전", 5), ("10분 전", 10), ("30분 전", 30), ("1시간 전", 60)]:
            btn = QPushButton(lbl)
            btn.clicked.connect(lambda checked=False, m=mins: self.notify.setValue(m))
            notify_row.addWidget(btn)
        prev_9 = QPushButton("전일 9시")
        prev_18 = QPushButton("전일 6시")
        prev_9.clicked.connect(lambda: self.set_previous_day_notify(9))
        prev_18.clicked.connect(lambda: self.set_previous_day_notify(18))
        notify_row.addWidget(prev_9)
        notify_row.addWidget(prev_18)
        notify_widget = QWidget()
        notify_widget.setLayout(notify_row)

        # 메모
        self.memo_edit = QTextEdit(self.item.get("memo", ""))
        self.memo_edit.setFixedHeight(70)

        form.addRow("제목", self.title_edit)
        form.addRow("중요도", self.priority_combo)
        form.addRow("마감기한", self.deadline_edit)
        form.addRow("알림 날짜", dt_widget)
        form.addRow("시간 선택", qt_widget)
        form.addRow("알림 설정", notify_widget)
        form.addRow("메모", self.memo_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("확인")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_datetime(self) -> datetime:
        return datetime.combine(self.alarm_date.date().toPyDate(), self.selected_time.toPyTime())

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
        self.time_label.setText(f"{self.selected_time.hour()}:{self.selected_time.minute():02d}")

    def set_previous_day_notify(self, hour: int) -> None:
        target = self.selected_datetime()
        notify_at = datetime.combine(target.date() - timedelta(days=1), dt_time(hour, 0))
        self.notify.setValue(max(0, int((target - notify_at).total_seconds() // 60)))
        self.update_notify_label()

    def value(self) -> dict:
        data = dict(self.item)
        if not data.get("id"):
            data["id"] = new_id("sc")
            data["created_at"] = now_iso()
            data["sort_order"] = 0
            data["usage_count"] = 0
        date_time = QDateTime(self.alarm_date.date(), self.selected_time)
        data.update({
            "title": self.title_edit.text().strip(),
            "priority": self.priority_combo.currentText(),
            "deadline": self.deadline_edit.date().toString("yyyy-MM-dd"),
            "datetime": date_time.toString(Qt.DateFormat.ISODate),
            "notify_before_minutes": self.notify.value(),
            "repeat": data.get("repeat", "none"),
            "memo": self.memo_edit.toPlainText(),
            "last_notified_at": data.get("last_notified_at", ""),
        })
        data.setdefault("completed", False)
        data.setdefault("completed_at", None)
        return data


# ── 완료 항목 다이얼로그 ──────────────────────────────────────────────────────

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
                pri = item.get("priority", "하")
                pc = PRIORITY_COLORS.get(pri, PRIORITY_COLORS["하"])
                badge = QLabel(pri)
                badge.setFixedSize(22, 18)
                badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
                badge.setStyleSheet(
                    f"background:{pc['badge_bg']};color:white;border-radius:3px;"
                    f"font-size:8pt;font-weight:800;"
                )
                rl.addWidget(badge)
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
            scroll.setFixedHeight(min(320, max(100, len(completed) * 38 + 16)))
            layout.addWidget(scroll)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
        self.resize(480, min(440, max(200, len(completed) * 38 + 130)))

    def _handle_toggle(self, item: dict, checked: bool, row: QWidget) -> None:
        if not checked and self.on_uncomplete:
            self.on_uncomplete(item)
            self.changed = True
            row.setStyleSheet("QWidget{background:#F0FDF4;border-radius:4px;}")
            for i in range(row.layout().count()):
                w = row.layout().itemAt(i).widget()
                if isinstance(w, QLabel) and "line-through" in (w.styleSheet() or ""):
                    w.setStyleSheet("color:#15803D;")


# ── 할 일(Todo) 목록 탭 ───────────────────────────────────────────────────────

class TodoListTab(QWidget):
    """1-컬럼 체크리스트 스타일 할 일 관리 탭."""

    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        self._sort_mode = "created"   # "created" | "deadline" | "priority"
        self._sort_asc = True

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        # ── 상단 검색 / 정렬 ──
        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("검색...")
        self.search.setFixedWidth(160)
        self.search.setFixedHeight(28)
        self.search.setStyleSheet("QLineEdit{padding:1px 6px;font-size:9pt;}")
        self.search.textChanged.connect(self.refresh)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["등록순", "기한순", "중요도순"])
        self.sort_combo.setFixedHeight(28)
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)

        self.order_combo = QComboBox()
        self.order_combo.addItems(["오름차순", "내림차순"])
        self.order_combo.setFixedHeight(28)
        self.order_combo.currentIndexChanged.connect(self._on_sort_changed)

        top.addWidget(self.search)
        top.addStretch(1)
        top.addWidget(self.sort_combo)
        top.addWidget(self.order_combo)
        outer.addLayout(top)

        # ── 스크롤 카드 영역 ──
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_content = QWidget()
        self._items_layout = QVBoxLayout(self._scroll_content)
        self._items_layout.setContentsMargins(0, 0, 0, 0)
        self._items_layout.setSpacing(4)
        self._items_layout.addStretch(1)
        self.scroll.setWidget(self._scroll_content)
        outer.addWidget(self.scroll, 1)

        # ── 하단 액션 바 ──
        bottom = QHBoxLayout()
        completed_btn = QPushButton("완료 항목 보기")
        completed_btn.clicked.connect(self.show_completed_items)
        clear_btn = QPushButton("완료 항목 지우기")
        clear_btn.clicked.connect(self.clear_completed_items)
        add_btn = QPushButton("+ 할 일")
        add_btn.clicked.connect(lambda: self.edit_item())
        bottom.addWidget(completed_btn)
        bottom.addWidget(clear_btn)
        bottom.addStretch(1)
        bottom.addWidget(add_btn)
        outer.addLayout(bottom)

    # ── 정렬 ────────────────────────────────────────────────────────────────

    def _on_sort_changed(self) -> None:
        mode_map = {0: "created", 1: "deadline", 2: "priority"}
        self._sort_mode = mode_map.get(self.sort_combo.currentIndex(), "created")
        self._sort_asc = (self.order_combo.currentIndex() == 0)
        self.refresh()

    def _sorted(self, items: list[dict]) -> list[dict]:
        reverse = not self._sort_asc
        if self._sort_mode == "deadline":
            def dl_key(item: dict) -> str:
                return item.get("deadline") or item.get("datetime", "")[:10] or "9999-99-99"
            return sorted(items, key=dl_key, reverse=reverse)
        if self._sort_mode == "priority":
            return sorted(items, key=lambda x: PRIORITY_ORDER.get(x.get("priority", "하"), 2), reverse=reverse)
        # created (default)
        return sorted(items, key=lambda x: x.get("created_at", ""), reverse=reverse)

    # ── 리프레시 ─────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        # 기존 카드 제거 (마지막 stretch 유지)
        while self._items_layout.count() > 1:
            child = self._items_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        q = self.search.text().strip().lower()
        pending = [i for i in self.main.data.get("schedules", []) if not i.get("completed", False)]
        visible = self._sorted(pending)

        inserted = 0
        for todo in visible:
            if q and q not in (todo.get("title", "") + " " + todo.get("memo", "")).lower():
                continue
            card = self._make_card(todo)
            self._items_layout.insertWidget(self._items_layout.count() - 1, card)
            inserted += 1

        if inserted == 0:
            msg = "할 일이 없어요! 🎉" if not q else "검색 결과가 없습니다."
            lbl = QLabel(msg)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color:#9CA3AF;font-size:10pt;padding:24px;")
            self._items_layout.insertWidget(0, lbl)

    # ── 카드 생성 ────────────────────────────────────────────────────────────

    def _make_card(self, item: dict) -> QWidget:
        priority = item.get("priority", "하")
        pc = PRIORITY_COLORS.get(priority, PRIORITY_COLORS["하"])

        card = QWidget()
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card.setObjectName("todoCard")
        card.setFixedHeight(48)

        h = QHBoxLayout(card)
        h.setContentsMargins(8, 4, 8, 4)
        h.setSpacing(8)

        # 체크박스
        cb = QCheckBox()
        cb.setChecked(False)
        cb.toggled.connect(lambda checked, i=item: self._on_check(i, checked))
        h.addWidget(cb)

        # 우선순위 배지
        badge = QLabel(priority)
        badge.setFixedSize(26, 20)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"background:{pc['badge_bg']};color:white;border-radius:4px;"
            f"font-size:8pt;font-weight:800;"
        )
        h.addWidget(badge)

        # 제목
        title_lbl = QLabel(item.get("title", "(제목 없음)"))
        title_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        title_lbl.setMinimumWidth(0)
        h.addWidget(title_lbl, 1)

        # 메모 미리보기
        memo = (item.get("memo") or "").strip()
        if memo:
            memo_lbl = QLabel((memo[:28] + "…") if len(memo) > 28 else memo)
            memo_lbl.setStyleSheet("color:#9CA3AF;font-size:8pt;")
            memo_lbl.setFixedWidth(90)
            h.addWidget(memo_lbl)

        # 마감기한 배지
        deadline = item.get("deadline", "")
        if deadline:
            try:
                dl_date = datetime.strptime(deadline, "%Y-%m-%d").date()
                today = datetime.now().date()
                days_left = (dl_date - today).days
                if days_left < 0:
                    dl_text, dl_color = f"D+{-days_left}", "#DC2626"
                elif days_left == 0:
                    dl_text, dl_color = "오늘", "#D97706"
                elif days_left <= 3:
                    dl_text, dl_color = f"D-{days_left}", "#D97706"
                else:
                    dl_text, dl_color = deadline[5:], "#6B7280"
                dl_lbl = QLabel(dl_text)
                dl_lbl.setStyleSheet(f"color:{dl_color};font-size:9pt;font-weight:700;min-width:40px;")
                dl_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                h.addWidget(dl_lbl)
            except Exception:
                pass

        # 수정/삭제
        h.addWidget(make_icon_button("edit", "수정", lambda checked=False, i=item: self.edit_item(i)))
        h.addWidget(make_icon_button("delete", "삭제", lambda checked=False, i=item: self.delete_item(i), True))

        # 배경색 (objectName selector 로 자식 위젯에 cascade 되지 않도록)
        if pc["bg"]:
            card.setStyleSheet(
                f"QWidget#todoCard{{background:{pc['bg']};border-radius:6px;"
                f"border:1px solid {pc['border']};}}"
            )
        else:
            card.setStyleSheet("QWidget#todoCard{border-radius:6px;}")
        return card

    # ── 이벤트 핸들러 ────────────────────────────────────────────────────────

    def _on_check(self, item: dict, checked: bool) -> None:
        if checked:
            item["completed"] = True
            item["completed_at"] = now_iso()
            self.main.save_data()

    def edit_item(self, item: dict | None = None) -> None:
        dialog = TodoDialog(item)
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
        self.main.data.get("schedules", []).remove(item)
        self.main.save_data()

    def show_completed_items(self) -> None:
        completed = [i for i in self.main.data.get("schedules", []) if i.get("completed")]
        dlg = CompletedItemsDialog(self, completed, on_uncomplete=self._uncomplete_item)
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
            self,
            "완료 항목 삭제",
            f"완료된 항목 {len(completed)}개를 영구 삭제합니다.\n복구할 수 없습니다. 계속하시겠습니까?",
            accent="#DC2626",
            yes_text="삭제",
            no_text="취소",
        ):
            self.main.data["schedules"] = [
                i for i in self.main.data.get("schedules", []) if not i.get("completed")
            ]
            self.main.save_data()

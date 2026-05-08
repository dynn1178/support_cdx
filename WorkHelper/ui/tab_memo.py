from __future__ import annotations

from datetime import datetime, time as dt_time, timedelta

from PyQt6.QtCore import QDateTime, QPoint, QTime, QTimer, Qt
from PyQt6.QtGui import QTextCharFormat, QColor, QPainter, QPen, QPolygon
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizeGrip,
    QSlider,
    QSpinBox,
    QTextEdit,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from app import config
from app.utils import new_id, now_iso, short_preview
from ui.common import GridPanel, SortControls, add_card_actions, apply_manual_reorder, apply_modern_dialog_style, bump_usage, make_card, make_icon_button, show_modern_warning


MEMO_COLORS = {
    "노랑": "#FFF9C4",
    "하늘": "#DFF3FF",
    "연두": "#E5F8D2",
    "분홍": "#FFE1EA",
    "흰색": "#FFFFFF",
}


WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]
REPEAT_LABELS = {"daily": "매일", "weekly": "매주", "monthly": "매월"}


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
        calendar = self.date.calendarWidget()
        today_format = QTextCharFormat()
        today_format.setBackground(QColor("#FFF3B0"))
        today_format.setForeground(QColor("#111827"))
        today_format.setFontWeight(700)
        calendar.setDateTextFormat(QDateTime.currentDateTime().date(), today_format)
        self.selected_time = current.time()
        self.time_label = QLabel()
        self.time_label.setObjectName("cardTitle")
        self.update_time_label()
        datetime_row = QHBoxLayout()
        datetime_row.setContentsMargins(0, 0, 0, 0)
        datetime_row.setSpacing(8)
        datetime_row.addWidget(self.date, 1)
        datetime_row.addWidget(self.time_label)
        datetime_widget = QWidget()
        datetime_widget.setLayout(datetime_row)
        quick_time_row = QHBoxLayout()
        quick_time_row.setContentsMargins(0, 0, 0, 0)
        quick_time_row.setSpacing(4)
        for hour in range(9, 19):
            btn = QPushButton(str(hour))
            btn.setFixedWidth(34)
            btn.clicked.connect(lambda checked=False, value=hour: self.set_time_hour(value))
            quick_time_row.addWidget(btn)
        for label, minutes in [("-10m", -10), ("+10m", 10), ("-30m", -30), ("+30m", 30)]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda checked=False, value=minutes: self.adjust_time(value))
            quick_time_row.addWidget(btn)
        quick_time_row.addStretch(1)
        quick_time_widget = QWidget()
        quick_time_widget.setLayout(quick_time_row)
        self.repeat = QComboBox()
        self.repeat.addItems(["없음", "매일", "매주", "매월"])
        repeat_map = {"none": "없음", "daily": "매일", "weekly": "매주", "monthly": "매월"}
        self.repeat.setCurrentIndex(max(self.repeat.findText(repeat_map.get(self.schedule.get("repeat", "none"), "없음")), 0))
        self.notify = QSpinBox()
        self.notify.setRange(0, 10080)
        self.notify.setValue(int(self.schedule.get("notify_before_minutes", 30)))
        notify_row = QHBoxLayout()
        notify_row.setContentsMargins(0, 0, 0, 0)
        notify_row.setSpacing(6)
        notify_row.addWidget(self.notify)
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

    def set_time_hour(self, hour: int) -> None:
        self.selected_time = QTime(hour, 0)
        self.update_time_label()

    def adjust_time(self, minutes: int) -> None:
        self.selected_time = self.selected_time.addSecs(minutes * 60)
        self.update_time_label()

    def update_time_label(self) -> None:
        hour = self.selected_time.hour()
        minute = self.selected_time.minute()
        self.time_label.setText(f"{hour}:{minute:02d}")

    def set_previous_day_notify(self, hour: int) -> None:
        target = self.selected_datetime()
        notify_at = datetime.combine(target.date() - timedelta(days=1), dt_time(hour, 0))
        self.notify.setValue(max(0, int((target - notify_at).total_seconds() // 60)))

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
        top = QHBoxLayout()
        top.addStretch(1)
        self.sort_controls = SortControls(self.refresh)
        top.addWidget(self.sort_controls)
        add_btn = QPushButton("+ 메모")
        add_btn.clicked.connect(lambda: self.edit_memo())
        self.grid = GridPanel(columns=2)
        layout.addLayout(top)
        layout.addWidget(self.grid, 1)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(add_btn)
        layout.addLayout(bottom)

    def refresh(self) -> None:
        cards = []
        source_items = self.main.data.get("memos", [])
        memos = self.sort_controls.sort_items(source_items, lambda item: item.get("title") or item.get("content", ""))
        if not self.sort_controls.is_manual():
            memos = sorted(memos, key=lambda item: not item.get("pinned"))
        for memo in memos:
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

    def show_sticker(self, memo: dict) -> None:
        bump_usage(memo)
        self.main.save_data()
        dialog = StickyMemoDialog(memo, self.main, self.refresh)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.destroyed.connect(lambda _obj=None, dlg=dialog: self.forget_sticker(dlg))
        self.sticky_windows.append(dialog)
        dialog.show()
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
        top = QHBoxLayout()
        top.addStretch(1)
        self.sort_controls = SortControls(self.refresh)
        top.addWidget(self.sort_controls)
        add_btn = QPushButton("+ 일정")
        add_btn.clicked.connect(lambda: self.edit_schedule())
        self.grid = GridPanel(columns=2)
        layout.addLayout(top)
        layout.addWidget(self.grid, 1)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(add_btn)
        layout.addLayout(bottom)

    def refresh(self) -> None:
        cards = []
        source_items = self.main.data.get("schedules", [])
        visible_items = self.sort_controls.sort_items(source_items, lambda item: item.get("title") or item.get("memo", ""))
        for schedule in visible_items:
            subtitle = f"{display_datetime(schedule.get('datetime', ''), schedule.get('repeat', 'none'))}\n{short_preview(schedule.get('memo', ''), 120)}"
            card = make_card(schedule.get("title", "(제목 없음)"), subtitle, card_size="b")
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

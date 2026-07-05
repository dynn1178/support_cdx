"""일정 관리(할 일/일정) 탭과 다이얼로그 (tab_memo.py에서 분리).
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


def display_datetime(value: str, repeat: str = "none") -> str:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return value.replace("T", " ")
    text = f"{parsed:%Y-%m-%d} {WEEKDAYS[parsed.weekday()]}요일 {parsed:%H:%M}"
    repeat_label = REPEAT_LABELS.get(repeat)
    return f"{text} ({repeat_label})" if repeat_label else text



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

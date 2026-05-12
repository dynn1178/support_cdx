from __future__ import annotations

import threading
import time
import calendar
from ctypes import wintypes
from datetime import date, datetime, timedelta
from typing import Any

from PyQt6.QtCore import QAbstractNativeEventFilter, QDate, QDateTime, QTime, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QIcon, QKeyEvent, QPixmap
from PyQt6.QtWidgets import QApplication, QCheckBox, QComboBox, QDateEdit, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QScrollArea, QSizePolicy, QSpinBox, QStackedWidget, QTabWidget, QTextEdit, QToolButton, QVBoxLayout, QWidget

from app import config
from app.date_tools import render_date_template
from app.hotkey_manager import HotkeyManager, USER32, WM_HOTKEY
from app.theme import apply_theme
from app.update_checker import check_just_updated, check_update_dialog
from app.utils import display_hotkey, normalize_hotkey
from ui.tab_clipboard import ClipboardTab
from ui.tab_calculator import CalculatorTab
from ui.tab_home import HomeTab
from ui.tab_image import ImageTab
from ui.tab_launcher import LauncherTab
from ui.tab_macro import MacroTab
from ui.tab_memo import MemoListTab, ScheduleListTab, TodoListTab
from ui.tab_misc import MiscTab, MouseHighlightOverlay
from ui.tab_phrase import PhraseTab
from ui.tab_settings import SettingsTab
from ui.tab_text_tools import TextToolsTab
from ui.common import apply_modern_dialog_style, ask_modern_question, bump_usage, fit_combo_to_contents, flash_taskbar, normalize_todo_groups, set_dialog_theme, show_modern_info, show_modern_warning


MINI_COPY_BUTTON_WIDTH = 64
MINI_COPY_BUTTON_HEIGHT = 26
CTRL_ONLY_VKS = {0x11, 0xA2, 0xA3}
ALT_ONLY_VKS = {0x12, 0xA4, 0xA5}
KEYBOARD_VKS = list(range(0x08, 0xFF))


class HotkeyEventFilter(QAbstractNativeEventFilter):
    def __init__(self, manager: HotkeyManager) -> None:
        super().__init__()
        self.manager = manager

    def nativeEventFilter(self, event_type, message):
        try:
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and self.manager.handle_message(msg.message, msg.wParam):
                return True, 0
        except Exception:
            pass
        return False, 0


class NumberPopupFilter(QAbstractNativeEventFilter):
    def __init__(self, popup: "NumberedTextPopup") -> None:
        super().__init__()
        self.popup = popup

    def nativeEventFilter(self, event_type, message):
        try:
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and 6201 <= int(msg.wParam) <= 6210:
                self.popup.choose((int(msg.wParam) - 6201) % 10)
                return True, 0
        except Exception:
            pass
        return False, 0


class NumberedTextPopup(QDialog):
    def __init__(self, parent: QWidget, title: str, items: list[dict], paste_callback) -> None:
        super().__init__(None)
        self.owner = parent
        self.items = items[:10]
        self.paste_callback = paste_callback
        self.filter = NumberPopupFilter(self)
        self.registered: list[int] = []
        self.previous_hwnd = 0
        self._closing = False
        self.setWindowTitle(title)
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedWidth(430)
        self.setStyleSheet(
            """
            QDialog { background: #EEF4FF; }
            QPushButton#miniCopyButton {
                padding: 0;
                min-width: 54px; max-width: 54px;
                min-height: 24px; max-height: 24px;
            }
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        container = QWidget()
        rows = QVBoxLayout(container)
        rows.setContentsMargins(0, 0, 0, 0)
        rows.setSpacing(3)
        if not self.items:
            rows.addWidget(QLabel("표시할 즐겨찾기가 없습니다."))
        for index, item in enumerate(self.items):
            rows.addWidget(self._row(index, item))
        rows.addStretch(1)
        scroll.setWidget(container)
        layout.addWidget(scroll)
        hint = QLabel("1~0 숫자키로 바로 복사")
        hint.setObjectName("mutedText")
        layout.addWidget(hint)
        self.setFixedHeight(58 + min(max(len(self.items), 1), 10) * 36)
        self.start_number_hotkeys()
        QTimer.singleShot(0, self.activate_popup)

    def _row(self, index: int, item: dict) -> QWidget:
        row = QWidget()
        row.setObjectName("card")
        row.setFixedHeight(33)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(6, 3, 6, 3)
        number = QLabel(str(index + 1) if index < 9 else "0")
        number.setObjectName("kbd")
        number.setAlignment(Qt.AlignmentFlag.AlignCenter)
        number.setFixedWidth(24)
        text = QLabel(item.get("text", "").replace("\n", " ")[:70])
        text.setToolTip(item.get("text", ""))
        text.setMinimumWidth(0)
        text.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        copy = QPushButton("복사")
        copy.setObjectName("miniCopyButton")
        copy.setFixedSize(54, 24)
        copy.clicked.connect(lambda checked=False, value=index: self.choose(value))
        layout.addWidget(number)
        layout.addWidget(text, 1)
        layout.addWidget(copy)
        return row

    def activate_popup(self) -> None:
        try:
            self.previous_hwnd = int(USER32.GetForegroundWindow())
        except Exception:
            self.previous_hwnd = 0
        cursor = QCursor.pos()
        screen = QApplication.screenAt(cursor) or QApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            x = min(max(cursor.x() + 12, area.left()), area.right() - self.width())
            y = min(max(cursor.y() + 12, area.top()), area.bottom() - self.height())
            self.move(x, y)
        self.raise_()
        self.activateWindow()
        self.setFocus(Qt.FocusReason.PopupFocusReason)

    def start_number_hotkeys(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        app.installNativeEventFilter(self.filter)
        hwnd = int(self.winId())
        for index, key in enumerate("1234567890"):
            hotkey_id = 6201 + index
            if USER32.RegisterHotKey(hwnd, hotkey_id, 0, ord(key)):
                self.registered.append(hotkey_id)

    def stop_number_hotkeys(self) -> None:
        hwnd = int(self.winId())
        for hotkey_id in self.registered:
            try:
                USER32.UnregisterHotKey(hwnd, hotkey_id)
            except Exception:
                pass
        self.registered.clear()
        app = QApplication.instance()
        if app is not None:
            try:
                app.removeNativeEventFilter(self.filter)
            except Exception:
                pass

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.text() in set("1234567890"):
            self.choose(("1234567890".index(event.text())))
            return
        super().keyPressEvent(event)

    def choose(self, index: int) -> None:
        if self._closing or not (0 <= index < len(self.items)):
            return
        self._closing = True
        item = self.items[index]
        bump_usage(item)
        text = item.get("text", "")
        try:
            self.owner.save_usage_data()
        except Exception:
            pass
        self.accept()
        self.paste_callback(text)

    def done(self, result: int) -> None:
        self.stop_number_hotkeys()
        super().done(result)
        self.restore_previous_window()

    def restore_previous_window(self) -> None:
        if not self.previous_hwnd:
            return
        try:
            USER32.SetForegroundWindow(self.previous_hwnd)
        except Exception:
            pass


class QuickMemoPopup(QDialog):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(None)
        self.setWindowTitle("빠른 메모")
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        layout = QVBoxLayout(self)
        self.text = QTextEdit()
        self.text.setPlaceholderText("메모를 입력하세요")
        self.sticky = QCheckBox("스티커로 띄우기")
        row = QHBoxLayout()
        save = QPushButton("저장")
        cancel = QPushButton("취소")
        save.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        row.addStretch(1)
        row.addWidget(save)
        row.addWidget(cancel)
        layout.addWidget(self.text)
        layout.addWidget(self.sticky)
        layout.addLayout(row)
        self.resize(340, 240)
        QTimer.singleShot(0, self.activate_popup)

    def activate_popup(self) -> None:
        cursor = QCursor.pos()
        screen = QApplication.screenAt(cursor) or QApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            x = min(max(cursor.x() + 12, area.left()), area.right() - self.width())
            y = min(max(cursor.y() + 12, area.top()), area.bottom() - self.height())
            self.move(x, y)
        self.raise_()
        self.activateWindow()
        self.text.setFocus(Qt.FocusReason.PopupFocusReason)


class QuickActionPopup(QDialog):
    """Alt 더블 탭 시 나타나는 빠른 작업 팝업 (할 일 / 메모 / 타이머 3탭)."""

    def __init__(self, owner: "MainWindow") -> None:
        super().__init__(None)
        self.owner = owner
        self.setWindowTitle("빠른 작업")
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        apply_modern_dialog_style(self)
        self.setObjectName("quickActionDialog")
        self.setFixedWidth(460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.tab_widget = QTabWidget()
        self._build_todo_tab()
        self._build_memo_tab()
        self._build_timer_tab()
        layout.addWidget(self.tab_widget)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel_btn = QPushButton("닫기")
        cancel_btn.clicked.connect(self.reject)
        self.save_btn = QPushButton("저장")
        self.save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        self.resize(460, 320)
        self.setStyleSheet(
            self.styleSheet()
            + """
            QDialog#quickActionDialog { background: #F8FAFC; }
            QTabWidget::pane { border: 1px solid #E5E7EB; border-radius: 8px; background: #FFFFFF; }
            QTabBar::tab { padding: 6px 12px; }
            QFormLayout { background: transparent; }
            """
        )
        QTimer.singleShot(0, self._activate)

    def _on_tab_changed(self, idx: int) -> None:
        self.save_btn.setText("시작" if idx == 2 else "저장")

    # ── 탭 1 : 할 일 ───────────────────────────────────────────────────────

    def _build_todo_tab(self) -> None:
        tab = QWidget()
        fl = QFormLayout(tab)
        fl.setContentsMargins(12, 12, 12, 10)
        fl.setVerticalSpacing(8)
        fl.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        fl.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        fl.setHorizontalSpacing(12)
        fl.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # 그룹 콤보
        self.todo_group = QComboBox()
        groups = normalize_todo_groups(self.owner.data.get("todo_groups", ["그룹 1", "그룹 2", "그룹 3"]))
        for g in groups:
            self.todo_group.addItem(g)
        if self.todo_group.count() == 0:
            self.todo_group.addItem("그룹 1")
        fit_combo_to_contents(self.todo_group, 140)

        # 제목
        self.todo_title = QLineEdit()
        self.todo_title.setPlaceholderText("할 일 제목...")

        self.todo_priority_combo = QComboBox()
        self.todo_priority_combo.addItems(["상", "중", "하"])
        self.todo_priority_combo.setCurrentText("하")
        fit_combo_to_contents(self.todo_priority_combo, 88)

        # 날짜: QDateEdit with calendar popup + today highlight
        from PyQt6.QtGui import QTextCharFormat, QColor
        self.todo_date = QDateEdit()
        self.todo_date.setCalendarPopup(True)
        self.todo_date.setDate(QDate.currentDate())
        self.todo_date.setMinimumWidth(130)
        cal = self.todo_date.calendarWidget()
        today_fmt = QTextCharFormat()
        today_fmt.setBackground(QColor("#FFF3B0"))
        today_fmt.setForeground(QColor("#111827"))
        today_fmt.setFontWeight(700)
        cal.setDateTextFormat(QDate.currentDate(), today_fmt)

        # 시간: hour + min combo
        self.todo_hour_combo = QComboBox()
        for h in range(24):
            self.todo_hour_combo.addItem(f"{h:02d}시")
        self.todo_hour_combo.setCurrentIndex(9)
        fit_combo_to_contents(self.todo_hour_combo, 72)

        self.todo_min_combo = QComboBox()
        for m in range(0, 60, 10):
            self.todo_min_combo.addItem(f"{m:02d}분")
        fit_combo_to_contents(self.todo_min_combo, 72)

        dt_row = QHBoxLayout()
        dt_row.setContentsMargins(0, 0, 0, 0)
        dt_row.setSpacing(5)
        dt_row.addWidget(self.todo_date)
        dt_row.addWidget(self.todo_hour_combo)
        dt_row.addWidget(self.todo_min_combo)
        dt_row.addStretch(1)
        dt_widget = QWidget()
        dt_widget.setLayout(dt_row)

        # 알림 콤보
        self.todo_notify_combo = QComboBox()
        self.todo_notify_combo.addItems(["알림 없음", "10분 전", "30분 전", "1시간 전"])
        self.todo_notify_combo.setCurrentIndex(2)
        fit_combo_to_contents(self.todo_notify_combo, 118)

        self.todo_repeat_combo = QComboBox()
        self.todo_repeat_combo.addItems(["없음", "매일", "매주", "매월", "매년"])
        fit_combo_to_contents(self.todo_repeat_combo, 130)
        self.todo_repeat_combo.currentTextChanged.connect(self._on_quick_todo_repeat_changed)

        weekday_widget = QWidget()
        wd_row = QHBoxLayout(weekday_widget)
        wd_row.setContentsMargins(0, 0, 0, 0)
        wd_row.setSpacing(6)
        self.todo_weekday_checks: list[QCheckBox] = []
        for day_name in ["월", "화", "수", "목", "금", "토", "일"]:
            cb = QCheckBox(day_name)
            self.todo_weekday_checks.append(cb)
            wd_row.addWidget(cb)
        wd_row.addStretch(1)
        self.todo_weekday_widget = weekday_widget
        self.todo_weekday_widget.setVisible(False)

        fl.addRow("그룹", self.todo_group)
        fl.addRow("중요도", self.todo_priority_combo)
        fl.addRow("제목", self.todo_title)
        fl.addRow("일정", dt_widget)
        fl.addRow("반복", self.todo_repeat_combo)
        fl.addRow("", self.todo_weekday_widget)
        fl.addRow("알림", self.todo_notify_combo)
        self.tab_widget.addTab(tab, "할 일")

    def _on_quick_todo_repeat_changed(self, text: str) -> None:
        self.todo_weekday_widget.setVisible(text == "매주")

    # ── 탭 2 : 메모 ───────────────────────────────────────────────────────

    def _build_memo_tab(self) -> None:
        tab = QWidget()
        vl = QVBoxLayout(tab)
        vl.setContentsMargins(12, 12, 12, 10)
        vl.setSpacing(8)
        self.memo_text = QTextEdit()
        self.memo_text.setPlaceholderText("메모를 입력하세요...")
        self.memo_text.setFixedHeight(100)
        vl.addWidget(self.memo_text)
        self.memo_sticky = QCheckBox("스티커로 띄우기")
        vl.addWidget(self.memo_sticky)
        vl.addStretch(1)
        self.tab_widget.addTab(tab, "메모")

    # ── 탭 3 : 타이머 ──────────────────────────────────────────────────────

    def _build_timer_tab(self) -> None:
        tab = QWidget()
        fl = QFormLayout(tab)
        fl.setContentsMargins(12, 12, 12, 10)
        fl.setVerticalSpacing(8)
        fl.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        fl.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        fl.setHorizontalSpacing(12)
        fl.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.timer_duration_combo = QComboBox()
        for minutes, label in [(5, "5분"), (10, "10분"), (15, "15분"), (20, "20분"),
                                (30, "30분"), (45, "45분"), (60, "1시간"),
                                (90, "1시간 30분"), (120, "2시간")]:
            self.timer_duration_combo.addItem(label, minutes)
        self.timer_duration_combo.setCurrentIndex(4)  # 30분 기본
        fit_combo_to_contents(self.timer_duration_combo, 120)

        self.timer_mode_combo = QComboBox()
        self.timer_mode_combo.addItems(["시간", "특정 시간"])
        fit_combo_to_contents(self.timer_mode_combo, 120)
        self.timer_mode_combo.currentTextChanged.connect(self._on_quick_timer_mode_changed)

        from PyQt6.QtGui import QTextCharFormat, QColor
        self.timer_exact_date = QDateEdit()
        self.timer_exact_date.setCalendarPopup(True)
        self.timer_exact_date.setDate(QDate.currentDate())
        self.timer_exact_date.setMinimumWidth(130)
        exact_cal = self.timer_exact_date.calendarWidget()
        exact_fmt = QTextCharFormat()
        exact_fmt.setBackground(QColor("#FFF3B0"))
        exact_fmt.setForeground(QColor("#111827"))
        exact_fmt.setFontWeight(700)
        exact_cal.setDateTextFormat(QDate.currentDate(), exact_fmt)
        self.timer_exact_hour = QComboBox()
        for h in range(24):
            self.timer_exact_hour.addItem(f"{h:02d}시")
        self.timer_exact_hour.setCurrentIndex(datetime.now().hour)
        fit_combo_to_contents(self.timer_exact_hour, 72)
        self.timer_exact_min = QComboBox()
        for m in range(0, 60, 10):
            self.timer_exact_min.addItem(f"{m:02d}분")
        fit_combo_to_contents(self.timer_exact_min, 72)

        exact_row = QHBoxLayout()
        exact_row.setContentsMargins(0, 0, 0, 0)
        exact_row.setSpacing(5)
        exact_row.addWidget(self.timer_exact_date)
        exact_row.addWidget(self.timer_exact_hour)
        exact_row.addWidget(self.timer_exact_min)
        exact_row.addStretch(1)
        self.timer_exact_widget = QWidget()
        self.timer_exact_widget.setLayout(exact_row)
        self.timer_exact_widget.setVisible(False)

        self.timer_note = QLineEdit()
        self.timer_note.setPlaceholderText("타이머 메모 (선택 사항)...")

        action_lbl = QLabel("알림")
        action_lbl.setObjectName("mutedText")

        self.timer_duration_label = QLabel("시간")
        self.timer_exact_label = QLabel("시간")
        fl.addRow("방식", self.timer_mode_combo)
        fl.addRow(self.timer_duration_label, self.timer_duration_combo)
        fl.addRow(self.timer_exact_label, self.timer_exact_widget)
        fl.addRow("메모", self.timer_note)
        fl.addRow("완료 시", action_lbl)
        self.timer_exact_label.setVisible(False)
        self.tab_widget.addTab(tab, "타이머")

    def _on_quick_timer_mode_changed(self, text: str) -> None:
        exact = text == "특정 시간"
        self.timer_duration_combo.setVisible(not exact)
        self.timer_exact_widget.setVisible(exact)
        self.timer_duration_label.setVisible(not exact)
        self.timer_exact_label.setVisible(exact)

    # ── 저장 / 팝업 공통 ──────────────────────────────────────────────────

    def _activate(self) -> None:
        cursor = QCursor.pos()
        screen = QApplication.screenAt(cursor) or QApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            x = min(max(cursor.x() + 12, area.left()), area.right() - self.width())
            y = min(max(cursor.y() + 12, area.top()), area.bottom() - self.height())
            self.move(x, y)
        self.raise_()
        self.activateWindow()
        line_edit = self.tab_widget.currentWidget().findChild(QLineEdit)
        if line_edit:
            line_edit.setFocus(Qt.FocusReason.PopupFocusReason)

    def _on_save(self) -> None:
        idx = self.tab_widget.currentIndex()
        if idx == 0:
            self._save_todo()
        elif idx == 1:
            self._save_memo()
        else:
            self._save_timer()

    def _save_todo(self) -> None:
        from app.utils import new_id, now_iso
        from datetime import datetime as py_datetime, time as py_time
        title = self.todo_title.text().strip()
        if not title:
            show_modern_warning(self, "입력 확인", "제목을 입력해주세요.")
            return
        selected_date = self.todo_date.date().toPyDate()
        hour = self.todo_hour_combo.currentIndex()
        minute = int(self.todo_min_combo.currentText().replace("분", ""))
        alarm_dt = py_datetime.combine(selected_date, py_time(hour, minute))
        notify_map = {"알림 없음": 0, "10분 전": 10, "30분 전": 30, "1시간 전": 60}
        notify_mins = notify_map.get(self.todo_notify_combo.currentText(), 0)
        repeat_map = {"없음": "none", "매일": "daily", "매주": "weekly", "매월": "monthly", "매년": "yearly"}
        repeat_val = repeat_map.get(self.todo_repeat_combo.currentText(), "none")
        group = self.todo_group.currentText()
        item = {
            "id": new_id("sc"),
            "title": title,
            "group": group,
            "priority": self.todo_priority_combo.currentText() or "하",
            "deadline": alarm_dt.strftime("%Y-%m-%d"),
            "datetime": alarm_dt.isoformat(timespec="seconds"),
            "notify_before_minutes": notify_mins,
            "repeat": repeat_val,
            "completed": False,
            "completed_at": None,
            "memo": "",
            "last_notified_at": "",
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "sort_order": len(self.owner.data.setdefault("schedules", [])),
            "usage_count": 0,
        }
        if repeat_val == "weekly":
            item["repeat_weekdays"] = [i for i, cb in enumerate(self.todo_weekday_checks) if cb.isChecked()] or [alarm_dt.weekday()]
        self.owner.data["schedules"].append(item)
        self.owner.save_data()
        self.todo_title.clear()
        show_modern_info(self, "저장 완료", f"'{title}' 이(가) 할 일에 추가되었습니다.")

    def _save_memo(self) -> None:
        from app.utils import new_id, now_iso
        content = self.memo_text.toPlainText().strip()
        if not content:
            show_modern_warning(self, "입력 확인", "메모를 입력해주세요.")
            return
        title = content.splitlines()[0][:30] or "빠른 메모"
        memo = {
            "id": new_id("mm"),
            "title": title,
            "content": content,
            "pinned": False,
            "always_on_top": True,
            "background": "노랑",
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "sort_order": len(self.owner.data.setdefault("memos", [])),
            "usage_count": 0,
        }
        self.owner.data["memos"].append(memo)
        self.owner.save_data()
        if self.memo_sticky.isChecked():
            memo["sticker_open"] = True
            self.owner.tabs[6].show_sticker(memo)
        self.memo_text.clear()
        self.reject()

    def _save_timer(self) -> None:
        if self.timer_mode_combo.currentText() == "특정 시간":
            from datetime import datetime as py_datetime, time as py_time
            minute = int(self.timer_exact_min.currentText().replace("분", ""))
            target = py_datetime.combine(
                self.timer_exact_date.date().toPyDate(),
                py_time(self.timer_exact_hour.currentIndex(), minute),
            )
            seconds = int((target - py_datetime.now()).total_seconds())
            if seconds <= 0:
                show_modern_warning(self, "설정 확인", "지정 시간이 현재 시간보다 이전입니다.")
                return
            duration_label = target.strftime("%Y-%m-%d %H:%M")
        else:
            minutes = self.timer_duration_combo.currentData()
            if not minutes:
                return
            seconds = int(minutes) * 60
            duration_label = self.timer_duration_combo.currentText()
        note = self.timer_note.text().strip()
        timer_tab = next((tab for tab in getattr(self.owner, "tabs", []) if hasattr(tab, "start_quick_timer")), None)
        if timer_tab is None:
            show_modern_warning(self, "타이머 시작 실패", "타이머 탭을 찾을 수 없습니다.")
            return
        timer_tab.start_quick_timer(seconds, note, duration_label)
        self.accept()
        show_modern_info(self.owner, "타이머 시작", f"{duration_label} 타이머가 시작되었습니다.")


class MainWindow(QMainWindow):
    CLIPBOARD_POPUP_HOTKEY_LABEL = "Ctrl+Shift+V"
    ctrl_double_tapped = pyqtSignal()
    alt_double_tapped = pyqtSignal()
    hotstring_expand_requested = pyqtSignal(str, str, str)
    HOME_TIPS = [
        "상용구에 자주 쓰는 답변을 등록하고 단축키를 지정하면 상담 문구를 바로 붙여넣을 수 있습니다.",
        "코드 스니펫에는 자주 쓰는 SQL이나 Python 조각을 저장해두고 필요한 순간 단축키로 복사해보세요.",
        "핫스트링은 gg. → google.com처럼 입력 문자열을 대체 텍스트로 바꿔 흐름을 크게 끊지 않고 문구를 불러올 수 있습니다.",
        "바로가기에 업무 사이트와 파일 경로를 등록하면 로그인 정보 복사와 열기를 한 번에 처리할 수 있습니다.",
        "컨닝페이퍼에는 참고 이미지나 업무 절차 캡처를 넣고 단축키로 즉시 열어볼 수 있습니다.",
        "매크로 녹화는 반복 클릭과 키 입력을 저장해두었다가 단축키로 다시 실행할 때 유용합니다.",
        "클립보드 미니팝업은 최근 복사한 내용을 빠르게 다시 꺼낼 때 좋습니다. Ctrl 두 번 설정도 활용해보세요.",
        "제목 생성은 날짜 토큰을 넣어 리포트명이나 파일명을 일정한 규칙으로 만드는 데 쓸 수 있습니다.",
        "계산기에서는 수식 계산과 날짜 계산을 한 화면 안에서 탭으로 나눠 처리할 수 있습니다.",
        "텍스트 변환은 URL 인코딩, UTM 분해, 줄바꿈과 따옴표 목록 변환을 빠르게 처리합니다.",
        "컬러 도구는 화면에서 색을 찍고 HEX, RGB, HSL 값을 바로 복사할 때 유용합니다.",
        "이모지 도구는 자주 쓴 이모지를 사용 횟수 순으로 다시 보여줍니다.",
        "빠른 메모는 Alt 두 번으로 마우스 근처에 띄워 즉시 기록할 수 있습니다.",
        "메모와 일정은 업무 중 놓치기 쉬운 체크 사항을 작게 고정하거나 알림으로 관리할 때 편합니다.",
        "프리셋을 나눠두면 업무 상황별 상용구, 바로가기, 매크로 묶음을 빠르게 전환할 수 있습니다.",
        "테마 설정으로 밝은 화면, 어두운 화면, 고대비 화면을 작업 환경에 맞게 바꿔보세요.",
        "다른 프로그램 단축키와 겹칠 때는 왼쪽 하단 단축키 ON/OFF 버튼으로 잠시 꺼둘 수 있습니다.",
    ]

    def __init__(self, app) -> None:
        super().__init__()
        config.ensure_data_files()
        self.app = app
        self._just_updated = False
        self.version = config.read_version()
        self.settings = config.load_settings()
        self.template_index = int(self.settings.get("active_preset", 1))
        self.data = config.load_template(self.template_index)
        self.data["settings"] = self.settings
        self.hotkeys = HotkeyManager()
        self.ctrl_listener_stop = threading.Event()
        self.ctrl_listener_thread = None
        self.key_listener_stop = threading.Event()
        self.key_listener_thread = None
        self.hotstring_listener = None
        self.hotstring_buffer = ""
        self.hotstring_busy = False
        self.mouse_highlight_overlay = None
        self._quick_action_popup: QuickActionPopup | None = None
        self.hotkey_event_filter = HotkeyEventFilter(self.hotkeys)
        self.app.installNativeEventFilter(self.hotkey_event_filter)
        self._last_ctrl_release = 0.0
        self._last_alt_release = 0.0
        self._ctrl_combo_used = False
        self._alt_combo_used = False
        self._home_tip_index = 0
        self.ctrl_double_tapped.connect(self.show_clipboard_popup)
        self.alt_double_tapped.connect(self.show_quick_action_popup)
        self.hotstring_expand_requested.connect(self.expand_hotstring)
        self._notified_schedule_ids: set[str] = set()
        self._quick_timers: list = []
        self.setWindowTitle(config.APP_NAME)
        icon2_path = config.BASE_DIR / "icon2.png" if (config.BASE_DIR / "icon2.png").exists() else config.RESOURCE_DIR / "icon2.png"
        icon_path = icon2_path if icon2_path.exists() else config.APP_ICON_PATH if config.APP_ICON_PATH.exists() else config.BUNDLED_ICON_PATH
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self._build_ui()
        self.hotkeys.set_hwnd(int(self.winId()))
        self.apply_current_settings()
        self.refresh_all_tabs()
        self.register_hotkeys()
        self.start_modifier_double_tap_listener()
        self.start_hotstring_listener()
        self.schedule_timer = QTimer(self)
        self.schedule_timer.timeout.connect(self.check_schedules)
        self.schedule_timer.start(60_000)
        self.tip_timer = QTimer(self)
        self.tip_timer.timeout.connect(self.rotate_home_tip)
        self.tip_timer.start(300_000)
        QTimer.singleShot(800, self._show_just_updated_notice)
        QTimer.singleShot(1500, self.check_update_on_startup)
        QTimer.singleShot(300, self.restore_open_stickers)

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(0)
        shell = QWidget()
        shell.setObjectName("appShell")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        body = QWidget()
        body.setObjectName("contentArea")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        sidebar = QWidget()
        sidebar.setObjectName("sideBar")
        sidebar.setFixedWidth(180)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(0, 0, 0, 0)
        side.setSpacing(0)
        side_header = QWidget()
        side_header.setObjectName("sideHeader")
        side_header.setFixedHeight(78)
        side_header_layout = QHBoxLayout(side_header)
        side_header_layout.setContentsMargins(14, 12, 14, 10)
        side_header_layout.setSpacing(10)
        brand_icon = QLabel()
        brand_icon.setFixedSize(34, 34)
        icon2_path = config.BASE_DIR / "icon2.png" if (config.BASE_DIR / "icon2.png").exists() else config.RESOURCE_DIR / "icon2.png"
        icon_path = icon2_path if icon2_path.exists() else config.APP_ICON_PATH if config.APP_ICON_PATH.exists() else config.BUNDLED_ICON_PATH
        if icon_path.exists():
            brand_icon.setPixmap(QPixmap(str(icon_path)).scaled(34, 34, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        brand_text = QLabel("6PM\nAssistant")
        brand_text.setObjectName("windowTitle")
        side_header_layout.addWidget(brand_icon)
        side_header_layout.addWidget(brand_text, 1)
        side.addWidget(side_header)

        nav = QWidget()
        nav_layout = QVBoxLayout(nav)
        nav_layout.setContentsMargins(6, 6, 6, 6)
        nav_layout.setSpacing(2)
        body_layout.addWidget(sidebar)

        content = QWidget()
        content.setObjectName("contentArea")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        screen_header = QWidget()
        screen_header.setObjectName("screenHeader")
        screen_header.setFixedHeight(78)
        screen_head = QHBoxLayout(screen_header)
        screen_head.setContentsMargins(20, 16, 20, 16)
        title_col = QVBoxLayout()
        title_col.setSpacing(3)
        self.screen_title = QLabel()
        self.screen_title.setObjectName("screenTitle")
        self.screen_subtitle = QLabel()
        self.screen_subtitle.setObjectName("screenSubtitle")
        self.screen_subtitle.setWordWrap(True)
        title_col.addWidget(self.screen_subtitle)
        screen_head.addLayout(title_col, 1)
        tip_nav_col = QVBoxLayout()
        tip_nav_col.setContentsMargins(0, 0, 0, 0)
        tip_nav_col.setSpacing(0)
        tip_nav_col.addStretch(1)
        tip_nav_row = QHBoxLayout()
        tip_nav_row.setContentsMargins(0, 0, 0, 0)
        tip_nav_row.setSpacing(2)
        self.prev_tip_button = QToolButton()
        self.prev_tip_button.setText("‹")
        self.prev_tip_button.setToolTip("이전 팁")
        self.prev_tip_button.setObjectName("tipNavButton")
        self.prev_tip_button.setFixedSize(30, 30)
        self.prev_tip_button.clicked.connect(self.prev_home_tip)
        self.next_tip_button = QToolButton()
        self.next_tip_button.setText("›")
        self.next_tip_button.setToolTip("다음 팁")
        self.next_tip_button.setObjectName("tipNavButton")
        self.next_tip_button.setFixedSize(30, 30)
        self.next_tip_button.clicked.connect(self.next_home_tip)
        tip_nav_row.addWidget(self.prev_tip_button)
        tip_nav_row.addWidget(self.next_tip_button)
        tip_nav_col.addLayout(tip_nav_row)
        screen_head.addLayout(tip_nav_col)
        content_layout.addWidget(screen_header)

        self.stack = QStackedWidget()
        self.clipboard_tab = ClipboardTab(self)
        self.tabs = [
            HomeTab(self),          # 0 홈
            PhraseTab(self),        # 1 상용구
            LauncherTab(self),      # 2 바로가기
            self.clipboard_tab,     # 3 클립보드
            ImageTab(self),         # 4 컨닝페이퍼
            TodoListTab(self),      # 5 일정 관리
            MemoListTab(self),      # 6 메모
            MacroTab(self),         # 7 매크로
            CalculatorTab(self),    # 8 계산기
            TextToolsTab(self),     # 9 텍스트 변환
            MiscTab(self),          # 10 피커/기타
            SettingsTab(self),      # 11 설정
        ]
        for tab in self.tabs:
            self.stack.addWidget(tab)
        content_layout.addWidget(self.stack, 1)

        names = ["홈", "상용구", "바로가기", "클립보드", "캡처 도구", "일정 관리", "메모", "매크로", "계산기", "텍스트 변환", "피커 · 기타", "설정"]
        self.buttons: list[QToolButton] = []
        for i, name in enumerate(names):
            button = QToolButton()
            button.setObjectName("navButton")
            button.setText(name)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            button.setCheckable(True)
            button.setFixedHeight(40)
            button.setMinimumWidth(150)
            button.clicked.connect(lambda checked=False, index=i: self.set_tab(index))
            self.buttons.append(button)
            nav_layout.addWidget(button)
        nav_layout.addStretch(1)
        side.addWidget(nav, 1)

        side_footer = QWidget()
        side_footer.setObjectName("sideFooter")
        side_footer_layout = QVBoxLayout(side_footer)
        side_footer_layout.setContentsMargins(12, 10, 12, 10)
        self.hotkey_toggle = QPushButton()
        self.hotkey_toggle.clicked.connect(self.toggle_hotkeys_enabled)
        side_footer_layout.addWidget(self.hotkey_toggle)
        side.addWidget(side_footer)

        body_layout.addWidget(content, 1)
        shell_layout.addWidget(body, 1)
        root.addWidget(shell)
        self.setCentralWidget(central)
        self.set_tab(0)
        self.update_hotkey_toggle_button()

    def set_tab(self, index: int) -> None:
        if hasattr(self, "stack") and self.stack.currentIndex() == 11 and index != 11:
            settings_tab = self.tabs[11]
            if hasattr(settings_tab, "is_dirty") and settings_tab.is_dirty():
                changes = settings_tab.changed_settings_summary() if hasattr(settings_tab, "changed_settings_summary") else []
                detail = "\n".join(changes[:8])
                if len(changes) > 8:
                    detail += f"\n- 외 {len(changes) - 8}개"
                message = "저장되지 않은 항목이 있습니다. 저장하시겠습니까?"
                if detail:
                    message = f"변경된 내역\n{detail}\n\n{message}"
                if ask_modern_question(self, "변경 내역 저장", message, None, "저장", "취소"):
                    if settings_tab.save_settings() is False:
                        return
                elif hasattr(settings_tab, "discard_changes"):
                    QTimer.singleShot(0, settings_tab.discard_changes)
        self.stack.setCurrentIndex(index)
        for i, button in enumerate(self.buttons):
            button.setChecked(i == index)
        subtitles = [
            "🔹" + self.numbered_home_tip(),                                                                                                                                                             # 0 홈
            f"🔹자주 쓰는 문구나 코드, 날짜 형식, 핫스트링을 저장하고 쉽게 불러오세요.\n💡즐겨찾기(★)로 상용구 호출도 가능합니다. (기본 단축키 {display_hotkey(self.settings.get('phrase_popup_hotkey')) or 'Ctrl+;'})",  # 1 상용구
            "🔹자주 찾는 사이트나 폴더, 파일을 단축키로 바로 불러올 수 있어요.\n💡사이트를 불러오면 함께 저장한 아이디와 비밀번호를 복사해줘요! (개인 계정은 보안상 사용하지 마세요)",                             # 2 바로가기
            "🔹복사했던 항목들을 보관하고 불러옵니다.\n💡Ctrl을 두 번 누르면 복사했던 이력을 미니 팝업으로 바로 확인하고 가져올 수 있어요",                                                                     # 3 클립보드
            "🔹원하는 이미지를 파일, URL, 캡처 방식으로 저장하고 불러올 수 있어요\n💡자주 참고하는 자료를 등록해보세요. (단축키, 조직도, KPI 등)",                                                              # 4 컨닝페이퍼
            "🔹할 일을 체크리스트로 관리합니다.\n💡우선순위·마감기한·알림을 설정하고, 완료 체크로 목록에서 제거하세요.",                                                                                           # 5 일정 관리
            "🔹메모를 저장할 수 있어요.\n💡Alt를 두 번 누르면 할 일/메모/일정을 빠르게 등록할 수 있어요.",                                                                                                        # 6 메모
            "🔹마우스와 키보드 동작을 녹화하고 그대로 반복&재생시킬 수 있어요.\n💡편집 화면에서 직접 편집하는 것도 가능해요.",                                                                                    # 7 매크로
            "🔹수식과 날짜를 계산하고 결과를 복사합니다.",                                                                                                                                                    # 8 계산기
            "🔹URL, UTM, 줄바꿈, 따옴표 변환을 처리합니다.",                                                                                                                                                  # 9 텍스트 변환
            "🔹컬러, 마우스 하이라이트, 이모지를 관리합니다.",                                                                                                                                                # 10 피커/기타
            "🔹일반, 단축키, 테마 옵션을 설정합니다.",                                                                                                                                                       # 11 설정
        ]
        subtitle = subtitles[index]
        if index == 0:
            subtitle = self.numbered_home_tip()
        self.prev_tip_button.setVisible(index == 0)
        self.next_tip_button.setVisible(index == 0)
        if "\n" in subtitle:
            first, second = subtitle.split("\n", 1)
            subtitle = f'<p style="margin:0 0 6px 0">{first}</p><p style="margin:0">{second}</p>'
        self.screen_subtitle.setText(subtitle)

    def rotate_home_tip(self) -> None:
        self.next_home_tip()

    def numbered_home_tip(self) -> str:
        return f"{self._home_tip_index + 1}. {self.HOME_TIPS[self._home_tip_index]}"

    def prev_home_tip(self) -> None:
        self._home_tip_index = (self._home_tip_index - 1) % len(self.HOME_TIPS)
        if self.stack.currentIndex() == 0:
            self.set_tab(0)

    def next_home_tip(self) -> None:
        self._home_tip_index = (self._home_tip_index + 1) % len(self.HOME_TIPS)
        if self.stack.currentIndex() == 0:
            self.set_tab(0)

    def apply_current_settings(self) -> None:
        settings = self.settings
        window = settings.get("window", {})
        self.setFixedSize(int(window.get("width", 900)), int(window.get("height", 580)))
        flags = self.windowFlags()
        if window.get("always_on_top"):
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        set_dialog_theme(settings.get("theme", "light"))
        apply_theme(self.app, settings.get("theme", "light"))

    def save_data(self) -> None:
        self.data["settings"] = self.settings
        config.save_template(self.template_index, self.data)
        config.save_settings(self.settings)
        self.register_hotkeys()
        self.refresh_all_tabs()

    def save_usage_data(self) -> None:
        config.save_template(self.template_index, self.data)
        self.refresh_home_tab()

    def refresh_all_tabs(self) -> None:
        for tab in self.tabs:
            if hasattr(tab, "refresh"):
                tab.refresh()

    def refresh_home_tab(self) -> None:
        if not hasattr(self, "tabs") or not self.tabs:
            return
        home = self.tabs[0]
        if hasattr(home, "refresh"):
            home.refresh()

    def change_template(self, index: int) -> None:
        config.save_template(self.template_index, self.data)
        self.template_index = index
        self.settings["active_preset"] = index
        config.save_settings(self.settings)
        self.data = config.load_template(index)
        self.data["settings"] = self.settings
        self.register_hotkeys()
        self.refresh_all_tabs()

    def hotkey_entries(self, candidate: dict | None = None, original: dict | None = None) -> list[tuple[str, dict]]:
        entries: list[tuple[str, dict]] = []
        for collection, label in [
            ("phrases", "상용구"),
            ("snippets", "코드"),
            ("title_templates", "제목 생성"),
            ("launchers", "바로가기"),
            ("images", "캡처 도구"),
            ("macros", "매크로"),
        ]:
            for item in self.data.get(collection, []):
                if original is not None and item is original:
                    continue
                hotkey = item.get("hotkey")
                if hotkey:
                    entries.append((f"{label}: {item.get('name', '(이름 없음)')}", hotkey))
        if candidate and candidate.get("hotkey"):
            entries.append((f"새 항목: {candidate.get('name', '(이름 없음)')}", candidate["hotkey"]))
        popup_hotkey = self.settings.get("clipboard_popup_hotkey")
        if popup_hotkey and not self.settings.get("clipboard_popup_double_ctrl", True):
            entries.append(("클립보드 미니팝업", popup_hotkey))
        quick_memo_hotkey = self.settings.get("quick_memo_hotkey")
        if quick_memo_hotkey and not self.settings.get("quick_memo_double_alt", True):
            entries.append(("빠른 메모", quick_memo_hotkey))
        phrase_popup_hotkey = self.settings.get("phrase_popup_hotkey")
        if phrase_popup_hotkey:
            entries.append(("상용구 미니팝업", phrase_popup_hotkey))
        steel_cut_hotkey = self.settings.get("steel_cut_hotkey")
        if steel_cut_hotkey:
            entries.append(("캡처 단축키", steel_cut_hotkey))
        screen_draw_hotkey = self.settings.get("screen_draw_hotkey")
        if screen_draw_hotkey:
            entries.append(("화면 그리기", screen_draw_hotkey))
        return entries

    def first_hotkey_conflict(self, candidate: dict | None = None, original: dict | None = None) -> str:
        seen: dict[str, str] = {}
        for label, hotkey in self.hotkey_entries(candidate, original):
            key = normalize_hotkey(hotkey)
            if not key:
                continue
            normalized = key.lower()
            if normalized in seen:
                return f"{key} 단축키가 이미 사용 중입니다.\n- {seen[normalized]}\n- {label}"
            seen[normalized] = label
        return ""

    def register_hotkeys(self) -> None:
        self.hotkeys.set_hwnd(int(self.winId()))
        self.hotkeys.unregister_all()
        if not self.settings.get("hotkeys_enabled", True):
            self.update_hotkey_toggle_button()
            return
        conflict = self.first_hotkey_conflict()
        if conflict:
            show_modern_warning(self, "단축키 충돌", conflict)
            return
        for item in self.data.get("phrases", []) + self.data.get("snippets", []):
            hotkey = item.get("hotkey")
            if hotkey:
                self.hotkeys.register(hotkey.get("modifiers", []), hotkey.get("key", ""), lambda value=item: self.paste_text_item(value), item.get("id", ""))
        for item in self.data.get("title_templates", []):
            hotkey = item.get("hotkey")
            if hotkey:
                self.hotkeys.register(hotkey.get("modifiers", []), hotkey.get("key", ""), lambda value=item: self.copy_title_template(value), item.get("id", ""))
        for item in self.data.get("launchers", []):
            hotkey = item.get("hotkey")
            if hotkey:
                self.hotkeys.register(hotkey.get("modifiers", []), hotkey.get("key", ""), lambda value=item: self.tabs[2].open_launcher(value), item.get("id", ""))
        for item in self.data.get("images", []):
            hotkey = item.get("hotkey")
            if hotkey:
                self.hotkeys.register(hotkey.get("modifiers", []), hotkey.get("key", ""), lambda value=item: self.tabs[4].view_image(value), item.get("id", ""))
        for item in self.data.get("macros", []):
            hotkey = item.get("hotkey")
            if hotkey:
                self.hotkeys.register(hotkey.get("modifiers", []), hotkey.get("key", ""), lambda value=item: self.tabs[7].play_macro(value), item.get("id", ""))
        settings = self.settings
        popup_hotkey = settings.get("clipboard_popup_hotkey")
        if popup_hotkey and not settings.get("clipboard_popup_double_ctrl", True):
            self.hotkeys.register(popup_hotkey.get("modifiers", []), popup_hotkey.get("key", ""), self.show_clipboard_popup, "clipboard_popup")
            self.CLIPBOARD_POPUP_HOTKEY_LABEL = normalize_hotkey(popup_hotkey)
        quick_memo_hotkey = settings.get("quick_memo_hotkey")
        if quick_memo_hotkey and not settings.get("quick_memo_double_alt", True):
            self.hotkeys.register(quick_memo_hotkey.get("modifiers", []), quick_memo_hotkey.get("key", ""), self.show_quick_memo_popup, "quick_memo")
        phrase_popup_hotkey = settings.get("phrase_popup_hotkey")
        if phrase_popup_hotkey:
            self.hotkeys.register(phrase_popup_hotkey.get("modifiers", []), phrase_popup_hotkey.get("key", ""), self.show_phrase_popup, "phrase_popup")
        steel_cut_hotkey = settings.get("steel_cut_hotkey")
        if steel_cut_hotkey:
            self.hotkeys.register(steel_cut_hotkey.get("modifiers", []), steel_cut_hotkey.get("key", ""), self.tabs[4].capture_steel_cut, "steel_cut")
        screen_draw_hotkey = settings.get("screen_draw_hotkey")
        if screen_draw_hotkey:
            self.hotkeys.register(screen_draw_hotkey.get("modifiers", []), screen_draw_hotkey.get("key", ""), self.tabs[10].start_screen_draw, "screen_draw")
        self.update_hotkey_status()
        self.update_hotkey_toggle_button()

    def update_hotkey_status(self) -> None:
        return

    def toggle_hotkeys_enabled(self) -> None:
        self.settings["hotkeys_enabled"] = not self.settings.get("hotkeys_enabled", True)
        config.save_settings(self.settings)
        if self.settings["hotkeys_enabled"]:
            self.register_hotkeys()
        else:
            self.hotkeys.unregister_all()
        self.update_hotkey_toggle_button()
        self.refresh_all_tabs()

    def update_hotkey_toggle_button(self) -> None:
        enabled = self.settings.get("hotkeys_enabled", True)
        self.hotkey_toggle.setText("단축키 ON" if enabled else "단축키 OFF")
        bg = "#2EA672" if enabled else "#9CA3AF"
        self.hotkey_toggle.setStyleSheet(f"QPushButton {{ color: {bg}; font-weight: 800; }}")

    def _show_just_updated_notice(self) -> None:
        version = check_just_updated()
        if version:
            self._just_updated = True
            from ui.common import show_modern_info
            show_modern_info(self, "업데이트 완료!", f"v{version} 으로 업데이트 되었습니다. 🎉")

    def check_update_on_startup(self) -> None:
        if self._just_updated:
            return  # 방금 업데이트 완료 → 재확인 스킵
        settings = self.settings
        if not settings.get("auto_update_check", False):
            return
        check_update_dialog(
            self,
            self.version,
            repo=config.GITHUB_REPO,
            auto_install=bool(settings.get("auto_update_install", False)),
        )

    def start_modifier_double_tap_listener(self) -> None:
        if self.ctrl_listener_thread and self.ctrl_listener_thread.is_alive():
            return

        def watch_modifiers() -> None:
            was_down = False
            alt_was_down = False
            while not self.ctrl_listener_stop.is_set():
                ctrl_down = bool(USER32.GetAsyncKeyState(0x11) & 0x8000)
                if ctrl_down and not was_down:
                    self.clear_key_press_history(CTRL_ONLY_VKS)
                if ctrl_down and self.has_disallowed_key_activity(CTRL_ONLY_VKS):
                    self._ctrl_combo_used = True
                if was_down and not ctrl_down:
                    self.handle_ctrl_release()
                was_down = ctrl_down
                alt_down = bool(USER32.GetAsyncKeyState(0x12) & 0x8000)
                if alt_down and not alt_was_down:
                    self.clear_key_press_history(ALT_ONLY_VKS)
                if alt_down and self.has_disallowed_key_activity(ALT_ONLY_VKS):
                    self._alt_combo_used = True
                if alt_was_down and not alt_down:
                    self.handle_alt_release()
                alt_was_down = alt_down
                time.sleep(0.02)

        self.ctrl_listener_thread = threading.Thread(target=watch_modifiers, daemon=True)
        self.ctrl_listener_thread.start()

    def handle_ctrl_release(self) -> None:
        if not self.settings.get("hotkeys_enabled", True):
            self._last_ctrl_release = 0.0
            return
        if not self.data.get("settings", {}).get("clipboard_popup_double_ctrl", True):
            self._last_ctrl_release = 0.0
            return
        if self._ctrl_combo_used:
            self._ctrl_combo_used = False
            self._last_ctrl_release = 0.0
            return
        now = time.monotonic()
        if 0 < now - self._last_ctrl_release <= 0.35:
            self._last_ctrl_release = 0.0
            self.ctrl_double_tapped.emit()
            return
        self._last_ctrl_release = now

    def clear_key_press_history(self, allowed_vks: set[int]) -> None:
        for vk in KEYBOARD_VKS:
            if vk not in allowed_vks:
                USER32.GetAsyncKeyState(vk)

    def has_disallowed_key_activity(self, allowed_vks: set[int]) -> bool:
        for vk in KEYBOARD_VKS:
            if vk in allowed_vks:
                continue
            state = USER32.GetAsyncKeyState(vk)
            if state & 0x8000 or state & 0x0001:
                return True
        return False

    def handle_alt_release(self) -> None:
        if not self.settings.get("hotkeys_enabled", True):
            self._last_alt_release = 0.0
            return
        if not self.settings.get("quick_memo_double_alt", True):
            self._last_alt_release = 0.0
            return
        if self._alt_combo_used:
            self._alt_combo_used = False
            self._last_alt_release = 0.0
            return
        now = time.monotonic()
        if 0 < now - self._last_alt_release <= 0.35:
            self._last_alt_release = 0.0
            self.alt_double_tapped.emit()
            return
        self._last_alt_release = now

    def show_clipboard_popup(self) -> None:
        self.clipboard_tab.show_mini_popup()

    def show_phrase_popup(self) -> None:
        favorite_ids = self.data.get("phrase_popup_favorites", [])[:10]
        by_id = {item.get("id"): item for item in self.data.get("phrases", []) + self.data.get("snippets", [])}
        for item in self.data.get("title_templates", []):
            by_id[item.get("id")] = {
                **item,
                "text": render_date_template(item.get("template", ""), business_days=bool(item.get("business_days", False))),
            }
        items = [by_id[item_id] for item_id in favorite_ids if item_id in by_id]
        NumberedTextPopup(self, "상용구", items, self.paste_text).exec()

    def show_quick_action_popup(self) -> None:
        if self._quick_action_popup is not None and self._quick_action_popup.isVisible():
            self._quick_action_popup.raise_()
            self._quick_action_popup.activateWindow()
            return
        popup = QuickActionPopup(self)
        self._quick_action_popup = popup
        popup.finished.connect(lambda _result, dialog=popup: self.clear_quick_action_popup(dialog))
        popup.exec()

    def clear_quick_action_popup(self, dialog: QuickActionPopup) -> None:
        if self._quick_action_popup is dialog:
            self._quick_action_popup = None

    def show_quick_memo_popup(self) -> None:
        """직접 호출용으로 유지 (QuickActionPopup 메모 탭과 동일 동작)."""
        dialog = QuickMemoPopup(self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        content = dialog.text.toPlainText().strip()
        if not content:
            return
        from app.utils import new_id, now_iso

        title = content.splitlines()[0][:30] or "빠른 메모"
        memo = {
            "id": new_id("mm"),
            "title": title,
            "content": content,
            "pinned": False,
            "always_on_top": True,
            "background": "노랑",
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "sort_order": len(self.data.setdefault("memos", [])),
            "usage_count": 0,
        }
        self.data.setdefault("memos", []).append(memo)
        self.save_data()
        if dialog.sticky.isChecked():
            memo["sticker_open"] = True
            self.tabs[6].show_sticker(memo)

    def copy_title_template(self, item: dict) -> None:
        bump_usage(item)
        text = render_date_template(item.get("template", ""), business_days=bool(item.get("business_days", False)))
        self.save_usage_data()
        self.paste_text(text)

    def clipboard_popup_shortcut_label(self) -> str:
        settings = self.settings
        if settings.get("clipboard_popup_double_ctrl", True):
            return "Ctrl x2"
        return display_hotkey(settings.get("clipboard_popup_hotkey"))

    def quick_memo_shortcut_label(self) -> str:
        settings = self.settings
        if settings.get("quick_memo_double_alt", True):
            return "Alt x2"
        return display_hotkey(settings.get("quick_memo_hotkey"))

    def paste_text(self, text: str) -> None:
        try:
            self.app.clipboard().setText(text)

            def send_paste() -> None:
                try:
                    import pyautogui

                    self.wait_for_modifier_release()
                    pyautogui.hotkey("ctrl", "v")
                except Exception:
                    pass

            threading.Thread(target=send_paste, daemon=True).start()
        except Exception as exc:
            show_modern_warning(self, "단축키 실행 실패", f"텍스트를 붙여넣지 못했습니다.\n{exc}")

    def paste_text_item(self, item: dict) -> None:
        bump_usage(item)
        self.save_usage_data()
        self.paste_text(item.get("text", ""))

    def start_hotstring_listener(self) -> None:
        try:
            from pynput import keyboard
        except Exception:
            return

        def on_press(key) -> None:
            if self.hotstring_busy or not self.settings.get("hotkeys_enabled", True):
                return
            try:
                char = key.char
            except AttributeError:
                if key in {keyboard.Key.space, keyboard.Key.enter, keyboard.Key.tab}:
                    self.hotstring_buffer = ""
                return
            if not char:
                return
            self.hotstring_buffer = (self.hotstring_buffer + char)[-80:]
            self.try_expand_hotstring()

        self.hotstring_listener = keyboard.Listener(on_press=on_press)
        self.hotstring_listener.daemon = True
        self.hotstring_listener.start()

    def try_expand_hotstring(self) -> None:
        for item in self.data.get("hotstrings", []):
            trigger = item.get("trigger", "")
            if not trigger:
                continue
            buffer = self.hotstring_buffer if item.get("case_sensitive") else self.hotstring_buffer.lower()
            needle = trigger if item.get("case_sensitive") else trigger.lower()
            if buffer.endswith(needle):
                self.hotstring_busy = True
                self.hotstring_expand_requested.emit(trigger, item.get("text", ""), item.get("id", ""))
                break

    def expand_hotstring(self, trigger: str, text: str, item_id: str) -> None:
        self.hotstring_busy = True
        for item in self.data.get("hotstrings", []):
            if item.get("id") == item_id:
                bump_usage(item)
                QTimer.singleShot(250, self.save_usage_data)
                break
        self.app.clipboard().setText(text)

        def worker() -> None:
            try:
                import pyautogui

                pyautogui.PAUSE = 0.01
                time.sleep(0.10)
                pyautogui.press("backspace", presses=len(trigger), interval=0.02)
                time.sleep(0.04)
                pyautogui.hotkey("ctrl", "v")
            except Exception:
                pass
            finally:
                self.hotstring_buffer = ""
                self.hotstring_busy = False

        threading.Thread(target=worker, daemon=True).start()

    def set_mouse_highlight(self, enabled: bool) -> None:
        if enabled:
            if self.mouse_highlight_overlay is None:
                self.mouse_highlight_overlay = MouseHighlightOverlay(self.settings)
            self.mouse_highlight_overlay.settings = self.settings
            self.mouse_highlight_overlay.show()
        elif self.mouse_highlight_overlay is not None:
            self.mouse_highlight_overlay.close()
            self.mouse_highlight_overlay = None

    def restore_open_stickers(self) -> None:
        if len(self.tabs) <= 8:
            return
        for memo in self.data.get("memos", []):
            if memo.get("sticker_open"):
                self.tabs[6].show_sticker(memo, track_usage=False, raise_window=False, toggle_existing=False)

    def wait_for_modifier_release(self, timeout: float = 1.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not any(USER32.GetAsyncKeyState(vk) & 0x8000 for vk in (0x10, 0x11, 0x12)):
                return
            time.sleep(0.01)

    def check_schedules(self) -> None:
        now = datetime.now()
        changed = False
        for schedule in self.data.get("schedules", []):
            try:
                target = datetime.fromisoformat(schedule.get("datetime", ""))
            except ValueError:
                continue
            notify_at = target - timedelta(minutes=int(schedule.get("notify_before_minutes", 0)))
            schedule_id = schedule.get("id", "")
            if notify_at <= now <= target + timedelta(minutes=1) and schedule_id not in self._notified_schedule_ids:
                self._notified_schedule_ids.add(schedule_id)
                schedule["last_notified_at"] = now.isoformat(timespec="seconds")
                self.advance_repeating_schedule(schedule, target)
                changed = True
                self.show_schedule_notification(schedule)
        if changed:
            config.save_template(self.template_index, self.data)

    def advance_repeating_schedule(self, schedule: dict[str, Any], target: datetime) -> None:
        repeat = schedule.get("repeat", "none")
        if repeat == "daily":
            schedule["datetime"] = (target + timedelta(days=1)).isoformat(timespec="seconds")
        elif repeat == "weekly":
            weekdays = schedule.get("repeat_weekdays", [target.weekday()])
            if weekdays:
                next_day = target + timedelta(days=1)
                for _ in range(7):
                    if next_day.weekday() in weekdays:
                        schedule["datetime"] = datetime.combine(
                            next_day.date(), target.time()
                        ).isoformat(timespec="seconds")
                        break
                    next_day += timedelta(days=1)
            else:
                schedule["datetime"] = (target + timedelta(weeks=1)).isoformat(timespec="seconds")
        elif repeat == "monthly":
            month = target.month + 1
            year = target.year
            if month > 12:
                month = 1
                year += 1
            day = min(target.day, calendar.monthrange(year, month)[1])
            schedule["datetime"] = target.replace(year=year, month=month, day=day).isoformat(timespec="seconds")
        elif repeat == "yearly":
            try:
                schedule["datetime"] = target.replace(year=target.year + 1).isoformat(timespec="seconds")
            except ValueError:
                schedule["datetime"] = (target + timedelta(days=365)).isoformat(timespec="seconds")
        elif repeat == "weekday":
            weekdays = schedule.get("repeat_weekdays", list(range(5)))
            if weekdays:
                next_day = target + timedelta(days=1)
                for _ in range(7):
                    if next_day.weekday() in weekdays:
                        schedule["datetime"] = datetime.combine(
                            next_day.date(), target.time()
                        ).isoformat(timespec="seconds")
                        break
                    next_day += timedelta(days=1)
            schedule["repeat"] = "weekly"

    def show_schedule_notification(self, schedule: dict[str, Any]) -> None:
        bump_usage(schedule)
        self.save_usage_data()
        title = schedule.get("title", "일정")
        priority = schedule.get("priority", "")
        deadline = schedule.get("deadline", "")
        memo = (schedule.get("memo") or "").strip()

        parts: list[str] = []
        if priority:
            parts.append(f"중요도: {priority}")
        if deadline:
            parts.append(f"마감: {deadline}")
        if memo:
            parts.append(memo)
        message = "\n".join(parts) if parts else "알림 시간이 되었습니다."

        try:
            from plyer import notification
            notification.notify(title=title, message=message, timeout=5)
        except Exception:
            pass

        flash_taskbar(self)
        accent_map = {"상": "#DC2626", "중": "#4338CA"}
        accent = accent_map.get(priority)
        show_modern_info(self, f"🔔 {title}", message, accent=accent)

    def closeEvent(self, event) -> None:
        self.hotkeys.unregister_all()
        if self.hotstring_listener is not None:
            try:
                self.hotstring_listener.stop()
            except Exception:
                pass
        self.set_mouse_highlight(False)
        self.app.removeNativeEventFilter(self.hotkey_event_filter)
        self.ctrl_listener_stop.set()
        if self.ctrl_listener_thread:
            self.ctrl_listener_thread.join(timeout=0.2)
        if hasattr(self.clipboard_tab, "stop"):
            self.clipboard_tab.stop()
        if hasattr(self.clipboard_tab, "cleanup_expired_images"):
            self.clipboard_tab.cleanup_expired_images(days=7)
        super().closeEvent(event)

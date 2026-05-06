from __future__ import annotations

from PyQt6.QtCore import QDateTime, Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.utils import new_id, now_iso, short_preview
from ui.common import add_widget_item, make_card


class StickyMemoDialog(QDialog):
    def __init__(self, memo: dict) -> None:
        super().__init__()
        self.setWindowTitle(memo.get("title", "메모"))
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        layout = QVBoxLayout(self)
        text = QTextEdit(memo.get("content", ""))
        text.setReadOnly(True)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(40, 100)
        slider.setValue(95)
        slider.valueChanged.connect(lambda value: self.setWindowOpacity(value / 100))
        layout.addWidget(text)
        layout.addWidget(slider)
        self.resize(260, 220)


class MemoTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.memo_page = QWidget()
        self.schedule_page = QWidget()
        self.tabs.addTab(self.memo_page, "메모")
        self.tabs.addTab(self.schedule_page, "일정")
        layout.addWidget(self.tabs)
        self._build_memo_page()
        self._build_schedule_page()

    def _build_memo_page(self) -> None:
        layout = QVBoxLayout(self.memo_page)
        self.memo_list = QListWidget()
        self.memo_title = QLineEdit()
        self.memo_content = QTextEdit()
        self.memo_pinned = QCheckBox("핀 고정")
        buttons = QHBoxLayout()
        new_btn = QPushButton("+ 새 메모")
        save_btn = QPushButton("저장")
        delete_btn = QPushButton("삭제")
        sticky_btn = QPushButton("스티커")
        new_btn.clicked.connect(self.new_memo)
        save_btn.clicked.connect(self.save_memo)
        delete_btn.clicked.connect(self.delete_memo)
        sticky_btn.clicked.connect(self.open_sticky)
        buttons.addWidget(new_btn)
        buttons.addWidget(save_btn)
        buttons.addWidget(delete_btn)
        buttons.addWidget(sticky_btn)
        layout.addWidget(self.memo_list, 1)
        layout.addWidget(QLabel("제목"))
        layout.addWidget(self.memo_title)
        layout.addWidget(QLabel("내용"))
        layout.addWidget(self.memo_content, 1)
        layout.addWidget(self.memo_pinned)
        layout.addLayout(buttons)
        self.memo_list.currentRowChanged.connect(self.load_selected_memo)

    def _build_schedule_page(self) -> None:
        layout = QVBoxLayout(self.schedule_page)
        self.schedule_list = QListWidget()
        form = QFormLayout()
        self.schedule_title = QLineEdit()
        self.schedule_dt = QDateTimeEdit()
        self.schedule_dt.setCalendarPopup(True)
        self.schedule_dt.setDateTime(QDateTime.currentDateTime())
        self.schedule_repeat = QComboBox()
        self.schedule_repeat.addItems(["none", "daily", "weekly"])
        self.schedule_notify = QSpinBox()
        self.schedule_notify.setRange(0, 1440)
        self.schedule_notify.setValue(30)
        self.schedule_memo = QTextEdit()
        form.addRow("제목", self.schedule_title)
        form.addRow("일시", self.schedule_dt)
        form.addRow("반복", self.schedule_repeat)
        form.addRow("알림 전(분)", self.schedule_notify)
        form.addRow("메모", self.schedule_memo)
        buttons = QHBoxLayout()
        new_btn = QPushButton("+ 새 일정")
        save_btn = QPushButton("저장")
        delete_btn = QPushButton("삭제")
        new_btn.clicked.connect(self.new_schedule)
        save_btn.clicked.connect(self.save_schedule)
        delete_btn.clicked.connect(self.delete_schedule)
        buttons.addWidget(new_btn)
        buttons.addWidget(save_btn)
        buttons.addWidget(delete_btn)
        layout.addWidget(self.schedule_list, 1)
        layout.addLayout(form)
        layout.addLayout(buttons)
        self.schedule_list.currentRowChanged.connect(self.load_selected_schedule)

    def refresh(self) -> None:
        self.memo_list.clear()
        memos = sorted(self.main.data.get("memos", []), key=lambda item: (not item.get("pinned"), item.get("updated_at", "")))
        for memo in memos:
            add_widget_item(self.memo_list, make_card(memo.get("title", "(제목 없음)"), short_preview(memo.get("content", ""))))
        self.schedule_list.clear()
        for schedule in self.main.data.get("schedules", []):
            add_widget_item(self.schedule_list, make_card(schedule.get("title", "(제목 없음)"), schedule.get("datetime", "")))

    def selected_memo(self) -> dict | None:
        row = self.memo_list.currentRow()
        memos = sorted(self.main.data.get("memos", []), key=lambda item: (not item.get("pinned"), item.get("updated_at", "")))
        return memos[row] if 0 <= row < len(memos) else None

    def selected_schedule(self) -> dict | None:
        row = self.schedule_list.currentRow()
        schedules = self.main.data.get("schedules", [])
        return schedules[row] if 0 <= row < len(schedules) else None

    def new_memo(self) -> None:
        self.memo_list.clearSelection()
        self.memo_title.clear()
        self.memo_content.clear()
        self.memo_pinned.setChecked(False)

    def load_selected_memo(self, *_args) -> None:
        memo = self.selected_memo()
        if not memo:
            return
        self.memo_title.setText(memo.get("title", ""))
        self.memo_content.setPlainText(memo.get("content", ""))
        self.memo_pinned.setChecked(bool(memo.get("pinned")))

    def save_memo(self) -> None:
        title = self.memo_title.text().strip()
        if not title:
            QMessageBox.warning(self, "입력 확인", "제목을 입력해주세요.")
            return
        memo = self.selected_memo()
        if not memo:
            memo = {"id": new_id("mm"), "created_at": now_iso()}
            self.main.data.setdefault("memos", []).append(memo)
        memo.update({"title": title, "content": self.memo_content.toPlainText(), "pinned": self.memo_pinned.isChecked(), "updated_at": now_iso()})
        self.main.save_data()

    def delete_memo(self) -> None:
        memo = self.selected_memo()
        if memo:
            self.main.data.get("memos", []).remove(memo)
            self.main.save_data()

    def open_sticky(self) -> None:
        memo = self.selected_memo()
        if memo:
            StickyMemoDialog(memo).exec()

    def new_schedule(self) -> None:
        self.schedule_list.clearSelection()
        self.schedule_title.clear()
        self.schedule_dt.setDateTime(QDateTime.currentDateTime())
        self.schedule_repeat.setCurrentIndex(0)
        self.schedule_notify.setValue(30)
        self.schedule_memo.clear()

    def load_selected_schedule(self, *_args) -> None:
        schedule = self.selected_schedule()
        if not schedule:
            return
        self.schedule_title.setText(schedule.get("title", ""))
        self.schedule_dt.setDateTime(QDateTime.fromString(schedule.get("datetime", ""), Qt.DateFormat.ISODate))
        idx = self.schedule_repeat.findText(schedule.get("repeat", "none"))
        self.schedule_repeat.setCurrentIndex(max(idx, 0))
        self.schedule_notify.setValue(int(schedule.get("notify_before_minutes", 30)))
        self.schedule_memo.setPlainText(schedule.get("memo", ""))

    def save_schedule(self) -> None:
        title = self.schedule_title.text().strip()
        if not title:
            QMessageBox.warning(self, "입력 확인", "제목을 입력해주세요.")
            return
        schedule = self.selected_schedule()
        if not schedule:
            schedule = {"id": new_id("sc")}
            self.main.data.setdefault("schedules", []).append(schedule)
        schedule.update(
            {
                "title": title,
                "datetime": self.schedule_dt.dateTime().toString(Qt.DateFormat.ISODate),
                "repeat": self.schedule_repeat.currentText(),
                "notify_before_minutes": self.schedule_notify.value(),
                "memo": self.schedule_memo.toPlainText(),
            }
        )
        self.main.save_data()

    def delete_schedule(self) -> None:
        schedule = self.selected_schedule()
        if schedule:
            self.main.data.get("schedules", []).remove(schedule)
            self.main.save_data()

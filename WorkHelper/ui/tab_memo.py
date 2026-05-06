from __future__ import annotations

from PyQt6.QtCore import QDateTime, Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.utils import new_id, now_iso, short_preview
from ui.common import GridPanel, add_card_actions, make_card


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
        self.resize(300, 240)


class MemoDialog(QDialog):
    def __init__(self, memo: dict | None = None) -> None:
        super().__init__()
        self.setWindowTitle("메모 편집")
        self.memo = memo or {}
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.title = QLineEdit(self.memo.get("title", ""))
        self.content = QTextEdit(self.memo.get("content", ""))
        self.pinned = QCheckBox("핀 고정")
        self.pinned.setChecked(bool(self.memo.get("pinned")))
        form.addRow("제목", self.title)
        form.addRow("내용", self.content)
        form.addRow("옵션", self.pinned)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def value(self) -> dict:
        data = dict(self.memo)
        if not data.get("id"):
            data["id"] = new_id("mm")
            data["created_at"] = now_iso()
        data.update(
            {
                "title": self.title.text().strip(),
                "content": self.content.toPlainText(),
                "pinned": self.pinned.isChecked(),
                "updated_at": now_iso(),
            }
        )
        return data


class ScheduleDialog(QDialog):
    def __init__(self, schedule: dict | None = None) -> None:
        super().__init__()
        self.setWindowTitle("일정 편집")
        self.schedule = schedule or {}
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.title = QLineEdit(self.schedule.get("title", ""))
        self.datetime = QDateTimeEdit()
        self.datetime.setCalendarPopup(True)
        schedule_dt = QDateTime.fromString(self.schedule.get("datetime", ""), Qt.DateFormat.ISODate)
        self.datetime.setDateTime(schedule_dt if schedule_dt.isValid() else QDateTime.currentDateTime())
        self.repeat = QComboBox()
        self.repeat.addItems(["none", "daily", "weekly"])
        idx = self.repeat.findText(self.schedule.get("repeat", "none"))
        self.repeat.setCurrentIndex(max(idx, 0))
        self.notify = QSpinBox()
        self.notify.setRange(0, 1440)
        self.notify.setValue(int(self.schedule.get("notify_before_minutes", 30)))
        self.memo = QTextEdit(self.schedule.get("memo", ""))
        form.addRow("제목", self.title)
        form.addRow("일시", self.datetime)
        form.addRow("반복", self.repeat)
        form.addRow("알림 전(분)", self.notify)
        form.addRow("메모", self.memo)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def value(self) -> dict:
        data = dict(self.schedule)
        if not data.get("id"):
            data["id"] = new_id("sc")
        data.update(
            {
                "title": self.title.text().strip(),
                "datetime": self.datetime.dateTime().toString(Qt.DateFormat.ISODate),
                "repeat": self.repeat.currentText(),
                "notify_before_minutes": self.notify.value(),
                "memo": self.memo.toPlainText(),
            }
        )
        return data


class MemoListTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        top = QHBoxLayout()
        top.addStretch(1)
        add_btn = QPushButton("+ 새 메모")
        add_btn.clicked.connect(lambda: self.edit_memo())
        top.addWidget(add_btn)
        self.grid = GridPanel(columns=2)
        layout.addLayout(top)
        layout.addWidget(self.grid, 1)

    def refresh(self) -> None:
        cards = []
        memos = sorted(self.main.data.get("memos", []), key=lambda item: (not item.get("pinned"), item.get("updated_at", "")))
        for memo in memos:
            card = make_card(memo.get("title", "(제목 없음)"), short_preview(memo.get("content", ""), 160))
            add_card_actions(
                card,
                [
                    ("📌", "스티커", lambda checked=False, value=memo: StickyMemoDialog(value).exec(), False),
                    ("✎", "편집", lambda checked=False, value=memo: self.edit_memo(value), False),
                    ("×", "삭제", lambda checked=False, value=memo: self.delete_memo(value), True),
                ],
            )
            cards.append(card)
        self.grid.add_cards(cards)

    def edit_memo(self, memo: dict | None = None) -> None:
        dialog = MemoDialog(memo)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        value = dialog.value()
        if not value.get("title"):
            QMessageBox.warning(self, "입력 확인", "제목을 입력해주세요.")
            return
        items = self.main.data.setdefault("memos", [])
        if memo in items:
            items[items.index(memo)] = value
        else:
            items.append(value)
        self.main.save_data()

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
        add_btn = QPushButton("+ 새 일정")
        add_btn.clicked.connect(lambda: self.edit_schedule())
        top.addWidget(add_btn)
        self.grid = GridPanel(columns=2)
        layout.addLayout(top)
        layout.addWidget(self.grid, 1)

    def refresh(self) -> None:
        cards = []
        for schedule in self.main.data.get("schedules", []):
            subtitle = f"{schedule.get('datetime', '')}\n{short_preview(schedule.get('memo', ''), 120)}"
            card = make_card(schedule.get("title", "(제목 없음)"), subtitle)
            add_card_actions(
                card,
                [
                    ("✎", "편집", lambda checked=False, value=schedule: self.edit_schedule(value), False),
                    ("×", "삭제", lambda checked=False, value=schedule: self.delete_schedule(value), True),
                ],
            )
            cards.append(card)
        self.grid.add_cards(cards)

    def edit_schedule(self, schedule: dict | None = None) -> None:
        dialog = ScheduleDialog(schedule)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        value = dialog.value()
        if not value.get("title"):
            QMessageBox.warning(self, "입력 확인", "제목을 입력해주세요.")
            return
        items = self.main.data.setdefault("schedules", [])
        if schedule in items:
            items[items.index(schedule)] = value
        else:
            items.append(value)
        self.main.save_data()

    def delete_schedule(self, schedule: dict) -> None:
        self.main.data.get("schedules", []).remove(schedule)
        self.main.save_data()

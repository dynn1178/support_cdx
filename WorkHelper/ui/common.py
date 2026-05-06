from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

HOTKEY_KEYS = [str(i) for i in range(1, 10)] + [f"F{i}" for i in range(1, 13)]


def make_card(title: str, subtitle: str = "", hotkey: str = "") -> QWidget:
    card = QWidget()
    card.setObjectName("card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(8)
    row = QHBoxLayout()
    row.setSpacing(10)
    title_label = QLabel(title)
    title_label.setObjectName("cardTitle")
    row.addWidget(title_label, 1)
    if hotkey:
        key_label = QLabel(hotkey)
        key_label.setObjectName("kbd")
        key_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        row.addWidget(key_label)
    layout.addLayout(row)
    if subtitle:
        sub = QLabel(subtitle)
        sub.setObjectName("cardSubtitle")
        sub.setWordWrap(True)
        layout.addWidget(sub)
    return card


def make_icon_button(text: str, tooltip: str, callback, danger: bool = False) -> QToolButton:
    button = QToolButton()
    button.setObjectName("dangerIconButton" if danger else "iconButton")
    button.setText(text)
    button.setToolTip(tooltip)
    button.setFixedSize(QSize(28, 26))
    button.clicked.connect(callback)
    return button


def add_card_actions(card: QWidget, actions: list[tuple[str, str, object, bool]]) -> None:
    row = QHBoxLayout()
    row.setContentsMargins(0, 2, 0, 0)
    row.addStretch(1)
    for text, tooltip, callback, danger in actions:
        row.addWidget(make_icon_button(text, tooltip, callback, danger))
    card.layout().addLayout(row)


class GridPanel(QScrollArea):
    def __init__(self, columns: int = 2, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.columns = max(1, columns)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.grid.setContentsMargins(10, 10, 10, 10)
        self.grid.setHorizontalSpacing(10)
        self.grid.setVerticalSpacing(10)
        self.setWidget(self.container)

    def clear(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def add_cards(self, cards: list[QWidget]) -> None:
        self.clear()
        for i, card in enumerate(cards):
            row, col = divmod(i, self.columns)
            self.grid.addWidget(card, row, col)
        for col in range(self.columns):
            self.grid.setColumnStretch(col, 1)
        self.grid.setRowStretch((len(cards) + self.columns - 1) // self.columns, 1)


def add_widget_item(list_widget, widget: QWidget) -> QListWidgetItem:
    item = QListWidgetItem(list_widget)
    item.setSizeHint(widget.sizeHint())
    list_widget.addItem(item)
    list_widget.setItemWidget(item, widget)
    return item


class HotkeyFields(QWidget):
    def __init__(self, hotkey: dict[str, Any] | None = None) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.ctrl = QCheckBox("Ctrl")
        self.alt = QCheckBox("Alt")
        self.shift = QCheckBox("Shift")
        self.key = QComboBox()
        self.key.addItems(HOTKEY_KEYS)
        layout.addWidget(self.ctrl)
        layout.addWidget(self.alt)
        layout.addWidget(self.shift)
        layout.addWidget(self.key, 1)
        self.set_hotkey(hotkey)

    def set_hotkey(self, hotkey: dict[str, Any] | None) -> None:
        if not hotkey:
            return
        modifiers = set(hotkey.get("modifiers", []))
        self.ctrl.setChecked("ctrl" in modifiers)
        self.alt.setChecked("alt" in modifiers)
        self.shift.setChecked("shift" in modifiers)
        key = hotkey.get("key")
        if key:
            index = self.key.findText(str(key))
            if index >= 0:
                self.key.setCurrentIndex(index)

    def value(self) -> dict[str, Any] | None:
        modifiers = []
        if self.ctrl.isChecked():
            modifiers.append("ctrl")
        if self.alt.isChecked():
            modifiers.append("alt")
        if self.shift.isChecked():
            modifiers.append("shift")
        if not modifiers:
            return None
        return {"modifiers": modifiers, "key": self.key.currentText()}


class TextItemDialog(QDialog):
    def __init__(self, title: str, item: dict[str, Any] | None = None, code: bool = False) -> None:
        super().__init__()
        self.setWindowTitle(title)
        self.item = item or {}
        self.code = code
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(self.item.get("name", ""))
        self.text = QTextEdit(self.item.get("text", ""))
        self.hotkey = HotkeyFields(self.item.get("hotkey"))
        form.addRow("이름", self.name)
        if code:
            self.language = QComboBox()
            self.language.addItems(["sql", "python", "other"])
            current = self.item.get("language", "sql")
            idx = self.language.findText(current)
            if idx >= 0:
                self.language.setCurrentIndex(idx)
            form.addRow("언어", self.language)
        form.addRow("내용", self.text)
        form.addRow("단축키", self.hotkey)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def value(self) -> dict[str, Any]:
        data = dict(self.item)
        data.update({"name": self.name.text().strip(), "text": self.text.toPlainText(), "hotkey": self.hotkey.value()})
        if self.code:
            data.update({"language": self.language.currentText(), "type": "code"})
        else:
            data.update({"type": "text"})
        return data

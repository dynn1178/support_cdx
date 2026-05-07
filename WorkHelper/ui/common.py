from __future__ import annotations

from typing import Any, Callable

from PyQt6.QtCore import QEvent, QPoint, QSize, Qt
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
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

HOTKEY_KEYS = [str(i) for i in range(1, 10)] + ["0"] + [chr(i) for i in range(ord("A"), ord("Z") + 1)] + [f"F{i}" for i in range(1, 13)]

SORT_MODES = [
    ("등록", "created"),
    ("가나다", "name"),
    ("수동", "manual"),
]
SORT_ORDERS = [
    ("내림차순", "desc"),
    ("오름차순", "asc"),
]

ACTION_ICONS = {
    "copy": "📋",
    "edit": "✏️",
    "delete": "🗑️",
    "play": "▶️",
    "view": "🔍",
    "pin": "📌",
    "open": "↗️",
    "sticker": "📝",
    "history": "📜",
}


class ElidedLabel(QLabel):
    def __init__(self, text: str) -> None:
        super().__init__()
        self._full_text = text
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(0)
        self.setToolTip(text)
        self._update_elided_text()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_elided_text()

    def _update_elided_text(self) -> None:
        width = max(0, self.contentsRect().width())
        text = self.fontMetrics().elidedText(self._full_text, Qt.TextElideMode.ElideRight, width)
        if self.text() != text:
            self.setText(text)


class ElidedMultilineLabel(QLabel):
    def __init__(self, text: str, max_lines: int = 2) -> None:
        super().__init__()
        self._full_text = text
        self._max_lines = max(1, max_lines)
        self.setToolTip(text)
        self.setWordWrap(True)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)
        self.setFixedHeight(self.fontMetrics().lineSpacing() * self._max_lines + 4)
        self._update_elided_text()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_elided_text()

    def _update_elided_text(self) -> None:
        width = max(0, self.contentsRect().width())
        lines = self._full_text.splitlines() or [self._full_text]
        visible = lines[: self._max_lines]
        if len(lines) > self._max_lines:
            visible[-1] += " ..."
        text = "\n".join(self.fontMetrics().elidedText(line, Qt.TextElideMode.ElideRight, width) for line in visible)
        if self.text() != text:
            self.setText(text)


def make_card(title: str, subtitle: str = "", hotkey: str = "", single_line: bool = False, hotkey_color: str = "", compact: bool = False) -> QWidget:
    card = QWidget()
    card.setObjectName("card")
    card.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(10, 6, 10, 6) if compact else layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(4 if compact else 8)
    row = QHBoxLayout()
    row.setSpacing(10)
    title_label = ElidedLabel(title) if single_line else QLabel(title)
    title_label.setObjectName("cardTitle")
    title_label.setWordWrap(not single_line)
    title_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    title_label.setMinimumWidth(0)
    title_label.setToolTip(title)
    row.addWidget(title_label, 1)
    if hotkey:
        row.addWidget(make_hotkey_caps(hotkey, hotkey_color))
    layout.addLayout(row)
    if subtitle:
        sub = ElidedMultilineLabel(subtitle, max_lines=1 if compact else 2)
        sub.setObjectName("cardSubtitle")
        layout.addWidget(sub)
    return card


def make_hotkey_caps(hotkey: str, hotkey_color: str = "") -> QWidget:
    container = QWidget()
    container.setObjectName("hotkeyCaps")
    container.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
    parts = [part.strip() for part in hotkey.split("+") if part.strip()]
    for part in parts:
        cap = QLabel(part)
        cap.setObjectName("keyCap")
        cap.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cap.setFixedHeight(20)
        cap.setMinimumWidth(18)
        cap.setContentsMargins(0, 0, 0, 0)
        if hotkey_color:
            cap.setStyleSheet(f"QLabel#keyCap {{ background: {hotkey_color}; color: #1F2937; border-color: rgba(31, 41, 55, 0.25); }}")
        layout.addWidget(cap)
    return container


def confirm_shift_digit_hotkey(parent: QWidget, hotkey: dict | None) -> bool:
    if not hotkey:
        return True
    modifiers = {str(modifier).lower() for modifier in hotkey.get("modifiers", [])}
    key = str(hotkey.get("key", ""))
    if modifiers != {"shift"} or key not in {str(i) for i in range(10)}:
        return True
    return (
        QMessageBox.question(
            parent,
            "단축키 확인",
            "Shift+숫자 단축키는 특수문자 입력을 대체할 수 있습니다.\n그래도 등록하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        == QMessageBox.StandardButton.Yes
    )


def make_icon_button(text: str, tooltip: str, callback, danger: bool = False) -> QToolButton:
    button = QToolButton()
    button.setObjectName("dangerIconButton" if danger else "iconButton")
    button.setText(ACTION_ICONS.get(text, text))
    button.setToolTip(tooltip)
    button.setFixedSize(QSize(30, 28))
    button.clicked.connect(callback)
    return button


def add_card_actions(card: QWidget, actions: list[tuple[str, str, object, bool]]) -> None:
    row = QHBoxLayout()
    row.setContentsMargins(0, 2, 0, 0)
    row.addStretch(1)
    for text, tooltip, callback, danger in actions:
        row.addWidget(make_icon_button(text, tooltip, callback, danger))
    card.layout().addLayout(row)


def ensure_item_meta(items: list[dict]) -> None:
    for index, item in enumerate(items):
        item.setdefault("sort_order", index)
        item.setdefault("usage_count", int(item.get("usage_count", 0) or 0))


def bump_usage(item: dict) -> None:
    item["usage_count"] = int(item.get("usage_count", 0) or 0) + 1


def apply_manual_reorder(items: list[dict], visible_items: list[dict], old_index: int, new_index: int) -> None:
    if old_index < 0 or old_index >= len(visible_items) or new_index < 0 or new_index >= len(visible_items):
        return
    moved = visible_items.pop(old_index)
    visible_items.insert(new_index, moved)
    for index, item in enumerate(visible_items):
        item["sort_order"] = index
    hidden_items = [item for item in items if item not in visible_items]
    offset = len(visible_items)
    for index, item in enumerate(hidden_items, start=offset):
        item["sort_order"] = index


def sort_items(
    items: list[dict],
    mode: str = "created",
    order: str = "desc",
    text_func: Callable[[dict], str] | None = None,
) -> list[dict]:
    ensure_item_meta(items)
    reverse = order == "desc"

    def text_value(item: dict) -> str:
        if text_func:
            return text_func(item)
        return str(item.get("name") or item.get("title") or item.get("text") or item.get("template") or "")

    def created_key(item: dict) -> tuple[str, int]:
        created = item.get("created_at") or item.get("updated_at") or item.get("copied_at") or ""
        return str(created), int(item.get("sort_order", 0) or 0)

    if mode == "name":
        key_func = lambda item: text_value(item).casefold()
    elif mode == "manual":
        key_func = lambda item: int(item.get("sort_order", 0) or 0)
        reverse = False
    else:
        key_func = created_key
    return sorted(items, key=key_func, reverse=reverse)


class SortControls(QWidget):
    def __init__(self, changed: Callable[[], None] | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sortControls")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)
        self.mode = QComboBox()
        for text, value in SORT_MODES:
            self.mode.addItem(text, value)
        self.order = QComboBox()
        for text, value in SORT_ORDERS:
            self.order.addItem(text, value)
        self.mode.setCurrentIndex(self.mode.findData("created"))
        self.order.setCurrentIndex(self.order.findData("desc"))
        layout.addWidget(self.mode)
        layout.addWidget(self.order)
        self.mode.setFixedHeight(26)
        self.order.setFixedHeight(26)
        self.mode.setFixedWidth(78)
        self.order.setFixedWidth(92)
        self.setFixedHeight(32)
        self.setStyleSheet(
            """
            QWidget#sortControls {
                border: 0;
                background: transparent;
            }
            QWidget#sortControls QComboBox {
                padding: 2px 9px;
                min-height: 18px;
            }
            """
        )
        self.mode.currentIndexChanged.connect(self.update_order_enabled)
        if changed:
            self.mode.currentIndexChanged.connect(lambda _index: changed())
            self.order.currentIndexChanged.connect(lambda _index: changed())
        self.update_order_enabled()

    def sort_items(self, items: list[dict], text_func: Callable[[dict], str] | None = None) -> list[dict]:
        return sort_items(items, self.mode.currentData() or "created", self.order.currentData() or "desc", text_func)

    def is_manual(self) -> bool:
        return self.mode.currentData() == "manual"

    def update_order_enabled(self, *_args) -> None:
        self.order.setEnabled(not self.is_manual())


class GridPanel(QScrollArea):
    def __init__(self, columns: int = 2, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.columns = max(1, columns)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._cards: list[QWidget] = []
        self._drag_card: QWidget | None = None
        self._drag_start = QPoint()
        self._dragging = False
        self._on_reorder: Callable[[int, int], None] | None = None
        self.container = QWidget()
        self.container.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.grid = QGridLayout(self.container)
        self.grid.setContentsMargins(10, 10, 10, 10)
        self.grid.setHorizontalSpacing(10)
        self.grid.setVerticalSpacing(10)
        self.setWidget(self.container)

    def clear(self) -> None:
        self._cards = []
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def add_cards(self, cards: list[QWidget], on_reorder: Callable[[int, int], None] | None = None) -> None:
        self.clear()
        self._cards = cards
        self._on_reorder = on_reorder
        for i, card in enumerate(cards):
            card.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            card.setMinimumWidth(0)
            self._install_drag_filter(card)
            row, col = divmod(i, self.columns)
            self.grid.addWidget(card, row, col)
        for col in range(self.columns):
            self.grid.setColumnStretch(col, 1)
        self.grid.setRowStretch((len(cards) + self.columns - 1) // self.columns, 1)

    def _install_drag_filter(self, widget: QWidget) -> None:
        widget.installEventFilter(self)
        for child in widget.findChildren(QWidget):
            child.installEventFilter(self)

    def _card_for_widget(self, widget: QWidget) -> QWidget | None:
        current: QWidget | None = widget
        while current is not None:
            if current in self._cards:
                return current
            parent = current.parent()
            current = parent if isinstance(parent, QWidget) else None
        return None

    def eventFilter(self, watched, event) -> bool:
        if not self._on_reorder or not isinstance(watched, QWidget):
            return super().eventFilter(watched, event)
        if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            card = self._card_for_widget(watched)
            if card:
                self._drag_card = card
                self._drag_start = event.globalPosition().toPoint()
                self._dragging = False
        elif event.type() == QEvent.Type.MouseMove and self._drag_card:
            if (event.globalPosition().toPoint() - self._drag_start).manhattanLength() > 8:
                self._dragging = True
                self._drag_card.setCursor(Qt.CursorShape.ClosedHandCursor)
                self._drag_card.setProperty("dragging", True)
                self._drag_card.style().unpolish(self._drag_card)
                self._drag_card.style().polish(self._drag_card)
        elif event.type() == QEvent.Type.MouseButtonRelease and self._drag_card:
            card = self._drag_card
            old_index = self._cards.index(card) if card in self._cards else -1
            new_index = self._drop_index(event.globalPosition().toPoint())
            card.setCursor(Qt.CursorShape.ArrowCursor)
            card.setProperty("dragging", False)
            card.style().unpolish(card)
            card.style().polish(card)
            self._drag_card = None
            was_dragging = self._dragging
            self._dragging = False
            if was_dragging and old_index >= 0 and new_index >= 0 and old_index != new_index:
                self._on_reorder(old_index, new_index)
                return True
        return super().eventFilter(watched, event)

    def _drop_index(self, global_pos: QPoint) -> int:
        if not self._cards:
            return -1
        container_pos = self.container.mapFromGlobal(global_pos)
        for index, card in enumerate(self._cards):
            if card.geometry().contains(container_pos):
                return index
        return len(self._cards) - 1


def add_widget_item(list_widget, widget: QWidget) -> QListWidgetItem:
    item = QListWidgetItem(list_widget)
    item.setSizeHint(widget.sizeHint())
    list_widget.addItem(item)
    list_widget.setItemWidget(item, widget)
    return item


class HotkeyFields(QWidget):
    def __init__(self, hotkey: dict[str, Any] | None = None) -> None:
        super().__init__()
        self.setMinimumHeight(34)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
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
    def __init__(self, title: str, item: dict[str, Any] | None = None, code: bool = False, require_name: bool = True) -> None:
        super().__init__()
        self.setWindowTitle(title)
        self.item = item or {}
        self.code = code
        self.require_name = require_name
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(self.item.get("name", ""))
        self.text = QTextEdit(self.item.get("text", ""))
        self.hotkey = HotkeyFields(self.item.get("hotkey"))
        if require_name:
            form.addRow("이름", self.name)
        if code:
            self.language = QComboBox()
            self.language.addItems(["sql", "python", "기타"])
            current = self.item.get("language", "sql")
            if current == "other":
                current = "기타"
            idx = self.language.findText(current)
            if idx >= 0:
                self.language.setCurrentIndex(idx)
            form.addRow("언어", self.language)
        form.addRow("내용", self.text)
        form.addRow("단축키", self.hotkey)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("확인")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def value(self) -> dict[str, Any]:
        data = dict(self.item)
        name = self.name.text().strip() if self.require_name else self.text.toPlainText().splitlines()[0][:30].strip()
        data.update({"name": name, "text": self.text.toPlainText(), "hotkey": self.hotkey.value()})
        if self.code:
            language = "other" if self.language.currentText() == "기타" else self.language.currentText()
            data.update({"language": language, "type": "code"})
        else:
            data.update({"type": "text"})
        return data

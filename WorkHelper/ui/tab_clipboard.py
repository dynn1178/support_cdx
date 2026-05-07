from __future__ import annotations

from PyQt6.QtCore import QAbstractNativeEventFilter, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QKeyEvent
from PyQt6.QtWidgets import QApplication, QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget

from app import config
from app.clipboard_watcher import ClipboardWatcher
from app.hotkey_manager import USER32, WM_HOTKEY
from app.utils import new_id, now_iso, short_preview
from ui.common import GridPanel, SortControls, add_card_actions, apply_manual_reorder, bump_usage, make_card


class PopupNumberFilter(QAbstractNativeEventFilter):
    def __init__(self, popup: "ClipboardMiniPopup") -> None:
        super().__init__()
        self.popup = popup

    def nativeEventFilter(self, event_type, message):
        try:
            from ctypes import wintypes

            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and 5201 <= int(msg.wParam) <= 5205:
                self.popup.copy_by_number(int(msg.wParam) - 5200)
                return True, 0
        except Exception:
            pass
        return False, 0


class ClipboardMiniPopup(QDialog):
    number_selected = pyqtSignal(int)

    def __init__(self, parent: QWidget, items: list[dict]) -> None:
        super().__init__(parent)
        self.items = items
        self.number_filter = PopupNumberFilter(self)
        self.registered_number_hotkeys: list[int] = []
        self._closing = False
        self.setWindowTitle("클립보드")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedWidth(360)
        self.number_selected.connect(self.copy_by_number)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        rows = QVBoxLayout(container)
        rows.setContentsMargins(0, 0, 0, 0)
        rows.setSpacing(3)

        if not self.items:
            rows.addWidget(self._empty_row())
        else:
            for index, item in enumerate(self.items, start=1):
                rows.addWidget(self._item_row(index, item))
        rows.addStretch(1)
        scroll.setWidget(container)
        layout.addWidget(scroll)

        footer = QHBoxLayout()
        hint = QLabel("1~5번 단축키를 누르면 바로 복사됩니다.")
        hint.setObjectName("mutedText")
        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(self.accept)
        footer.addWidget(hint, 1)
        footer.addWidget(close_btn)
        layout.addLayout(footer)

        visible_rows = min(max(len(self.items), 1), 7)
        self.setFixedHeight(54 + visible_rows * 34)
        self.start_number_hotkeys()
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
        self.setFocus(Qt.FocusReason.PopupFocusReason)

    def start_number_hotkeys(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        app.installNativeEventFilter(self.number_filter)
        hwnd = int(self.winId())
        for number in range(1, 6):
            hotkey_id = 5200 + number
            if USER32.RegisterHotKey(hwnd, hotkey_id, 0, ord(str(number))):
                self.registered_number_hotkeys.append(hotkey_id)

    def stop_number_hotkeys(self) -> None:
        hwnd = int(self.winId())
        for hotkey_id in self.registered_number_hotkeys:
            try:
                USER32.UnregisterHotKey(hwnd, hotkey_id)
            except Exception:
                pass
        self.registered_number_hotkeys.clear()
        app = QApplication.instance()
        if app is not None:
            try:
                app.removeNativeEventFilter(self.number_filter)
            except Exception:
                pass

    def _empty_row(self) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(6, 4, 6, 4)
        label = QLabel("클립보드 이력이 없습니다.")
        layout.addWidget(label)
        return row

    def _item_row(self, index: int, item: dict) -> QWidget:
        row = QWidget()
        row.setObjectName("card")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(6)

        number = QLabel(str(index) if index <= 5 else "")
        number.setObjectName("kbd")
        number.setAlignment(Qt.AlignmentFlag.AlignCenter)
        number.setFixedWidth(24)
        text = QLabel(short_preview(item.get("text", ""), 55))
        text.setWordWrap(False)
        text.setFixedWidth(230)
        text.setToolTip(item.get("text", ""))
        copy_btn = QPushButton("복사")
        copy_btn.setFixedWidth(48)
        copy_btn.clicked.connect(lambda checked=False, value=item: self.copy_and_close(value))

        layout.addWidget(number)
        layout.addWidget(text, 1)
        layout.addWidget(copy_btn)
        return row

    def keyPressEvent(self, event: QKeyEvent) -> None:
        text = event.text()
        if text in {"1", "2", "3", "4", "5"}:
            self.copy_by_number(int(text))
            return
        super().keyPressEvent(event)

    def copy_by_number(self, number: int) -> None:
        if self._closing:
            return
        index = number - 1
        if 0 <= index < min(len(self.items), 5):
            self.copy_and_close(self.items[index])

    def copy_and_close(self, item: dict) -> None:
        if self._closing:
            return
        self._closing = True
        QApplication.clipboard().setText(item.get("text", ""))
        self.accept()

    def done(self, result: int) -> None:
        self.stop_number_hotkeys()
        super().done(result)

    def closeEvent(self, event) -> None:
        self.stop_number_hotkeys()
        super().closeEvent(event)


class ClipboardTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        self.history = config.load_clipboard_history()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText("검색")
        self.search.textChanged.connect(self.refresh)
        self.sort_controls = SortControls(self.refresh)
        self.list = GridPanel(columns=2)
        top = QHBoxLayout()
        top.addWidget(self.search, 1)
        top.addWidget(self.sort_controls)
        layout.addLayout(top)
        layout.addWidget(self.list, 1)
        self.watcher = ClipboardWatcher()
        self.watcher.new_item.connect(self.add_history)
        self.watcher.start()

    def stop(self) -> None:
        self.watcher.stop()
        self.watcher.wait(1000)

    def add_history(self, text: str) -> None:
        items = self.history.setdefault("history", [])
        if items and items[0].get("text") == text:
            return
        items.insert(
            0,
            {
                "id": new_id("cb"),
                "text": text,
                "copied_at": now_iso(),
                "created_at": now_iso(),
                "sort_order": len(items),
                "usage_count": 0,
                "pinned": False,
            },
        )
        limit = int(self.main.data.get("settings", {}).get("clipboard_history_limit", 50))
        pinned = [item for item in items if item.get("pinned")]
        unpinned = [item for item in items if not item.get("pinned")][: max(0, limit - len(pinned))]
        self.history["history"] = pinned + unpinned
        config.save_clipboard_history(self.history)
        self.refresh()

    def refresh(self) -> None:
        cards = []
        query = self.search.text().strip().lower()
        source_items = self.history.get("history", [])
        items = self.sort_controls.sort_items(source_items, lambda value: value.get("text", ""))
        if not self.sort_controls.is_manual():
            items = sorted(items, key=lambda item: not item.get("pinned"))
        for item in items:
            text = item.get("text", "")
            if query and query not in text.lower():
                continue
            card = make_card(("📌 " if item.get("pinned") else "") + short_preview(text, 160), "고정됨" if item.get("pinned") else "", single_line=True)
            if item.get("pinned"):
                card.setStyleSheet("QWidget#card { border: 2px solid #3B6CF5; background: #EEF2FF; }")
            add_card_actions(
                card,
                [
                    ("copy", "복사", lambda checked=False, value=item: self.copy_item(value), False),
                    ("pin", "고정/해제", lambda checked=False, value=item: self.toggle_pin(value), False),
                    ("delete", "삭제", lambda checked=False, value=item: self.delete_item(value), True),
                ],
            )
            cards.append(card)
        callback = (lambda old, new: self.reorder_items(source_items, items, old, new)) if self.sort_controls.is_manual() else None
        self.list.add_cards(cards, on_reorder=callback)

    def reorder_items(self, source: list[dict], visible: list[dict], old: int, new: int) -> None:
        apply_manual_reorder(source, visible, old, new)
        config.save_clipboard_history(self.history)
        self.refresh()

    def copy_item(self, item: dict) -> None:
        bump_usage(item)
        QApplication.clipboard().setText(item.get("text", ""))
        config.save_clipboard_history(self.history)
        self.refresh()

    def toggle_pin(self, item: dict) -> None:
        item["pinned"] = not item.get("pinned")
        config.save_clipboard_history(self.history)
        self.refresh()

    def delete_item(self, item: dict) -> None:
        self.history.get("history", []).remove(item)
        config.save_clipboard_history(self.history)
        self.refresh()

    def show_mini_popup(self) -> None:
        limit = int(self.main.data.get("settings", {}).get("clipboard_history_limit", 50))
        ClipboardMiniPopup(self, self.history.get("history", [])[:limit]).exec()

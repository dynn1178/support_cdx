from __future__ import annotations

import pyperclip
from PyQt6.QtWidgets import QHBoxLayout, QLineEdit, QListWidget, QMessageBox, QPushButton, QVBoxLayout, QWidget

from app import config
from app.clipboard_watcher import ClipboardWatcher
from app.utils import new_id, now_iso, short_preview
from ui.common import add_widget_item, make_card


class ClipboardTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        self.history = config.load_clipboard_history()
        layout = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText("검색")
        self.search.textChanged.connect(self.refresh)
        self.list = QListWidget()
        layout.addWidget(self.search)
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
        items.insert(0, {"id": new_id("cb"), "text": text, "copied_at": now_iso(), "pinned": False})
        limit = int(self.main.data.get("settings", {}).get("clipboard_history_limit", 50))
        pinned = [item for item in items if item.get("pinned")]
        unpinned = [item for item in items if not item.get("pinned")][: max(0, limit - len(pinned))]
        self.history["history"] = pinned + unpinned
        config.save_clipboard_history(self.history)
        self.refresh()

    def refresh(self) -> None:
        self.list.clear()
        query = self.search.text().strip().lower()
        items = sorted(self.history.get("history", []), key=lambda item: (not item.get("pinned"), item.get("copied_at", "")), reverse=False)
        for item in items:
            text = item.get("text", "")
            if query and query not in text.lower():
                continue
            card = make_card("고정됨" if item.get("pinned") else item.get("copied_at", ""), short_preview(text, 160))
            row = QHBoxLayout()
            copy_btn = QPushButton("복사")
            pin_btn = QPushButton("핀 해제" if item.get("pinned") else "핀 고정")
            del_btn = QPushButton("삭제")
            copy_btn.clicked.connect(lambda checked=False, value=item: self.copy_item(value))
            pin_btn.clicked.connect(lambda checked=False, value=item: self.toggle_pin(value))
            del_btn.clicked.connect(lambda checked=False, value=item: self.delete_item(value))
            row.addWidget(copy_btn)
            row.addWidget(pin_btn)
            row.addWidget(del_btn)
            card.layout().addLayout(row)
            add_widget_item(self.list, card)

    def copy_item(self, item: dict) -> None:
        try:
            pyperclip.copy(item.get("text", ""))
        except Exception as exc:
            QMessageBox.warning(self, "복사 실패", str(exc))

    def toggle_pin(self, item: dict) -> None:
        item["pinned"] = not item.get("pinned")
        config.save_clipboard_history(self.history)
        self.refresh()

    def delete_item(self, item: dict) -> None:
        self.history.get("history", []).remove(item)
        config.save_clipboard_history(self.history)
        self.refresh()


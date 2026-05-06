from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QDialog, QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout, QWidget

from app import config
from app.clipboard_watcher import ClipboardWatcher
from app.utils import new_id, now_iso, short_preview
from ui.common import GridPanel, add_card_actions, make_card


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
        self.list = GridPanel(columns=2)
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
        cards = []
        query = self.search.text().strip().lower()
        items = sorted(self.history.get("history", []), key=lambda item: (not item.get("pinned"), item.get("copied_at", "")), reverse=False)
        for item in items:
            text = item.get("text", "")
            if query and query not in text.lower():
                continue
            card = make_card("고정됨" if item.get("pinned") else item.get("copied_at", ""), short_preview(text, 160))
            add_card_actions(
                card,
                [
                    ("⧉", "복사", lambda checked=False, value=item: self.copy_item(value), False),
                    ("★" if item.get("pinned") else "☆", "핀 고정/해제", lambda checked=False, value=item: self.toggle_pin(value), False),
                    ("×", "삭제", lambda checked=False, value=item: self.delete_item(value), True),
                ],
            )
            cards.append(card)
        self.list.add_cards(cards)

    def copy_item(self, item: dict) -> None:
        QApplication.clipboard().setText(item.get("text", ""))

    def toggle_pin(self, item: dict) -> None:
        item["pinned"] = not item.get("pinned")
        config.save_clipboard_history(self.history)
        self.refresh()

    def delete_item(self, item: dict) -> None:
        self.history.get("history", []).remove(item)
        config.save_clipboard_history(self.history)
        self.refresh()

    def show_mini_popup(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("클립보드 이력")
        dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        dialog.resize(420, 360)
        layout = QVBoxLayout(dialog)
        panel = GridPanel(columns=1)
        cards = []
        for item in self.history.get("history", [])[:10]:
            card = make_card(item.get("copied_at", ""), short_preview(item.get("text", ""), 180))
            add_card_actions(card, [("⧉", "복사", lambda checked=False, value=item: self.copy_item(value), False)])
            cards.append(card)
        if not cards:
            cards.append(make_card("클립보드 이력이 없습니다.", "텍스트를 복사하면 이곳에 표시됩니다."))
        panel.add_cards(cards)
        layout.addWidget(panel)
        close_btn = QPushButton("닫기")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)
        dialog.exec()

from __future__ import annotations

import pyperclip
from PyQt6.QtWidgets import QHBoxLayout, QListWidget, QMessageBox, QPushButton, QTabWidget, QVBoxLayout, QWidget

from app.utils import new_id, normalize_hotkey, short_preview
from ui.common import TextItemDialog, add_widget_item, make_card


class PhraseTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.phrase_list = QListWidget()
        self.snippet_list = QListWidget()
        self.tabs.addTab(self.phrase_list, "일반 텍스트")
        self.tabs.addTab(self.snippet_list, "코드 스니펫")
        layout.addWidget(self.tabs, 1)
        buttons = QHBoxLayout()
        add_phrase = QPushButton("+ 상용구")
        add_snippet = QPushButton("+ 스니펫")
        add_phrase.clicked.connect(lambda: self.edit_item("phrases"))
        add_snippet.clicked.connect(lambda: self.edit_item("snippets"))
        buttons.addWidget(add_phrase)
        buttons.addWidget(add_snippet)
        layout.addLayout(buttons)

    def refresh(self) -> None:
        self._fill(self.phrase_list, "phrases", False)
        self._fill(self.snippet_list, "snippets", True)

    def _fill(self, list_widget: QListWidget, collection: str, code: bool) -> None:
        list_widget.clear()
        for item in self.main.data.get(collection, []):
            card = make_card(item.get("name", "(이름 없음)"), short_preview(item.get("text", "")), normalize_hotkey(item.get("hotkey")))
            row = QHBoxLayout()
            copy_btn = QPushButton("복사")
            edit_btn = QPushButton("편집")
            del_btn = QPushButton("삭제")
            copy_btn.clicked.connect(lambda checked=False, text=item.get("text", ""): self.copy_text(text))
            edit_btn.clicked.connect(lambda checked=False, value=item, col=collection, is_code=code: self.edit_item(col, value, is_code))
            del_btn.clicked.connect(lambda checked=False, value=item, col=collection: self.delete_item(col, value))
            row.addWidget(copy_btn)
            row.addWidget(edit_btn)
            row.addWidget(del_btn)
            card.layout().addLayout(row)
            add_widget_item(list_widget, card)

    def copy_text(self, text: str) -> None:
        try:
            pyperclip.copy(text)
        except Exception as exc:
            QMessageBox.warning(self, "복사 실패", str(exc))

    def edit_item(self, collection: str, item: dict | None = None, code: bool | None = None) -> None:
        is_code = collection == "snippets" if code is None else code
        dialog = TextItemDialog("스니펫 편집" if is_code else "상용구 편집", item, is_code)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        value = dialog.value()
        if not value.get("name"):
            QMessageBox.warning(self, "입력 확인", "이름을 입력해주세요.")
            return
        if not value.get("id"):
            value["id"] = new_id("sn" if is_code else "ph")
        items = self.main.data.setdefault(collection, [])
        if item in items:
            items[items.index(item)] = value
        else:
            items.append(value)
        self.main.save_data()

    def delete_item(self, collection: str, item: dict) -> None:
        if QMessageBox.question(self, "삭제", "선택한 항목을 삭제할까요?") != QMessageBox.StandardButton.Yes:
            return
        self.main.data.get(collection, []).remove(item)
        self.main.save_data()


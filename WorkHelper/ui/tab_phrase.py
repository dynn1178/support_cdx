from __future__ import annotations

from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.date_tools import render_date_template
from app.utils import new_id, normalize_hotkey, now_iso, short_preview
from ui.common import GridPanel, HotkeyFields, SortControls, TextItemDialog, add_card_actions, apply_manual_reorder, bump_usage, make_card


class TitleTemplateDialog(QDialog):
    def __init__(self, item: dict | None = None) -> None:
        super().__init__()
        self.setWindowTitle("제목 템플릿")
        self.item = item or {}
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.template = QTextEdit(self.item.get("template", "보고서_{yyyy-mm-dd}"))
        self.business_days = QCheckBox("일 단위 계산 시 영업일 기준")
        self.business_days.setChecked(bool(self.item.get("business_days", False)))
        self.hotkey = HotkeyFields(self.item.get("hotkey"))
        form.addRow("템플릿", self.template)
        form.addRow("옵션", self.business_days)
        form.addRow("단축키", self.hotkey)
        layout.addLayout(form)
        help_text = QLabel(
            "예시\n"
            "기본: {yyyy-mm-dd}\n"
            "계산: {yyyy-mm-dd+1D}, {yyyy-mm-dd-2W}, {yyyy-mm+1M}, {yyyy-q+1Q}, {yyyy+1Y}\n"
            "서식: yyyy, yy, qq, q, mm, m, ww, w, dd, d, ddd, dddd, aaa, aaaa\n"
            "조합: {yyyy년 m월 d일 dddd}, {yy.mm.dd(aaa)}, {yyyy년 qq}"
        )
        help_text.setObjectName("mutedText")
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("확인")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def value(self) -> dict:
        data = dict(self.item)
        data.update(
            {
                "name": short_preview(self.template.toPlainText(), 40) or "제목 템플릿",
                "template": self.template.toPlainText(),
                "business_days": self.business_days.isChecked(),
                "hotkey": self.hotkey.value(),
            }
        )
        return data


class PhraseTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        self.phrase_list = GridPanel(columns=2)
        self.snippet_list = GridPanel(columns=1)
        self.title_list = GridPanel(columns=1)
        self.tabs.addTab(self.phrase_list, "일반 텍스트")
        self.tabs.addTab(self.snippet_list, "코드 스니펫")
        self.tabs.addTab(self.title_list, "제목 생성")
        layout.addWidget(self.tabs, 1)
        buttons = QHBoxLayout()
        self.sort_controls = SortControls(self.refresh)
        add_phrase = QPushButton("+ 텍스트")
        add_snippet = QPushButton("+ 스니펫")
        add_title = QPushButton("+ 제목")
        add_phrase.clicked.connect(lambda: self.edit_item("phrases"))
        add_snippet.clicked.connect(lambda: self.edit_item("snippets"))
        add_title.clicked.connect(lambda: self.edit_title())
        buttons.addStretch(1)
        buttons.addWidget(self.sort_controls)
        buttons.addWidget(add_phrase)
        buttons.addWidget(add_snippet)
        buttons.addWidget(add_title)
        layout.addLayout(buttons)

    def refresh(self) -> None:
        self._fill(self.phrase_list, "phrases", False)
        self._fill(self.snippet_list, "snippets", True)
        self._fill_titles()

    def _fill(self, list_widget: GridPanel, collection: str, code: bool) -> None:
        cards = []
        collection_items = self.main.data.get(collection, [])
        items = self.sort_controls.sort_items(
            collection_items,
            lambda value: value.get("name") or value.get("text", ""),
        )
        for item in items:
            if collection == "phrases":
                card = make_card(short_preview(item.get("text", ""), 160), "", normalize_hotkey(item.get("hotkey")))
            else:
                card = make_card(item.get("name", "(이름 없음)"), short_preview(item.get("text", "")), normalize_hotkey(item.get("hotkey")))
            add_card_actions(
                card,
                [
                    ("copy", "복사", lambda checked=False, value=item: self.copy_text(value), False),
                    ("edit", "수정", lambda checked=False, value=item, col=collection, is_code=code: self.edit_item(col, value, is_code), False),
                    ("delete", "삭제", lambda checked=False, value=item, col=collection: self.delete_item(col, value), True),
                ],
            )
            cards.append(card)
        callback = (lambda old, new, source=collection_items, visible=items: self.reorder_items(source, visible, old, new)) if self.sort_controls.is_manual() and items else None
        list_widget.add_cards(cards, on_reorder=callback)

    def _fill_titles(self) -> None:
        cards = []
        collection_items = self.main.data.get("title_templates", [])
        items = self.sort_controls.sort_items(collection_items, lambda value: value.get("template", ""))
        for item in items:
            rendered = render_date_template(item.get("template", ""), business_days=bool(item.get("business_days", False)))
            card = make_card(rendered, "", normalize_hotkey(item.get("hotkey")))
            add_card_actions(
                card,
                [
                    ("copy", "생성된 제목 복사", lambda checked=False, value=item: self.copy_title(value), False),
                    ("edit", "수정", lambda checked=False, value=item: self.edit_title(value), False),
                    ("delete", "삭제", lambda checked=False, value=item: self.delete_title(value), True),
                ],
            )
            cards.append(card)
        if not cards:
            cards.append(make_card("템플릿 예시", "{yyyy-mm-dd}, {yyyy-mm-dd+1D}, {yyyy년 m월 d일 dddd} 처럼 입력할 수 있습니다."))
        callback = (lambda old, new, source=collection_items, visible=items: self.reorder_items(source, visible, old, new)) if self.sort_controls.is_manual() and items else None
        self.title_list.add_cards(cards, on_reorder=callback)

    def reorder_items(self, source: list[dict], visible: list[dict], old: int, new: int) -> None:
        apply_manual_reorder(source, visible, old, new)
        self.main.save_data()

    def copy_text(self, item: dict) -> None:
        bump_usage(item)
        QApplication.clipboard().setText(item.get("text", ""))
        self.main.save_data()

    def copy_title(self, item: dict) -> None:
        bump_usage(item)
        QApplication.clipboard().setText(render_date_template(item.get("template", ""), business_days=bool(item.get("business_days", False))))
        self.main.save_data()

    def edit_item(self, collection: str, item: dict | None = None, code: bool | None = None) -> None:
        is_code = collection == "snippets" if code is None else code
        require_name = collection != "phrases"
        dialog = TextItemDialog("스니펫 수정" if is_code else "상용구 수정", item, is_code, require_name=require_name)
        while dialog.exec() == dialog.DialogCode.Accepted:
            value = dialog.value()
            if require_name and not value.get("name"):
                QMessageBox.warning(dialog, "입력 확인", "이름을 지정해주세요.")
                continue
            if not value.get("text"):
                QMessageBox.warning(dialog, "입력 확인", "내용을 지정해주세요.")
                continue
            if not value.get("id"):
                value["id"] = new_id("sn" if is_code else "ph")
                value["created_at"] = now_iso()
                value["sort_order"] = len(self.main.data.setdefault(collection, []))
                value["usage_count"] = 0
            conflict = self.main.first_hotkey_conflict(candidate=value, original=item)
            if conflict:
                QMessageBox.warning(dialog, "단축키 충돌", conflict)
                continue
            items = self.main.data.setdefault(collection, [])
            if item in items:
                items[items.index(item)] = value
            else:
                items.append(value)
            self.main.save_data()
            return

    def edit_title(self, item: dict | None = None) -> None:
        dialog = TitleTemplateDialog(item)
        while dialog.exec() == dialog.DialogCode.Accepted:
            value = dialog.value()
            if not value.get("template"):
                QMessageBox.warning(dialog, "입력 확인", "템플릿을 지정해주세요.")
                continue
            if not value.get("id"):
                value["id"] = new_id("tt")
                value["created_at"] = now_iso()
                value["sort_order"] = len(self.main.data.setdefault("title_templates", []))
                value["usage_count"] = 0
            conflict = self.main.first_hotkey_conflict(candidate=value, original=item)
            if conflict:
                QMessageBox.warning(dialog, "단축키 충돌", conflict)
                continue
            items = self.main.data.setdefault("title_templates", [])
            if item in items:
                items[items.index(item)] = value
            else:
                items.append(value)
            self.main.save_data()
            return

    def delete_item(self, collection: str, item: dict) -> None:
        if QMessageBox.question(self, "삭제", "선택한 항목을 삭제할까요?") != QMessageBox.StandardButton.Yes:
            return
        self.main.data.get(collection, []).remove(item)
        self.main.save_data()

    def delete_title(self, item: dict) -> None:
        if QMessageBox.question(self, "삭제", "선택한 제목 템플릿을 삭제할까요?") != QMessageBox.StandardButton.Yes:
            return
        self.main.data.get("title_templates", []).remove(item)
        self.main.save_data()

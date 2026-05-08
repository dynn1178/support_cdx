from __future__ import annotations

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app import config
from app.date_tools import render_date_template
from app.utils import display_hotkey, new_id, now_iso, short_preview
from ui.common import (
    GridPanel,
    HotkeyFields,
    SortControls,
    TextItemDialog,
    apply_modern_dialog_style,
    ask_modern_question,
    add_card_actions,
    apply_manual_reorder,
    bump_usage,
    confirm_shift_digit_hotkey,
    make_card,
    make_icon_button,
    show_modern_info,
    show_modern_warning,
)


class TitleTemplateDialog(QDialog):
    def __init__(self, item: dict | None = None) -> None:
        super().__init__()
        self.setWindowTitle("제목 템플릿")
        apply_modern_dialog_style(self)
        self.item = item or {}
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.template = QTextEdit(self.item.get("template", "보고서 {yyyy-mm-dd}"))
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


class HotstringDialog(QDialog):
    def __init__(self, item: dict | None = None) -> None:
        super().__init__()
        self.setWindowTitle("핫스트링")
        apply_modern_dialog_style(self)
        self.item = item or {}
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.trigger = QLineEdit(self.item.get("trigger", ""))
        self.text = QTextEdit(self.item.get("text", ""))
        self.case_sensitive = QCheckBox("대소문자 구분")
        self.case_sensitive.setChecked(bool(self.item.get("case_sensitive", False)))
        form.addRow("입력 문자열", self.trigger)
        form.addRow("대체 텍스트", self.text)
        form.addRow("옵션", self.case_sensitive)
        layout.addLayout(form)
        help_text = QLabel("입력 문자열을 입력하면 대체 텍스트로 변환됩니다. 예시: gg. → google.com")
        help_text.setObjectName("mutedText")
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
                "trigger": self.trigger.text().strip(),
                "text": self.text.toPlainText(),
                "case_sensitive": self.case_sensitive.isChecked(),
            }
        )
        return data


class PhraseTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.sort_controls = SortControls(self.refresh)
        self.tabs = QTabWidget()
        self.tabs.setCornerWidget(self.sort_controls, Qt.Corner.TopRightCorner)
        self.phrase_list = GridPanel(columns=2)
        self.snippet_list = GridPanel(columns=1)
        self.hotstring_list = GridPanel(columns=2)
        self.title_list = GridPanel(columns=1)
        self.tabs.addTab(self.tab_page(self.phrase_list, "+ 텍스트", lambda: self.edit_item("phrases")), "일반 텍스트")
        self.tabs.addTab(self.tab_page(self.snippet_list, "+ 스니펫", lambda: self.edit_item("snippets")), "코드 스니펫")
        self.tabs.addTab(self.tab_page(self.title_list, "+ 제목", lambda: self.edit_title()), "제목 생성")
        self.tabs.addTab(self.tab_page(self.hotstring_list, "+ 핫스트링", lambda: self.edit_hotstring()), "핫스트링")
        layout.addWidget(self.tabs, 1)
        self.status_label = QLabel("")
        self.status_label.setObjectName("mutedText")

    def tab_page(self, panel: GridPanel, button_text: str, callback) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(panel, 1)
        buttons = QHBoxLayout()
        add_button = QPushButton(button_text)
        add_button.clicked.connect(callback)
        buttons.addStretch(1)
        buttons.addWidget(add_button)
        layout.addLayout(buttons)
        return page

    def refresh(self) -> None:
        self._fill(self.phrase_list, "phrases", False)
        self._fill(self.snippet_list, "snippets", True)
        self._fill_hotstrings()
        self._fill_titles()

    def _fill(self, list_widget: GridPanel, collection: str, code: bool) -> None:
        cards = []
        collection_items = self.main.data.get(collection, [])
        items = self.sort_controls.sort_items(collection_items, lambda value: value.get("name") or value.get("text", ""))
        for item in items:
            if collection == "phrases":
                card = make_card(short_preview(item.get("text", ""), 160), "", display_hotkey(item.get("hotkey")), card_size="a")
            else:
                card = make_card(item.get("name", "(이름 없음)"), short_preview(item.get("text", "")), display_hotkey(item.get("hotkey")), card_size="b")
            self.add_phrase_actions(card, item, collection, code)
            cards.append(card)
        callback = (lambda old, new, source=collection_items, visible=items: self.reorder_items(source, visible, old, new)) if self.sort_controls.is_manual() and items else None
        list_widget.add_cards(cards, on_reorder=callback)

    def _fill_hotstrings(self) -> None:
        cards = []
        collection_items = self.main.data.get("hotstrings", [])
        items = self.sort_controls.sort_items(collection_items, lambda value: value.get("trigger", ""))
        for item in items:
            trigger = item.get("trigger", "")
            card = make_card(short_preview(item.get("text", ""), 160), "", f"[{trigger.lower()}]", single_line=True, card_size="a")
            add_card_actions(
                card,
                [
                    ("copy", "대체 텍스트 복사", lambda checked=False, value=item: self.copy_hotstring(value), False),
                    ("edit", "수정", lambda checked=False, value=item: self.edit_hotstring(value), False),
                    ("delete", "삭제", lambda checked=False, value=item: self.delete_hotstring(value), True),
                ],
            )
            cards.append(card)
        callback = (lambda old, new, source=collection_items, visible=items: self.reorder_items(source, visible, old, new)) if self.sort_controls.is_manual() and items else None
        self.hotstring_list.add_cards(cards, on_reorder=callback)

    def _fill_titles(self) -> None:
        cards = []
        collection_items = self.main.data.get("title_templates", [])
        items = self.sort_controls.sort_items(collection_items, lambda value: value.get("template", ""))
        for item in items:
            rendered = render_date_template(item.get("template", ""), business_days=bool(item.get("business_days", False)))
            card = make_card(rendered, "", display_hotkey(item.get("hotkey")), card_size="a")
            self.add_title_actions(card, item)
            cards.append(card)
        if not cards:
            cards.append(make_card("템플릿 예시", "{yyyy-mm-dd}, {yyyy-mm-dd+1D}, {yyyy년 m월 d일 dddd} 처럼 입력할 수 있습니다.", card_size="a"))
        callback = (lambda old, new, source=collection_items, visible=items: self.reorder_items(source, visible, old, new)) if self.sort_controls.is_manual() and items else None
        self.title_list.add_cards(cards, on_reorder=callback)

    def reorder_items(self, source: list[dict], visible: list[dict], old: int, new: int) -> None:
        apply_manual_reorder(source, visible, old, new)
        self.main.save_data()

    def copy_text(self, item: dict) -> None:
        bump_usage(item)
        QApplication.clipboard().setText(item.get("text", ""))
        self.main.save_data()

    def add_phrase_actions(self, card: QWidget, item: dict, collection: str, code: bool) -> None:
        row = QHBoxLayout()
        row.setContentsMargins(0, 2, 0, 0)
        status = QLabel("")
        status.setStyleSheet("color: #168A4A; font-weight: 700;")
        row.addWidget(status, 1)
        row.addWidget(make_icon_button("copy", "복사", lambda checked=False, value=item: self.copy_text(value)))
        pin = make_icon_button("pin", "상용구 팝업 즐겨찾기", lambda checked=False, value=item, label=status: self.toggle_popup_favorite(value, label, pin))
        if item.get("id") in self.main.data.get("phrase_popup_favorites", []):
            pin.setStyleSheet("QToolButton#iconButton { color: #F5B301; font-size: 13pt; font-weight: 900; }")
        row.addWidget(pin)
        row.addWidget(make_icon_button("edit", "수정", lambda checked=False, value=item, col=collection, is_code=code: self.edit_item(col, value, is_code)))
        row.addWidget(make_icon_button("delete", "삭제", lambda checked=False, value=item, col=collection: self.delete_item(col, value), True))
        card.layout().addLayout(row)

    def add_title_actions(self, card: QWidget, item: dict) -> None:
        row = QHBoxLayout()
        row.setContentsMargins(0, 2, 0, 0)
        status = QLabel("")
        status.setStyleSheet("color: #168A4A; font-weight: 700;")
        row.addWidget(status, 1)
        row.addWidget(make_icon_button("copy", "생성한 제목 복사", lambda checked=False, value=item: self.copy_title(value)))
        pin = make_icon_button("pin", "상용구 팝업 즐겨찾기", lambda checked=False, value=item, label=status: self.toggle_popup_favorite(value, label, pin))
        if item.get("id") in self.main.data.get("phrase_popup_favorites", []):
            pin.setStyleSheet("QToolButton#iconButton { color: #F5B301; font-size: 13pt; font-weight: 900; }")
        row.addWidget(pin)
        row.addWidget(make_icon_button("edit", "수정", lambda checked=False, value=item: self.edit_title(value)))
        row.addWidget(make_icon_button("delete", "삭제", lambda checked=False, value=item: self.delete_title(value), True))
        card.layout().addLayout(row)

    def toggle_popup_favorite(self, item: dict, status_label: QLabel | None = None, button: QWidget | None = None) -> None:
        favorites = self.main.data.setdefault("phrase_popup_favorites", [])
        item_id = item.get("id")
        if not item_id:
            return
        if item_id in favorites:
            favorites.remove(item_id)
            if button is not None:
                button.setStyleSheet("QToolButton#iconButton { color: #A3A8B3; font-size: 13pt; font-weight: 900; }")
        elif len(favorites) < 10:
            favorites.append(item_id)
            if button is not None:
                button.setStyleSheet("QToolButton#iconButton { color: #F5B301; font-size: 13pt; font-weight: 900; }")
            self.show_status("상용구 미니팝업 등록 완료", status_label)
        else:
            show_modern_info(self, "즐겨찾기", "상용구 미니팝업은 최대 10개까지 등록할 수 있습니다.")
            return
        self.main.data["settings"] = self.main.settings
        config.save_template(self.main.template_index, self.main.data)
        config.save_settings(self.main.settings)
        QTimer.singleShot(1000, self.refresh)

    def show_status(self, text: str, status_label: QLabel | None = None) -> None:
        target = status_label or self.status_label
        target.setText(text)
        QTimer.singleShot(1000, target.clear)

    def copy_hotstring(self, item: dict) -> None:
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
                show_modern_warning(dialog, "입력 확인", "이름을 지정해주세요.")
                continue
            if not value.get("text"):
                show_modern_warning(dialog, "입력 확인", "내용을 지정해주세요.")
                continue
            if not value.get("id"):
                value["id"] = new_id("sn" if is_code else "ph")
                value["created_at"] = now_iso()
                value["sort_order"] = len(self.main.data.setdefault(collection, []))
                value["usage_count"] = 0
            conflict = self.main.first_hotkey_conflict(candidate=value, original=item)
            if conflict:
                show_modern_warning(dialog, "단축키 충돌", conflict)
                continue
            if not confirm_shift_digit_hotkey(dialog, value.get("hotkey")):
                continue
            items = self.main.data.setdefault(collection, [])
            if item in items:
                items[items.index(item)] = value
            else:
                items.append(value)
            self.main.save_data()
            return

    def edit_hotstring(self, item: dict | None = None) -> None:
        dialog = HotstringDialog(item)
        while dialog.exec() == dialog.DialogCode.Accepted:
            value = dialog.value()
            if not value.get("trigger"):
                show_modern_warning(dialog, "입력 확인", "입력 문자열을 지정해주세요.")
                continue
            if not value.get("text"):
                show_modern_warning(dialog, "입력 확인", "대체 텍스트를 지정해주세요.")
                continue
            if not value.get("id"):
                value["id"] = new_id("hs")
                value["created_at"] = now_iso()
                value["sort_order"] = len(self.main.data.setdefault("hotstrings", []))
                value["usage_count"] = 0
            items = self.main.data.setdefault("hotstrings", [])
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
                show_modern_warning(dialog, "입력 확인", "템플릿을 지정해주세요.")
                continue
            if not value.get("id"):
                value["id"] = new_id("tt")
                value["created_at"] = now_iso()
                value["sort_order"] = len(self.main.data.setdefault("title_templates", []))
                value["usage_count"] = 0
            conflict = self.main.first_hotkey_conflict(candidate=value, original=item)
            if conflict:
                show_modern_warning(dialog, "단축키 충돌", conflict)
                continue
            if not confirm_shift_digit_hotkey(dialog, value.get("hotkey")):
                continue
            items = self.main.data.setdefault("title_templates", [])
            if item in items:
                items[items.index(item)] = value
            else:
                items.append(value)
            self.main.save_data()
            return

    def delete_item(self, collection: str, item: dict) -> None:
        if not ask_modern_question(self, "삭제", "선택한 항목을 삭제할까요?", "#D7263D", "삭제", "취소"):
            return
        self.main.data.get(collection, []).remove(item)
        self.main.save_data()

    def delete_title(self, item: dict) -> None:
        if not ask_modern_question(self, "삭제", "선택한 제목 템플릿을 삭제할까요?", "#D7263D", "삭제", "취소"):
            return
        self.main.data.get("title_templates", []).remove(item)
        self.main.save_data()

    def delete_hotstring(self, item: dict) -> None:
        if not ask_modern_question(self, "삭제", "선택한 핫스트링을 삭제할까요?", "#D7263D", "삭제", "취소"):
            return
        self.main.data.get("hotstrings", []).remove(item)
        self.main.save_data()

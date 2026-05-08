from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.utils import display_hotkey, short_preview
from ui.common import GridPanel, make_card


class HomeTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.summary = GridPanel(columns=4)
        self.summary.setFixedHeight(126)
        self.summary.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.hotkeys = GridPanel(columns=2)
        label = QLabel("등록된 단축키")
        label.setObjectName("cardTitle")
        layout.addWidget(self.summary)
        layout.addWidget(label)
        layout.addWidget(self.hotkeys, 2)

    def refresh(self) -> None:
        data = self.main.data
        stats = [
            ("상용구", len(data.get("phrases", [])), "일반 텍스트"),
            ("코드", len(data.get("snippets", [])), "코드 스니펫"),
            ("바로가기", len(data.get("launchers", [])), "사이트/파일"),
            ("컨닝페이퍼", len(data.get("images", [])), "이미지 자료"),
            ("매크로", len(data.get("macros", [])), "녹화/재생"),
            ("클립보드", len(getattr(self.main.clipboard_tab, "history", {}).get("history", [])), "복사 이력"),
            ("메모", len(data.get("memos", [])), "빠른 메모"),
            ("일정", len(data.get("schedules", [])), "알림"),
        ]
        self.summary.add_cards([make_card(name, f"{count}개 · {desc}", compact=True, card_height=48) for name, count, desc in stats])

        hotkey_cards = []
        sections = [
            (data.get("phrases", []), lambda item: item.get("text") or item.get("name", "")),
            (data.get("snippets", []), lambda item: item.get("text") or item.get("name", "")),
            (data.get("title_templates", []), lambda item: item.get("template", "")),
            (data.get("launchers", []), lambda item: item.get("name") or item.get("description") or item.get("url") or item.get("path", "")),
            (data.get("images", []), lambda item: item.get("name") or item.get("path", "")),
            (data.get("macros", []), lambda item: item.get("name") or f"{len(item.get('actions', []))}개 액션"),
        ]
        for items, content in sections:
            for item in items:
                key = display_hotkey(item.get("hotkey"))
                if key:
                    hotkey_cards.append(make_card(short_preview(content(item), 90), "", key, single_line=True, compact=True, card_height=46))

        popup_label = self.main.clipboard_popup_shortcut_label()
        if popup_label:
            hotkey_cards.append(make_card("최근 복사 이력 미니팝업", "", popup_label, single_line=True, compact=True, card_height=46))
        if not hotkey_cards:
            hotkey_cards.append(make_card("등록된 단축키 없음", "각 기능 화면에서 단축키를 지정할 수 있습니다.", compact=True, card_height=56))
        self.hotkeys.add_cards(hotkey_cards)

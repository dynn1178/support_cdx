from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

from app.macro_script import count_steps
from app.theme import THEMES
from app.utils import display_hotkey, short_preview
from ui.common import GridPanel, make_card

MAX_SECTION_ROWS = 8


class HomeTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(8)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(10)
        self.memo_list = QListWidget()
        self.timer_list = QListWidget()
        self.schedule_list = QListWidget()
        top.addWidget(self.registered_section("메모", self.memo_list, self.create_memo), 1)
        top.addWidget(self.registered_section("타이머", self.timer_list, self.create_timer), 1)
        top.addWidget(self.registered_section("일정", self.schedule_list, self.create_schedule), 1)

        self.memo_list.itemDoubleClicked.connect(lambda list_item: self._open_registered(list_item, self.main.memo_tab.edit_memo))
        self.timer_list.itemDoubleClicked.connect(lambda list_item: self._open_registered(list_item, self.main.todo_tab.edit_timer_preset))
        self.schedule_list.itemDoubleClicked.connect(lambda list_item: self._open_registered(list_item, self.main.todo_tab.edit_item))

        top_holder = QWidget()
        top_holder.setLayout(top)
        top_holder.setFixedHeight(132)  # 기존 220의 60%

        hotkey_label = QLabel("등록 단축키")
        hotkey_label.setObjectName("cardTitle")
        self.hotkeys = GridPanel(columns=2)
        self.hotkeys.setMinimumHeight(160)

        layout.addWidget(top_holder)
        layout.addWidget(hotkey_label)
        layout.addWidget(self.hotkeys, 1)
        self._style_registered_lists()

    def registered_section(self, title: str, list_widget: QListWidget, on_add) -> QWidget:
        card = QWidget()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(4)
        header = QHBoxLayout()
        header.setSpacing(6)
        title_label = QLabel(f"{title} 등록")
        title_label.setObjectName("cardTitle")
        add_btn = QPushButton("+")
        add_btn.setToolTip(f"{title} 등록")
        add_btn.setFixedSize(22, 20)
        add_btn.setStyleSheet("QPushButton { padding: 0; font-weight: 800; }")
        add_btn.clicked.connect(on_add)
        header.addWidget(title_label, 1)
        header.addWidget(add_btn)
        layout.addLayout(header)
        list_widget.setSpacing(0)
        list_widget.setUniformItemSizes(True)
        list_widget.setToolTip("더블클릭하면 편집창이 열립니다.")
        list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        list_widget.setTextElideMode(Qt.TextElideMode.ElideRight)
        font = list_widget.font()
        font.setPointSize(9)
        list_widget.setFont(font)
        layout.addWidget(list_widget, 1)
        return card

    def _style_registered_lists(self) -> None:
        colors = self._theme()
        style = (
            "QListWidget { border: none; background: transparent; font-size: 9pt; }"
            f"QListWidget::item {{ padding: 0px 4px; color: {colors['text']}; }}"
            f"QListWidget::item:selected {{ background: {colors['hover']}; color: {colors['text']}; }}"
            f"QListWidget::item:hover:!selected {{ background: {colors['hover']}; }}"
        )
        for list_widget in (self.memo_list, self.timer_list, self.schedule_list):
            list_widget.setStyleSheet(style)

    def apply_theme(self) -> None:
        self._style_registered_lists()
        self.refresh_hotkeys()

    def _open_registered(self, list_item: QListWidgetItem, handler) -> None:
        data = list_item.data(Qt.ItemDataRole.UserRole)
        if data is not None:
            handler(data)

    def _fill_list(self, list_widget: QListWidget, entries: list[tuple[str, dict]], empty_text: str) -> None:
        list_widget.clear()
        row_height = list_widget.fontMetrics().height()
        if not entries:
            placeholder = QListWidgetItem(empty_text)
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            placeholder.setSizeHint(QSize(0, row_height))
            list_widget.addItem(placeholder)
            return
        for text, item in entries[:MAX_SECTION_ROWS]:
            list_item = QListWidgetItem(text)
            list_item.setData(Qt.ItemDataRole.UserRole, item)
            list_item.setToolTip(text)
            list_item.setSizeHint(QSize(0, row_height))
            list_widget.addItem(list_item)

    def create_memo(self) -> None:
        self.main.memo_tab.edit_memo(None)

    def create_timer(self) -> None:
        self.main.todo_tab.edit_timer_preset(None)

    def create_schedule(self) -> None:
        self.main.todo_tab.edit_item(None)

    def _timer_summary(self, item: dict) -> str:
        if item.get("mode") == "exact":
            return f"{item.get('target_date', '')} {int(item.get('target_hour', 0) or 0):02d}:{int(item.get('target_minute', 0) or 0):02d}"
        h, m, s = int(item.get("hours", 0) or 0), int(item.get("minutes", 0) or 0), int(item.get("seconds", 0) or 0)
        parts = []
        if h:
            parts.append(f"{h}시간")
        if m:
            parts.append(f"{m}분")
        if s:
            parts.append(f"{s}초")
        return " ".join(parts) or "0초"

    def refresh_memos(self) -> None:
        memos = sorted(self.main.data.get("memos", []), key=lambda entry: entry.get("created_at", ""), reverse=True)
        entries = [(f"{memo.get('title') or '(제목 없음)'}  —  {short_preview(memo.get('content', ''), 20)}", memo) for memo in memos]
        self._fill_list(self.memo_list, entries, "등록된 메모가 없습니다.")

    def refresh_timers(self) -> None:
        timers = sorted(self.main.data.get("timers", []), key=lambda entry: entry.get("created_at", ""), reverse=True)
        entries = [(f"{timer.get('label') or '(이름 없음)'}  —  {self._timer_summary(timer)}", timer) for timer in timers]
        self._fill_list(self.timer_list, entries, "등록된 타이머가 없습니다.")

    def refresh_schedules(self) -> None:
        parsed = []
        for schedule in self.main.data.get("schedules", []):
            if schedule.get("completed"):
                continue
            try:
                target = datetime.fromisoformat(schedule.get("datetime", ""))
            except Exception:
                continue
            parsed.append((target, schedule))
        parsed.sort(key=lambda pair: pair[0])  # 만료(마감)가 가까운 순
        entries = [(f"{short_preview(schedule.get('title', ''), 20) or '일정'}  —  {target.strftime('%m/%d %H:%M')}", schedule) for target, schedule in parsed]
        self._fill_list(self.schedule_list, entries, "등록된 일정이 없습니다.")

    def _theme(self) -> dict:
        theme_name = getattr(self.main, "settings", {}).get("theme", "light")
        return THEMES.get(theme_name, THEMES["light"])

    def setting_hotkey_cards(self) -> list[QWidget]:
        settings = self.main.settings
        colors = self._theme()
        content = colors.get("content", "#F7F8FA")
        border = colors.get("border", "#B9C0CC")
        text = colors.get("text", "#1F2433")
        cards = []

        def system_card(label: str, hotkey_label: str) -> QWidget:
            card = make_card(label, "", hotkey_label, single_line=True, compact=True, card_height=46, inline_hotkey=True)
            card.setStyleSheet(
                f"QWidget#card {{ background: {content}; border: 1px solid {border}; }}"
                f"QLabel#keyCap {{ background: transparent; border: 1px solid {border}; color: {text}; }}"
            )
            return card

        clipboard_label = self.main.clipboard_popup_shortcut_label()
        if clipboard_label:
            cards.append(system_card("클립보드 미니팝업", clipboard_label))
        quick_memo_label = self.main.quick_memo_shortcut_label()
        if quick_memo_label:
            cards.append(system_card("빠른 메모", quick_memo_label))
        phrase_popup_label = display_hotkey(settings.get("phrase_popup_hotkey"))
        if phrase_popup_label:
            cards.append(system_card("상용구 미니팝업", phrase_popup_label))
        steel_cut_label = display_hotkey(settings.get("steel_cut_hotkey"))
        if steel_cut_label:
            cards.append(system_card("스틸컷 촬영", steel_cut_label))
        return cards

    def single_line_preview(self, text: str, limit: int = 90) -> str:
        lines = text.splitlines()
        first_line = lines[0] if lines else text
        suffix = "..." if len(lines) > 1 else ""
        preview = short_preview(first_line, max(1, limit - len(suffix)))
        return f"{preview}{suffix}" if suffix and not preview.endswith("...") else preview

    def _is_recent(self, item: dict, hours: int = 24) -> bool:
        try:
            created = datetime.fromisoformat(str(item.get("created_at", "")))
        except Exception:
            return False
        return (datetime.now() - created).total_seconds() < hours * 3600

    def refresh_hotkeys(self) -> None:
        data = self.main.data
        colors = self._theme()
        hotkey_cards = self.setting_hotkey_cards()
        sections = [
            (data.get("phrases", []), lambda item: item.get("text") or item.get("name", "")),
            (data.get("snippets", []), lambda item: item.get("text") or item.get("name", "")),
            (data.get("title_templates", []), lambda item: item.get("template", "")),
            (data.get("launchers", []), lambda item: item.get("name") or item.get("url") or item.get("path", "")),
            (data.get("images", []), lambda item: item.get("name") or item.get("path", "")),
            (data.get("macros", []), lambda item: item.get("name") or f"{count_steps(item.get('script', ''))}줄"),
            (data.get("process_hotkeys", []), lambda item: item.get("name") or item.get("process_exe", "")),
        ]
        for items, content in sections:
            for item in items:
                key = display_hotkey(item.get("hotkey"))
                if not key:
                    continue
                card = make_card(self.single_line_preview(content(item), 90), "", key, single_line=True, compact=True, card_height=46, title_bold=False, inline_hotkey=True)
                if self._is_recent(item):
                    card.setStyleSheet(f"QWidget#card {{ background: {colors['hover']}; border: 1px solid {colors['accent']}; }}")
                hotkey_cards.append(card)
        if not hotkey_cards:
            hotkey_cards.append(make_card("등록된 단축키 없음", "각 기능 화면에서 단축키를 지정할 수 있습니다.", compact=True, card_height=56))
        self.hotkeys.add_cards(hotkey_cards)

    def refresh(self) -> None:
        self.refresh_memos()
        self.refresh_timers()
        self.refresh_schedules()
        self.refresh_hotkeys()

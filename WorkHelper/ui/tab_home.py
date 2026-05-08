from __future__ import annotations

from datetime import datetime
from typing import Callable

from PyQt6.QtWidgets import QLabel, QHBoxLayout, QVBoxLayout, QWidget

from app import config
from app.utils import display_hotkey, short_preview
from ui.common import GridPanel, make_card


COLLECTION_META: dict[str, tuple[str, str, Callable[[dict], str], Callable[[dict], str]]] = {
    "phrases": ("상용구", "문구", lambda item: short_preview(item.get("text", ""), 30) or item.get("name", ""), lambda item: item.get("name", "")),
    "snippets": ("코드", "코드", lambda item: short_preview(item.get("text", ""), 30) or item.get("name", ""), lambda item: item.get("name", "")),
    "hotstrings": ("핫스트링", "자동", lambda item: short_preview(item.get("text", ""), 30) or item.get("trigger", ""), lambda item: item.get("trigger", "")),
    "title_templates": ("제목", "제목", lambda item: short_preview(item.get("template", ""), 30) or item.get("name", ""), lambda item: item.get("name", "")),
    "launchers": ("바로가기", "링크", lambda item: item.get("url") or item.get("path", "") or item.get("name", ""), lambda item: item.get("name", "")),
    "images": ("이미지", "이미지", lambda item: item.get("path", "") or item.get("name", "이미지"), lambda item: item.get("name", "")),
    "macros": ("매크로", "매크로", lambda item: f"{len(item.get('actions', []))}개 액션", lambda item: item.get("name", "")),
    "memos": ("메모", "메모", lambda item: short_preview(item.get("content", ""), 30) or item.get("title", "메모"), lambda item: item.get("title", "")),
}


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
        self.recent_body = QVBoxLayout()
        self.frequent_body = QVBoxLayout()
        self.schedule_body = QVBoxLayout()
        top.addWidget(self.section("최근 사용", self.recent_body), 1)
        top.addWidget(self.section("자주 사용", self.frequent_body), 1)
        top.addWidget(self.section("등록 일정", self.schedule_body), 1)

        top_holder = QWidget()
        top_holder.setLayout(top)
        top_holder.setFixedHeight(148)

        hotkey_label = QLabel("등록 단축키")
        hotkey_label.setObjectName("cardTitle")
        self.hotkeys = GridPanel(columns=2)

        layout.addWidget(top_holder)
        layout.addWidget(hotkey_label)
        layout.addWidget(self.hotkeys, 1)

    def section(self, title: str, body: QVBoxLayout) -> QWidget:
        card = QWidget()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        layout.addWidget(title_label)
        body.setContentsMargins(0, 2, 0, 0)
        body.setSpacing(2)
        layout.addLayout(body)
        layout.addStretch(1)
        return card

    def clear_layout(self, layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def usage_items(self) -> list[dict]:
        items = []
        for collection in config.PRESET_COLLECTION_KEYS:
            meta = COLLECTION_META.get(collection)
            if not meta:
                continue
            label, badge, title_func, desc_func = meta
            for item in self.main.data.get(collection, []):
                items.append(
                    {
                        "collection": collection,
                        "label": label,
                        "badge": badge,
                        "title": title_func(item) or label,
                        "desc": desc_func(item),
                        "item": item,
                    }
                )
        return items

    def usage_row(self, entry: dict, right_text: str) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        title = QLabel(f"[{entry['badge']}] {short_preview(entry['title'], 18)}")
        title.setToolTip(f"{entry['label']} - {entry['title']}\n{entry['desc']}")
        title.setMinimumWidth(0)
        right = QLabel(right_text)
        right.setObjectName("cardSubtitle")
        layout.addWidget(title, 1)
        layout.addWidget(right)
        return row

    def empty_row(self, text: str) -> QWidget:
        label = QLabel(text)
        label.setObjectName("cardSubtitle")
        label.setWordWrap(True)
        return label

    def relative_used_time(self, value: str) -> str:
        try:
            delta = datetime.now() - datetime.fromisoformat(value)
        except Exception:
            return ""
        minutes = max(0, int(delta.total_seconds() // 60))
        if minutes < 1:
            return "방금"
        if minutes < 60:
            return f"{minutes}분"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}시간"
        return f"{hours // 24}일"

    def schedule_right_text(self, target: datetime) -> str:
        if target.date() == datetime.now().date():
            minutes = int((target - datetime.now()).total_seconds() // 60)
            if minutes >= 60:
                return f"{minutes // 60}h"
            if minutes >= 0:
                return f"{minutes}m"
            return "지남"
        days = (target.date() - datetime.now().date()).days
        return f"D-{days}" if days >= 0 else f"D+{abs(days)}"

    def refresh_recent(self, items: list[dict]) -> None:
        recent = sorted(
            [entry for entry in items if entry["item"].get("last_used_at")],
            key=lambda entry: entry["item"].get("last_used_at", ""),
            reverse=True,
        )[:5]
        if not recent:
            self.recent_body.addWidget(self.empty_row("사용 기록 없음"))
            return
        for entry in recent:
            self.recent_body.addWidget(self.usage_row(entry, self.relative_used_time(entry["item"].get("last_used_at", ""))))

    def refresh_frequent(self, items: list[dict]) -> None:
        today = datetime.now().date().isoformat()
        today_items = [
            entry for entry in items
            if entry["item"].get("used_today_date") == today and int(entry["item"].get("used_today_count", 0) or 0) > 0
        ]
        today_items.sort(key=lambda entry: int(entry["item"].get("used_today_count", 0) or 0), reverse=True)
        if not today_items:
            self.frequent_body.addWidget(self.empty_row("오늘 기록 없음"))
            return
        for index, entry in enumerate(today_items[:5], start=1):
            count = int(entry["item"].get("used_today_count", 0) or 0)
            self.frequent_body.addWidget(self.usage_row(entry, f"{index}위 {count}회"))

    def refresh_schedules(self) -> None:
        parsed = []
        for schedule in self.main.data.get("schedules", []):
            try:
                target = datetime.fromisoformat(schedule.get("datetime", ""))
            except Exception:
                continue
            parsed.append((target, schedule))
        parsed.sort(key=lambda pair: pair[0], reverse=True)
        if not parsed:
            self.schedule_body.addWidget(self.empty_row("등록 일정 없음"))
            return
        for target, schedule in parsed[:5]:
            entry = {
                "collection": "schedules",
                "label": "일정",
                "badge": "일정",
                "title": short_preview(schedule.get("memo", ""), 30) or schedule.get("title") or "일정",
                "desc": schedule.get("title", ""),
                "item": schedule,
            }
            when = target.strftime("%m-%d %H:%M")
            self.schedule_body.addWidget(self.usage_row(entry, f"{when} {self.schedule_right_text(target)}"))

    def setting_hotkey_cards(self) -> list[QWidget]:
        settings = self.main.settings
        cards = []
        clipboard_label = self.main.clipboard_popup_shortcut_label()
        if clipboard_label:
            cards.append(make_card("클립보드 미니팝업", "", clipboard_label, single_line=True, compact=True, card_height=46))
        quick_memo_label = self.main.quick_memo_shortcut_label()
        if quick_memo_label:
            cards.append(make_card("빠른 메모", "", quick_memo_label, single_line=True, compact=True, card_height=46))
        phrase_popup_label = display_hotkey(settings.get("phrase_popup_hotkey"))
        if phrase_popup_label:
            cards.append(make_card("상용구 미니팝업", "", phrase_popup_label, single_line=True, compact=True, card_height=46))
        return cards

    def single_line_preview(self, text: str, limit: int = 90) -> str:
        lines = text.splitlines()
        first_line = lines[0] if lines else text
        suffix = "..." if len(lines) > 1 else ""
        preview = short_preview(first_line, max(1, limit - len(suffix)))
        return f"{preview}{suffix}" if suffix and not preview.endswith("...") else preview

    def refresh_hotkeys(self) -> None:
        data = self.main.data
        hotkey_cards = self.setting_hotkey_cards()
        sections = [
            (data.get("phrases", []), lambda item: item.get("text") or item.get("name", "")),
            (data.get("snippets", []), lambda item: item.get("text") or item.get("name", "")),
            (data.get("title_templates", []), lambda item: item.get("template", "")),
            (data.get("launchers", []), lambda item: item.get("name") or item.get("url") or item.get("path", "")),
            (data.get("images", []), lambda item: item.get("name") or item.get("path", "")),
            (data.get("macros", []), lambda item: item.get("name") or f"{len(item.get('actions', []))}개 액션"),
        ]
        for items, content in sections:
            for item in items:
                key = display_hotkey(item.get("hotkey"))
                if key:
                    hotkey_cards.append(make_card(self.single_line_preview(content(item), 90), "", key, single_line=True, compact=True, card_height=46))
        if not hotkey_cards:
            hotkey_cards.append(make_card("등록된 단축키 없음", "각 기능 화면에서 단축키를 지정할 수 있습니다.", compact=True, card_height=56))
        self.hotkeys.add_cards(hotkey_cards)

    def refresh(self) -> None:
        for body in [self.recent_body, self.frequent_body, self.schedule_body]:
            self.clear_layout(body)
        items = self.usage_items()
        self.refresh_recent(items)
        self.refresh_frequent(items)
        self.refresh_schedules()
        self.refresh_hotkeys()

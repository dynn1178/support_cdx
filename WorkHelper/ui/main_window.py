from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QLabel, QMainWindow, QMessageBox, QStackedWidget, QToolButton, QVBoxLayout, QWidget, QHBoxLayout

from app import config
from app.hotkey_manager import HotkeyManager
from app.theme import apply_theme
from app.update_checker import check_update_dialog
from ui.tab_clipboard import ClipboardTab
from ui.tab_image import ImageTab
from ui.tab_launcher import LauncherTab
from ui.tab_macro import MacroTab
from ui.tab_memo import MemoTab
from ui.tab_phrase import PhraseTab
from ui.tab_settings import SettingsTab


class MainWindow(QMainWindow):
    def __init__(self, app) -> None:
        super().__init__()
        config.ensure_data_files()
        self.app = app
        self.version = config.read_version()
        self.template_index = 1
        self.data = config.load_template(self.template_index)
        self.hotkeys = HotkeyManager()
        self._notified_schedule_ids: set[str] = set()
        self.setWindowTitle(f"{config.APP_NAME} {self.version}")
        self._build_ui()
        self.apply_current_settings()
        self.refresh_all_tabs()
        self.register_hotkeys()
        self.schedule_timer = QTimer(self)
        self.schedule_timer.timeout.connect(self.check_schedules)
        self.schedule_timer.start(60_000)
        QTimer.singleShot(1500, lambda: check_update_dialog(self, self.version))

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)
        header = QHBoxLayout()
        title = QLabel(f"업무 보조 프로그램  v{self.version}")
        title.setStyleSheet("font-weight: 700;")
        header.addWidget(title, 1)
        root.addLayout(header)
        self.stack = QStackedWidget()
        self.tabs = [
            PhraseTab(self),
            LauncherTab(self),
            ImageTab(self),
            MacroTab(self),
            ClipboardTab(self),
            MemoTab(self),
            SettingsTab(self),
        ]
        for tab in self.tabs:
            self.stack.addWidget(tab)
        root.addWidget(self.stack, 1)
        tabbar = QHBoxLayout()
        names = ["상용구", "바로가기", "이미지", "매크로", "클립보드", "메모", "설정"]
        self.buttons: list[QToolButton] = []
        for i, name in enumerate(names):
            button = QToolButton()
            button.setText(name)
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, index=i: self.set_tab(index))
            self.buttons.append(button)
            tabbar.addWidget(button)
        root.addLayout(tabbar)
        self.setCentralWidget(central)
        self.set_tab(0)

    def set_tab(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        for i, button in enumerate(self.buttons):
            button.setChecked(i == index)

    def apply_current_settings(self) -> None:
        settings = self.data.get("settings", {})
        window = settings.get("window", {})
        self.setFixedSize(int(window.get("width", 400)), int(window.get("height", 700)))
        flags = self.windowFlags()
        if window.get("always_on_top"):
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        apply_theme(self.app, settings.get("theme", "light"), settings.get("font_family", "맑은 고딕"), settings.get("font_size", 9))

    def save_data(self) -> None:
        config.save_template(self.template_index, self.data)
        self.register_hotkeys()
        self.refresh_all_tabs()

    def refresh_all_tabs(self) -> None:
        for tab in self.tabs:
            if hasattr(tab, "refresh"):
                tab.refresh()

    def change_template(self, index: int) -> None:
        self.template_index = index
        self.data = config.load_template(index)
        self.apply_current_settings()
        self.register_hotkeys()
        self.refresh_all_tabs()

    def register_hotkeys(self) -> None:
        self.hotkeys.unregister_all()
        for item in self.data.get("phrases", []) + self.data.get("snippets", []):
            hotkey = item.get("hotkey")
            if not hotkey:
                continue
            self.hotkeys.register(hotkey.get("modifiers", []), hotkey.get("key", ""), lambda text=item.get("text", ""): self.paste_text(text), item.get("id", ""))

    def paste_text(self, text: str) -> None:
        try:
            import keyboard
            import pyperclip

            pyperclip.copy(text)
            keyboard.press_and_release("ctrl+v")
        except Exception as exc:
            QMessageBox.warning(self, "단축키 실행 실패", f"클립보드 붙여넣기를 실행하지 못했습니다.\n{exc}")

    def check_schedules(self) -> None:
        now = datetime.now()
        changed = False
        for schedule in self.data.get("schedules", []):
            try:
                target = datetime.fromisoformat(schedule.get("datetime", ""))
            except ValueError:
                continue
            notify_at = target - timedelta(minutes=int(schedule.get("notify_before_minutes", 0)))
            schedule_id = schedule.get("id", "")
            if notify_at <= now <= target + timedelta(minutes=1) and schedule_id not in self._notified_schedule_ids:
                self._notified_schedule_ids.add(schedule_id)
                schedule["last_notified_at"] = now.isoformat(timespec="seconds")
                changed = True
                self.show_schedule_notification(schedule)
        if changed:
            config.save_template(self.template_index, self.data)

    def show_schedule_notification(self, schedule: dict[str, Any]) -> None:
        try:
            from plyer import notification

            notification.notify(title=schedule.get("title", "일정 알림"), message=schedule.get("memo", ""), timeout=5)
        except Exception:
            pass
        QMessageBox.information(self, "일정 알림", f"{schedule.get('title', '일정')}\n\n{schedule.get('memo', '')}")

    def closeEvent(self, event) -> None:
        self.hotkeys.unregister_all()
        clipboard_tab = self.tabs[4]
        if hasattr(clipboard_tab, "stop"):
            clipboard_tab.stop()
        super().closeEvent(event)

from __future__ import annotations

import threading
from ctypes import wintypes
from datetime import datetime, timedelta
from typing import Any

from PyQt6.QtCore import QAbstractNativeEventFilter, QTimer, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QLabel, QMainWindow, QMessageBox, QStackedWidget, QToolButton, QVBoxLayout, QWidget, QHBoxLayout

from app import config
from app.hotkey_manager import HotkeyManager, WM_HOTKEY
from app.theme import apply_theme
from app.update_checker import check_update_dialog
from ui.tab_clipboard import ClipboardTab
from ui.tab_home import HomeTab
from ui.tab_image import ImageTab
from ui.tab_launcher import LauncherTab
from ui.tab_macro import MacroTab
from ui.tab_memo import MemoListTab, ScheduleListTab
from ui.tab_phrase import PhraseTab
from ui.tab_settings import SettingsTab


class HotkeyEventFilter(QAbstractNativeEventFilter):
    def __init__(self, manager: HotkeyManager) -> None:
        super().__init__()
        self.manager = manager

    def nativeEventFilter(self, event_type, message):
        try:
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and self.manager.handle_message(msg.message, msg.wParam):
                return True, 0
        except Exception:
            pass
        return False, 0


class MainWindow(QMainWindow):
    CLIPBOARD_POPUP_HOTKEY_LABEL = "Ctrl+Shift+V"

    def __init__(self, app) -> None:
        super().__init__()
        config.ensure_data_files()
        self.app = app
        self.version = config.read_version()
        self.template_index = 1
        self.data = config.load_template(self.template_index)
        self.hotkeys = HotkeyManager()
        self.hotkey_event_filter = HotkeyEventFilter(self.hotkeys)
        self.app.installNativeEventFilter(self.hotkey_event_filter)
        self._notified_schedule_ids: set[str] = set()
        self.setWindowTitle(f"{config.APP_NAME} {self.version}")
        if config.APP_ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(config.APP_ICON_PATH)))
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
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(0)

        shell = QWidget()
        shell.setObjectName("appShell")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        body = QWidget()
        body.setObjectName("contentArea")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        sidebar = QWidget()
        sidebar.setObjectName("sideBar")
        sidebar.setFixedWidth(180)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(0, 0, 0, 0)
        side.setSpacing(0)

        side_header = QWidget()
        side_header.setObjectName("sideHeader")
        side_header.setFixedHeight(68)
        side_header_layout = QVBoxLayout(side_header)
        side_header_layout.setContentsMargins(14, 12, 14, 10)
        eyebrow = QLabel("6PM ASSISTANT")
        eyebrow.setObjectName("eyebrow")
        menu = QLabel("메뉴")
        menu.setObjectName("windowTitle")
        side_header_layout.addWidget(eyebrow)
        side_header_layout.addWidget(menu)
        side.addWidget(side_header)

        nav = QWidget()
        nav_layout = QVBoxLayout(nav)
        nav_layout.setContentsMargins(6, 6, 6, 6)
        nav_layout.setSpacing(2)
        body_layout.addWidget(sidebar)

        content = QWidget()
        content.setObjectName("contentArea")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        screen_header = QWidget()
        screen_header.setObjectName("screenHeader")
        screen_header.setFixedHeight(68)
        screen_head = QHBoxLayout(screen_header)
        screen_head.setContentsMargins(20, 16, 20, 16)
        screen_head.setSpacing(12)
        title_col = QVBoxLayout()
        title_col.setSpacing(3)
        self.screen_title = QLabel()
        self.screen_title.setObjectName("screenTitle")
        self.screen_subtitle = QLabel()
        self.screen_subtitle.setObjectName("screenSubtitle")
        title_col.addWidget(self.screen_title)
        title_col.addWidget(self.screen_subtitle)
        screen_head.addLayout(title_col, 1)
        self.status = QLabel()
        screen_head.addWidget(self.status, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        content_layout.addWidget(screen_header)

        self.stack = QStackedWidget()
        self.clipboard_tab = ClipboardTab(self)
        self.tabs = [
            HomeTab(self),
            PhraseTab(self),
            LauncherTab(self),
            ImageTab(self),
            MacroTab(self),
            self.clipboard_tab,
            MemoListTab(self),
            ScheduleListTab(self),
            SettingsTab(self),
        ]
        for tab in self.tabs:
            self.stack.addWidget(tab)
        content_layout.addWidget(self.stack, 1)

        names = ["홈 화면", "상용구&코드", "바로가기", "컨닝페이퍼", "매크로", "클립보드 이력", "메모", "일정", "설정"]
        self.buttons: list[QToolButton] = []
        for i, name in enumerate(names):
            button = QToolButton()
            button.setObjectName("navButton")
            button.setText(name)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            button.setCheckable(True)
            button.setFixedHeight(40)
            button.setMinimumWidth(150)
            button.clicked.connect(lambda checked=False, index=i: self.set_tab(index))
            self.buttons.append(button)
            nav_layout.addWidget(button)
        nav_layout.addStretch(1)
        side.addWidget(nav, 1)

        side_footer = QWidget()
        side_footer.setObjectName("sideFooter")
        side_footer_layout = QVBoxLayout(side_footer)
        side_footer_layout.setContentsMargins(12, 10, 12, 10)
        hint = QLabel("단축키는 어느 화면에서나 동작합니다.")
        hint.setObjectName("mutedText")
        hint.setWordWrap(True)
        side_footer_layout.addWidget(hint)
        side.addWidget(side_footer)

        body_layout.addWidget(content, 1)
        shell_layout.addWidget(body, 1)
        root.addWidget(shell)
        self.setCentralWidget(central)
        self.set_tab(0)
        self.update_hotkey_status()

    def set_tab(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        for i, button in enumerate(self.buttons):
            button.setChecked(i == index)
        titles = [
            ("홈 화면", "등록된 단축키와 기능 현황을 한눈에 확인"),
            ("상용구&코드", "자주 쓰는 문구와 코드 스니펫을 단축키로 붙여넣기"),
            ("바로가기", "사이트 계정 정보를 복사하고 파일/폴더를 빠르게 열기"),
            ("컨닝페이퍼", "업무 참고 이미지를 등록하고 별도 창으로 확인"),
            ("매크로", "마우스와 키보드 동작을 녹화하고 재생"),
            ("클립보드 이력", "복사한 텍스트를 검색하고 고정"),
            ("메모", "빠른 메모를 카드로 관리"),
            ("일정", "알림 일정을 카드로 관리"),
            ("설정", "테마, 폰트, 템플릿과 내보내기 설정"),
        ]
        title, subtitle = titles[index]
        self.screen_title.setText(title)
        self.screen_subtitle.setText(subtitle)

    def apply_current_settings(self) -> None:
        settings = self.data.get("settings", {})
        window = settings.get("window", {})
        self.setFixedSize(int(window.get("width", 900)), int(window.get("height", 580)))
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
        for item in self.data.get("launchers", []):
            hotkey = item.get("hotkey")
            if hotkey:
                self.hotkeys.register(hotkey.get("modifiers", []), hotkey.get("key", ""), lambda value=item: self.tabs[2].open_launcher(value), item.get("id", ""))
        for item in self.data.get("images", []):
            hotkey = item.get("hotkey")
            if hotkey:
                self.hotkeys.register(hotkey.get("modifiers", []), hotkey.get("key", ""), lambda value=item: self.tabs[3].view_image(value), item.get("id", ""))
        for item in self.data.get("macros", []):
            hotkey = item.get("hotkey")
            if hotkey:
                self.hotkeys.register(hotkey.get("modifiers", []), hotkey.get("key", ""), lambda value=item: self.tabs[4].play_macro(value), item.get("id", ""))
        self.hotkeys.register(["ctrl", "shift"], "v", self.show_clipboard_popup, "clipboard_popup")
        self.update_hotkey_status()

    def update_hotkey_status(self) -> None:
        if self.hotkeys.registered_count > 0:
            self.status.setObjectName("statusPill")
            self.status.setText("● 단축키 활성")
        else:
            self.status.setObjectName("statusPillInactive")
            self.status.setText("△ 단축키 미등록")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def show_clipboard_popup(self) -> None:
        self.clipboard_tab.show_mini_popup()

    def paste_text(self, text: str) -> None:
        try:
            self.app.clipboard().setText(text)

            def send_paste() -> None:
                try:
                    import pyautogui

                    pyautogui.hotkey("ctrl", "v")
                except Exception:
                    pass

            threading.Timer(0.08, send_paste).start()
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
        self.app.removeNativeEventFilter(self.hotkey_event_filter)
        if hasattr(self.clipboard_tab, "stop"):
            self.clipboard_tab.stop()
        super().closeEvent(event)

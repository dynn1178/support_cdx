from __future__ import annotations

import threading
import time
from ctypes import wintypes
from datetime import datetime, timedelta
from typing import Any

from PyQt6.QtCore import QAbstractNativeEventFilter, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QLabel, QHBoxLayout, QMainWindow, QMessageBox, QStackedWidget, QToolButton, QVBoxLayout, QWidget

from app import config
from app.date_tools import render_date_template
from app.hotkey_manager import HotkeyManager, USER32, WM_HOTKEY
from app.theme import apply_theme
from app.update_checker import check_update_dialog
from app.utils import normalize_hotkey
from ui.tab_clipboard import ClipboardTab
from ui.tab_date_calc import DateCalculatorTab
from ui.tab_home import HomeTab
from ui.tab_image import ImageTab
from ui.tab_launcher import LauncherTab
from ui.tab_macro import MacroTab
from ui.tab_memo import MemoListTab, ScheduleListTab
from ui.tab_phrase import PhraseTab
from ui.tab_settings import SettingsTab
from ui.common import bump_usage


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
    ctrl_double_tapped = pyqtSignal()

    def __init__(self, app) -> None:
        super().__init__()
        config.ensure_data_files()
        self.app = app
        self.version = config.read_version()
        self.settings = config.load_settings()
        self.template_index = int(self.settings.get("active_preset", 1))
        self.data = config.load_template(self.template_index)
        self.data["settings"] = self.settings
        self.hotkeys = HotkeyManager()
        self.ctrl_listener_stop = threading.Event()
        self.ctrl_listener_thread = None
        self.hotkey_event_filter = HotkeyEventFilter(self.hotkeys)
        self.app.installNativeEventFilter(self.hotkey_event_filter)
        self._last_ctrl_release = 0.0
        self.ctrl_double_tapped.connect(self.show_clipboard_popup)
        self._notified_schedule_ids: set[str] = set()
        self.setWindowTitle(f"{config.APP_NAME} {self.version}")
        icon_path = config.APP_ICON_PATH if config.APP_ICON_PATH.exists() else config.BUNDLED_ICON_PATH
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self._build_ui()
        self.hotkeys.set_hwnd(int(self.winId()))
        self.apply_current_settings()
        self.refresh_all_tabs()
        self.register_hotkeys()
        self.start_ctrl_double_tap_listener()
        self.schedule_timer = QTimer(self)
        self.schedule_timer.timeout.connect(self.check_schedules)
        self.schedule_timer.start(60_000)
        QTimer.singleShot(1500, self.check_update_on_startup)

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(0)
        shell = QWidget()
        shell.setObjectName("appShell")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
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
        screen_header = QWidget()
        screen_header.setObjectName("screenHeader")
        screen_header.setFixedHeight(68)
        screen_head = QHBoxLayout(screen_header)
        screen_head.setContentsMargins(20, 16, 20, 16)
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
            DateCalculatorTab(self),
            MemoListTab(self),
            ScheduleListTab(self),
            SettingsTab(self),
        ]
        for tab in self.tabs:
            self.stack.addWidget(tab)
        content_layout.addWidget(self.stack, 1)

        names = ["홈", "상용구/코드", "바로가기", "컨닝페이퍼", "매크로", "클립보드", "날짜 계산기", "메모", "일정", "설정"]
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
        hint = QLabel("단축키는 이 프로그램이 실행 중일 때 동작합니다.")
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
            ("홈", "등록된 기능과 단축키 현황을 확인합니다."),
            ("상용구/코드", "자주 쓰는 문구, 코드 스니펫, 날짜 제목을 복사합니다."),
            ("바로가기", "사이트, 파일, 폴더를 빠르게 엽니다."),
            ("컨닝페이퍼", "업무 참고 이미지를 확인합니다."),
            ("매크로", "마우스와 키보드 동작을 녹화하고 재생합니다."),
            ("클립보드", "복사한 텍스트를 검색하고 고정합니다."),
            ("날짜 계산기", "날짜를 계산하고 원하는 형식으로 복사합니다."),
            ("메모", "메모 스티커를 관리합니다."),
            ("일정", "알림 일정을 관리합니다."),
            ("설정", "테마, 프리셋, 단축키, 클립보드 옵션을 설정합니다."),
        ]
        title, subtitle = titles[index]
        self.screen_title.setText(title)
        self.screen_subtitle.setText(subtitle)

    def apply_current_settings(self) -> None:
        settings = self.settings
        window = settings.get("window", {})
        self.setFixedSize(int(window.get("width", 900)), int(window.get("height", 580)))
        flags = self.windowFlags()
        if window.get("always_on_top"):
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        apply_theme(self.app, settings.get("theme", "light"), settings.get("font_family", "Malgun Gothic"), settings.get("font_size", 9))

    def save_data(self) -> None:
        self.data["settings"] = self.settings
        config.save_template(self.template_index, self.data)
        config.save_settings(self.settings)
        self.register_hotkeys()
        self.refresh_all_tabs()

    def refresh_all_tabs(self) -> None:
        for tab in self.tabs:
            if hasattr(tab, "refresh"):
                tab.refresh()

    def change_template(self, index: int) -> None:
        config.save_template(self.template_index, self.data)
        self.template_index = index
        self.settings["active_preset"] = index
        config.save_settings(self.settings)
        self.data = config.load_template(index)
        self.data["settings"] = self.settings
        self.register_hotkeys()
        self.refresh_all_tabs()

    def hotkey_entries(self, candidate: dict | None = None, original: dict | None = None) -> list[tuple[str, dict]]:
        entries: list[tuple[str, dict]] = []
        for collection, label in [
            ("phrases", "상용구"),
            ("snippets", "코드"),
            ("title_templates", "제목 생성"),
            ("launchers", "바로가기"),
            ("images", "컨닝페이퍼"),
            ("macros", "매크로"),
        ]:
            for item in self.data.get(collection, []):
                if original is not None and item is original:
                    continue
                hotkey = item.get("hotkey")
                if hotkey:
                    entries.append((f"{label}: {item.get('name', '(이름 없음)')}", hotkey))
        if candidate and candidate.get("hotkey"):
            entries.append((f"새 항목: {candidate.get('name', '(이름 없음)')}", candidate["hotkey"]))
        popup_hotkey = self.settings.get("clipboard_popup_hotkey")
        if popup_hotkey and not self.settings.get("clipboard_popup_double_ctrl", True):
            entries.append(("클립보드 미니팝업", popup_hotkey))
        return entries

    def first_hotkey_conflict(self, candidate: dict | None = None, original: dict | None = None) -> str:
        seen: dict[str, str] = {}
        for label, hotkey in self.hotkey_entries(candidate, original):
            key = normalize_hotkey(hotkey)
            if not key:
                continue
            normalized = key.lower()
            if normalized in seen:
                return f"{key} 단축키가 이미 사용 중입니다.\n- {seen[normalized]}\n- {label}"
            seen[normalized] = label
        return ""

    def register_hotkeys(self) -> None:
        self.hotkeys.set_hwnd(int(self.winId()))
        self.hotkeys.unregister_all()
        conflict = self.first_hotkey_conflict()
        if conflict:
            self.status.setObjectName("statusPillInactive")
            self.status.setText("단축키 충돌")
            self.status.setToolTip(conflict)
            self.status.style().unpolish(self.status)
            self.status.style().polish(self.status)
            return
        for item in self.data.get("phrases", []) + self.data.get("snippets", []):
            hotkey = item.get("hotkey")
            if hotkey:
                self.hotkeys.register(hotkey.get("modifiers", []), hotkey.get("key", ""), lambda text=item.get("text", ""): self.paste_text(text), item.get("id", ""))
        for item in self.data.get("title_templates", []):
            hotkey = item.get("hotkey")
            if hotkey:
                self.hotkeys.register(hotkey.get("modifiers", []), hotkey.get("key", ""), lambda value=item: self.copy_title_template(value), item.get("id", ""))
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
        settings = self.settings
        popup_hotkey = settings.get("clipboard_popup_hotkey")
        if popup_hotkey and not settings.get("clipboard_popup_double_ctrl", True):
            self.hotkeys.register(popup_hotkey.get("modifiers", []), popup_hotkey.get("key", ""), self.show_clipboard_popup, "clipboard_popup")
            self.CLIPBOARD_POPUP_HOTKEY_LABEL = normalize_hotkey(popup_hotkey)
        self.update_hotkey_status()

    def update_hotkey_status(self) -> None:
        if self.hotkeys.registered_count > 0:
            self.status.setObjectName("statusPill")
            self.status.setText("단축키 활성")
            self.status.setToolTip("")
        else:
            self.status.setObjectName("statusPillInactive")
            self.status.setText("단축키 없음")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def check_update_on_startup(self) -> None:
        settings = self.settings
        if not settings.get("auto_update_check", False):
            return
        check_update_dialog(
            self,
            self.version,
            repo=config.GITHUB_REPO,
            auto_install=bool(settings.get("auto_update_install", False)),
        )

    def start_ctrl_double_tap_listener(self) -> None:
        if self.ctrl_listener_thread and self.ctrl_listener_thread.is_alive():
            return

        def watch_ctrl() -> None:
            was_down = False
            while not self.ctrl_listener_stop.is_set():
                ctrl_down = bool(USER32.GetAsyncKeyState(0x11) & 0x8000)
                if was_down and not ctrl_down:
                    self.handle_ctrl_release()
                was_down = ctrl_down
                time.sleep(0.02)

        self.ctrl_listener_thread = threading.Thread(target=watch_ctrl, daemon=True)
        self.ctrl_listener_thread.start()

    def handle_ctrl_release(self) -> None:
        if not self.data.get("settings", {}).get("clipboard_popup_double_ctrl", True):
            self._last_ctrl_release = 0.0
            return
        now = time.monotonic()
        if 0 < now - self._last_ctrl_release <= 0.35:
            self._last_ctrl_release = 0.0
            self.ctrl_double_tapped.emit()
            return
        self._last_ctrl_release = now

    def show_clipboard_popup(self) -> None:
        self.clipboard_tab.show_mini_popup()

    def copy_title_template(self, item: dict) -> None:
        bump_usage(item)
        self.app.clipboard().setText(render_date_template(item.get("template", ""), business_days=bool(item.get("business_days", False))))
        config.save_template(self.template_index, self.data)

    def clipboard_popup_shortcut_label(self) -> str:
        settings = self.settings
        if settings.get("clipboard_popup_double_ctrl", True):
            return "Ctrl 두 번"
        return normalize_hotkey(settings.get("clipboard_popup_hotkey"))

    def paste_text(self, text: str) -> None:
        try:
            self.app.clipboard().setText(text)

            def send_paste() -> None:
                try:
                    import pyautogui

                    self.wait_for_modifier_release()
                    pyautogui.hotkey("ctrl", "v")
                except Exception:
                    pass

            threading.Thread(target=send_paste, daemon=True).start()
        except Exception as exc:
            QMessageBox.warning(self, "단축키 실행 실패", f"텍스트를 붙여넣지 못했습니다.\n{exc}")

    def wait_for_modifier_release(self, timeout: float = 1.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not any(USER32.GetAsyncKeyState(vk) & 0x8000 for vk in (0x10, 0x11, 0x12)):
                return
            time.sleep(0.01)

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

            notification.notify(title=schedule.get("title", "일정"), message=schedule.get("memo", ""), timeout=5)
        except Exception:
            pass
        QMessageBox.information(self, "일정 알림", f"{schedule.get('title', '일정')}\n\n{schedule.get('memo', '')}")

    def closeEvent(self, event) -> None:
        self.hotkeys.unregister_all()
        self.app.removeNativeEventFilter(self.hotkey_event_filter)
        self.ctrl_listener_stop.set()
        if self.ctrl_listener_thread:
            self.ctrl_listener_thread.join(timeout=0.2)
        if hasattr(self.clipboard_tab, "stop"):
            self.clipboard_tab.stop()
        super().closeEvent(event)

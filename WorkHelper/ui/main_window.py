from __future__ import annotations

import threading
import time
import calendar
from ctypes import wintypes
from datetime import datetime, timedelta
from typing import Any

from PyQt6.QtCore import QAbstractNativeEventFilter, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QIcon, QKeyEvent, QPixmap
from PyQt6.QtWidgets import QApplication, QCheckBox, QDialog, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton, QScrollArea, QSizePolicy, QStackedWidget, QTextEdit, QToolButton, QVBoxLayout, QWidget

from app import config
from app.date_tools import render_date_template
from app.hotkey_manager import HotkeyManager, USER32, WM_HOTKEY
from app.theme import apply_theme
from app.update_checker import check_update_dialog
from app.utils import display_hotkey, normalize_hotkey
from ui.tab_clipboard import ClipboardTab
from ui.tab_calculator import CalculatorTab
from ui.tab_home import HomeTab
from ui.tab_image import ImageTab
from ui.tab_launcher import LauncherTab
from ui.tab_macro import MacroTab
from ui.tab_memo import MemoListTab, ScheduleListTab
from ui.tab_misc import MiscTab, MouseHighlightOverlay
from ui.tab_phrase import PhraseTab
from ui.tab_settings import SettingsTab
from ui.tab_text_tools import TextToolsTab
from ui.common import ask_modern_question, bump_usage, set_dialog_theme, show_modern_info, show_modern_warning


MINI_COPY_BUTTON_WIDTH = 64
MINI_COPY_BUTTON_HEIGHT = 26


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


class NumberPopupFilter(QAbstractNativeEventFilter):
    def __init__(self, popup: "NumberedTextPopup") -> None:
        super().__init__()
        self.popup = popup

    def nativeEventFilter(self, event_type, message):
        try:
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and 6201 <= int(msg.wParam) <= 6210:
                self.popup.choose((int(msg.wParam) - 6201) % 10)
                return True, 0
        except Exception:
            pass
        return False, 0


class NumberedTextPopup(QDialog):
    def __init__(self, parent: QWidget, title: str, items: list[dict], paste_callback) -> None:
        super().__init__(None)
        self.owner = parent
        self.items = items[:10]
        self.paste_callback = paste_callback
        self.filter = NumberPopupFilter(self)
        self.registered: list[int] = []
        self.previous_hwnd = 0
        self._closing = False
        self.setWindowTitle(title)
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedWidth(430)
        self.setStyleSheet(
            """
            QDialog { background: #EEF4FF; }
            QPushButton#miniCopyButton {
                padding: 0;
                min-width: 54px; max-width: 54px;
                min-height: 24px; max-height: 24px;
            }
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        container = QWidget()
        rows = QVBoxLayout(container)
        rows.setContentsMargins(0, 0, 0, 0)
        rows.setSpacing(3)
        if not self.items:
            rows.addWidget(QLabel("표시할 즐겨찾기가 없습니다."))
        for index, item in enumerate(self.items):
            rows.addWidget(self._row(index, item))
        rows.addStretch(1)
        scroll.setWidget(container)
        layout.addWidget(scroll)
        hint = QLabel("1~0 숫자키로 바로 복사")
        hint.setObjectName("mutedText")
        layout.addWidget(hint)
        self.setFixedHeight(58 + min(max(len(self.items), 1), 10) * 36)
        self.start_number_hotkeys()
        QTimer.singleShot(0, self.activate_popup)

    def _row(self, index: int, item: dict) -> QWidget:
        row = QWidget()
        row.setObjectName("card")
        row.setFixedHeight(33)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(6, 3, 6, 3)
        number = QLabel(str(index + 1) if index < 9 else "0")
        number.setObjectName("kbd")
        number.setAlignment(Qt.AlignmentFlag.AlignCenter)
        number.setFixedWidth(24)
        text = QLabel(item.get("text", "").replace("\n", " ")[:70])
        text.setToolTip(item.get("text", ""))
        text.setMinimumWidth(0)
        text.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        copy = QPushButton("복사")
        copy.setObjectName("miniCopyButton")
        copy.setFixedSize(54, 24)
        copy.clicked.connect(lambda checked=False, value=index: self.choose(value))
        layout.addWidget(number)
        layout.addWidget(text, 1)
        layout.addWidget(copy)
        return row

    def activate_popup(self) -> None:
        try:
            self.previous_hwnd = int(USER32.GetForegroundWindow())
        except Exception:
            self.previous_hwnd = 0
        cursor = QCursor.pos()
        screen = QApplication.screenAt(cursor) or QApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            x = min(max(cursor.x() + 12, area.left()), area.right() - self.width())
            y = min(max(cursor.y() + 12, area.top()), area.bottom() - self.height())
            self.move(x, y)
        self.raise_()
        self.activateWindow()
        self.setFocus(Qt.FocusReason.PopupFocusReason)

    def start_number_hotkeys(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        app.installNativeEventFilter(self.filter)
        hwnd = int(self.winId())
        for index, key in enumerate("1234567890"):
            hotkey_id = 6201 + index
            if USER32.RegisterHotKey(hwnd, hotkey_id, 0, ord(key)):
                self.registered.append(hotkey_id)

    def stop_number_hotkeys(self) -> None:
        hwnd = int(self.winId())
        for hotkey_id in self.registered:
            try:
                USER32.UnregisterHotKey(hwnd, hotkey_id)
            except Exception:
                pass
        self.registered.clear()
        app = QApplication.instance()
        if app is not None:
            try:
                app.removeNativeEventFilter(self.filter)
            except Exception:
                pass

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.text() in set("1234567890"):
            self.choose(("1234567890".index(event.text())))
            return
        super().keyPressEvent(event)

    def choose(self, index: int) -> None:
        if self._closing or not (0 <= index < len(self.items)):
            return
        self._closing = True
        item = self.items[index]
        bump_usage(item)
        text = item.get("text", "")
        try:
            self.owner.save_usage_data()
        except Exception:
            pass
        self.accept()
        self.paste_callback(text)

    def done(self, result: int) -> None:
        self.stop_number_hotkeys()
        super().done(result)
        self.restore_previous_window()

    def restore_previous_window(self) -> None:
        if not self.previous_hwnd:
            return
        try:
            USER32.SetForegroundWindow(self.previous_hwnd)
        except Exception:
            pass


class QuickMemoPopup(QDialog):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(None)
        self.setWindowTitle("빠른 메모")
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        layout = QVBoxLayout(self)
        self.text = QTextEdit()
        self.text.setPlaceholderText("메모를 입력하세요")
        self.sticky = QCheckBox("스티커로 띄우기")
        row = QHBoxLayout()
        save = QPushButton("저장")
        cancel = QPushButton("취소")
        save.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        row.addStretch(1)
        row.addWidget(save)
        row.addWidget(cancel)
        layout.addWidget(self.text)
        layout.addWidget(self.sticky)
        layout.addLayout(row)
        self.resize(340, 240)
        QTimer.singleShot(0, self.activate_popup)

    def activate_popup(self) -> None:
        cursor = QCursor.pos()
        screen = QApplication.screenAt(cursor) or QApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            x = min(max(cursor.x() + 12, area.left()), area.right() - self.width())
            y = min(max(cursor.y() + 12, area.top()), area.bottom() - self.height())
            self.move(x, y)
        self.raise_()
        self.activateWindow()
        self.text.setFocus(Qt.FocusReason.PopupFocusReason)


class MainWindow(QMainWindow):
    CLIPBOARD_POPUP_HOTKEY_LABEL = "Ctrl+Shift+V"
    ctrl_double_tapped = pyqtSignal()
    alt_double_tapped = pyqtSignal()
    hotstring_expand_requested = pyqtSignal(str, str, str)
    HOME_TIPS = [
        "상용구에 자주 쓰는 답변을 등록하고 단축키를 지정하면 상담 문구를 바로 붙여넣을 수 있습니다.",
        "코드 스니펫에는 자주 쓰는 SQL이나 Python 조각을 저장해두고 필요한 순간 단축키로 복사해보세요.",
        "핫스트링은 gg. → google.com처럼 입력 문자열을 대체 텍스트로 바꿔 흐름을 크게 끊지 않고 문구를 불러올 수 있습니다.",
        "바로가기에 업무 사이트와 파일 경로를 등록하면 로그인 정보 복사와 열기를 한 번에 처리할 수 있습니다.",
        "컨닝페이퍼에는 참고 이미지나 업무 절차 캡처를 넣고 단축키로 즉시 열어볼 수 있습니다.",
        "매크로 녹화는 반복 클릭과 키 입력을 저장해두었다가 단축키로 다시 실행할 때 유용합니다.",
        "클립보드 미니팝업은 최근 복사한 내용을 빠르게 다시 꺼낼 때 좋습니다. Ctrl 두 번 설정도 활용해보세요.",
        "제목 생성은 날짜 토큰을 넣어 리포트명이나 파일명을 일정한 규칙으로 만드는 데 쓸 수 있습니다.",
        "계산기에서는 수식 계산과 날짜 계산을 한 화면 안에서 탭으로 나눠 처리할 수 있습니다.",
        "텍스트 변환은 URL 인코딩, UTM 분해, 줄바꿈과 따옴표 목록 변환을 빠르게 처리합니다.",
        "컬러 도구는 화면에서 색을 찍고 HEX, RGB, HSL 값을 바로 복사할 때 유용합니다.",
        "이모지 도구는 자주 쓴 이모지를 사용 횟수 순으로 다시 보여줍니다.",
        "빠른 메모는 Alt 두 번으로 마우스 근처에 띄워 즉시 기록할 수 있습니다.",
        "메모와 일정은 업무 중 놓치기 쉬운 체크 사항을 작게 고정하거나 알림으로 관리할 때 편합니다.",
        "프리셋을 나눠두면 업무 상황별 상용구, 바로가기, 매크로 묶음을 빠르게 전환할 수 있습니다.",
        "테마 설정으로 밝은 화면, 어두운 화면, 고대비 화면을 작업 환경에 맞게 바꿔보세요.",
        "다른 프로그램 단축키와 겹칠 때는 왼쪽 하단 단축키 ON/OFF 버튼으로 잠시 꺼둘 수 있습니다.",
    ]

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
        self.key_listener_stop = threading.Event()
        self.key_listener_thread = None
        self.hotstring_listener = None
        self.hotstring_buffer = ""
        self.hotstring_busy = False
        self.mouse_highlight_overlay = None
        self.hotkey_event_filter = HotkeyEventFilter(self.hotkeys)
        self.app.installNativeEventFilter(self.hotkey_event_filter)
        self._last_ctrl_release = 0.0
        self._last_alt_release = 0.0
        self._home_tip_index = 0
        self.ctrl_double_tapped.connect(self.show_clipboard_popup)
        self.alt_double_tapped.connect(self.show_quick_memo_popup)
        self.hotstring_expand_requested.connect(self.expand_hotstring)
        self._notified_schedule_ids: set[str] = set()
        self.setWindowTitle(f"{config.APP_NAME} {self.version}")
        icon2_path = config.BASE_DIR / "icon2.png" if (config.BASE_DIR / "icon2.png").exists() else config.RESOURCE_DIR / "icon2.png"
        icon_path = icon2_path if icon2_path.exists() else config.APP_ICON_PATH if config.APP_ICON_PATH.exists() else config.BUNDLED_ICON_PATH
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self._build_ui()
        self.hotkeys.set_hwnd(int(self.winId()))
        self.apply_current_settings()
        self.refresh_all_tabs()
        self.register_hotkeys()
        self.start_modifier_double_tap_listener()
        self.start_hotstring_listener()
        self.schedule_timer = QTimer(self)
        self.schedule_timer.timeout.connect(self.check_schedules)
        self.schedule_timer.start(60_000)
        self.tip_timer = QTimer(self)
        self.tip_timer.timeout.connect(self.rotate_home_tip)
        self.tip_timer.start(300_000)
        QTimer.singleShot(1500, self.check_update_on_startup)
        QTimer.singleShot(300, self.restore_open_stickers)

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
        side_header.setFixedHeight(78)
        side_header_layout = QHBoxLayout(side_header)
        side_header_layout.setContentsMargins(14, 12, 14, 10)
        side_header_layout.setSpacing(10)
        brand_icon = QLabel()
        brand_icon.setFixedSize(34, 34)
        icon2_path = config.BASE_DIR / "icon2.png" if (config.BASE_DIR / "icon2.png").exists() else config.RESOURCE_DIR / "icon2.png"
        icon_path = icon2_path if icon2_path.exists() else config.APP_ICON_PATH if config.APP_ICON_PATH.exists() else config.BUNDLED_ICON_PATH
        if icon_path.exists():
            brand_icon.setPixmap(QPixmap(str(icon_path)).scaled(34, 34, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        brand_text = QLabel("6PM\nAssistant")
        brand_text.setObjectName("windowTitle")
        side_header_layout.addWidget(brand_icon)
        side_header_layout.addWidget(brand_text, 1)
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
        screen_header.setFixedHeight(78)
        screen_head = QHBoxLayout(screen_header)
        screen_head.setContentsMargins(20, 16, 20, 16)
        title_col = QVBoxLayout()
        title_col.setSpacing(3)
        self.screen_title = QLabel()
        self.screen_title.setObjectName("screenTitle")
        self.screen_subtitle = QLabel()
        self.screen_subtitle.setObjectName("screenSubtitle")
        self.screen_subtitle.setWordWrap(True)
        title_col.addWidget(self.screen_subtitle)
        screen_head.addLayout(title_col, 1)
        tip_nav_col = QVBoxLayout()
        tip_nav_col.setContentsMargins(0, 0, 0, 0)
        tip_nav_col.setSpacing(0)
        tip_nav_col.addStretch(1)
        tip_nav_row = QHBoxLayout()
        tip_nav_row.setContentsMargins(0, 0, 0, 0)
        tip_nav_row.setSpacing(2)
        self.prev_tip_button = QToolButton()
        self.prev_tip_button.setText("‹")
        self.prev_tip_button.setToolTip("이전 팁")
        self.prev_tip_button.setObjectName("tipNavButton")
        self.prev_tip_button.setFixedSize(30, 30)
        self.prev_tip_button.clicked.connect(self.prev_home_tip)
        self.next_tip_button = QToolButton()
        self.next_tip_button.setText("›")
        self.next_tip_button.setToolTip("다음 팁")
        self.next_tip_button.setObjectName("tipNavButton")
        self.next_tip_button.setFixedSize(30, 30)
        self.next_tip_button.clicked.connect(self.next_home_tip)
        tip_nav_row.addWidget(self.prev_tip_button)
        tip_nav_row.addWidget(self.next_tip_button)
        tip_nav_col.addLayout(tip_nav_row)
        screen_head.addLayout(tip_nav_col)
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
            CalculatorTab(self),
            TextToolsTab(self),
            MemoListTab(self),
            ScheduleListTab(self),
            MiscTab(self),
            SettingsTab(self),
        ]
        for tab in self.tabs:
            self.stack.addWidget(tab)
        content_layout.addWidget(self.stack, 1)

        names = ["홈", "상용구/코드", "바로가기", "컨닝페이퍼", "매크로", "클립보드", "계산기", "텍스트 변환", "메모", "일정 알림", "기타", "설정"]
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
        self.hotkey_toggle = QPushButton()
        self.hotkey_toggle.clicked.connect(self.toggle_hotkeys_enabled)
        side_footer_layout.addWidget(self.hotkey_toggle)
        side.addWidget(side_footer)

        body_layout.addWidget(content, 1)
        shell_layout.addWidget(body, 1)
        root.addWidget(shell)
        self.setCentralWidget(central)
        self.set_tab(0)
        self.update_hotkey_toggle_button()

    def set_tab(self, index: int) -> None:
        if hasattr(self, "stack") and self.stack.currentIndex() == 11 and index != 11:
            settings_tab = self.tabs[11]
            if hasattr(settings_tab, "is_dirty") and settings_tab.is_dirty():
                if ask_modern_question(self, "변경 내역 저장", "설정 - 일반에 저장되지 않은 변경 내역이 있습니다.\n저장하고 이동할까요?", None, "저장", "저장안함"):
                    settings_tab.save_settings()
        self.stack.setCurrentIndex(index)
        for i, button in enumerate(self.buttons):
            button.setChecked(i == index)
        subtitles = [
            "🔹" + self.numbered_home_tip(),
            f"🔹자주 쓰는 문구나 코드, 날짜 형식, 핫스트링을 저장하고 쉽게 불러오세요.\n💡즐겨찾기(★)로 상용구 호출도 가능합니다. (기본 단축키 {display_hotkey(self.settings.get('phrase_popup_hotkey')) or 'Ctrl+;'})",
            "🔹자주 찾는 사이트나 폴더, 파일을 단축키로 바로 불러올 수 있어요.\n💡사이트를 불러오면 함께 저장한 아이디와 비밀번호를 복사해줘요! (개인 계정은 보안상 사용하지 마세요)",
            "🔹원하는 이미지를 파일, URL, 캡처 방식으로 저장하고 불러올 수 있어요\n💡자주 참고하는 자료를 등록해보세요. (단축키, 조직도, KPI 등)",
            "🔹마우스와 키보드 동작을 녹화하고 그대로 반복&재생시킬 수 있어요.\n💡편집 화면에서 직접 편집하는 것도 가능해요.",
            "🔹복사했던 항목들을 보관하고 불러옵니다.\n💡Ctrl을 두 번 누르면 복사했던 이력을 미니 팝업으로 바로 확인하고 가져올 수 있어요",
            "🔹수식과 날짜를 계산하고 결과를 복사합니다.",
            "🔹URL, UTM, 줄바꿈, 따옴표 변환을 처리합니다.",
            "🔹메모를 저장할 수 있어요.\n💡Alt를 두 번 누르면 어디서든 빠른 메모를 등록할 수 있어요.",
            "🔹일정 알림을 관리합니다.",
            "🔹컬러, 마우스 하이라이트, 이모지를 관리합니다.",
            "🔹일반, 단축키, 테마 옵션을 설정합니다.",
        ]
        subtitle = subtitles[index]
        if index == 0:
            subtitle = self.numbered_home_tip()
        self.prev_tip_button.setVisible(index == 0)
        self.next_tip_button.setVisible(index == 0)
        if "\n" in subtitle:
            first, second = subtitle.split("\n", 1)
            subtitle = f'<p style="margin:0 0 6px 0">{first}</p><p style="margin:0">{second}</p>'
        self.screen_subtitle.setText(subtitle)

    def rotate_home_tip(self) -> None:
        self.next_home_tip()

    def numbered_home_tip(self) -> str:
        return f"{self._home_tip_index + 1}. {self.HOME_TIPS[self._home_tip_index]}"

    def prev_home_tip(self) -> None:
        self._home_tip_index = (self._home_tip_index - 1) % len(self.HOME_TIPS)
        if self.stack.currentIndex() == 0:
            self.set_tab(0)

    def next_home_tip(self) -> None:
        self._home_tip_index = (self._home_tip_index + 1) % len(self.HOME_TIPS)
        if self.stack.currentIndex() == 0:
            self.set_tab(0)

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
        set_dialog_theme(settings.get("theme", "light"))
        apply_theme(self.app, settings.get("theme", "light"))

    def save_data(self) -> None:
        self.data["settings"] = self.settings
        config.save_template(self.template_index, self.data)
        config.save_settings(self.settings)
        self.register_hotkeys()
        self.refresh_all_tabs()

    def save_usage_data(self) -> None:
        config.save_template(self.template_index, self.data)
        self.refresh_home_tab()

    def refresh_all_tabs(self) -> None:
        for tab in self.tabs:
            if hasattr(tab, "refresh"):
                tab.refresh()

    def refresh_home_tab(self) -> None:
        if not hasattr(self, "tabs") or not self.tabs:
            return
        home = self.tabs[0]
        if hasattr(home, "refresh"):
            home.refresh()

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
        quick_memo_hotkey = self.settings.get("quick_memo_hotkey")
        if quick_memo_hotkey and not self.settings.get("quick_memo_double_alt", True):
            entries.append(("빠른 메모", quick_memo_hotkey))
        phrase_popup_hotkey = self.settings.get("phrase_popup_hotkey")
        if phrase_popup_hotkey:
            entries.append(("상용구 미니팝업", phrase_popup_hotkey))
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
        if not self.settings.get("hotkeys_enabled", True):
            self.update_hotkey_toggle_button()
            return
        conflict = self.first_hotkey_conflict()
        if conflict:
            show_modern_warning(self, "단축키 충돌", conflict)
            return
        for item in self.data.get("phrases", []) + self.data.get("snippets", []):
            hotkey = item.get("hotkey")
            if hotkey:
                self.hotkeys.register(hotkey.get("modifiers", []), hotkey.get("key", ""), lambda value=item: self.paste_text_item(value), item.get("id", ""))
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
        quick_memo_hotkey = settings.get("quick_memo_hotkey")
        if quick_memo_hotkey and not settings.get("quick_memo_double_alt", True):
            self.hotkeys.register(quick_memo_hotkey.get("modifiers", []), quick_memo_hotkey.get("key", ""), self.show_quick_memo_popup, "quick_memo")
        phrase_popup_hotkey = settings.get("phrase_popup_hotkey")
        if phrase_popup_hotkey:
            self.hotkeys.register(phrase_popup_hotkey.get("modifiers", []), phrase_popup_hotkey.get("key", ""), self.show_phrase_popup, "phrase_popup")
        self.update_hotkey_status()
        self.update_hotkey_toggle_button()

    def update_hotkey_status(self) -> None:
        return

    def toggle_hotkeys_enabled(self) -> None:
        self.settings["hotkeys_enabled"] = not self.settings.get("hotkeys_enabled", True)
        config.save_settings(self.settings)
        if self.settings["hotkeys_enabled"]:
            self.register_hotkeys()
        else:
            self.hotkeys.unregister_all()
        self.update_hotkey_toggle_button()
        self.refresh_all_tabs()

    def update_hotkey_toggle_button(self) -> None:
        enabled = self.settings.get("hotkeys_enabled", True)
        self.hotkey_toggle.setText("단축키 ON" if enabled else "단축키 OFF")
        bg = "#2EA672" if enabled else "#9CA3AF"
        self.hotkey_toggle.setStyleSheet(f"QPushButton {{ color: {bg}; font-weight: 800; }}")

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

    def start_modifier_double_tap_listener(self) -> None:
        if self.ctrl_listener_thread and self.ctrl_listener_thread.is_alive():
            return

        def watch_modifiers() -> None:
            was_down = False
            alt_was_down = False
            while not self.ctrl_listener_stop.is_set():
                ctrl_down = bool(USER32.GetAsyncKeyState(0x11) & 0x8000)
                if was_down and not ctrl_down:
                    self.handle_ctrl_release()
                was_down = ctrl_down
                alt_down = bool(USER32.GetAsyncKeyState(0x12) & 0x8000)
                if alt_was_down and not alt_down:
                    self.handle_alt_release()
                alt_was_down = alt_down
                time.sleep(0.02)

        self.ctrl_listener_thread = threading.Thread(target=watch_modifiers, daemon=True)
        self.ctrl_listener_thread.start()

    def handle_ctrl_release(self) -> None:
        if not self.settings.get("hotkeys_enabled", True):
            self._last_ctrl_release = 0.0
            return
        if not self.data.get("settings", {}).get("clipboard_popup_double_ctrl", True):
            self._last_ctrl_release = 0.0
            return
        now = time.monotonic()
        if 0 < now - self._last_ctrl_release <= 0.35:
            self._last_ctrl_release = 0.0
            self.ctrl_double_tapped.emit()
            return
        self._last_ctrl_release = now

    def handle_alt_release(self) -> None:
        if not self.settings.get("hotkeys_enabled", True):
            self._last_alt_release = 0.0
            return
        if not self.settings.get("quick_memo_double_alt", True):
            self._last_alt_release = 0.0
            return
        now = time.monotonic()
        if 0 < now - self._last_alt_release <= 0.35:
            self._last_alt_release = 0.0
            self.alt_double_tapped.emit()
            return
        self._last_alt_release = now

    def show_clipboard_popup(self) -> None:
        self.clipboard_tab.show_mini_popup()

    def show_phrase_popup(self) -> None:
        favorite_ids = self.data.get("phrase_popup_favorites", [])[:10]
        by_id = {item.get("id"): item for item in self.data.get("phrases", []) + self.data.get("snippets", [])}
        for item in self.data.get("title_templates", []):
            by_id[item.get("id")] = {
                **item,
                "text": render_date_template(item.get("template", ""), business_days=bool(item.get("business_days", False))),
            }
        items = [by_id[item_id] for item_id in favorite_ids if item_id in by_id]
        NumberedTextPopup(self, "상용구", items, self.paste_text).exec()

    def show_quick_memo_popup(self) -> None:
        dialog = QuickMemoPopup(self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        content = dialog.text.toPlainText().strip()
        if not content:
            return
        from app.utils import new_id, now_iso

        title = content.splitlines()[0][:30] or "빠른 메모"
        memo = {
            "id": new_id("mm"),
            "title": title,
            "content": content,
            "pinned": False,
            "always_on_top": True,
            "background": "노랑",
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "sort_order": len(self.data.setdefault("memos", [])),
            "usage_count": 0,
        }
        self.data.setdefault("memos", []).append(memo)
        self.save_data()
        if dialog.sticky.isChecked():
            memo["sticker_open"] = True
            self.tabs[8].show_sticker(memo)

    def copy_title_template(self, item: dict) -> None:
        bump_usage(item)
        text = render_date_template(item.get("template", ""), business_days=bool(item.get("business_days", False)))
        self.save_usage_data()
        self.paste_text(text)

    def clipboard_popup_shortcut_label(self) -> str:
        settings = self.settings
        if settings.get("clipboard_popup_double_ctrl", True):
            return "Ctrl x2"
        return display_hotkey(settings.get("clipboard_popup_hotkey"))

    def quick_memo_shortcut_label(self) -> str:
        settings = self.settings
        if settings.get("quick_memo_double_alt", True):
            return "Alt x2"
        return display_hotkey(settings.get("quick_memo_hotkey"))

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
            show_modern_warning(self, "단축키 실행 실패", f"텍스트를 붙여넣지 못했습니다.\n{exc}")

    def paste_text_item(self, item: dict) -> None:
        bump_usage(item)
        self.save_usage_data()
        self.paste_text(item.get("text", ""))

    def start_hotstring_listener(self) -> None:
        try:
            from pynput import keyboard
        except Exception:
            return

        def on_press(key) -> None:
            if self.hotstring_busy or not self.settings.get("hotkeys_enabled", True):
                return
            try:
                char = key.char
            except AttributeError:
                if key in {keyboard.Key.space, keyboard.Key.enter, keyboard.Key.tab}:
                    self.hotstring_buffer = ""
                return
            if not char:
                return
            self.hotstring_buffer = (self.hotstring_buffer + char)[-80:]
            self.try_expand_hotstring()

        self.hotstring_listener = keyboard.Listener(on_press=on_press)
        self.hotstring_listener.daemon = True
        self.hotstring_listener.start()

    def try_expand_hotstring(self) -> None:
        for item in self.data.get("hotstrings", []):
            trigger = item.get("trigger", "")
            if not trigger:
                continue
            buffer = self.hotstring_buffer if item.get("case_sensitive") else self.hotstring_buffer.lower()
            needle = trigger if item.get("case_sensitive") else trigger.lower()
            if buffer.endswith(needle):
                self.hotstring_busy = True
                self.hotstring_expand_requested.emit(trigger, item.get("text", ""), item.get("id", ""))
                break

    def expand_hotstring(self, trigger: str, text: str, item_id: str) -> None:
        self.hotstring_busy = True
        for item in self.data.get("hotstrings", []):
            if item.get("id") == item_id:
                bump_usage(item)
                QTimer.singleShot(250, self.save_usage_data)
                break
        self.app.clipboard().setText(text)

        def worker() -> None:
            try:
                import pyautogui

                pyautogui.PAUSE = 0.01
                time.sleep(0.10)
                pyautogui.press("backspace", presses=len(trigger), interval=0.02)
                time.sleep(0.04)
                pyautogui.hotkey("ctrl", "v")
            except Exception:
                pass
            finally:
                self.hotstring_buffer = ""
                self.hotstring_busy = False

        threading.Thread(target=worker, daemon=True).start()

    def set_mouse_highlight(self, enabled: bool) -> None:
        if enabled:
            if self.mouse_highlight_overlay is None:
                self.mouse_highlight_overlay = MouseHighlightOverlay(self.settings)
            self.mouse_highlight_overlay.settings = self.settings
            self.mouse_highlight_overlay.show()
        elif self.mouse_highlight_overlay is not None:
            self.mouse_highlight_overlay.close()
            self.mouse_highlight_overlay = None

    def restore_open_stickers(self) -> None:
        if len(self.tabs) <= 8:
            return
        for memo in self.data.get("memos", []):
            if memo.get("sticker_open"):
                self.tabs[8].show_sticker(memo, track_usage=False, raise_window=False)

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
                self.advance_repeating_schedule(schedule, target)
                changed = True
                self.show_schedule_notification(schedule)
        if changed:
            config.save_template(self.template_index, self.data)

    def advance_repeating_schedule(self, schedule: dict[str, Any], target: datetime) -> None:
        repeat = schedule.get("repeat", "none")
        if repeat == "daily":
            schedule["datetime"] = (target + timedelta(days=1)).isoformat(timespec="seconds")
        elif repeat == "weekly":
            schedule["datetime"] = (target + timedelta(weeks=1)).isoformat(timespec="seconds")
        elif repeat == "monthly":
            month = target.month + 1
            year = target.year
            if month > 12:
                month = 1
                year += 1
            day = min(target.day, calendar.monthrange(year, month)[1])
            schedule["datetime"] = target.replace(year=year, month=month, day=day).isoformat(timespec="seconds")

    def show_schedule_notification(self, schedule: dict[str, Any]) -> None:
        bump_usage(schedule)
        self.save_usage_data()
        try:
            from plyer import notification

            notification.notify(title=schedule.get("title", "일정"), message=schedule.get("memo", ""), timeout=5)
        except Exception:
            pass
        show_modern_info(self, "일정 알림", f"{schedule.get('title', '일정')}\n\n{schedule.get('memo', '')}")

    def closeEvent(self, event) -> None:
        self.hotkeys.unregister_all()
        if self.hotstring_listener is not None:
            try:
                self.hotstring_listener.stop()
            except Exception:
                pass
        self.set_mouse_highlight(False)
        self.app.removeNativeEventFilter(self.hotkey_event_filter)
        self.ctrl_listener_stop.set()
        if self.ctrl_listener_thread:
            self.ctrl_listener_thread.join(timeout=0.2)
        if hasattr(self.clipboard_tab, "stop"):
            self.clipboard_tab.stop()
        if hasattr(self.clipboard_tab, "cleanup_expired_images"):
            self.clipboard_tab.cleanup_expired_images(days=7)
        super().closeEvent(event)

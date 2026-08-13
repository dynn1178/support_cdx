from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from PyQt6.QtCore import QEvent, QObject, QPoint, QPropertyAnimation, QRunnable, QSize, Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QGraphicsOpacityEffect
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.theme import THEMES
from app.utils import now_iso

class ImageSaveSignals(QObject):
    finished = pyqtSignal(str, bool)


class ImageSaveWorker(QRunnable):
    """이미지 저장(인코딩+디스크 쓰기)을 백그라운드 스레드에서 수행해 UI가 멈추지 않게 한다."""

    def __init__(self, image, path: Path, image_format: str = "PNG", quality: int = -1) -> None:
        super().__init__()
        self.image = image
        self.path = path
        self.image_format = image_format
        self.quality = quality
        self.signals = ImageSaveSignals()

    @pyqtSlot()
    def run(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            ok = True if self.path.exists() else self.image.save(str(self.path), self.image_format, self.quality)
        except Exception:
            ok = False
        self.signals.finished.emit(str(self.path), ok)


HOTKEY_KEYS = (
    [str(i) for i in range(1, 10)]
    + ["0"]
    + [chr(i) for i in range(ord("A"), ord("Z") + 1)]
    + [f"F{i}" for i in range(1, 13)]
    + [";", "'", "`", ",", ".", "/", "\\", "-", "=", "[", "]"]
    + [f"Num{i}" for i in range(1, 10)]
    + ["Num0"]
)
DIALOG_THEME = "light"
CARD_SIZE_A = 72
CARD_SIZE_B = 108
CARD_SIZE_C = 126
CORNER_CONTROL_HEIGHT = 26
CORNER_CONTAINER_HEIGHT = 32
CORNER_SEARCH_WIDTH = 120
CORNER_SORT_MODE_WIDTH = 92
CORNER_SORT_ORDER_WIDTH = 104
BOTTOM_ACTION_HEIGHT = 30
BOTTOM_ACTION_MARGINS = (0, 0, 3, 3)  # (left, top, right, bottom) - 우측 하단 3px 기준
BOTTOM_ACTION_SPACING = 6
CARD_ACTION_ICON_SIZE = 24
CARD_ACTION_ROW_MARGIN_X = 3
CARD_ACTION_ROW_MARGIN_Y = 0
CARD_ACTION_ROW_SPACING = 2
CARD_ACTION_OVERLAY_MARGIN = 8
CARD_ACTION_OVERLAY_Y_OFFSET = 0
CARD_ACTION_ICON_PADDING = "0 0 2px 0"
CARD_CONTENT_TOP_MARGIN = 8
CARD_LABEL_ALIGNMENT = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
GRID_PANEL_MARGINS = (10, 10, 10, 10)  # (left, top, right, bottom) - 카드 그리드 시작 상단 10px 기준

# [정책] 용어: 왼쪽 사이드바 버튼은 "메뉴", 메뉴 안의 QTabWidget 세부 화면은 "탭"으로 부른다.
# [정책] 메뉴/탭 수정 요청은 아래 한글명을 먼저 확인하고 해당 py 파일에서 변경한다.
# [정책] 메뉴: 홈=ui/tab_home.py, 상용구=ui/tab_phrase.py, 바로가기=ui/tab_launcher.py,
# [정책] 메뉴: 클립보드=ui/tab_clipboard.py, 캡처 · 그리기=ui/tab_image.py,
# [정책] 메뉴: 일정 관리=ui/tab_memo.py(TodoListTab), 메모=ui/tab_memo.py(MemoListTab),
# [정책] 메뉴: 매크로=ui/tab_macro.py, 계산기=ui/tab_calculator.py, 텍스트 변환=ui/tab_text_tools.py,
# [정책] 메뉴: 피커 · 기타=ui/tab_misc.py, 설정=ui/tab_settings.py.
# [정책] 탭: 상용구/일반 텍스트·스니펫·핫스트링·날짜/보고 양식=ui/tab_phrase.py.
# [정책] 탭: 바로가기/사이트·파일/폴더·바로검색=ui/tab_launcher.py.
# [정책] 탭: 클립보드/클립보드=ui/tab_clipboard.py.
# [정책] 탭: 캡처 · 그리기/캡처 · 그리기·컨닝페이퍼=ui/tab_image.py.
# [정책] 탭: 일정 관리/To Do·타이머=ui/tab_memo.py, 메모/메모=ui/tab_memo.py.
# [정책] 탭: 매크로/매크로=ui/tab_macro.py, 계산기/연산 계산·날짜 계산=ui/tab_calculator.py.
# [정책] 탭: 텍스트 변환/URL 인코딩·UTM·줄바꿈/따옴표·대소문자 변환=ui/tab_text_tools.py.
# [정책] 탭: 피커 · 기타/컬러·이모지·특수문자·마우스 하이라이트·화면 그리기=ui/tab_misc.py.
# [정책] 탭: 설정/일반·단축키·테마·위젯=ui/tab_settings.py.
# [정책] 카드 패널 위의 컨텐츠는 테마 배경(bg/content)보다 카드 패널 배경(panel)을 우선 적용한다.
# [정책] 카드 컨텐츠의 상단 여백은 CARD_CONTENT_TOP_MARGIN(8px)로 고정한다. 한 줄/여러 줄 모두 같은 시작점에서 내용을 시작한다.
# [정책] make_card()를 쓰지 않는 수동 카드도 상단 여백은 CARD_CONTENT_TOP_MARGIN 값을 직접 참조한다.
# [정책] 카드 목록 그리드의 외곽 여백은 GRID_PANEL_MARGINS 값을 참조한다. 카드 시작 상단 위치는 GRID_PANEL_MARGINS[1](10px) 기준이다.
# [정책] 카드 텍스트 라벨은 CARD_LABEL_ALIGNMENT(좌측+상단 정렬)을 사용한다. 라벨 내부에서도 한 줄/여러 줄 모두 상단 기준으로 정렬한다.
# [정책] 단축키 마커는 make_hotkey_caps()를 사용한다. hotkeyCaps는 패널 배경 + 패널색 2px 테두리 기준이다.
# [정책] 홈 인라인 단축키는 inline_hotkey=True + hotkeyCapsInline(투명)을 사용한다.
# [정책] 호버 아이콘은 add_card_actions() 또는 set_card_action_widget()를 사용하고, 행/아이콘 높이는 CARD_ACTION_* 전역 상수만 변경해 관리한다.
# [정책] 우측 하단 버튼 묶음은 bottom_action_bar()를 사용한다. 시작점은 우측 하단 꼭지점 기준 가로/세로 3px 여백이며 버튼 높이는 BOTTOM_ACTION_HEIGHT로 통일한다.
# [정책] 탭 하단 추가 버튼은 내부 컨텐츠 margin이 아니라 bottom_action_bar 전역 정책만 따른다.

SORT_MODES = [
    ("등록", "created"),
    ("가나다", "name"),
    ("수동", "manual"),
]
SORT_ORDERS = [
    ("내림차순", "desc"),
    ("오름차순", "asc"),
]


def fit_combo_to_contents(combo: QComboBox, min_width: int = 120, extra: int = 44) -> QComboBox:
    """Size dropdowns so their current and menu text are visible."""
    combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
    width = min_width
    metrics = combo.fontMetrics()
    for index in range(combo.count()):
        width = max(width, metrics.horizontalAdvance(combo.itemText(index)) + extra)
    combo.setMinimumWidth(width)
    combo.view().setMinimumWidth(width)
    return combo


def set_corner_button_policy(button: QToolButton | QWidget, min_width: int = 92) -> None:
    button.setFixedHeight(CORNER_CONTROL_HEIGHT)
    button.setFixedWidth(min_width)
    font = button.font()
    if font.pointSize() <= 0:
        font.setPointSize(9)
    font.setBold(False)
    button.setFont(font)
    button.setStyleSheet("padding: 1px 6px; font-size: 9pt; font-weight: 400;")


def set_corner_combo_policy(combo: QComboBox, width: int) -> None:
    combo.setFixedHeight(CORNER_CONTROL_HEIGHT)
    combo.setFixedWidth(width)
    combo.view().setMinimumWidth(width)
    combo.setStyleSheet("padding: 1px 6px; font-size: 9pt;")


def set_bottom_action_button_policy(button: QPushButton | QToolButton) -> None:
    button.setFixedHeight(BOTTOM_ACTION_HEIGHT)


def bottom_action_bar(*buttons: QPushButton | QToolButton) -> QHBoxLayout:
    layout = QHBoxLayout()
    layout.setContentsMargins(*BOTTOM_ACTION_MARGINS)
    layout.setSpacing(BOTTOM_ACTION_SPACING)
    layout.addStretch(1)
    for button in buttons:
        set_bottom_action_button_policy(button)
        layout.addWidget(button)
    return layout


PRIORITY_STYLES = {
    "상": {"background": "#FFD6D6", "border": "#F4A3A3", "text": "#7F1D1D"},
    "중": {"background": "#D8EAFE", "border": "#A9CFF5", "text": "#1E3A8A"},
    "하": {"background": "transparent", "border": "transparent", "text": "#6B7280"},
}


def normalize_todo_group(entry: object, index: int = 0) -> str:
    if isinstance(entry, dict):
        name = str(entry.get("name", "")).strip()
    else:
        name = str(entry or "").strip()
    return name


def normalize_todo_groups(raw: object) -> list[str]:
    values = raw if isinstance(raw, list) else []
    groups = [normalize_todo_group(entry, index) for index, entry in enumerate(values)]
    groups = [group for group in groups if group]
    return groups or ["그룹 1"]

ACTION_ICONS = {
    "copy": "📋",
    "edit": "✏️",
    "delete": "✕",
    "play": "▶️",
    "view": "🔍",
    "pin": "★",
    "open": "🔗",
    "sticker": "🗒️",
    "history": "📜",
    "save": "💾",
}


class ElidedLabel(QLabel):
    def __init__(self, text: str) -> None:
        super().__init__()
        self._full_text = text
        self.setAlignment(CARD_LABEL_ALIGNMENT)
        self.setContentsMargins(0, 0, 0, 0)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(0)
        self.setToolTip(text)
        self._update_elided_text()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_elided_text()

    def _update_elided_text(self) -> None:
        width = max(0, self.contentsRect().width())
        text = self.fontMetrics().elidedText(self._full_text, Qt.TextElideMode.ElideRight, width)
        if self.text() != text:
            self.setText(text)


class ElidedMultilineLabel(QLabel):
    def __init__(self, text: str, max_lines: int = 2, line_height: int | None = None) -> None:
        super().__init__()
        self._full_text = text
        self._max_lines = max(1, max_lines)
        self._line_height = line_height
        self.setAlignment(CARD_LABEL_ALIGNMENT)
        self.setContentsMargins(0, 0, 0, 0)
        self.setToolTip(text)
        self.setWordWrap(True)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)
        if line_height is not None:
            self.setFixedHeight(line_height * self._max_lines + 4)
        else:
            self.setFixedHeight(self.fontMetrics().lineSpacing() * self._max_lines + 4)
        self._update_elided_text()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_elided_text()

    def _update_elided_text(self) -> None:
        width = max(0, self.contentsRect().width())
        lines = self._full_text.splitlines() or [self._full_text]
        visible = lines[: self._max_lines]
        if len(lines) > self._max_lines:
            visible[-1] += " ..."
        if self._line_height is not None:
            elided = [self.fontMetrics().elidedText(line, Qt.TextElideMode.ElideRight, width) for line in visible]
            safe = [l.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") for l in elided]
            text = f'<div style="line-height:{self._line_height}px;margin:0;padding:0;">{"<br>".join(safe)}</div>'
        else:
            text = "\n".join(self.fontMetrics().elidedText(line, Qt.TextElideMode.ElideRight, width) for line in visible)
        if self.text() != text:
            self.setText(text)


def make_card(
    title: str,
    subtitle: str = "",
    hotkey: str = "",
    single_line: bool = False,
    hotkey_color: str = "",
    compact: bool = False,
    card_height: int | None = None,
    card_size: str | None = None,
    word_wrap: bool = False,
    title_bold: bool = True,
    dense: bool = False,
    inline_hotkey: bool = False,
    title_max_lines: int = 2,
    subtitle_max_lines: int | None = None,
    dense_top_margin: int | None = None,
    v_center: bool = False,
    title_line_height: int | None = None,
) -> QWidget:
    card = QWidget()
    card.setObjectName("card")
    card.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    if card_size == "a":
        card_height = CARD_SIZE_A if card_height is None else card_height
        compact = True
    elif card_size == "b":
        card_height = CARD_SIZE_B if card_height is None else card_height
        compact = False
    elif card_size == "c":
        card_height = CARD_SIZE_C if card_height is None else card_height
        compact = False
    elif card_height is None:
        card_height = 56 if compact else CARD_SIZE_B
    card.setFixedHeight(card_height)
    layout = QVBoxLayout(card)
    if compact:
        layout.setContentsMargins(10, CARD_CONTENT_TOP_MARGIN, 10, CARD_CONTENT_TOP_MARGIN if v_center else 6)
        layout.setSpacing(4)
    elif dense:
        _top_m = CARD_CONTENT_TOP_MARGIN if dense_top_margin is None else dense_top_margin
        layout.setContentsMargins(12, _top_m, 12, _top_m if v_center else 6)
        layout.setSpacing(3)
    elif card_size == "c":
        layout.setContentsMargins(12, CARD_CONTENT_TOP_MARGIN, 12, 8)
        layout.setSpacing(5)
    else:
        layout.setContentsMargins(12, CARD_CONTENT_TOP_MARGIN, 12, CARD_CONTENT_TOP_MARGIN if v_center else 10)
        layout.setSpacing(6)
    row = QHBoxLayout()
    row.setSpacing(10)
    if word_wrap:
        title_label = ElidedMultilineLabel(title, max_lines=title_max_lines, line_height=title_line_height)
        title_label.setObjectName("cardTitle")
    else:
        title_display = title.splitlines()[0] + "..." if "\n" in title or "\r" in title else title
        title_label = ElidedLabel(title_display)
        title_label.setObjectName("cardTitle")
        title_label.setWordWrap(False)
        title_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        title_label.setMinimumWidth(0)
        title_label.setFixedHeight(22)
        title_label.setToolTip(title)
    if not title_bold:
        title_label.setStyleSheet("font-weight: 400;")
    row.addWidget(title_label, 1)
    if inline_hotkey and hotkey:
        # [정책] 홈화면 단축키 카드: 제목 행 우측에 인라인 표시, 투명 배경(hotkeyCapsInline)
        caps = make_hotkey_caps(hotkey, hotkey_color)
        caps.setObjectName("hotkeyCapsInline")
        row.addWidget(caps)
    layout.addLayout(row)
    if subtitle or card_size in {"b", "c"}:
        line_count = subtitle_max_lines if subtitle_max_lines is not None else 2 if card_size == "c" else 1 if compact else 2
        sub = ElidedMultilineLabel(subtitle, max_lines=line_count)
        sub.setObjectName("cardSubtitle")
        if subtitle_max_lines is not None:
            sub.setFixedHeight(sub.fontMetrics().lineSpacing() * line_count + 4)
        else:
            sub.setFixedHeight(38 if card_size == "c" else 18 if compact else 24)
        layout.addWidget(sub)
    layout.addStretch(1)
    if v_center:
        layout.insertStretch(0, 1)
    if not inline_hotkey:
        hotkey_overlay = QWidget(card)
        hotkey_overlay.setObjectName("cardOverlayHotkey")
        hotkey_overlay.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        hotkey_overlay.setStyleSheet("QWidget#cardOverlayHotkey { background: transparent; border: 0; }")
        h_layout = QHBoxLayout(hotkey_overlay)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(2)
        if hotkey:
            h_layout.addWidget(make_hotkey_caps(hotkey, hotkey_color))
        else:
            hotkey_overlay.hide()
        card._hotkey_overlay = hotkey_overlay

        _MARGIN = 8

        def _position_hotkey(c=card, h=hotkey_overlay, m=_MARGIN):
            try:
                size = h.sizeHint()
                h.setGeometry(
                    max(m, c.width() - size.width() - m),
                    max(m, c.height() - size.height() - m),
                    size.width(), size.height(),
                )
                h.raise_()
            except RuntimeError:
                pass

        def _on_card_resize(event, fn=_position_hotkey):
            fn()

        card.resizeEvent = _on_card_resize
        QTimer.singleShot(0, _position_hotkey)
    return card


def make_hotkey_caps(hotkey: str, hotkey_color: str = "") -> QWidget:
    container = QWidget()
    container.setObjectName("hotkeyCaps")
    container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    container.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
    parts = [part.strip() for part in hotkey.split("+") if part.strip()]
    for part in parts:
        cap = QLabel(part)
        cap.setObjectName("keyCap")
        cap.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cap.setFixedHeight(20)
        cap.setMinimumWidth(max(28, cap.fontMetrics().horizontalAdvance(part) + 24))
        cap.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        cap.setContentsMargins(0, 0, 0, 0)
        if hotkey_color:
            cap.setStyleSheet(f"QLabel#keyCap {{ background: {hotkey_color}; color: #1F2937; border-color: rgba(31, 41, 55, 0.25); }}")
        layout.addWidget(cap)
    return container


def confirm_shift_digit_hotkey(parent: QWidget, hotkey: dict | None) -> bool:
    if not hotkey:
        return True
    modifiers = {str(modifier).lower() for modifier in hotkey.get("modifiers", [])}
    key = str(hotkey.get("key", ""))
    if modifiers != {"shift"} or key not in {str(i) for i in range(10)}:
        return True
    return (
        QMessageBox.question(
            parent,
            "단축키 확인",
            "Shift+숫자 단축키는 특수문자 입력을 대체할 수 있습니다.\n그래도 등록하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        == QMessageBox.StandardButton.Yes
    )


def make_icon_button(text: str, tooltip: str, callback, danger: bool = False, size: QSize | None = None) -> QToolButton:
    button = QToolButton()
    button.setObjectName("dangerIconButton" if danger else "iconButton")
    button.setText(ACTION_ICONS.get(text, text))
    button.setToolTip(tooltip)
    button.setFixedSize(size or QSize(30, 28))
    if danger:
        button.setStyleSheet("QToolButton#dangerIconButton { color: #D7263D; font-size: 14pt; font-weight: 900; }")
    if size is not None:
        selector = "QToolButton#dangerIconButton" if danger else "QToolButton#iconButton"
        color_rule = "color: #D7263D;" if danger else ""
        button.setStyleSheet(
            f"{selector} {{ background: transparent; border: 0; border-radius: 3px; padding: {CARD_ACTION_ICON_PADDING}; "
            f"min-width: {size.width()}px; min-height: {size.height()}px; "
            f"max-width: {size.width()}px; max-height: {size.height()}px; font-size: 10pt; {color_rule} }}"
        )
    button.clicked.connect(callback)
    return button


def dialog_palette(parent: QWidget | None, accent: str | None = None) -> dict[str, str]:
    widget = parent
    while widget is not None:
        main = getattr(widget, "main", None)
        if main is not None and hasattr(main, "settings"):
            colors = dict(THEMES.get(main.settings.get("theme", "light"), THEMES["light"]))
            if accent:
                colors["accent"] = accent
            return colors
        if hasattr(widget, "settings"):
            colors = dict(THEMES.get(widget.settings.get("theme", "light"), THEMES["light"]))
            if accent:
                colors["accent"] = accent
            return colors
        parent_obj = widget.parent()
        widget = parent_obj if isinstance(parent_obj, QWidget) else None
    colors = dict(THEMES.get(DIALOG_THEME, THEMES["light"]))
    if accent:
        colors["accent"] = accent
    return colors


def style_list_selection(list_widget, colors: dict[str, str]) -> None:
    """QListWidget 선택 항목이 테마와 무관하게 항상 읽히도록 배경/글씨색을 명시한다.

    Qt 기본 팔레트에 맡기면 일부 테마 조합에서 선택된 항목의 배경과 글씨가 둘 다
    흰색이 되어 내용이 안 보이는 경우가 있어, 선택 시 배경만 강조색(hover)으로 바꾸고
    글씨색은 그대로 유지한다. 위젯에 이미 다른 스타일시트가 있으면 뒤에 이어붙인다.
    """
    extra = (
        f"QListWidget::item:selected {{ background: {colors['hover']}; color: {colors['text']}; }}"
        f"QListWidget::item:hover:!selected {{ background: {colors['hover']}; }}"
    )
    list_widget.setStyleSheet(list_widget.styleSheet() + extra)


def set_dialog_theme(theme: str) -> None:
    global DIALOG_THEME
    DIALOG_THEME = theme if theme in THEMES else "light"


class ModernInfoDialog(QDialog):
    def __init__(self, parent: QWidget, title: str, message: str, accent: str | None = None, buttons: tuple[str, ...] = ("확인",)) -> None:
        super().__init__(parent)
        colors = dialog_palette(parent, accent)
        self.choice = ""
        self.setWindowTitle(title)
        self.setModal(True)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 14)
        layout.setSpacing(12)
        header = QLabel(title)
        header.setObjectName("modernDialogTitle")
        message_label = QLabel(message)
        message_label.setWordWrap(True)
        message_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(header)
        layout.addWidget(message_label)
        row = QHBoxLayout()
        row.addStretch(1)
        for text in buttons:
            button = QToolButton()
            button.setText(text)
            button.setFixedHeight(32)
            button.clicked.connect(lambda checked=False, value=text: self.done_with_choice(value))
            row.addWidget(button)
        layout.addLayout(row)
        self.setStyleSheet(
            f"""
            QDialog {{ background: {colors["panel"]}; border: 1px solid {colors["border"]}; border-radius: 10px; }}
            QLabel {{ color: {colors["text"]}; }}
            QLabel#modernDialogTitle {{ color: {colors["accent"]}; font-size: 14pt; font-weight: 900; }}
            QToolButton {{ background: {colors["accent"]}; color: white; border: 0; border-radius: 6px; padding: 0 16px; font-weight: 800; }}
            """
        )
        self.resize(360, 170)

    def done_with_choice(self, choice: str) -> None:
        self.choice = choice
        self.accept()


def flash_taskbar(widget: QWidget, msec: int = 4000) -> None:
    """작업표시줄 아이콘을 msec 밀리초 동안 깜빡입니다."""
    from PyQt6.QtWidgets import QApplication
    window = widget.window()
    if window:
        QApplication.alert(window, msec)


def force_activate_window(widget: QWidget, focus_target: QWidget | None = None) -> None:
    """팝업 창을 최상위로 올리고 Win32 포그라운드 전환까지 시도한다.

    전역 단축키로 뜨는 팝업은 다른 앱이 포그라운드일 때 activateWindow()만으로는
    포커스를 얻지 못하는 경우가 많아 SetForegroundWindow 계열을 함께 호출한다.
    """
    if not widget.isVisible():
        return
    widget.raise_()
    widget.activateWindow()
    if focus_target is not None:
        focus_target.setFocus(Qt.FocusReason.PopupFocusReason)
    try:
        import ctypes

        hwnd = int(widget.winId())
        user32 = ctypes.windll.user32
        user32.ShowWindow(hwnd, 5)  # SW_SHOW
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        user32.SetActiveWindow(hwnd)
    except Exception:
        pass


def confirm_delete(parent: QWidget, message: str = "이 항목을 삭제하시겠습니까?") -> bool:
    colors = dialog_palette(parent)
    dialog = QDialog(parent)
    dialog.setWindowTitle("삭제 확인")
    dialog.setModal(True)
    dialog.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(18, 18, 18, 14)
    layout.setSpacing(12)
    header = QLabel("삭제 확인")
    header.setObjectName("modernDialogTitle")
    msg_label = QLabel(message)
    msg_label.setWordWrap(True)
    layout.addWidget(header)
    layout.addWidget(msg_label)
    row = QHBoxLayout()
    row.addStretch(1)
    cancel_btn = QToolButton()
    cancel_btn.setText("취소")
    cancel_btn.setFixedHeight(32)
    cancel_btn.clicked.connect(dialog.reject)
    delete_btn = QToolButton()
    delete_btn.setText("삭제")
    delete_btn.setFixedHeight(32)
    delete_btn.clicked.connect(dialog.accept)
    row.addWidget(cancel_btn)
    row.addWidget(delete_btn)
    layout.addLayout(row)
    danger = colors.get("danger", "#D7263D")
    bg = colors.get("bg", "#F8FAFC")
    text_color = colors.get("text", "#1F2433")
    border = colors.get("border", "#E5E7EB")
    panel = colors.get("panel", "#FFFFFF")
    dialog.setStyleSheet(
        f"QDialog {{ background: {panel}; border: 1px solid {border}; border-radius: 10px; }}"
        f"QLabel {{ color: {text_color}; }}"
        f"QLabel#modernDialogTitle {{ color: {danger}; font-size: 14pt; font-weight: 900; }}"
    )
    cancel_btn.setStyleSheet(
        f"QToolButton {{ background: {bg}; color: {text_color}; border: 1px solid {border}; border-radius: 6px; padding: 0 16px; font-weight: 600; }}"
    )
    delete_btn.setStyleSheet(
        f"QToolButton {{ background: {danger}; color: white; border: 0; border-radius: 6px; padding: 0 16px; font-weight: 800; }}"
    )
    dialog.resize(360, 150)
    return dialog.exec() == QDialog.DialogCode.Accepted


def show_modern_info(parent: QWidget, title: str, message: str, accent: str | None = None) -> None:
    ModernInfoDialog(parent, title, message, accent).exec()


def show_topmost_modern_info(parent: QWidget, title: str, message: str, accent: str | None = None) -> None:
    dialog = ModernInfoDialog(parent, title, message, accent)
    dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    try:
        import ctypes

        hwnd = int(dialog.winId())
        ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040)
        ctypes.windll.user32.BringWindowToTop(hwnd)
    except Exception:
        pass
    dialog.exec()


def show_modern_warning(parent: QWidget, title: str, message: str) -> None:
    colors = dialog_palette(parent)
    ModernInfoDialog(parent, title, message, colors.get("danger", "#D7263D")).exec()


def ask_modern_question(parent: QWidget, title: str, message: str, accent: str | None = None, yes_text: str = "확인", no_text: str = "취소") -> bool:
    dialog = ModernInfoDialog(parent, title, message, accent, (no_text, yes_text))
    dialog.exec()
    return dialog.choice == yes_text


def apply_modern_dialog_style(dialog: QDialog, accent: str = "#3B6CF5") -> None:
    colors = dialog_palette(dialog, accent)
    dialog.setStyleSheet(
        f"""
        QDialog {{ background: {colors["panel"]}; }}
        QLineEdit, QTextEdit, QComboBox, QSpinBox, QDateEdit {{
            border: 1px solid {colors["border"]};
            border-radius: 7px;
            padding: 6px;
            background: {colors["field"]};
            color: {colors["text"]};
        }}
        QPushButton {{
            background: {colors["accent"]};
            color: white;
            border: 0;
            border-radius: 7px;
            padding: 7px 14px;
            font-weight: 800;
        }}
        QPushButton:disabled {{ background: #CBD5E1; }}
        QLabel {{ color: {colors["text"]}; }}
        QLabel#cardTitle {{ color: {colors["accent"]}; font-weight: 900; }}
        """
    )


def add_card_actions(card: QWidget, actions: list[tuple[str, str, object, bool]]) -> None:
    # [정책] 카드 패널 위에 배치되는 항목은 테마 배경색보다 카드 배경색(panel)을 우선 적용한다.
    action_page = QWidget()
    action_page.setObjectName("cardActionBar")
    row = QHBoxLayout(action_page)
    row.setContentsMargins(CARD_ACTION_ROW_MARGIN_X, CARD_ACTION_ROW_MARGIN_Y, CARD_ACTION_ROW_MARGIN_X, CARD_ACTION_ROW_MARGIN_Y)
    row.setSpacing(CARD_ACTION_ROW_SPACING)
    row.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
    for text, tooltip, callback, danger in actions:
        row.addWidget(make_icon_button(text, tooltip, callback, danger, size=QSize(CARD_ACTION_ICON_SIZE, CARD_ACTION_ICON_SIZE)))
    set_card_action_widget(card, action_page)


def set_card_action_widget(card: QWidget, action_page: QWidget) -> None:
    # 기존 액션 오버레이 제거
    old = getattr(card, "_actions_overlay", None)
    if old is not None:
        try:
            old.hide()
            old.setParent(None)
            old.deleteLater()
        except RuntimeError:
            pass

    hotkey_overlay = getattr(card, "_hotkey_overlay", None)
    action_page.setParent(card)
    action_page.setObjectName("cardActionBar")
    action_page.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    action_page.hide()
    card._actions_overlay = action_page

    _MARGIN = CARD_ACTION_OVERLAY_MARGIN
    _Y_OFFSET = CARD_ACTION_OVERLAY_Y_OFFSET

    def _position(c=card, h=hotkey_overlay, a=action_page, m=_MARGIN, y_offset=_Y_OFFSET):
        try:
            a_size = a.sizeHint()
            a.setGeometry(
                max(m, c.width() - a_size.width() - m),
                max(m, c.height() - a_size.height() - m + y_offset),
                a_size.width(), a_size.height(),
            )
            a.raise_()
            if h is not None:
                size = h.sizeHint()
                h.setGeometry(
                    max(m, c.width() - size.width() - m),
                    max(m, c.height() - size.height() - m),
                    size.width(), size.height(),
                )
                h.raise_()
        except RuntimeError:
            pass

    # enterEvent/leaveEvent은 반드시 None을 반환해야 한다 (SIP sipBadCatcherResult 방지).
    # 캡처된 C++ 객체가 이미 해제된 경우 RuntimeError를 조용히 무시한다.
    def _on_enter(event, h=hotkey_overlay, a=action_page):
        try:
            a.setVisible(True)
            if h is not None:
                h.setVisible(False)
            a.raise_()
        except RuntimeError:
            pass

    def _on_leave(event, h=hotkey_overlay, a=action_page):
        try:
            a.setVisible(False)
            if h is not None and h.layout() is not None and h.layout().count() > 0:
                h.setVisible(True)
        except RuntimeError:
            pass

    def _on_resize(event, fn=_position):
        fn()

    card.enterEvent = _on_enter
    card.leaveEvent = _on_leave
    card.resizeEvent = _on_resize

    QTimer.singleShot(0, _position)


def add_card_status_label(card: QWidget) -> QLabel:
    label = QLabel("")
    label.setParent(card)
    label.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
    label.setStyleSheet("color: #168A4A; font-weight: 700; background: transparent; border: 0;")
    effect = QGraphicsOpacityEffect(label)
    effect.setOpacity(1.0)
    label.setGraphicsEffect(effect)
    label.hide()
    card._status_label = label
    return label


def show_card_status(card: QWidget, text: str, hold_ms: int = 1100, fade_ms: int = 900) -> None:
    label = getattr(card, "_status_label", None)
    if label is None:
        return
    try:
        old_animation = getattr(label, "_fade_animation", None)
        if old_animation is not None:
            old_animation.stop()
        effect = label.graphicsEffect()
        if isinstance(effect, QGraphicsOpacityEffect):
            effect.setOpacity(1.0)
        generation = int(getattr(label, "_status_generation", 0)) + 1
        label._status_generation = generation
        label.setText(text)
        label.adjustSize()
        _M = 8
        label.move(_M, max(_M, card.height() - label.height() - _M))
        label.raise_()
        label.show()

        def _fade_out(lbl=label, expected_generation=generation):
            try:
                if getattr(lbl, "_status_generation", None) != expected_generation:
                    return
                current_effect = lbl.graphicsEffect()
                if not isinstance(current_effect, QGraphicsOpacityEffect):
                    lbl.hide()
                    return
                animation = QPropertyAnimation(current_effect, b"opacity", lbl)
                animation.setDuration(fade_ms)
                animation.setStartValue(1.0)
                animation.setEndValue(0.0)

                def _hide_after_fade():
                    try:
                        lbl.hide()
                        current_effect.setOpacity(1.0)
                    except RuntimeError:
                        pass

                animation.finished.connect(_hide_after_fade)
                lbl._fade_animation = animation
                animation.start()
            except RuntimeError:
                pass

        QTimer.singleShot(hold_ms, _fade_out)
    except RuntimeError:
        pass


def add_favorite_badge_to_card(card: QWidget) -> None:
    card_layout = card.layout()
    if card_layout is None:
        return
    title_row_item = card_layout.itemAt(0)
    if title_row_item is None:
        return
    title_row = title_row_item.layout()
    if title_row is None:
        return
    remove_favorite_badge_from_card(card)
    badge = QLabel("★")
    badge.setObjectName("cardFavoriteBadge")
    badge.setFixedSize(16, 18)
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    badge.setStyleSheet(
        'QLabel#cardFavoriteBadge { color: #F5B301; background: transparent; border: 0; '
        'font-family: "Segoe UI Symbol", "Malgun Gothic"; font-size: 11pt; font-weight: 900; padding: 0 0 1px 0; }'
    )
    title_row.addWidget(badge)
    card._favorite_badge = badge


def remove_favorite_badge_from_card(card: QWidget) -> None:
    badge = getattr(card, "_favorite_badge", None)
    if badge is None:
        return
    try:
        badge.hide()
        badge.setParent(None)
        badge.deleteLater()
    except RuntimeError:
        pass
    card._favorite_badge = None


def ensure_item_meta(items: list[dict]) -> None:
    for index, item in enumerate(items):
        item.setdefault("sort_order", index)
        item.setdefault("usage_count", int(item.get("usage_count", 0) or 0))


def bump_usage(item: dict) -> None:
    item["usage_count"] = int(item.get("usage_count", 0) or 0) + 1
    used_at = now_iso()
    today = used_at[:10]
    if item.get("used_today_date") == today:
        item["used_today_count"] = int(item.get("used_today_count", 0) or 0) + 1
    else:
        item["used_today_date"] = today
        item["used_today_count"] = 1
    item["last_used_at"] = used_at


def apply_manual_reorder(items: list[dict], visible_items: list[dict], old_index: int, new_index: int) -> None:
    if old_index < 0 or old_index >= len(visible_items) or new_index < 0 or new_index >= len(visible_items):
        return
    moved = visible_items.pop(old_index)
    visible_items.insert(new_index, moved)
    for index, item in enumerate(visible_items):
        item["sort_order"] = index
    hidden_items = [item for item in items if item not in visible_items]
    offset = len(visible_items)
    for index, item in enumerate(hidden_items, start=offset):
        item["sort_order"] = index


def sort_items(
    items: list[dict],
    mode: str = "created",
    order: str = "desc",
    text_func: Callable[[dict], str] | None = None,
) -> list[dict]:
    ensure_item_meta(items)
    reverse = order == "desc"

    def text_value(item: dict) -> str:
        if text_func:
            return text_func(item)
        return str(item.get("name") or item.get("title") or item.get("text") or item.get("template") or "")

    def created_key(item: dict) -> tuple[str, int]:
        created = item.get("created_at") or item.get("updated_at") or item.get("copied_at") or ""
        return str(created), int(item.get("sort_order", 0) or 0)

    if mode == "name":
        key_func = lambda item: text_value(item).casefold()
    elif mode == "deadline":
        key_func = lambda item: item.get("deadline") or str(item.get("datetime", ""))[:10] or "9999-99-99"
    elif mode == "priority":
        ranks = {"상": 0, "중": 1, "하": 2, "": 2}
        key_func = lambda item: (ranks.get(str(item.get("priority", "하") or "하"), 2), created_key(item))
    elif mode == "manual":
        key_func = lambda item: int(item.get("sort_order", 0) or 0)
        reverse = False
    else:
        key_func = created_key
    return sorted(items, key=key_func, reverse=reverse)


class SortControls(QWidget):
    def __init__(
        self,
        changed: Callable[[], None] | None = None,
        parent: QWidget | None = None,
        modes: list[tuple[str, str]] | None = None,
        default_order: str = "desc",
    ) -> None:
        super().__init__(parent)
        self.setObjectName("sortControls")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)
        self.mode = QComboBox()
        for text, value in (modes or SORT_MODES):
            self.mode.addItem(text, value)
        self.order = QComboBox()
        for text, value in SORT_ORDERS:
            self.order.addItem(text, value)
        self.mode.setCurrentIndex(self.mode.findData("created"))
        self.order.setCurrentIndex(self.order.findData(default_order))
        layout.addWidget(self.mode)
        layout.addWidget(self.order)
        self.mode.setFixedHeight(CORNER_CONTROL_HEIGHT)
        self.order.setFixedHeight(CORNER_CONTROL_HEIGHT)
        fit_combo_to_contents(self.mode, CORNER_SORT_MODE_WIDTH)
        fit_combo_to_contents(self.order, CORNER_SORT_ORDER_WIDTH)
        self.setFixedHeight(32)
        self.setStyleSheet(
            """
            QWidget#sortControls {
                border: 0;
                background: transparent;
            }
            QWidget#sortControls QComboBox {
                padding: 2px 9px;
                min-height: 18px;
            }
            """
        )
        self.mode.currentIndexChanged.connect(self.update_order_enabled)
        if changed:
            self.mode.currentIndexChanged.connect(lambda _index: changed())
            self.order.currentIndexChanged.connect(lambda _index: changed())
        self.update_order_enabled()

    def sort_items(self, items: list[dict], text_func: Callable[[dict], str] | None = None) -> list[dict]:
        return sort_items(items, self.mode.currentData() or "created", self.order.currentData() or "desc", text_func)

    def is_manual(self) -> bool:
        return self.mode.currentData() == "manual"

    def update_order_enabled(self, *_args) -> None:
        self.order.setEnabled(not self.is_manual())


class GridPanel(QScrollArea):
    def __init__(self, columns: int = 2, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.columns = max(1, columns)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._cards: list[QWidget] = []
        self._drag_card: QWidget | None = None
        self._drag_start = QPoint()
        self._dragging = False
        self._on_reorder: Callable[[int, int], None] | None = None
        # 드래그한 카드를 다른 카드(그룹 폴더 등) 위에 놓았을 때 호출.
        # True를 반환하면 드롭이 처리된 것으로 보고 재정렬은 하지 않는다.
        self._on_drop: Callable[[int, int], bool] | None = None
        self.container = QWidget()
        self.container.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.grid = QGridLayout(self.container)
        self.grid.setContentsMargins(*GRID_PANEL_MARGINS)
        self.grid.setHorizontalSpacing(10)
        self.grid.setVerticalSpacing(10)
        self.setWidget(self.container)

    def clear(self) -> None:
        self._cards = []
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def add_cards(
        self,
        cards: list[QWidget],
        on_reorder: Callable[[int, int], None] | None = None,
        on_drop: Callable[[int, int], bool] | None = None,
    ) -> None:
        self.clear()
        self._cards = cards
        self._on_reorder = on_reorder
        self._on_drop = on_drop
        for i, card in enumerate(cards):
            card.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            card.setMinimumWidth(0)
            self._install_drag_filter(card)
            row, col = divmod(i, self.columns)
            self.grid.addWidget(card, row, col)
        for col in range(self.columns):
            self.grid.setColumnStretch(col, 1)
        self.grid.setRowStretch((len(cards) + self.columns - 1) // self.columns, 1)

    def _install_drag_filter(self, widget: QWidget) -> None:
        widget.installEventFilter(self)
        for child in widget.findChildren(QWidget):
            child.installEventFilter(self)

    def _card_for_widget(self, widget: QWidget) -> QWidget | None:
        current: QWidget | None = widget
        while current is not None:
            if current in self._cards:
                return current
            parent = current.parent()
            current = parent if isinstance(parent, QWidget) else None
        return None

    def eventFilter(self, watched, event) -> bool:
        if not (self._on_reorder or self._on_drop) or not isinstance(watched, QWidget):
            return super().eventFilter(watched, event)
        if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            card = self._card_for_widget(watched)
            if card:
                self._drag_card = card
                self._drag_start = event.globalPosition().toPoint()
                self._dragging = False
        elif event.type() == QEvent.Type.MouseMove and self._drag_card:
            if (event.globalPosition().toPoint() - self._drag_start).manhattanLength() > 8:
                self._dragging = True
                self._drag_card.setCursor(Qt.CursorShape.ClosedHandCursor)
                self._drag_card.setProperty("dragging", True)
                self._drag_card.style().unpolish(self._drag_card)
                self._drag_card.style().polish(self._drag_card)
        elif event.type() == QEvent.Type.MouseButtonRelease and self._drag_card:
            card = self._drag_card
            old_index = self._cards.index(card) if card in self._cards else -1
            new_index = self._drop_index(event.globalPosition().toPoint())
            card.setCursor(Qt.CursorShape.ArrowCursor)
            card.setProperty("dragging", False)
            card.style().unpolish(card)
            card.style().polish(card)
            self._drag_card = None
            was_dragging = self._dragging
            self._dragging = False
            if was_dragging and old_index >= 0 and new_index >= 0 and old_index != new_index:
                if self._on_drop is not None and self._on_drop(old_index, new_index):
                    return True
                if self._on_reorder is not None:
                    self._on_reorder(old_index, new_index)
                    return True
        return super().eventFilter(watched, event)

    def _drop_index(self, global_pos: QPoint) -> int:
        if not self._cards:
            return -1
        container_pos = self.container.mapFromGlobal(global_pos)
        for index, card in enumerate(self._cards):
            if card.geometry().contains(container_pos):
                return index
        return len(self._cards) - 1


def add_widget_item(list_widget, widget: QWidget) -> QListWidgetItem:
    item = QListWidgetItem(list_widget)
    item.setSizeHint(widget.sizeHint())
    list_widget.addItem(item)
    list_widget.setItemWidget(item, widget)
    return item


class HotkeyFields(QWidget):
    def __init__(self, hotkey: dict[str, Any] | None = None) -> None:
        super().__init__()
        self.setMinimumHeight(34)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.ctrl = QCheckBox("Ctrl")
        self.alt = QCheckBox("Alt")
        self.shift = QCheckBox("Shift")
        self.win = QCheckBox("Win")
        self.key = QComboBox()
        self.key.addItems(HOTKEY_KEYS)
        fit_combo_to_contents(self.key, min_width=86, extra=56)
        self.key.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.ctrl)
        layout.addWidget(self.alt)
        layout.addWidget(self.shift)
        layout.addWidget(self.win)
        layout.addWidget(self.key, 1)
        self.set_hotkey(hotkey)

    def set_hotkey(self, hotkey: dict[str, Any] | None) -> None:
        if not hotkey:
            return
        modifiers = {str(modifier).lower() for modifier in hotkey.get("modifiers", [])}
        self.ctrl.setChecked("ctrl" in modifiers)
        self.alt.setChecked("alt" in modifiers)
        self.shift.setChecked("shift" in modifiers)
        self.win.setChecked(bool(modifiers & {"win", "windows", "meta", "super"}))
        key = hotkey.get("key")
        if key:
            index = self.key.findText(str(key))
            if index >= 0:
                self.key.setCurrentIndex(index)

    def value(self) -> dict[str, Any] | None:
        modifiers = []
        if self.ctrl.isChecked():
            modifiers.append("ctrl")
        if self.alt.isChecked():
            modifiers.append("alt")
        if self.shift.isChecked():
            modifiers.append("shift")
        if self.win.isChecked():
            modifiers.append("win")
        if not modifiers:
            return None
        return {"modifiers": modifiers, "key": self.key.currentText()}


class TextItemDialog(QDialog):
    def __init__(
        self,
        title: str,
        item: dict[str, Any] | None = None,
        code: bool = False,
        require_name: bool = True,
        help_text: str = "",
    ) -> None:
        super().__init__()
        self.setWindowTitle(title)
        apply_modern_dialog_style(self)
        if code:
            self.setMinimumWidth(500)
        self.item = item or {}
        self.code = code
        self.require_name = require_name
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(self.item.get("name", ""))
        self.text = QTextEdit()
        self.text.setPlainText(self.item.get("text", ""))
        self.hotkey = HotkeyFields(self.item.get("hotkey"))
        if require_name:
            form.addRow("이름", self.name)
        if code:
            self._setup_code_editor(form)
        form.addRow("내용", self.text)
        form.addRow("단축키", self.hotkey)
        layout.addLayout(form)
        footer = QHBoxLayout()
        hint = QLabel(help_text or "줄바꿈 형태 지원 · 변수: {clipboard} {date} {date:yyyy-MM-dd} {time} {cursor}")
        hint.setObjectName("mutedText")
        footer.addWidget(hint)
        footer.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("확인")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        footer.addWidget(buttons)
        layout.addLayout(footer)

    # --- 코드 편집기 -----------------------------------------------------

    def _setup_code_editor(self, form: QFormLayout) -> None:
        """언어 선택 + 구문 강조를 붙인다. '자동 감지'면 내용에서 언어를 추정한다."""
        from ui.code_syntax import (
            AUTO_LANGUAGE,
            CodeHighlighter,
            LanguageComboBox,
            apply_code_editor_style,
            detect_language,
            is_dark_background,
            language_label,
            normalize_language,
        )

        self.setMinimumWidth(620)
        colors = dialog_palette(self)
        dark = is_dark_background(colors["field"])
        apply_code_editor_style(self.text, dark, colors["border"])
        self.text.setMinimumHeight(260)

        saved_language = normalize_language(self.item.get("language"))
        # 이전에 사용자가 이 대화상자에서 수동으로 언어를 고정한 적(language_auto=False)이 없다면
        # 항상 '자동 감지'를 기본 선택으로 보여준다.
        auto_mode = bool(self.item.get("language_auto", True))
        self.language = LanguageComboBox(AUTO_LANGUAGE if auto_mode else saved_language)
        self.highlighter = CodeHighlighter(self.text.document(), saved_language, dark)
        self.language_hint = QLabel("")
        self.language_hint.setObjectName("mutedText")

        language_row = QWidget()
        language_layout = QHBoxLayout(language_row)
        language_layout.setContentsMargins(0, 0, 0, 0)
        language_layout.setSpacing(8)
        language_layout.addWidget(self.language)
        language_layout.addWidget(self.language_hint, 1)
        form.addRow("코드 형식", language_row)

        self._detect_timer = QTimer(self)
        self._detect_timer.setSingleShot(True)
        self._detect_timer.setInterval(300)
        self._detect_timer.timeout.connect(self._sync_highlight_language)
        self.language.language_changed.connect(lambda _value: self._sync_highlight_language())
        self.text.textChanged.connect(self._detect_timer.start)
        self._detect_language = detect_language
        self._language_label = language_label
        self._sync_highlight_language()

    def _sync_highlight_language(self) -> None:
        """콤보가 '자동 감지'면 내용으로 언어를 정하고, 아니면 고른 언어를 그대로 쓴다."""
        from ui.code_syntax import AUTO_LANGUAGE

        selected = self.language.language()
        if selected == AUTO_LANGUAGE:
            resolved = self._detect_language(self.text.toPlainText())
            self.language_hint.setText(f"자동 인식: {self._language_label(resolved)}")
        else:
            resolved = selected
            self.language_hint.setText("")
        self.highlighter.set_language(resolved)

    def resolved_language(self) -> str:
        if not self.code:
            return ""
        # 디바운스 타이머가 아직 안 돌았을 수 있어 저장 직전에 한 번 더 맞춘다.
        if self._detect_timer.isActive():
            self._detect_timer.stop()
            self._sync_highlight_language()
        return self.highlighter.language

    def value(self) -> dict[str, Any]:
        data = dict(self.item)
        name = self.name.text().strip() if self.require_name else (self.text.toPlainText().splitlines() or [""])[0][:30].strip()
        data.update({"name": name, "text": self.text.toPlainText(), "hotkey": self.hotkey.value()})
        if self.code:
            from ui.code_syntax import AUTO_LANGUAGE

            auto_mode = self.language.language() == AUTO_LANGUAGE
            data.update(
                {
                    # 자동 감지여도 확장자 판단에 쓸 수 있도록 확정된 언어를 저장한다.
                    "language": self.resolved_language(),
                    "language_auto": auto_mode,
                    "type": "code",
                }
            )
        else:
            data.update({"type": "text"})
        return data

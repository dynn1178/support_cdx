from __future__ import annotations

"""전용 단축키 — 특정 프로그램(프로세스)이 활성 창일 때만 동작하는 단축키.

전역 단축키(HotkeyManager)로 등록하되, 콜백에서 현재 활성 창의 프로세스가
등록해둔 대상 프로그램과 일치할 때만 매크로 스크립트를 실행한다(그 외에는
아무 동작도 하지 않는다). 실행 자체는 매크로 탭의 MacroPlayerThread를 그대로
재사용한다 — 스크립트 문법·Send 처리·정지 방법(마우스 가운데 버튼)이 매크로와
완전히 동일하다.

단축키를 만드는 3가지 방식(스크립트 입력 / 직접 지정 / 녹화)은 모두 결국 매크로와 같은
스크립트(Send 줄 + Click/MouseMove/MouseDrag 줄)로 수렴한다. 직접 지정·녹화는 Ctrl/Alt/Shift는
누르기(Down)/떼기(Up)를 구분해 기록하고, 그 외 키는 누르는 즉시 떼어지는 입력(Tap) 하나로
기록한다 — 예: 엑셀 셀 병합(Alt→H→M→C, 각 키를 따로 탭)은 Alt만 Down/Up으로 감싸고 h/m/c는
순서대로 탭 입력하면 된다.

마우스(이동/클릭/더블클릭/우클릭/드래그)도 단계로 추가·녹화할 수 있다. 좌표는 화면 전체
기준이 아니라 대상 프로그램 창의 클라이언트 영역(제목표시줄·테두리 제외) 기준으로 저장되므로
(CoordMode, Mouse, Client), 창을 옮기거나 크기를 바꿔도 같은 위치를 가리킨다.
"""

from PyQt6.QtCore import Qt, QObject, QTimer, pyqtSignal
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.macro_script import MacroScriptError, escape_send_literal, parse_script
from app.utils import display_hotkey, new_id, now_iso
from ui.common import (
    HOTKEY_KEYS,
    GridPanel,
    HotkeyFields,
    SortControls,
    add_card_actions,
    apply_manual_reorder,
    bump_usage,
    confirm_delete,
    confirm_shift_digit_hotkey,
    dialog_palette,
    make_card,
    style_list_selection,
)


TAP_NAMED_KEYS = ["Enter", "Tab", "Esc", "Space", "Backspace", "Delete", "Insert", "Home", "End", "Up", "Down", "Left", "Right", "PgUp", "PgDn"]
_MODIFIER_AHK_NAME = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift"}
_MODIFIER_KEY_NAMES = {
    "ctrl": "ctrl", "ctrl_l": "ctrl", "ctrl_r": "ctrl",
    "alt": "alt", "alt_l": "alt", "alt_r": "alt", "alt_gr": "alt",
    "shift": "shift", "shift_l": "shift", "shift_r": "shift",
}


_MOUSE_BUTTON_LABEL = {"left": "왼쪽", "right": "오른쪽", "middle": "가운데"}


def step_label(step: dict) -> str:
    kind = step["kind"]
    if kind in ("down", "up"):
        key = step["key"]
        return f"{_MODIFIER_AHK_NAME.get(key, key)} {'누르기 (Down)' if kind == 'down' else '떼기 (Up)'}"
    if kind == "tap":
        return f"{step['key']} 입력 (Tap)"
    if kind == "move":
        return f"({step['x']}, {step['y']})로 마우스 이동"
    if kind == "click":
        button_label = _MOUSE_BUTTON_LABEL.get(step.get("button", "left"), step.get("button", "left"))
        action = "더블클릭" if step.get("double") else "클릭"
        return f"({step['x']}, {step['y']}) {button_label} {action}"
    if kind == "drag":
        button_label = _MOUSE_BUTTON_LABEL.get(step.get("button", "left"), step.get("button", "left"))
        return f"({step['x1']}, {step['y1']}) → ({step['x2']}, {step['y2']}) {button_label} 드래그"
    return str(step)


def steps_to_script_text(steps: list[dict]) -> str:
    """단계 목록을 매크로 스크립트 텍스트로 바꾼다.

    키보드 단계는 이어붙여 하나의 Send 줄로 묶고, 마우스 단계(이동/클릭/드래그)가 나오면
    그때까지 모은 Send 줄을 먼저 내보낸 뒤 별도 줄로 추가한다. 마우스 단계가 하나라도
    있으면 맨 앞에 CoordMode, Mouse, Client 를 넣어 좌표를 대상 창의 클라이언트 영역
    기준으로 해석하게 한다(창 위치·크기가 달라져도 같은 지점을 가리킴).
    """
    if not steps:
        return ""
    lines: list[str] = []
    if any(step["kind"] in ("move", "click", "drag") for step in steps):
        lines.append("CoordMode, Mouse, Client")
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            lines.append("Send, " + "".join(buffer))
            buffer.clear()

    for step in steps:
        kind = step["kind"]
        if kind in ("down", "up"):
            name = _MODIFIER_AHK_NAME.get(step["key"], step["key"].capitalize())
            buffer.append("{" + name + ("Down" if kind == "down" else "Up") + "}")
        elif kind == "tap":
            key = step["key"]
            buffer.append(escape_send_literal(key) if len(key) == 1 else "{" + key + "}")
        elif kind == "move":
            flush()
            lines.append(f"MouseMove, {step['x']}, {step['y']}")
        elif kind == "click":
            flush()
            button = step.get("button", "left")
            command = "MouseDoubleClick" if step.get("double") else "MouseClick"
            lines.append(f"{command}, {button}, {step['x']}, {step['y']}")
        elif kind == "drag":
            flush()
            button = step.get("button", "left")
            lines.append(f"MouseDrag, {step['x1']}, {step['y1']}, {step['x2']}, {step['y2']}, {button}")
    flush()
    return "\n".join(lines)


def _client_relative_position(process_exe: str, x: int, y: int) -> tuple[int, int]:
    """화면 좌표(x, y)를 대상 프로그램 창의 클라이언트 영역 기준 좌표로 바꾼다.

    대상 창을 찾지 못하면(프로그램이 꺼져 있는 등) 화면 좌표를 그대로 돌려준다.
    """
    from app import win_control

    hwnd = win_control.find_window(f"ahk_exe {process_exe}") if process_exe else None
    origin = win_control.client_origin(hwnd) if hwnd else None
    if origin:
        return (x - origin[0], y - origin[1])
    return (x, y)


class KeyRecorder(QObject):
    """전용 단축키 녹화용 — 키보드와 마우스(클릭/더블클릭/드래그)를 듣는다.

    마우스 좌표는 process_exe로 지정한 대상 창을 찾아 클라이언트 영역 기준으로 변환해
    캡처한다(찾지 못하면 화면 좌표 그대로). 마우스 이동 자체는 기록하지 않고(너무 잦아서),
    클릭/더블클릭/드래그만 기록한다 — 누른 채로 일정 거리 이상 움직이면 드래그로,
    짧은 시간 안에 같은 위치를 두 번 클릭하면 더블클릭으로 인식한다.
    """

    step_captured = pyqtSignal(dict)

    _DRAG_THRESHOLD_PX = 6
    _DOUBLE_CLICK_WINDOW_SEC = 0.4
    _DOUBLE_CLICK_RADIUS_PX = 4

    def __init__(self, process_exe: str = "") -> None:
        super().__init__()
        self.process_exe = process_exe
        self._pressed_mods: set[str] = set()
        self._pressed_keys: set[str] = set()
        self.keyboard_listener = None
        self.mouse_listener = None
        self._press_screen_pos: tuple[int, int] | None = None
        self._last_click_pos: tuple[int, int] | None = None
        self._last_click_time = 0.0

    def _key_name(self, key) -> str:
        try:
            char = key.char
            if char and len(char) == 1 and ord(char) < 32:
                return chr(ord(char) + 96)
            return str(char).lower() if char else ""
        except AttributeError:
            return str(key).replace("Key.", "").lower()

    def _on_press(self, key) -> None:
        name = self._key_name(key)
        if not name:
            return
        mod = _MODIFIER_KEY_NAMES.get(name)
        if mod:
            if mod in self._pressed_mods:
                return
            self._pressed_mods.add(mod)
            self.step_captured.emit({"kind": "down", "key": mod})
            return
        if name in self._pressed_keys:
            return  # 키 반복(오토리핏) 무시
        self._pressed_keys.add(name)
        from app.macro_script import PYNPUT_KEY_TO_AHK

        if len(name) == 1:
            tap_key = name
        else:
            tap_key = PYNPUT_KEY_TO_AHK.get(name)
        if tap_key is None:
            return
        self.step_captured.emit({"kind": "tap", "key": tap_key})

    def _on_release(self, key) -> None:
        name = self._key_name(key)
        mod = _MODIFIER_KEY_NAMES.get(name)
        if mod:
            if mod in self._pressed_mods:
                self._pressed_mods.discard(mod)
                self.step_captured.emit({"kind": "up", "key": mod})
        elif name:
            self._pressed_keys.discard(name)

    def _button_name(self, button) -> str:
        text = str(button).lower()
        if "right" in text:
            return "right"
        if "middle" in text:
            return "middle"
        return "left"

    def _on_click(self, x: int, y: int, button, pressed: bool) -> None:
        import time

        if pressed:
            self._press_screen_pos = (x, y)
            return
        if self._press_screen_pos is None:
            return
        px, py = self._press_screen_pos
        self._press_screen_pos = None
        button_name = self._button_name(button)
        moved = ((x - px) ** 2 + (y - py) ** 2) ** 0.5
        if moved > self._DRAG_THRESHOLD_PX:
            x1, y1 = _client_relative_position(self.process_exe, px, py)
            x2, y2 = _client_relative_position(self.process_exe, x, y)
            self._last_click_pos = None
            self.step_captured.emit({"kind": "drag", "x1": x1, "y1": y1, "x2": x2, "y2": y2, "button": button_name})
            return
        cx, cy = _client_relative_position(self.process_exe, x, y)
        now = time.monotonic()
        if (
            self._last_click_pos is not None
            and abs(cx - self._last_click_pos[0]) <= self._DOUBLE_CLICK_RADIUS_PX
            and abs(cy - self._last_click_pos[1]) <= self._DOUBLE_CLICK_RADIUS_PX
            and now - self._last_click_time < self._DOUBLE_CLICK_WINDOW_SEC
        ):
            self._last_click_pos = None
            self.step_captured.emit({"kind": "click", "button": button_name, "double": True, "x": cx, "y": cy, "_merge_last": True})
            return
        self._last_click_pos = (cx, cy)
        self._last_click_time = now
        self.step_captured.emit({"kind": "click", "button": button_name, "double": False, "x": cx, "y": cy})

    def start(self) -> None:
        from pynput import keyboard as pynput_keyboard
        from pynput import mouse as pynput_mouse

        self.keyboard_listener = pynput_keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self.keyboard_listener.start()
        self.mouse_listener = pynput_mouse.Listener(on_click=self._on_click)
        self.mouse_listener.start()

    def stop(self) -> None:
        for attr in ("keyboard_listener", "mouse_listener"):
            listener = getattr(self, attr)
            if listener:
                try:
                    listener.stop()
                except Exception:
                    pass
                setattr(self, attr, None)


class MousePositionCaptureDialog(QDialog):
    """3초 뒤 현재 마우스 위치를 대상 창의 클라이언트 좌표로 캡처한다."""

    captured = pyqtSignal(tuple)  # (x, y) — 대상 창 기준(찾지 못하면 화면 기준)

    def __init__(self, process_exe: str, position_label: str, parent=None) -> None:
        super().__init__(parent)
        self.process_exe = process_exe
        self.setWindowTitle("마우스 위치 캡처")
        layout = QVBoxLayout(self)
        self.label = QLabel(f"3초 후 현재 마우스 위치를 '{position_label}' 위치로 캡처합니다.\n캡처하고 싶은 위치로 마우스를 옮겨두세요.")
        self.label.setWordWrap(True)
        layout.addWidget(self.label)
        self._countdown = 3
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    def _tick(self) -> None:
        self._countdown -= 1
        if self._countdown <= 0:
            self._timer.stop()
            pos = QCursor.pos()
            self.captured.emit(_client_relative_position(self.process_exe, pos.x(), pos.y()))
            self.accept()
            return
        self.label.setText(f"{self._countdown}초 후 캡처됩니다. 캡처하고 싶은 위치로 마우스를 옮겨두세요.")


class ProcessPickerDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("대상 프로그램 선택")
        self.resize(440, 420)
        layout = QVBoxLayout(self)
        hint = QLabel("단축키를 적용할 프로그램을 선택하세요. 목록에 없다면 해당 프로그램을 먼저 실행한 뒤 새로고침하세요.")
        hint.setObjectName("mutedText")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.search = QLineEdit()
        self.search.setPlaceholderText("검색...")
        self.search.textChanged.connect(self._apply_filter)
        layout.addWidget(self.search)
        self.list = QListWidget()
        style_list_selection(self.list, dialog_palette(self))
        self.list.itemDoubleClicked.connect(lambda _item: self.accept())
        layout.addWidget(self.list, 1)
        self._entries: list[tuple[str, str]] = []

        refresh = QPushButton("새로고침")
        refresh.clicked.connect(self._reload)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("선택")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        row = QHBoxLayout()
        row.addWidget(refresh)
        row.addStretch(1)
        row.addWidget(buttons)
        layout.addLayout(row)
        self._reload()

    def _reload(self) -> None:
        from app import win_control

        self._entries = win_control.list_foreground_processes()
        self._apply_filter()

    def _apply_filter(self) -> None:
        query = self.search.text().strip().lower()
        self.list.clear()
        for exe, title in self._entries:
            label = f"{exe}  —  {title}"
            if query and query not in label.lower():
                continue
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, (exe, title))
            self.list.addItem(item)

    def selected(self) -> tuple[str, str] | None:
        item = self.list.currentItem()
        if not item:
            return None
        return item.data(Qt.ItemDataRole.UserRole)


class ProcessHotkeyDialog(QDialog):
    def __init__(self, item: dict) -> None:
        super().__init__()
        self.item = item
        self.process_exe = item.get("process_exe", "")
        self.direct_steps: list[dict] = []
        self.record_steps: list[dict] = []
        self.recorder: KeyRecorder | None = None
        self.setWindowTitle(f"프로그램별 단축키 - {item.get('name') or '새 항목'}")
        self.resize(700, 580)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(item.get("name", ""))
        self.process_label_widget = QLabel(self._process_display())
        self.process_label_widget.setObjectName("mutedText")
        pick_btn = QPushButton("대상 프로그램 선택...")
        pick_btn.clicked.connect(self.pick_process)
        process_row = QHBoxLayout()
        process_row.setContentsMargins(0, 0, 0, 0)
        process_row.addWidget(pick_btn)
        process_row.addWidget(self.process_label_widget, 1)
        process_widget = QWidget()
        process_widget.setLayout(process_row)
        self.hotkey = HotkeyFields(item.get("hotkey"))
        form.addRow("이름", self.name)
        form.addRow("대상 프로그램", process_widget)
        form.addRow("실행 단축키", self.hotkey)
        layout.addLayout(form)

        hint = QLabel("대상 프로그램이 활성 창일 때만 이 단축키가 동작합니다. 다른 프로그램에서는 이 키 조합이 아무 동작도 하지 않습니다.")
        hint.setObjectName("mutedText")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_script_tab(), "스크립트 입력")
        self.tabs.addTab(self._build_direct_tab(), "직접 지정")
        self.tabs.addTab(self._build_record_tab(), "녹화")
        layout.addWidget(self.tabs, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("저장")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
        buttons.accepted.connect(self._try_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # --- 대상 프로그램 -----------------------------------------------------

    def _process_display(self) -> str:
        return self.process_exe or "(선택 안 됨)"

    def pick_process(self) -> None:
        dialog = ProcessPickerDialog(self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        selected = dialog.selected()
        if not selected:
            return
        exe, title = selected
        self.process_exe = exe
        self.process_label_widget.setText(f"{exe}  ({title})")

    # --- 스크립트 입력 -----------------------------------------------------

    def _build_script_tab(self) -> QWidget:
        from ui.code_syntax import apply_code_editor_style, is_dark_background
        from ui.tab_macro import MacroScriptHighlighter

        page = QWidget()
        layout = QVBoxLayout(page)
        self.script_edit = QTextEdit()
        self.script_edit.setAcceptRichText(False)
        self.script_edit.setPlainText(self.item.get("script", ""))
        self.script_edit.setPlaceholderText("Send, {AltDown}{AltUp}hmc")
        colors = dialog_palette(self)
        dark = is_dark_background(colors["field"])
        apply_code_editor_style(self.script_edit, dark, colors["border"])
        self.script_highlighter = MacroScriptHighlighter(self.script_edit.document(), dark)
        layout.addWidget(self.script_edit, 1)
        toolbar = QHBoxLayout()
        help_btn = QPushButton("명령어 도움말")
        help_btn.clicked.connect(self._show_help)
        toolbar.addWidget(help_btn)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)
        hint = QLabel("매크로와 동일한 스크립트 문법입니다 (Send, Sleep, {CtrlDown}/{CtrlUp} 등). '직접 지정'·'녹화' 탭에서 만든 내용도 이 칸에 채워집니다.")
        hint.setObjectName("mutedText")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        return page

    def _show_help(self) -> None:
        from ui.tab_macro import MacroReferenceDialog

        if getattr(self, "_reference_dialog", None) is None:
            self._reference_dialog = MacroReferenceDialog(self)
        self._reference_dialog.show()
        self._reference_dialog.raise_()
        self._reference_dialog.activateWindow()

    # --- 직접 지정 ---------------------------------------------------------

    def _build_direct_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        hint = QLabel(
            "Ctrl/Alt/Shift는 누르기(Down)·떼기(Up)를 따로 추가해 조합을 만들고, 그 외 키는 누르는 즉시 떼어지는 "
            "입력(Tap) 한 번으로 추가됩니다. 마우스 이동/클릭/드래그는 버튼을 누르면 3초 뒤 현재 마우스 위치를 "
            "대상 프로그램 창 기준 좌표로 캡처합니다(대상 프로그램을 먼저 선택해주세요). 최대 10단계까지 만들 수 있습니다.\n"
            "예: 엑셀 셀 병합(Alt→H→M→C) = Alt 누르기 → Alt 떼기 → H 입력 → M 입력 → C 입력"
        )
        hint.setObjectName("mutedText")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.direct_list = QListWidget()
        style_list_selection(self.direct_list, dialog_palette(self))
        layout.addWidget(self.direct_list, 1)

        mod_row = QHBoxLayout()
        self.mod_combo = QComboBox()
        self.mod_combo.addItems(["Ctrl", "Alt", "Shift"])
        down_btn = QPushButton("누르기(Down) 추가")
        up_btn = QPushButton("떼기(Up) 추가")
        down_btn.clicked.connect(lambda: self._add_direct_step("down", self.mod_combo.currentText().lower()))
        up_btn.clicked.connect(lambda: self._add_direct_step("up", self.mod_combo.currentText().lower()))
        mod_row.addWidget(QLabel("보조키"))
        mod_row.addWidget(self.mod_combo)
        mod_row.addWidget(down_btn)
        mod_row.addWidget(up_btn)
        mod_row.addStretch(1)
        layout.addLayout(mod_row)

        tap_row = QHBoxLayout()
        self.tap_combo = QComboBox()
        self.tap_combo.addItems(list(HOTKEY_KEYS) + TAP_NAMED_KEYS)
        tap_btn = QPushButton("입력(Tap) 추가")
        tap_btn.clicked.connect(lambda: self._add_direct_step("tap", self._tap_key_value()))
        tap_row.addWidget(QLabel("키"))
        tap_row.addWidget(self.tap_combo)
        tap_row.addWidget(tap_btn)
        tap_row.addStretch(1)
        layout.addLayout(tap_row)

        mouse_row = QHBoxLayout()
        self.mouse_button_combo = QComboBox()
        self.mouse_button_combo.addItems(["왼쪽", "오른쪽", "가운데"])
        self.mouse_double_check = QCheckBox("더블클릭")
        move_btn = QPushButton("이동 위치 캡처")
        click_btn = QPushButton("클릭 위치 캡처")
        drag_btn = QPushButton("드래그 캡처(시작→도착)")
        move_btn.clicked.connect(self._add_mouse_move_step)
        click_btn.clicked.connect(self._add_mouse_click_step)
        drag_btn.clicked.connect(self._add_mouse_drag_step)
        mouse_row.addWidget(QLabel("마우스 버튼"))
        mouse_row.addWidget(self.mouse_button_combo)
        mouse_row.addWidget(self.mouse_double_check)
        mouse_row.addWidget(move_btn)
        mouse_row.addWidget(click_btn)
        mouse_row.addWidget(drag_btn)
        mouse_row.addStretch(1)
        layout.addLayout(mouse_row)

        manage_row = QHBoxLayout()
        remove_btn = QPushButton("선택 삭제")
        clear_btn = QPushButton("전체 삭제")
        apply_btn = QPushButton("스크립트에 반영")
        remove_btn.clicked.connect(self._remove_direct_step)
        clear_btn.clicked.connect(self._clear_direct_steps)
        apply_btn.clicked.connect(self._apply_direct_steps)
        manage_row.addWidget(remove_btn)
        manage_row.addWidget(clear_btn)
        manage_row.addStretch(1)
        manage_row.addWidget(apply_btn)
        layout.addLayout(manage_row)
        return page

    def _tap_key_value(self) -> str:
        text = self.tap_combo.currentText()
        return text if text in TAP_NAMED_KEYS else text.lower()

    def _mouse_button_value(self) -> str:
        return {"왼쪽": "left", "오른쪽": "right", "가운데": "middle"}.get(self.mouse_button_combo.currentText(), "left")

    def _add_direct_step(self, kind: str, key: str) -> None:
        if len(self.direct_steps) >= 10:
            QMessageBox.information(self, "단계 제한", "직접 지정 방식은 최대 10단계까지 추가할 수 있습니다.")
            return
        step = {"kind": kind, "key": key}
        self.direct_steps.append(step)
        self.direct_list.addItem(step_label(step))

    def _capture_mouse_position(self, position_label: str) -> tuple[int, int] | None:
        if not self.process_exe:
            QMessageBox.warning(self, "대상 프로그램 필요", "마우스 위치를 캡처하려면 먼저 대상 프로그램을 선택해주세요.")
            return None
        result: dict[str, tuple[int, int]] = {}
        dialog = MousePositionCaptureDialog(self.process_exe, position_label, self)
        dialog.captured.connect(lambda pos: result.update(xy=pos))
        dialog.exec()
        return result.get("xy")

    def _add_mouse_move_step(self) -> None:
        if len(self.direct_steps) >= 10:
            QMessageBox.information(self, "단계 제한", "직접 지정 방식은 최대 10단계까지 추가할 수 있습니다.")
            return
        pos = self._capture_mouse_position("이동")
        if pos is None:
            return
        step = {"kind": "move", "x": pos[0], "y": pos[1]}
        self.direct_steps.append(step)
        self.direct_list.addItem(step_label(step))

    def _add_mouse_click_step(self) -> None:
        if len(self.direct_steps) >= 10:
            QMessageBox.information(self, "단계 제한", "직접 지정 방식은 최대 10단계까지 추가할 수 있습니다.")
            return
        double = self.mouse_double_check.isChecked()
        pos = self._capture_mouse_position("더블클릭" if double else "클릭")
        if pos is None:
            return
        step = {"kind": "click", "button": self._mouse_button_value(), "double": double, "x": pos[0], "y": pos[1]}
        self.direct_steps.append(step)
        self.direct_list.addItem(step_label(step))

    def _add_mouse_drag_step(self) -> None:
        if len(self.direct_steps) >= 10:
            QMessageBox.information(self, "단계 제한", "직접 지정 방식은 최대 10단계까지 추가할 수 있습니다.")
            return
        start = self._capture_mouse_position("드래그 시작")
        if start is None:
            return
        end = self._capture_mouse_position("드래그 도착")
        if end is None:
            return
        step = {"kind": "drag", "x1": start[0], "y1": start[1], "x2": end[0], "y2": end[1], "button": self._mouse_button_value()}
        self.direct_steps.append(step)
        self.direct_list.addItem(step_label(step))

    def _remove_direct_step(self) -> None:
        row = self.direct_list.currentRow()
        if row < 0:
            return
        self.direct_list.takeItem(row)
        self.direct_steps.pop(row)

    def _clear_direct_steps(self) -> None:
        self.direct_list.clear()
        self.direct_steps.clear()

    def _apply_direct_steps(self) -> None:
        if not self.direct_steps:
            QMessageBox.information(self, "추가된 단계 없음", "먼저 단계를 추가해주세요.")
            return
        self.script_edit.setPlainText(steps_to_script_text(self.direct_steps))
        self.tabs.setCurrentIndex(0)

    # --- 녹화 ---------------------------------------------------------------

    def _build_record_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        hint = QLabel(
            "녹화 시작 후 실제로 누를 키·클릭할 위치를 순서대로 입력하세요. "
            "Ctrl/Alt/Shift는 누르기·떼기가 각각 기록되고, 그 외 키는 누르는 즉시 한 번의 입력(Tap)으로 기록됩니다. "
            "마우스는 클릭 위치가 대상 프로그램 창 기준 좌표로 기록되며(이동 자체는 기록하지 않음), "
            "누른 채로 옮기면 드래그로, 짧은 시간 안에 같은 위치를 두 번 클릭하면 더블클릭으로 인식합니다. "
            "대상 프로그램을 먼저 선택해야 좌표가 올바르게 기록됩니다."
        )
        hint.setObjectName("mutedText")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.record_list = QListWidget()
        style_list_selection(self.record_list, dialog_palette(self))
        layout.addWidget(self.record_list, 1)
        btn_row = QHBoxLayout()
        self.record_start_btn = QPushButton("녹화 시작")
        self.record_stop_btn = QPushButton("녹화 정지")
        self.record_stop_btn.setEnabled(False)
        clear_btn = QPushButton("전체 삭제")
        apply_btn = QPushButton("스크립트에 반영")
        self.record_start_btn.clicked.connect(self._start_record)
        self.record_stop_btn.clicked.connect(self._stop_record)
        clear_btn.clicked.connect(self._clear_record_steps)
        apply_btn.clicked.connect(self._apply_record_steps)
        btn_row.addWidget(self.record_start_btn)
        btn_row.addWidget(self.record_stop_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(clear_btn)
        btn_row.addWidget(apply_btn)
        layout.addLayout(btn_row)
        return page

    def _start_record(self) -> None:
        try:
            from pynput import keyboard, mouse  # noqa: F401  (설치 여부만 확인)
        except Exception as exc:
            QMessageBox.warning(self, "녹화 시작 실패", str(exc))
            return
        if not self.process_exe:
            QMessageBox.warning(self, "대상 프로그램 필요", "녹화된 마우스 좌표를 대상 창 기준으로 저장하려면 먼저 대상 프로그램을 선택해주세요.")
            return
        self.record_steps = []
        self.record_list.clear()
        self.recorder = KeyRecorder(self.process_exe)
        self.recorder.step_captured.connect(self._on_record_step)
        self.recorder.start()
        self.record_start_btn.setEnabled(False)
        self.record_stop_btn.setEnabled(True)

    def _on_record_step(self, step: dict) -> None:
        if step.pop("_merge_last", False) and self.record_steps:
            self.record_steps[-1] = step
            self.record_list.item(self.record_list.count() - 1).setText(step_label(step))
            return
        self.record_steps.append(step)
        self.record_list.addItem(step_label(step))

    def _stop_record(self) -> None:
        if self.recorder:
            self.recorder.stop()
            self.recorder = None
        self.record_start_btn.setEnabled(True)
        self.record_stop_btn.setEnabled(False)

    def _clear_record_steps(self) -> None:
        self.record_steps = []
        self.record_list.clear()

    def _apply_record_steps(self) -> None:
        if not self.record_steps:
            QMessageBox.information(self, "녹화 내용 없음", "먼저 녹화를 진행해주세요.")
            return
        self.script_edit.setPlainText(steps_to_script_text(self.record_steps))
        self.tabs.setCurrentIndex(0)

    # --- 저장/취소 ------------------------------------------------------------

    def closeEvent(self, event) -> None:
        self._stop_record()
        super().closeEvent(event)

    def reject(self) -> None:
        self._stop_record()
        super().reject()

    def _try_accept(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(self, "입력 확인", "이름을 지정해주세요.")
            return
        if not self.process_exe:
            QMessageBox.warning(self, "입력 확인", "대상 프로그램을 선택해주세요.")
            return
        if not self.hotkey.value():
            QMessageBox.warning(self, "입력 확인", "실행 단축키를 지정해주세요.")
            return
        script = self.script_edit.toPlainText()
        if not script.strip():
            QMessageBox.warning(self, "입력 확인", "스크립트를 입력하거나, '직접 지정'/'녹화' 탭에서 '스크립트에 반영'을 눌러주세요.")
            return
        try:
            parse_script(script)
        except MacroScriptError as exc:
            QMessageBox.warning(self, "스크립트 오류", str(exc))
            return
        self._stop_record()
        self.accept()

    def value(self) -> dict:
        return {
            "name": self.name.text().strip(),
            "process_exe": self.process_exe,
            "hotkey": self.hotkey.value(),
            "script": self.script_edit.toPlainText(),
        }


class ProcessHotkeyTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        self._players: list = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText("검색...")
        self.search.setFixedWidth(120)
        self.search.setFixedHeight(26)
        self.search.setStyleSheet("QLineEdit { padding: 1px 6px; font-size: 9pt; }")
        self.search.textChanged.connect(self.refresh)
        self.sort_controls = SortControls(self.refresh)
        # 검색/정렬은 이 탭 자체가 아니라 상위(단축키/매크로) 탭의 코너 위젯으로 올라간다 —
        # HotkeyMacroTab이 이 위젯을 가져다 붙인다.
        self.corner_widget = QWidget()
        corner_layout = QHBoxLayout(self.corner_widget)
        corner_layout.setContentsMargins(0, 0, 4, 0)
        corner_layout.setSpacing(4)
        corner_layout.addWidget(self.search)
        corner_layout.addWidget(self.sort_controls)
        self.list = GridPanel(columns=2)
        layout.addWidget(self.list, 1)
        new_btn = QPushButton("신규")
        new_btn.clicked.connect(self.create_item)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(new_btn)
        layout.addLayout(btn_row)

    def refresh(self) -> None:
        cards = []
        q = self.search.text().strip().lower()
        source_items = self.main.data.get("process_hotkeys", [])
        visible_items = self.sort_controls.sort_items(source_items, lambda value: value.get("name", ""))
        for item in visible_items:
            if q and q not in item.get("name", "").lower() and q not in item.get("process_exe", "").lower():
                continue
            card = make_card(item.get("name", "(이름 없음)"), item.get("process_exe", ""), display_hotkey(item.get("hotkey")), card_size="b")
            add_card_actions(
                card,
                [
                    ("edit", "수정", lambda checked=False, value=item: self.edit_item(value), False),
                    ("play", "테스트 실행", lambda checked=False, value=item: self.test_run(value), False),
                    ("delete", "삭제", lambda checked=False, value=item: self.delete_item(value), True),
                ],
            )
            cards.append(card)
        callback = (lambda old, new: self.reorder_items(source_items, visible_items, old, new)) if self.sort_controls.is_manual() else None
        self.list.add_cards(cards, on_reorder=callback)

    def reorder_items(self, source: list[dict], visible: list[dict], old: int, new: int) -> None:
        apply_manual_reorder(source, visible, old, new)
        self.main.save_data()

    def create_item(self) -> None:
        dialog = ProcessHotkeyDialog({"name": "", "process_exe": "", "hotkey": None, "script": ""})
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        value = dialog.value()
        conflict = self.main.first_hotkey_conflict(candidate=value)
        if conflict:
            QMessageBox.warning(self, "단축키 충돌", conflict)
            return
        if not confirm_shift_digit_hotkey(self, value.get("hotkey")):
            return
        items = self.main.data.setdefault("process_hotkeys", [])
        items.append(
            {
                "id": new_id("ph"),
                "name": value["name"],
                "process_exe": value["process_exe"],
                "hotkey": value["hotkey"],
                "script": value["script"],
                "created_at": now_iso(),
                "sort_order": len(items),
                "usage_count": 0,
            }
        )
        self.main.save_data()
        self.refresh()

    def edit_item(self, item: dict) -> None:
        dialog = ProcessHotkeyDialog(item)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        value = dialog.value()
        conflict = self.main.first_hotkey_conflict(candidate=value, original=item)
        if conflict:
            QMessageBox.warning(dialog, "단축키 충돌", conflict)
            return
        if not confirm_shift_digit_hotkey(dialog, value.get("hotkey")):
            return
        item["name"] = value["name"]
        item["process_exe"] = value["process_exe"]
        item["hotkey"] = value["hotkey"]
        item["script"] = value["script"]
        self.main.save_data()
        self.refresh()

    def delete_item(self, item: dict) -> None:
        if not confirm_delete(self, "선택한 프로그램별 단축키를 삭제할까요?"):
            return
        self.main.data.get("process_hotkeys", []).remove(item)
        self.main.save_data()
        self.refresh()

    def test_run(self, item: dict) -> None:
        from app import win_control

        active = win_control.active_process_name()
        target = str(item.get("process_exe") or "")
        if active.lower() != target.lower():
            QMessageBox.information(
                self,
                "대상 프로그램 아님",
                f"현재 활성 창의 프로그램({active or '알 수 없음'})이 지정한 대상({target})과 다릅니다.\n대상 프로그램을 활성화한 뒤 다시 실행해주세요.",
            )
            return
        self._run_action(item)

    def trigger(self, item: dict) -> None:
        from app import win_control

        active = win_control.active_process_name().lower()
        target = str(item.get("process_exe") or "").lower()
        if not target or active != target:
            return
        self._run_action(item)

    def _run_action(self, item: dict) -> None:
        from ui.tab_macro import MacroPlayerThread

        bump_usage(item)
        self.main.save_usage_data()
        # 전용 단축키는 리본 단축키(Alt→H→M→C)처럼 즉각 반응해야 체감이 좋다.
        # 매크로 기본 시작 지연(1초)은 트리거 키 릴리즈 대기용이라 여기서는 과하다.
        player = MacroPlayerThread({"script": item.get("script", ""), "repeat": 1, "start_delay": 0.15})
        self._players.append(player)
        player.error.connect(lambda err: QMessageBox.warning(self, "프로그램별 단축키 실행 실패", err))
        player.finished.connect(lambda p=player: self._players.remove(p) if p in self._players else None)
        player.finished.connect(player.deleteLater)
        player.start()

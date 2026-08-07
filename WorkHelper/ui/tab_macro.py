from __future__ import annotations

import re
import time
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QFont, QSyntaxHighlighter, QTextCharFormat
from PyQt6.QtWidgets import (
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
    QSpinBox,
    QTabWidget,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.macro_script import MacroScriptError, count_steps, parse_script, record_actions_to_script, resolve_assign_value, substitute_vars, tokenize_send
from app.utils import display_hotkey, new_id, now_iso
from ui.common import GridPanel, HotkeyFields, SortControls, add_card_actions, apply_manual_reorder, bump_usage, confirm_delete, confirm_shift_digit_hotkey, dialog_palette, make_card


MODIFIER_NAMES = {"ctrl", "ctrl_l", "ctrl_r", "alt", "alt_l", "alt_r", "shift", "shift_l", "shift_r"}

MACRO_REF_CATEGORY_ALL = "전체"

# 매크로 스크립트 참조 패널에 표시되는 명령어 · 변수 · 키 목록.
# 각 항목: category(분류) · name(목록에 보일 이름) · signature(사용법) · desc(한글 설명) · example(예시 코드) · note(예시 설명)
MACRO_REFERENCE: list[dict[str, str]] = [
    {"category": "명령어", "name": "Sleep", "signature": "Sleep, ms", "desc": "지정한 밀리초(ms)만큼 실행을 잠시 멈춥니다. 클릭이나 키 입력 사이에 여유 시간을 줄 때 사용합니다.", "example": "Sleep, 1000", "note": "1초(1000ms) 동안 대기"},
    {"category": "명령어", "name": "Click", "signature": "Click [, x, y]", "desc": "마우스 왼쪽 버튼을 클릭합니다. 좌표(x, y)를 생략하면 현재 마우스 위치를 그대로 클릭합니다.", "example": "Click, 500, 300", "note": "화면 좌표 (500, 300) 위치를 클릭"},
    {"category": "명령어", "name": "MouseClick", "signature": "MouseClick, Button [, x, y]", "desc": "지정한 버튼(left/right/middle)으로 클릭합니다. 좌표를 생략하면 현재 마우스 위치를 클릭합니다.", "example": "MouseClick, right, 500, 300", "note": "(500, 300) 위치를 오른쪽 버튼으로 클릭"},
    {"category": "명령어", "name": "MouseMove", "signature": "MouseMove, x, y [, R]", "desc": "마우스 커서를 이동합니다. 맨 끝에 R을 붙이면 절대 좌표가 아니라 현재 마우스 위치를 기준으로 한 상대 이동이 됩니다.", "example": "MouseMove, 80, 0, 0, R", "note": "현재 위치에서 오른쪽으로 80px 이동 (세 번째 값 0은 속도로, 무시됩니다)"},
    {"category": "명령어", "name": "MouseGetPos", "signature": "MouseGetPos, x변수, y변수", "desc": "현재 마우스 좌표를 두 변수에 저장합니다.", "example": "MouseGetPos, mx, my", "note": "mx, my 에 현재 마우스의 x, y 좌표가 저장됨"},
    {"category": "명령어", "name": "Send / SendInput", "signature": "Send, keys", "desc": "키보드 입력을 보냅니다. ^ ! + # 로 Ctrl/Alt/Shift/Win 을 조합하고, {}로 감싸 Enter, Tab 같은 특수 키를 입력합니다. 그 외 문자는 그대로 타이핑됩니다. SendInput 도 동일하게 동작합니다.", "example": "Send, +{Home}^c", "note": "Shift+Home 으로 줄 앞까지 선택한 뒤 Ctrl+C 로 복사"},
    {"category": "명령어", "name": "Run", "signature": "Run, 대상 [, 작업폴더]", "desc": "프로그램을 실행하거나 URL·파일·폴더를 기본 프로그램으로 엽니다. 실행 파일 경로는 큰따옴표로 감싸고, 뒤에 인자를 이어 쓸 수 있습니다.", "example": "Run, \"C:\\Program Files\\Naver\\Naver Whale\\Application\\whale.exe\" \"https://naver.com\"", "note": "Whale 브라우저로 naver.com 을 엶"},
    {"category": "명령어", "name": "IniWrite", "signature": "IniWrite, 값, 파일, 섹션, 키", "desc": "값을 지정한 파일에 저장합니다. 매크로를 다시 실행하거나 다른 매크로에서도 IniRead 로 값을 불러올 수 있습니다.", "example": "IniWrite, %clip%, setting.ini, Settings, clip", "note": "clip 변수 값을 setting.ini 파일의 [Settings] clip 항목에 저장"},
    {"category": "명령어", "name": "IniRead", "signature": "IniRead, 변수명, 파일, 섹션, 키", "desc": "파일에 저장된 값을 읽어와 변수에 저장합니다.", "example": "IniRead, gx, setting.ini, Settings, loc_x", "note": "setting.ini 파일의 [Settings] loc_x 값을 gx 변수에 저장"},
    {"category": "명령어", "name": "KeyWait", "signature": "KeyWait, 키이름 [, U]", "desc": "지정한 키를 누를 때까지(기본) 대기합니다. 뒤에 U 를 붙이면 뗄 때까지 대기합니다.", "example": "KeyWait, f9", "note": "F9 키를 누를 때까지 매크로 실행을 멈춤"},
    {"category": "명령어", "name": "CoordMode", "signature": "CoordMode, Mouse, Screen|Window|Client", "desc": "이후 나오는 Click/MouseMove/MouseGetPos 의 좌표 기준을 바꿉니다. Screen(기본값)은 화면 전체, Window 는 활성 창의 좌상단, Client 는 활성 창의 제목표시줄·테두리를 뺀 내용 영역 좌상단을 기준으로 합니다.", "example": "CoordMode, Mouse, Client\nClick, 55, 280", "note": "활성 창의 내용 영역 기준 (55, 280) 위치를 클릭"},
    {"category": "명령어", "name": "; (주석)", "signature": "; 내용", "desc": "줄 맨 앞에 세미콜론(;)을 붙이면 그 줄은 실행되지 않는 주석이 됩니다. 메모를 남길 때 사용하세요.", "example": "; 여기부터 클립보드 저장 시작", "note": "실행되지 않고 무시됨"},
    {"category": "창 제어", "name": "WinActivate", "signature": "WinActivate [, 제목]", "desc": "제목에 포함된 문자열로 창을 찾아 활성화합니다. 'ahk_exe 파일명.exe' 형식으로 프로세스 이름으로도 찾을 수 있습니다. 제목을 생략하면 바로 앞의 WinExist/if 에서 찾은 창을 활성화합니다.", "example": "WinActivate, ahk_exe notepad.exe", "note": "메모장 창을 찾아 활성화"},
    {"category": "창 제어", "name": "WinWait / WinWaitActive", "signature": "WinWait(Active), 제목 [, 텍스트] [, 초]", "desc": "창이 나타날 때까지(WinWait) 또는 활성화될 때까지(WinWaitActive) 대기합니다. 초를 지정하면 그만큼만 기다리고 넘어갑니다(기본 10초).", "example": "WinWaitActive, 메모장", "note": "제목에 '메모장'이 포함된 창이 활성화될 때까지 대기"},
    {"category": "창 제어", "name": "WinMinimize / WinClose", "signature": "WinMinimize [, 제목] / WinClose [, 제목]", "desc": "창을 최소화하거나 닫습니다.", "example": "WinMinimize, ahk_exe KakaoTalk.exe", "note": "카카오톡 창을 최소화"},
    {"category": "창 제어", "name": "IfWinNotActive / IfWinActive", "signature": "IfWinNotActive, 제목, , WinActivate, 제목", "desc": "창이 비활성(IfWinNotActive) 또는 활성(IfWinActive) 상태일 때만 WinActivate 를 실행하는 한 줄 조건문입니다.", "example": "IfWinNotActive, 엑셀, , WinActivate, 엑셀", "note": "'엑셀' 창이 활성 상태가 아니면 활성화"},
    {"category": "창 제어", "name": "if WinExist(...) { }", "signature": "if WinExist(\"제목\") { ... } / if !WinExist(\"제목\") { ... }", "desc": "창이 존재하면(또는 !를 붙이면 존재하지 않으면) 중괄호 안을 실행합니다. WinExist 대신 WinActive 를 쓰면 '활성 상태인지'로 검사합니다.", "example": "if WinExist(\"카카오톡\") {\n    WinActivate\n}", "note": "카카오톡 창이 있을 때만 활성화"},
    {"category": "제어 흐름", "name": "Loop { }", "signature": "Loop [, 횟수] { ... }", "desc": "중괄호 안을 반복 실행합니다. 횟수를 생략하면 무한 반복이며, 정지 버튼이나 마우스 가운데 버튼으로만 멈춥니다.", "example": "Loop, 3 {\n    Click\n    Sleep, 500\n}", "note": "클릭 후 0.5초 대기를 3번 반복"},
    {"category": "제어 흐름", "name": "if (변수 비교) { }", "signature": "if (변수 == \"값\") { ... } / if (변수 != \"값\") { ... }", "desc": "변수 값이 지정한 문자열과 같은지(==) 다른지(!=) 비교해 중괄호 안을 실행합니다. 빈 문자열(\"\")과 비교하면 '값이 있는지' 검사할 수 있습니다.", "example": "if (saved != \"\") {\n    Clipboard := saved\n}", "note": "saved 변수에 값이 있을 때만 클립보드에 되돌려 씀"},
    {
        "category": "변수",
        "name": "변수 지정 - := (표현식)",
        "signature": "이름 := 값",
        "desc": (
            "변수를 만들고 값을 저장합니다. 우변이 큰따옴표(\"...\")로 감싸여 있으면 그 안의 글자 그대로 저장됩니다(따옴표 자체는 값에 포함되지 않음). "
            "반면 우변에 따옴표가 전혀 없고 그 전체가 다른 변수 이름과 정확히 같으면, %없이도 그 변수의 값을 그대로 참조합니다 — IniRead 로 읽어온 값을 "
            "그대로 옮길 때 특히 자주 씁니다. 그 외의(공백·기호가 섞인) 따옴표 없는 값은 %변수명% 부분만 치환되고 나머지는 글자 그대로 취급됩니다."
        ),
        "example": (
            "IniRead, gx, setting.ini, Settings, loc_x\n"
            "Clipboard := gx        ; \"gx\" 라는 글자가 아니라, gx 변수에 저장된 값을 클립보드에 넣음\n\n"
            "name := \"홍길동\"        ; 따옴표로 감쌌으므로 글자 그대로 홍길동\n"
            "msg := %name%님 안녕하세요   ; msg 에는 \"홍길동님 안녕하세요\""
        ),
        "note": "정리: 값 하나만 있는 우변(따옴표 없음) = 변수 참조 · \"값\" = 글자 그대로 · %이름%이 섞인 문장 = 그 부분만 치환",
    },
    {"category": "변수", "name": "변수 지정 - = (레거시)", "signature": "이름 = 값", "desc": "값을 항상 글자 그대로 저장합니다 (:= 와 달리 우변이 변수 이름과 같아도 절대 참조하지 않음). %변수명% 치환만 적용됩니다. 값 뒤에 공백+세미콜론(' ;')이 오면 그 뒤는 주석으로 잘려나갑니다.", "example": "clipboard =   ;        ; 빈 문자열로 지움 (뒤의 ;가 주석 처리됨)\nclipboard = ybtour tableau12@#", "note": "clipboard 변수에 'ybtour tableau12@#' 문자열이 그대로 저장됨"},
    {"category": "변수", "name": "%변수명%", "signature": "%변수명%", "desc": "Send, IniWrite 등 값이 들어가는 자리에서 변수의 내용으로 치환됩니다. (:= 우변에서 변수 하나만 참조할 땐 %없이도 되지만, 그 외 자리에서는 항상 %로 감싸야 합니다.)", "example": "Send, %clip%", "note": "clip 변수에 저장된 텍스트를 그대로 입력"},
    {"category": "변수", "name": "Clipboard / ClipboardAll", "signature": "Clipboard / Clipboard := 값", "desc": "클립보드(복사한 내용)를 나타내는 특수 변수입니다. 우변에 그대로 쓰면(따옴표 없이) 클립보드 값을 읽고, 좌변에 쓰면 클립보드에 값을 저장합니다. ClipboardAll 도 동일하게 취급됩니다(이미지 등 서식 없이 텍스트만 다룸).", "example": "clip := Clipboard\nClipboard := %clip%", "note": "현재 클립보드 값을 clip에 저장한 뒤, 다시 클립보드에 그대로 되돌려 씀"},
    {"category": "한정자", "name": "^ (Ctrl)", "signature": "^키", "desc": "Send 안에서 바로 다음 키에 Ctrl 을 조합합니다.", "example": "Send, ^c", "note": "Ctrl+C (복사)"},
    {"category": "한정자", "name": "! (Alt)", "signature": "!키", "desc": "Send 안에서 바로 다음 키에 Alt 를 조합합니다.", "example": "Send, !{F4}", "note": "Alt+F4 (활성 창 닫기)"},
    {"category": "한정자", "name": "+ (Shift)", "signature": "+키", "desc": "Send 안에서 바로 다음 키에 Shift 를 조합합니다.", "example": "Send, +{Home}", "note": "Shift+Home (커서부터 줄 앞까지 선택)"},
    {"category": "한정자", "name": "# (Win)", "signature": "#키", "desc": "Send 안에서 바로 다음 키에 Win 키를 조합합니다.", "example": "Send, #d", "note": "Win+D (바탕화면 보기)"},
    {
        "category": "특수 키",
        "name": "단축키 설정 가능 리스트",
        "signature": "Send 안에서 {키이름} 형태로 사용",
        "desc": (
            "Send 명령에서 { } 로 감싸서 쓸 수 있는 모든 키 이름 목록입니다. 뒤에 숫자를 붙이면 그만큼 반복해서 누릅니다"
            "(예: {Down 3} = 아래 방향키 3번). {CtrlDown}/{CtrlUp} 계열은 키를 누른 채로 유지/해제하며, 매크로가 끝나면 "
            "혹시 남아있어도 자동으로 떼어집니다. 마지막 줄은 ^ ! + # % { } 문자를 조합 기호가 아니라 글자 그대로 입력하고 싶을 때 씁니다."
        ),
        "example": (
            "이동/편집   {Enter} {Tab} {Esc} {Space} {Backspace} {Delete} {Insert}\n"
            "            {Home} {End} {Up} {Down} {Left} {Right} {PgUp} {PgDn}\n"
            "기능키      {F1} ~ {F24}\n"
            "잠금/기타   {CapsLock} {NumLock} {ScrollLock} {PrintScreen} {Pause} {AppsKey} {LWin} {RWin}\n"
            "누른 채 유지 {CtrlDown} {CtrlUp} {AltDown} {AltUp} {ShiftDown} {ShiftUp}\n"
            "그대로 입력 {^} {!} {+} {#} {%} {{} {}}"
        ),
        "note": "예: Send, hello{Enter}  ·  Send, {Down 3}  ·  Send, {CtrlDown}v{CtrlUp}  ·  Send, 50{%} 할인",
    },
    {
        "category": "지원하지 않음",
        "name": "산술식 (+, -, * 등 계산)",
        "signature": "vx+1  같은 계산식",
        "desc": (
            "값이 다른 변수 하나만 정확히 가리키면 참조되지만(위 '변수 지정 - :=' 참고), 거기에 연산 기호가 섞이면 "
            "계산하지 않고 그 글자를 그대로 취급합니다. MouseGetPos 로 좌표를 얻어 1픽셀만 움직이는 자리비움 방지 패턴은 "
            "MouseMove 의 R(상대 이동) 옵션으로 대신할 수 있습니다."
        ),
        "example": (
            "MouseGetPos, vx, vy\n"
            "MouseMove, vx+1, vy+1   ; 오류 — 'vx+1' 은 숫자가 아니라서 실행 중 실패\n\n"
            "; 대신 이렇게 (MouseGetPos 자체가 필요 없음)\n"
            "MouseMove, 1, 0, R      ; 현재 위치에서 오른쪽으로 1px 이동"
        ),
        "note": "",
    },
    {
        "category": "지원하지 않음",
        "name": "문자열 함수 (SubStr, InStr 등)",
        "signature": "SubStr(...), InStr(...), StrLen(...)",
        "desc": "함수를 호출하는 문법은 지원하지 않습니다. 오류가 나지는 않지만, 계산되지 않고 그 글자(함수 호출 문구 자체)가 그대로 변수에 저장됩니다.",
        "example": "c1 := SubStr(Clipboard, -6, 1)   ; c1 에는 잘라낸 글자가 아니라\n                                  ; 'SubStr(Clipboard, -6, 1)' 이라는 문자열 그대로 저장됨",
        "note": "문자열을 가공해야 한다면, 가공된 값을 미리 IniWrite 로 저장해두고 IniRead 로 불러오는 방식을 권장합니다",
    },
    {
        "category": "지원하지 않음",
        "name": "문자열 연결 ( . 연산자)",
        "signature": '"a" . "b"',
        "desc": '점(.)으로 여러 문자열을 이어붙이는 연결 연산자는 지원하지 않습니다. 따옴표가 두 쌍 이상이면(문자열이 여러 개면) 통째로 원문 그대로 저장됩니다.',
        "example": 'x := "a" . "b"   ; x 에는 ab 가 아니라 \'"a" . "b"\' 문자열 그대로 저장됨',
        "note": "",
    },
    {
        "category": "지원하지 않음",
        "name": "else 블록",
        "signature": "if (...) { ... } else { ... }",
        "desc": "if 블록(및 if WinExist)은 지원하지만 else 는 지원하지 않습니다. else 줄에서 파싱 오류가 납니다.",
        "example": 'if (x == "1") {\n    Click\n} else {          ; 파싱 오류\n    Click, 10, 10\n}',
        "note": "반대 조건의 if 를 하나 더 쓰세요 — 예: if (x != \"1\") { Click, 10, 10 }",
    },
    {
        "category": "지원하지 않음",
        "name": "SplashImage / Gui / MsgBox",
        "signature": "SplashImage, ... / MsgBox, ... / Gui, ...",
        "desc": "이미지·메시지 상자·커스텀 창 같은 화면 팝업 표시는 지원하지 않습니다. 매크로는 화면에 직접 창을 띄울 수 없는 백그라운드 스레드에서 실행됩니다.",
        "example": "SplashImage, hint.png, x0 y30   ; 알 수 없는 명령어 오류\nMsgBox, 완료되었습니다             ; 알 수 없는 명령어 오류",
        "note": "",
    },
    {
        "category": "지원하지 않음",
        "name": "ExitApp / Reload / WinGetPos",
        "signature": "ExitApp / Reload / WinGetPos, x, y",
        "desc": "오토핫키 스크립트 자체의 종료·재시작·창 위치 저장 명령입니다. 이 앱은 매크로 하나당 스크립트 하나이고 트레이 메뉴로 앱을 직접 관리하므로 필요하지 않습니다.",
        "example": "ExitApp   ; 알 수 없는 명령어 오류",
        "note": "",
    },
    {
        "category": "지원하지 않음",
        "name": "핫스트링 (::트리거::)",
        "signature": "::트리거::내용",
        "desc": "자동 치환 문구는 매크로가 아니라 앱의 '핫스트링' 메뉴에서 이미 지원합니다. 매크로 스크립트 안에 넣으면 파싱 오류가 납니다.",
        "example": "::gr.::안녕하세요~   ; 알 수 없는 명령어 오류 — 핫스트링 메뉴에 등록하세요",
        "note": "",
    },
]


class MacroReferenceDialog(QDialog):
    """매크로 스크립트에서 쓸 수 있는 명령어 · 변수 · 키를 찾아보는 참조 패널."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("매크로 명령어 · 키 참조")
        self.setModal(False)
        self.resize(680, 460)

        layout = QHBoxLayout(self)

        left = QVBoxLayout()
        left.setSpacing(6)
        self.category = QComboBox()
        self.category.addItem(MACRO_REF_CATEGORY_ALL)
        for category in dict.fromkeys(item["category"] for item in MACRO_REFERENCE):
            self.category.addItem(category)
        self.category.currentTextChanged.connect(self._apply_filter)
        self.search = QLineEdit()
        self.search.setPlaceholderText("검색...")
        self.search.textChanged.connect(self._apply_filter)
        self.list = QListWidget()
        self.list.currentItemChanged.connect(self._show_detail)
        left.addWidget(self.category)
        left.addWidget(self.search)
        left.addWidget(self.list, 1)
        left_widget = QWidget()
        left_widget.setLayout(left)
        left_widget.setFixedWidth(210)

        self.detail = QTextBrowser()
        self.detail.setOpenExternalLinks(False)

        layout.addWidget(left_widget)
        layout.addWidget(self.detail, 1)

        self._apply_filter()

    def _apply_filter(self) -> None:
        category = self.category.currentText()
        query = self.search.text().strip().lower()
        self.list.clear()
        for item in MACRO_REFERENCE:
            if category != MACRO_REF_CATEGORY_ALL and item["category"] != category:
                continue
            if query and query not in item["name"].lower() and query not in item["desc"].lower():
                continue
            list_item = QListWidgetItem(item["name"])
            list_item.setData(Qt.ItemDataRole.UserRole, item)
            self.list.addItem(list_item)
        if self.list.count():
            self.list.setCurrentRow(0)
        else:
            self.detail.clear()

    def _show_detail(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            self.detail.clear()
            return
        item = current.data(Qt.ItemDataRole.UserRole)
        example_html = item["example"].replace("\n", "<br>")
        note_html = f"<p style='color:#888;'>{item['note']}</p>" if item.get("note") else ""
        self.detail.setHtml(
            f"<h3>{item['name']} <span style='font-weight:normal;'>({item['signature']})</span></h3>"
            f"<p>{item['desc']}</p>"
            f"<pre style='background:rgba(127,127,127,0.15); padding:8px 10px; border-radius:6px;'>{example_html}</pre>"
            f"{note_html}"
        )


class MacroPlayerThread(QThread):
    error = pyqtSignal(str)
    completed = pyqtSignal(bool)  # True = 정상 완료, False = 중간 중지

    def __init__(self, macro: dict) -> None:
        super().__init__()
        self.macro = macro
        self._stop_flag = False
        self._variables: dict[str, str] = {}

    def stop(self) -> None:
        self._stop_flag = True

    def _sleep(self, seconds: float) -> bool:
        """지정 시간만큼 0.1초 단위로 나눠 대기한다. True면 중지 요청이 감지된 것."""
        elapsed = 0.0
        while elapsed < seconds:
            if self._stop_flag:
                return True
            chunk = min(0.1, seconds - elapsed)
            time.sleep(chunk)
            elapsed += chunk
        return self._stop_flag

    @staticmethod
    def _ini_path(file_name: str) -> Path:
        from app import config

        safe_name = Path(file_name).name or "macro.ini"
        return config.MACRO_INI_DIR / safe_name

    @staticmethod
    def _ini_write(path: Path, section: str, key: str, value: str) -> None:
        import configparser

        # interpolation=None 필수: 기본 BasicInterpolation 은 값에 '%'가 하나라도 있으면
        # (클립보드 텍스트에는 흔함) InterpolationSyntaxError 를 던진다. 우리 값은 항상
        # 원문 그대로 저장/조회해야 하므로 보간 기능 자체를 끈다.
        parser = configparser.ConfigParser(interpolation=None)
        parser.optionxform = str
        if path.exists():
            parser.read(path, encoding="utf-8")
        if not parser.has_section(section):
            parser.add_section(section)
        parser.set(section, key, value)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            parser.write(f)

    @staticmethod
    def _ini_read(path: Path, section: str, key: str) -> str:
        import configparser

        parser = configparser.ConfigParser(interpolation=None)
        parser.optionxform = str
        if not path.exists():
            return ""
        parser.read(path, encoding="utf-8")
        return parser.get(section, key, fallback="")

    def run(self) -> None:
        try:
            try:
                steps = parse_script(self.macro.get("script", ""))
            except MacroScriptError as exc:
                self.error.emit(str(exc))
                return

            import os
            import subprocess

            import pyautogui
            import pyperclip
            from pynput import keyboard as pynput_keyboard
            from pynput import mouse as pynput_mouse

            from app import key_send, win_control
            from app.macro_script import run_target_is_executable

            def on_middle_click(x, y, button, pressed):
                if pressed and str(button).lower().endswith("middle"):
                    self._stop_flag = True
                    return False

            listener = pynput_mouse.Listener(on_click=on_middle_click)
            listener.start()

            held_keys: list[str] = []
            last_hwnd: list[int | None] = [None]  # 리스트로 감싸 클로저에서 값 변경

            def get_clipboard() -> str:
                try:
                    return pyperclip.paste()
                except Exception:
                    return ""

            def set_clipboard(value: str) -> None:
                try:
                    pyperclip.copy(value)
                except Exception:
                    pass

            def resolve(text: str) -> str:
                return substitute_vars(text, self._variables, get_clipboard)

            def find_window(title: str | None) -> int | None:
                if title:
                    return win_control.find_window(resolve(title))
                return last_hwnd[0]

            mouse_coord_mode = ["screen"]  # CoordMode, Mouse, Screen|Window|Client

            def coord_origin() -> tuple[int, int] | None:
                mode = mouse_coord_mode[0]
                if mode == "screen":
                    return None
                hwnd = win_control.active_window()
                return win_control.client_origin(hwnd) if mode == "client" else win_control.window_origin(hwnd)

            def to_screen_point(x: int, y: int) -> tuple[int, int]:
                origin = coord_origin()
                return (x + origin[0], y + origin[1]) if origin else (x, y)

            def from_screen_point(x: int, y: int) -> tuple[int, int]:
                origin = coord_origin()
                return (x - origin[0], y - origin[1]) if origin else (x, y)

            def run_send(text: str) -> None:
                for kind, value in tokenize_send(resolve(text)):
                    if kind == "text":
                        pyautogui.typewrite(value, interval=0.02)
                    elif kind == "keys":
                        *modifiers, final_key = value
                        # pyautogui.hotkey() 는 옛 API(keybd_event)를 쓰고 Home/End/방향키 등에
                        # KEYEVENTF_EXTENDEDKEY 도 설정하지 않아, NumLock 상태에 따라 Shift+Home
                        # 같은 조합이 선택 없이 커서만 이동시키는 문제가 있었다(Ctrl+C 해도 빈
                        # 클립보드). key_send 는 SendInput 하나로 모디파이어까지 일관되게 보낸다.
                        if not key_send.send_hotkey(modifiers, final_key):
                            pyautogui.hotkey(*value)
                    elif kind == "keydown":
                        if not key_send.press_down(value):
                            pyautogui.keyDown(value)
                        if value not in held_keys:
                            held_keys.append(value)
                    elif kind == "keyup":
                        if not key_send.press_up(value):
                            pyautogui.keyUp(value)
                        if value in held_keys:
                            held_keys.remove(value)

            def run_target(raw_target: str, working_dir: str | None) -> None:
                target = resolve(raw_target)
                try:
                    if run_target_is_executable(target):
                        subprocess.Popen(target, cwd=working_dir or None, shell=False)
                    else:
                        os.startfile(target)
                except Exception:
                    pass  # 실행 대상이 없거나 열 수 없어도 매크로 자체는 계속 진행

            def keywait(key_name: str, wait_for: str) -> bool:
                """지정 키가 눌리거나(기본)/떼어질 때까지 대기한다. True면 중지된 것."""
                target = key_name.strip().lower()
                done = {"flag": False}

                def key_name_of(key) -> str:
                    try:
                        char = key.char
                        return char.lower() if char else ""
                    except AttributeError:
                        return str(key).replace("Key.", "").lower()

                def on_event(key):
                    if key_name_of(key) == target:
                        done["flag"] = True
                        return False

                kw_listener = pynput_keyboard.Listener(
                    on_press=on_event if wait_for == "press" else None,
                    on_release=on_event if wait_for == "release" else None,
                )
                kw_listener.start()
                stopped = False
                while not done["flag"]:
                    if self._stop_flag:
                        stopped = True
                        break
                    time.sleep(0.05)
                try:
                    kw_listener.stop()
                except Exception:
                    pass
                return stopped

            def run_steps(step_list: list) -> bool:
                """스텝 목록을 순서대로 실행한다. True 를 돌려주면 중지 요청이 감지된 것."""
                for step in step_list:
                    if self._stop_flag:
                        return True
                    if execute_step(step):
                        return True
                return False

            def execute_step(step) -> bool:
                params = step.params
                if step.type == "sleep":
                    return self._sleep(params["ms"] / 1000)
                if step.type == "click":
                    x, y = params["x"], params["y"]
                    button = params.get("button", "left")
                    if x is None or y is None:
                        pyautogui.click(button=button)
                    else:
                        sx, sy = to_screen_point(x, y)
                        pyautogui.click(sx, sy, button=button)
                    return False
                if step.type == "mousemove":
                    x, y = params["x"], params["y"]
                    if params["relative"]:
                        pyautogui.moveRel(x, y)
                    else:
                        sx, sy = to_screen_point(x, y)
                        pyautogui.moveTo(sx, sy)
                    return False
                if step.type == "mousegetpos":
                    x, y = pyautogui.position()
                    x, y = from_screen_point(x, y)
                    self._variables[params["x_var"].lower()] = str(x)
                    self._variables[params["y_var"].lower()] = str(y)
                    return False
                if step.type == "coordmode":
                    mouse_coord_mode[0] = params["mode"]
                    return False
                if step.type == "send":
                    run_send(params["text"])
                    return False
                if step.type == "run":
                    run_target(params["target"], params.get("working_dir"))
                    return False
                if step.type == "assign":
                    name = params["name"]
                    value = resolve_assign_value(params, self._variables, get_clipboard)
                    if name.lower() == "clipboard":
                        set_clipboard(value)
                    else:
                        self._variables[name.lower()] = value
                    return False
                if step.type == "iniwrite":
                    path = self._ini_path(resolve(params["file"]))
                    self._ini_write(path, params["section"], params["key"], resolve(params["value"]))
                    return False
                if step.type == "iniread":
                    path = self._ini_path(resolve(params["file"]))
                    value = self._ini_read(path, params["section"], params["key"])
                    self._variables[params["name"].lower()] = value
                    return False
                if step.type == "winactivate":
                    hwnd = find_window(params["title"])
                    if hwnd:
                        win_control.activate_window(hwnd)
                        last_hwnd[0] = hwnd
                    return False
                if step.type == "winminimize":
                    hwnd = find_window(params["title"])
                    win_control.minimize_window(hwnd)
                    return False
                if step.type == "winclose":
                    hwnd = find_window(params["title"])
                    win_control.close_window(hwnd)
                    return False
                if step.type in ("winwait", "winwaitactive"):
                    timeout = params.get("timeout") or 10.0
                    deadline = time.monotonic() + timeout
                    while time.monotonic() < deadline:
                        if self._stop_flag:
                            return True
                        hwnd = win_control.find_window(resolve(params["title"]))
                        if hwnd and (step.type == "winwait" or win_control.is_window_active(hwnd)):
                            last_hwnd[0] = hwnd
                            return False
                        if self._sleep(0.1):
                            return True
                    return False  # 시간 초과 — 오토핫키처럼 매크로를 중단시키지 않고 계속 진행
                if step.type == "ifwin_command":
                    hwnd = win_control.find_window(resolve(params["title"]))
                    is_active = hwnd is not None and win_control.is_window_active(hwnd)
                    should_run = (not is_active) if params["mode"] == "not_active" else is_active
                    if should_run:
                        target_hwnd = win_control.find_window(resolve(params["action_title"]))
                        if target_hwnd:
                            win_control.activate_window(target_hwnd)
                            last_hwnd[0] = target_hwnd
                    return False
                if step.type == "if_win":
                    hwnd = win_control.find_window(resolve(params["title"]))
                    found = hwnd is not None
                    if found and params["mode"] == "active":
                        found = win_control.is_window_active(hwnd)
                    if found:
                        last_hwnd[0] = hwnd
                    condition = (not found) if params["negate"] else found
                    return run_steps(params["body"]) if condition else False
                if step.type == "if_var":
                    current = self._variables.get(params["name"].lower(), "")
                    equal = current == params["value"]
                    condition = (not equal) if params["negate"] else equal
                    return run_steps(params["body"]) if condition else False
                if step.type == "loop":
                    count = params["count"]
                    if count is None:
                        while True:
                            if self._stop_flag or run_steps(params["body"]):
                                return True
                    for _ in range(count):
                        if self._stop_flag or run_steps(params["body"]):
                            return True
                    return False
                if step.type == "keywait":
                    return keywait(params["key"], params["wait_for"])
                return False

            repeat = max(1, int(self.macro.get("repeat", 1)))
            time.sleep(1.0)
            stopped = False
            for _ in range(repeat):
                if self._stop_flag or run_steps(steps):
                    stopped = True
                    break

            for key in held_keys:
                try:
                    if not key_send.press_up(key):
                        pyautogui.keyUp(key)
                except Exception:
                    pass

            try:
                listener.stop()
            except Exception:
                pass

            self.completed.emit(not stopped)
        except Exception as exc:
            self.error.emit(str(exc))


_COMMAND_PATTERN = re.compile(
    r"^\s*(Sleep|Click|MouseClick|MouseMove|MouseGetPos|Send(?:Input|Play|Event)?|IniWrite|IniRead|Run|"
    r"WinActivate|WinWait(?:Active)?|WinMinimize|WinClose|IfWinNotActive|IfWinActive|if|Loop|KeyWait|"
    r"CoordMode|SetWinDelay|SetKeyDelay|SetControlDelay|SetMouseDelay|SendMode|ClipWait|Return)\b",
    re.IGNORECASE,
)
_NUMBER_PATTERN = re.compile(r"(?<![%\w])\d+(?:\.\d+)?\b")
_VAR_PATTERN = re.compile(r"%[A-Za-z_]\w*%")
_BRACE_PATTERN = re.compile(r"\{[^{}]*\}")
_ASSIGN_PATTERN = re.compile(r"^\s*[A-Za-z_]\w*\s*(:=)")


class MacroScriptHighlighter(QSyntaxHighlighter):
    """AHK 스타일 매크로 스크립트용 경량 구문 강조기."""

    def __init__(self, document, dark: bool) -> None:
        super().__init__(document)
        self._build_formats(dark)

    def _build_formats(self, dark: bool) -> None:
        from ui.code_syntax import code_colors

        colors = code_colors(dark)
        self._comment_format = self._format(colors["comment"], italic=True)
        self._keyword_format = self._format(colors["keyword"], bold=True)
        self._string_format = self._format(colors["string"])
        self._number_format = self._format(colors["number"])
        self._var_format = self._format(colors["function"])
        self._assign_format = self._format(colors["type"], bold=True)

    @staticmethod
    def _format(color: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        if bold:
            fmt.setFontWeight(QFont.Weight.Bold)
        if italic:
            fmt.setFontItalic(True)
        return fmt

    def set_dark(self, dark: bool) -> None:
        self._build_formats(dark)
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:  # noqa: N802 (Qt 시그니처)
        if text.strip().startswith(";"):
            self.setFormat(0, len(text), self._comment_format)
            return
        assign_match = _ASSIGN_PATTERN.match(text)
        if assign_match:
            self.setFormat(assign_match.start(1), len(":="), self._assign_format)
        else:
            command_match = _COMMAND_PATTERN.match(text)
            if command_match:
                self.setFormat(command_match.start(1), len(command_match.group(1)), self._keyword_format)
        for pattern, fmt in (
            (_BRACE_PATTERN, self._string_format),
            (_VAR_PATTERN, self._var_format),
            (_NUMBER_PATTERN, self._number_format),
        ):
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), fmt)


class MacroActionsDialog(QDialog):
    def __init__(self, macro: dict) -> None:
        super().__init__()
        self.macro = macro
        self.setWindowTitle(f"매크로 편집 - {macro.get('name') or '새 매크로'}")
        self.setMinimumWidth(640)
        self.resize(720, 560)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(macro.get("name", ""))
        self.hotkey = HotkeyFields(macro.get("hotkey"))
        self.repeat = QSpinBox()
        self.repeat.setRange(1, 999)
        self.repeat.setValue(macro.get("repeat", 1))
        repeat_row = QHBoxLayout()
        repeat_row.setContentsMargins(0, 0, 0, 0)
        repeat_row.addWidget(self.repeat)
        repeat_row.addWidget(QLabel("회"))
        repeat_row.addStretch(1)
        form.addRow("이름", self.name)
        form.addRow("실행 단축키", self.hotkey)
        form.addRow("반복 횟수", repeat_row)
        layout.addLayout(form)

        from ui.code_syntax import apply_code_editor_style, is_dark_background

        self.editor = QTextEdit()
        self.editor.setAcceptRichText(False)
        self.editor.setPlainText(macro.get("script", ""))
        self.editor.setPlaceholderText("Sleep, 100\nClick, 500, 300\nSend, hello{Enter}")
        colors = dialog_palette(self)
        dark = is_dark_background(colors["field"])
        apply_code_editor_style(self.editor, dark, colors["border"])
        self.editor.setMinimumHeight(260)
        self.highlighter = MacroScriptHighlighter(self.editor.document(), dark)
        layout.addWidget(self.editor, 1)

        toolbar = QHBoxLayout()
        self.insert_coord_btn = QPushButton("좌표 삽입 (3초 후 현재 마우스 위치)")
        self.insert_coord_btn.clicked.connect(self.insert_current_coords)
        insert_coord_btn = self.insert_coord_btn
        help_btn = QPushButton("명령어 도움말")
        help_btn.clicked.connect(self.show_help)
        toolbar.addWidget(insert_coord_btn)
        toolbar.addWidget(help_btn)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        hint = QLabel(
            "Sleep · Click/MouseClick/MouseMove/MouseGetPos · Send(^Ctrl !Alt +Shift {Enter}...) · "
            "변수(:= / Clipboard) · IniWrite/IniRead · Run · WinActivate/WinWait 등 창 제어 · Loop/if { } — "
            "자세한 목록은 '명령어 도움말' 참고"
        )
        hint.setObjectName("mutedText")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("저장")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
        buttons.accepted.connect(self._try_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def insert_current_coords(self) -> None:
        self._countdown = 3
        self.insert_coord_btn.setEnabled(False)
        self.insert_coord_btn.setText(f"{self._countdown}초 후 캡처... (대상 위로 마우스를 옮기세요)")
        self._countdown_timer = QTimer(self)
        self._countdown_timer.timeout.connect(self._tick_countdown)
        self._countdown_timer.start(1000)

    def _tick_countdown(self) -> None:
        self._countdown -= 1
        if self._countdown <= 0:
            self._countdown_timer.stop()
            self._capture_coords()
            self.insert_coord_btn.setEnabled(True)
            self.insert_coord_btn.setText("좌표 삽입 (3초 후 현재 마우스 위치)")
        else:
            self.insert_coord_btn.setText(f"{self._countdown}초 후 캡처... (대상 위로 마우스를 옮기세요)")

    def _capture_coords(self) -> None:
        pos = QCursor.pos()
        cursor = self.editor.textCursor()
        cursor.insertText(f"MouseMove, {pos.x()}, {pos.y()}\nClick\n")

    def show_help(self) -> None:
        if getattr(self, "_reference_dialog", None) is None:
            self._reference_dialog = MacroReferenceDialog(self)
        self._reference_dialog.show()
        self._reference_dialog.raise_()
        self._reference_dialog.activateWindow()

    def _try_accept(self) -> None:
        try:
            parse_script(self.editor.toPlainText())
        except MacroScriptError as exc:
            QMessageBox.warning(self, "스크립트 오류", str(exc))
            return
        self.accept()

    def value(self) -> dict:
        return {
            "name": self.name.text().strip(),
            "hotkey": self.hotkey.value(),
            "repeat": self.repeat.value(),
            "script": self.editor.toPlainText(),
        }


class MacroRecordDialog(QDialog):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("매크로 녹화")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit()
        self.hotkey = HotkeyFields()
        form.addRow("이름", self.name)
        form.addRow("실행 단축키", self.hotkey)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("확인")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def value(self) -> dict:
        return {"name": self.name.text().strip(), "hotkey": self.hotkey.value()}


class MacroTab(QWidget):
    stop_recording_requested = pyqtSignal()

    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        self.recording = False
        self.recorded_actions: list[dict] = []
        self.record_hotkey = None
        self.mouse_listener = None
        self.keyboard_listener = None
        self.record_name = ""
        self.last_event_at = 0.0
        self.pressed_modifiers: set[str] = set()
        self.pressed_keys: set[str] = set()
        self.stop_recording_requested.connect(self.stop_recording)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText("검색...")
        self.search.setFixedWidth(120)
        self.search.setFixedHeight(26)
        self.search.setStyleSheet("QLineEdit { padding: 1px 6px; font-size: 9pt; }")
        self.search.textChanged.connect(self.refresh)
        self.sort_controls = SortControls(self.refresh)
        corner = QWidget()
        corner_layout = QHBoxLayout(corner)
        corner_layout.setContentsMargins(0, 0, 4, 0)
        corner_layout.setSpacing(4)
        corner_layout.addWidget(self.search)
        corner_layout.addWidget(self.sort_controls)
        self.tabs = QTabWidget()
        self.tabs.setCornerWidget(corner, Qt.Corner.TopRightCorner)
        self.list = GridPanel(columns=2)
        new_btn = QPushButton("신규")
        record_btn = QPushButton("녹화")
        stop_btn = QPushButton("정지")
        new_btn.clicked.connect(self.create_macro)
        record_btn.clicked.connect(self.start_recording)
        stop_btn.clicked.connect(self.stop_recording)
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(self.list, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(new_btn)
        row.addWidget(record_btn)
        row.addWidget(stop_btn)
        page_layout.addLayout(row)
        self.tabs.addTab(page, "매크로")
        layout.addWidget(self.tabs, 1)

    def refresh(self) -> None:
        cards = []
        q = self.search.text().strip().lower()
        source_items = self.main.data.get("macros", [])
        visible_items = self.sort_controls.sort_items(source_items, lambda value: value.get("name", ""))
        for macro in visible_items:
            if q and q not in macro.get("name", "").lower():
                continue
            repeat = macro.get("repeat", 1)
            repeat_label = f" · {repeat}회 반복" if repeat > 1 else ""
            card = make_card(macro.get("name", "(이름 없음)"), f"{count_steps(macro.get('script', ''))}줄{repeat_label}", display_hotkey(macro.get("hotkey")), card_size="b")
            add_card_actions(
                card,
                [
                    ("edit", "이력 보기/수정", lambda checked=False, value=macro: self.edit_actions(value), False),
                    ("play", "재생", lambda checked=False, value=macro: self.play_macro(value), False),
                    ("delete", "삭제", lambda checked=False, value=macro: self.delete_macro(value), True),
                ],
            )
            cards.append(card)
        callback = (lambda old, new: self.reorder_items(source_items, visible_items, old, new)) if self.sort_controls.is_manual() else None
        self.list.add_cards(cards, on_reorder=callback)

    def reorder_items(self, source: list[dict], visible: list[dict], old: int, new: int) -> None:
        apply_manual_reorder(source, visible, old, new)
        self.main.save_data()

    def create_macro(self) -> None:
        dialog = MacroActionsDialog({"name": "", "hotkey": None, "repeat": 1, "script": ""})
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        value = dialog.value()
        if not value["name"]:
            QMessageBox.warning(self, "입력 확인", "이름을 지정해주세요.")
            return
        conflict = self.main.first_hotkey_conflict(candidate=value)
        if conflict:
            QMessageBox.warning(self, "단축키 충돌", conflict)
            return
        if not confirm_shift_digit_hotkey(self, value.get("hotkey")):
            return
        items = self.main.data.setdefault("macros", [])
        items.append(
            {
                "id": new_id("mc"),
                "name": value["name"],
                "hotkey": value["hotkey"],
                "repeat": value["repeat"],
                "script": value["script"],
                "created_at": now_iso(),
                "sort_order": len(items),
                "usage_count": 0,
            }
        )
        self.main.save_data()

    def edit_actions(self, macro: dict) -> None:
        dialog = MacroActionsDialog(macro)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        value = dialog.value()
        if not value["name"]:
            QMessageBox.warning(dialog, "입력 확인", "이름을 지정해주세요.")
            return
        conflict = self.main.first_hotkey_conflict(candidate=value, original=macro)
        if conflict:
            QMessageBox.warning(dialog, "단축키 충돌", conflict)
            return
        if not confirm_shift_digit_hotkey(dialog, value.get("hotkey")):
            return
        macro["name"] = value["name"]
        macro["hotkey"] = value["hotkey"]
        macro["repeat"] = value["repeat"]
        macro["script"] = value["script"]
        self.main.save_data()

    def start_recording(self) -> None:
        if self.recording:
            return
        dialog = MacroRecordDialog()
        while dialog.exec() == dialog.DialogCode.Accepted:
            value = dialog.value()
            if not value["name"]:
                QMessageBox.warning(dialog, "입력 확인", "이름을 지정해주세요.")
                continue
            candidate = {"name": value["name"], "hotkey": value["hotkey"]}
            conflict = self.main.first_hotkey_conflict(candidate=candidate)
            if conflict:
                QMessageBox.warning(dialog, "단축키 충돌", conflict)
                continue
            if not confirm_shift_digit_hotkey(dialog, value.get("hotkey")):
                continue
            break
        else:
            return
        try:
            from pynput import keyboard as pynput_keyboard
            from pynput import mouse as pynput_mouse
        except Exception as exc:
            QMessageBox.warning(self, "녹화 시작 실패", str(exc))
            return
        self.recording = True
        self.record_name = value["name"]
        self.record_hotkey = value["hotkey"]
        self.recorded_actions = []
        self.pressed_modifiers = set()
        self.pressed_keys = set()
        self.last_event_at = time.monotonic()
        self.mouse_listener = pynput_mouse.Listener(on_click=self._record_click)
        self.keyboard_listener = pynput_keyboard.Listener(on_press=self._record_key, on_release=self._release_key)
        self.mouse_listener.start()
        self.keyboard_listener.start()
        QMessageBox.information(self, "녹화 시작", "매크로 녹화를 시작했습니다. 정지 버튼 또는 마우스 가운데 버튼으로 종료할 수 있습니다.")

    def stop_recording(self) -> None:
        if not self.recording:
            return
        self.recording = False
        for listener in [self.mouse_listener, self.keyboard_listener]:
            if listener:
                try:
                    listener.stop()
                except Exception:
                    pass
        self.mouse_listener = None
        self.keyboard_listener = None
        script = record_actions_to_script(self.recorded_actions)
        items = self.main.data.setdefault("macros", [])
        items.append(
            {
                "id": new_id("mc"),
                "name": self.record_name,
                "hotkey": self.record_hotkey,
                "script": script,
                "created_at": now_iso(),
                "sort_order": len(items),
                "usage_count": 0,
            }
        )
        self.main.save_data()
        QMessageBox.information(self, "녹화 완료", f"{count_steps(script)}줄의 스크립트를 저장했습니다.")

    def _delay(self) -> float:
        now = time.monotonic()
        delay = max(0.0, now - self.last_event_at)
        self.last_event_at = now
        return round(delay, 3)

    def _record_click(self, x, y, button, pressed) -> None:
        if not self.recording or not pressed:
            return
        if str(button).lower().endswith("middle"):
            self.stop_recording_requested.emit()
            return
        self.recorded_actions.append({"type": "click", "x": int(x), "y": int(y), "delay": self._delay()})

    def _record_key(self, key) -> None:
        if not self.recording:
            return
        name = self._key_name(key)
        if not name:
            return
        if name in MODIFIER_NAMES:
            self.pressed_modifiers.add(self._normalize_modifier(name))
            return
        if name in self.pressed_keys:
            return
        self.pressed_keys.add(name)
        keys = sorted(self.pressed_modifiers) + [name]
        if keys:
            self.recorded_actions.append({"type": "hotkey", "keys": keys, "delay": self._delay()})

    def _release_key(self, key) -> None:
        name = self._key_name(key)
        if name in MODIFIER_NAMES:
            self.pressed_modifiers.discard(self._normalize_modifier(name))
        else:
            self.pressed_keys.discard(name)

    def _key_name(self, key) -> str:
        try:
            char = key.char
            if char and len(char) == 1 and ord(char) < 32:
                return chr(ord(char) + 96)
            return str(char).lower()
        except AttributeError:
            return str(key).replace("Key.", "").lower()

    def _normalize_modifier(self, name: str) -> str:
        if name.startswith("ctrl"):
            return "ctrl"
        if name.startswith("alt"):
            return "alt"
        if name.startswith("shift"):
            return "shift"
        return name

    def play_macro(self, macro: dict, show_intro: bool = True) -> None:
        if show_intro:
            msg = QMessageBox(self)
            msg.setWindowTitle("매크로 재생")
            msg.setText("매크로를 멈추려면 마우스 가운데 버튼을 눌러주세요.")
            msg.exec()
        bump_usage(macro)
        self.main.save_usage_data()
        self._player = MacroPlayerThread(macro)
        self._player.error.connect(lambda err: QMessageBox.warning(self, "매크로 실행 실패", err))
        self._player.completed.connect(self._on_macro_completed)
        self._player.finished.connect(self._player.deleteLater)
        self._player.start()

    def _on_macro_completed(self, finished_normally: bool) -> None:
        from ui.common import flash_taskbar
        flash_taskbar(self)
        title = "매크로 완료" if finished_normally else "매크로 중지"
        text = "매크로 실행이 완료되었습니다." if finished_normally else "매크로 실행이 중지되었습니다."
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(text)
        QTimer.singleShot(3000, msg.close)
        msg.exec()

    def delete_macro(self, macro: dict) -> None:
        if not confirm_delete(self, "선택한 매크로를 삭제할까요?"):
            return
        self.main.data.get("macros", []).remove(macro)
        self.main.save_data()

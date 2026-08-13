from __future__ import annotations

"""매크로 스크립트(오토핫키 스타일) 파서 · 변환 유틸.

지원 명령 (대소문자 구분 없음):
    ; 주석                            줄 전체가 세미콜론으로 시작하면 주석
    Sleep, ms                         ms 밀리초 대기
    Click [, x, y]                    클릭 (좌표 생략 시 현재 마우스 위치)
    MouseClick, Button [, x, y]       Button(left/right/middle) 지정 클릭
    MouseDoubleClick [, Button, x, y] 지정 버튼(기본 left)으로 더블클릭
    MouseDrag, x1, y1, x2, y2 [, Button]   (x1,y1)에서 버튼을 누른 채 (x2,y2)까지 드래그
    MouseMove, x, y [, speed] [, R]   마우스 이동 (R 이 있으면 x,y 는 현재 위치 기준 상대 이동)
    MouseGetPos, xVar, yVar           현재 마우스 좌표를 변수에 저장
    MouseRestorePos                   가장 최근 MouseGetPos 위치로 마우스를 되돌림
    Send / SendInput, keys            키 입력 — ^Ctrl !Alt +Shift #Win, {Enter} {Tab} {Esc} 등,
                                       {CtrlDown}/{CtrlUp} 등으로 키를 누른 채 유지 가능
    VarName := 값                      변수 지정. 값이 "..."로 감싸이지 않은 경우, 값에서 %변수명% 치환
                                       + 우변 전체가 변수 이름과 완전히 같으면 그 변수의 값(참조)로 취급
                                       (우변이 Clipboard/ClipboardAll 이면 클립보드 값)
    VarName = 값                       변수 지정(레거시). 값은 항상 글자 그대로(변수 참조 없음),
                                       %변수명% 치환만 적용
    Clipboard := 값                    클립보드에 값 저장
    IniWrite, 값, 파일, 섹션, 키          값을 파일에 저장 (다른 매크로 실행/재실행 후에도 유지)
    IniRead, 변수명, 파일, 섹션, 키        파일에서 값을 읽어 변수에 저장
    Run, 대상 [, 작업폴더]               프로그램 실행 / URL·파일·폴더 열기
    WinActivate [, 제목]                창 활성화 (제목 생략 시 마지막으로 찾은 창)
    WinWait / WinWaitActive, 제목 [, 텍스트] [, 초]  창이 나타날/활성화될 때까지 대기
    WinMinimize [, 제목] / WinClose [, 제목]
    IfWinNotActive / IfWinActive, 제목, , WinActivate, 제목   창이 (비)활성 상태면 활성화
    if WinExist("제목") { ... } / if !WinExist("제목") { ... }   창 존재 여부에 따라 실행 (WinActive 도 동일)
    if (변수 == "값") { ... } / if (변수 != "값") { ... }        변수 값 비교
    Loop [, 횟수] { ... }               반복 (횟수 생략 시 무한 반복)
    KeyWait, 키이름 [, U]               키를 누를(기본)/뗄(U) 때까지 대기
    CoordMode, Mouse, Screen|Window|Client   이후 Click/MouseMove/MouseGetPos 좌표 기준
                                       (Screen: 화면 전체 기준(기본값), Window: 활성 창 좌상단 기준,
                                        Client: 활성 창 클라이언트 영역(제목표시줄·테두리 제외) 기준)
    SetWinDelay / SetKeyDelay / SetControlDelay / SetMouseDelay / SendMode / ClipWait / Return
                                       무시 (다른 오토핫키 스크립트를 붙여넣어도 오류가 나지 않도록 허용)
    ^!1:: 같은 핫키 레이블 줄            무시 (매크로 한 개 = 스크립트 한 개이므로 레이블 자체는 필요 없음)

"창 제목"에는 'ahk_exe 파일명.exe' 형식도 쓸 수 있어 프로세스 이름으로 창을 찾을 수 있다.

이 모듈은 Qt/pyautogui 에 의존하지 않아 단독으로 테스트할 수 있다.
실제 클릭/키입력/클립보드/창 제어 실행은 ui/tab_macro.py 의 MacroPlayerThread 가 담당한다.
"""

import re
from dataclasses import dataclass, field


class MacroScriptError(Exception):
    def __init__(self, line_no: int, message: str) -> None:
        super().__init__(f"{line_no}행: {message}")
        self.line_no = line_no
        self.message = message


@dataclass
class Step:
    type: str
    line: int
    params: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 스크립트 파싱
# ---------------------------------------------------------------------------

_ASSIGN_RE = re.compile(r"^([A-Za-z_]\w*)\s*:=\s*(.*)$")
_LEGACY_ASSIGN_RE = re.compile(r"^([A-Za-z_]\w*)\s=\s(.*)$")
_TRAILING_COMMENT_RE = re.compile(r"(?:^|\s);.*$")
_HOTKEY_LABEL_RE = re.compile(r"^[\^!+#<>*~$]*[A-Za-z0-9_]+::?$")
_IF_WIN_RE = re.compile(r'^if\s*\(?\s*(!)?\s*Win(Exist|Active)\s*\(\s*"([^"]*)"\s*\)\s*\)?$', re.IGNORECASE)
_IF_VAR_RE = re.compile(r'^if\s*\(\s*([A-Za-z_]\w*)\s*(==|!=|=)\s*"([^"]*)"\s*\)$', re.IGNORECASE)
_LOOP_RE = re.compile(r"^loop\b\s*,?\s*(.*)$", re.IGNORECASE)
_NUMBER_ONLY_RE = re.compile(r"^\d+(\.\d+)?$")
# 클래식 오토핫키는 명령어와 첫 인자 사이의 콤마를 생략할 수 있다 (예: "Send ^l", "ClipWait 0.1").
# 콤마/공백 어느 쪽으로 구분해도 명령어와 나머지 인자를 동일하게 분리한다.
_COMMAND_HEAD_RE = re.compile(r"^([^\s,]+)\s*,?\s*(.*)$")

_NOOP_COMMANDS = {
    "return",
    "setworkingdir",
    "settitlematchmode",
    "clipwait",
    "setwindelay",
    "setkeydelay",
    "setcontroldelay",
    "setmousedelay",
    "sendmode",
}
_MOUSE_BUTTONS = {"left", "right", "middle"}


def _split_args(text: str, maxsplit: int = -1) -> list[str]:
    return [part.strip() for part in text.split(",", maxsplit)]


def _strip_trailing_comment(raw_value: str) -> str:
    """' ;' 로 시작하는 줄 끝 주석을 제거한다 (오토핫키의 `Var = 값 ; 주석` 관례)."""
    match = _TRAILING_COMMENT_RE.search(raw_value)
    if match:
        return raw_value[: match.start()].rstrip()
    return raw_value.strip()


def _unquote_expression_literal(value: str) -> tuple[str, bool]:
    """':=' 대입 우변이 통째로 "..." 로 감싸인 문자열 리터럴이면 따옴표를 벗긴다.

    (값, 원래 따옴표로 감싸여 있었는지) 를 돌려준다. 따옴표가 있었다면 실행기는
    이 값을 순수 리터럴로만 취급해야 한다 — 따옴표가 없는 ``Clipboard := gx`` 는
    오토핫키 표현식 문법상 gx 변수를 참조하는 것이지만, ``Clipboard := "gx"`` 는
    글자 그대로 "gx" 이기 때문이다. 연결(.)이 섞인 복잡한 표현식은 지원하지 않으므로
    따옴표가 정확히 처음/끝에 한 쌍만 있을 때만 벗기고, 그 외에는 원문 그대로 둔다.
    """
    if len(value) >= 2 and value.startswith('"') and value.endswith('"') and value.count('"') == 2:
        return value[1:-1], True
    return value, False


def _parse_number(text: str, line_no: int, label: str) -> float:
    try:
        return float(text.strip())
    except ValueError:
        raise MacroScriptError(line_no, f"{label} 값은 숫자여야 합니다: {text!r}") from None


def _parse_int(text: str, line_no: int, label: str) -> int:
    try:
        return int(float(text.strip()))
    except ValueError:
        raise MacroScriptError(line_no, f"{label} 값은 숫자여야 합니다: {text!r}") from None


@dataclass
class _Token:
    line: int
    kind: str  # "stmt" | "open" | "close"
    content: str = ""


def _tokenize_lines(text: str) -> list[_Token]:
    """줄 단위로 나누고, 블록 시작('{')/끝('}') 을 별도 토큰으로 분리한다."""
    tokens: list[_Token] = []
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith(";"):
            continue
        if line == "{":
            tokens.append(_Token(line_no, "open"))
            continue
        if line == "}":
            tokens.append(_Token(line_no, "close"))
            continue
        # Send 의 {Enter} 처럼 완결된 {..} 쌍은 먼저 제거한 뒤, 그래도 줄 끝이 '{' 라면
        # Loop/if 블록의 시작으로 본다.
        without_pairs = re.sub(r"\{[^{}]*\}", "", line).rstrip()
        if without_pairs.endswith("{"):
            content = line.rstrip()[:-1].rstrip()
            tokens.append(_Token(line_no, "stmt", content))
            tokens.append(_Token(line_no, "open"))
            continue
        tokens.append(_Token(line_no, "stmt", line))
    return tokens


def parse_script(text: str) -> list[Step]:
    """스크립트 텍스트를 실행 가능한 Step 목록으로 변환한다.

    문법 오류가 있으면 MacroScriptError(line_no, message) 를 발생시킨다.
    Loop/if 블록은 중첩된 Step 목록(params["body"])으로 표현된다.
    """
    tokens = _tokenize_lines(text)
    steps, index = _parse_block(tokens, 0, top_level=True)
    if index < len(tokens):
        raise MacroScriptError(tokens[index].line, "짝이 맞지 않는 '}' 입니다.")
    return steps


def _parse_block(tokens: list[_Token], index: int, top_level: bool = False, open_line: int | None = None) -> tuple[list[Step], int]:
    steps: list[Step] = []
    while index < len(tokens):
        token = tokens[index]
        if token.kind == "close":
            return steps, index + 1
        if token.kind == "open":
            # 앞선 Loop/if 없이 등장한 '{' 는 단순 그룹핑으로 보고 내용을 그대로 이어붙인다.
            # (오토핫키 최신 문법의 '핫키::  { ... }' 전체 감싸기 스타일을 허용하기 위함)
            body, index = _parse_block(tokens, index + 1, open_line=token.line)
            steps.extend(body)
            continue
        step, opens_block = _parse_statement(token.content, token.line)
        index += 1
        if opens_block:
            if index >= len(tokens) or tokens[index].kind != "open":
                raise MacroScriptError(token.line, f"{step.type} 다음에는 {{ }} 블록이 와야 합니다.")
            body, index = _parse_block(tokens, index + 1, open_line=tokens[index].line)
            step.params["body"] = body
            steps.append(step)
            continue
        if step.type != "noop":
            steps.append(step)
    if not top_level:
        raise MacroScriptError(open_line or 1, "여는 '{' 에 대응하는 '}' 를 찾을 수 없습니다.")
    return steps, index


def _parse_statement(line: str, line_no: int) -> tuple[Step, bool]:
    """한 줄을 Step 으로 변환한다. (Step, 블록을 여는 명령인지 여부) 를 돌려준다."""
    if_win_match = _IF_WIN_RE.match(line)
    if if_win_match:
        negate, mode, title = if_win_match.groups()
        return Step("if_win", line_no, {"negate": bool(negate), "mode": mode.lower(), "title": title}), True

    if_var_match = _IF_VAR_RE.match(line)
    if if_var_match:
        var_name, operator, literal = if_var_match.groups()
        return Step("if_var", line_no, {"name": var_name, "negate": operator == "!=", "value": literal}), True

    loop_match = _LOOP_RE.match(line)
    if loop_match:
        count_text = loop_match.group(1).strip()
        count = _parse_int(count_text, line_no, "Loop 반복 횟수") if count_text else None
        return Step("loop", line_no, {"count": count}), True

    assign_match = _ASSIGN_RE.match(line)
    if assign_match:
        name, value = assign_match.groups()
        value, quoted = _unquote_expression_literal(_strip_trailing_comment(value))
        # expr=True(:=)이고 따옴표가 없었다면, 오토핫키 표현식 문법상 우변이 그냥
        # 리터럴 텍스트가 아니라 변수 참조/Clipboard 일 수 있다 (실행기가 판단).
        return Step("assign", line_no, {"name": name, "value": value, "expr": True, "quoted": quoted}), False

    legacy_match = _LEGACY_ASSIGN_RE.match(line)
    if legacy_match:
        name, value = legacy_match.groups()
        value = _strip_trailing_comment(value)
        return Step("assign", line_no, {"name": name, "value": value, "expr": False, "quoted": False}), False

    head_match = _COMMAND_HEAD_RE.match(line)
    command = head_match.group(1) if head_match else line
    rest = head_match.group(2) if head_match else ""
    command_lower = command.lower()

    if command_lower == "sleep":
        return Step("sleep", line_no, {"ms": _parse_number(rest, line_no, "Sleep")}), False

    if command_lower == "click":
        args = _split_args(rest) if rest.strip() else []
        if len(args) >= 2 and args[0] and args[1]:
            x = _parse_int(args[0], line_no, "Click 의 x좌표")
            y = _parse_int(args[1], line_no, "Click 의 y좌표")
            return Step("click", line_no, {"x": x, "y": y}), False
        return Step("click", line_no, {"x": None, "y": None}), False

    if command_lower == "mouseclick":
        args = _split_args(rest) if rest.strip() else []
        button = args[0].lower() if args and args[0] else "left"
        if button not in _MOUSE_BUTTONS:
            raise MacroScriptError(line_no, f"지원하지 않는 마우스 버튼입니다: {button}")
        if len(args) >= 3 and args[1] and args[2]:
            x = _parse_int(args[1], line_no, "MouseClick 의 x좌표")
            y = _parse_int(args[2], line_no, "MouseClick 의 y좌표")
        else:
            x = y = None
        return Step("click", line_no, {"x": x, "y": y, "button": button}), False

    if command_lower == "mousedoubleclick":
        args = _split_args(rest) if rest.strip() else []
        button = args[0].lower() if args and args[0] else "left"
        if button not in _MOUSE_BUTTONS:
            raise MacroScriptError(line_no, f"지원하지 않는 마우스 버튼입니다: {button}")
        if len(args) >= 3 and args[1] and args[2]:
            x = _parse_int(args[1], line_no, "MouseDoubleClick 의 x좌표")
            y = _parse_int(args[2], line_no, "MouseDoubleClick 의 y좌표")
        else:
            x = y = None
        return Step("doubleclick", line_no, {"x": x, "y": y, "button": button}), False

    if command_lower == "mousedrag":
        args = _split_args(rest)
        if len(args) < 4 or not all(args[:4]):
            raise MacroScriptError(line_no, "MouseDrag 는 x1, y1, x2, y2 가 필요합니다.")
        x1 = _parse_int(args[0], line_no, "MouseDrag 의 시작 x좌표")
        y1 = _parse_int(args[1], line_no, "MouseDrag 의 시작 y좌표")
        x2 = _parse_int(args[2], line_no, "MouseDrag 의 도착 x좌표")
        y2 = _parse_int(args[3], line_no, "MouseDrag 의 도착 y좌표")
        button = args[4].lower() if len(args) > 4 and args[4] else "left"
        if button not in _MOUSE_BUTTONS:
            raise MacroScriptError(line_no, f"지원하지 않는 마우스 버튼입니다: {button}")
        return Step("drag", line_no, {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "button": button}), False

    if command_lower == "mousemove":
        args = _split_args(rest)
        if len(args) < 2 or not args[0] or not args[1]:
            raise MacroScriptError(line_no, "MouseMove 는 x, y 좌표가 필요합니다.")
        x = _parse_int(args[0], line_no, "MouseMove 의 x좌표")
        y = _parse_int(args[1], line_no, "MouseMove 의 y좌표")
        relative = any(part.strip().lower() == "r" for part in args[2:])
        return Step("mousemove", line_no, {"x": x, "y": y, "relative": relative}), False

    if command_lower == "mousegetpos":
        args = _split_args(rest)
        if len(args) < 2 or not args[0] or not args[1]:
            raise MacroScriptError(line_no, "MouseGetPos, x변수, y변수 형식이어야 합니다.")
        return Step("mousegetpos", line_no, {"x_var": args[0], "y_var": args[1]}), False

    if command_lower == "mouserestorepos":
        return Step("mouserestorepos", line_no, {}), False

    if command_lower == "coordmode":
        args = _split_args(rest)
        target = args[0].lower() if args and args[0] else ""
        if target != "mouse":
            # Pixel/ToolTip/Caret/Menu 등은 구현하지 않으므로 무시한다.
            return Step("noop", line_no, {}), False
        mode = args[1].lower() if len(args) > 1 and args[1] else "screen"
        if mode not in ("screen", "window", "client"):
            raise MacroScriptError(line_no, f"CoordMode 의 좌표 기준은 Screen/Window/Client 중 하나여야 합니다: {mode}")
        return Step("coordmode", line_no, {"mode": mode}), False

    if command_lower in ("send", "sendinput", "sendplay", "sendevent"):
        return Step("send", line_no, {"text": rest}), False

    if command_lower == "run":
        args = _split_args(rest, 2)
        target = args[0] if args else ""
        if not target:
            raise MacroScriptError(line_no, "Run 은 실행할 대상이 필요합니다.")
        working_dir = args[1] if len(args) > 1 and args[1] else None
        return Step("run", line_no, {"target": target, "working_dir": working_dir}), False

    if command_lower in ("winactivate", "winminimize", "winclose"):
        args = _split_args(rest) if rest.strip() else []
        title = args[0] if args and args[0] else None
        return Step(command_lower, line_no, {"title": title}), False

    if command_lower in ("winwait", "winwaitactive"):
        args = _split_args(rest) if rest.strip() else []
        if not args or not args[0]:
            raise MacroScriptError(line_no, f"{command} 은(는) 창 제목이 필요합니다.")
        title = args[0]
        timeout = None
        for extra in args[1:]:
            if extra and _NUMBER_ONLY_RE.match(extra):
                timeout = float(extra)
        return Step(command_lower, line_no, {"title": title, "timeout": timeout}), False

    if command_lower in ("ifwinnotactive", "ifwinactive"):
        args = _split_args(rest)
        if not args or not args[0]:
            raise MacroScriptError(line_no, f"{command} 은(는) 창 제목이 필요합니다.")
        title = args[0]
        action_command = args[2].strip().lower() if len(args) > 2 else ""
        if action_command != "winactivate":
            raise MacroScriptError(line_no, f"{command} 은(는) 현재 ', , WinActivate, 창제목' 형태만 지원합니다.")
        action_title = args[3] if len(args) > 3 and args[3] else title
        mode = "not_active" if command_lower == "ifwinnotactive" else "active"
        return Step("ifwin_command", line_no, {"mode": mode, "title": title, "action_title": action_title}), False

    if command_lower == "keywait":
        args = _split_args(rest)
        if not args or not args[0]:
            raise MacroScriptError(line_no, "KeyWait 는 키 이름이 필요합니다.")
        key_name = args[0]
        wait_for = "release" if any(part.strip().lower() == "u" for part in args[1:]) else "press"
        return Step("keywait", line_no, {"key": key_name, "wait_for": wait_for}), False

    if command_lower == "iniwrite":
        args = _split_args(rest, 3)
        if len(args) != 4:
            raise MacroScriptError(line_no, "IniWrite, 값, 파일, 섹션, 키 형식이어야 합니다.")
        value, file_name, section, key = args
        if not file_name or not section or not key:
            raise MacroScriptError(line_no, "IniWrite 는 파일/섹션/키를 모두 지정해야 합니다.")
        return Step("iniwrite", line_no, {"value": value, "file": file_name, "section": section, "key": key}), False

    if command_lower == "iniread":
        args = _split_args(rest, 3)
        if len(args) != 4:
            raise MacroScriptError(line_no, "IniRead, 변수명, 파일, 섹션, 키 형식이어야 합니다.")
        name, file_name, section, key = args
        if not name or not file_name or not section or not key:
            raise MacroScriptError(line_no, "IniRead 는 변수명/파일/섹션/키를 모두 지정해야 합니다.")
        return Step("iniread", line_no, {"name": name, "file": file_name, "section": section, "key": key}), False

    if command_lower in _NOOP_COMMANDS:
        return Step("noop", line_no, {}), False

    if _HOTKEY_LABEL_RE.match(line):
        return Step("noop", line_no, {}), False

    raise MacroScriptError(line_no, f"알 수 없는 명령어입니다: {command}")


def count_steps(text: str) -> int:
    """실제로 실행될 줄 수(주석/빈 줄 제외)를 센다. 파싱 오류가 있어도 죽지 않는다."""
    count = 0
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line and not line.startswith(";"):
            count += 1
    return count


def run_target_is_executable(target: str) -> bool:
    """Run 대상이 '"...exe" 인자...' 형태(따옴표로 감싼 실행 파일)인지 판별한다.

    참이면 실행기가 명령줄 문자열 그대로 프로세스를 띄우고(따옴표/인자 처리를 OS 에 맡김),
    거짓이면 URL·문서·폴더로 보고 기본 연결 프로그램으로 연다.
    """
    stripped = target.strip()
    if not stripped.startswith('"'):
        return False
    end = stripped.find('"', 1)
    if end == -1:
        return False
    return stripped[1:end].strip().lower().endswith(".exe")


# ---------------------------------------------------------------------------
# 변수 치환
# ---------------------------------------------------------------------------

_VAR_PATTERN = re.compile(r"%([A-Za-z_]\w*)%")
_CLIPBOARD_VAR_NAMES = ("clipboard", "clipboardall")


def substitute_vars(text: str, variables: dict[str, str], clipboard_getter) -> str:
    """%VarName% 및 %Clipboard%/%ClipboardAll% 를 치환한다."""

    def repl(match: re.Match) -> str:
        name = match.group(1).lower()
        if name in _CLIPBOARD_VAR_NAMES:
            return clipboard_getter()
        return variables.get(name, match.group(0))

    return _VAR_PATTERN.sub(repl, str(text or ""))


def resolve_assign_value(params: dict, variables: dict[str, str], clipboard_getter) -> str:
    """"assign" 스텝(:= 또는 =)의 우변 값을 계산한다.

    := 는 오토핫키 표현식 문법이라, 따옴표로 감싸지 않은 우변 전체가 변수 이름과
    똑같으면 %없이도 그 변수를 참조한다(예: ``Clipboard := gx``). = (레거시)는 항상
    글자 그대로이며 %변수명% 치환만 적용된다. 우변이 (따옴표 없이) Clipboard 또는
    ClipboardAll 이면 클립보드 값을 쓴다 — 이건 := / = 양쪽 다 해당한다.
    """
    raw_value = params["value"]
    stripped = raw_value.strip()
    quoted = params.get("quoted", False)
    if not quoted and stripped.lower() in _CLIPBOARD_VAR_NAMES:
        return clipboard_getter()
    if params.get("expr") and not quoted and stripped.isidentifier():
        return variables.get(stripped.lower(), "")
    return substitute_vars(raw_value, variables, clipboard_getter)


# ---------------------------------------------------------------------------
# Send 문자열 토큰화 (오토핫키 미니 문법)
# ---------------------------------------------------------------------------

MODIFIER_SYMBOLS = {"^": "ctrl", "!": "alt", "+": "shift", "#": "win"}

_SEND_SPECIAL_CHARS = set("^!+#{}%")

AHK_KEY_TO_PYAUTOGUI = {
    "enter": "enter",
    "return": "enter",
    "tab": "tab",
    "esc": "esc",
    "escape": "esc",
    "space": "space",
    "backspace": "backspace",
    "bs": "backspace",
    "delete": "delete",
    "del": "delete",
    "insert": "insert",
    "ins": "insert",
    "home": "home",
    "end": "end",
    "up": "up",
    "down": "down",
    "left": "left",
    "right": "right",
    "pgup": "pageup",
    "pageup": "pageup",
    "pgdn": "pagedown",
    "pagedown": "pagedown",
    "capslock": "capslock",
    "numlock": "numlock",
    "scrolllock": "scrolllock",
    "printscreen": "printscreen",
    "prtsc": "printscreen",
    "pause": "pause",
    "appskey": "apps",
    "lwin": "winleft",
    "rwin": "winright",
}
for _n in range(1, 25):
    AHK_KEY_TO_PYAUTOGUI[f"f{_n}"] = f"f{_n}"
for _n in range(0, 10):
    AHK_KEY_TO_PYAUTOGUI[f"num{_n}"] = f"num{_n}"

# {CtrlDown} {AltUp} 처럼 붙여 쓰는 키 홀드/해제 토큰 → (pyautogui 키 이름, "down"|"up")
_MODIFIER_HOLD_KEYS = {
    "ctrl": "ctrl",
    "alt": "alt",
    "shift": "shift",
    "win": "win",
    "lwin": "winleft",
    "rwin": "winright",
}
_MODIFIER_HOLD_RE = re.compile(r"^(ctrl|alt|shift|lwin|rwin|win)(down|up)$")


def tokenize_send(raw: str) -> list[tuple[str, object]]:
    """Send 인자 문자열을 다음 토큰으로 분해한다.

    ('text', str)              그대로 타이핑
    ('keys', [mod..., key])    조합키 입력 (예: ['ctrl', 'c'])
    ('keydown', key) / ('keyup', key)   {CtrlDown}/{CtrlUp} 등 — 키를 누른 채 유지/해제
    """
    tokens: list[tuple[str, object]] = []
    buffer: list[str] = []
    pending_mods: list[str] = []
    i = 0
    n = len(raw)

    def flush_text() -> None:
        if buffer:
            tokens.append(("text", "".join(buffer)))
            buffer.clear()

    while i < n:
        ch = raw[i]
        if ch in MODIFIER_SYMBOLS:
            pending_mods.append(MODIFIER_SYMBOLS[ch])
            i += 1
            continue
        if ch == "{":
            end = raw.find("}", i + 1)
            if end == -1:
                buffer.append(ch)
                i += 1
                continue
            inner = raw[i + 1 : end].strip()
            i = end + 1
            if inner in ("{", "}"):
                buffer.append(inner)
                continue
            if not inner:
                continue
            hold_match = _MODIFIER_HOLD_RE.match(inner.replace(" ", "").lower())
            if hold_match:
                mod_name, direction = hold_match.groups()
                flush_text()
                tokens.append(("keydown" if direction == "down" else "keyup", _MODIFIER_HOLD_KEYS[mod_name]))
                pending_mods = []
                continue
            parts = inner.split()
            key_word = parts[0].lower()
            repeat = 1
            if len(parts) > 1 and parts[1].isdigit():
                repeat = int(parts[1])
            mapped = AHK_KEY_TO_PYAUTOGUI.get(key_word)
            if mapped is None:
                buffer.append(inner)
                pending_mods = []
                continue
            flush_text()
            for _ in range(repeat):
                tokens.append(("keys", pending_mods + [mapped]))
            pending_mods = []
            continue
        if pending_mods:
            flush_text()
            key = ch.lower() if ch.isalpha() else ch
            tokens.append(("keys", pending_mods + [key]))
            pending_mods = []
            i += 1
            continue
        buffer.append(ch)
        i += 1
    flush_text()
    return tokens


def escape_send_literal(text: str) -> str:
    """텍스트를 그대로 입력되도록 Send 특수문자(^!+#{}%)를 이스케이프한다."""
    out = []
    for ch in text:
        if ch in _SEND_SPECIAL_CHARS:
            out.append("{" + ch + "}")
        else:
            out.append(ch)
    return "".join(out)


# ---------------------------------------------------------------------------
# 레거시 녹화 형식(actions 리스트) → 스크립트 텍스트 변환 (마이그레이션 · 신규 녹화 공용)
# ---------------------------------------------------------------------------

# pynput 키 이름 → 오토핫키 표기
PYNPUT_KEY_TO_AHK = {
    "enter": "Enter",
    "tab": "Tab",
    "esc": "Esc",
    "space": "Space",
    "backspace": "Backspace",
    "delete": "Delete",
    "insert": "Insert",
    "home": "Home",
    "end": "End",
    "up": "Up",
    "down": "Down",
    "left": "Left",
    "right": "Right",
    "page_up": "PgUp",
    "page_down": "PgDn",
    "caps_lock": "CapsLock",
    "num_lock": "NumLock",
    "scroll_lock": "ScrollLock",
    "print_screen": "PrintScreen",
    "pause": "Pause",
    "menu": "AppsKey",
    "cmd": "LWin",
    "cmd_l": "LWin",
    "cmd_r": "RWin",
}
for _n in range(1, 25):
    PYNPUT_KEY_TO_AHK[f"f{_n}"] = f"F{_n}"

_DELAY_SLEEP_THRESHOLD = 0.05  # 이보다 짧은 지연은 Sleep 을 생략
_MERGE_GAP_THRESHOLD = 0.3  # 이보다 긴 지연이면 문자 입력을 이어붙이지 않고 끊음


def _sleep_line(delay_seconds: float) -> str | None:
    if delay_seconds < _DELAY_SLEEP_THRESHOLD:
        return None
    return f"Sleep, {round(delay_seconds * 1000)}"


def _hotkey_action_to_token(action: dict) -> tuple[str | None, bool]:
    """(전송용 토큰 문자열, 단순 리터럴 문자 여부) 를 돌려준다."""
    keys = list(action.get("keys") or [])
    if not keys:
        return None, False
    modifiers = [k for k in keys[:-1] if k in ("ctrl", "alt", "shift")]
    final_key = keys[-1]
    symbol_order = {"ctrl": "^", "alt": "!", "shift": "+"}
    prefix = "".join(symbol_order[m] for m in ("ctrl", "alt", "shift") if m in modifiers)
    if not modifiers and len(final_key) == 1:
        return final_key, True
    ahk_name = PYNPUT_KEY_TO_AHK.get(final_key)
    if ahk_name:
        return f"{prefix}{{{ahk_name}}}", False
    if len(final_key) == 1:
        return f"{prefix}{final_key}", False
    # 알 수 없는 특수 키 — 이름을 그대로 중괄호로 감싼다.
    return f"{prefix}{{{final_key}}}", False


def record_actions_to_script(actions: list[dict]) -> str:
    """레거시 {type: click/hotkey/type, ...} 액션 리스트를 스크립트 텍스트로 변환한다."""
    lines: list[str] = []
    literal_buffer: list[str] = []
    pending_sleep: str | None = None

    def flush_literal() -> None:
        nonlocal pending_sleep
        if literal_buffer:
            if pending_sleep:
                lines.append(pending_sleep)
                pending_sleep = None
            escaped = escape_send_literal("".join(literal_buffer))
            lines.append(f"Send, {escaped}")
            literal_buffer.clear()

    for action in actions:
        action_type = action.get("type")
        delay = float(action.get("delay") or 0)
        sleep_line = _sleep_line(delay)

        if action_type == "hotkey":
            token, is_literal = _hotkey_action_to_token(action)
            if token is None:
                continue
            if is_literal and (not sleep_line or delay < _MERGE_GAP_THRESHOLD):
                if not literal_buffer and sleep_line:
                    pending_sleep = sleep_line
                literal_buffer.append(token)
                continue
            flush_literal()
            if sleep_line:
                lines.append(sleep_line)
            lines.append(f"Send, {token if not is_literal else escape_send_literal(token)}")
            continue

        flush_literal()
        if sleep_line:
            lines.append(sleep_line)
        if action_type == "click":
            x, y = action.get("x"), action.get("y")
            lines.append("Click" if x is None or y is None else f"Click, {int(x)}, {int(y)}")
        elif action_type == "type":
            lines.append(f"Send, {escape_send_literal(str(action.get('text', '')))}")

    flush_literal()
    return "\n".join(lines)

import pytest

from app.macro_script import (
    MacroScriptError,
    count_steps,
    escape_send_literal,
    parse_script,
    record_actions_to_script,
    resolve_assign_value,
    run_target_is_executable,
    substitute_vars,
    tokenize_send,
)


def test_parse_basic_commands():
    steps = parse_script(
        """
        ; 주석
        Sleep, 100
        Click
        Click, 10, 20
        MouseMove, 55, 280
        MouseMove, 80, 0, 0, R
        Send, hello
        """
    )
    types = [step.type for step in steps]
    assert types == ["sleep", "click", "click", "mousemove", "mousemove", "send"]
    assert steps[0].params == {"ms": 100.0}
    assert steps[1].params == {"x": None, "y": None}
    assert steps[2].params == {"x": 10, "y": 20}
    assert steps[3].params == {"x": 55, "y": 280, "relative": False}
    assert steps[4].params == {"x": 80, "y": 0, "relative": True}


def test_parse_assignment_and_clipboard():
    steps = parse_script("clip := Clipboard\nClipboard := %clip%")
    assert steps[0].type == "assign"
    assert steps[0].params == {"name": "clip", "value": "Clipboard", "expr": True, "quoted": False}
    assert steps[1].params == {"name": "Clipboard", "value": "%clip%", "expr": True, "quoted": False}


def test_parse_ini_commands():
    steps = parse_script("IniWrite, %clip%, setting.ini, Settings, clip\nIniRead, gx, setting.ini, Settings, loc_x")
    assert steps[0].type == "iniwrite"
    assert steps[0].params == {"value": "%clip%", "file": "setting.ini", "section": "Settings", "key": "clip"}
    assert steps[1].type == "iniread"
    assert steps[1].params == {"name": "gx", "file": "setting.ini", "section": "Settings", "key": "loc_x"}


def test_parse_ignores_noop_commands():
    steps = parse_script("CoordMode, Pixel, Screen\nClick\nReturn")
    assert [step.type for step in steps] == ["click"]


def test_parse_coordmode_mouse():
    steps = parse_script("CoordMode, Mouse, Client\nClick, 10, 20")
    assert steps[0].type == "coordmode"
    assert steps[0].params == {"mode": "client"}
    assert steps[1].type == "click"


def test_parse_coordmode_mouse_defaults_to_screen():
    steps = parse_script("CoordMode, Mouse")
    assert steps[0].params == {"mode": "screen"}


def test_parse_coordmode_invalid_mode_raises():
    with pytest.raises(MacroScriptError):
        parse_script("CoordMode, Mouse, Bogus")


def test_parse_unknown_command_raises_with_line_number():
    with pytest.raises(MacroScriptError) as exc_info:
        parse_script("Click\nFooBar, 1, 2")
    assert exc_info.value.line_no == 2


def test_parse_mousemove_requires_coordinates():
    with pytest.raises(MacroScriptError):
        parse_script("MouseMove, 10")


def test_count_steps_ignores_comments_and_blank_lines():
    assert count_steps("Click\n; comment\n\nSleep, 10") == 2


def test_substitute_vars():
    result = substitute_vars("%a%-%b%-%missing%", {"a": "1", "b": "2"}, lambda: "CLIP")
    assert result == "1-2-%missing%"
    assert substitute_vars("%Clipboard%", {}, lambda: "CLIP") == "CLIP"


def test_tokenize_send_modifiers_and_braces():
    tokens = tokenize_send("+{Home}^c")
    assert tokens == [("keys", ["shift", "home"]), ("keys", ["ctrl", "c"])]


def test_tokenize_send_literal_text_between_keys():
    tokens = tokenize_send("Hello{Enter}World")
    assert tokens == [("text", "Hello"), ("keys", ["enter"]), ("text", "World")]


def test_tokenize_send_escaped_special_chars():
    tokens = tokenize_send("50{%} off")
    assert tokens == [("text", "50% off")]


def test_escape_send_literal_roundtrip():
    escaped = escape_send_literal("100% ^done^")
    tokens = tokenize_send(escaped)
    assert tokens == [("text", "100% ^done^")]


def test_record_actions_to_script_merges_plain_typing():
    actions = [
        {"type": "hotkey", "keys": ["h"], "delay": 0.2},
        {"type": "hotkey", "keys": ["i"], "delay": 0.01},
        {"type": "click", "x": 100, "y": 200, "delay": 0.5},
        {"type": "hotkey", "keys": ["ctrl", "c"], "delay": 0.1},
    ]
    script = record_actions_to_script(actions)
    assert script == "Sleep, 200\nSend, hi\nSleep, 500\nClick, 100, 200\nSleep, 100\nSend, ^c"


def test_record_actions_to_script_bare_click_and_special_key():
    actions = [
        {"type": "click", "x": None, "y": None, "delay": 60.0},
        {"type": "hotkey", "keys": ["enter"], "delay": 0.0},
    ]
    script = record_actions_to_script(actions)
    assert script == "Sleep, 60000\nClick\nSend, {Enter}"


# ---------------------------------------------------------------------------
# 레거시 대입(=)과 := 문자열 리터럴, 인라인 주석
# ---------------------------------------------------------------------------


def test_legacy_equals_assignment_is_alias_for_colon_equals():
    steps = parse_script("clipboard = ybtour tableau12@#")
    assert steps[0].type == "assign"
    assert steps[0].params == {"name": "clipboard", "value": "ybtour tableau12@#", "expr": False, "quoted": False}


def test_legacy_assignment_strips_trailing_comment_idiom():
    # 'Var =   ;' 는 오토핫키에서 값을 빈 문자열로 지우는 관용구
    steps = parse_script("clipboard =   ;")
    assert steps[0].params == {"name": "clipboard", "value": "", "expr": False, "quoted": False}


def test_colon_equals_unquotes_string_literal():
    steps = parse_script('Clipboard := "wnsln1898!"')
    assert steps[0].params == {"name": "Clipboard", "value": "wnsln1898!", "expr": True, "quoted": True}


def test_colon_equals_keeps_bare_word_unquoted():
    steps = parse_script("clip := Clipboard")
    assert steps[0].params["value"] == "Clipboard"


def test_colon_equals_does_not_unquote_concatenation():
    # 따옴표가 둘 이상(연결식 등)인 복잡한 표현식은 그대로 둔다 (지원하지 않음, 원문 보존)
    steps = parse_script('x := "a" . "b"')
    assert steps[0].params["value"] == '"a" . "b"'


def test_send_without_comma_classic_syntax():
    steps = parse_script("Send ^l")
    assert steps[0].type == "send"
    assert steps[0].params["text"] == "^l"


def test_clipwait_and_delay_commands_are_noop():
    steps = parse_script("ClipWait 0.1\nSetWinDelay, 0\nSetKeyDelay, 0\nSendMode, Input\nClick")
    assert [step.type for step in steps] == ["click"]


def test_hotkey_labels_are_ignored():
    steps = parse_script("^!1::\n    Click\n    Return")
    assert [step.type for step in steps] == ["click"]


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------


def test_parse_run_command():
    steps = parse_script('Run, "C:\\Program Files\\Whale\\whale.exe" "https://naver.com"')
    assert steps[0].type == "run"
    assert steps[0].params["target"] == '"C:\\Program Files\\Whale\\whale.exe" "https://naver.com"'
    assert steps[0].params["working_dir"] is None


def test_run_target_is_executable():
    assert run_target_is_executable('"C:\\Program Files\\Whale\\whale.exe" "https://naver.com"')
    assert run_target_is_executable('"C:\\apps\\XPlatform.exe" -K CHORUS')
    assert not run_target_is_executable("https://naver.com")
    assert not run_target_is_executable("D:\\업무폴더")
    assert not run_target_is_executable('"C:\\docs\\readme.txt"')


# ---------------------------------------------------------------------------
# 창 제어
# ---------------------------------------------------------------------------


def test_parse_window_commands():
    steps = parse_script(
        "WinActivate, ahk_exe notepad.exe\n"
        "WinActivate\n"
        "WinWait, 메모장, , 5\n"
        "WinWaitActive, 메모장\n"
        "WinMinimize\n"
        "WinClose, 메모장\n"
    )
    assert steps[0].params == {"title": "ahk_exe notepad.exe"}
    assert steps[1].params == {"title": None}
    assert steps[2].type == "winwait"
    assert steps[2].params == {"title": "메모장", "timeout": 5.0}
    assert steps[3].type == "winwaitactive"
    assert steps[3].params["timeout"] is None
    assert steps[4].type == "winminimize"
    assert steps[5].params == {"title": "메모장"}


def test_parse_ifwinnotactive_idiom():
    steps = parse_script("IfWinNotActive, 엑셀, , WinActivate, 엑셀")
    assert steps[0].type == "ifwin_command"
    assert steps[0].params == {"mode": "not_active", "title": "엑셀", "action_title": "엑셀"}


def test_ifwinnotactive_requires_winactivate_action():
    with pytest.raises(MacroScriptError):
        parse_script("IfWinNotActive, 엑셀, , WinClose, 엑셀")


def test_parse_if_winexist_block():
    steps = parse_script(
        'if WinExist("NateOn") {\n'
        "    WinActivate\n"
        "    Send ^l\n"
        "}\n"
    )
    assert steps[0].type == "if_win"
    assert steps[0].params["negate"] is False
    assert steps[0].params["mode"] == "exist"
    assert steps[0].params["title"] == "NateOn"
    assert [s.type for s in steps[0].params["body"]] == ["winactivate", "send"]


def test_parse_if_winexist_negated():
    steps = parse_script('if !WinExist("X") {\n    Click\n}\n')
    assert steps[0].params["negate"] is True


def test_parse_if_var_block():
    steps = parse_script('if (ClipSaved != "") {\n    Clipboard := ClipSaved\n}\n')
    assert steps[0].type == "if_var"
    assert steps[0].params["name"] == "ClipSaved"
    assert steps[0].params["negate"] is True
    assert steps[0].params["value"] == ""
    assert len(steps[0].params["body"]) == 1


# ---------------------------------------------------------------------------
# Loop 블록 (유한/무한), 중첩, 전체 감싸는 '{ }'
# ---------------------------------------------------------------------------


def test_parse_loop_with_count_and_brace_on_next_line():
    steps = parse_script("Loop, 3\n{\n    Click\n    Sleep, 10\n}\n")
    assert steps[0].type == "loop"
    assert steps[0].params["count"] == 3
    assert [s.type for s in steps[0].params["body"]] == ["click", "sleep"]


def test_parse_loop_infinite_when_count_omitted():
    steps = parse_script("Loop\n{\n    Sleep, 10\n}\n")
    assert steps[0].params["count"] is None


def test_parse_loop_inline_brace():
    steps = parse_script("Loop, 5 {\n    Click\n}\n")
    assert steps[0].params["count"] == 5


def test_parse_bare_braces_wrap_whole_script_without_error():
    # 최신 오토핫키 스타일의 '핫키:: { ... }' 전체 감싸기 — 단순 그룹핑으로 처리
    steps = parse_script("{\n    Click\n    Sleep, 10\n}\n")
    assert [s.type for s in steps] == ["click", "sleep"]


def test_parse_unmatched_brace_raises():
    with pytest.raises(MacroScriptError):
        parse_script("Loop, 3\n{\n    Click\n")


def test_parse_loop_without_block_raises():
    with pytest.raises(MacroScriptError):
        parse_script("Loop, 3\nClick\n")


# ---------------------------------------------------------------------------
# MouseClick / MouseGetPos / KeyWait
# ---------------------------------------------------------------------------


def test_parse_mouseclick():
    steps = parse_script("MouseClick, left,  1345,  697\nMouseClick, right\n")
    assert steps[0].type == "click"
    assert steps[0].params == {"x": 1345, "y": 697, "button": "left"}
    assert steps[1].params == {"x": None, "y": None, "button": "right"}


def test_parse_mouseclick_invalid_button_raises():
    with pytest.raises(MacroScriptError):
        parse_script("MouseClick, invalid, 1, 2")


def test_parse_mousedoubleclick():
    steps = parse_script("MouseDoubleClick, left, 500, 300\nMouseDoubleClick\n")
    assert steps[0].type == "doubleclick"
    assert steps[0].params == {"x": 500, "y": 300, "button": "left"}
    assert steps[1].params == {"x": None, "y": None, "button": "left"}


def test_parse_mousedoubleclick_invalid_button_raises():
    with pytest.raises(MacroScriptError):
        parse_script("MouseDoubleClick, invalid, 1, 2")


def test_parse_mousedrag():
    steps = parse_script("MouseDrag, 100, 100, 400, 300\nMouseDrag, 0, 0, 10, 10, right\n")
    assert steps[0].type == "drag"
    assert steps[0].params == {"x1": 100, "y1": 100, "x2": 400, "y2": 300, "button": "left"}
    assert steps[1].params == {"x1": 0, "y1": 0, "x2": 10, "y2": 10, "button": "right"}


def test_parse_mousedrag_missing_args_raises():
    with pytest.raises(MacroScriptError):
        parse_script("MouseDrag, 100, 100")


def test_parse_mousedrag_invalid_button_raises():
    with pytest.raises(MacroScriptError):
        parse_script("MouseDrag, 0, 0, 1, 1, invalid")


def test_parse_mousegetpos():
    steps = parse_script("MouseGetPos,vx,vy")
    assert steps[0].type == "mousegetpos"
    assert steps[0].params == {"x_var": "vx", "y_var": "vy"}


def test_parse_mouserestorepos():
    steps = parse_script("MouseGetPos, vx, vy\nClick, 300, 100\nMouseRestorePos")
    assert [s.type for s in steps] == ["mousegetpos", "click", "mouserestorepos"]
    assert steps[2].params == {}


def test_parse_keywait():
    steps = parse_script("KeyWait, f9")
    assert steps[0].params == {"key": "f9", "wait_for": "press"}
    steps = parse_script("KeyWait, f9, U")
    assert steps[0].params["wait_for"] == "release"


# ---------------------------------------------------------------------------
# {CtrlDown}/{CtrlUp} 등 키 홀드 토큰, ClipboardAll
# ---------------------------------------------------------------------------


def test_tokenize_send_modifier_hold_tokens():
    tokens = tokenize_send("{CTRLDOWN}v{CTRLUP}")
    assert tokens == [("keydown", "ctrl"), ("text", "v"), ("keyup", "ctrl")]


def test_tokenize_send_modifier_hold_case_insensitive():
    tokens = tokenize_send("{ShiftDown}{Home}{ShiftUp}{Delete}")
    assert tokens == [("keydown", "shift"), ("keys", ["home"]), ("keyup", "shift"), ("keys", ["delete"])]


def test_substitute_vars_clipboardall_alias():
    assert substitute_vars("%ClipboardAll%", {}, lambda: "CLIP") == "CLIP"


# ---------------------------------------------------------------------------
# resolve_assign_value — ':=' 우변의 따옴표 없는 bare word 는 변수 참조
# (회귀 테스트: "Clipboard := gx" 가 변수 gx 대신 리터럴 문자열 "gx" 를
# 클립보드에 넣던 버그)
# ---------------------------------------------------------------------------


def _clip(text: str = "CLIP"):
    return lambda: text


def test_resolve_assign_value_bare_word_dereferences_variable():
    steps = parse_script("Clipboard := gx")
    value = resolve_assign_value(steps[0].params, {"gx": "1234"}, _clip())
    assert value == "1234"


def test_resolve_assign_value_undefined_bare_word_is_empty():
    steps = parse_script("Clipboard := neverset")
    value = resolve_assign_value(steps[0].params, {}, _clip())
    assert value == ""


def test_resolve_assign_value_quoted_literal_stays_literal_even_if_it_matches_a_var_name():
    steps = parse_script('x := "gx"')
    value = resolve_assign_value(steps[0].params, {"gx": "1234"}, _clip())
    assert value == "gx"


def test_resolve_assign_value_legacy_equals_never_dereferences():
    steps = parse_script("x = gx")
    value = resolve_assign_value(steps[0].params, {"gx": "1234"}, _clip())
    assert value == "gx"


def test_resolve_assign_value_bare_clipboard_keyword():
    steps = parse_script("clip := Clipboard")
    assert resolve_assign_value(steps[0].params, {}, _clip("copied text")) == "copied text"


def test_resolve_assign_value_percent_substitution_still_works_in_expr_mode():
    steps = parse_script("y := %x%_suffix")
    value = resolve_assign_value(steps[0].params, {"x": "1"}, _clip())
    assert value == "1_suffix"


def test_resolve_assign_value_full_iniread_then_assign_roundtrip():
    # ^!2:: 스크립트의 실제 패턴: IniRead 로 읽은 값을 Clipboard := 로 그대로 옮김
    steps = parse_script("IniRead, gx, setting.ini, Settings, loc_x\nClipboard := gx")
    variables = {}
    # IniRead 는 실행기가 파일을 읽어 변수에 저장하는 부분이라 여기서는 결과만 흉내낸다
    variables[steps[0].params["name"].lower()] = "1234"
    value = resolve_assign_value(steps[1].params, variables, _clip())
    assert value == "1234"

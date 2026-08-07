from __future__ import annotations

"""키 조합(핫키) 입력 — pyautogui 가 놓치는 확장 키(Home/End/방향키/PageUp/PageDown/
Insert/Delete)의 KEYEVENTF_EXTENDEDKEY 플래그를 채워서 보낸다.

pyautogui.hotkey()/press() 는 내부적으로 keybd_event 를 쓰면서 이 키들에
KEYEVENTF_EXTENDEDKEY 플래그를 설정하지 않는다. 그 결과 NumLock 상태 등에 따라
Windows 가 넘패드 쪽 스캔코드로 오인할 수 있고, 특히 Shift 와 조합했을 때
(예: Shift+Home) 커서만 이동하고 텍스트 선택은 되지 않는 문제가 생긴다
(Ctrl+C 로 복사해도 클립보드가 빔 — 실측으로 확인됨).

같은 keybd_event API 를 쓰되(그래야 pyautogui 와 섞여도 문제없다) 확장 키에만
플래그를 추가하고, 모디파이어→키→모디파이어 사이에 짧은 delay 를 둔다(대상 앱이
모디파이어가 눌린 상태를 인식하기 전에 다음 키 이벤트가 도착하면 조합이 씹히는
경우가 실측으로 확인됨).
"""

import ctypes
import time

USER32 = ctypes.WinDLL("user32", use_last_error=True)
USER32.keybd_event.argtypes = [ctypes.c_ubyte, ctypes.c_ubyte, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong)]

_KEYEVENTF_EXTENDEDKEY = 0x0001
_KEYEVENTF_KEYUP = 0x0002

# 101/104키 키보드 기준 확장 키 — KEYEVENTF_EXTENDEDKEY 가 필요한 키들.
EXTENDED_KEYS = {
    "home": 0x24,
    "end": 0x23,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
    "pageup": 0x21,
    "pagedown": 0x22,
    "insert": 0x2D,
    "delete": 0x2E,
}
_EXTENDED_VK_CODES = set(EXTENDED_KEYS.values())

_MODIFIER_VK = {
    "shift": 0x10,
    "ctrl": 0x11,
    "alt": 0x12,
    "win": 0x5B,
}

_NAMED_VK = {
    **_MODIFIER_VK,
    **EXTENDED_KEYS,
    "backspace": 0x08,
    "tab": 0x09,
    "enter": 0x0D,
    "return": 0x0D,
    "esc": 0x1B,
    "escape": 0x1B,
    "space": 0x20,
    "capslock": 0x14,
    "numlock": 0x90,
    "scrolllock": 0x91,
    "printscreen": 0x2C,
    "pause": 0x13,
    "apps": 0x5D,
    "winleft": 0x5B,
    "winright": 0x5C,
}
for _n in range(1, 25):
    _NAMED_VK[f"f{_n}"] = 0x6F + _n  # F1=0x70 ... F24=0x87


def key_to_vk(name: str) -> int | None:
    """키 이름(pyautogui 이름 규칙)을 가상 키 코드로 변환한다. 모르는 키면 None."""
    lowered = name.lower()
    if lowered in _NAMED_VK:
        return _NAMED_VK[lowered]
    if len(name) == 1:
        ch = name.upper()
        if ch.isalnum():
            return ord(ch)
    return None


def _send(vk_code: int, key_up: bool) -> None:
    flags = _KEYEVENTF_EXTENDEDKEY if vk_code in _EXTENDED_VK_CODES else 0
    if key_up:
        flags |= _KEYEVENTF_KEYUP
    USER32.keybd_event(vk_code, 0, flags, None)


def press_down(name: str) -> bool:
    """이름의 키를 누른 채로 유지한다({CtrlDown} 등). 모르는 키면 False."""
    vk = key_to_vk(name)
    if vk is None:
        return False
    _send(vk, key_up=False)
    return True


def press_up(name: str) -> bool:
    """이름의 키를 뗀다({CtrlUp} 등). 모르는 키면 False."""
    vk = key_to_vk(name)
    if vk is None:
        return False
    _send(vk, key_up=True)
    return True


def send_hotkey(modifier_names: list[str], key_name: str, delay: float = 0.03) -> bool:
    """모디파이어(shift/ctrl/alt/win)를 누른 채로 key_name 을 누르고 모두 뗀다.

    key_name 이 확장 키가 아니어도 동작하지만, 이 함수의 핵심 목적은 Shift+Home
    같이 확장 키가 낀 조합을 올바르게 보내는 것이다. key_name 을 인식하지 못하면
    아무 것도 하지 않고 False 를 돌려준다.
    """
    vk = key_to_vk(key_name)
    if vk is None:
        return False
    mod_vks = [_MODIFIER_VK[m] for m in modifier_names if m in _MODIFIER_VK]
    for mod_vk in mod_vks:
        _send(mod_vk, key_up=False)
        time.sleep(delay)
    _send(vk, key_up=False)
    time.sleep(delay)
    _send(vk, key_up=True)
    time.sleep(delay)
    for mod_vk in reversed(mod_vks):
        _send(mod_vk, key_up=True)
        time.sleep(delay)
    return True

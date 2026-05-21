from __future__ import annotations

import ctypes
from collections.abc import Callable

from ctypes import wintypes


WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

USER32 = ctypes.WinDLL("user32", use_last_error=True)
USER32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_uint, ctypes.c_uint]
USER32.RegisterHotKey.restype = wintypes.BOOL
USER32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
USER32.UnregisterHotKey.restype = wintypes.BOOL
USER32.GetAsyncKeyState.argtypes = [ctypes.c_int]
USER32.GetAsyncKeyState.restype = ctypes.c_short


class HotkeyManager:
    def __init__(self, hwnd: int | None = None) -> None:
        self.hwnd = int(hwnd or 0)
        self._registered: dict[str, int] = {}
        self._callbacks: dict[int, Callable[[], None]] = {}
        self._items: dict[int, str] = {}
        self._next_id = 1000
        self.available = True
        self.last_error = ""

    def set_hwnd(self, hwnd: int) -> None:
        self.hwnd = int(hwnd)

    def _make_hotkey(self, modifiers: list[str], key: str) -> str:
        aliases = {"control": "ctrl", "windows": "win", "meta": "win", "super": "win"}
        normalized = [aliases.get(str(modifier).lower(), str(modifier).lower()) for modifier in modifiers]
        return "+".join(sorted(dict.fromkeys(normalized)) + [key.lower()])

    def _modifier_flags(self, modifiers: list[str]) -> int:
        flags = MOD_NOREPEAT
        normalized = {str(m).lower() for m in modifiers}
        if "ctrl" in normalized or "control" in normalized:
            flags |= MOD_CONTROL
        if "alt" in normalized:
            flags |= MOD_ALT
        if "shift" in normalized:
            flags |= MOD_SHIFT
        if normalized & {"win", "windows", "meta", "super"}:
            flags |= MOD_WIN
        return flags

    def _vk_code(self, key: str) -> int:
        value = str(key).strip().upper()
        if len(value) == 1 and value.isalnum():
            return ord(value)
        if value.startswith("F") and value[1:].isdigit():
            number = int(value[1:])
            if 1 <= number <= 24:
                return 0x70 + number - 1
        special = {
            ";": 0xBA,
            "SPACE": 0x20,
            "TAB": 0x09,
            "ESC": 0x1B,
            "ESCAPE": 0x1B,
            "ENTER": 0x0D,
            "RETURN": 0x0D,
        }
        return special.get(value, 0)

    def register(self, modifiers: list[str], key: str, callback: Callable[[], None], item_id: str) -> bool:
        hotkey_str = self._make_hotkey(modifiers, key)
        if not hotkey_str or hotkey_str in self._registered:
            return False
        vk = self._vk_code(key)
        if not vk:
            self.last_error = f"unsupported key: {key}"
            return False
        hotkey_id = self._next_id
        self._next_id += 1
        ok = USER32.RegisterHotKey(wintypes.HWND(self.hwnd), hotkey_id, self._modifier_flags(modifiers), vk)
        if not ok:
            self.last_error = f"RegisterHotKey failed: {ctypes.get_last_error()}"
            return False
        self._registered[hotkey_str] = hotkey_id
        self._callbacks[hotkey_id] = callback
        self._items[hotkey_id] = item_id
        return True

    def unregister(self, modifiers: list[str], key: str) -> None:
        hotkey_str = self._make_hotkey(modifiers, key)
        hotkey_id = self._registered.pop(hotkey_str, None)
        if hotkey_id is None:
            return
        USER32.UnregisterHotKey(wintypes.HWND(self.hwnd), hotkey_id)
        self._callbacks.pop(hotkey_id, None)
        self._items.pop(hotkey_id, None)

    def unregister_all(self) -> None:
        for hotkey_id in list(self._callbacks):
            USER32.UnregisterHotKey(wintypes.HWND(self.hwnd), hotkey_id)
        self._registered.clear()
        self._callbacks.clear()
        self._items.clear()

    def is_conflict(self, modifiers: list[str], key: str) -> bool:
        return self._make_hotkey(modifiers, key) in self._registered

    def handle_message(self, message, wparam) -> bool:
        if int(message) != WM_HOTKEY:
            return False
        callback = self._callbacks.get(int(wparam))
        if not callback:
            return False
        callback()
        return True

    @property
    def registered_count(self) -> int:
        return len(self._registered)

from __future__ import annotations

from collections.abc import Callable

try:
    import keyboard
except Exception:  # pragma: no cover - depends on host permissions
    keyboard = None


class HotkeyManager:
    def __init__(self) -> None:
        self._registered: dict[str, str] = {}
        self._callbacks: dict[str, Callable[[], None]] = {}
        self.available = keyboard is not None

    def _make_hotkey(self, modifiers: list[str], key: str) -> str:
        return "+".join(sorted([m.lower() for m in modifiers]) + [key.lower()])

    def register(self, modifiers: list[str], key: str, callback: Callable[[], None], item_id: str) -> bool:
        hotkey_str = self._make_hotkey(modifiers, key)
        if not hotkey_str or hotkey_str in self._registered:
            return False
        if self.available:
            try:
                keyboard.add_hotkey(hotkey_str, callback)
            except Exception:
                self.available = False
                return False
        self._registered[hotkey_str] = item_id
        self._callbacks[hotkey_str] = callback
        return True

    def unregister(self, modifiers: list[str], key: str) -> None:
        hotkey_str = self._make_hotkey(modifiers, key)
        if hotkey_str not in self._registered:
            return
        if self.available:
            try:
                keyboard.remove_hotkey(hotkey_str)
            except Exception:
                self.available = False
        self._registered.pop(hotkey_str, None)
        self._callbacks.pop(hotkey_str, None)

    def unregister_all(self) -> None:
        if self.available:
            try:
                keyboard.unhook_all_hotkeys()
            except Exception:
                self.available = False
        self._registered.clear()
        self._callbacks.clear()

    def is_conflict(self, modifiers: list[str], key: str) -> bool:
        return self._make_hotkey(modifiers, key) in self._registered


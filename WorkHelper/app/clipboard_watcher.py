from __future__ import annotations

import time
import ctypes
from ctypes import wintypes

from PyQt6.QtCore import QThread, pyqtSignal


CF_UNICODETEXT = 13

USER32 = ctypes.WinDLL("user32", use_last_error=True)
KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
USER32.OpenClipboard.argtypes = [wintypes.HWND]
USER32.OpenClipboard.restype = wintypes.BOOL
USER32.CloseClipboard.argtypes = []
USER32.CloseClipboard.restype = wintypes.BOOL
USER32.GetClipboardData.argtypes = [wintypes.UINT]
USER32.GetClipboardData.restype = wintypes.HANDLE
KERNEL32.GlobalLock.argtypes = [wintypes.HGLOBAL]
KERNEL32.GlobalLock.restype = wintypes.LPWSTR
KERNEL32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
KERNEL32.GlobalUnlock.restype = wintypes.BOOL


def read_clipboard_text() -> str:
    if not USER32.OpenClipboard(None):
        return ""
    try:
        handle = USER32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""
        pointer = KERNEL32.GlobalLock(handle)
        if not pointer:
            return ""
        try:
            return ctypes.wstring_at(pointer)
        finally:
            KERNEL32.GlobalUnlock(handle)
    finally:
        USER32.CloseClipboard()


class ClipboardWatcher(QThread):
    new_item = pyqtSignal(str)

    def __init__(self, interval: float = 0.5) -> None:
        super().__init__()
        self.interval = interval
        self._running = True

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        prev = ""
        while self._running:
            try:
                current = read_clipboard_text()
            except Exception:
                current = ""
            if current != prev and current.strip():
                prev = current
                self.new_item.emit(current)
            time.sleep(self.interval)

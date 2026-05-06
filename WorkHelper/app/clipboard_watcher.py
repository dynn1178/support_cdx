from __future__ import annotations

import time

import pyperclip
from PyQt6.QtCore import QThread, pyqtSignal


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
                current = pyperclip.paste()
            except Exception:
                current = ""
            if current != prev and current.strip():
                prev = current
                self.new_item.emit(current)
            time.sleep(self.interval)


from __future__ import annotations

import time

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.utils import new_id, normalize_hotkey
from ui.common import add_widget_item, make_card


class MacroTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        self.recording = False
        self.recorded_actions: list[dict] = []
        self.mouse_listener = None
        self.keyboard_listener = None
        self.record_name = ""
        self.last_event_at = 0.0
        layout = QVBoxLayout(self)
        self.list = QListWidget()
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["type", "value", "delay", "extra"])
        layout.addWidget(self.list, 1)
        layout.addWidget(self.table, 1)
        row = QHBoxLayout()
        add_btn = QPushButton("+ 빈 매크로")
        record_btn = QPushButton("녹화")
        stop_btn = QPushButton("정지")
        play_btn = QPushButton("재생")
        delete_btn = QPushButton("삭제")
        add_btn.clicked.connect(self.add_macro)
        record_btn.clicked.connect(self.start_recording)
        stop_btn.clicked.connect(self.stop_recording)
        play_btn.clicked.connect(self.play_selected)
        delete_btn.clicked.connect(self.delete_selected)
        row.addWidget(add_btn)
        row.addWidget(record_btn)
        row.addWidget(stop_btn)
        row.addWidget(play_btn)
        row.addWidget(delete_btn)
        layout.addLayout(row)
        self.list.currentRowChanged.connect(self.load_actions)

    def refresh(self) -> None:
        self.list.clear()
        for macro in self.main.data.get("macros", []):
            add_widget_item(self.list, make_card(macro.get("name", "(이름 없음)"), f"{len(macro.get('actions', []))}개 액션", normalize_hotkey(macro.get("hotkey"))))

    def selected_macro(self) -> dict | None:
        row = self.list.currentRow()
        macros = self.main.data.get("macros", [])
        return macros[row] if 0 <= row < len(macros) else None

    def load_actions(self, *_args) -> None:
        macro = self.selected_macro()
        actions = macro.get("actions", []) if macro else []
        self.table.setRowCount(len(actions))
        for row, action in enumerate(actions):
            self.table.setItem(row, 0, QTableWidgetItem(action.get("type", "")))
            if action.get("type") == "click":
                value = f"{action.get('x', 0)}, {action.get('y', 0)}"
            elif action.get("type") == "hotkey":
                value = "+".join(action.get("keys", []))
            else:
                value = action.get("text", "")
            self.table.setItem(row, 1, QTableWidgetItem(value))
            self.table.setItem(row, 2, QTableWidgetItem(str(action.get("delay", 0))))
            self.table.setItem(row, 3, QTableWidgetItem(""))

    def add_macro(self) -> None:
        name, ok = QInputDialog.getText(self, "매크로 추가", "이름")
        if not ok or not name.strip():
            return
        self.main.data.setdefault("macros", []).append({"id": new_id("mc"), "name": name.strip(), "hotkey": None, "actions": []})
        self.main.save_data()

    def start_recording(self) -> None:
        if self.recording:
            return
        name, ok = QInputDialog.getText(self, "매크로 녹화", "이름")
        if not ok or not name.strip():
            return
        try:
            from pynput import keyboard as pynput_keyboard
            from pynput import mouse as pynput_mouse
        except Exception as exc:
            QMessageBox.warning(self, "녹화 시작 실패", str(exc))
            return
        self.recording = True
        self.record_name = name.strip()
        self.recorded_actions = []
        self.last_event_at = time.monotonic()
        self.mouse_listener = pynput_mouse.Listener(on_click=self._record_click)
        self.keyboard_listener = pynput_keyboard.Listener(on_press=self._record_key)
        self.mouse_listener.start()
        self.keyboard_listener.start()
        QMessageBox.information(self, "녹화 시작", "매크로 녹화를 시작했습니다. 종료하려면 정지 버튼을 누르세요.")

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
        self.main.data.setdefault("macros", []).append(
            {"id": new_id("mc"), "name": self.record_name, "hotkey": None, "actions": self.recorded_actions}
        )
        self.main.save_data()
        QMessageBox.information(self, "녹화 완료", f"{len(self.recorded_actions)}개 액션을 저장했습니다.")

    def _delay(self) -> float:
        now = time.monotonic()
        delay = max(0.0, now - self.last_event_at)
        self.last_event_at = now
        return round(delay, 3)

    def _record_click(self, x, y, button, pressed) -> None:
        if self.recording and pressed:
            self.recorded_actions.append({"type": "click", "x": int(x), "y": int(y), "delay": self._delay()})

    def _record_key(self, key) -> None:
        if not self.recording:
            return
        try:
            name = key.char
        except AttributeError:
            name = str(key).replace("Key.", "")
        if name:
            self.recorded_actions.append({"type": "hotkey", "keys": [name], "delay": self._delay()})

    def play_selected(self) -> None:
        macro = self.selected_macro()
        if not macro:
            return
        try:
            import pyautogui

            for action in macro.get("actions", []):
                time.sleep(float(action.get("delay", 0)))
                if action.get("type") == "click":
                    pyautogui.click(int(action.get("x", 0)), int(action.get("y", 0)))
                elif action.get("type") == "hotkey":
                    pyautogui.hotkey(*action.get("keys", []))
                elif action.get("type") == "type":
                    pyautogui.typewrite(action.get("text", ""), interval=0.05)
        except Exception as exc:
            QMessageBox.warning(self, "매크로 실행 실패", str(exc))

    def delete_selected(self) -> None:
        macro = self.selected_macro()
        if macro:
            self.main.data.get("macros", []).remove(macro)
            self.main.save_data()

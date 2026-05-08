from __future__ import annotations

import time

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHeaderView,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.utils import display_hotkey, new_id, now_iso
from ui.common import GridPanel, HotkeyFields, SortControls, add_card_actions, apply_manual_reorder, bump_usage, confirm_shift_digit_hotkey, make_card


MODIFIER_NAMES = {"ctrl", "ctrl_l", "ctrl_r", "alt", "alt_l", "alt_r", "shift", "shift_l", "shift_r"}


class MacroActionsDialog(QDialog):
    def __init__(self, macro: dict) -> None:
        super().__init__()
        self.macro = macro
        self.setWindowTitle(f"매크로 이력 - {macro.get('name', '(이름 없음)')}")
        self.resize(720, 420)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(macro.get("name", ""))
        self.hotkey = HotkeyFields(macro.get("hotkey"))
        form.addRow("이름", self.name)
        form.addRow("실행 단축키", self.hotkey)
        layout.addLayout(form)
        self.table = QTableWidget(0, 4)
        self.table.setStyleSheet("QHeaderView::section { padding: 3px 6px; font-weight: 500; }")
        self.table.setHorizontalHeaderLabels(["TYPE", "VALUE", "DELAY", "EXTRA"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.load_actions()
        layout.addWidget(self.table)

        action_row = QHBoxLayout()
        delete_row = QPushButton("선택 이력 삭제")
        delete_row.clicked.connect(self.delete_selected_rows)
        action_row.addWidget(delete_row)
        action_row.addStretch(1)
        layout.addLayout(action_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("저장")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def delete_selected_rows(self) -> None:
        rows = sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.table.removeRow(row)

    def load_actions(self) -> None:
        actions = self.macro.get("actions", [])
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

    def actions(self) -> list[dict]:
        edited = []
        for row in range(self.table.rowCount()):
            action_type = self._text(row, 0)
            value = self._text(row, 1)
            try:
                delay = float(self._text(row, 2) or 0)
            except ValueError:
                delay = 0.0
            if action_type == "click":
                parts = [part.strip() for part in value.split(",", 1)]
                if len(parts) == 2:
                    edited.append({"type": "click", "x": int(float(parts[0])), "y": int(float(parts[1])), "delay": delay})
            elif action_type == "hotkey":
                keys = [part.strip() for part in value.split("+") if part.strip()]
                if keys:
                    edited.append({"type": "hotkey", "keys": keys, "delay": delay})
            elif action_type == "type":
                edited.append({"type": "type", "text": value, "delay": delay})
        return edited

    def value(self) -> dict:
        return {"name": self.name.text().strip(), "hotkey": self.hotkey.value(), "actions": self.actions()}

    def _text(self, row: int, col: int) -> str:
        item = self.table.item(row, col)
        return item.text().strip() if item else ""


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
        top = QHBoxLayout()
        self.sort_controls = SortControls(self.refresh)
        top.addStretch(1)
        top.addWidget(self.sort_controls)
        layout.addLayout(top)
        row = QHBoxLayout()
        record_btn = QPushButton("녹화")
        stop_btn = QPushButton("정지")
        record_btn.clicked.connect(self.start_recording)
        stop_btn.clicked.connect(self.stop_recording)
        row.addStretch(1)
        row.addWidget(record_btn)
        row.addWidget(stop_btn)
        self.list = GridPanel(columns=3)
        layout.addWidget(self.list, 1)
        layout.addLayout(row)

    def refresh(self) -> None:
        cards = []
        source_items = self.main.data.get("macros", [])
        visible_items = self.sort_controls.sort_items(source_items, lambda value: value.get("name", ""))
        for macro in visible_items:
            card = make_card(macro.get("name", "(이름 없음)"), f"{len(macro.get('actions', []))}개 액션", display_hotkey(macro.get("hotkey")), card_size="b")
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
        macro["actions"] = value["actions"]
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
        items = self.main.data.setdefault("macros", [])
        items.append(
            {
                "id": new_id("mc"),
                "name": self.record_name,
                "hotkey": self.record_hotkey,
                "actions": self.recorded_actions,
                "created_at": now_iso(),
                "sort_order": len(items),
                "usage_count": 0,
            }
        )
        self.main.save_data()
        QMessageBox.information(self, "녹화 완료", f"{len(self.recorded_actions)}개 액션을 저장했습니다.")

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

    def play_macro(self, macro: dict) -> None:
        try:
            import pyautogui

            bump_usage(macro)
            self.main.save_data()
            time.sleep(1.0)
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

    def delete_macro(self, macro: dict) -> None:
        self.main.data.get("macros", []).remove(macro)
        self.main.save_data()

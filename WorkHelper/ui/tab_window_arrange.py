from __future__ import annotations

"""창 정렬 — 템플릿에 프로그램별 창 위치/크기를 저장해두고 한 번에 불러온다.

각 템플릿(예: 웹서핑용/보고용/분석용)은 여러 개의 항목을 담고, 항목마다
대상 프로그램(프로세스 파일명)과 화면 좌표(x, y, width, height)를 저장한다.
정렬 버튼은 두 가지다 — 이미 실행 중인 창만 옮기는 것과, 실행되지 않은
항목은 등록해둔 실행 파일로 띄운 뒤(창이 뜰 때까지 잠시 기다렸다가) 옮기는 것.
"""

from PyQt6.QtCore import QThread, QTimer, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.utils import new_id, now_iso
from ui.common import (
    GridPanel,
    SortControls,
    add_card_actions,
    apply_manual_reorder,
    confirm_delete,
    dialog_palette,
    make_card,
    style_list_selection,
)


def _item_label(item: dict) -> str:
    return item.get("label") or item.get("process_exe") or "(이름 없음)"


def _item_summary(item: dict) -> str:
    if item.get("maximized"):
        return f"{item.get('process_exe', '')} · 최대화"
    return f"{item.get('process_exe', '')} · {item.get('width', 0)}x{item.get('height', 0)} @ ({item.get('x', 0)}, {item.get('y', 0)})"


class WindowCaptureDialog(QDialog):
    """3초 뒤 현재 활성 창의 위치/크기/프로세스를 캡처한다 (매크로 탭의 좌표 캡처와 같은 패턴)."""

    captured = pyqtSignal(tuple)  # (process_exe, title, x, y, width, height)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("창 캡처")
        layout = QVBoxLayout(self)
        self.label = QLabel("3초 후 현재 활성 창(맨 앞에 있는 창)의 위치와 크기를 캡처합니다.\n캡처하고 싶은 창을 지금 클릭해 활성화해두세요.")
        self.label.setWordWrap(True)
        layout.addWidget(self.label)
        self._countdown = 3
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    def _tick(self) -> None:
        self._countdown -= 1
        if self._countdown <= 0:
            self._timer.stop()
            from app import win_control

            info = win_control.active_window_info()
            self.captured.emit(info or ())
            self.accept()
            return
        self.label.setText(f"{self._countdown}초 후 캡처됩니다. 캡처하고 싶은 창을 지금 활성화해두세요.")


class WindowLayoutItemDialog(QDialog):
    def __init__(self, item: dict) -> None:
        super().__init__()
        self.item = item
        self.process_exe = item.get("process_exe", "")
        self.window_title = item.get("window_title", "")
        self.setWindowTitle(f"창 항목 - {_item_label(item)}")
        self.resize(420, 340)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.label = QLineEdit(item.get("label", ""))
        self.process_display = QLabel(self.process_exe or "(캡처 필요)")
        self.process_display.setObjectName("mutedText")
        capture_btn = QPushButton("현재 활성 창 캡처 (3초 후)")
        capture_btn.clicked.connect(self.capture_window)
        process_row = QHBoxLayout()
        process_row.setContentsMargins(0, 0, 0, 0)
        process_row.addWidget(capture_btn)
        process_row.addWidget(self.process_display, 1)
        process_widget = QWidget()
        process_widget.setLayout(process_row)
        form.addRow("이름", self.label)
        form.addRow("대상 프로그램", process_widget)

        self.x = QSpinBox()
        self.y = QSpinBox()
        self.width = QSpinBox()
        self.height = QSpinBox()
        for spin in (self.x, self.y):
            spin.setRange(-10000, 10000)
        for spin in (self.width, self.height):
            spin.setRange(1, 10000)
        self.x.setValue(int(item.get("x", 0)))
        self.y.setValue(int(item.get("y", 0)))
        self.width.setValue(int(item.get("width", 800) or 800))
        self.height.setValue(int(item.get("height", 600) or 600))
        pos_row = QHBoxLayout()
        pos_row.setContentsMargins(0, 0, 0, 0)
        for caption, field in (("X", self.x), ("Y", self.y), ("W", self.width), ("H", self.height)):
            pos_row.addWidget(QLabel(caption))
            pos_row.addWidget(field)
        pos_widget = QWidget()
        pos_widget.setLayout(pos_row)
        form.addRow("위치/크기", pos_widget)

        self.maximized = QCheckBox("이 창은 최대화 상태로 정렬")
        self.maximized.setChecked(bool(item.get("maximized")))
        self.maximized.toggled.connect(lambda checked: pos_widget.setDisabled(checked))
        pos_widget.setDisabled(self.maximized.isChecked())
        form.addRow("", self.maximized)

        self.launch_path = QLineEdit(item.get("launch_path", ""))
        self.launch_path.setPlaceholderText("실행되지 않았을 때 대신 실행할 파일 (선택)")
        browse_btn = QPushButton("찾아보기...")
        browse_btn.clicked.connect(self.browse_launch_path)
        launch_row = QHBoxLayout()
        launch_row.setContentsMargins(0, 0, 0, 0)
        launch_row.addWidget(self.launch_path, 1)
        launch_row.addWidget(browse_btn)
        launch_widget = QWidget()
        launch_widget.setLayout(launch_row)
        form.addRow("실행 파일", launch_widget)
        layout.addLayout(form)

        hint = QLabel("실행 파일을 지정해두면 '실행 안 된 항목도 실행해서 정렬' 버튼을 눌렀을 때 이 경로로 프로그램을 띄운 뒤 위치를 맞춥니다.")
        hint.setObjectName("mutedText")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("확인")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
        buttons.accepted.connect(self._try_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def capture_window(self) -> None:
        dialog = WindowCaptureDialog(self)
        dialog.captured.connect(self._on_captured)
        dialog.exec()

    def _on_captured(self, info: tuple) -> None:
        if not info:
            QMessageBox.warning(self, "캡처 실패", "활성 창 정보를 가져오지 못했습니다.")
            return
        process_exe, title, x, y, width, height = info
        self.process_exe = process_exe
        self.window_title = title
        self.process_display.setText(f"{process_exe}  ({title})")
        self.x.setValue(x)
        self.y.setValue(y)
        self.width.setValue(max(1, width))
        self.height.setValue(max(1, height))
        if not self.label.text().strip():
            self.label.setText(title[:30] or process_exe)

    def browse_launch_path(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "실행 파일 선택", "", "실행 파일 (*.exe *.lnk);;모든 파일 (*.*)")
        if path:
            self.launch_path.setText(path)

    def _try_accept(self) -> None:
        if not self.process_exe:
            QMessageBox.warning(self, "입력 확인", "먼저 '현재 활성 창 캡처'로 대상 프로그램을 지정해주세요.")
            return
        if not self.label.text().strip():
            self.label.setText(self.process_exe)
        self.accept()

    def value(self) -> dict:
        return {
            "id": self.item.get("id") or new_id("wli"),
            "label": self.label.text().strip(),
            "process_exe": self.process_exe,
            "window_title": self.window_title,
            "x": self.x.value(),
            "y": self.y.value(),
            "width": self.width.value(),
            "height": self.height.value(),
            "maximized": self.maximized.isChecked(),
            "launch_path": self.launch_path.text().strip(),
        }


class WindowLayoutDialog(QDialog):
    def __init__(self, layout_item: dict) -> None:
        super().__init__()
        self.layout_item = layout_item
        self.items: list[dict] = [dict(entry) for entry in layout_item.get("items", [])]
        self.setWindowTitle(f"창 정렬 템플릿 - {layout_item.get('name') or '새 템플릿'}")
        self.resize(520, 480)

        outer = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(layout_item.get("name", ""))
        form.addRow("템플릿 이름", self.name)
        outer.addLayout(form)

        self.list = QListWidget()
        style_list_selection(self.list, dialog_palette(self))
        self.list.itemDoubleClicked.connect(lambda _item: self.edit_item())
        outer.addWidget(self.list, 1)
        self._refresh_list()

        btn_row = QHBoxLayout()
        add_btn = QPushButton("창 추가")
        edit_btn = QPushButton("수정")
        remove_btn = QPushButton("삭제")
        up_btn = QPushButton("위로")
        down_btn = QPushButton("아래로")
        add_btn.clicked.connect(self.add_item)
        edit_btn.clicked.connect(self.edit_item)
        remove_btn.clicked.connect(self.remove_item)
        up_btn.clicked.connect(lambda: self._move_item(-1))
        down_btn.clicked.connect(lambda: self._move_item(1))
        for btn in (add_btn, edit_btn, remove_btn, up_btn, down_btn):
            btn_row.addWidget(btn)
        outer.addLayout(btn_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("저장")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
        buttons.accepted.connect(self._try_accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _refresh_list(self) -> None:
        self.list.clear()
        for entry in self.items:
            self.list.addItem(f"{_item_label(entry)}  —  {_item_summary(entry)}")

    def add_item(self) -> None:
        dialog = WindowLayoutItemDialog({})
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        self.items.append(dialog.value())
        self._refresh_list()

    def edit_item(self) -> None:
        row = self.list.currentRow()
        if row < 0:
            return
        dialog = WindowLayoutItemDialog(self.items[row])
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        self.items[row] = dialog.value()
        self._refresh_list()

    def remove_item(self) -> None:
        row = self.list.currentRow()
        if row < 0:
            return
        self.items.pop(row)
        self._refresh_list()

    def _move_item(self, delta: int) -> None:
        row = self.list.currentRow()
        new_row = row + delta
        if row < 0 or new_row < 0 or new_row >= len(self.items):
            return
        self.items[row], self.items[new_row] = self.items[new_row], self.items[row]
        self._refresh_list()
        self.list.setCurrentRow(new_row)

    def _try_accept(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(self, "입력 확인", "템플릿 이름을 지정해주세요.")
            return
        if not self.items:
            QMessageBox.warning(self, "입력 확인", "창을 하나 이상 추가해주세요.")
            return
        self.accept()

    def value(self) -> dict:
        return {"name": self.name.text().strip(), "items": self.items}


class WindowArrangeThread(QThread):
    finished_summary = pyqtSignal(dict)

    def __init__(self, layout_data: dict, launch_missing: bool) -> None:
        super().__init__()
        self.layout_data = layout_data
        self.launch_missing = launch_missing

    def run(self) -> None:
        import os
        import time

        from app import win_control

        positioned: list[str] = []
        skipped: list[str] = []
        for item in self.layout_data.get("items", []):
            process_exe = str(item.get("process_exe") or "").strip()
            label = _item_label(item)
            if not process_exe:
                skipped.append(label)
                continue
            hwnd = win_control.find_window(f"ahk_exe {process_exe}")
            if not hwnd and self.launch_missing:
                launch_path = str(item.get("launch_path") or "").strip()
                if launch_path:
                    try:
                        os.startfile(launch_path)
                    except Exception:
                        pass
                    deadline = time.monotonic() + 15.0
                    while hwnd is None and time.monotonic() < deadline:
                        time.sleep(0.5)
                        hwnd = win_control.find_window(f"ahk_exe {process_exe}")
            if not hwnd:
                skipped.append(label)
                continue
            win_control.move_resize_window(
                hwnd,
                item.get("x", 0),
                item.get("y", 0),
                item.get("width", 800),
                item.get("height", 600),
                bool(item.get("maximized")),
            )
            positioned.append(label)
        self.finished_summary.emit({"positioned": positioned, "skipped": skipped})


class WindowArrangeTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        self._threads: list[WindowArrangeThread] = []
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
        new_btn = QPushButton("신규 템플릿")
        new_btn.clicked.connect(self.create_layout)
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        hint = QLabel("템플릿에 등록해둔 위치/크기대로 창을 옮깁니다. '실행중만 정렬'은 이미 켜진 창만 옮기고, '실행+정렬'은 꺼져 있는 항목을 실행 파일로 띄운 뒤 옮깁니다.")
        hint.setObjectName("mutedText")
        hint.setWordWrap(True)
        page_layout.addWidget(hint)
        page_layout.addWidget(self.list, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(new_btn)
        page_layout.addLayout(row)
        self.tabs.addTab(page, "창 정렬")
        layout.addWidget(self.tabs, 1)

    def refresh(self) -> None:
        cards = []
        q = self.search.text().strip().lower()
        source_items = self.main.data.get("window_layouts", [])
        visible_items = self.sort_controls.sort_items(source_items, lambda value: value.get("name", ""))
        for layout_item in visible_items:
            if q and q not in layout_item.get("name", "").lower():
                continue
            card = make_card(layout_item.get("name", "(이름 없음)"), f"{len(layout_item.get('items', []))}개 창", "", card_size="b")
            add_card_actions(
                card,
                [
                    ("edit", "수정", lambda checked=False, value=layout_item: self.edit_layout(value), False),
                    ("▶️", "실행중만 정렬", lambda checked=False, value=layout_item: self.run_layout(value, False), False),
                    ("🚀", "실행 안 된 항목도 실행해서 정렬", lambda checked=False, value=layout_item: self.run_layout(value, True), False),
                    ("delete", "삭제", lambda checked=False, value=layout_item: self.delete_layout(value), True),
                ],
            )
            cards.append(card)
        callback = (lambda old, new: self.reorder_items(source_items, visible_items, old, new)) if self.sort_controls.is_manual() else None
        self.list.add_cards(cards, on_reorder=callback)

    def reorder_items(self, source: list[dict], visible: list[dict], old: int, new: int) -> None:
        apply_manual_reorder(source, visible, old, new)
        self.main.save_data()

    def create_layout(self) -> None:
        dialog = WindowLayoutDialog({"name": "", "items": []})
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        value = dialog.value()
        items = self.main.data.setdefault("window_layouts", [])
        items.append(
            {
                "id": new_id("wl"),
                "name": value["name"],
                "items": value["items"],
                "created_at": now_iso(),
                "sort_order": len(items),
            }
        )
        self.main.save_data()
        self.refresh()

    def edit_layout(self, layout_item: dict) -> None:
        dialog = WindowLayoutDialog(layout_item)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        value = dialog.value()
        layout_item["name"] = value["name"]
        layout_item["items"] = value["items"]
        self.main.save_data()
        self.refresh()

    def delete_layout(self, layout_item: dict) -> None:
        if not confirm_delete(self, "선택한 창 정렬 템플릿을 삭제할까요?"):
            return
        self.main.data.get("window_layouts", []).remove(layout_item)
        self.main.save_data()
        self.refresh()

    def run_layout(self, layout_item: dict, launch_missing: bool) -> None:
        thread = WindowArrangeThread(layout_item, launch_missing)
        self._threads.append(thread)
        thread.finished_summary.connect(lambda summary, t=thread: self._on_arrange_finished(summary, t))
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def _on_arrange_finished(self, summary: dict, thread: WindowArrangeThread) -> None:
        if thread in self._threads:
            self._threads.remove(thread)
        positioned = summary.get("positioned", [])
        skipped = summary.get("skipped", [])
        lines = [f"정렬 완료: {len(positioned)}개"]
        if positioned:
            lines.append("· " + ", ".join(positioned))
        if skipped:
            lines.append(f"찾지 못한 항목: {len(skipped)}개")
            lines.append("· " + ", ".join(skipped))
        QMessageBox.information(self, "창 정렬", "\n".join(lines))

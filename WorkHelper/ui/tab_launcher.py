from __future__ import annotations

import os
import subprocess
import webbrowser

import pyperclip
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.utils import new_id, short_preview
from ui.common import add_widget_item, make_card


class LauncherDialog(QDialog):
    def __init__(self, item: dict | None = None, launcher_type: str = "site") -> None:
        super().__init__()
        self.setWindowTitle("바로가기 편집")
        self.item = item or {"type": launcher_type}
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.type = QComboBox()
        self.type.addItems(["site", "file", "folder"])
        idx = self.type.findText(self.item.get("type", launcher_type))
        self.type.setCurrentIndex(max(idx, 0))
        self.name = QLineEdit(self.item.get("name", ""))
        self.description = QLineEdit(self.item.get("description", ""))
        self.url = QLineEdit(self.item.get("url", ""))
        self.path = QLineEdit(self.item.get("path", ""))
        self.username = QLineEdit(self.item.get("username", ""))
        self.password = QLineEdit(self.item.get("password", ""))
        self.browser_path = QLineEdit(self.item.get("browser_path", ""))
        browse = QPushButton("찾기")
        browse.clicked.connect(self.browse_path)
        path_row = QHBoxLayout()
        path_row.addWidget(self.path, 1)
        path_row.addWidget(browse)
        form.addRow("종류", self.type)
        form.addRow("이름", self.name)
        form.addRow("설명", self.description)
        form.addRow("URL", self.url)
        form.addRow("경로", path_row)
        form.addRow("아이디", self.username)
        form.addRow("비밀번호", self.password)
        form.addRow("브라우저", self.browser_path)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def browse_path(self) -> None:
        if self.type.currentText() == "folder":
            path = QFileDialog.getExistingDirectory(self, "폴더 선택")
        else:
            path, _ = QFileDialog.getOpenFileName(self, "파일 선택")
        if path:
            self.path.setText(path)

    def value(self) -> dict:
        data = dict(self.item)
        data.update(
            {
                "type": self.type.currentText(),
                "name": self.name.text().strip(),
                "description": self.description.text().strip(),
                "url": self.url.text().strip(),
                "path": self.path.text().strip(),
                "username": self.username.text().strip(),
                "password": self.password.text(),
                "browser_path": self.browser_path.text().strip(),
            }
        )
        return data


class LauncherTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.site_list = QListWidget()
        self.file_list = QListWidget()
        self.tabs.addTab(self.site_list, "사이트")
        self.tabs.addTab(self.file_list, "파일/폴더")
        layout.addWidget(self.tabs, 1)
        add_btn = QPushButton("+ 바로가기")
        add_btn.clicked.connect(self.edit_launcher)
        layout.addWidget(add_btn)

    def refresh(self) -> None:
        self.site_list.clear()
        self.file_list.clear()
        for item in self.main.data.get("launchers", []):
            target = self.site_list if item.get("type") == "site" else self.file_list
            card = make_card(item.get("name", "(이름 없음)"), item.get("description", "") or short_preview(item.get("url") or item.get("path", "")))
            row = QHBoxLayout()
            open_btn = QPushButton("열기")
            edit_btn = QPushButton("편집")
            del_btn = QPushButton("삭제")
            open_btn.clicked.connect(lambda checked=False, value=item: self.open_launcher(value))
            edit_btn.clicked.connect(lambda checked=False, value=item: self.edit_launcher(value))
            del_btn.clicked.connect(lambda checked=False, value=item: self.delete_launcher(value))
            row.addWidget(open_btn)
            row.addWidget(edit_btn)
            row.addWidget(del_btn)
            card.layout().addLayout(row)
            add_widget_item(target, card)

    def open_launcher(self, item: dict) -> None:
        try:
            if item.get("type") == "site":
                credential = item.get("password") or item.get("username")
                if credential:
                    pyperclip.copy(credential)
                if item.get("browser_path"):
                    subprocess.Popen([item["browser_path"], item.get("url", "")])
                else:
                    webbrowser.open(item.get("url", ""))
            elif item.get("type") == "folder":
                subprocess.Popen(["explorer", item.get("path", "")])
            else:
                os.startfile(item.get("path", ""))
        except Exception as exc:
            QMessageBox.warning(self, "실행 실패", str(exc))

    def edit_launcher(self, item: dict | None = None) -> None:
        dialog = LauncherDialog(item)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        value = dialog.value()
        if not value.get("name"):
            QMessageBox.warning(self, "입력 확인", "이름을 입력해주세요.")
            return
        if not value.get("id"):
            value["id"] = new_id("ln")
        items = self.main.data.setdefault("launchers", [])
        if item in items:
            items[items.index(item)] = value
        else:
            items.append(value)
        self.main.save_data()

    def delete_launcher(self, item: dict) -> None:
        if QMessageBox.question(self, "삭제", "선택한 바로가기를 삭제할까요?") != QMessageBox.StandardButton.Yes:
            return
        self.main.data.get("launchers", []).remove(item)
        self.main.save_data()


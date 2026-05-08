from __future__ import annotations

import os
import subprocess
import webbrowser
from pathlib import Path

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app import config
from app.utils import display_hotkey, new_id, now_iso, short_preview
from ui.common import GridPanel, HotkeyFields, SortControls, apply_manual_reorder, apply_modern_dialog_style, ask_modern_question, bump_usage, confirm_shift_digit_hotkey, make_card, make_icon_button, show_modern_warning


TYPE_LABELS = {"site": "사이트", "file": "파일", "folder": "폴더"}
TYPE_ALIASES = {"사이트": "site", "파일": "file", "폴더": "folder", "site": "site", "file": "file", "folder": "folder"}


def launcher_type(value: str | None) -> str:
    return TYPE_ALIASES.get(str(value or "site").strip().lower(), TYPE_ALIASES.get(str(value or "site").strip(), "site"))


class LauncherDialog(QDialog):
    def __init__(self, item: dict | None = None, launcher_type_value: str = "site") -> None:
        super().__init__()
        self.setWindowTitle("바로가기 편집")
        apply_modern_dialog_style(self)
        self.setMinimumWidth(460)
        self.item = item or {"type": launcher_type_value}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.type = QComboBox()
        for value in ["site", "file", "folder"]:
            self.type.addItem(TYPE_LABELS[value], value)
        self.type.setCurrentIndex(max(self.type.findData(launcher_type(self.item.get("type"))), 0))
        self.type.currentIndexChanged.connect(self.update_enabled_fields)

        self.name = QLineEdit(self.item.get("name", ""))
        self.description = QLineEdit(self.item.get("description", ""))
        self.url = QLineEdit(self.item.get("url", ""))
        self.path = QLineEdit(self.item.get("path", ""))
        self.username = QLineEdit(self.item.get("username", ""))
        self.password = QLineEdit(self.item.get("password", ""))
        self.browser_path = QLineEdit(self.item.get("browser_path", ""))
        self.hotkey = HotkeyFields(self.item.get("hotkey"))
        self.browser_path.setPlaceholderText("기본 브라우저로 연결")

        self.browse_path_btn = QPushButton("찾기")
        self.browse_path_btn.clicked.connect(self.browse_path)
        self.browse_browser_btn = QPushButton("찾기")
        self.browse_browser_btn.clicked.connect(self.browse_browser)

        path_row = QHBoxLayout()
        path_row.setContentsMargins(0, 0, 0, 0)
        path_row.setSpacing(8)
        path_row.addWidget(self.path, 1)
        path_row.addWidget(self.browse_path_btn)
        path_widget = QWidget()
        path_widget.setLayout(path_row)

        browser_row = QHBoxLayout()
        browser_row.setContentsMargins(0, 0, 0, 0)
        browser_row.setSpacing(8)
        browser_row.addWidget(self.browser_path, 1)
        browser_row.addWidget(self.browse_browser_btn)
        browser_widget = QWidget()
        browser_widget.setLayout(browser_row)

        form.addRow("종류", self.type)
        form.addRow("이름", self.name)
        form.addRow("설명", self.description)
        form.addRow("URL", self.url)
        form.addRow("경로", path_widget)
        form.addRow("아이디", self.username)
        form.addRow("비밀번호", self.password)
        form.addRow("브라우저 경로", browser_widget)
        form.addRow("단축키", self.hotkey)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("확인")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.update_enabled_fields()

    def current_type(self) -> str:
        return self.type.currentData()

    def set_field_enabled(self, widget: QWidget, enabled: bool) -> None:
        widget.setEnabled(enabled)
        widget.setStyleSheet("" if enabled else "background: #D1D5DB; color: #6B7280; border-color: #9CA3AF;")

    def update_enabled_fields(self, *_args) -> None:
        is_site = self.current_type() == "site"
        self.set_field_enabled(self.url, is_site)
        self.set_field_enabled(self.browser_path, is_site)
        self.browse_browser_btn.setEnabled(is_site)
        self.set_field_enabled(self.username, is_site)
        self.set_field_enabled(self.password, is_site)
        self.set_field_enabled(self.path, not is_site)
        self.browse_path_btn.setEnabled(not is_site)

    def browse_path(self) -> None:
        if self.current_type() == "folder":
            path = QFileDialog.getExistingDirectory(self, "폴더 선택")
        else:
            path, _ = QFileDialog.getOpenFileName(self, "파일 선택")
        if path:
            self.path.setText(path)

    def browse_browser(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "브라우저 선택", "", "Programs (*.exe);;All Files (*.*)")
        if path:
            self.browser_path.setText(path)

    def value(self) -> dict:
        data = dict(self.item)
        data.update(
            {
                "type": self.current_type(),
                "name": self.name.text().strip(),
                "description": self.description.text().strip(),
                "url": self.url.text().strip(),
                "path": self.path.text().strip(),
                "username": self.username.text().strip(),
                "password": self.password.text(),
                "browser_path": self.browser_path.text().strip(),
                "hotkey": self.hotkey.value(),
            }
        )
        return data


class LauncherTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        self.status_labels: dict[str, QLabel] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        self.site_list = GridPanel(columns=2)
        self.file_list = GridPanel(columns=3)
        self.tabs.addTab(self.site_list, "사이트")
        self.tabs.addTab(self.file_list, "파일/폴더")
        self.sort_controls = SortControls(self.refresh)
        self.tabs.setCornerWidget(self.sort_controls, Qt.Corner.TopRightCorner)
        layout.addWidget(self.tabs, 1)
        add_btn = QPushButton("+ 바로가기")
        add_btn.clicked.connect(self.edit_launcher)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(add_btn)
        layout.addLayout(row)

    def refresh(self) -> None:
        self.status_labels = {}
        site_cards = []
        file_cards = []
        source_items = self.main.data.get("launchers", [])
        items = self.sort_controls.sort_items(
            source_items,
            lambda value: value.get("name") or value.get("description") or value.get("url") or value.get("path", ""),
        )
        site_items = []
        file_items = []
        for item in items:
            item_type = launcher_type(item.get("type"))
            card = make_card(item.get("name", "(이름 없음)"), item.get("description", "") or short_preview(item.get("url") or item.get("path", "")), display_hotkey(item.get("hotkey")), card_size="b")
            self.add_launcher_actions(card, item)
            if item_type == "site":
                site_items.append(item)
                site_cards.append(card)
            else:
                file_items.append(item)
                file_cards.append(card)
        site_callback = (lambda old, new: self.reorder_items(source_items, site_items, old, new)) if self.sort_controls.is_manual() else None
        file_callback = (lambda old, new: self.reorder_items(source_items, file_items, old, new)) if self.sort_controls.is_manual() else None
        self.site_list.add_cards(site_cards, on_reorder=site_callback)
        self.file_list.add_cards(file_cards, on_reorder=file_callback)

    def reorder_items(self, source: list[dict], visible: list[dict], old: int, new: int) -> None:
        apply_manual_reorder(source, visible, old, new)
        self.main.save_data()

    def add_launcher_actions(self, card: QWidget, item: dict) -> None:
        row = QHBoxLayout()
        row.setContentsMargins(0, 2, 0, 0)
        status = QLabel("")
        status.setStyleSheet("color: #168A4A; font-weight: 700;")
        status.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.status_labels[item.get("id", "")] = status
        row.addWidget(status, 1)
        row.addWidget(make_icon_button("open", "열기", lambda checked=False, value=item: self.open_launcher(value)))
        row.addWidget(make_icon_button("edit", "수정", lambda checked=False, value=item: self.edit_launcher(value)))
        row.addWidget(make_icon_button("delete", "삭제", lambda checked=False, value=item: self.delete_launcher(value), True))
        card.layout().addLayout(row)

    def show_credential_status(self, item: dict) -> None:
        label = self.status_labels.get(item.get("id", ""))
        if not label:
            return
        label.setText("아이디/비밀번호 클립보드 저장 완료!")
        timer = QTimer(label)
        timer.setSingleShot(True)
        timer.timeout.connect(label.clear)
        timer.timeout.connect(timer.deleteLater)
        timer.start(1000)

    def save_usage_only(self) -> None:
        config.save_template(self.main.template_index, self.main.data)

    def open_launcher(self, item: dict) -> None:
        try:
            item_type = launcher_type(item.get("type"))
            bump_usage(item)
            if item_type == "site":
                credentials = " ".join(part for part in [item.get("username", ""), item.get("password", "")] if part)
                if credentials:
                    QApplication.clipboard().setText(credentials)
                    self.show_credential_status(item)
                if item.get("browser_path"):
                    subprocess.Popen([item["browser_path"], item.get("url", "")])
                else:
                    webbrowser.open(item.get("url", ""))
                self.save_usage_only()
                return

            path = item.get("path", "")
            if not path or not Path(path).exists():
                show_modern_warning(self, "실행 실패", f"경로를 찾을 수 없습니다.\n{path}")
                return
            os.startfile(path)
            self.save_usage_only()
        except Exception as exc:
            show_modern_warning(self, "실행 실패", str(exc))

    def edit_launcher(self, item: dict | None = None) -> None:
        dialog = LauncherDialog(item)
        while dialog.exec() == dialog.DialogCode.Accepted:
            value = dialog.value()
            if not value.get("name"):
                show_modern_warning(dialog, "입력 확인", "이름을 지정해주세요.")
                continue
            if value.get("type") == "site" and not value.get("url"):
                show_modern_warning(dialog, "입력 확인", "URL을 지정해주세요.")
                continue
            if value.get("type") in {"file", "folder"} and not value.get("path"):
                show_modern_warning(dialog, "입력 확인", "경로를 지정해주세요.")
                continue
            if value.get("type") == "site" and (value.get("username") or value.get("password")):
                if not ask_modern_question(
                    dialog,
                    "계정 정보 저장 주의",
                    "입력한 아이디와 비밀번호는 별도 보안 작업 없이 저장됩니다.\n개인 계정 입력은 피하고 공용 계정 정보만 입력해주세요.\n\n그래도 등록할까요?",
                    None,
                    "등록",
                    "취소",
                ):
                    continue
            conflict = self.main.first_hotkey_conflict(candidate=value, original=item)
            if conflict:
                show_modern_warning(dialog, "단축키 충돌", conflict)
                continue
            if not confirm_shift_digit_hotkey(dialog, value.get("hotkey")):
                continue
            if not value.get("id"):
                value["id"] = new_id("ln")
                value["created_at"] = now_iso()
                value["sort_order"] = len(self.main.data.setdefault("launchers", []))
                value["usage_count"] = 0
            items = self.main.data.setdefault("launchers", [])
            if item in items:
                items[items.index(item)] = value
            else:
                items.append(value)
            self.main.save_data()
            return

    def delete_launcher(self, item: dict) -> None:
        if not ask_modern_question(self, "삭제", "선택한 바로가기를 삭제할까요?", None, "삭제", "취소"):
            return
        self.main.data.get("launchers", []).remove(item)
        self.main.save_data()

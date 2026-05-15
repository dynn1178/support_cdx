from __future__ import annotations

import os
import re
import subprocess
import threading
import webbrowser
from pathlib import Path
from urllib.parse import quote_plus, urljoin, urlparse

from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QImageReader, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app import config
from app.utils import display_hotkey, new_id, now_iso, resolve_image_path, short_preview
from ui.common import ElidedLabel, ElidedMultilineLabel, GridPanel, HotkeyFields, SortControls, apply_manual_reorder, apply_modern_dialog_style, ask_modern_question, bump_usage, confirm_delete, confirm_shift_digit_hotkey, dialog_palette, make_card, make_hotkey_caps, make_icon_button, show_modern_warning


TYPE_ALIASES = {"사이트": "site", "파일": "file", "폴더": "folder", "site": "site", "file": "file", "folder": "folder"}


class CustomSearchDialog(QDialog):
    def __init__(self, item: dict | None = None) -> None:
        super().__init__()
        self.item = item or {}
        action = "수정" if item else "등록"
        self.setWindowTitle(f"검색 바로가기 {action}")
        apply_modern_dialog_style(self)
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(12)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.name = QLineEdit(self.item.get("name", ""))
        self.url = QLineEdit(self.item.get("url", ""))
        self.url.setPlaceholderText("https://example.com/search?q={query}")
        form.addRow("이름", self.name)
        form.addRow("검색 URL", self.url)
        hint = QLabel("{query} 자리에 검색어가 삽입됩니다.")
        hint.setObjectName("mutedText")
        layout.addLayout(form)
        layout.addWidget(hint)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("확인")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def value(self) -> dict:
        data = dict(self.item)
        data.update({"name": self.name.text().strip(), "url": self.url.text().strip()})
        return data


def launcher_type(value: str | None) -> str:
    return TYPE_ALIASES.get(str(value or "site").strip().lower(), TYPE_ALIASES.get(str(value or "site").strip(), "site"))


LAUNCHER_ICON_EMOJIS = [
    "🌐", "🔗", "⭐", "🔎", "💬", "📌", "📍", "🚀", "⚡", "🔥",
    "✅", "📣", "📨", "🛒", "💳", "💼", "📊", "📈", "📉", "🧾",
    "🗂️", "📁", "📂", "📄", "📝", "📋", "📎", "🖼️", "🎨", "🧰",
    "🛠️", "⚙️", "🔒", "🔑", "🏠", "🏢", "🏦", "🏨", "✈️", "🧳",
    "🚗", "📅", "⏰", "☕", "🍽️", "🎁", "🎬", "🎵", "🎮", "💡",
    "❤️", "😊", "🤝", "👥", "📞", "📧", "💻", "🖥️", "🗃️", "🧭",
]
DEFAULT_LAUNCHER_ICONS = {"site": "🌐", "file": "📄", "folder": "📁"}


def launcher_icon_mode(item: dict) -> str:
    return "emoji" if item.get("icon_mode") == "emoji" else "auto"


def launcher_icon_emoji(item: dict) -> str:
    item_type = launcher_type(item.get("type"))
    emoji = str(item.get("icon_emoji") or "").strip()
    return emoji or DEFAULT_LAUNCHER_ICONS.get(item_type, "🔗")


def launcher_auto_emoji(item: dict) -> str:
    return DEFAULT_LAUNCHER_ICONS.get(launcher_type(item.get("type")), "🔗")


def launcher_favicon_pixmap(item: dict) -> QPixmap:
    if launcher_type(item.get("type")) != "site" or launcher_icon_mode(item) != "auto":
        return QPixmap()
    return QPixmap(resolve_image_path(item.get("favicon_path", ""), config.BASE_DIR))


def valid_favicon_path(path_value: str) -> bool:
    path = resolve_image_path(path_value, config.BASE_DIR)
    if not path_value or not Path(path).exists():
        return False
    reader = QImageReader(path)
    return reader.canRead()


def launcher_display_emoji(item: dict) -> str:
    return launcher_icon_emoji(item) if launcher_icon_mode(item) == "emoji" else launcher_auto_emoji(item)


class LauncherDialog(QDialog):
    def __init__(self, item: dict | None = None, launcher_type_value: str = "site") -> None:
        super().__init__()
        self.item = item or {"type": launcher_type_value}
        self.fixed_type = launcher_type(self.item.get("type", launcher_type_value))
        action = "수정" if item else "등록"
        title_by_type = {"site": f"사이트 {action}", "file": f"파일/폴더 {action}", "folder": f"파일/폴더 {action}"}
        self.setWindowTitle(title_by_type.get(self.fixed_type, "바로가기 등록"))
        apply_modern_dialog_style(self)
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.name = QLineEdit(self.item.get("name", ""))
        self.url = QLineEdit(self.item.get("url", ""))
        self.path = QLineEdit(self.item.get("path", ""))
        self.username = QLineEdit(self.item.get("username", ""))
        self.password = QLineEdit(self.item.get("password", ""))
        self.show_credentials_on_card = QCheckBox("카드에 아이디/비밀번호 표시")
        self.show_credentials_on_card.setChecked(bool(self.item.get("show_credentials_on_card", False)))
        self.browser_path = QLineEdit(self.item.get("browser_path", ""))
        self.hotkey = HotkeyFields(self.item.get("hotkey"))
        self.selected_icon_emoji = launcher_icon_emoji(self.item)
        self.icon_mode_group = QButtonGroup(self)
        self.icon_mode_auto = QRadioButton("파비콘 사용" if self.fixed_type == "site" else "기본 아이콘 사용")
        self.icon_mode_emoji = QRadioButton("이모지 직접 지정")
        self.icon_mode_group.addButton(self.icon_mode_auto)
        self.icon_mode_group.addButton(self.icon_mode_emoji)
        if launcher_icon_mode(self.item) == "emoji":
            self.icon_mode_emoji.setChecked(True)
        else:
            self.icon_mode_auto.setChecked(True)
        self.browser_path.setPlaceholderText("기본 브라우저로 연결")

        self.browse_file_btn = QPushButton("파일")
        self.browse_file_btn.clicked.connect(self.browse_file)
        self.browse_folder_btn = QPushButton("폴더")
        self.browse_folder_btn.clicked.connect(self.browse_folder)
        self.browse_browser_btn = QPushButton("찾기")
        self.browse_browser_btn.clicked.connect(self.browse_browser)

        path_row = QHBoxLayout()
        path_row.setContentsMargins(0, 0, 0, 0)
        path_row.setSpacing(8)
        path_row.addWidget(self.path, 1)
        path_row.addWidget(self.browse_file_btn)
        path_row.addWidget(self.browse_folder_btn)
        path_widget = QWidget()
        path_widget.setLayout(path_row)

        browser_row = QHBoxLayout()
        browser_row.setContentsMargins(0, 0, 0, 0)
        browser_row.setSpacing(8)
        browser_row.addWidget(self.browser_path, 1)
        browser_row.addWidget(self.browse_browser_btn)
        browser_widget = QWidget()
        browser_widget.setLayout(browser_row)

        form.addRow("이름", self.name)
        if self.fixed_type == "site":
            form.addRow("URL", self.url)
            form.addRow("아이디", self.username)
            form.addRow("비밀번호", self.password)
            form.addRow("브라우저 경로", browser_widget)
        else:
            form.addRow("경로", path_widget)
        form.addRow("단축키", self.hotkey)
        layout.addLayout(form)

        icon_box = QWidget()
        icon_box.setObjectName("launcherIconPicker")
        colors = dialog_palette(self)
        icon_box.setStyleSheet(f"QWidget#launcherIconPicker {{ background: {colors.get('panel', 'transparent')}; border: 0; }}")
        icon_layout = QVBoxLayout(icon_box)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setSpacing(8)
        mode_row = QHBoxLayout()
        mode_row.setContentsMargins(0, 0, 0, 0)
        mode_row.addWidget(self.icon_mode_auto)
        mode_row.addWidget(self.icon_mode_emoji)
        mode_row.addStretch(1)
        self.pick_emoji_btn = QPushButton("이모지 선택")
        self.pick_emoji_btn.clicked.connect(self.open_emoji_picker)
        mode_row.addWidget(self.pick_emoji_btn)
        self.icon_preview = QLabel()
        self.icon_preview.setFixedSize(28, 28)
        self.icon_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_preview.setStyleSheet("font-size: 14pt; background: transparent; border: 0;")
        mode_row.addWidget(self.icon_preview)
        icon_layout.addLayout(mode_row)

        self.emoji_grid_widget = QWidget()
        self.emoji_grid_widget.setObjectName("launcherEmojiGrid")
        emoji_grid = QGridLayout()
        emoji_grid.setContentsMargins(0, 0, 0, 0)
        emoji_grid.setHorizontalSpacing(4)
        emoji_grid.setVerticalSpacing(4)
        self.emoji_grid_widget.setLayout(emoji_grid)
        self.emoji_grid_widget.setParent(self)
        self.emoji_grid_widget.setWindowFlags(Qt.WindowType.Widget)
        self.emoji_grid_widget.hide()
        self.emoji_grid_widget.setStyleSheet(
            f"""
            QWidget#launcherEmojiGrid {{
                background: {colors.get("panel", "#FFFFFF")};
                border: 1px solid {colors.get("border", "#B9C0CC")};
                border-radius: 8px;
            }}
            """
        )
        self.emoji_buttons: list[QPushButton] = []
        for index, emoji in enumerate(LAUNCHER_ICON_EMOJIS):
            button = QPushButton(emoji)
            button.setCheckable(True)
            button.setFixedSize(28, 26)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(
                "QPushButton { background: transparent; color: inherit; border: 1px solid rgba(148, 163, 184, 55);"
                " border-radius: 5px; font-size: 11pt; padding: 0; margin: 0; }"
                "QPushButton:hover { background: rgba(148, 163, 184, 28); }"
                "QPushButton:checked { background: rgba(59, 108, 245, 38); border-color: #3B6CF5; }"
            )
            button.clicked.connect(lambda checked=False, value=emoji: self.select_icon_emoji(value))
            self.emoji_buttons.append(button)
            emoji_grid.addWidget(button, index // 10, index % 10)
        layout.addWidget(icon_box)
        self.icon_mode_auto.toggled.connect(self.refresh_icon_picker)
        self.icon_mode_emoji.toggled.connect(self.refresh_icon_picker)
        self.refresh_icon_picker()

        footer = QHBoxLayout()
        if self.fixed_type == "site":
            footer.addWidget(self.show_credentials_on_card)
        footer.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("확인")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        footer.addWidget(buttons)
        layout.addLayout(footer)

    def select_icon_emoji(self, emoji: str) -> None:
        self.selected_icon_emoji = emoji
        self.icon_mode_emoji.setChecked(True)
        if hasattr(self, "emoji_grid_widget"):
            self.emoji_grid_widget.hide()
        self.refresh_icon_picker()

    def open_emoji_picker(self) -> None:
        if not self.icon_mode_emoji.isChecked():
            self.icon_mode_emoji.setChecked(True)
        self.refresh_icon_picker()
        self.emoji_grid_widget.adjustSize()
        pos = self.pick_emoji_btn.mapTo(self, self.pick_emoji_btn.rect().bottomLeft())
        max_x = max(0, self.width() - self.emoji_grid_widget.width() - 10)
        x = min(max(10, pos.x()), max_x)
        y = min(pos.y() + 6, max(10, self.height() - self.emoji_grid_widget.height() - 10))
        self.emoji_grid_widget.move(x, y)
        self.emoji_grid_widget.raise_()
        self.emoji_grid_widget.show()

    def refresh_icon_picker(self) -> None:
        emoji_enabled = self.icon_mode_emoji.isChecked()
        preview = self.selected_icon_emoji if emoji_enabled else DEFAULT_LAUNCHER_ICONS.get(self.fixed_type, "🔗")
        self.icon_preview.setText(preview)
        if hasattr(self, "pick_emoji_btn"):
            self.pick_emoji_btn.setVisible(emoji_enabled)
        if hasattr(self, "emoji_grid_widget"):
            if not emoji_enabled:
                self.emoji_grid_widget.hide()
        for button in getattr(self, "emoji_buttons", []):
            button.setEnabled(emoji_enabled)
            button.setChecked(button.text() == self.selected_icon_emoji)
        if not emoji_enabled:
            self.adjustSize()

    def current_type(self) -> str:
        return self.fixed_type

    def browse_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "파일 선택")
        if path:
            self.path.setText(path)

    def browse_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "폴더 선택")
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
                "type": "folder" if self.current_type() != "site" and Path(self.path.text().strip()).is_dir() else self.current_type(),
                "name": self.name.text().strip(),
                "description": "",
                "url": self.url.text().strip() if self.current_type() == "site" else "",
                "path": self.path.text().strip() if self.current_type() != "site" else "",
                "username": self.username.text().strip() if self.current_type() == "site" else "",
                "password": self.password.text() if self.current_type() == "site" else "",
                "browser_path": self.browser_path.text().strip() if self.current_type() == "site" else "",
                "show_credentials_on_card": self.current_type() == "site" and self.show_credentials_on_card.isChecked(),
                "icon_mode": "emoji" if self.icon_mode_emoji.isChecked() else "auto",
                "icon_emoji": self.selected_icon_emoji,
                "hotkey": self.hotkey.value(),
            }
        )
        return data


class LauncherTab(QWidget):
    _favicon_done = pyqtSignal()

    SEARCH_ENGINES = [
        ("네이버", "https://search.naver.com/search.naver?query={query}"),
        ("구글", "https://www.google.com/search?q={query}"),
        ("유튜브", "https://www.youtube.com/results?search_query={query}"),
        ("다음", "https://search.daum.net/search?q={query}"),
        ("빙", "https://www.bing.com/search?q={query}"),
    ]

    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        self.status_labels: dict[str, QLabel] = {}
        self._favicon_done.connect(self._on_favicon_ready)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        self.site_list = GridPanel(columns=2)
        self.file_list = GridPanel(columns=2)
        self.quick_search_page = QWidget()
        self._quick_search_page_layout = QVBoxLayout(self.quick_search_page)
        self._quick_search_page_layout.setContentsMargins(0, 0, 0, 0)
        self._quick_search_content = None
        self.tabs.addTab(self.site_list, "사이트")
        self.tabs.addTab(self.file_list, "파일/폴더")
        self.tabs.addTab(self.quick_search_page, "바로검색")
        self.sort_controls = SortControls(self.refresh)
        self.search = QLineEdit()
        self.search.setPlaceholderText("검색...")
        self.search.setFixedWidth(120)
        self.search.setFixedHeight(26)
        self.search.setStyleSheet("QLineEdit { padding: 1px 6px; font-size: 9pt; }")
        self.search.textChanged.connect(self.refresh)
        corner = QWidget()
        corner_layout = QHBoxLayout(corner)
        corner_layout.setContentsMargins(0, 0, 4, 0)
        corner_layout.setSpacing(4)
        corner_layout.addWidget(self.search)
        corner_layout.addWidget(self.sort_controls)
        self.tabs.setCornerWidget(corner, Qt.Corner.TopRightCorner)
        layout.addWidget(self.tabs, 1)
        self.add_site_btn = QPushButton("+ 사이트 등록")
        self.add_site_btn.clicked.connect(lambda: self.edit_launcher(launcher_type_value="site"))
        self.add_file_btn = QPushButton("+ 파일/폴더 등록")
        self.add_file_btn.clicked.connect(lambda: self.edit_launcher(launcher_type_value="file"))
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.add_site_btn)
        row.addWidget(self.add_file_btn)
        layout.addLayout(row)
        self.tabs.currentChanged.connect(self.update_add_buttons)
        self.build_quick_search_tab()
        self.update_add_buttons()

    def update_add_buttons(self) -> None:
        idx = self.tabs.currentIndex()
        is_quick_search = idx == 2
        self.search.setVisible(not is_quick_search)
        self.sort_controls.setVisible(not is_quick_search)
        self.add_site_btn.setVisible(idx == 0)
        self.add_file_btn.setVisible(idx == 1)

    def build_quick_search_tab(self) -> None:
        if self._quick_search_content is not None:
            self._quick_search_page_layout.removeWidget(self._quick_search_content)
            self._quick_search_content.deleteLater()
            self._quick_search_content = None

        content = QWidget()
        clayout = QVBoxLayout(content)
        clayout.setContentsMargins(10, 10, 10, 10)
        clayout.setSpacing(8)

        for name, url in self.SEARCH_ENGINES:
            clayout.addWidget(self._make_search_row(name, url))

        for item in self.main.data.get("custom_searches", []):
            clayout.addWidget(self._make_custom_search_row(item))

        add_btn = QPushButton("+ 검색 추가")
        add_btn.clicked.connect(self.add_custom_search)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(add_btn)
        clayout.addLayout(btn_row)
        clayout.addStretch(1)

        self._quick_search_content = content
        self._quick_search_page_layout.addWidget(content)

    def _make_search_row(self, name: str, url: str) -> QWidget:
        row = QWidget()
        row.setObjectName("card")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(10, 8, 10, 8)
        row_layout.setSpacing(8)
        label = QLabel(name)
        label.setMinimumWidth(64)
        label.setObjectName("cardTitle")
        query = QLineEdit()
        query.setPlaceholderText(f"{name} 검색어")
        query.returnPressed.connect(lambda value=url, field=query: self.open_quick_search(value, field))
        row_layout.addWidget(label)
        row_layout.addWidget(query, 1)
        return row

    def _make_custom_search_row(self, item: dict) -> QWidget:
        row = QWidget()
        row.setObjectName("card")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(10, 8, 10, 8)
        row_layout.setSpacing(8)
        label = QLabel(item.get("name", ""))
        label.setMinimumWidth(64)
        label.setObjectName("cardTitle")
        query = QLineEdit()
        query.setPlaceholderText(f"{item.get('name', '')} 검색어")
        url = item.get("url", "")
        query.returnPressed.connect(lambda value=url, field=query: self.open_quick_search(value, field))
        row_layout.addWidget(label)
        row_layout.addWidget(query, 1)
        row_layout.addWidget(make_icon_button("edit", "수정", lambda checked=False, value=item: self.edit_custom_search(value)))
        row_layout.addWidget(make_icon_button("delete", "삭제", lambda checked=False, value=item: self.delete_custom_search(value), True))
        return row

    def add_custom_search(self) -> None:
        dialog = CustomSearchDialog()
        while dialog.exec() == dialog.DialogCode.Accepted:
            value = dialog.value()
            if not value.get("name"):
                show_modern_warning(dialog, "입력 확인", "이름을 입력해주세요.")
                continue
            if not value.get("url") or "{query}" not in value.get("url", ""):
                show_modern_warning(dialog, "입력 확인", "검색 URL에 {query}를 포함해주세요.\n예: https://example.com/search?q={query}")
                continue
            value["id"] = new_id("srch")
            self.main.data.setdefault("custom_searches", []).append(value)
            self.main.save_data()
            self.build_quick_search_tab()
            return

    def edit_custom_search(self, item: dict) -> None:
        dialog = CustomSearchDialog(item)
        while dialog.exec() == dialog.DialogCode.Accepted:
            value = dialog.value()
            if not value.get("name"):
                show_modern_warning(dialog, "입력 확인", "이름을 입력해주세요.")
                continue
            if not value.get("url") or "{query}" not in value.get("url", ""):
                show_modern_warning(dialog, "입력 확인", "검색 URL에 {query}를 포함해주세요.\n예: https://example.com/search?q={query}")
                continue
            items = self.main.data.get("custom_searches", [])
            if item in items:
                items[items.index(item)] = value
            self.main.save_data()
            self.build_quick_search_tab()
            return

    def delete_custom_search(self, item: dict) -> None:
        if not confirm_delete(self, "선택한 검색 바로가기를 삭제할까요?"):
            return
        items = self.main.data.get("custom_searches", [])
        if item in items:
            items.remove(item)
        self.main.save_data()
        self.build_quick_search_tab()

    def open_quick_search(self, url_template: str, field: QLineEdit) -> None:
        query = field.text().strip()
        if not query:
            field.setFocus()
            return
        webbrowser.open(url_template.format(query=quote_plus(query)))

    def site_card_subtitle(self, item: dict) -> str:
        lines = [item.get("url", "")]
        if item.get("show_credentials_on_card"):
            username = item.get("username", "")
            password = item.get("password", "")
            if username or password:
                lines.append(f"{username} / {password}")
        return "\n".join(lines)

    def refresh(self) -> None:
        self.status_labels = {}
        site_cards = []
        file_cards = []
        source_items = self.main.data.get("launchers", [])
        items = self.sort_controls.sort_items(
            source_items,
            lambda value: value.get("name") or value.get("description") or value.get("url") or value.get("path", ""),
        )
        items = sorted(items, key=lambda value: 0 if value.get("favorite") else 1)
        q = self.search.text().strip().lower()
        site_items = []
        file_items = []
        for item in items:
            if q and q not in (item.get("name", "") + " " + item.get("url", "") + " " + item.get("path", "")).lower():
                continue
            item_type = launcher_type(item.get("type"))
            if item_type == "site":
                card = self.make_site_card(item)
                site_items.append(item)
                site_cards.append(card)
            else:
                card = make_card(item.get("name", "(이름 없음)"), short_preview(item.get("path", "")), display_hotkey(item.get("hotkey")), card_size="b")
                self.decorate_launcher_card_icon(card, item)
                self.add_launcher_actions(card, item)
                file_items.append(item)
                file_cards.append(card)
        site_callback = (lambda old, new: self.reorder_items(source_items, site_items, old, new)) if self.sort_controls.is_manual() else None
        file_callback = (lambda old, new: self.reorder_items(source_items, file_items, old, new)) if self.sort_controls.is_manual() else None
        self.site_list.add_cards(site_cards, on_reorder=site_callback)
        self.file_list.add_cards(file_cards, on_reorder=file_callback)

    def reorder_items(self, source: list[dict], visible: list[dict], old: int, new: int) -> None:
        apply_manual_reorder(source, visible, old, new)
        self.main.save_data()

    def make_launcher_icon_label(self, item: dict, size: int = 17) -> QLabel:
        label = QLabel()
        label.setFixedSize(size, size)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(f"color:#334155; background: transparent; border: 0; font-size: {max(9, size - 7)}pt; padding: 0;")
        pixmap = launcher_favicon_pixmap(item)
        if not pixmap.isNull():
            label.setPixmap(pixmap.scaled(size - 3, size - 3, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            label.setText(launcher_display_emoji(item))
        return label

    def decorate_launcher_card_icon(self, card: QWidget, item: dict) -> None:
        layout = card.layout()
        row_item = layout.itemAt(0) if layout is not None else None
        row = row_item.layout() if row_item is not None else None
        if row is not None:
            row.insertWidget(0, self.make_launcher_icon_label(item))

    def make_site_card(self, item: dict) -> QWidget:
        card = QWidget()
        card.setObjectName("card")
        card.setFixedHeight(75)
        card.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(3)

        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        favicon = QLabel()
        favicon.setFixedSize(20, 20)
        favicon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        favicon_path = resolve_image_path(item.get("favicon_path", ""), config.BASE_DIR)
        pixmap = QPixmap(favicon_path)
        if pixmap.isNull():
            favicon.setText("◇")
            favicon.setStyleSheet("color:#9CA3AF; background: transparent; border: 0;")
        else:
            favicon.setPixmap(pixmap.scaled(18, 18, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        title_row.addWidget(self.make_launcher_icon_label(item))
        title = ElidedLabel(item.get("name", "(이름 없음)"))
        title.setObjectName("cardTitle")
        title.setFixedHeight(22)
        title_row.addWidget(title, 1)

        status = QLabel("")
        status.setStyleSheet("color: #168A4A; font-weight: 700;")
        status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        status.setFixedHeight(22)
        status.setMaximumWidth(170)
        self.status_labels[item.get("id", "")] = status
        title_row.addWidget(status)

        hotkey = display_hotkey(item.get("hotkey"))
        if hotkey:
            hotkey_slot = QWidget()
            hotkey_slot.setObjectName("hotkeySlot")
            hotkey_slot.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
            hotkey_slot.setFixedSize(150, 22)
            hotkey_slot.setStyleSheet("QWidget#hotkeySlot { background: transparent; border: 0; }")
            hotkey_layout = QHBoxLayout(hotkey_slot)
            hotkey_layout.setContentsMargins(0, 0, 0, 0)
            hotkey_layout.setSpacing(0)
            hotkey_layout.addStretch(1)
            hotkey_layout.addWidget(make_hotkey_caps(hotkey))
            title_row.addWidget(hotkey_slot)
        layout.addLayout(title_row)

        body_row = QHBoxLayout()
        body_row.setContentsMargins(0, 0, 0, 0)
        body_row.setSpacing(8)
        subtitle = ElidedMultilineLabel(self.site_card_subtitle(item), max_lines=2)
        subtitle.setObjectName("cardSubtitle")
        subtitle.setFixedHeight(38)
        body_row.addWidget(subtitle, 3)

        actions = QWidget()
        actions.setObjectName("launcherCardActions")
        actions.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        actions.setStyleSheet("QWidget#launcherCardActions { background: transparent; border: 0; }")
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(4)
        actions_layout.addStretch(1)
        pin_btn = make_icon_button("pin", "즐겨찾기", lambda checked=False, value=item: self.toggle_launcher_favorite(value, pin_btn))
        self.style_launcher_favorite_button(pin_btn, item)
        actions_layout.addWidget(pin_btn)
        actions_layout.addWidget(make_icon_button("open", "열기", lambda checked=False, value=item: self.open_launcher(value)))
        actions_layout.addWidget(make_icon_button("edit", "수정", lambda checked=False, value=item: self.edit_launcher(value)))
        actions_layout.addWidget(make_icon_button("delete", "삭제", lambda checked=False, value=item: self.delete_launcher(value), True))
        body_row.addWidget(actions, 2)
        layout.addLayout(body_row)
        return card

    def add_launcher_actions(self, card: QWidget, item: dict) -> None:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        status = QLabel("")
        status.setStyleSheet("color: #168A4A; font-weight: 700;")
        status.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.status_labels[item.get("id", "")] = status
        row.addWidget(status, 1)
        pin_btn = make_icon_button("pin", "즐겨찾기", lambda checked=False, value=item: self.toggle_launcher_favorite(value, pin_btn))
        self.style_launcher_favorite_button(pin_btn, item)
        row.addWidget(pin_btn)
        row.addWidget(make_icon_button("open", "열기", lambda checked=False, value=item: self.open_launcher(value)))
        row.addWidget(make_icon_button("edit", "수정", lambda checked=False, value=item: self.edit_launcher(value)))
        row.addWidget(make_icon_button("delete", "삭제", lambda checked=False, value=item: self.delete_launcher(value), True))
        card.layout().addLayout(row)

    def toggle_launcher_favorite(self, item: dict, button=None) -> None:
        item["favorite"] = not bool(item.get("favorite"))
        if button is not None:
            self.style_launcher_favorite_button(button, item)
        QApplication.processEvents()
        QTimer.singleShot(0, self.main.save_data)
        QTimer.singleShot(1000, self.refresh)

    def persist_launcher_favorite(self) -> None:
        self.main.save_data()

    def style_launcher_favorite_button(self, button, item: dict) -> None:
        color = "#F5B301" if item.get("favorite") else "#A3A8B3"
        button.setText("★")
        button.setStyleSheet(
            f"QToolButton#iconButton {{ color: {color}; font-size: 13pt; font-weight: 900; padding: 0 0 2px 0; }}"
        )

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
        self.main.save_usage_data()

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

    def edit_launcher(self, item: dict | None = None, launcher_type_value: str = "site") -> None:
        dialog = LauncherDialog(item, launcher_type_value)
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
            self.ensure_launcher_favicon(value, item)
            items = self.main.data.setdefault("launchers", [])
            if item in items:
                items[items.index(item)] = value
            else:
                items.append(value)
            self.main.save_data()
            return

    def ensure_launcher_favicon(self, value: dict, original: dict | None = None) -> None:
        if launcher_type(value.get("type")) != "site":
            value.pop("favicon_path", None)
            return
        if launcher_icon_mode(value) != "auto":
            value.pop("favicon_path", None)
            return
        url = value.get("url", "").strip()
        if not url:
            return
        if original and original.get("url") == url and valid_favicon_path(original.get("favicon_path", "")):
            value["favicon_path"] = original.get("favicon_path")
            return
        value.pop("favicon_path", None)
        parsed = urlparse(url if "://" in url else f"https://{url}")
        domain = parsed.netloc or parsed.path.split("/")[0]
        if not domain:
            return
        base_url = f"{parsed.scheme or 'https'}://{domain}"

        def fetch() -> None:
            try:
                import requests
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                icon_dir = config.DATA_DIR / "favicons"
                icon_dir.mkdir(parents=True, exist_ok=True)
                target = icon_dir / f"{new_id('favicon')}.png"
                headers = {"User-Agent": "Mozilla/5.0 WorkHelper favicon fetcher"}
                candidates = [
                    f"https://www.google.com/s2/favicons?domain_url={base_url}&sz=64",
                    f"https://www.google.com/s2/favicons?domain={domain}&sz=64",
                    f"{base_url}/favicon.ico",
                ]
                try:
                    page = requests.get(base_url, headers=headers, timeout=6, verify=False)
                    if page.ok:
                        for href in re.findall(r"""<link[^>]+rel=["'][^"']*(?:icon|shortcut icon|apple-touch-icon)[^"']*["'][^>]+href=["']([^"']+)["']""", page.text, re.IGNORECASE):
                            candidates.append(urljoin(base_url, href))
                except Exception:
                    pass
                for api_url in candidates:
                    try:
                        response = requests.get(api_url, headers=headers, timeout=6, verify=False)
                        response.raise_for_status()
                        target.write_bytes(response.content)
                        if valid_favicon_path(str(target)):
                            break
                    except Exception:
                        continue
                if not valid_favicon_path(str(target)):
                    target.unlink(missing_ok=True)
                    return
                value["favicon_path"] = str(target.resolve().relative_to(config.BASE_DIR.resolve())).replace("\\", "/")
            except Exception:
                pass
            finally:
                self._favicon_done.emit()

        threading.Thread(target=fetch, daemon=True).start()

    def _on_favicon_ready(self) -> None:
        self.main.save_data()
        self.refresh()

    def delete_launcher(self, item: dict) -> None:
        if not confirm_delete(self, "선택한 바로가기를 삭제할까요?"):
            return
        self.main.data.get("launchers", []).remove(item)
        self.main.save_data()


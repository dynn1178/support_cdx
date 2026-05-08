from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app import config
from app.theme import THEMES
from app.update_checker import check_update_dialog
from app.utils import set_startup_enabled
from ui.common import HotkeyFields, ask_modern_question, confirm_shift_digit_hotkey, show_modern_info, show_modern_warning


THEME_LABELS = {
    "light": "밝은 테마",
    "dark": "어두운 테마",
    "blue": "블루",
    "green": "그린",
    "warm": "웜톤",
    "dark_red": "다크 레드",
    "mono": "모노",
    "mint": "민트",
    "lavender": "라벤더",
    "graphite": "그래파이트",
    "high_contrast": "고대비",
}


class SettingsTab(QWidget):
    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        self._refreshing = False
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.general_tab = QWidget()
        self.hotkey_tab = QWidget()
        self.theme_tab = QWidget()
        self.tabs.addTab(self.general_tab, "일반")
        self.tabs.addTab(self.hotkey_tab, "단축키")
        self.tabs.addTab(self.theme_tab, "테마")
        layout.addWidget(self.tabs, 1)
        self.build_general()
        self.build_hotkeys()
        self.build_theme()

        preset_buttons = QHBoxLayout()
        action_buttons = QHBoxLayout()
        save_btn = QPushButton("설정 저장")
        update_btn = QPushButton("업데이트 확인")
        export_btn = QPushButton("현재 프리셋 내보내기")
        import_btn = QPushButton("현재 프리셋 가져오기")
        reset_btn = QPushButton("현재 프리셋 초기화")
        creator_btn = QPushButton("제작자")
        save_btn.clicked.connect(self.save_settings)
        update_btn.clicked.connect(self.check_update_now)
        export_btn.clicked.connect(self.export_template)
        import_btn.clicked.connect(self.import_template)
        reset_btn.clicked.connect(self.reset_template)
        creator_btn.clicked.connect(self.show_creator)
        for button in [export_btn, import_btn, reset_btn, creator_btn, update_btn, save_btn]:
            button.setMinimumWidth(button.fontMetrics().horizontalAdvance(button.text()) + 34)
        preset_buttons.addStretch(1)
        preset_buttons.addWidget(export_btn)
        preset_buttons.addWidget(import_btn)
        preset_buttons.addWidget(reset_btn)
        action_buttons.addStretch(1)
        action_buttons.addWidget(creator_btn)
        action_buttons.addWidget(update_btn)
        action_buttons.addWidget(save_btn)
        layout.addLayout(preset_buttons)
        layout.addLayout(action_buttons)
        self._general_snapshot = {}

    def build_general(self) -> None:
        layout = QVBoxLayout(self.general_tab)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.template = QComboBox()
        self.template.currentIndexChanged.connect(self.change_template)
        self.template_name = QLineEdit()
        self.always_on_top = QCheckBox("항상 위")
        self.clipboard_limit = QSpinBox()
        self.clipboard_limit.setRange(10, 500)
        self.auto_update_check = QCheckBox("프로그램 시작 시 자동 확인")
        self.auto_update_install = QCheckBox("exe 실행 중이면 업데이트 파일 자동 교체")
        self.startup_with_windows = QCheckBox("Windows 시작 시 함께 실행")
        form.addRow("활성 프리셋", self.template)
        form.addRow("프리셋 이름", self.template_name)
        form.addRow("창 옵션", self.always_on_top)
        form.addRow("클립보드 최대 개수", self.clipboard_limit)
        form.addRow("업데이트 확인", self.auto_update_check)
        form.addRow("자동 업데이트", self.auto_update_install)
        form.addRow("시작 프로그램", self.startup_with_windows)
        layout.addLayout(form)
        layout.addStretch(1)

    def build_hotkeys(self) -> None:
        layout = QVBoxLayout(self.hotkey_tab)

        self.popup_mode_group = QButtonGroup(self)
        self.popup_mode_hotkey = QRadioButton("지정 단축키 사용")
        self.popup_mode_double_ctrl = QRadioButton("Ctrl 키 두 번 사용")
        self.popup_mode_group.addButton(self.popup_mode_hotkey, 0)
        self.popup_mode_group.addButton(self.popup_mode_double_ctrl, 1)
        self.clipboard_popup_hotkey = HotkeyFields()
        layout.addWidget(self.hotkey_group("클립보드 미니팝업", self.popup_mode_double_ctrl, self.popup_mode_hotkey, self.clipboard_popup_hotkey))

        self.memo_mode_group = QButtonGroup(self)
        self.memo_mode_hotkey = QRadioButton("지정 단축키 사용")
        self.memo_mode_double_alt = QRadioButton("Alt 키 두 번 사용")
        self.memo_mode_group.addButton(self.memo_mode_hotkey, 0)
        self.memo_mode_group.addButton(self.memo_mode_double_alt, 1)
        self.quick_memo_hotkey = HotkeyFields()
        layout.addWidget(self.hotkey_group("빠른 메모", self.memo_mode_double_alt, self.memo_mode_hotkey, self.quick_memo_hotkey))

        self.phrase_popup_hotkey = HotkeyFields()
        phrase_box = QWidget()
        phrase_box.setObjectName("card")
        phrase_layout = QFormLayout(phrase_box)
        phrase_layout.setContentsMargins(12, 10, 12, 10)
        phrase_layout.addRow("상용구 미니팝업", self.phrase_popup_hotkey)
        layout.addWidget(phrase_box)
        self.popup_mode_group.buttonToggled.connect(self.update_mode_enabled)
        self.memo_mode_group.buttonToggled.connect(self.update_mode_enabled)
        layout.addStretch(1)

    def build_theme(self) -> None:
        layout = QVBoxLayout(self.theme_tab)
        self.theme_cards: dict[str, QPushButton] = {}
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        for index, (key, theme) in enumerate(THEMES.items()):
            button = QPushButton()
            button.setCheckable(True)
            button.setMinimumSize(104, 54)
            button.setMaximumHeight(58)
            button.clicked.connect(lambda checked=False, value=key: self.select_theme(value))
            button.setStyleSheet(self.theme_card_style(theme, False))
            swatch = f"{THEME_LABELS.get(key, key)}"
            button.setText(swatch)
            self.theme_cards[key] = button
            grid.addWidget(button, index // 3, index % 3)
        layout.addLayout(grid)
        layout.addStretch(1)

    def hotkey_group(self, title: str, default_radio: QRadioButton, custom_radio: QRadioButton, fields: HotkeyFields) -> QWidget:
        box = QWidget()
        box.setObjectName("card")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        layout.addWidget(title_label)
        layout.addWidget(default_radio)
        custom_row = QHBoxLayout()
        custom_row.setContentsMargins(0, 0, 0, 0)
        custom_row.addWidget(custom_radio)
        custom_row.addWidget(fields, 1)
        layout.addLayout(custom_row)
        return box

    def theme_card_style(self, theme: dict, checked: bool) -> str:
        border = theme.get("accent", "#3B6CF5") if checked else theme.get("border", "#B9C0CC")
        return (
            "QPushButton {"
            f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {theme.get('panel')}, stop:.48 {theme.get('content')}, stop:.49 {theme.get('accent')}, stop:1 {theme.get('bg')});"
            f"color: {theme.get('text')}; border: {'2' if checked else '1'}px solid {border}; border-radius: 7px; font-weight: 800; padding-top: 24px;"
            "}"
        )

    def select_theme(self, key: str) -> None:
        self.main.settings["theme"] = key
        for name, button in self.theme_cards.items():
            button.setChecked(name == key)
            button.setStyleSheet(self.theme_card_style(THEMES[name], name == key))

    def update_mode_enabled(self, *_args) -> None:
        self.clipboard_popup_hotkey.setEnabled(self.popup_mode_hotkey.isChecked())
        self.quick_memo_hotkey.setEnabled(self.memo_mode_hotkey.isChecked())

    def refresh_template_combo(self) -> None:
        self.template.blockSignals(True)
        self.template.clear()
        for index in range(1, config.TEMPLATE_COUNT + 1):
            try:
                data = config.load_template(index)
                name = data.get("meta", {}).get("preset_name") or data.get("meta", {}).get("template_name") or f"프리셋 {index}"
            except Exception:
                name = f"프리셋 {index}"
            self.template.addItem(f"{index}. {name}")
        self.template.setCurrentIndex(self.main.template_index - 1)
        self.template.blockSignals(False)

    def change_template(self, index: int) -> None:
        if self._refreshing:
            return
        self.main.change_template(index + 1)

    def refresh(self) -> None:
        self._refreshing = True
        settings = self.main.settings
        self.refresh_template_combo()
        self.template_name.setText(self.main.data.get("meta", {}).get("preset_name", f"프리셋 {self.main.template_index}"))
        self.select_theme(settings.get("theme", "light"))
        self.always_on_top.setChecked(bool(settings.get("window", {}).get("always_on_top", False)))
        self.clipboard_limit.setValue(int(settings.get("clipboard_history_limit", 50)))
        self.auto_update_check.setChecked(bool(settings.get("auto_update_check", False)))
        self.auto_update_install.setChecked(bool(settings.get("auto_update_install", False)))
        self.startup_with_windows.setChecked(bool(settings.get("startup_with_windows", False)))
        self.clipboard_popup_hotkey.set_hotkey(settings.get("clipboard_popup_hotkey"))
        self.quick_memo_hotkey.set_hotkey(settings.get("quick_memo_hotkey"))
        self.phrase_popup_hotkey.set_hotkey(settings.get("phrase_popup_hotkey"))
        self.popup_mode_double_ctrl.setChecked(bool(settings.get("clipboard_popup_double_ctrl", True)))
        self.popup_mode_hotkey.setChecked(not self.popup_mode_double_ctrl.isChecked())
        self.memo_mode_double_alt.setChecked(bool(settings.get("quick_memo_double_alt", True)))
        self.memo_mode_hotkey.setChecked(not self.memo_mode_double_alt.isChecked())
        self.update_mode_enabled()
        self._general_snapshot = self.current_general_state()
        self._refreshing = False

    def current_general_state(self) -> dict:
        return {
            "template_name": self.template_name.text().strip(),
            "always_on_top": self.always_on_top.isChecked(),
            "clipboard_limit": self.clipboard_limit.value(),
            "auto_update_check": self.auto_update_check.isChecked(),
            "auto_update_install": self.auto_update_install.isChecked(),
            "startup_with_windows": self.startup_with_windows.isChecked(),
        }

    def is_dirty(self) -> bool:
        if self._refreshing:
            return False
        return self.current_general_state() != getattr(self, "_general_snapshot", {})

    def save_settings(self) -> None:
        settings = self.main.settings
        window = settings.setdefault("window", {"width": 900, "height": 580, "always_on_top": False})
        self.main.data.setdefault("meta", {})["preset_name"] = self.template_name.text().strip() or f"프리셋 {self.main.template_index}"
        settings["clipboard_history_limit"] = self.clipboard_limit.value()
        settings["clipboard_popup_hotkey"] = self.clipboard_popup_hotkey.value()
        settings["clipboard_popup_double_ctrl"] = self.popup_mode_double_ctrl.isChecked()
        settings["quick_memo_hotkey"] = self.quick_memo_hotkey.value()
        settings["quick_memo_double_alt"] = self.memo_mode_double_alt.isChecked()
        settings["phrase_popup_hotkey"] = self.phrase_popup_hotkey.value()
        settings["auto_update_check"] = self.auto_update_check.isChecked()
        settings["auto_update_install"] = self.auto_update_install.isChecked()
        settings["startup_with_windows"] = self.startup_with_windows.isChecked()
        settings["active_preset"] = self.main.template_index
        window["always_on_top"] = self.always_on_top.isChecked()
        conflict = self.main.first_hotkey_conflict()
        if conflict:
            show_modern_warning(self, "단축키 충돌", conflict)
            return
        for hotkey in [settings.get("clipboard_popup_hotkey"), settings.get("quick_memo_hotkey"), settings.get("phrase_popup_hotkey")]:
            if not confirm_shift_digit_hotkey(self, hotkey):
                return
        try:
            set_startup_enabled(self.startup_with_windows.isChecked())
        except Exception as exc:
            show_modern_warning(self, "시작 프로그램 설정 실패", str(exc))
            return
        self.main.apply_current_settings()
        self.main.save_data()
        self.refresh_template_combo()
        self._general_snapshot = self.current_general_state()
        self.main.set_tab(self.main.stack.currentIndex())
        self.main.show()

    def show_creator(self) -> None:
        show_modern_info(self, "제작자", "6PM Assistant\n문의: dynn1178@naver.com")

    def check_update_now(self) -> None:
        check_update_dialog(
            self,
            self.main.version,
            repo=config.GITHUB_REPO,
            auto_install=self.auto_update_install.isChecked(),
            silent_no_update=False,
        )

    def export_template(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "현재 프리셋 내보내기", f"preset_{self.main.template_index}.json", "JSON (*.json)")
        if not path:
            return
        try:
            config.export_template(self.main.template_index, path)
            show_modern_info(self, "완료", "현재 프리셋을 내보냈습니다.")
        except Exception as exc:
            show_modern_warning(self, "내보내기 실패", str(exc))

    def import_template(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "현재 프리셋 가져오기", "", "JSON (*.json)")
        if not path:
            return
        try:
            config.import_template(path, self.main.template_index)
            self.main.data = config.load_template(self.main.template_index)
            self.main.data["settings"] = self.main.settings
            self.main.register_hotkeys()
            self.main.refresh_all_tabs()
            show_modern_info(self, "완료", "현재 프리셋으로 가져왔습니다.")
        except Exception as exc:
            show_modern_warning(self, "가져오기 실패", str(exc))

    def reset_template(self) -> None:
        if not ask_modern_question(self, "프리셋 초기화", "현재 프리셋에 등록된 항목을 기본값으로 초기화할까요?", None, "초기화", "취소"):
            return
        config.save_template(self.main.template_index, config.default_template(self.main.template_index))
        self.main.data = config.load_template(self.main.template_index)
        self.main.data["settings"] = self.main.settings
        self.main.register_hotkeys()
        self.main.refresh_all_tabs()
        self.refresh_template_combo()
        show_modern_info(self, "완료", "현재 프리셋을 초기화했습니다.")

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app import config
from app.theme import THEMES
from app.update_checker import check_update_dialog
from app.utils import is_startup_enabled, set_startup_enabled
from ui.common import HotkeyFields, confirm_shift_digit_hotkey


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
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)

        self.template = QComboBox()
        self.template.currentIndexChanged.connect(self.change_template)
        self.template_name = QLineEdit()
        self.theme = QComboBox()
        for key in THEMES:
            self.theme.addItem(THEME_LABELS.get(key, key), key)
        self.always_on_top = QCheckBox("항상 위")
        self.clipboard_limit = QSpinBox()
        self.clipboard_limit.setRange(10, 500)
        self.auto_update_check = QCheckBox("프로그램 시작 시 자동 확인")
        self.auto_update_install = QCheckBox("exe 실행 중이면 업데이트 파일 자동 교체")
        self.startup_with_windows = QCheckBox("Windows 시작 시 함께 실행")

        self.popup_mode_group = QButtonGroup(self)
        self.popup_mode_hotkey = QRadioButton("지정 단축키 사용")
        self.popup_mode_double_ctrl = QRadioButton("Ctrl 키 두 번 사용")
        self.popup_mode_group.addButton(self.popup_mode_hotkey, 0)
        self.popup_mode_group.addButton(self.popup_mode_double_ctrl, 1)
        self.clipboard_popup_hotkey = HotkeyFields()
        popup_mode = QWidget()
        popup_mode.setMinimumHeight(66)
        popup_mode_layout = QVBoxLayout(popup_mode)
        popup_mode_layout.setContentsMargins(0, 2, 0, 2)
        popup_mode_layout.setSpacing(8)
        hotkey_row = QHBoxLayout()
        hotkey_row.setContentsMargins(0, 0, 0, 0)
        hotkey_row.addWidget(self.popup_mode_hotkey)
        hotkey_row.addWidget(self.clipboard_popup_hotkey, 1)
        popup_mode_layout.addLayout(hotkey_row)
        popup_mode_layout.addWidget(self.popup_mode_double_ctrl)
        self.popup_mode_group.buttonToggled.connect(self.update_popup_mode_enabled)

        form.addRow("활성 프리셋", self.template)
        form.addRow("프리셋 이름", self.template_name)
        form.addRow("테마", self.theme)
        form.addRow("창 옵션", self.always_on_top)
        form.addRow("클립보드 최대 개수", self.clipboard_limit)
        form.addRow("클립보드 미니팝업", popup_mode)
        form.addRow("업데이트 확인", self.auto_update_check)
        form.addRow("자동 업데이트", self.auto_update_install)
        form.addRow("시작 프로그램", self.startup_with_windows)
        layout.addLayout(form)
        layout.addStretch(1)

        buttons = QHBoxLayout()
        save_btn = QPushButton("설정 저장")
        update_btn = QPushButton("업데이트 확인")
        export_btn = QPushButton("현재 프리셋 내보내기")
        import_btn = QPushButton("현재 프리셋 가져오기")
        creator_btn = QPushButton("제작자")
        save_btn.clicked.connect(self.save_settings)
        update_btn.clicked.connect(self.check_update_now)
        export_btn.clicked.connect(self.export_template)
        import_btn.clicked.connect(self.import_template)
        creator_btn.clicked.connect(self.show_creator)
        buttons.addStretch(1)
        buttons.addWidget(update_btn)
        buttons.addWidget(save_btn)
        buttons.addWidget(export_btn)
        buttons.addWidget(import_btn)
        buttons.addWidget(creator_btn)
        layout.addLayout(buttons)
        self._refreshing = False

    def update_popup_mode_enabled(self, *_args) -> None:
        self.clipboard_popup_hotkey.setEnabled(self.popup_mode_hotkey.isChecked())

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
        theme_index = self.theme.findData(settings.get("theme", "light"))
        self.theme.setCurrentIndex(max(theme_index, 0))
        self.always_on_top.setChecked(bool(settings.get("window", {}).get("always_on_top", False)))
        self.clipboard_limit.setValue(int(settings.get("clipboard_history_limit", 50)))
        self.auto_update_check.setChecked(bool(settings.get("auto_update_check", False)))
        self.auto_update_install.setChecked(bool(settings.get("auto_update_install", False)))
        self.startup_with_windows.setChecked(is_startup_enabled())
        self.clipboard_popup_hotkey.set_hotkey(settings.get("clipboard_popup_hotkey"))
        if settings.get("clipboard_popup_double_ctrl", True):
            self.popup_mode_double_ctrl.setChecked(True)
        else:
            self.popup_mode_hotkey.setChecked(True)
        self.update_popup_mode_enabled()
        self._refreshing = False

    def save_settings(self) -> None:
        settings = self.main.settings
        window = settings.setdefault("window", {"width": 900, "height": 580, "always_on_top": False})
        self.main.data.setdefault("meta", {})["preset_name"] = self.template_name.text().strip() or f"프리셋 {self.main.template_index}"
        settings["theme"] = self.theme.currentData()
        settings["clipboard_history_limit"] = self.clipboard_limit.value()
        settings["clipboard_popup_hotkey"] = self.clipboard_popup_hotkey.value()
        settings["clipboard_popup_double_ctrl"] = self.popup_mode_double_ctrl.isChecked()
        settings["auto_update_check"] = self.auto_update_check.isChecked()
        settings["auto_update_install"] = self.auto_update_install.isChecked()
        settings["startup_with_windows"] = self.startup_with_windows.isChecked()
        settings["active_preset"] = self.main.template_index
        window["always_on_top"] = self.always_on_top.isChecked()
        conflict = self.main.first_hotkey_conflict()
        if conflict:
            QMessageBox.warning(self, "단축키 충돌", conflict)
            return
        if not confirm_shift_digit_hotkey(self, settings.get("clipboard_popup_hotkey")):
            return
        try:
            set_startup_enabled(self.startup_with_windows.isChecked())
        except Exception as exc:
            QMessageBox.warning(self, "시작 프로그램 설정 실패", str(exc))
            return
        self.main.apply_current_settings()
        self.main.save_data()
        self.refresh_template_combo()
        self.main.show()

    def show_creator(self) -> None:
        QMessageBox.information(self, "제작자", "문의: dynn1178@naver.com")

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
            QMessageBox.information(self, "완료", "현재 활성 프리셋을 내보냈습니다.")
        except Exception as exc:
            QMessageBox.warning(self, "내보내기 실패", str(exc))

    def import_template(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "현재 프리셋 가져오기", "", "JSON (*.json)")
        if not path:
            return
        try:
            config.import_template(path, self.main.template_index)
            self.main.change_template(self.main.template_index)
            QMessageBox.information(self, "완료", "현재 활성 프리셋으로 가져왔습니다.")
        except Exception as exc:
            QMessageBox.warning(self, "가져오기 실패", str(exc))

from __future__ import annotations

import re
import webbrowser

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app import config
from app.theme import THEMES
from app.update_checker import check_update_dialog
from app.utils import resolve_image_path, set_startup_enabled
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
        layout.setContentsMargins(0, 0, 0, 0)
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
        preset_buttons.setContentsMargins(10, 4, 10, 0)
        action_buttons = QHBoxLayout()
        action_buttons.setContentsMargins(10, 4, 10, 8)
        save_btn = QPushButton("설정 저장")
        update_btn = QPushButton("업데이트 확인")
        export_btn = QPushButton("현재 프리셋 내보내기")
        import_btn = QPushButton("현재 프리셋 가져오기")
        reset_btn = QPushButton("현재 프리셋 초기화")
        creator_btn = QPushButton("문의 및 홈페이지")
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
        self.auto_update_install = QCheckBox("업데이트 동의 시 앱에서 바로 설치")
        self.auto_update_install.setEnabled(False)
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
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

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
        self.steel_cut_hotkey = HotkeyFields()
        phrase_layout.addRow("스틸 컷", self.steel_cut_hotkey)
        self.steel_cut_capture_mode_group = QButtonGroup(self)
        self.steel_cut_capture_mode_widget = QWidget()
        mode_layout = QVBoxLayout(self.steel_cut_capture_mode_widget)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.setSpacing(6)
        self.steel_cut_mode_radios: dict[str, QRadioButton] = {}
        for key, label in [
            ("region", "드래그 선택영역 캡처"),
            ("full", "전체 캡처"),
            ("window", "선택창 캡처"),
            ("fixed", "특정 사이즈 고정 캡처"),
        ]:
            radio = QRadioButton(label)
            self.steel_cut_mode_radios[key] = radio
            self.steel_cut_capture_mode_group.addButton(radio)
            mode_layout.addWidget(radio)
        phrase_layout.addRow("스틸 컷 캡처 방식", self.steel_cut_capture_mode)
        fixed_size_row = QHBoxLayout()
        self.steel_cut_fixed_width = QSpinBox()
        self.steel_cut_fixed_width.setRange(50, 8000)
        self.steel_cut_fixed_width.setSuffix(" px")
        self.steel_cut_fixed_height = QSpinBox()
        self.steel_cut_fixed_height.setRange(50, 8000)
        self.steel_cut_fixed_height.setSuffix(" px")
        fixed_size_row.addWidget(self.steel_cut_fixed_width)
        fixed_size_row.addWidget(QLabel("x"))
        fixed_size_row.addWidget(self.steel_cut_fixed_height)
        phrase_layout.addRow("고정 캡처 크기", fixed_size_row)
        layout.addWidget(phrase_box)
        phrase_box.hide()

        phrase_card = QWidget()
        phrase_card.setObjectName("card")
        phrase_card.setMinimumHeight(92)
        phrase_card_layout = QFormLayout(phrase_card)
        phrase_card_layout.setContentsMargins(14, 14, 14, 14)
        phrase_card_layout.setVerticalSpacing(10)
        phrase_title = QLabel("상용구 미니팝업")
        phrase_title.setObjectName("cardTitle")
        phrase_card_layout.addRow(phrase_title)
        phrase_card_layout.addRow("단축키", self.phrase_popup_hotkey)
        layout.addWidget(phrase_card)

        steel_card = QWidget()
        steel_card.setObjectName("card")
        steel_card.setMinimumHeight(190)
        steel_card_layout = QFormLayout(steel_card)
        steel_card_layout.setContentsMargins(14, 14, 14, 14)
        steel_card_layout.setVerticalSpacing(14)
        steel_card_layout.setHorizontalSpacing(16)
        steel_title = QLabel("스틸 컷")
        steel_title.setObjectName("cardTitle")
        steel_card_layout.addRow(steel_title)
        steel_card_layout.addRow("단축키", self.steel_cut_hotkey)
        steel_card_layout.addRow("캡처 방식", self.steel_cut_capture_mode)
        fixed_size_row.setSpacing(10)
        self.steel_cut_fixed_width.setMinimumWidth(150)
        self.steel_cut_fixed_height.setMinimumWidth(150)
        fixed_size_row.addStretch(1)
        steel_card_layout.addRow("고정 캡처 크기", fixed_size_row)
        layout.addWidget(steel_card)
        steel_card.hide()

        steel_hotkey_card = QWidget()
        steel_hotkey_card.setObjectName("card")
        steel_hotkey_card.setMinimumHeight(92)
        steel_hotkey_layout = QFormLayout(steel_hotkey_card)
        steel_hotkey_layout.setContentsMargins(14, 14, 14, 14)
        steel_hotkey_title = QLabel("스틸 컷 단축키")
        steel_hotkey_title.setObjectName("cardTitle")
        steel_hotkey_layout.addRow(steel_hotkey_title)
        steel_hotkey_layout.addRow("단축키", self.steel_cut_hotkey)
        layout.addWidget(steel_hotkey_card)

        steel_mode_card = QWidget()
        steel_mode_card.setObjectName("card")
        steel_mode_card.setMinimumHeight(92)
        steel_mode_layout = QFormLayout(steel_mode_card)
        steel_mode_layout.setContentsMargins(14, 14, 14, 14)
        steel_mode_title = QLabel("스틸 컷 캡처 방식")
        steel_mode_title.setObjectName("cardTitle")
        steel_mode_layout.addRow(steel_mode_title)
        steel_mode_layout.addRow("방식", self.steel_cut_capture_mode)
        layout.addWidget(steel_mode_card)

        steel_size_card = QWidget()
        steel_size_card.setObjectName("card")
        steel_size_card.setMinimumHeight(98)
        steel_size_layout = QFormLayout(steel_size_card)
        steel_size_layout.setContentsMargins(14, 14, 14, 14)
        steel_size_title = QLabel("고정 캡처 크기")
        steel_size_title.setObjectName("cardTitle")
        steel_size_layout.addRow(steel_size_title)
        steel_size_layout.addRow("크기", fixed_size_row)
        layout.addWidget(steel_size_card)
        self.popup_mode_group.buttonToggled.connect(self.update_mode_enabled)
        self.memo_mode_group.buttonToggled.connect(self.update_mode_enabled)
        layout.addStretch(1)

    def build_hotkeys(self) -> None:
        root = QVBoxLayout(self.hotkey_tab)
        root.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        content.setStyleSheet("QComboBox, QSpinBox { padding: 3px 8px; min-height: 16px; }")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        self.popup_mode_group = QButtonGroup(self)
        self.popup_mode_hotkey = QRadioButton("지정 단축키 사용")
        self.popup_mode_double_ctrl = QRadioButton("Ctrl 두 번 사용")
        self.popup_mode_group.addButton(self.popup_mode_hotkey, 0)
        self.popup_mode_group.addButton(self.popup_mode_double_ctrl, 1)
        self.clipboard_popup_hotkey = HotkeyFields()
        self.clipboard_popup_hotkey.setFixedHeight(28)
        layout.addWidget(self.hotkey_group("클립보드 미니팝업", self.popup_mode_double_ctrl, self.popup_mode_hotkey, self.clipboard_popup_hotkey))

        self.memo_mode_group = QButtonGroup(self)
        self.memo_mode_hotkey = QRadioButton("지정 단축키 사용")
        self.memo_mode_double_alt = QRadioButton("Alt 두 번 사용")
        self.memo_mode_group.addButton(self.memo_mode_hotkey, 0)
        self.memo_mode_group.addButton(self.memo_mode_double_alt, 1)
        self.quick_memo_hotkey = HotkeyFields()
        self.quick_memo_hotkey.setFixedHeight(28)
        layout.addWidget(self.hotkey_group("빠른 메모", self.memo_mode_double_alt, self.memo_mode_hotkey, self.quick_memo_hotkey))

        self.phrase_popup_hotkey = HotkeyFields()
        self.phrase_popup_hotkey.setFixedHeight(28)
        layout.addWidget(self.single_hotkey_group("상용구 미니팝업", "단축키", self.phrase_popup_hotkey))

        self.steel_cut_hotkey = HotkeyFields()
        self.steel_cut_hotkey.setFixedHeight(28)
        self.steel_cut_capture_mode_group = QButtonGroup(self)
        self.steel_cut_capture_mode_widget = QWidget()
        self.steel_cut_capture_mode_widget.setObjectName("captureModeRow")
        mode_layout = QHBoxLayout(self.steel_cut_capture_mode_widget)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.setSpacing(16)
        self.steel_cut_mode_radios: dict[str, QRadioButton] = {}
        for key, label in [
            ("region", "드래그"),
            ("full", "전체 화면"),
            ("window", "선택 창"),
            ("fixed", "고정 크기"),
        ]:
            radio = QRadioButton(label)
            self.steel_cut_mode_radios[key] = radio
            self.steel_cut_capture_mode_group.addButton(radio)
            mode_layout.addWidget(radio)
        mode_layout.addStretch(1)
        self.steel_cut_fixed_width = QSpinBox()
        self.steel_cut_fixed_width.setRange(50, 8000)
        self.steel_cut_fixed_width.setSuffix(" px")
        self.steel_cut_fixed_width.setMinimumWidth(150)
        self.steel_cut_fixed_height = QSpinBox()
        self.steel_cut_fixed_height.setRange(50, 8000)
        self.steel_cut_fixed_height.setSuffix(" px")
        self.steel_cut_fixed_height.setMinimumWidth(150)

        self.screen_draw_hotkey = HotkeyFields()
        self.screen_draw_hotkey.setFixedHeight(28)

        steel_box = QWidget()
        steel_box.setObjectName("card")
        steel_box.setMinimumHeight(178)
        steel_layout = QFormLayout(steel_box)
        steel_layout.setContentsMargins(14, 14, 14, 14)
        steel_layout.setVerticalSpacing(12)
        title = QLabel("캡처 도구")
        title.setObjectName("cardTitle")
        steel_layout.addRow(title)
        steel_layout.addRow("캡처 단축키", self.steel_cut_hotkey)
        steel_layout.addRow("캡처 방식", self.steel_cut_capture_mode_widget)
        fixed_size_row = QHBoxLayout()
        fixed_size_row.setSpacing(10)
        fixed_size_row.addWidget(self.steel_cut_fixed_width)
        fixed_size_row.addWidget(QLabel("x"))
        fixed_size_row.addWidget(self.steel_cut_fixed_height)
        fixed_size_row.addStretch(1)
        steel_layout.addRow("고정 캡처 크기", fixed_size_row)
        layout.addWidget(steel_box)

        layout.addWidget(self.single_hotkey_group("화면그리기", "단축키", self.screen_draw_hotkey))

        self.popup_mode_group.buttonToggled.connect(self.update_mode_enabled)
        self.memo_mode_group.buttonToggled.connect(self.update_mode_enabled)
        self.steel_cut_capture_mode_group.buttonToggled.connect(self.update_mode_enabled)
        layout.addStretch(1)

    def single_hotkey_group(self, title: str, label: str, fields: HotkeyFields) -> QWidget:
        box = QWidget()
        box.setObjectName("card")
        box.setMinimumHeight(92)
        layout = QFormLayout(box)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setVerticalSpacing(10)
        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        layout.addRow(title_label)
        layout.addRow(label, fields)
        return box

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
        mode_row = QHBoxLayout()
        mode_row.setContentsMargins(0, 0, 0, 0)
        mode_row.setSpacing(16)
        mode_row.addWidget(default_radio)
        mode_row.addWidget(custom_radio)
        mode_row.addWidget(fields, 1)
        layout.addLayout(mode_row)
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

    def selected_steel_cut_capture_mode(self) -> str:
        for key, radio in getattr(self, "steel_cut_mode_radios", {}).items():
            if radio.isChecked():
                return key
        return "region"

    def set_steel_cut_capture_mode(self, mode: str) -> None:
        radios = getattr(self, "steel_cut_mode_radios", {})
        radio = radios.get(mode) or radios.get("region")
        if radio is not None:
            radio.setChecked(True)

    def update_mode_enabled(self, *_args) -> None:
        self.clipboard_popup_hotkey.setEnabled(self.popup_mode_hotkey.isChecked())
        self.quick_memo_hotkey.setEnabled(self.memo_mode_hotkey.isChecked())
        fixed_enabled = self.selected_steel_cut_capture_mode() == "fixed"
        self.steel_cut_fixed_width.setEnabled(fixed_enabled)
        self.steel_cut_fixed_height.setEnabled(fixed_enabled)

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
        self.auto_update_install.setChecked(True)
        self.startup_with_windows.setChecked(bool(settings.get("startup_with_windows", False)))
        self.clipboard_popup_hotkey.set_hotkey(settings.get("clipboard_popup_hotkey"))
        self.quick_memo_hotkey.set_hotkey(settings.get("quick_memo_hotkey"))
        self.phrase_popup_hotkey.set_hotkey(settings.get("phrase_popup_hotkey"))
        self.steel_cut_hotkey.set_hotkey(settings.get("steel_cut_hotkey"))
        self.screen_draw_hotkey.set_hotkey(settings.get("screen_draw_hotkey"))
        mode = settings.get("steel_cut_capture_mode", "region")
        self.set_steel_cut_capture_mode(mode)
        self.steel_cut_fixed_width.setValue(int(settings.get("steel_cut_fixed_width", 800) or 800))
        self.steel_cut_fixed_height.setValue(int(settings.get("steel_cut_fixed_height", 450) or 450))
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
            "auto_update_install": True,
            "startup_with_windows": self.startup_with_windows.isChecked(),
            "steel_cut_capture_mode": self.selected_steel_cut_capture_mode() if hasattr(self, "steel_cut_mode_radios") else "region",
            "steel_cut_fixed_width": self.steel_cut_fixed_width.value() if hasattr(self, "steel_cut_fixed_width") else 800,
            "steel_cut_fixed_height": self.steel_cut_fixed_height.value() if hasattr(self, "steel_cut_fixed_height") else 450,
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
        settings["steel_cut_hotkey"] = self.steel_cut_hotkey.value()
        settings["steel_cut_capture_mode"] = self.selected_steel_cut_capture_mode()
        settings["steel_cut_fixed_width"] = self.steel_cut_fixed_width.value()
        settings["steel_cut_fixed_height"] = self.steel_cut_fixed_height.value()
        settings["screen_draw_hotkey"] = self.screen_draw_hotkey.value()
        settings["auto_update_check"] = self.auto_update_check.isChecked()
        settings["auto_update_install"] = True
        settings["startup_with_windows"] = self.startup_with_windows.isChecked()
        settings["active_preset"] = self.main.template_index
        window["always_on_top"] = self.always_on_top.isChecked()
        conflict = self.main.first_hotkey_conflict()
        if conflict:
            show_modern_warning(self, "단축키 충돌", conflict)
            return
        for hotkey in [
            settings.get("clipboard_popup_hotkey"),
            settings.get("quick_memo_hotkey"),
            settings.get("phrase_popup_hotkey"),
            settings.get("steel_cut_hotkey"),
            settings.get("screen_draw_hotkey"),
        ]:
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
        from ui.common import dialog_palette
        HOMEPAGE = "https://6pma.vercel.app/"
        dlg = QDialog(self)
        dlg.setWindowTitle("제작자")
        dlg.setModal(True)
        dlg.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        colors = dialog_palette(self)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(22, 20, 22, 16)
        layout.setSpacing(10)
        title_lbl = QLabel("제작자")
        title_lbl.setObjectName("modernDialogTitle")
        info_lbl = QLabel("6PM Assistant\n문의: dynn1178@naver.com")
        info_lbl.setWordWrap(True)
        url_lbl = QLabel(f'<a href="{HOMEPAGE}" style="color:{colors["accent"]}">{HOMEPAGE}</a>')
        url_lbl.setOpenExternalLinks(True)
        url_lbl.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        layout.addWidget(title_lbl)
        layout.addWidget(info_lbl)
        layout.addWidget(url_lbl)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        open_btn = QToolButton()
        open_btn.setText("홈페이지 열기")
        open_btn.setFixedHeight(32)
        open_btn.clicked.connect(lambda: webbrowser.open(HOMEPAGE))
        close_btn = QToolButton()
        close_btn.setText("확인")
        close_btn.setFixedHeight(32)
        close_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(open_btn)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
        dlg.setStyleSheet(
            f"""
            QDialog {{ background: {colors["panel"]}; border: 1px solid {colors["border"]}; border-radius: 10px; }}
            QLabel {{ color: {colors["text"]}; }}
            QLabel#modernDialogTitle {{ color: {colors["accent"]}; font-size: 14pt; font-weight: 900; }}
            QToolButton {{ background: {colors["accent"]}; color: white; border: 0; border-radius: 6px; padding: 0 16px; font-weight: 800; }}
            """
        )
        dlg.resize(360, 200)
        dlg.exec()

    def check_update_now(self) -> None:
        check_update_dialog(
            self,
            self.main.version,
            repo=config.GITHUB_REPO,
            auto_install=self.auto_update_install.isChecked(),
            silent_no_update=False,
        )

    def export_template(self) -> None:
        preset_name = self.main.data.get("meta", {}).get("preset_name", f"프리셋 {self.main.template_index}")
        safe_name = re.sub(r'[\\/:*?"<>|]', "", preset_name).strip()
        default_filename = f"preset_{self.main.template_index}_{safe_name}.json" if safe_name else f"preset_{self.main.template_index}.json"
        path, _ = QFileDialog.getSaveFileName(self, "현재 프리셋 내보내기", default_filename, "JSON (*.json)")
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
            self.refresh_template_combo()
            imported_name = self.main.data.get("meta", {}).get("preset_name", "")
            msg = f'"{imported_name}" 프리셋을 가져왔습니다.' if imported_name else "현재 프리셋으로 가져왔습니다."
            show_modern_info(self, "완료", msg)
        except Exception as exc:
            show_modern_warning(self, "가져오기 실패", str(exc))

    def reset_template(self) -> None:
        if not ask_modern_question(self, "프리셋 초기화", "현재 프리셋에 등록된 항목을 기본값으로 초기화할까요?", None, "초기화", "취소"):
            return
        # 스틸컷 이미지 파일 삭제
        for item in self.main.data.get("steel_cuts", []):
            try:
                from pathlib import Path
                path = Path(resolve_image_path(item.get("path", ""), config.BASE_DIR))
                if path.exists() and config.BASE_DIR.resolve() in path.resolve().parents:
                    path.unlink(missing_ok=True)
            except Exception:
                pass
        # 템플릿 항목 초기화 (상용구·바로가기·매크로 등 + 홈 화면 사용이력)
        config.save_template(self.main.template_index, config.default_template(self.main.template_index))
        self.main.data = config.load_template(self.main.template_index)
        self.main.data["settings"] = self.main.settings
        # 색상 최근 사용이력 초기화
        self.main.settings["color_history"] = []
        # 이모지 최근 사용이력 초기화
        self.main.settings["emoji_usage"] = {}
        self.main.settings["recent_emojis"] = []
        # 특수문자 최근 사용이력 초기화
        self.main.settings["special_char_usage"] = {}
        self.main.settings["phrase_popup_hotkey"] = {"modifiers": ["ctrl"], "key": ";"}
        self.main.settings["steel_cut_hotkey"] = {"modifiers": ["ctrl", "shift"], "key": "S"}
        self.main.settings["steel_cut_capture_mode"] = "region"
        config.save_settings(self.main.settings)
        # 클립보드 이력 초기화 (메모리 + 디스크)
        for tab in self.main.tabs:
            if hasattr(tab, "history"):
                tab.history["history"] = []
                break
        config.save_clipboard_history({"history": []})
        # 클립보드 이미지 파일 삭제
        if config.CLIPBOARD_IMAGE_DIR.exists():
            for img_path in config.CLIPBOARD_IMAGE_DIR.glob("*.png"):
                try:
                    img_path.unlink(missing_ok=True)
                except Exception:
                    pass
        self.main.register_hotkeys()
        self.main.refresh_all_tabs()
        self.refresh_template_combo()
        show_modern_info(self, "완료", "현재 프리셋을 초기화했습니다.")

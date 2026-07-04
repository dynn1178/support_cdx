from __future__ import annotations

import re
import webbrowser
from datetime import datetime

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication,
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
    QSlider,
    QSpinBox,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app import config
from app.screen_utils import signature_for_monitor_index
from app.theme import THEMES
from app.update_checker import check_update_dialog
from app.utils import display_hotkey, is_startup_enabled, resolve_image_path, set_startup_enabled
from ui.common import HotkeyFields, ask_modern_question, bottom_action_bar, confirm_shift_digit_hotkey, show_modern_info, show_modern_warning
from ui.floating_widget import CATEGORY_ORDER


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
    FIELD_MAX_WIDTH = 340  # 드롭다운·슬라이더 최대 너비 (카드 폭의 ~50%)

    def __init__(self, main) -> None:
        super().__init__()
        self.main = main
        self._refreshing = False
        self._widget_slider_holders: list[QWidget] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        self.general_tab = QWidget()
        self.hotkey_tab = QWidget()
        self.theme_tab = QWidget()
        self.widget_tab = QWidget()
        self.tabs.addTab(self.general_tab, "일반")
        self.tabs.addTab(self.hotkey_tab, "단축키")
        self.tabs.addTab(self.theme_tab, "테마")
        self.tabs.addTab(self.widget_tab, "위젯")
        layout.addWidget(self.tabs, 1)
        self.build_general()
        self.build_hotkeys()
        self.build_theme()
        self.build_widget()

        save_btn = QPushButton("설정 저장")
        update_btn = QPushButton("업데이트 확인")
        export_btn = QPushButton("내보내기")
        import_btn = QPushButton("가져오기")
        reset_btn = QPushButton("초기화")
        creator_btn = QPushButton("문의 및 홈페이지")
        save_btn.clicked.connect(self.save_settings)
        update_btn.clicked.connect(self.check_update_now)
        export_btn.clicked.connect(self.export_template)
        import_btn.clicked.connect(self.import_template)
        reset_btn.clicked.connect(self.reset_template)
        creator_btn.clicked.connect(self.show_creator)
        for button in [export_btn, import_btn, reset_btn, creator_btn, update_btn, save_btn]:
            button.setMinimumWidth(button.fontMetrics().horizontalAdvance(button.text()) + 34)
        layout.addLayout(bottom_action_bar(export_btn, import_btn, reset_btn, creator_btn, update_btn, save_btn))
        self._general_snapshot = {}
        self._settings_snapshot = {}

    def build_general(self) -> None:
        layout = QVBoxLayout(self.general_tab)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.template = QComboBox()
        self.template.setMaximumWidth(self.FIELD_MAX_WIDTH)
        self.template.currentIndexChanged.connect(self.change_template)
        self.template_name = QLineEdit()
        self.template_name.setMaximumWidth(self.FIELD_MAX_WIDTH)
        self.always_on_top = QCheckBox("항상 위")
        self.clipboard_limit = QSpinBox()
        self.clipboard_limit.setRange(10, 500)
        self.clipboard_limit.setMaximumWidth(self.FIELD_MAX_WIDTH)
        self.auto_update_check = QCheckBox("프로그램 시작 시 자동 확인")
        self.auto_update_install = QCheckBox("업데이트 동의 시 앱에서 바로 설치")
        self.auto_update_install.setEnabled(False)
        self.startup_with_windows = QCheckBox("Windows 시작 시 함께 실행")
        self.update_snooze_label = QLabel("업데이트 알림 숨김")
        self.update_snooze_until = QLabel("")
        self.update_snooze_until.setObjectName("mutedText")
        form.addRow("활성 프리셋", self.template)
        form.addRow("프리셋 이름", self.template_name)
        form.addRow("창 옵션", self.always_on_top)
        form.addRow("클립보드 최대 개수", self.clipboard_limit)
        form.addRow("시작 프로그램", self.startup_with_windows)
        form.addRow("자동 업데이트", self.auto_update_install)
        form.addRow("업데이트 확인", self.auto_update_check)
        form.addRow(self.update_snooze_label, self.update_snooze_until)
        layout.addLayout(form)
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
        self.clipboard_popup_hotkey.setMaximumWidth(self.FIELD_MAX_WIDTH)
        layout.addWidget(self.hotkey_group("클립보드 미니팝업", self.popup_mode_double_ctrl, self.popup_mode_hotkey, self.clipboard_popup_hotkey))

        self.memo_mode_group = QButtonGroup(self)
        self.memo_mode_hotkey = QRadioButton("지정 단축키 사용")
        self.memo_mode_double_alt = QRadioButton("Alt 두 번 사용")
        self.memo_mode_group.addButton(self.memo_mode_hotkey, 0)
        self.memo_mode_group.addButton(self.memo_mode_double_alt, 1)
        self.quick_memo_hotkey = HotkeyFields()
        self.quick_memo_hotkey.setFixedHeight(28)
        self.quick_memo_hotkey.setMaximumWidth(self.FIELD_MAX_WIDTH)
        layout.addWidget(self.hotkey_group("빠른 메모", self.memo_mode_double_alt, self.memo_mode_hotkey, self.quick_memo_hotkey))

        self.phrase_popup_hotkey = HotkeyFields()
        self.phrase_popup_hotkey.setFixedHeight(28)
        self.phrase_popup_hotkey.setMaximumWidth(self.FIELD_MAX_WIDTH)
        layout.addWidget(self.single_hotkey_group("상용구 미니팝업", "단축키", self.phrase_popup_hotkey))

        self.steel_cut_hotkey = HotkeyFields()
        self.steel_cut_hotkey.setFixedHeight(28)
        self.steel_cut_hotkey.setMaximumWidth(self.FIELD_MAX_WIDTH)

        self.screen_draw_hotkey = HotkeyFields()
        self.screen_draw_hotkey.setFixedHeight(28)
        self.screen_draw_hotkey.setMaximumWidth(self.FIELD_MAX_WIDTH)

        # 캡처는 항상 스마트 캡처(요소 인식 + 드래그 + 전체/활성 창 단축키)로
        # 동작하므로 캡처 방식/고정 캡처 크기 설정은 두지 않는다.
        steel_box = QWidget()
        steel_box.setObjectName("card")
        steel_box.setMinimumHeight(92)
        steel_layout = QFormLayout(steel_box)
        steel_layout.setContentsMargins(14, 14, 14, 14)
        steel_layout.setVerticalSpacing(12)
        title = QLabel("캡처 도구")
        title.setObjectName("cardTitle")
        steel_layout.addRow(title)
        steel_layout.addRow("캡처 단축키", self.steel_cut_hotkey)
        hint = QLabel("스마트 캡처로 동작합니다. 캡처 중 A: 전체 화면, S: 활성 창, Z: 겹친 영역 전환")
        hint.setObjectName("mutedText")
        steel_layout.addRow("", hint)
        layout.addWidget(steel_box)

        layout.addWidget(self.single_hotkey_group("화면그리기", "단축키", self.screen_draw_hotkey))

        self.popup_mode_group.buttonToggled.connect(self.update_mode_enabled)
        self.memo_mode_group.buttonToggled.connect(self.update_mode_enabled)
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

    def build_widget(self) -> None:
        root = QVBoxLayout(self.widget_tab)
        root.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        self.widget_scroll = scroll
        self.widget_content = content
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        sidebar_box = QWidget()
        sidebar_box.setObjectName("card")
        form = QFormLayout(sidebar_box)
        form.setContentsMargins(14, 14, 14, 14)
        form.setVerticalSpacing(12)
        title = QLabel("플로팅 위젯")
        title.setObjectName("cardTitle")
        form.addRow(title)

        self.floating_widget_enabled = QCheckBox("마우스를 화면 가장자리로 가져가면 위젯 보이기")
        form.addRow("사용", self.floating_widget_enabled)

        self.floating_widget_edge = QComboBox()
        self.floating_widget_edge.setMaximumWidth(self.FIELD_MAX_WIDTH)
        for label, value in [("아래", "bottom"), ("위", "top"), ("왼쪽", "left"), ("오른쪽", "right")]:
            self.floating_widget_edge.addItem(label, value)
        form.addRow("사이드 영역", self.floating_widget_edge)

        self.floating_widget_monitor = QComboBox()
        self.floating_widget_monitor.setMaximumWidth(self.FIELD_MAX_WIDTH)
        form.addRow("표시 모니터", self.floating_widget_monitor)

        self.floating_widget_panel_position = self.widget_slider(0, 100, "%")
        form.addRow("패널 위치", self.floating_widget_panel_position)

        self.floating_widget_panel_size = self.widget_slider(130, 280, " px")
        form.addRow("패널 사이즈", self.floating_widget_panel_size)
        self.floating_widget_panel_width = self.widget_slider(260, 1400, " px")
        form.addRow("패널 가로 너비", self.floating_widget_panel_width)
        self.floating_widget_icon_size = self.widget_slider(40, 128, " px")
        form.addRow("아이콘 사이즈", self.floating_widget_icon_size)
        self.floating_widget_speed = self.widget_slider(60, 900, " ms")
        form.addRow("등장 속도", self.floating_widget_speed)
        self.floating_widget_show_delay = self.widget_slider(0, 2000, " ms")
        form.addRow("표시 딜레이", self.floating_widget_show_delay)
        self.floating_widget_opacity = self.widget_slider(20, 100, " %")
        form.addRow("투명도", self.floating_widget_opacity)

        self.floating_widget_theme = QComboBox()
        self.floating_widget_theme.setMaximumWidth(self.FIELD_MAX_WIDTH)
        self.floating_widget_theme.addItem("밝은 테마", "light")
        self.floating_widget_theme.addItem("어두운 테마", "dark")
        self.floating_widget_theme.addItem("미러 글래스", "glass")
        self.floating_widget_theme.addItem("민트", "mint")
        self.floating_widget_theme.addItem("로즈", "rose")
        form.addRow("위젯 테마", self.floating_widget_theme)

        self.floating_widget_show_hover_text = QCheckBox("마우스 오버 시 전체 내용 팝업 메시지 표시")
        form.addRow("팝업 메시지", self.floating_widget_show_hover_text)

        self.floating_widget_icon_size.slider.valueChanged.connect(lambda _value: self.sync_widget_size_sliders("icon"))
        self.floating_widget_panel_size.slider.valueChanged.connect(lambda _value: self.sync_widget_size_sliders("panel"))
        self.floating_widget_show_hover_text.toggled.connect(lambda _checked: self.sync_widget_size_sliders("hover"))

        menu_box = QWidget()
        menu_box.setObjectName("floatingWidgetMenuBox")
        menu_theme = THEMES.get(self.main.settings.get("theme", "light"), THEMES["light"])
        menu_box.setStyleSheet(
            f"""
            QWidget#floatingWidgetMenuBox {{
                background: transparent;
                border: 0;
            }}
            QWidget#floatingWidgetMenuBox QCheckBox {{
                background: transparent;
                color: {menu_theme["text"]};
            }}
            """
        )
        menu_layout = QGridLayout(menu_box)
        menu_layout.setContentsMargins(0, 0, 0, 0)
        menu_layout.setHorizontalSpacing(12)
        menu_layout.setVerticalSpacing(4)
        self.floating_widget_category_checks = {}
        for index, (key, label, _icon) in enumerate(CATEGORY_ORDER):
            check = QCheckBox(label)
            self.floating_widget_category_checks[key] = check
            menu_layout.addWidget(check, index // 3, index % 3)
            check.toggled.connect(lambda _checked: self.preview_widget_settings())
        form.addRow("표시 메뉴", menu_box)

        layout.addWidget(sidebar_box)

        memo_box = QWidget()
        memo_box.setObjectName("card")
        memo_form = QFormLayout(memo_box)
        memo_form.setContentsMargins(14, 14, 14, 14)
        memo_form.setVerticalSpacing(12)
        memo_title = QLabel("메모 정렬")
        memo_title.setObjectName("cardTitle")
        memo_form.addRow(memo_title)

        # 표시 방식
        display_row = QWidget()
        display_layout = QHBoxLayout(display_row)
        display_layout.setContentsMargins(0, 0, 0, 0)
        display_layout.setSpacing(16)
        self._memo_display_group = QButtonGroup(self)
        self.memo_display_floating = QRadioButton("플로팅 형태")
        self.memo_display_index = QRadioButton("인덱스 형태")
        self._memo_display_group.addButton(self.memo_display_floating)
        self._memo_display_group.addButton(self.memo_display_index)
        self.memo_display_floating.setChecked(True)
        display_layout.addWidget(self.memo_display_floating)
        display_layout.addWidget(self.memo_display_index)
        display_layout.addStretch(1)
        display_row.setStyleSheet("background: transparent; border: 0;")
        memo_form.addRow("표시 방식", display_row)

        # 정렬 모니터 (공통)
        self.sticky_memo_arrange_monitor = QComboBox()
        self.sticky_memo_arrange_monitor.setMaximumWidth(self.FIELD_MAX_WIDTH)
        memo_form.addRow("정렬 모니터", self.sticky_memo_arrange_monitor)

        # 정렬 기준 - 플로팅 전용
        self.sticky_memo_arrange_corner = QComboBox()
        self.sticky_memo_arrange_corner.setMaximumWidth(self.FIELD_MAX_WIDTH)
        for label, value in [
            ("우측 상단", "top_right"),
            ("좌측 상단", "top_left"),
            ("우측 하단", "bottom_right"),
            ("좌측 하단", "bottom_left"),
        ]:
            self.sticky_memo_arrange_corner.addItem(label, value)
        self._memo_floating_corner_lbl = QLabel("정렬 기준")
        memo_form.addRow(self._memo_floating_corner_lbl, self.sticky_memo_arrange_corner)

        # 정렬 기준 - 인덱스 전용 (좌/우)
        self._memo_index_side_widget = QWidget()
        index_side_row = QHBoxLayout(self._memo_index_side_widget)
        index_side_row.setContentsMargins(0, 0, 0, 0)
        index_side_row.setSpacing(16)
        self._memo_index_side_group = QButtonGroup(self)
        self.memo_index_side_left = QRadioButton("좌측")
        self.memo_index_side_right = QRadioButton("우측")
        self._memo_index_side_group.addButton(self.memo_index_side_left)
        self._memo_index_side_group.addButton(self.memo_index_side_right)
        self.memo_index_side_right.setChecked(True)
        index_side_row.addWidget(self.memo_index_side_left)
        index_side_row.addWidget(self.memo_index_side_right)
        index_side_row.addStretch(1)
        self._memo_index_side_widget.setStyleSheet("background: transparent; border: 0;")
        self._memo_index_side_lbl = QLabel("정렬 기준")
        memo_form.addRow(self._memo_index_side_lbl, self._memo_index_side_widget)

        # 시작 위치 - 인덱스 전용
        self.memo_index_start_y = self.widget_slider(0, 90, "%")
        self._memo_index_start_y_lbl = QLabel("시작 위치")
        memo_form.addRow(self._memo_index_start_y_lbl, self.memo_index_start_y)

        # 초기 가시성 (플로팅이 기본)
        self._memo_index_side_lbl.setVisible(False)
        self._memo_index_side_widget.setVisible(False)
        self._memo_index_start_y_lbl.setVisible(False)
        self.memo_index_start_y.setVisible(False)

        self.memo_display_floating.toggled.connect(self._update_memo_display_mode_ui)
        self.memo_display_index.toggled.connect(self._update_memo_display_mode_ui)
        self.memo_index_start_y.slider.valueChanged.connect(self._preview_index_settings)
        self.memo_index_side_left.toggled.connect(self._preview_index_settings)
        self.memo_index_side_right.toggled.connect(self._preview_index_settings)
        self.connect_widget_preview_controls()

        layout.addWidget(memo_box)
        layout.addStretch(1)

    def _update_memo_display_mode_ui(self) -> None:
        is_index = hasattr(self, "memo_display_index") and self.memo_display_index.isChecked()
        if hasattr(self, "_memo_floating_corner_lbl"):
            self._memo_floating_corner_lbl.setVisible(not is_index)
        if hasattr(self, "sticky_memo_arrange_corner"):
            self.sticky_memo_arrange_corner.setVisible(not is_index)
        if hasattr(self, "_memo_index_side_lbl"):
            self._memo_index_side_lbl.setVisible(is_index)
        if hasattr(self, "_memo_index_side_widget"):
            self._memo_index_side_widget.setVisible(is_index)
        if hasattr(self, "_memo_index_start_y_lbl"):
            self._memo_index_start_y_lbl.setVisible(is_index)
        if hasattr(self, "memo_index_start_y"):
            self.memo_index_start_y.setVisible(is_index)

    def _get_memo_tab(self):
        for tab in getattr(self.main, "tabs", []):
            if hasattr(tab, "_arrange_index_cards"):
                return tab
        return None

    def _preview_index_settings(self) -> None:
        if self._refreshing:
            return
        if not (hasattr(self, "memo_display_index") and self.memo_display_index.isChecked()):
            return
        tab = self._get_memo_tab()
        if tab is None:
            return
        settings = self.main.settings
        settings["sticky_memo_index_start_y"] = self.widget_slider_value(self.memo_index_start_y, 0)
        settings["sticky_memo_index_side"] = "left" if (hasattr(self, "memo_index_side_left") and self.memo_index_side_left.isChecked()) else "right"
        tab._arrange_index_cards()

    def _accent(self) -> str:
        return THEMES.get(self.main.settings.get("theme", "light"), THEMES["light"]).get("highlight", "#94AEF4")

    def _slider_stylesheet(self, accent: str) -> str:
        return f"""
            QWidget {{ background: transparent; border: 0; }}
            QSlider {{ background: transparent; }}
            QSlider::groove:horizontal {{
                height: 6px;
                background: rgba(148, 163, 184, 70);
                border: 0;
                border-radius: 3px;
            }}
            QSlider::sub-page:horizontal {{
                background: {accent};
                border: 0;
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                width: 15px;
                height: 15px;
                margin: -5px 0;
                background: #FFFFFF;
                border: 1px solid {accent};
                border-radius: 8px;
            }}
        """

    def apply_theme(self) -> None:
        stylesheet = self._slider_stylesheet(self._accent())
        for holder in self._widget_slider_holders:
            holder.setStyleSheet(stylesheet)

    def widget_slider(self, minimum: int, maximum: int, suffix: str) -> QWidget:
        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        value_label = QLabel()
        value_label.setFixedWidth(64)
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        slider.valueChanged.connect(lambda value, label=value_label: label.setText(f"{value}{suffix}"))
        row.addWidget(slider, 1)
        row.addWidget(value_label)
        holder.slider = slider
        holder.value_label = value_label
        holder.setMaximumWidth(self.FIELD_MAX_WIDTH)
        holder.setStyleSheet(self._slider_stylesheet(self._accent()))
        self._widget_slider_holders.append(holder)
        return holder

    def set_widget_slider_value(self, holder: QWidget, value: int) -> None:
        slider = getattr(holder, "slider", None)
        if slider is not None:
            slider.setValue(value)

    def widget_slider_value(self, holder: QWidget, fallback: int) -> int:
        slider = getattr(holder, "slider", None)
        return int(slider.value()) if slider is not None else fallback

    def minimum_panel_for_icon(self, icon_size: int | None = None) -> int:
        icon_size = int(icon_size if icon_size is not None else self.widget_slider_value(self.floating_widget_icon_size, 50))
        hover_height = 12
        spacing = 3
        item_height = max(78, int(icon_size * 1.32) + 34)
        return max(130, 20 + hover_height + spacing + item_height)

    def sync_widget_size_sliders(self, source: str = "") -> None:
        if not hasattr(self, "floating_widget_panel_size") or getattr(self, "_syncing_widget_sizes", False):
            return
        self._syncing_widget_sizes = True
        try:
            panel_slider = self.floating_widget_panel_size.slider
            icon_slider = self.floating_widget_icon_size.slider
            min_panel = self.minimum_panel_for_icon(icon_slider.value())
            panel_slider.setMinimum(min_panel)
            if panel_slider.value() < min_panel:
                panel_slider.setValue(min_panel)
        finally:
            self._syncing_widget_sizes = False
        self.preview_widget_settings()

    def connect_widget_preview_controls(self) -> None:
        controls = [
            self.floating_widget_enabled,
            self.floating_widget_edge,
            self.floating_widget_monitor,
            self.floating_widget_theme,
            self.floating_widget_show_hover_text,
        ]
        for control in controls:
            if isinstance(control, QCheckBox):
                control.toggled.connect(lambda _checked: self.preview_widget_settings())
            elif isinstance(control, QComboBox):
                control.currentIndexChanged.connect(lambda _index: self.preview_widget_settings())
        for holder in [
            self.floating_widget_panel_size,
            self.floating_widget_panel_width,
            self.floating_widget_icon_size,
            self.floating_widget_speed,
            self.floating_widget_show_delay,
            self.floating_widget_opacity,
        ]:
            holder.slider.valueChanged.connect(lambda _value: self.preview_widget_settings())
        self.floating_widget_panel_position.slider.valueChanged.connect(lambda _value: self.preview_widget_position_settings())
        if hasattr(self, "sticky_memo_arrange_monitor"):
            self.sticky_memo_arrange_monitor.currentIndexChanged.connect(lambda _index: self.preview_memo_arrange_settings())
        if hasattr(self, "sticky_memo_arrange_corner"):
            self.sticky_memo_arrange_corner.currentIndexChanged.connect(lambda _index: self.preview_memo_arrange_settings())

    def widget_settings_state(self) -> dict:
        floating_monitor = int(self.floating_widget_monitor.currentData() or 1)
        sticky_monitor = int(self.sticky_memo_arrange_monitor.currentData() or 1) if hasattr(self, "sticky_memo_arrange_monitor") else 1
        floating_signature = signature_for_monitor_index(floating_monitor) or self.main.settings.get("floating_widget_monitor_signature")
        sticky_signature = signature_for_monitor_index(sticky_monitor) or self.main.settings.get("sticky_memo_arrange_monitor_signature")
        return {
            "floating_widget_enabled": self.floating_widget_enabled.isChecked(),
            "floating_widget_edge": self.floating_widget_edge.currentData(),
            "floating_widget_monitor": floating_monitor,
            "floating_widget_monitor_preferred": floating_monitor,
            "floating_widget_monitor_signature": floating_signature,
            "floating_widget_panel_position": self.widget_slider_value(self.floating_widget_panel_position, 50),
            "floating_widget_panel_size": self.widget_slider_value(self.floating_widget_panel_size, 160),
            "floating_widget_panel_width": self.widget_slider_value(self.floating_widget_panel_width, 860),
            "floating_widget_icon_size": self.widget_slider_value(self.floating_widget_icon_size, 50),
            "floating_widget_speed": self.widget_slider_value(self.floating_widget_speed, 80),
            "floating_widget_show_delay": self.widget_slider_value(self.floating_widget_show_delay, 1000),
            "floating_widget_opacity": self.widget_slider_value(self.floating_widget_opacity, 77),
            "floating_widget_theme": self.floating_widget_theme.currentData(),
            "floating_widget_show_hover_text": self.floating_widget_show_hover_text.isChecked(),
            "floating_widget_categories": self.widget_categories_value(),
            "sticky_memo_arrange_monitor": sticky_monitor,
            "sticky_memo_arrange_monitor_preferred": sticky_monitor,
            "sticky_memo_arrange_monitor_signature": sticky_signature,
            "sticky_memo_arrange_corner": self.sticky_memo_arrange_corner.currentData() if hasattr(self, "sticky_memo_arrange_corner") else "top_right",
        }

    def preview_widget_settings(self) -> None:
        if self._refreshing or getattr(self, "_syncing_widget_sizes", False):
            return
        if not hasattr(self, "floating_widget_enabled"):
            return
        self.main.settings.update(self.widget_settings_state())
        widget = getattr(self.main, "floating_widget", None)
        if widget is not None:
            widget.preview_settings()
        memo_tab = self._get_memo_tab()
        if memo_tab is not None:
            memo_tab.arrange_compact_stickers()

    def preview_widget_position_settings(self) -> None:
        if self._refreshing:
            return
        if not hasattr(self, "floating_widget_panel_position"):
            return
        self.main.settings["floating_widget_panel_position"] = self.widget_slider_value(self.floating_widget_panel_position, 50)
        widget = getattr(self.main, "floating_widget", None)
        if widget is not None:
            widget.preview_position_settings()

    def preview_memo_arrange_settings(self) -> None:
        if self._refreshing:
            return
        if hasattr(self, "sticky_memo_arrange_monitor"):
            sticky_monitor = int(self.sticky_memo_arrange_monitor.currentData() or 1)
            self.main.settings["sticky_memo_arrange_monitor"] = sticky_monitor
            self.main.settings["sticky_memo_arrange_monitor_preferred"] = sticky_monitor
            self.main.settings["sticky_memo_arrange_monitor_signature"] = signature_for_monitor_index(sticky_monitor) or self.main.settings.get("sticky_memo_arrange_monitor_signature")
        if hasattr(self, "sticky_memo_arrange_corner"):
            self.main.settings["sticky_memo_arrange_corner"] = self.sticky_memo_arrange_corner.currentData()
        memo_tab = self._get_memo_tab()
        if memo_tab is not None:
            memo_tab.arrange_compact_stickers()

    def refresh_widget_monitor_combo(self, selected: int | None = None) -> None:
        if not hasattr(self, "floating_widget_monitor"):
            return
        selected = int(selected or self.main.settings.get("floating_widget_monitor", 1) or 1)
        screens = QApplication.screens()
        self.floating_widget_monitor.blockSignals(True)
        self.floating_widget_monitor.clear()
        if hasattr(self, "sticky_memo_arrange_monitor"):
            sticky_selected = int(self.main.settings.get("sticky_memo_arrange_monitor", 1) or 1)
            self.sticky_memo_arrange_monitor.blockSignals(True)
            self.sticky_memo_arrange_monitor.clear()
        if not screens:
            self.floating_widget_monitor.addItem("1번 모니터", 1)
            if hasattr(self, "sticky_memo_arrange_monitor"):
                self.sticky_memo_arrange_monitor.addItem("1번 모니터", 1)
        else:
            for index, screen in enumerate(screens, start=1):
                geo = screen.geometry()
                primary = " · 기본" if screen is QApplication.primaryScreen() else ""
                self.floating_widget_monitor.addItem(f"{index}번 모니터 ({geo.width()}x{geo.height()}){primary}", index)
                if hasattr(self, "sticky_memo_arrange_monitor"):
                    self.sticky_memo_arrange_monitor.addItem(f"{index}번 모니터 ({geo.width()}x{geo.height()}){primary}", index)
        if selected > self.floating_widget_monitor.count():
            self.floating_widget_monitor.addItem(f"{selected}번 모니터 (현재 미연결)", selected)
        index = self.floating_widget_monitor.findData(max(1, selected))
        self.floating_widget_monitor.setCurrentIndex(index if index >= 0 else 0)
        self.floating_widget_monitor.blockSignals(False)
        if hasattr(self, "sticky_memo_arrange_monitor"):
            if sticky_selected > self.sticky_memo_arrange_monitor.count():
                self.sticky_memo_arrange_monitor.addItem(f"{sticky_selected}번 모니터 (현재 미연결)", sticky_selected)
            sticky_index = self.sticky_memo_arrange_monitor.findData(max(1, sticky_selected))
            self.sticky_memo_arrange_monitor.setCurrentIndex(sticky_index if sticky_index >= 0 else 0)
            self.sticky_memo_arrange_monitor.blockSignals(False)

    def set_widget_categories(self, categories: list | None) -> None:
        enabled = categories if isinstance(categories, list) else [key for key, _label, _icon in CATEGORY_ORDER]
        enabled_set = {str(key) for key in enabled}
        for key, check in getattr(self, "floating_widget_category_checks", {}).items():
            check.setChecked(key in enabled_set)

    def widget_categories_value(self) -> list[str]:
        result = [
            key
            for key, check in getattr(self, "floating_widget_category_checks", {}).items()
            if check.isChecked()
        ]
        return result or [key for key, _label, _icon in CATEGORY_ORDER]

    def end_widget_preview(self) -> None:
        widget = getattr(self.main, "floating_widget", None)
        if widget is not None and getattr(widget, "_preview_pinned", False):
            widget.apply_settings()

    def focus_sticky_memo_index_mode(self) -> None:
        self.tabs.setCurrentWidget(self.widget_tab)
        self._clear_update_shortcut_guides()
        if hasattr(self, "memo_display_index"):
            self.memo_display_index.setChecked(True)
            self.memo_display_index.setFocus(Qt.FocusReason.OtherFocusReason)
            scroll = getattr(self, "widget_scroll", None)
            if scroll is not None:
                for delay in (0, 120, 300, 600):
                    QTimer.singleShot(delay, lambda margin=96: self._scroll_to_memo_index_mode(margin))
            QTimer.singleShot(620, self.flash_sticky_memo_index_mode)
            QTimer.singleShot(880, self.show_sticky_memo_index_hint)

    def _scroll_to_memo_index_mode(self, margin: int = 80) -> None:
        self._scroll_to_widget_target(getattr(self, "memo_display_index", None), margin)

    def _scroll_to_floating_panel_position(self, margin: int = 80) -> None:
        self._scroll_to_widget_target(getattr(self, "floating_widget_panel_position", None), margin)

    def _scroll_to_widget_target(self, target: QWidget | None, margin: int = 80) -> None:
        scroll = getattr(self, "widget_scroll", None)
        content = getattr(self, "widget_content", None)
        if scroll is None or content is None or target is None:
            return
        if scroll.widget() is not content:
            content = scroll.widget()
        if content is None:
            return
        content.adjustSize()
        scroll.updateGeometry()
        QApplication.processEvents()
        bar = scroll.verticalScrollBar()
        target_y = target.mapTo(content, target.rect().topLeft()).y()
        desired = max(bar.minimum(), target_y - margin)
        bar.setValue(min(bar.maximum(), desired))
        scroll.ensureWidgetVisible(target, 32, margin)
        scroll.viewport().update()

    def flash_sticky_memo_index_mode(self) -> None:
        self._show_update_shortcut_highlight(getattr(self, "memo_display_index", None))

    def _clear_update_shortcut_guides(self) -> None:
        seen = set()
        for attr in ("_update_shortcut_highlight", "_memo_index_highlight", "_memo_index_hint"):
            widget = getattr(self, attr, None)
            if widget is not None and id(widget) not in seen:
                seen.add(id(widget))
                widget.hide()
                widget.deleteLater()
            setattr(self, attr, None)

    def _show_update_shortcut_highlight(self, target: QWidget | None) -> None:
        if target is None:
            return
        old = getattr(self, "_update_shortcut_highlight", None)
        if old is not None:
            old.hide()
            old.deleteLater()
        highlight = QWidget(self.widget_tab)
        highlight.setObjectName("memoIndexHighlight")
        highlight.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        highlight.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        highlight.setStyleSheet(
            """
            QWidget#memoIndexHighlight {
                background: rgba(225, 29, 72, 22);
                border: 2px solid rgba(225, 29, 72, 210);
                border-radius: 8px;
            }
            """
        )
        pad = 5
        pos = target.mapTo(self.widget_tab, target.rect().topLeft())
        highlight.setGeometry(pos.x() - pad, pos.y() - pad, target.width() + pad * 2, target.height() + pad * 2)
        highlight.show()
        highlight.raise_()
        self._update_shortcut_highlight = highlight
        self._memo_index_highlight = highlight

    def show_sticky_memo_index_hint(self) -> None:
        target = getattr(self, "memo_display_index", None)
        self._show_update_shortcut_bubble(
            target,
            "인덱스 형태를 선택하면 메모가 화면 가장자리 카드로 열립니다.",
            "다음",
            self.focus_floating_widget_panel_position,
        )

    def focus_floating_widget_panel_position(self) -> None:
        old = getattr(self, "_memo_index_hint", None)
        if old is not None:
            old.hide()
            old.deleteLater()
            self._memo_index_hint = None
        for delay in (0, 120, 300, 600):
            QTimer.singleShot(delay, lambda margin=96: self._scroll_to_floating_panel_position(margin))
        QTimer.singleShot(620, lambda: self._show_update_shortcut_highlight(getattr(self, "floating_widget_panel_position", None)))
        QTimer.singleShot(880, self.show_floating_widget_panel_position_hint)

    def show_floating_widget_panel_position_hint(self) -> None:
        self._show_update_shortcut_bubble(
            getattr(self, "floating_widget_panel_position", None),
            "플로팅 위젯의 위치를 변경할 수 있어요.",
            "x",
            self._clear_update_shortcut_guides,
        )

    def _show_update_shortcut_bubble(self, target: QWidget | None, message: str, button_text: str, callback) -> None:
        if target is None:
            return
        old = getattr(self, "_memo_index_hint", None)
        if old is not None:
            old.hide()
            old.deleteLater()
        hint = QWidget(self.widget_tab)
        hint.setObjectName("memoIndexHintBubble")
        hint.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row = QHBoxLayout(hint)
        row.setContentsMargins(10, 7, 8, 7)
        row.setSpacing(8)
        label = QLabel(message)
        label.setWordWrap(True)
        action = QPushButton(button_text)
        action.setFixedHeight(24)
        action.clicked.connect(callback)
        row.addWidget(label, 1)
        row.addWidget(action, 0, Qt.AlignmentFlag.AlignTop)
        hint.setStyleSheet(
            """
            QWidget#memoIndexHintBubble {
                background: #FFFFFF;
                border: 1px solid #FB7185;
                border-radius: 8px;
            }
            QWidget#memoIndexHintBubble QLabel {
                color: #9F1239;
                font-size: 9pt;
                font-weight: 700;
            }
            QWidget#memoIndexHintBubble QPushButton {
                background: #E11D48;
                border: 0;
                border-radius: 6px;
                color: #FFFFFF;
                font-size: 8pt;
                font-weight: 800;
                padding: 2px 9px;
            }
            """
        )
        hint.setFixedWidth(300)
        hint.adjustSize()
        pos = target.mapTo(self.widget_tab, target.rect().bottomLeft())
        x = min(max(8, pos.x()), max(8, self.widget_tab.width() - hint.width() - 8))
        y = min(max(8, pos.y() + 8), max(8, self.widget_tab.height() - hint.height() - 8))
        hint.move(x, y)
        hint.show()
        hint.raise_()
        self._memo_index_hint = hint

    def hideEvent(self, event) -> None:
        self.end_widget_preview()
        super().hideEvent(event)

    def hotkey_group(self, title: str, default_radio: QRadioButton, custom_radio: QRadioButton, fields: HotkeyFields) -> QWidget:
        box = QWidget()
        box.setObjectName("card")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        layout.addWidget(title_label)
        layout.addWidget(default_radio)
        custom_row = QHBoxLayout()
        custom_row.setContentsMargins(0, 0, 0, 0)
        custom_row.setSpacing(12)
        custom_row.addWidget(custom_radio)
        custom_row.addWidget(fields)
        custom_row.addStretch(1)
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
        self.auto_update_install.setChecked(True)
        actual_startup = is_startup_enabled()
        self.startup_with_windows.setChecked(actual_startup)
        settings["startup_with_windows"] = actual_startup
        snooze_text = self.format_update_snooze_until(settings.get("update_notice_snooze_until", ""))
        self.update_snooze_until.setText(snooze_text)
        self.update_snooze_label.setVisible(bool(snooze_text))
        self.update_snooze_until.setVisible(bool(snooze_text))
        self.floating_widget_enabled.setChecked(bool(settings.get("floating_widget_enabled", True)))
        edge = str(settings.get("floating_widget_edge", "top") or "top")
        edge_index = self.floating_widget_edge.findData(edge)
        self.floating_widget_edge.setCurrentIndex(edge_index if edge_index >= 0 else 0)
        self.refresh_widget_monitor_combo(int(settings.get("floating_widget_monitor", 1) or 1))
        self.set_widget_slider_value(self.floating_widget_panel_position, int(settings.get("floating_widget_panel_position", 50) or 50))
        self.set_widget_slider_value(self.floating_widget_panel_size, int(settings.get("floating_widget_panel_size", 160) or 160))
        self.set_widget_slider_value(self.floating_widget_panel_width, int(settings.get("floating_widget_panel_width", 860) or 860))
        self.set_widget_slider_value(self.floating_widget_icon_size, int(settings.get("floating_widget_icon_size", 50) or 50))
        self.set_widget_slider_value(self.floating_widget_speed, int(settings.get("floating_widget_speed", 80) or 80))
        self.set_widget_slider_value(self.floating_widget_show_delay, int(settings.get("floating_widget_show_delay", 1000) or 1000))
        self.set_widget_slider_value(self.floating_widget_opacity, int(settings.get("floating_widget_opacity", 77) or 77))
        widget_theme = str(settings.get("floating_widget_theme", "dark") or "dark")
        widget_theme_index = self.floating_widget_theme.findData(widget_theme)
        self.floating_widget_theme.setCurrentIndex(widget_theme_index if widget_theme_index >= 0 else 0)
        self.floating_widget_show_hover_text.setChecked(bool(settings.get("floating_widget_show_hover_text", True)))
        self.sync_widget_size_sliders("refresh")
        self.set_widget_categories(settings.get("floating_widget_categories"))
        sticky_corner = str(settings.get("sticky_memo_arrange_corner", "top_right") or "top_right")
        sticky_corner_index = self.sticky_memo_arrange_corner.findData(sticky_corner)
        self.sticky_memo_arrange_corner.setCurrentIndex(sticky_corner_index if sticky_corner_index >= 0 else 0)
        # 메모 표시 방식
        display_mode = str(settings.get("sticky_memo_display_mode", "floating") or "floating")
        if hasattr(self, "memo_display_index"):
            if display_mode == "index":
                self.memo_display_index.setChecked(True)
            else:
                self.memo_display_floating.setChecked(True)
        if hasattr(self, "memo_index_side_left"):
            if str(settings.get("sticky_memo_index_side", "right") or "right") == "left":
                self.memo_index_side_left.setChecked(True)
            else:
                self.memo_index_side_right.setChecked(True)
        if hasattr(self, "memo_index_start_y"):
            self.set_widget_slider_value(self.memo_index_start_y, int(settings.get("sticky_memo_index_start_y", 0) or 0))
        self._update_memo_display_mode_ui()
        self.clipboard_popup_hotkey.set_hotkey(settings.get("clipboard_popup_hotkey"))
        self.quick_memo_hotkey.set_hotkey(settings.get("quick_memo_hotkey"))
        self.phrase_popup_hotkey.set_hotkey(settings.get("phrase_popup_hotkey"))
        self.steel_cut_hotkey.set_hotkey(settings.get("steel_cut_hotkey"))
        self.screen_draw_hotkey.set_hotkey(settings.get("screen_draw_hotkey"))
        self.popup_mode_double_ctrl.setChecked(bool(settings.get("clipboard_popup_double_ctrl", True)))
        self.popup_mode_hotkey.setChecked(not self.popup_mode_double_ctrl.isChecked())
        self.memo_mode_double_alt.setChecked(bool(settings.get("quick_memo_double_alt", True)))
        self.memo_mode_hotkey.setChecked(not self.memo_mode_double_alt.isChecked())
        self.update_mode_enabled()
        self._general_snapshot = self.current_general_state()
        self._settings_snapshot = self.current_settings_state()
        self._refreshing = False

    def current_general_state(self) -> dict:
        return {
            "template_name": self.template_name.text().strip(),
            "always_on_top": self.always_on_top.isChecked(),
            "clipboard_limit": self.clipboard_limit.value(),
            "auto_update_check": self.auto_update_check.isChecked(),
            "auto_update_install": True,
            "startup_with_windows": self.startup_with_windows.isChecked(),
            "floating_widget_enabled": self.floating_widget_enabled.isChecked() if hasattr(self, "floating_widget_enabled") else True,
            "floating_widget_edge": self.floating_widget_edge.currentData() if hasattr(self, "floating_widget_edge") else "top",
            "floating_widget_monitor": self.floating_widget_monitor.currentData() if hasattr(self, "floating_widget_monitor") else 1,
            "floating_widget_monitor_preferred": self.floating_widget_monitor.currentData() if hasattr(self, "floating_widget_monitor") else 1,
            "floating_widget_monitor_signature": (signature_for_monitor_index(int(self.floating_widget_monitor.currentData() or 1)) or self.main.settings.get("floating_widget_monitor_signature")) if hasattr(self, "floating_widget_monitor") else None,
            "floating_widget_panel_position": self.widget_slider_value(self.floating_widget_panel_position, 50) if hasattr(self, "floating_widget_panel_position") else 50,
            "floating_widget_panel_size": self.widget_slider_value(self.floating_widget_panel_size, 160) if hasattr(self, "floating_widget_panel_size") else 160,
            "floating_widget_panel_width": self.widget_slider_value(self.floating_widget_panel_width, 860) if hasattr(self, "floating_widget_panel_width") else 860,
            "floating_widget_icon_size": self.widget_slider_value(self.floating_widget_icon_size, 50) if hasattr(self, "floating_widget_icon_size") else 50,
            "floating_widget_speed": self.widget_slider_value(self.floating_widget_speed, 80) if hasattr(self, "floating_widget_speed") else 80,
            "floating_widget_opacity": self.widget_slider_value(self.floating_widget_opacity, 77) if hasattr(self, "floating_widget_opacity") else 77,
            "floating_widget_theme": self.floating_widget_theme.currentData() if hasattr(self, "floating_widget_theme") else "dark",
            "floating_widget_show_hover_text": self.floating_widget_show_hover_text.isChecked() if hasattr(self, "floating_widget_show_hover_text") else True,
            "floating_widget_categories": self.widget_categories_value() if hasattr(self, "floating_widget_category_checks") else [key for key, _label, _icon in CATEGORY_ORDER],
            "sticky_memo_arrange_monitor": int(self.sticky_memo_arrange_monitor.currentData() or 1) if hasattr(self, "sticky_memo_arrange_monitor") else 1,
            "sticky_memo_arrange_monitor_preferred": int(self.sticky_memo_arrange_monitor.currentData() or 1) if hasattr(self, "sticky_memo_arrange_monitor") else 1,
            "sticky_memo_arrange_monitor_signature": (signature_for_monitor_index(int(self.sticky_memo_arrange_monitor.currentData() or 1)) or self.main.settings.get("sticky_memo_arrange_monitor_signature")) if hasattr(self, "sticky_memo_arrange_monitor") else None,
            "sticky_memo_arrange_corner": self.sticky_memo_arrange_corner.currentData() if hasattr(self, "sticky_memo_arrange_corner") else "top_right",
            "sticky_memo_display_mode": "index" if (hasattr(self, "memo_display_index") and self.memo_display_index.isChecked()) else "floating",
            "sticky_memo_index_side": "left" if (hasattr(self, "memo_index_side_left") and self.memo_index_side_left.isChecked()) else "right",
            "sticky_memo_index_start_y": self.widget_slider_value(self.memo_index_start_y, 0) if hasattr(self, "memo_index_start_y") else 0,
        }

    def format_update_snooze_until(self, value: str) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError:
            return raw
        return dt.strftime("%Y-%m-%d %H:%M까지")

    def selected_theme_key(self) -> str:
        for key, button in getattr(self, "theme_cards", {}).items():
            if button.isChecked():
                return key
        return self.main.settings.get("theme", "light")

    def current_settings_state(self) -> dict:
        state = self.current_general_state()
        state.update(
            {
                "theme": self.selected_theme_key(),
                "clipboard_popup_double_ctrl": self.popup_mode_double_ctrl.isChecked(),
                "clipboard_popup_hotkey": self.clipboard_popup_hotkey.value(),
                "quick_memo_double_alt": self.memo_mode_double_alt.isChecked(),
                "quick_memo_hotkey": self.quick_memo_hotkey.value(),
                "phrase_popup_hotkey": self.phrase_popup_hotkey.value(),
                "steel_cut_hotkey": self.steel_cut_hotkey.value(),
                "screen_draw_hotkey": self.screen_draw_hotkey.value(),
            }
        )
        return state

    def format_setting_value(self, key: str, value) -> str:
        if key == "theme":
            return THEME_LABELS.get(value, str(value))
        if key == "floating_widget_edge":
            return {"top": "위", "bottom": "아래", "left": "왼쪽", "right": "오른쪽"}.get(value, str(value))
        if key == "floating_widget_theme":
            return {"light": "밝은 테마", "dark": "어두운 테마", "glass": "미러 글래스", "mint": "민트", "rose": "로즈"}.get(value, str(value))
        if key.endswith("_hotkey"):
            return display_hotkey(value) or "없음"
        if key in {"clipboard_popup_double_ctrl", "quick_memo_double_alt", "always_on_top", "auto_update_check", "startup_with_windows", "floating_widget_enabled", "floating_widget_show_hover_text"}:
            return "사용" if value else "사용 안 함"
        return str(value)

    def changed_settings_summary(self) -> list[str]:
        labels = {
            "template_name": "프리셋 이름",
            "always_on_top": "창 항상 위",
            "clipboard_limit": "클립보드 최대 개수",
            "auto_update_check": "업데이트 자동 확인",
            "startup_with_windows": "시작 프로그램",
            "theme": "테마",
            "clipboard_popup_double_ctrl": "클립보드 기본 단축키",
            "clipboard_popup_hotkey": "클립보드 지정 단축키",
            "quick_memo_double_alt": "빠른 메모 기본 단축키",
            "quick_memo_hotkey": "빠른 메모 지정 단축키",
            "phrase_popup_hotkey": "상용구 미니팝업 단축키",
            "steel_cut_hotkey": "캡처 단축키",
            "screen_draw_hotkey": "화면그리기 단축키",
            "floating_widget_enabled": "플로팅 위젯",
            "floating_widget_edge": "위젯 사이드 영역",
            "floating_widget_monitor": "위젯 표시 모니터",
            "floating_widget_panel_position": "위젯 패널 위치",
            "floating_widget_panel_size": "위젯 패널 사이즈",
            "floating_widget_panel_width": "위젯 패널 가로 너비",
            "floating_widget_icon_size": "위젯 아이콘 사이즈",
            "floating_widget_speed": "위젯 등장 속도",
            "floating_widget_opacity": "위젯 투명도",
            "floating_widget_theme": "위젯 테마",
            "floating_widget_show_hover_text": "위젯 팝업 메시지",
            "floating_widget_categories": "위젯 표시 메뉴",
        }
        before = getattr(self, "_settings_snapshot", {})
        current = self.current_settings_state()
        changes = []
        for key, label in labels.items():
            if before.get(key) != current.get(key):
                old_value = self.format_setting_value(key, before.get(key))
                new_value = self.format_setting_value(key, current.get(key))
                changes.append(f"- {label}: {old_value} → {new_value}")
        return changes

    def is_dirty(self) -> bool:
        if self._refreshing:
            return False
        return self.current_settings_state() != getattr(self, "_settings_snapshot", {})

    def discard_changes(self) -> None:
        snapshot = getattr(self, "_settings_snapshot", {})
        if not snapshot:
            self.refresh()
            return
        self._refreshing = True
        settings = self.main.settings
        window = settings.setdefault("window", {"width": 900, "height": 580, "always_on_top": False})
        self.main.data.setdefault("meta", {})["preset_name"] = snapshot.get("template_name", f"프리셋 {self.main.template_index}")
        window["always_on_top"] = bool(snapshot.get("always_on_top", False))
        settings["clipboard_history_limit"] = int(snapshot.get("clipboard_limit", 30) or 30)
        settings["auto_update_check"] = bool(snapshot.get("auto_update_check", False))
        settings["auto_update_install"] = True
        settings["startup_with_windows"] = bool(snapshot.get("startup_with_windows", False))
        settings["steel_cut_capture_mode"] = "region"
        settings["floating_widget_enabled"] = bool(snapshot.get("floating_widget_enabled", True))
        settings["floating_widget_edge"] = snapshot.get("floating_widget_edge", "top")
        settings["floating_widget_monitor"] = int(snapshot.get("floating_widget_monitor", 1) or 1)
        settings["floating_widget_monitor_preferred"] = int(snapshot.get("floating_widget_monitor_preferred", snapshot.get("floating_widget_monitor", 1)) or 1)
        settings["floating_widget_monitor_signature"] = snapshot.get("floating_widget_monitor_signature")
        settings["floating_widget_panel_position"] = int(snapshot.get("floating_widget_panel_position", 50) or 50)
        settings["floating_widget_panel_size"] = int(snapshot.get("floating_widget_panel_size", 160) or 160)
        settings["floating_widget_panel_width"] = int(snapshot.get("floating_widget_panel_width", 860) or 860)
        settings["floating_widget_icon_size"] = int(snapshot.get("floating_widget_icon_size", 50) or 50)
        settings["floating_widget_speed"] = int(snapshot.get("floating_widget_speed", 80) or 80)
        settings["floating_widget_opacity"] = int(snapshot.get("floating_widget_opacity", 77) or 77)
        settings["floating_widget_theme"] = snapshot.get("floating_widget_theme", "dark")
        settings["floating_widget_icon_shape"] = "square"
        settings["floating_widget_show_hover_text"] = bool(snapshot.get("floating_widget_show_hover_text", True))
        settings["floating_widget_categories"] = snapshot.get("floating_widget_categories") or [key for key, _label, _icon in CATEGORY_ORDER]
        settings["sticky_memo_arrange_monitor"] = int(snapshot.get("sticky_memo_arrange_monitor", 1) or 1)
        settings["sticky_memo_arrange_monitor_preferred"] = int(snapshot.get("sticky_memo_arrange_monitor_preferred", snapshot.get("sticky_memo_arrange_monitor", 1)) or 1)
        settings["sticky_memo_arrange_monitor_signature"] = snapshot.get("sticky_memo_arrange_monitor_signature")
        settings["sticky_memo_arrange_corner"] = snapshot.get("sticky_memo_arrange_corner", "top_right")
        settings.pop("floating_widget_color", None)
        settings.pop("floating_widget_item_spacing", None)
        settings["theme"] = snapshot.get("theme", "light")
        settings["clipboard_popup_double_ctrl"] = bool(snapshot.get("clipboard_popup_double_ctrl", True))
        settings["clipboard_popup_hotkey"] = snapshot.get("clipboard_popup_hotkey")
        settings["quick_memo_double_alt"] = bool(snapshot.get("quick_memo_double_alt", True))
        settings["quick_memo_hotkey"] = snapshot.get("quick_memo_hotkey")
        settings["phrase_popup_hotkey"] = snapshot.get("phrase_popup_hotkey")
        settings["steel_cut_hotkey"] = snapshot.get("steel_cut_hotkey") or {"modifiers": ["ctrl", "shift"], "key": "S"}
        settings["screen_draw_hotkey"] = snapshot.get("screen_draw_hotkey")
        self.template_name.setText(str(snapshot.get("template_name", f"프리셋 {self.main.template_index}")))
        self.select_theme(settings.get("theme", "light"))
        self.always_on_top.setChecked(bool(snapshot.get("always_on_top", False)))
        self.clipboard_limit.setValue(int(snapshot.get("clipboard_limit", 30) or 30))
        self.auto_update_check.setChecked(bool(snapshot.get("auto_update_check", False)))
        self.auto_update_install.setChecked(True)
        self.startup_with_windows.setChecked(bool(snapshot.get("startup_with_windows", False)))
        self.set_hotkey_field(self.clipboard_popup_hotkey, snapshot.get("clipboard_popup_hotkey"))
        self.set_hotkey_field(self.quick_memo_hotkey, snapshot.get("quick_memo_hotkey"))
        self.set_hotkey_field(self.phrase_popup_hotkey, snapshot.get("phrase_popup_hotkey"))
        self.set_hotkey_field(self.steel_cut_hotkey, snapshot.get("steel_cut_hotkey") or {"modifiers": ["ctrl", "shift"], "key": "S"})
        self.set_hotkey_field(self.screen_draw_hotkey, snapshot.get("screen_draw_hotkey"))
        self.floating_widget_enabled.setChecked(bool(snapshot.get("floating_widget_enabled", True)))
        edge_index = self.floating_widget_edge.findData(snapshot.get("floating_widget_edge", "top"))
        self.floating_widget_edge.setCurrentIndex(edge_index if edge_index >= 0 else 0)
        self.refresh_widget_monitor_combo(int(snapshot.get("floating_widget_monitor", 1) or 1))
        self.set_widget_slider_value(self.floating_widget_panel_position, int(snapshot.get("floating_widget_panel_position", 50) or 50))
        self.set_widget_slider_value(self.floating_widget_panel_size, int(snapshot.get("floating_widget_panel_size", 160) or 160))
        self.set_widget_slider_value(self.floating_widget_panel_width, int(snapshot.get("floating_widget_panel_width", 860) or 860))
        self.set_widget_slider_value(self.floating_widget_icon_size, int(snapshot.get("floating_widget_icon_size", 50) or 50))
        self.set_widget_slider_value(self.floating_widget_speed, int(snapshot.get("floating_widget_speed", 80) or 80))
        self.set_widget_slider_value(self.floating_widget_opacity, int(snapshot.get("floating_widget_opacity", 77) or 77))
        theme_index = self.floating_widget_theme.findData(snapshot.get("floating_widget_theme", "dark"))
        self.floating_widget_theme.setCurrentIndex(theme_index if theme_index >= 0 else 0)
        self.floating_widget_show_hover_text.setChecked(bool(snapshot.get("floating_widget_show_hover_text", True)))
        self.sync_widget_size_sliders("discard")
        self.set_widget_categories(snapshot.get("floating_widget_categories"))
        sticky_corner_index = self.sticky_memo_arrange_corner.findData(snapshot.get("sticky_memo_arrange_corner", "top_right"))
        self.sticky_memo_arrange_corner.setCurrentIndex(sticky_corner_index if sticky_corner_index >= 0 else 0)
        self.popup_mode_double_ctrl.setChecked(bool(snapshot.get("clipboard_popup_double_ctrl", True)))
        self.popup_mode_hotkey.setChecked(not self.popup_mode_double_ctrl.isChecked())
        self.memo_mode_double_alt.setChecked(bool(snapshot.get("quick_memo_double_alt", True)))
        self.memo_mode_hotkey.setChecked(not self.memo_mode_double_alt.isChecked())
        self.update_mode_enabled()
        self._general_snapshot = self.current_general_state()
        self._settings_snapshot = self.current_settings_state()
        self._refreshing = False
        if hasattr(self.main, "apply_current_settings"):
            self.main.apply_current_settings()

    def set_hotkey_field(self, field: HotkeyFields, hotkey: dict | None) -> None:
        field.ctrl.blockSignals(True)
        field.alt.blockSignals(True)
        field.shift.blockSignals(True)
        field.key.blockSignals(True)
        field.ctrl.setChecked(False)
        field.alt.setChecked(False)
        field.shift.setChecked(False)
        if field.key.count():
            field.key.setCurrentIndex(0)
        field.ctrl.blockSignals(False)
        field.alt.blockSignals(False)
        field.shift.blockSignals(False)
        field.key.blockSignals(False)
        field.set_hotkey(hotkey)

    def show_saving_dialog(self) -> QDialog:
        dlg = QDialog(self)
        dlg.setWindowTitle("저장중")
        dlg.setModal(True)
        dlg.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        dlg.setFixedSize(240, 96)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(18, 18, 18, 18)
        label = QLabel("저장중입니다...")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size: 11pt; font-weight: 800;")
        layout.addWidget(label, 1)
        dlg.setStyleSheet(
            """
            QDialog {
                background: #FFFFFF;
                border: 1px solid #D1D5DB;
                border-radius: 10px;
            }
            QLabel { color: #111827; }
            """
        )
        dlg.show()
        QApplication.processEvents()
        return dlg

    def save_settings(self) -> bool:
        before = dict(getattr(self, "_settings_snapshot", {}) or {})
        prev_display_mode = str(before.get("sticky_memo_display_mode", "floating") or "floating")
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
        settings["steel_cut_capture_mode"] = "region"
        settings["floating_widget_enabled"] = self.floating_widget_enabled.isChecked()
        settings["floating_widget_edge"] = self.floating_widget_edge.currentData()
        floating_monitor = int(self.floating_widget_monitor.currentData() or 1)
        settings["floating_widget_monitor"] = floating_monitor
        settings["floating_widget_monitor_preferred"] = floating_monitor
        settings["floating_widget_monitor_signature"] = signature_for_monitor_index(floating_monitor) or settings.get("floating_widget_monitor_signature")
        settings["floating_widget_panel_position"] = self.widget_slider_value(self.floating_widget_panel_position, 50)
        settings["floating_widget_panel_size"] = self.widget_slider_value(self.floating_widget_panel_size, 160)
        settings["floating_widget_panel_width"] = self.widget_slider_value(self.floating_widget_panel_width, 860)
        settings["floating_widget_icon_size"] = self.widget_slider_value(self.floating_widget_icon_size, 50)
        settings["floating_widget_speed"] = self.widget_slider_value(self.floating_widget_speed, 80)
        settings["floating_widget_opacity"] = self.widget_slider_value(self.floating_widget_opacity, 77)
        settings["floating_widget_theme"] = self.floating_widget_theme.currentData()
        settings["floating_widget_icon_shape"] = "square"
        settings["floating_widget_show_hover_text"] = self.floating_widget_show_hover_text.isChecked()
        settings["floating_widget_categories"] = self.widget_categories_value()
        sticky_monitor = int(self.sticky_memo_arrange_monitor.currentData() or 1)
        settings["sticky_memo_arrange_monitor"] = sticky_monitor
        settings["sticky_memo_arrange_monitor_preferred"] = sticky_monitor
        settings["sticky_memo_arrange_monitor_signature"] = signature_for_monitor_index(sticky_monitor) or settings.get("sticky_memo_arrange_monitor_signature")
        settings["sticky_memo_arrange_corner"] = self.sticky_memo_arrange_corner.currentData()
        settings["sticky_memo_display_mode"] = "index" if (hasattr(self, "memo_display_index") and self.memo_display_index.isChecked()) else "floating"
        settings["sticky_memo_index_side"] = "left" if (hasattr(self, "memo_index_side_left") and self.memo_index_side_left.isChecked()) else "right"
        settings["sticky_memo_index_start_y"] = self.widget_slider_value(self.memo_index_start_y, 0) if hasattr(self, "memo_index_start_y") else 0
        settings.pop("floating_widget_color", None)
        settings.pop("floating_widget_item_spacing", None)
        settings["screen_draw_hotkey"] = self.screen_draw_hotkey.value()
        settings["auto_update_check"] = self.auto_update_check.isChecked()
        settings["auto_update_install"] = True
        settings["startup_with_windows"] = self.startup_with_windows.isChecked()
        settings["active_preset"] = self.main.template_index
        window["always_on_top"] = self.always_on_top.isChecked()
        conflict = self.main.first_hotkey_conflict()
        if conflict:
            show_modern_warning(self, "단축키 충돌", conflict)
            return False
        for hotkey in [
            settings.get("clipboard_popup_hotkey"),
            settings.get("quick_memo_hotkey"),
            settings.get("phrase_popup_hotkey"),
            settings.get("steel_cut_hotkey"),
            settings.get("screen_draw_hotkey"),
        ]:
            if not confirm_shift_digit_hotkey(self, hotkey):
                return False
        current = self.current_settings_state()
        visual_keys = {
            "theme",
            "always_on_top",
            "floating_widget_enabled",
            "floating_widget_edge",
            "floating_widget_monitor",
            "floating_widget_monitor_preferred",
            "floating_widget_monitor_signature",
            "floating_widget_panel_position",
            "floating_widget_panel_size",
            "floating_widget_panel_width",
            "floating_widget_icon_size",
            "floating_widget_speed",
            "floating_widget_opacity",
            "floating_widget_theme",
            "floating_widget_show_hover_text",
            "floating_widget_categories",
            "sticky_memo_arrange_monitor",
            "sticky_memo_arrange_monitor_preferred",
            "sticky_memo_arrange_monitor_signature",
            "sticky_memo_arrange_corner",
            "sticky_memo_display_mode",
            "sticky_memo_index_side",
            "sticky_memo_index_start_y",
        }
        hotkey_keys = {
            "clipboard_popup_double_ctrl",
            "clipboard_popup_hotkey",
            "quick_memo_double_alt",
            "quick_memo_hotkey",
            "phrase_popup_hotkey",
            "steel_cut_hotkey",
            "screen_draw_hotkey",
        }
        template_name_changed = before.get("template_name") != current.get("template_name")
        visual_changed = any(before.get(key) != current.get(key) for key in visual_keys)
        hotkeys_changed = any(before.get(key) != current.get(key) for key in hotkey_keys)
        startup_changed = before.get("startup_with_windows") != current.get("startup_with_windows")
        saving_dialog = self.show_saving_dialog()
        try:
            if startup_changed:
                set_startup_enabled(self.startup_with_windows.isChecked())
            config.save_settings(settings)
            if template_name_changed:
                config.save_template(self.main.template_index, self.main.data)
                self.refresh_template_combo()
            if visual_changed:
                self.main.apply_current_settings()
            if hotkeys_changed:
                self.main.register_hotkeys()
            self.main.refresh_home_tab()
            new_display_mode = str(settings.get("sticky_memo_display_mode", "floating") or "floating")
            if prev_display_mode != new_display_mode:
                memo_tab = self._get_memo_tab()
                if memo_tab is not None:
                    memo_tab.reopen_stickers_for_mode()
                    if prev_display_mode == "index" and new_display_mode == "floating":
                        memo_tab.collapse_all_stickers()
                        memo_tab.arrange_compact_stickers()
            elif any(before.get(key) != current.get(key) for key in {
                "sticky_memo_arrange_monitor",
                "sticky_memo_arrange_corner",
                "sticky_memo_index_side",
                "sticky_memo_index_start_y",
            }):
                memo_tab = self._get_memo_tab()
                if memo_tab is not None:
                    memo_tab.arrange_compact_stickers()
            self._general_snapshot = self.current_general_state()
            self._settings_snapshot = self.current_settings_state()
        except Exception as exc:
            saving_dialog.close()
            QApplication.processEvents()
            show_modern_warning(self, "저장 실패", str(exc))
            return False
        finally:
            if saving_dialog.isVisible():
                saving_dialog.close()
                QApplication.processEvents()
        show_modern_info(self, "저장 완료", "저장 완료되었습니다.")
        return True

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
        path, _ = QFileDialog.getOpenFileName(self, "가져오기", "", "JSON (*.json)")
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
        self.main.settings["screen_draw_hotkey"] = None
        for key in ("mouse_highlight_color", "mouse_highlight_shape", "mouse_highlight_size", "mouse_highlight_opacity"):
            self.main.settings[key] = config.DEFAULT_SETTINGS[key]
        for key in (
            "floating_widget_enabled",
            "floating_widget_edge",
            "floating_widget_monitor",
            "floating_widget_monitor_preferred",
            "floating_widget_panel_position",
            "floating_widget_panel_size",
            "floating_widget_panel_width",
            "floating_widget_icon_size",
            "floating_widget_speed",
            "floating_widget_opacity",
            "floating_widget_theme",
            "floating_widget_icon_shape",
            "floating_widget_show_hover_text",
            "floating_widget_categories",
            "sticky_memo_arrange_monitor",
            "sticky_memo_arrange_monitor_preferred",
            "sticky_memo_arrange_corner",
        ):
            value = config.DEFAULT_SETTINGS.get(key)
            self.main.settings[key] = list(value) if isinstance(value, list) else value
        self.main.settings.pop("floating_widget_color", None)
        self.main.settings.pop("floating_widget_item_spacing", None)
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

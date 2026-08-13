from __future__ import annotations

"""'단축키 / 매크로' 통합 탭 — 프로그램별 단축키(전용 단축키) + 매크로를 한 메뉴로 묶는다."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QTabWidget, QVBoxLayout, QWidget


class HotkeyMacroTab(QWidget):
    def __init__(self, process_hotkey_tab: QWidget, macro_tab: QWidget) -> None:
        super().__init__()
        self.process_hotkey_tab = process_hotkey_tab
        self.macro_tab = macro_tab
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        self.tabs.addTab(process_hotkey_tab, "프로그램별 단축키")
        self.tabs.addTab(macro_tab, "매크로")

        # 각 하위 탭의 검색/정렬 컨트롤을 이 탭의 탭바 코너로 끌어올려, 다른 메뉴들처럼
        # 검색/정렬이 탭바와 같은 줄에 오도록 맞춘다(하위 탭 내부에 별도 줄로 두면 한 칸
        # 아래로 밀려 보인다).
        corner = QWidget()
        corner_layout = QHBoxLayout(corner)
        corner_layout.setContentsMargins(0, 0, 0, 0)
        corner_layout.setSpacing(0)
        corner_layout.addWidget(process_hotkey_tab.corner_widget)
        corner_layout.addWidget(macro_tab.corner_widget)
        self.tabs.setCornerWidget(corner, Qt.Corner.TopRightCorner)
        self.tabs.currentChanged.connect(self._sync_corner)
        self._sync_corner(self.tabs.currentIndex())

        layout.addWidget(self.tabs, 1)

    def _sync_corner(self, index: int) -> None:
        self.process_hotkey_tab.corner_widget.setVisible(index == 0)
        self.macro_tab.corner_widget.setVisible(index == 1)

    def refresh(self) -> None:
        for tab in (self.process_hotkey_tab, self.macro_tab):
            if hasattr(tab, "refresh"):
                tab.refresh()

    def apply_theme(self) -> None:
        for tab in (self.process_hotkey_tab, self.macro_tab):
            if hasattr(tab, "apply_theme"):
                tab.apply_theme()

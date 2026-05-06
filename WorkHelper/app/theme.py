from __future__ import annotations

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication


THEMES = {
    "light": """
        QWidget { background: #EEF0F3; color: #1F2433; selection-background-color: #3B6CF5; selection-color: #FFFFFF; }
        QWidget#appShell { background: #FFFFFF; border: 1px solid #CBD0D9; border-radius: 8px; }
        QWidget#sideBar { background: #FFFFFF; border-right: 1px solid #E2E5EB; }
        QWidget#sideHeader { background: #FFFFFF; border-bottom: 1px solid #E2E5EB; }
        QWidget#sideFooter { background: #F7F8FA; border-top: 1px solid #E2E5EB; }
        QWidget#contentArea { background: #F7F8FA; }
        QWidget#screenHeader { background: #FFFFFF; border-bottom: 1px solid #E2E5EB; }
        QLabel { background: transparent; }
        QLabel#eyebrow { color: #818797; font-size: 9pt; font-weight: 700; }
        QLabel#windowTitle, QLabel#screenTitle { color: #1F2433; font-weight: 800; }
        QLabel#screenSubtitle, QLabel#mutedText { color: #818797; }
        QLabel#statusPill { background: #FFFFFF; color: #2EA672; border: 1px solid #CDEBDD; border-radius: 6px; padding: 4px 9px; font-weight: 800; }
        QLabel#statusPillInactive { background: #FFFFFF; color: #D99229; border: 1px solid #F0D8B4; border-radius: 6px; padding: 4px 9px; font-weight: 800; }
        QLabel#cardTitle { color: #1F2433; font-weight: 700; }
        QLabel#cardSubtitle { color: #4A5163; }
        QLabel#kbd {
            color: #4A5163; background: #F7F8FA; border: 1px solid #E2E5EB;
            border-bottom: 2px solid #CBD0D9; border-radius: 4px; padding: 3px 8px;
            font-family: Consolas, "Courier New"; font-weight: 700;
            min-height: 18px;
        }
        QWidget#card {
            background: #FFFFFF; border: 1px solid #E2E5EB; border-radius: 8px;
        }
        QWidget#card:hover { border-color: #CBD0D9; }
        QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDateTimeEdit {
            background: #FFFFFF; border: 1px solid #E2E5EB; border-radius: 6px; padding: 7px 10px;
            color: #1F2433;
        }
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDateTimeEdit:focus {
            border-color: #3B6CF5;
        }
        QPushButton {
            background: #FFFFFF; border: 1px solid #E2E5EB; border-radius: 6px;
            padding: 6px 12px; color: #4A5163; font-weight: 700;
        }
        QPushButton:hover { background: #F7F8FA; border-color: #CBD0D9; }
        QPushButton:pressed { background: #EEF2FF; }
        QToolButton#iconButton {
            background: #FFFFFF; border: 1px solid #E2E5EB; border-radius: 6px;
            min-width: 28px; min-height: 26px; max-height: 26px; padding: 0;
            color: #4A5163;
        }
        QToolButton#iconButton:hover { background: #F7F8FA; border-color: #CBD0D9; }
        QToolButton#dangerIconButton {
            background: #FFFFFF; border: 1px solid #F0C4CA; border-radius: 6px;
            min-width: 28px; min-height: 26px; max-height: 26px; padding: 0;
            color: #E25C6C;
        }
        QToolButton#dangerIconButton:hover { background: #FDF0F2; }
        QToolButton#navButton {
            background: transparent; border: 0; border-left: 3px solid transparent;
            border-radius: 6px; padding: 0 12px; color: #1F2433; text-align: left;
            font-weight: 700;
        }
        QToolButton#navButton:hover { background: #F7F8FA; }
        QToolButton#navButton:checked {
            background: #EEF2FF; border-left-color: #3B6CF5; color: #3B6CF5;
        }
        QTabWidget::pane { border: 0; background: transparent; }
        QTabBar::tab {
            background: transparent; color: #818797; padding: 7px 10px;
            border: 0; border-bottom: 2px solid transparent; font-weight: 700;
        }
        QTabBar::tab:selected { color: #3B6CF5; border-bottom-color: #3B6CF5; }
        QTabBar::tab:hover { color: #4A5163; }
        QComboBox {
            combobox-popup: 0;
            padding-right: 26px;
        }
        QComboBox::drop-down {
            border: 0; width: 24px; subcontrol-origin: padding; subcontrol-position: top right;
            background: transparent;
        }
        QComboBox::down-arrow {
            image: none; border: 0; width: 0; height: 0;
            border-left: 4px solid transparent; border-right: 4px solid transparent;
            border-top: 5px solid #818797; margin-right: 9px;
        }
        QComboBox QAbstractItemView {
            background: #FFFFFF; border: 1px solid #E2E5EB; border-radius: 6px;
            selection-background-color: #EEF2FF; selection-color: #3B6CF5;
            padding: 4px;
        }
        QSpinBox::up-button, QSpinBox::down-button, QDateTimeEdit::up-button, QDateTimeEdit::down-button {
            border: 0; background: transparent; width: 18px;
        }
        QSpinBox::up-arrow, QDateTimeEdit::up-arrow {
            image: none; width: 0; height: 0; border-left: 4px solid transparent;
            border-right: 4px solid transparent; border-bottom: 5px solid #818797;
        }
        QSpinBox::down-arrow, QDateTimeEdit::down-arrow {
            image: none; width: 0; height: 0; border-left: 4px solid transparent;
            border-right: 4px solid transparent; border-top: 5px solid #818797;
        }
        QListWidget {
            background: transparent; border: none; outline: 0;
        }
        QListWidget::item { border: 0; padding: 4px; }
        QListWidget::item:selected { background: transparent; }
        QTableWidget {
            background: #FFFFFF; border: 1px solid #E2E5EB; border-radius: 8px; gridline-color: #E2E5EB;
        }
        QHeaderView::section {
            background: #F7F8FA; color: #818797; border: 0; border-bottom: 1px solid #E2E5EB;
            padding: 6px; font-weight: 700;
        }
        QScrollBar:vertical { background: transparent; width: 8px; margin: 2px; }
        QScrollBar::handle:vertical { background: #CBD0D9; border-radius: 4px; min-height: 24px; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
    """,
    "dark": """
        QWidget { background: #202124; color: #F1F3F4; }
        QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDateTimeEdit {
            background: #2B2C30; border: 1px solid #555860; border-radius: 6px; padding: 6px;
        }
        QPushButton { background: #2B2C30; border: 1px solid #5F6368; border-radius: 6px; padding: 6px 8px; }
        QPushButton:hover, QPushButton:checked { background: #374151; }
        QListWidget { background: transparent; border: none; }
    """,
    "blue": """
        QWidget { background: #F3F7FB; color: #17324D; }
        QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDateTimeEdit, QPushButton {
            background: #FFFFFF; border: 1px solid #B8C7D9; border-radius: 6px; padding: 6px;
        }
        QPushButton:hover, QPushButton:checked { background: #DCEBFA; }
        QListWidget { background: transparent; border: none; }
    """,
    "green": """
        QWidget { background: #F3F8F4; color: #163B2A; }
        QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDateTimeEdit, QPushButton {
            background: #FFFFFF; border: 1px solid #BCD2C4; border-radius: 6px; padding: 6px;
        }
        QPushButton:hover, QPushButton:checked { background: #DDF1E4; }
        QListWidget { background: transparent; border: none; }
    """,
    "warm": """
        QWidget { background: #FAF6F0; color: #3A2A1B; }
        QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDateTimeEdit, QPushButton {
            background: #FFFFFF; border: 1px solid #D8C7B6; border-radius: 6px; padding: 6px;
        }
        QPushButton:hover, QPushButton:checked { background: #F4E5D3; }
        QListWidget { background: transparent; border: none; }
    """,
    "dark_red": """
        QWidget { background: #272323; color: #FFECEC; }
        QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDateTimeEdit, QPushButton {
            background: #332C2C; border: 1px solid #6F4B4B; border-radius: 6px; padding: 6px;
        }
        QPushButton:hover, QPushButton:checked { background: #513737; }
        QListWidget { background: transparent; border: none; }
    """,
}


def apply_theme(app: QApplication, theme: str, font_family: str, font_size: int) -> None:
    app.setStyleSheet(THEMES.get(theme, THEMES["light"]))
    app.setFont(QFont(font_family or "맑은 고딕", int(font_size or 9)))

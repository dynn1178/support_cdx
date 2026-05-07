from __future__ import annotations

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication


THEMES = {
    "light": {
        "bg": "#EEF0F3",
        "panel": "#FFFFFF",
        "content": "#F7F8FA",
        "text": "#1F2433",
        "muted": "#6B7280",
        "border": "#B9C0CC",
        "field": "#FFFFFF",
        "hover": "#EEF2FF",
        "accent": "#3B6CF5",
        "danger": "#E25C6C",
    },
    "dark": {
        "bg": "#202124",
        "panel": "#2B2C30",
        "content": "#242529",
        "text": "#F1F3F4",
        "muted": "#B8BDC7",
        "border": "#6E7480",
        "field": "#303136",
        "hover": "#3A3D45",
        "accent": "#7AA2FF",
        "danger": "#FF7B8A",
    },
    "blue": {
        "bg": "#F3F7FB",
        "panel": "#FFFFFF",
        "content": "#EEF5FC",
        "text": "#17324D",
        "muted": "#52677D",
        "border": "#91A9C2",
        "field": "#FFFFFF",
        "hover": "#DCEBFA",
        "accent": "#2F72B8",
        "danger": "#D94D5E",
    },
    "green": {
        "bg": "#F3F8F4",
        "panel": "#FFFFFF",
        "content": "#EEF7F0",
        "text": "#163B2A",
        "muted": "#557064",
        "border": "#8FAE9B",
        "field": "#FFFFFF",
        "hover": "#DDF1E4",
        "accent": "#2E8A57",
        "danger": "#CF4D5B",
    },
    "warm": {
        "bg": "#FAF6F0",
        "panel": "#FFFFFF",
        "content": "#F5EFE7",
        "text": "#3A2A1B",
        "muted": "#756554",
        "border": "#BCA68F",
        "field": "#FFFFFF",
        "hover": "#F4E5D3",
        "accent": "#B66A25",
        "danger": "#C94F5E",
    },
    "dark_red": {
        "bg": "#272323",
        "panel": "#332C2C",
        "content": "#2B2525",
        "text": "#FFECEC",
        "muted": "#D4B8B8",
        "border": "#8F6666",
        "field": "#3A3030",
        "hover": "#513737",
        "accent": "#FF8A8A",
        "danger": "#FF7B8A",
    },
    "mono": {
        "bg": "#F1F2F4",
        "panel": "#FFFFFF",
        "content": "#F7F7F8",
        "text": "#202124",
        "muted": "#60646C",
        "border": "#AEB4BE",
        "field": "#FFFFFF",
        "hover": "#E9EBEF",
        "accent": "#4B5563",
        "danger": "#C24150",
    },
    "mint": {
        "bg": "#EEF8F6",
        "panel": "#FFFFFF",
        "content": "#F5FBFA",
        "text": "#123A35",
        "muted": "#5E7772",
        "border": "#8DBDB4",
        "field": "#FFFFFF",
        "hover": "#DDF3EE",
        "accent": "#168A7A",
        "danger": "#D04F62",
    },
    "lavender": {
        "bg": "#F5F3FA",
        "panel": "#FFFFFF",
        "content": "#FAF9FD",
        "text": "#2F2942",
        "muted": "#6C6680",
        "border": "#AAA0C8",
        "field": "#FFFFFF",
        "hover": "#ECE7F8",
        "accent": "#7257B5",
        "danger": "#C84F70",
    },
    "graphite": {
        "bg": "#1F2328",
        "panel": "#2B3036",
        "content": "#252A30",
        "text": "#F2F4F7",
        "muted": "#B8C0CC",
        "border": "#737D8C",
        "field": "#333940",
        "hover": "#3A414A",
        "accent": "#7BC7E8",
        "danger": "#FF7B8A",
    },
    "high_contrast": {
        "bg": "#FFFFFF",
        "panel": "#FFFFFF",
        "content": "#F6F6F6",
        "text": "#000000",
        "muted": "#3A3A3A",
        "border": "#000000",
        "field": "#FFFFFF",
        "hover": "#E6F0FF",
        "accent": "#005FCC",
        "danger": "#B00020",
    },
}


def build_stylesheet(colors: dict[str, str]) -> str:
    return f"""
        QWidget {{
            background: {colors["bg"]}; color: {colors["text"]};
            selection-background-color: {colors["accent"]}; selection-color: #FFFFFF;
        }}
        QWidget#appShell {{
            background: {colors["panel"]}; border: 1px solid {colors["border"]}; border-radius: 8px;
        }}
        QWidget#sideBar, QWidget#sideHeader, QWidget#screenHeader {{
            background: {colors["panel"]}; border-color: {colors["border"]};
        }}
        QWidget#sideBar {{ border-right: 1px solid {colors["border"]}; }}
        QWidget#sideHeader, QWidget#screenHeader {{ border-bottom: 1px solid {colors["border"]}; }}
        QWidget#sideFooter, QWidget#contentArea {{ background: {colors["content"]}; }}
        QWidget#sideFooter {{ border-top: 1px solid {colors["border"]}; }}
        QLabel {{ background: transparent; }}
        QLabel#eyebrow, QLabel#screenSubtitle, QLabel#mutedText {{ color: {colors["muted"]}; }}
        QLabel#windowTitle, QLabel#screenTitle, QLabel#cardTitle {{ color: {colors["text"]}; font-weight: 800; }}
        QLabel#cardSubtitle {{ color: {colors["muted"]}; }}
        QLabel#statusPill {{
            background: {colors["panel"]}; color: #2EA672; border: 1px solid {colors["border"]};
            border-radius: 6px; padding: 4px 9px; font-weight: 800;
        }}
        QLabel#statusPillInactive {{
            background: {colors["panel"]}; color: #D99229; border: 1px solid {colors["border"]};
            border-radius: 6px; padding: 4px 9px; font-weight: 800;
        }}
        QLabel#kbd {{
            color: {colors["text"]}; background: {colors["content"]}; border: 1px solid {colors["border"]};
            border-bottom: 2px solid {colors["border"]}; border-radius: 4px; padding: 3px 8px;
            font-family: Consolas, "Courier New"; font-weight: 700; min-height: 18px;
        }}
        QWidget#card {{
            background: {colors["panel"]}; border: 1px solid {colors["border"]}; border-radius: 8px;
        }}
        QWidget#card:hover {{ border-color: {colors["accent"]}; }}
        QWidget#card[dragging="true"] {{ border: 2px dashed {colors["accent"]}; }}
        QWidget#sortControls {{
            background: {colors["panel"]}; border: 1px solid {colors["border"]}; border-radius: 7px;
        }}
        QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDateEdit, QTimeEdit, QDateTimeEdit {{
            background: {colors["field"]}; border: 1px solid {colors["border"]}; border-radius: 6px;
            padding: 7px 10px; color: {colors["text"]}; min-height: 20px;
        }}
        QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{
            background: #D1D5DB; color: #6B7280; border-color: #9CA3AF;
        }}
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus, QTimeEdit:focus, QDateTimeEdit:focus {{
            border-color: {colors["accent"]};
        }}
        QPushButton {{
            background: {colors["panel"]}; border: 1px solid {colors["border"]}; border-radius: 6px;
            padding: 6px 12px; color: {colors["text"]}; font-weight: 700; min-height: 22px;
        }}
        QPushButton:hover {{ background: {colors["hover"]}; border-color: {colors["accent"]}; }}
        QPushButton:pressed {{ background: {colors["content"]}; }}
        QToolButton#iconButton, QToolButton#dangerIconButton {{
            background: transparent; border: 0; border-radius: 4px; padding: 0;
            min-width: 30px; min-height: 28px; max-width: 30px; max-height: 28px; font-size: 12pt;
        }}
        QToolButton#iconButton:hover {{ background: {colors["hover"]}; }}
        QToolButton#dangerIconButton {{ color: {colors["danger"]}; }}
        QToolButton#dangerIconButton:hover {{ background: {colors["hover"]}; }}
        QToolButton#navButton {{
            background: transparent; border: 0; border-left: 3px solid transparent;
            border-radius: 6px; padding: 0 12px; color: {colors["text"]}; text-align: left; font-weight: 700;
        }}
        QToolButton#navButton:hover {{ background: {colors["hover"]}; }}
        QToolButton#navButton:checked {{
            background: {colors["hover"]}; border-left-color: {colors["accent"]}; color: {colors["accent"]};
        }}
        QTabWidget::pane {{ border: 0; background: transparent; }}
        QTabBar::tab {{
            background: transparent; color: {colors["muted"]}; padding: 7px 10px;
            border: 0; border-bottom: 2px solid transparent; font-weight: 700; min-height: 20px;
        }}
        QTabBar::tab:selected {{ color: {colors["accent"]}; border-bottom-color: {colors["accent"]}; }}
        QTabBar::tab:hover {{ color: {colors["text"]}; }}
        QCheckBox, QRadioButton {{ spacing: 7px; background: transparent; }}
        QCheckBox::indicator {{
            width: 15px; height: 15px; border: 2px solid {colors["border"]}; border-radius: 3px;
            background: {colors["field"]};
        }}
        QRadioButton::indicator {{
            width: 15px; height: 15px; border: 2px solid {colors["border"]}; border-radius: 8px;
            background: {colors["field"]};
        }}
        QCheckBox::indicator:hover, QRadioButton::indicator:hover {{ border-color: {colors["accent"]}; }}
        QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
            background: {colors["accent"]}; border-color: {colors["accent"]};
        }}
        QComboBox {{ combobox-popup: 0; padding-right: 10px; }}
        QComboBox::drop-down {{ border: 0; background: transparent; width: 0; }}
        QComboBox::down-arrow {{ image: none; border: 0; width: 0; height: 0; background: transparent; }}
        QComboBox QAbstractItemView {{
            background: {colors["panel"]}; border: 1px solid {colors["border"]}; border-radius: 6px;
            selection-background-color: {colors["hover"]}; selection-color: {colors["accent"]}; padding: 4px;
        }}
        QSpinBox::up-button, QSpinBox::down-button, QDateEdit::up-button, QDateEdit::down-button, QTimeEdit::up-button, QTimeEdit::down-button, QDateTimeEdit::up-button, QDateTimeEdit::down-button {{
            border: 0; background: transparent; width: 0;
        }}
        QSpinBox::up-arrow, QSpinBox::down-arrow, QDateEdit::up-arrow, QDateEdit::down-arrow, QTimeEdit::up-arrow, QTimeEdit::down-arrow, QDateTimeEdit::up-arrow, QDateTimeEdit::down-arrow {{
            image: none; border: 0; width: 0; height: 0; background: transparent;
        }}
        QTableWidget {{
            background: {colors["panel"]}; border: 1px solid {colors["border"]}; border-radius: 8px; gridline-color: {colors["border"]};
        }}
        QHeaderView::section {{
            background: {colors["content"]}; color: {colors["muted"]}; border: 0;
            border-bottom: 1px solid {colors["border"]}; padding: 4px 6px; font-weight: 600;
        }}
        QListWidget {{ background: transparent; border: none; outline: 0; }}
        QListWidget::item {{ border: 0; padding: 4px; }}
        QListWidget::item:selected {{ background: transparent; }}
        QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
        QScrollBar::handle:vertical {{ background: {colors["border"]}; border-radius: 4px; min-height: 24px; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; border: 0; background: transparent; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
        QScrollBar:horizontal {{ background: transparent; height: 8px; margin: 0; }}
        QScrollBar::handle:horizontal {{ background: {colors["border"]}; border-radius: 4px; min-width: 24px; }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; border: 0; background: transparent; }}
    """


def apply_theme(app: QApplication, theme: str, font_family: str, font_size: int) -> None:
    app.setStyleSheet(build_stylesheet(THEMES.get(theme, THEMES["light"])))
    app.setFont(QFont(font_family or "Malgun Gothic", int(font_size or 9)))

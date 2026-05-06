from __future__ import annotations

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication


THEMES = {
    "light": """
        QWidget { background: #F7F7F5; color: #222222; }
        QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDateTimeEdit {
            background: #FFFFFF; border: 1px solid #D0D5DD; border-radius: 6px; padding: 6px;
        }
        QPushButton { background: #FFFFFF; border: 1px solid #C9CED6; border-radius: 6px; padding: 6px 8px; }
        QPushButton:hover { background: #EEF4FF; }
        QPushButton:checked { background: #D8E7FF; border-color: #4F7DB8; }
        QTabBar::tab { padding: 6px 8px; }
        QListWidget { background: transparent; border: none; }
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


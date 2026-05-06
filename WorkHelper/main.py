from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from app import config
from ui.main_window import MainWindow


def main() -> int:
    config.ensure_data_files()
    app = QApplication(sys.argv)
    window = MainWindow(app)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())


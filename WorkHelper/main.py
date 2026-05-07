from __future__ import annotations

import sys

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from app import config
from ui.main_window import MainWindow


def main() -> int:
    config.ensure_data_files()
    app = QApplication(sys.argv)
    icon_path = config.APP_ICON_PATH if config.APP_ICON_PATH.exists() else config.BUNDLED_ICON_PATH
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    window = MainWindow(app)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

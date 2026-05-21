from __future__ import annotations

import ctypes
import sys

from PyQt6.QtCore import qInstallMessageHandler
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import QApplication

from app import config


def enable_dpi_awareness() -> None:
    if not sys.platform.startswith("win"):
        return
    try:
        # PER_MONITOR_AWARE_V2 keeps screen geometry and captured pixels aligned
        # on mixed-DPI Windows setups.
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def qt_message_handler(_mode, _context, message: str) -> None:
    if (
        "DirectWrite: CreateFontFaceFromHDC() failed" in message
        and 'Family="Fixedsys"' in message
    ):
        return
    sys.stderr.write(f"{message}\n")


def main() -> int:
    enable_dpi_awareness()
    config.ensure_data_files()
    qInstallMessageHandler(qt_message_handler)
    QFont.insertSubstitution("Fixedsys", "Consolas")
    QFont.insertSubstitution("Terminal", "Consolas")
    app = QApplication(sys.argv)
    app.setFont(QFont("Malgun Gothic", 9))
    from ui.main_window import MainWindow

    icon_path = config.APP_ICON_PATH if config.APP_ICON_PATH.exists() else config.BUNDLED_ICON_PATH
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    window = MainWindow(app)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

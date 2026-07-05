from __future__ import annotations

import logging
import logging.handlers
import sys

from .utils import app_base_dir

LOG_DIR = app_base_dir() / "logs"
LOG_PATH = LOG_DIR / "app.log"

_ROOT_NAME = "workhelper"
_configured = False


def setup_logging() -> None:
    """회전 파일 핸들러로 앱 전역 로거를 구성한다. 여러 번 호출해도 안전."""
    global _configured
    if _configured:
        return
    _configured = True
    root = logging.getLogger(_ROOT_NAME)
    root.setLevel(logging.DEBUG)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            LOG_PATH, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
        )
        root.addHandler(handler)
    except Exception:
        # 로그 디렉터리를 만들 수 없는 환경(읽기 전용 등)에서도 앱은 떠야 한다.
        root.addHandler(logging.NullHandler())


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(f"{_ROOT_NAME}.{name}")


def install_excepthook() -> None:
    """처리되지 않은 예외를 로그 파일에 남긴다(기존 훅은 유지)."""
    logger = get_logger("unhandled")
    previous = sys.excepthook

    def hook(exc_type, exc_value, exc_tb) -> None:
        try:
            logger.error("unhandled exception", exc_info=(exc_type, exc_value, exc_tb))
        except Exception:
            pass
        previous(exc_type, exc_value, exc_tb)

    sys.excepthook = hook

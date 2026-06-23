from __future__ import annotations

import ctypes
import sys

from PyQt6.QtCore import QRect
from PyQt6.QtWidgets import QApplication


def qt_virtual_screen_geometry() -> QRect:
    """Union of currently connected screens only.

    Seeding from primaryScreen().virtualGeometry() previously kept a
    disconnected monitor's bounds alive (Qt's cached virtual-desktop value
    can lag a screenRemoved event), which inflated the rect with a phantom
    region and shifted/cropped screenshots after a monitor was unplugged.
    """
    rect = QRect()
    for item in QApplication.screens():
        rect = rect.united(item.geometry()) if not rect.isNull() else QRect(item.geometry())
    return rect


def win32_virtual_screen_geometry() -> QRect:
    if not sys.platform.startswith("win"):
        return QRect()
    try:
        user32 = ctypes.windll.user32
        left = int(user32.GetSystemMetrics(76))  # SM_XVIRTUALSCREEN
        top = int(user32.GetSystemMetrics(77))  # SM_YVIRTUALSCREEN
        width = int(user32.GetSystemMetrics(78))  # SM_CXVIRTUALSCREEN
        height = int(user32.GetSystemMetrics(79))  # SM_CYVIRTUALSCREEN
    except Exception:
        return QRect()
    if width <= 0 or height <= 0:
        return QRect()
    return QRect(left, top, width, height)


def virtual_screen_geometry() -> QRect:
    """Return the full desktop bounds, including negative and stacked monitors.

    Qt's per-screen geometry() is always in device-independent (logical) pixels,
    matching QCursor.pos() and every widget geometry in this app. win32's
    GetSystemMetrics(SM_*VIRTUALSCREEN) returns raw physical pixels instead, so
    unioning the two on any monitor with DPI scaling != 100% inflates the rect
    (e.g. a single 150%-scaled 1280x720 logical screen reports as 1920x1080),
    which made capture overlays and the mouse highlight render oversized.
    Only fall back to the win32 metrics when Qt reports no screens at all.
    """
    rect = qt_virtual_screen_geometry()
    if not rect.isNull():
        return rect
    return win32_virtual_screen_geometry()


def screen_signature(screen) -> dict:
    """Return a stable-enough monitor signature for reconnect matching."""
    geo = screen.geometry()
    available = screen.availableGeometry()
    parts = []
    for attr in ("name", "manufacturer", "model", "serialNumber"):
        try:
            value = getattr(screen, attr)()
        except Exception:
            value = ""
        parts.append(str(value or "").strip())
    return {
        "name": parts[0],
        "manufacturer": parts[1],
        "model": parts[2],
        "serial": parts[3],
        "geometry": [geo.x(), geo.y(), geo.width(), geo.height()],
        "available": [available.x(), available.y(), available.width(), available.height()],
    }


def current_screen_signatures() -> list[dict]:
    return [screen_signature(screen) for screen in QApplication.screens()]


def signature_score(saved: dict | None, current: dict) -> int:
    if not isinstance(saved, dict):
        return 0
    score = 0
    for key, weight in (("serial", 80), ("name", 35), ("model", 30), ("manufacturer", 15)):
        if saved.get(key) and saved.get(key) == current.get(key):
            score += weight
    if saved.get("geometry") == current.get("geometry"):
        score += 25
    if saved.get("available") == current.get("available"):
        score += 10
    return score


def find_screen_index_by_signature(saved: dict | None, minimum_score: int = 35) -> int | None:
    best_index = None
    best_score = 0
    for index, current in enumerate(current_screen_signatures(), start=1):
        score = signature_score(saved, current)
        if score > best_score:
            best_index = index
            best_score = score
    return best_index if best_index is not None and best_score >= minimum_score else None


def signature_for_monitor_index(index: int) -> dict | None:
    screens = QApplication.screens()
    if not screens:
        return None
    index = int(index or 1)
    if index < 1 or index > len(screens):
        return None
    return screen_signature(screens[index - 1])


def restore_monitor_from_signature(settings: dict, monitor_key: str, signature_key: str) -> bool:
    matched = find_screen_index_by_signature(settings.get(signature_key))
    if matched is None:
        return False
    if int(settings.get(monitor_key, 1) or 1) == matched:
        return False
    settings[monitor_key] = matched
    return True

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime
from pathlib import Path


def app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def bundled_resource_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).resolve()
    return app_base_dir()


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def resolve_image_path(path: str, base_dir: str | Path | None = None) -> str:
    if not path:
        return ""
    if os.path.isabs(path):
        return path
    root = Path(base_dir) if base_dir else app_base_dir()
    return str((root / path).resolve())


def short_preview(text: str, limit: int = 120) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1] + "..."


def normalize_hotkey(hotkey: dict | None) -> str:
    if not hotkey:
        return ""
    modifiers = hotkey.get("modifiers", [])
    key = hotkey.get("key", "")
    return "+".join([m.title() for m in modifiers] + ([key] if key else []))


def display_hotkey(hotkey: dict | None) -> str:
    if not hotkey:
        return ""
    aliases = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift"}
    modifiers = [aliases.get(str(modifier).lower(), str(modifier).title()) for modifier in hotkey.get("modifiers", [])]
    key = hotkey.get("key", "")
    return "+".join(modifiers + ([key] if key else []))


def hotkey_to_keyboard_string(hotkey: dict | None) -> str:
    if not hotkey:
        return ""
    modifiers = [m.lower() for m in hotkey.get("modifiers", [])]
    key = str(hotkey.get("key", "")).lower()
    return "+".join(sorted(modifiers) + ([key] if key else []))


STARTUP_APP_NAME = "6PM Assistant"


def startup_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    return f'"{sys.executable}" "{app_base_dir() / "main.py"}"'


def is_startup_enabled() -> bool:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
            value, _ = winreg.QueryValueEx(key, STARTUP_APP_NAME)
        return value == startup_command()
    except Exception:
        return False


def set_startup_enabled(enabled: bool) -> None:
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, STARTUP_APP_NAME, 0, winreg.REG_SZ, startup_command())
        else:
            try:
                winreg.DeleteValue(key, STARTUP_APP_NAME)
            except FileNotFoundError:
                pass


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


def hotkey_to_keyboard_string(hotkey: dict | None) -> str:
    if not hotkey:
        return ""
    modifiers = [m.lower() for m in hotkey.get("modifiers", [])]
    key = str(hotkey.get("key", "")).lower()
    return "+".join(sorted(modifiers) + ([key] if key else []))


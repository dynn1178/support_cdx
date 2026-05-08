from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path
from typing import Any

from .utils import app_base_dir, bundled_resource_dir, now_iso

APP_NAME = "6PM Assistant"
DEFAULT_VERSION = "1.0.0"
GITHUB_REPO = "dynn1178/support_cdx"
TEMPLATE_COUNT = 5

BASE_DIR = app_base_dir()
RESOURCE_DIR = bundled_resource_dir()
DATA_DIR = BASE_DIR / "data"
TEMPLATE_DIR = DATA_DIR / "templates"
SETTINGS_PATH = DATA_DIR / "settings.json"
CLIPBOARD_HISTORY_PATH = DATA_DIR / "clipboard_history.json"
CLIPBOARD_IMAGE_DIR = DATA_DIR / "clipboard_images"
VERSION_PATH = BASE_DIR / "version.txt"
APP_ICON_PATH = BASE_DIR / "assets" / "icons" / "app.ico"
BUNDLED_ICON_PATH = RESOURCE_DIR / "assets" / "icons" / "app.ico"

DEFAULT_SETTINGS: dict[str, Any] = {
    "theme": "light",
    "window": {"width": 900, "height": 580, "always_on_top": False},
    "clipboard_history_limit": 50,
    "clipboard_popup_hotkey": {"modifiers": ["ctrl", "shift"], "key": "v"},
    "clipboard_popup_double_ctrl": True,
    "quick_memo_hotkey": {"modifiers": ["ctrl", "alt"], "key": "M"},
    "quick_memo_double_alt": True,
    "phrase_popup_hotkey": {"modifiers": ["ctrl"], "key": ";"},
    "hotkeys_enabled": True,
    "auto_update_check": False,
    "auto_update_install": False,
    "startup_with_windows": False,
    "active_preset": 1,
    "color_presets": [],
    "color_history": [],
    "favorite_emojis": [],
    "recent_emojis": [],
    "emoji_usage": {},
    "mouse_highlight_color": "#FFDD33",
    "mouse_highlight_shape": "원",
    "mouse_highlight_size": 70,
    "mouse_highlight_opacity": 50,
}


DEFAULT_TEMPLATE: dict[str, Any] = {
    "meta": {
        "preset_name": "기본 프리셋",
        "version": DEFAULT_VERSION,
        "saved_at": now_iso(),
    },
    "phrases": [
        {
            "id": "ph_sample",
            "name": "인사말",
            "text": "안녕하세요. 노랑풍선 CRM팀입니다.",
            "hotkey": {"modifiers": ["ctrl", "alt"], "key": "1"},
            "type": "text",
        }
    ],
    "snippets": [
        {
            "id": "sn_sample",
            "name": "RFM 기본 쿼리",
            "text": "SELECT customer_id, COUNT(*) AS frequency FROM orders GROUP BY customer_id",
            "language": "sql",
            "hotkey": {"modifiers": ["ctrl", "shift"], "key": "1"},
            "type": "code",
        }
    ],
    "launchers": [
        {
            "id": "ln_sample_site",
            "name": "Tableau",
            "description": "BI 대시보드 시스템",
            "type": "site",
            "url": "https://tableau.company.com",
            "username": "shared_id@company.com",
            "password": "",
            "browser_path": "",
            "hotkey": None,
        },
        {
            "id": "ln_sample_file",
            "name": "주간보고서",
            "description": "매주 월요일 업데이트",
            "type": "file",
            "path": r"D:\reports\weekly.xlsx",
            "hotkey": None,
        },
    ],
    "images": [
        {
            "id": "img_sample",
            "name": "세그먼트 맵",
            "path": "assets/images/segment_map.png",
            "path_type": "relative",
            "hotkey": {"modifiers": ["ctrl", "alt"], "key": "F1"},
        }
    ],
    "macros": [
        {
            "id": "mc_sample",
            "name": "일별 리포트 복사",
            "hotkey": {"modifiers": ["ctrl", "alt"], "key": "F5"},
            "actions": [
                {"type": "click", "x": 540, "y": 320, "delay": 0.5},
                {"type": "hotkey", "keys": ["ctrl", "c"], "delay": 0.3},
                {"type": "type", "text": "입력할 텍스트", "delay": 0.2},
            ],
        }
    ],
    "memos": [
        {
            "id": "mm_sample",
            "title": "메모 제목",
            "content": "내용",
            "pinned": False,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
    ],
    "schedules": [
        {
            "id": "sc_sample",
            "title": "캠페인 발송",
            "datetime": "2026-05-10T14:00:00",
            "repeat": "none",
            "notify_before_minutes": 30,
            "memo": "5월 멤버십 대상",
            "last_notified_at": "",
        }
    ],
    "hotstrings": [
        {
            "id": "hs_sample",
            "trigger": "GR.",
            "text": "안녕하세요~",
            "case_sensitive": False,
            "created_at": now_iso(),
            "sort_order": 0,
            "usage_count": 0,
        }
    ],
    "title_templates": [
        {
            "id": "tt_sample",
            "name": "일별 제목",
            "template": "리포트 {yyyy-mm-dd}",
            "business_days": False,
        }
    ],
    "phrase_popup_favorites": [],
}

PRESET_COLLECTION_KEYS = (
    "phrases",
    "snippets",
    "hotstrings",
    "title_templates",
    "launchers",
    "images",
    "macros",
    "memos",
    "schedules",
)
PRESET_LINK_KEYS = ("phrase_popup_favorites",)
PRESET_LIST_KEYS = PRESET_COLLECTION_KEYS + PRESET_LINK_KEYS
PRESET_RUNTIME_EXCLUDED_KEYS = {"settings"}


def ensure_data_files() -> None:
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "assets" / "images").mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "assets" / "icons").mkdir(parents=True, exist_ok=True)
    CLIPBOARD_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    copy_bundled_file(RESOURCE_DIR / "assets" / "icons" / "app.ico", APP_ICON_PATH)
    if not VERSION_PATH.exists():
        if not copy_bundled_file(RESOURCE_DIR / "version.txt", VERSION_PATH):
            VERSION_PATH.write_text(DEFAULT_VERSION, encoding="utf-8")
    if not SETTINGS_PATH.exists():
        save_settings(load_legacy_settings() or DEFAULT_SETTINGS)
    for index in range(1, TEMPLATE_COUNT + 1):
        path = template_path(index)
        if not path.exists():
            bundled_template = RESOURCE_DIR / "data" / "templates" / f"template_{index}.json"
            if not copy_bundled_file(bundled_template, path):
                data = default_template(index)
                save_template(index, data)
    if not CLIPBOARD_HISTORY_PATH.exists():
        if not copy_bundled_file(RESOURCE_DIR / "data" / "clipboard_history.json", CLIPBOARD_HISTORY_PATH):
            save_clipboard_history({"history": []})


def copy_bundled_file(source: Path, target: Path) -> bool:
    if not source.exists() or target.exists():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return True


def load_legacy_settings() -> dict[str, Any] | None:
    for index in range(1, TEMPLATE_COUNT + 1):
        path = template_path(index)
        if not path.exists():
            continue
        try:
            with path.open("r", encoding="utf-8") as f:
                settings = json.load(f).get("settings", {})
        except Exception:
            continue
        if settings:
            migrated = copy.deepcopy(settings)
            migrated["active_preset"] = int(migrated.pop("active_template", index) or index)
            return migrated
    return None


def default_template(index: int = 1) -> dict[str, Any]:
    data = copy.deepcopy(DEFAULT_TEMPLATE)
    data["meta"]["preset_name"] = "기본 프리셋" if index == 1 else f"프리셋 {index}"
    data["meta"]["saved_at"] = now_iso()
    return data


def template_path(index: int) -> Path:
    if index < 1 or index > TEMPLATE_COUNT:
        raise ValueError("template index must be between 1 and 5")
    return TEMPLATE_DIR / f"template_{index}.json"


def read_version() -> str:
    ensure_data_files()
    return VERSION_PATH.read_text(encoding="utf-8").strip() or DEFAULT_VERSION


def load_template(index: int) -> dict[str, Any]:
    ensure_data_files()
    with template_path(index).open("r", encoding="utf-8") as f:
        data = json.load(f)
    return merge_template_defaults(data)


def save_template(index: int, data: dict[str, Any]) -> None:
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    data_to_save = copy.deepcopy(data)
    for key in PRESET_RUNTIME_EXCLUDED_KEYS:
        data_to_save.pop(key, None)
    for collection in PRESET_LIST_KEYS:
        data_to_save.setdefault(collection, [])
    data_to_save.setdefault("meta", {})
    data_to_save["meta"]["saved_at"] = now_iso()
    with template_path(index).open("w", encoding="utf-8") as f:
        json.dump(data_to_save, f, ensure_ascii=False, indent=2)


def merge_template_defaults(data: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(DEFAULT_TEMPLATE)
    for key, value in data.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key].update(value)
        else:
            merged[key] = value
    for collection in PRESET_LIST_KEYS:
        merged.setdefault(collection, [])
    for key in PRESET_RUNTIME_EXCLUDED_KEYS:
        merged.pop(key, None)
    meta = merged.setdefault("meta", {})
    if not meta.get("preset_name"):
        meta["preset_name"] = meta.get("template_name") or "프리셋"
    meta.pop("template_name", None)
    return merged


def load_settings() -> dict[str, Any]:
    ensure_data_files()
    try:
        with SETTINGS_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    settings = copy.deepcopy(DEFAULT_SETTINGS)
    for key, value in data.items():
        if isinstance(value, dict) and isinstance(settings.get(key), dict):
            settings[key].update(value)
        elif key in {"font_family", "font_size"}:
            continue
        elif key == "active_template":
            settings["active_preset"] = value
        else:
            settings[key] = value
    settings.setdefault("window", copy.deepcopy(DEFAULT_SETTINGS["window"]))
    settings["active_preset"] = max(1, min(TEMPLATE_COUNT, int(settings.get("active_preset", 1) or 1)))
    return settings


def save_settings(settings: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data = copy.deepcopy(DEFAULT_SETTINGS)
    for key, value in settings.items():
        if key in {"font_family", "font_size"}:
            continue
        if isinstance(value, dict) and isinstance(data.get(key), dict):
            data[key].update(value)
        else:
            data[key] = value
    with SETTINGS_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_clipboard_history() -> dict[str, Any]:
    ensure_data_files()
    with CLIPBOARD_HISTORY_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("history", [])
    return data


def save_clipboard_history(data: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data.setdefault("history", [])
    with CLIPBOARD_HISTORY_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def export_template(template_index: int, export_path: str | Path) -> None:
    data = load_template(template_index)
    with Path(export_path).open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def import_template(import_path: str | Path, target_index: int) -> None:
    with Path(import_path).open("r", encoding="utf-8") as f:
        incoming = merge_template_defaults(json.load(f))
    save_template(target_index, incoming)

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from .utils import app_base_dir, now_iso

APP_NAME = "WorkHelper"
DEFAULT_VERSION = "1.0.0"
TEMPLATE_COUNT = 5

BASE_DIR = app_base_dir()
DATA_DIR = BASE_DIR / "data"
TEMPLATE_DIR = DATA_DIR / "templates"
CLIPBOARD_HISTORY_PATH = DATA_DIR / "clipboard_history.json"
VERSION_PATH = BASE_DIR / "version.txt"


DEFAULT_TEMPLATE: dict[str, Any] = {
    "meta": {
        "template_name": "기본 설정",
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
    "settings": {
        "theme": "light",
        "font_family": "맑은 고딕",
        "font_size": 9,
        "window": {"width": 400, "height": 700, "always_on_top": False},
        "clipboard_history_limit": 50,
        "active_template": 1,
    },
}


def ensure_data_files() -> None:
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "assets" / "images").mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "assets" / "icons").mkdir(parents=True, exist_ok=True)
    if not VERSION_PATH.exists():
        VERSION_PATH.write_text(DEFAULT_VERSION, encoding="utf-8")
    for index in range(1, TEMPLATE_COUNT + 1):
        path = template_path(index)
        if not path.exists():
            data = default_template(index)
            save_template(index, data)
    if not CLIPBOARD_HISTORY_PATH.exists():
        save_clipboard_history({"history": []})


def default_template(index: int = 1) -> dict[str, Any]:
    data = copy.deepcopy(DEFAULT_TEMPLATE)
    data["meta"]["template_name"] = "기본 설정" if index == 1 else f"템플릿 {index}"
    data["meta"]["saved_at"] = now_iso()
    data["settings"]["active_template"] = index
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
    data.setdefault("meta", {})
    data["meta"]["saved_at"] = now_iso()
    with template_path(index).open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def merge_template_defaults(data: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(DEFAULT_TEMPLATE)
    for key, value in data.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key].update(value)
        else:
            merged[key] = value
    for collection in ["phrases", "snippets", "launchers", "images", "macros", "memos", "schedules"]:
        merged.setdefault(collection, [])
    merged.setdefault("settings", {}).setdefault("window", {"width": 400, "height": 700, "always_on_top": False})
    return merged


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
    for launcher in data.get("launchers", []):
        launcher["password"] = ""
    with Path(export_path).open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def import_template(import_path: str | Path, target_index: int) -> None:
    with Path(import_path).open("r", encoding="utf-8") as f:
        incoming = merge_template_defaults(json.load(f))
    existing = load_template(target_index)
    for i, launcher in enumerate(incoming.get("launchers", [])):
        if i < len(existing.get("launchers", [])):
            launcher["password"] = existing["launchers"][i].get("password", "")
    incoming["settings"]["active_template"] = target_index
    save_template(target_index, incoming)


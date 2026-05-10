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

SETTINGS_VERSION = 2

DEFAULT_SETTINGS: dict[str, Any] = {
    "settings_version": SETTINGS_VERSION,
    "theme": "light",
    "window": {"width": 900, "height": 580, "always_on_top": False},
    "clipboard_history_limit": 30,
    "clipboard_popup_hotkey": {"modifiers": ["ctrl", "shift"], "key": "v"},
    "clipboard_popup_double_ctrl": True,
    "quick_memo_hotkey": {"modifiers": ["ctrl", "alt"], "key": "M"},
    "quick_memo_double_alt": True,
    "phrase_popup_hotkey": {"modifiers": ["ctrl"], "key": ";"},
    "steel_cut_hotkey": {"modifiers": ["ctrl", "alt"], "key": "S"},
    "hotkeys_enabled": True,
    "auto_update_check": True,
    "auto_update_install": True,
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
            "name": "안녕하세요. 6PM ASSIST 육땡이입니다.",
            "text": "안녕하세요. 6PM ASSIST 육땡이입니다.",
            "hotkey": {"modifiers": ["alt"], "key": "F1"},
            "type": "text",
            "sort_order": 0,
            "usage_count": 0,
        },
        {
            "id": "ph_sample2",
            "name": "★ 즐겨찾기시 상용구 (ctrl+;) 로도 호출 가능해",
            "text": "★ 즐겨찾기시 상용구 (ctrl+;) 로도 호출 가능해요. \n단축키 변경은 설정에서 할 수 있어요",
            "hotkey": None,
            "type": "text",
            "sort_order": 1,
            "usage_count": 0,
        },
    ],
    "snippets": [
        {
            "id": "sn_sample",
            "name": "자주 사용하는 쿼리",
            "text": "SELECT \n\tcustomer_id, \n\tCOUNT(*) AS frequency \nFROM SIX_PM \nGROUP BY customer_id",
            "language": "sql",
            "hotkey": None,
            "type": "code",
            "sort_order": 0,
            "usage_count": 0,
        },
        {
            "id": "sn_sample2",
            "name": "월간 보고 양식",
            "text": (
                "📋 [6PM 혁신팀] 2026년 5월 월간 업무 보고\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "보고일자 : 2026. 05. 30 (금)\n"
                "작  성  자 : 육땡\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "■ 1. 이달의 주요 성과\n\n"
                "  [Project #1]\n  · \n  · \n"
                "  [Project #2]\n  · \n  · \n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "■ 2. 이슈 및 대응\n\n"
                "  · [이슈 #1] \n  · [이슈 #2] \n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "■ 3. 다음 달 예정 업무\n\n  · \n  · \n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "■ 4. 기타 / 공유 사항\n\n  · 없음\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            "language": "other",
            "hotkey": None,
            "type": "code",
            "sort_order": 1,
            "usage_count": 0,
        },
    ],
    "launchers": [
        {
            "id": "ln_sample_site",
            "name": "네이버",
            "description": "",
            "type": "site",
            "url": "https://naver.com",
            "username": "",
            "password": "",
            "browser_path": "",
            "hotkey": None,
            "sort_order": 0,
            "usage_count": 0,
            "path": "",
            "show_credentials_on_card": False,
        },
        {
            "id": "ln_sample_site2",
            "name": "배포 사이트",
            "description": "",
            "type": "site",
            "url": "https://6pma.vercel.app/",
            "username": "finishwork",
            "password": "ontime",
            "browser_path": "",
            "show_credentials_on_card": True,
            "hotkey": None,
            "path": "",
            "sort_order": 1,
            "usage_count": 0,
        },
    ],
    "images": [
        {
            "id": "img_sample",
            "name": "엑셀 단축키",
            "path": "assets/images/capture_e05542b42c.png",
            "path_type": "relative",
            "hotkey": {"modifiers": ["ctrl", "alt"], "key": "F1"},
            "sort_order": 0,
            "usage_count": 0,
            "display_scale": 100,
        }
    ],
    "steel_cuts": [],
    "macros": [],
    "memos": [
        {
            "id": "mm_sample",
            "title": "메모를 저장하세요",
            "content": "스티커 버튼을 누르면 바탕화면에 띄울 수 있어요.",
            "pinned": False,
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "sort_order": 0,
            "usage_count": 0,
            "always_on_top": True,
            "background": "노랑",
        },
        {
            "id": "mm_sample2",
            "title": "ALT를 2번 빠르게 눌러보세요",
            "content": "빠르게 메모 입력이 가능합니다. (단축키는 설정에서 변경 가능)",
            "pinned": False,
            "always_on_top": True,
            "background": "노랑",
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "sort_order": 1,
            "usage_count": 0,
        },
    ],
    "schedules": [
        {
            "id": "sc_sample",
            "title": "할 일을 등록해보세요",
            "priority": "중",
            "deadline": "2030-12-31",
            "datetime": "2030-12-31T09:00:00",
            "repeat": "none",
            "notify_before_minutes": 30,
            "completed": False,
            "completed_at": None,
            "memo": "체크박스로 완료 표시, 우선순위·마감기한·알림 설정 가능",
            "last_notified_at": "",
            "sort_order": 0,
            "usage_count": 0,
        }
    ],
    "hotstrings": [
        {
            "id": "hs_sample",
            "trigger": "gg.",
            "text": "google.com",
            "case_sensitive": False,
            "created_at": now_iso(),
            "sort_order": 0,
            "usage_count": 0,
        },
        {
            "id": "hs_sample2",
            "trigger": "req;",
            "text": "위와 같이 요청 드립니다. 확인 부탁드립니다.",
            "case_sensitive": False,
            "created_at": now_iso(),
            "sort_order": 1,
            "usage_count": 0,
        },
        {
            "id": "hs_sample3",
            "trigger": "ack;",
            "text": "확인했습니다. 검토 후 회신 드리겠습니다.",
            "case_sensitive": False,
            "created_at": now_iso(),
            "sort_order": 2,
            "usage_count": 0,
        },
        {
            "id": "hs_sample4",
            "trigger": "sel;",
            "text": "SELECT * FROM WHERE ROWNUM <= 100",
            "case_sensitive": False,
            "created_at": now_iso(),
            "sort_order": 3,
            "usage_count": 0,
        },
        {
            "id": "hs_sample5",
            "trigger": "tx;",
            "text": "감사합니다.",
            "case_sensitive": False,
            "created_at": now_iso(),
            "sort_order": 4,
            "usage_count": 0,
        },
        {
            "id": "hs_sample6",
            "trigger": "hi;",
            "text": "안녕하세요. 6PM ASSIST 육땡이입니다.",
            "case_sensitive": False,
            "created_at": now_iso(),
            "sort_order": 5,
            "usage_count": 0,
        },
    ],
    "title_templates": [
        {
            "id": "tt_sample",
            "name": "금일 {yyyy-mm-dd}",
            "template": "금일 {yyyy-mm-dd}",
            "business_days": False,
            "hotkey": {"modifiers": ["shift"], "key": "F1"},
            "sort_order": 0,
            "usage_count": 0,
        },
        {
            "id": "tt_sample2",
            "name": "{yymmdd}_데일리 세일즈 리포트",
            "template": "{yymmdd}_데일리 세일즈 리포트 ({m-1d}월 {d-1d}일 ({ddd-1d}) 기준)",
            "business_days": True,
            "hotkey": None,
            "sort_order": 1,
            "usage_count": 0,
        },
        {
            "id": "tt_sample3",
            "name": "주간 동향",
            "template": "{yyyy-7d}.{mm-7d}.{dd-7d}~{yyyy}.{mm}.{dd} 주간 동향",
            "business_days": False,
            "hotkey": None,
            "sort_order": 2,
            "usage_count": 0,
        },
        {
            "id": "tt_sample4",
            "name": "{yyyy}년 {m}월 월간성과 보고",
            "template": "{yyyy}년 {m}월 월간성과 보고",
            "business_days": False,
            "hotkey": None,
            "sort_order": 3,
            "usage_count": 0,
        },
    ],
    "phrase_popup_favorites": ["ph_sample2"],
    "todo_groups": ["그룹 1", "그룹 2", "그룹 3"],
}

PRESET_COLLECTION_KEYS = (
    "phrases",
    "snippets",
    "hotstrings",
    "title_templates",
    "launchers",
    "images",
    "steel_cuts",
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
    # version.txt는 항상 번들 버전으로 덮어씀 (이전 버전 exe가 남긴 파일 방지)
    bundled_version = RESOURCE_DIR / "version.txt"
    if bundled_version.exists():
        VERSION_PATH.write_text(bundled_version.read_text(encoding="utf-8"), encoding="utf-8")
    elif not VERSION_PATH.exists():
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


def _migrate_settings(data: dict[str, Any]) -> dict[str, Any]:
    """이전 버전 settings를 현재 버전으로 마이그레이션."""
    version = int(data.get("settings_version") or 0)
    if version < 2:
        # v2: auto_update_check/install 기본값 True, clipboard_history_limit 기본값 30
        if not data.get("auto_update_check"):
            data["auto_update_check"] = True
        if not data.get("auto_update_install"):
            data["auto_update_install"] = True
        if data.get("clipboard_history_limit", 0) > 30:
            data["clipboard_history_limit"] = 30
    data["settings_version"] = SETTINGS_VERSION
    return data


def load_settings() -> dict[str, Any]:
    ensure_data_files()
    try:
        with SETTINGS_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    data = _migrate_settings(data)
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

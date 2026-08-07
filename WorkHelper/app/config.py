from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path
from typing import Any

from .logger import get_logger
from .utils import app_base_dir, bundled_resource_dir, now_iso

log = get_logger("config")

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
MACRO_INI_DIR = DATA_DIR / "macro_vars"
SCREENSHOT_DIR = BASE_DIR / "screenshot"
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
    "steel_cut_hotkey": {"modifiers": ["ctrl", "shift"], "key": "S"},
    "steel_cut_capture_mode": "region",
    "screen_draw_hotkey": None,
    "steel_cut_fixed_width": 800,
    "steel_cut_fixed_height": 450,
    "steel_cut_fixed_x": None,
    "steel_cut_fixed_y": None,
    "hotkeys_enabled": True,
    "auto_update_check": True,
    "auto_update_install": True,
    "update_notice_snooze_until": "",
    "startup_with_windows": False,
    "active_preset": 1,
    "color_presets": [],
    "color_history": [],
    "favorite_emojis": [],
    "recent_emojis": [],
    "emoji_usage": {},
    "special_char_usage": {},
    "mouse_highlight_color": "#FFDD33",
    "mouse_highlight_shape": "원",
    "mouse_highlight_size": 70,
    "mouse_highlight_opacity": 50,
    "floating_widget_enabled": True,
    "floating_widget_edge": "top",
    "floating_widget_monitor": 1,
    "floating_widget_monitor_preferred": 1,
    "floating_widget_monitor_signature": None,
    "floating_widget_panel_position": 50,
    "floating_widget_panel_size": 160,
    "floating_widget_panel_width": 860,
    "floating_widget_icon_size": 50,
    "floating_widget_speed": 80,
    "floating_widget_show_delay": 1000,
    "floating_widget_opacity": 77,
    "floating_widget_theme": "dark",
    "floating_widget_icon_shape": "square",
    "floating_widget_show_hover_text": True,
    "floating_widget_hint_dismissed": False,
    "floating_widget_categories": ["text", "snippet", "date", "site", "file", "folder", "cheat", "memo", "emoji"],
    "sticky_memo_arrange_monitor": 1,
    "sticky_memo_arrange_monitor_preferred": 1,
    "sticky_memo_arrange_monitor_signature": None,
    "sticky_memo_arrange_corner": "top_right",
    "sticky_memo_display_mode": "floating",
    "sticky_memo_index_side": "right",
    "sticky_memo_index_start_y": 0,
    "update_shortcut_notice_ack": "",
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
        },
        {
            "id": "ph_sample2",
            "name": "★ 즐겨찾기시 상용구 (ctrl+;) 로도 호출 가능해",
            "text": "★ 즐겨찾기시 상용구 (ctrl+;) 로도 호출 가능해요. \n단축키 변경은 설정에서 할 수 있어요",
            "hotkey": None,
            "type": "text",
            "sort_order": 1,
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
            "path": "",
            "show_credentials_on_card": False,
        },
        {
            "id": "ln_sample_site2",
            "name": "6PM Assistant 사이트",
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
            "display_scale": 100,
        }
    ],
    "steel_cuts": [],
    "macros": [
        {
            "id": "mc_sample",
            "name": "자리비움 방지",
            "hotkey": None,
            "script": "Sleep, 60000\nClick",
            "sort_order": 0,
            "repeat": 100,
        },
    ],
    "memos": [
        {
            "id": "mm_sample",
            "title": "메모를 저장하세요",
            "content": "스티커 버튼을 누르면 바탕화면에 띄울 수 있어요.",
            "pinned": False,
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "sort_order": 0,
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
        },
    ],
    "schedules": [
        {
            "id": "sc_sample",
            "title": "할 일 등록",
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
            "group": "그룹 2",
        },
        {
            "id": "sc_sample2",
            "title": "칼퇴 하기",
            "group": "그룹 1",
            "priority": "상",
            "deadline": "2029-05-05",
            "datetime": "2029-05-05T18:00:00",
            "notify_before_minutes": 10,
            "repeat": "none",
            "memo": "",
            "last_notified_at": "",
            "completed": False,
            "completed_at": None,
            "sort_order": 1,
        },
    ],
    "hotstrings": [
        {
            "id": "hs_sample",
            "trigger": "gg.",
            "text": "google.com",
            "case_sensitive": False,
            "created_at": now_iso(),
            "sort_order": 0,
        },
        {
            "id": "hs_sample2",
            "trigger": "req;",
            "text": "위와 같이 요청 드립니다. 확인 부탁드립니다.",
            "case_sensitive": False,
            "created_at": now_iso(),
            "sort_order": 1,
        },
        {
            "id": "hs_sample3",
            "trigger": "ack;",
            "text": "확인했습니다. 검토 후 회신 드리겠습니다.",
            "case_sensitive": False,
            "created_at": now_iso(),
            "sort_order": 2,
        },
        {
            "id": "hs_sample4",
            "trigger": "sel;",
            "text": "SELECT * FROM WHERE ROWNUM <= 100",
            "case_sensitive": False,
            "created_at": now_iso(),
            "sort_order": 3,
        },
        {
            "id": "hs_sample5",
            "trigger": "tx;",
            "text": "감사합니다.",
            "case_sensitive": False,
            "created_at": now_iso(),
            "sort_order": 4,
        },
        {
            "id": "hs_sample6",
            "trigger": "hi;",
            "text": "안녕하세요. 6PM ASSIST 육땡이입니다.",
            "case_sensitive": False,
            "created_at": now_iso(),
            "sort_order": 5,
        },
    ],
    "title_templates": [
        {
            "id": "tt_sample2",
            "name": "{yymmdd}_데일리 세일즈 리포트",
            "template": "{yymmdd}_데일리 세일즈 리포트 ({m-1d}월 {d-1d}일 ({ddd-1d}) 기준)",
            "business_days": True,
            "hotkey": None,
            "sort_order": 0,
        },
        {
            "id": "tt_sample3",
            "name": "주간 동향",
            "template": "{yyyy-7d}.{mm-7d}.{dd-7d}~{yyyy}.{mm}.{dd} 주간 동향",
            "business_days": False,
            "hotkey": None,
            "sort_order": 1,
        },
        {
            "id": "tt_sample4",
            "name": "[{yyyy}년 {m}월] 월간 성과 보고서",
            "template": (
                "[{yyyy}년 {m}월] 월간 성과 보고서\n"
                "─────────────────────\n"
                "보고일자 : {yyyy}년 {m}월 {d}일 {dddd}\n"
                "담당자 : 육땡\n"
                "─────────────────────\n\n"
                "1. 당월 업무 총평\n\n"
                "2. 주요 성과 (Key Achievements)\n\n"
                " - 핵심 KPI 달성 현황\n"
                " - 주요 프로젝트 성과\n"
                " - 정량적 데이터 요약\n\n"
                "3. 세부 업무 추진 현황\n\n"
                " - 완료 업무\n"
                " - 진행 업무 및 진척도\n"
                " - 이월/보류 업무\n\n"
                "4. 문제점 및 개선 방안 (Issue & Solution)\n\n"
                " - 발생 이슈 및 원인 분석\n"
                " - 조치 사항 및 대응 결과\n"
                " - 향후 재발 방지 대책\n\n"
                "5. 익월(6월) 주요 계획\n\n"
                " - 차기 달 핵심 목표\n"
                " - 주요 일정 및 마일스톤\n"
                " - 리소스 투입 계획\n\n"
                "6. 건의 및 지원 요청 사항\n \n"
                "[첨부 자료]"
            ),
            "business_days": True,
            "hotkey": None,
            "sort_order": 2,
        },
        {
            "id": "tt_sample5",
            "name": "날짜 변수로 Date값을 쉽게 호출하세요.",
            "template": "날짜 변수로 Date값을 쉽게 호출하세요.",
            "business_days": False,
            "hotkey": None,
            "sort_order": 3,
        },
    ],
    "phrase_popup_favorites": ["ph_sample2"],
    "todo_groups": ["그룹 1", "그룹 2", "그룹 3"],
    "custom_searches": [],
}

EXPORT_STRIP_ITEM_FIELDS = ("last_used_at", "used_today_date", "used_today_count", "usage_count", "favicon_attempted")
EXPORT_EXCLUDED_COLLECTIONS = frozenset({"steel_cuts"})

PRESET_COLLECTION_KEYS = (
    "phrases",
    "snippets",
    "hotstrings",
    "title_templates",
    "launchers",
    "custom_searches",
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
    MACRO_INI_DIR.mkdir(parents=True, exist_ok=True)
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
            # 초기 배포용 샘플은 seed/에 분리 보관한다. (data/는 사용자 데이터라
            # git/배포 번들에서 제외) 구버전 번들 호환을 위해 data/ 경로도 시도한다.
            seeded = copy_bundled_file(RESOURCE_DIR / "seed" / "templates" / f"template_{index}.json", path)
            if not seeded:
                seeded = copy_bundled_file(RESOURCE_DIR / "data" / "templates" / f"template_{index}.json", path)
            if not seeded:
                save_template(index, default_template(index))
    if not CLIPBOARD_HISTORY_PATH.exists():
        if not copy_bundled_file(RESOURCE_DIR / "seed" / "clipboard_history.json", CLIPBOARD_HISTORY_PATH):
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
    version = VERSION_PATH.read_text(encoding="utf-8").strip().lstrip("\ufeff").strip()
    return version or DEFAULT_VERSION


def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    with temp_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    temp_path.replace(path)


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
    _write_json_atomic(template_path(index), data_to_save)


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
    merged["macros"] = [_migrate_macro(item) for item in merged.get("macros", [])]
    return merged


def _migrate_macro(macro: dict[str, Any]) -> dict[str, Any]:
    """행 단위 actions 리스트로 저장된 옛 매크로를 script 텍스트로 변환한다."""
    if "script" in macro or "actions" not in macro:
        return macro
    from .macro_script import record_actions_to_script

    migrated = dict(macro)
    migrated["script"] = record_actions_to_script(migrated.pop("actions", []))
    return migrated


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
        log.warning("settings.json 로드 실패 — 기본값으로 시작", exc_info=True)
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
    for monitor_key in ("floating_widget_monitor", "sticky_memo_arrange_monitor"):
        preferred_key = f"{monitor_key}_preferred"
        if preferred_key not in data:
            settings[preferred_key] = settings.get(monitor_key, DEFAULT_SETTINGS.get(monitor_key, 1))
    settings.setdefault("window", copy.deepcopy(DEFAULT_SETTINGS["window"]))
    if not settings.get("steel_cut_hotkey"):
        settings["steel_cut_hotkey"] = copy.deepcopy(DEFAULT_SETTINGS["steel_cut_hotkey"])
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
    _write_json_atomic(SETTINGS_PATH, data)


def load_clipboard_history() -> dict[str, Any]:
    ensure_data_files()
    with CLIPBOARD_HISTORY_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("history", [])
    return data


def save_clipboard_history(data: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data.setdefault("history", [])
    _write_json_atomic(CLIPBOARD_HISTORY_PATH, data)


def _strip_for_export(data: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(data)
    for collection in EXPORT_EXCLUDED_COLLECTIONS:
        result.pop(collection, None)
    for collection in PRESET_COLLECTION_KEYS:
        if collection in EXPORT_EXCLUDED_COLLECTIONS:
            continue
        for item in result.get(collection, []):
            for field in EXPORT_STRIP_ITEM_FIELDS:
                item.pop(field, None)
    return result


def export_template(template_index: int, export_path: str | Path) -> None:
    data = _strip_for_export(load_template(template_index))
    with Path(export_path).open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def import_template(import_path: str | Path, target_index: int) -> None:
    with Path(import_path).open("r", encoding="utf-8") as f:
        incoming = merge_template_defaults(json.load(f))
    save_template(target_index, incoming)

import copy

from app.config import (
    DEFAULT_SETTINGS,
    DEFAULT_TEMPLATE,
    SETTINGS_VERSION,
    _migrate_settings,
    default_template,
    merge_template_defaults,
)


def test_merge_template_defaults_fills_missing_collections():
    merged = merge_template_defaults({"phrases": [{"id": "x"}]})
    assert merged["phrases"] == [{"id": "x"}]
    for key in ("snippets", "memos", "schedules", "launchers"):
        assert key in merged


def test_merge_template_defaults_drops_runtime_settings():
    merged = merge_template_defaults({"settings": {"theme": "dark"}, "memos": []})
    assert "settings" not in merged


def test_merge_template_defaults_drops_legacy_template_name():
    # 기본 meta가 preset_name을 항상 채우므로 template_name은 제거만 된다.
    merged = merge_template_defaults({"meta": {"template_name": "옛이름"}})
    assert "template_name" not in merged["meta"]
    assert merged["meta"]["preset_name"]


def test_merge_does_not_mutate_default_template():
    snapshot = copy.deepcopy(DEFAULT_TEMPLATE)
    merged = merge_template_defaults({"phrases": [{"id": "y"}]})
    merged["phrases"].append({"id": "z"})
    assert DEFAULT_TEMPLATE == snapshot


def test_default_template_names_by_index():
    assert default_template(1)["meta"]["preset_name"] == "기본 프리셋"
    assert default_template(3)["meta"]["preset_name"] == "프리셋 3"


def test_migrate_settings_sets_current_version():
    data = _migrate_settings({})
    assert data["settings_version"] == SETTINGS_VERSION


def test_migrate_settings_clamps_clipboard_limit_from_v1():
    data = _migrate_settings({"settings_version": 1, "clipboard_history_limit": 300})
    assert data["clipboard_history_limit"] == 30


def test_migrate_settings_keeps_v2_values():
    data = _migrate_settings(
        {"settings_version": SETTINGS_VERSION, "auto_update_check": False, "clipboard_history_limit": 200}
    )
    assert data["auto_update_check"] is False
    assert data["clipboard_history_limit"] == 200


def test_default_settings_has_monitor_signature_keys():
    for key in (
        "floating_widget_monitor_signature",
        "sticky_memo_arrange_monitor_signature",
    ):
        assert key in DEFAULT_SETTINGS

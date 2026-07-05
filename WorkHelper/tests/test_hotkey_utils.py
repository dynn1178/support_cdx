from app.utils import display_hotkey, hotkey_to_keyboard_string, normalize_hotkey


def test_normalize_hotkey_orders_modifiers():
    assert normalize_hotkey({"modifiers": ["shift", "ctrl"], "key": "V"}) == "Ctrl+Shift+V"
    assert normalize_hotkey({"modifiers": ["alt"], "key": "F1"}) == "Alt+F1"


def test_normalize_hotkey_deduplicates_and_aliases():
    assert normalize_hotkey({"modifiers": ["control", "ctrl"], "key": "a"}) == "Ctrl+a"
    assert normalize_hotkey({"modifiers": ["meta"], "key": "x"}) == "Win+x"


def test_normalize_hotkey_empty():
    assert normalize_hotkey(None) == ""
    assert normalize_hotkey({}) == ""
    assert normalize_hotkey({"modifiers": ["ctrl"], "key": ""}) == "Ctrl"


def test_display_hotkey_is_same_format():
    hotkey = {"modifiers": ["shift", "ctrl"], "key": "S"}
    assert display_hotkey(hotkey) == normalize_hotkey(hotkey)


def test_hotkey_to_keyboard_string():
    assert hotkey_to_keyboard_string({"modifiers": ["Control", "Shift"], "key": "V"}) == "ctrl+shift+v"
    assert hotkey_to_keyboard_string(None) == ""

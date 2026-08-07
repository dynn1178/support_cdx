import pytest

pytest.importorskip("PyQt6.QtGui")

from ui.tab_macro import MacroPlayerThread  # noqa: E402


def test_ini_roundtrip_with_percent_sign_in_value(tmp_path):
    # 클립보드 텍스트에 '%' 가 들어있으면 configparser 의 기본 보간 기능이
    # InterpolationSyntaxError 를 던지던 버그의 회귀 테스트.
    path = tmp_path / "setting.ini"
    MacroPlayerThread._ini_write(path, "Settings", "clip", "할인 50% 적용")
    assert MacroPlayerThread._ini_read(path, "Settings", "clip") == "할인 50% 적용"


def test_ini_roundtrip_with_double_percent(tmp_path):
    path = tmp_path / "setting.ini"
    MacroPlayerThread._ini_write(path, "Settings", "key", "100%%literal")
    assert MacroPlayerThread._ini_read(path, "Settings", "key") == "100%%literal"


def test_ini_read_missing_file_returns_empty(tmp_path):
    path = tmp_path / "missing.ini"
    assert MacroPlayerThread._ini_read(path, "Settings", "key") == ""


def test_ini_write_preserves_other_keys(tmp_path):
    path = tmp_path / "setting.ini"
    MacroPlayerThread._ini_write(path, "Settings", "loc_x", "55")
    MacroPlayerThread._ini_write(path, "Settings", "loc_y", "80%")
    assert MacroPlayerThread._ini_read(path, "Settings", "loc_x") == "55"
    assert MacroPlayerThread._ini_read(path, "Settings", "loc_y") == "80%"

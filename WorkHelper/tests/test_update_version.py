from app.update_checker import _build_update_info, normalize_version, parse_version


def test_normalize_version():
    assert normalize_version("v1.4.19") == "1.4.19"
    assert normalize_version("﻿ 1.2.3 ") == "1.2.3"


def test_parse_version_ordering():
    assert parse_version("1.4.19") > parse_version("1.4.18")
    assert parse_version("1.10.0") > parse_version("1.9.9")
    assert parse_version("1.4.0") == parse_version("1.4")
    assert parse_version("v2.0") > parse_version("1.99.99")


def test_build_update_info_skips_same_or_older():
    payload = {"tag_name": "v1.4.19", "assets": [], "html_url": "u"}
    assert _build_update_info(payload, "1.4.19") is None
    assert _build_update_info(payload, "1.5.0") is None
    info = _build_update_info(payload, "1.4.18")
    assert info is not None and info.latest_version == "1.4.19"


def test_build_update_info_prefers_zip_asset():
    payload = {
        "tag_name": "v9.9.9",
        "html_url": "u",
        "assets": [
            {"name": "6PM.Assistant.exe", "browser_download_url": "exe_url"},
            {"name": "6PM.Assistant.zip", "browser_download_url": "zip_url"},
        ],
    }
    info = _build_update_info(payload, "1.0.0")
    assert info.download_url == "zip_url"
    assert info.asset_name.endswith(".zip")

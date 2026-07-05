from datetime import datetime

from app.snippet_vars import has_snippet_variables, render_snippet_text

NOW = datetime(2026, 7, 4, 9, 5, 7)


def test_plain_text_passthrough():
    rendered, cursor = render_snippet_text("안녕하세요", now=NOW)
    assert rendered == "안녕하세요"
    assert cursor is None


def test_clipboard_variable():
    rendered, _ = render_snippet_text("인용: {clipboard}", clipboard_text="복사한 값", now=NOW)
    assert rendered == "인용: 복사한 값"


def test_date_default_and_custom_format():
    assert render_snippet_text("{date}", now=NOW)[0] == "2026-07-04"
    assert render_snippet_text("{date:yyyy.MM.dd}", now=NOW)[0] == "2026.07.04"
    assert render_snippet_text("{date:yyyy-MM-dd HH:mm}", now=NOW)[0] == "2026-07-04 09:05"
    assert render_snippet_text("{time}", now=NOW)[0] == "09:05"


def test_cursor_marker_removed_and_offset():
    rendered, cursor = render_snippet_text("앞{cursor}뒤끝", now=NOW)
    assert rendered == "앞뒤끝"
    assert cursor == 2  # '뒤끝' 두 글자만큼 왼쪽으로 이동

    rendered, cursor = render_snippet_text("끝에{cursor}", now=NOW)
    assert rendered == "끝에"
    assert cursor == 0


def test_multiple_cursor_markers_use_first():
    rendered, cursor = render_snippet_text("a{cursor}b{cursor}c", now=NOW)
    assert rendered == "abc"
    assert cursor == 2


def test_has_snippet_variables():
    assert has_snippet_variables("{clipboard}")
    assert has_snippet_variables("{date:yy}")
    assert has_snippet_variables("{cursor}")
    assert not has_snippet_variables("그냥 텍스트 {unknown}")

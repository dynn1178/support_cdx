import pytest

pytest.importorskip("PyQt6.QtWidgets")

from app import config  # noqa: E402
from ui.memo_windows import MemoPreviewPopup  # noqa: E402
from ui.tab_memo import MemoListTab  # noqa: E402


class DummyWindow:
    def __init__(self, visible: bool, auto_hidden: bool = False) -> None:
        self._visible = visible
        self._auto_hidden = auto_hidden

    def isVisible(self) -> bool:
        return self._visible


def test_auto_hide_default_exists():
    assert config.DEFAULT_SETTINGS["sticky_memo_auto_hide"] is False


def test_auto_hidden_window_counts_as_open():
    assert MemoListTab._sticker_is_open(DummyWindow(True)) is True
    assert MemoListTab._sticker_is_open(DummyWindow(False, auto_hidden=True)) is True
    assert MemoListTab._sticker_is_open(DummyWindow(False)) is False
    assert MemoListTab._sticker_is_open(None) is False


def test_preview_text_is_shortened():
    assert MemoPreviewPopup._shorten("   ") == "(내용 없음)"
    assert MemoPreviewPopup._shorten("한 줄") == "한 줄"

    long_lines = "\n".join(str(index) for index in range(MemoPreviewPopup.MAX_LINES + 5))
    shortened = MemoPreviewPopup._shorten(long_lines)
    assert shortened.endswith("…")
    assert len(shortened.splitlines()) == MemoPreviewPopup.MAX_LINES

    shortened_chars = MemoPreviewPopup._shorten("가" * (MemoPreviewPopup.MAX_CHARS + 50))
    assert shortened_chars.endswith("…")
    assert len(shortened_chars) <= MemoPreviewPopup.MAX_CHARS + 2

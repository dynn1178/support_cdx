import zipfile

from app.text_export import build_entries, safe_filename, save_text_file, save_zip, unique_filename


def test_safe_filename_strips_invalid_characters():
    assert safe_filename('보고서/2026: 1분기*') == "보고서 2026 1분기"
    assert safe_filename("   ") == "무제"
    assert safe_filename("CON") == "무제"  # 윈도우 예약어
    assert safe_filename("", "메모_1") == "메모_1"


def test_unique_filename_adds_index():
    used: set[str] = set()
    assert unique_filename(used, "메모", "txt") == "메모.txt"
    assert unique_filename(used, "메모", "txt") == "메모 (2).txt"
    assert unique_filename(used, "메모", "txt") == "메모 (3).txt"


def test_build_entries_handles_duplicates_and_blanks():
    entries = build_entries([("메모", "a"), ("메모", "b"), ("", "c")], "txt", "메모")
    assert [name for name, _ in entries] == ["메모.txt", "메모 (2).txt", "메모_3.txt"]


def test_save_text_file_uses_crlf_for_txt_only(tmp_path):
    txt = save_text_file(tmp_path / "a.txt", "1\n2")
    code = save_text_file(tmp_path / "a.sql", "SELECT 1\nFROM t")
    assert txt.read_bytes() == "1\r\n2".encode("utf-8")
    assert code.read_bytes() == "SELECT 1\nFROM t".encode("utf-8")


def test_save_zip_contains_every_entry(tmp_path):
    target = save_zip(tmp_path / "backup.zip", build_entries([("첫 메모", "내용"), ("둘째 메모", "내용2")]))
    with zipfile.ZipFile(target) as archive:
        assert archive.namelist() == ["첫 메모.txt", "둘째 메모.txt"]
        assert archive.read("첫 메모.txt").decode("utf-8") == "내용"

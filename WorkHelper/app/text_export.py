"""메모·스니펫을 텍스트 파일이나 zip 묶음으로 내보내는 헬퍼."""

from __future__ import annotations

import zipfile
from pathlib import Path

INVALID_FILENAME_CHARS = '<>:"/\\|?*'
RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
MAX_BASENAME = 80


def safe_filename(name: str, fallback: str = "무제") -> str:
    """윈도우에서 쓸 수 없는 문자를 걸러 파일명으로 쓸 수 있게 만든다."""
    cleaned = "".join(" " if char in INVALID_FILENAME_CHARS else char for char in str(name or ""))
    cleaned = "".join(char for char in cleaned if char.isprintable())
    cleaned = " ".join(cleaned.split()).strip(" .")
    if len(cleaned) > MAX_BASENAME:
        cleaned = cleaned[:MAX_BASENAME].strip()
    if not cleaned or cleaned.upper() in RESERVED_NAMES:
        return fallback
    return cleaned


def unique_filename(used: set[str], base: str, extension: str) -> str:
    """같은 이름이 이미 쓰였으면 '이름 (2).txt'처럼 번호를 붙인다."""
    extension = extension.lstrip(".")
    candidate = f"{base}.{extension}"
    index = 2
    while candidate.lower() in used:
        candidate = f"{base} ({index}).{extension}"
        index += 1
    used.add(candidate.lower())
    return candidate


def normalize_newlines(text: str, extension: str) -> str:
    """txt는 메모장 호환을 위해 CRLF로, 코드 파일은 LF로 통일한다."""
    body = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    return body.replace("\n", "\r\n") if extension.lstrip(".").lower() == "txt" else body


def save_text_file(path: str | Path, text: str) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    body = normalize_newlines(text, target.suffix)
    target.write_bytes(body.encode("utf-8"))
    return target


def build_entries(items: list[tuple[str, str]], extension: str = "txt", fallback: str = "무제") -> list[tuple[str, str]]:
    """(이름, 본문) 목록을 (중복 없는 파일명, 본문) 목록으로 바꾼다."""
    used: set[str] = set()
    entries = []
    for index, (name, text) in enumerate(items, start=1):
        base = safe_filename(name, f"{fallback}_{index}")
        entries.append((unique_filename(used, base, extension), text))
    return entries


def save_zip(path: str | Path, entries: list[tuple[str, str]]) -> Path:
    """(파일명, 본문) 목록을 하나의 zip으로 저장한다."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for filename, text in entries:
            archive.writestr(filename, normalize_newlines(text, Path(filename).suffix).encode("utf-8"))
    return target

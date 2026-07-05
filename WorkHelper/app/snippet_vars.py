from __future__ import annotations

"""상용구/스니핏 텍스트의 변수 치환.

지원 변수:
- ``{clipboard}``            현재 클립보드 텍스트
- ``{date}``                 오늘 날짜 (yyyy-MM-dd)
- ``{date:yyyy-MM-dd}``      지정 포맷 날짜/시간 (yyyy, MM, dd, HH, mm, ss, M, d, H)
- ``{time}``                 현재 시각 (HH:mm)
- ``{cursor}``               붙여넣기 후 커서가 위치할 지점 (텍스트에서는 제거됨)

Qt에 의존하지 않는 순수 함수라 단독 테스트가 가능하다.
"""

import re
from datetime import datetime

CURSOR_MARKER = "{cursor}"

_DATE_PATTERN = re.compile(r"\{date(?::([^{}]+))?\}")
_TIME_PATTERN = re.compile(r"\{time(?::([^{}]+))?\}")

# Qt 스타일 포맷 토큰 → strftime 변환 (긴 토큰 먼저)
_FORMAT_TOKENS = [
    ("yyyy", "%Y"),
    ("yy", "%y"),
    ("MM", "%m"),
    ("dd", "%d"),
    ("HH", "%H"),
    ("mm", "%M"),
    ("ss", "%S"),
]


def _qt_format_to_strftime(fmt: str) -> str:
    result = ""
    index = 0
    while index < len(fmt):
        for token, replacement in _FORMAT_TOKENS:
            if fmt.startswith(token, index):
                result += replacement
                index += len(token)
                break
        else:
            char = fmt[index]
            # 단독 M/d/H는 0 채움 없는 값으로 처리
            if char == "M":
                result += "%#m"
            elif char == "d":
                result += "%#d"
            elif char == "H":
                result += "%#H"
            elif char == "%":
                result += "%%"
            else:
                result += char
            index += 1
    return result


def _format_now(fmt: str | None, default: str, now: datetime) -> str:
    strftime_fmt = _qt_format_to_strftime(fmt) if fmt else default
    try:
        return now.strftime(strftime_fmt)
    except ValueError:
        return now.strftime(default)


def has_snippet_variables(text: str) -> bool:
    return (
        "{clipboard}" in text
        or CURSOR_MARKER in text
        or bool(_DATE_PATTERN.search(text))
        or bool(_TIME_PATTERN.search(text))
    )


def render_snippet_text(
    text: str,
    clipboard_text: str = "",
    now: datetime | None = None,
) -> tuple[str, int | None]:
    """변수를 치환한 텍스트와, 커서 마커 뒤 글자 수를 돌려준다.

    두 번째 반환값은 붙여넣기 후 왼쪽 화살표를 몇 번 보내야 커서가
    ``{cursor}`` 위치로 가는지이며, 마커가 없으면 None이다.
    """
    now = now or datetime.now()
    rendered = str(text or "")
    rendered = rendered.replace("{clipboard}", clipboard_text)
    rendered = _DATE_PATTERN.sub(lambda m: _format_now(m.group(1), "%Y-%m-%d", now), rendered)
    rendered = _TIME_PATTERN.sub(lambda m: _format_now(m.group(1), "%H:%M", now), rendered)
    cursor_back: int | None = None
    marker_index = rendered.find(CURSOR_MARKER)
    if marker_index >= 0:
        # 첫 마커만 인식하고 나머지는 제거한다.
        rendered = rendered.replace(CURSOR_MARKER, "")
        cursor_back = len(rendered) - marker_index
    return rendered, cursor_back

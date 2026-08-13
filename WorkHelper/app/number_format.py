"""계산 결과 표시용 숫자 서식 — 천 단위 구분, 한글 병기, 백분율 병기."""

from __future__ import annotations

KOREAN_DIGITS = "영일이삼사오육칠팔구"
KOREAN_SMALL_UNITS = ("", "십", "백", "천")
KOREAN_BIG_UNITS = ("", "만", "억", "조", "경", "해")


def _group_to_korean(value: int) -> str:
    """0~9999 구간을 한글로 바꾼다. 십/백/천 앞의 '일'은 생략한다(15 → 십오)."""
    text = ""
    for position in range(3, -1, -1):
        digit = (value // (10**position)) % 10
        if digit == 0:
            continue
        if digit == 1 and position > 0:
            text += KOREAN_SMALL_UNITS[position]
        else:
            text += KOREAN_DIGITS[digit] + KOREAN_SMALL_UNITS[position]
    return text


def korean_number(value: int) -> str:
    """정수를 한글 읽기로 바꾼다. 해(10^20) 단위를 넘으면 빈 문자열."""
    if value == 0:
        return "영"
    sign = "마이너스 " if value < 0 else ""
    remaining = abs(value)
    groups: list[tuple[int, int]] = []
    unit_index = 0
    while remaining > 0:
        if unit_index >= len(KOREAN_BIG_UNITS):
            return ""  # 표기 단위를 넘어서면 한글 병기를 생략한다.
        groups.append((remaining % 10000, unit_index))
        remaining //= 10000
        unit_index += 1
    parts = []
    for group_value, index in reversed(groups):
        if group_value == 0:
            continue
        # 10000은 '일만'이 아니라 '만'으로 읽는다.
        head = "" if (index == 1 and group_value == 1) else _group_to_korean(group_value)
        parts.append(head + KOREAN_BIG_UNITS[index])
    return sign + " ".join(parts)


def format_percent(value: float) -> str:
    """소수를 백분율 문자열로 바꾼다. 0.0966666 → '9.67%'"""
    percent = value * 100
    if percent == 0:
        return "0%"
    if abs(percent) < 0.01:
        text = f"{percent:.4g}"
    else:
        text = f"{percent:,.2f}".rstrip("0").rstrip(".")
    return f"{text}%"


def normalize_result(value: float | int) -> float | int:
    """5.0처럼 소수부가 없는 실수는 정수로 되돌린다.

    이진 부동소수점 오차(48.7-41.3 → 7.400000000000006)를 없애기 위해
    소수 10자리로 반올림한 뒤 정수 여부를 판단한다.
    """
    if isinstance(value, float):
        value = round(value, 10)
        if value.is_integer():
            return int(value)
    return value


def format_calc_result(value: float | int) -> tuple[str, str]:
    """(화면 표시 문자열, 복사용 원본 문자열)을 돌려준다.

    정수  → '9,000,000  구백만' / 복사는 '9000000'
    소수  → '0.0966666  (9.67%)' / 복사는 '0.0966666'
    백분율 병기는 절댓값이 1 이하일 때만 표시한다.
    """
    value = normalize_result(value)
    if isinstance(value, int):
        raw = str(value)
        display = f"{value:,}"
        korean = korean_number(value)
        return (f"{display}  {korean}" if korean else display), raw
    raw = repr(value)
    if value != value or value in (float("inf"), float("-inf")):  # NaN/무한대
        return raw, raw
    if abs(value) <= 1:
        return f"{value:,}  ({format_percent(value)})", raw
    return f"{value:,}", raw

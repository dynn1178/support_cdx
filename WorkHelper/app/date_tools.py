from __future__ import annotations

import re
from datetime import date, datetime, timedelta


DATE_TOKEN_RE = re.compile(r"\{([^{}]+)\}")
OFFSET_RE = re.compile(r"([+-]\d+)([DWMQY])$", re.IGNORECASE)
LEGACY_TOKEN_RE = re.compile(r"^date(?::([^}:]+))?(?::([^}]+))?$", re.IGNORECASE)

KO_WEEKDAYS_SHORT = ["월", "화", "수", "목", "금", "토", "일"]
KO_WEEKDAYS_LONG = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
EN_WEEKDAYS_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
EN_WEEKDAYS_LONG = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    month_lengths = [31, 29 if is_leap_year(year) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return value.replace(year=year, month=month, day=min(value.day, month_lengths[month - 1]))


def is_leap_year(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def add_business_days(value: date, days: int) -> date:
    direction = 1 if days >= 0 else -1
    remaining = abs(days)
    current = value
    while remaining:
        current += timedelta(days=direction)
        if current.weekday() < 5:
            remaining -= 1
    return current


def apply_offset(value: date, expression: str = "", business_days: bool = False) -> date:
    expression = expression.strip().replace(" ", "")
    if not expression:
        return value

    short_match = re.fullmatch(r"([+-]?\d+)([DWMQY])", expression, re.IGNORECASE)
    if short_match:
        return apply_short_offset(value, int(short_match.group(1)), short_match.group(2), business_days)

    legacy_match = re.fullmatch(r"([+-]?\d+)(day|days|week|weeks|month|months|quarter|quarters|year|years)", expression, re.IGNORECASE)
    if not legacy_match:
        return value
    amount = int(legacy_match.group(1))
    unit = legacy_match.group(2).lower()
    if unit.startswith("day"):
        return apply_short_offset(value, amount, "D", business_days)
    if unit.startswith("week"):
        return apply_short_offset(value, amount, "W", business_days)
    if unit.startswith("month"):
        return apply_short_offset(value, amount, "M", business_days)
    if unit.startswith("quarter"):
        return apply_short_offset(value, amount, "Q", business_days)
    if unit.startswith("year"):
        return apply_short_offset(value, amount, "Y", business_days)
    return value


def apply_short_offset(value: date, amount: int, unit: str, business_days: bool = False) -> date:
    unit = unit.upper()
    if unit == "D":
        return add_business_days(value, amount) if business_days else value + timedelta(days=amount)
    if unit == "W":
        return value + timedelta(weeks=amount)
    if unit == "M":
        return add_months(value, amount)
    if unit == "Q":
        return add_months(value, amount * 3)
    if unit == "Y":
        return add_months(value, amount * 12)
    return value


def split_format_and_offset(token: str) -> tuple[str, str]:
    token = token.strip()
    legacy = LEGACY_TOKEN_RE.fullmatch(token)
    if legacy:
        return legacy.group(1) or "yyyy-mm-dd", legacy.group(2) or ""

    match = OFFSET_RE.search(token.replace(" ", ""))
    if not match:
        return token or "yyyy-mm-dd", ""
    compact = token.replace(" ", "")
    offset = match.group(0)
    return compact[: match.start()] or "yyyy-mm-dd", offset


def format_date(value: date, fmt: str) -> str:
    quarter = (value.month - 1) // 3 + 1
    week = value.isocalendar().week
    replacements = {
        "yyyy": f"{value.year:04d}",
        "yy": f"{value.year % 100:02d}",
        "qq": f"{quarter}분기",
        "q": f"{quarter}Q",
        "mm": f"{value.month:02d}",
        "m": str(value.month),
        "ww": f"{week}주차",
        "w": f"{week}W",
        "dd": f"{value.day:02d}",
        "d": str(value.day),
        "dddd": KO_WEEKDAYS_LONG[value.weekday()],
        "ddd": KO_WEEKDAYS_SHORT[value.weekday()],
        "aaaa": EN_WEEKDAYS_LONG[value.weekday()],
        "aaa": EN_WEEKDAYS_SHORT[value.weekday()],
    }
    result = fmt or "yyyy-mm-dd"
    token_re = re.compile("|".join(re.escape(token) for token in sorted(replacements, key=len, reverse=True)), re.IGNORECASE)
    return token_re.sub(lambda match: replacements[match.group(0).lower()], result)


def render_date_template(template: str, base: date | None = None, business_days: bool = False) -> str:
    base_date = base or datetime.now().date()

    def replace(match: re.Match[str]) -> str:
        fmt, offset = split_format_and_offset(match.group(1))
        return format_date(apply_offset(base_date, offset, business_days), fmt)

    return DATE_TOKEN_RE.sub(replace, template)

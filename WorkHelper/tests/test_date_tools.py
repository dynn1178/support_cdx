from datetime import date

from app.date_tools import (
    add_business_days,
    add_months,
    apply_offset,
    format_date,
    is_leap_year,
    render_date_template,
    split_format_and_offset,
)


def test_add_months_clamps_day_end():
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)  # 윤년
    assert add_months(date(2026, 3, 15), -3) == date(2025, 12, 15)


def test_is_leap_year():
    assert is_leap_year(2024)
    assert not is_leap_year(2025)
    assert not is_leap_year(1900)
    assert is_leap_year(2000)


def test_add_business_days_skips_weekend():
    friday = date(2026, 7, 3)
    assert add_business_days(friday, 1) == date(2026, 7, 6)  # 월요일
    assert add_business_days(friday, -1) == date(2026, 7, 2)


def test_apply_offset_short_and_legacy():
    base = date(2026, 7, 4)
    assert apply_offset(base, "+1D") == date(2026, 7, 5)
    assert apply_offset(base, "-1W") == date(2026, 6, 27)
    assert apply_offset(base, "+1M") == date(2026, 8, 4)
    assert apply_offset(base, "+1Q") == date(2026, 10, 4)
    assert apply_offset(base, "+1Y") == date(2027, 7, 4)
    assert apply_offset(base, "+2days") == date(2026, 7, 6)
    assert apply_offset(base, "") == base
    assert apply_offset(base, "garbage") == base


def test_split_format_and_offset():
    assert split_format_and_offset("yyyy-mm-dd+1D") == ("yyyy-mm-dd", "+1D")
    assert split_format_and_offset("yyyy-mm-dd") == ("yyyy-mm-dd", "")
    assert split_format_and_offset("") == ("yyyy-mm-dd", "")


def test_format_date_tokens():
    value = date(2026, 7, 4)  # 토요일
    assert format_date(value, "yyyy-mm-dd") == "2026-07-04"
    assert format_date(value, "yy.m.d") == "26.7.4"
    assert format_date(value, "ddd") == "토"
    assert format_date(value, "aaa") == "Sat"


def test_render_date_template():
    base = date(2026, 7, 4)
    assert render_date_template("{yyyy-mm-dd}_보고", base=base) == "2026-07-04_보고"
    assert render_date_template("{yyyy-mm-dd+1D}", base=base) == "2026-07-05"
    assert render_date_template("변수 없음", base=base) == "변수 없음"

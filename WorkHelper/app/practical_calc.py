"""계산기 탭의 실용 계산 — 단위/진법 변환, 퍼센트, 세금(부가세), 환율, 이자 계산.

Qt/UI에 의존하지 않는 순수 함수만 모아, 단독으로 테스트할 수 있다.
실제 화면(콤보박스·입력창)은 ui/tab_calculator.py 가 담당한다.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 길이 변환 (기준 단위: 미터)
# ---------------------------------------------------------------------------

LENGTH_UNITS: dict[str, float] = {
    "mm": 0.001,
    "cm": 0.01,
    "m": 1.0,
    "km": 1000.0,
    "in(인치)": 0.0254,
    "ft(피트)": 0.3048,
    "yd(야드)": 0.9144,
    "mile(마일)": 1609.344,
}


def convert_length(value: float, from_unit: str, to_unit: str) -> float:
    return value * LENGTH_UNITS[from_unit] / LENGTH_UNITS[to_unit]


# ---------------------------------------------------------------------------
# 무게 변환 (기준 단위: 킬로그램)
# ---------------------------------------------------------------------------

WEIGHT_UNITS: dict[str, float] = {
    "mg": 0.000001,
    "g": 0.001,
    "kg": 1.0,
    "t(톤)": 1000.0,
    "oz(온스)": 0.0283495231,
    "lb(파운드)": 0.45359237,
}


def convert_weight(value: float, from_unit: str, to_unit: str) -> float:
    return value * WEIGHT_UNITS[from_unit] / WEIGHT_UNITS[to_unit]


# ---------------------------------------------------------------------------
# 온도 변환
# ---------------------------------------------------------------------------

TEMPERATURE_UNITS = ("섭씨(°C)", "화씨(°F)", "켈빈(K)")


def _to_celsius(value: float, unit: str) -> float:
    if unit == "섭씨(°C)":
        return value
    if unit == "화씨(°F)":
        return (value - 32) * 5 / 9
    if unit == "켈빈(K)":
        return value - 273.15
    raise ValueError(f"알 수 없는 온도 단위: {unit}")


def _from_celsius(celsius: float, unit: str) -> float:
    if unit == "섭씨(°C)":
        return celsius
    if unit == "화씨(°F)":
        return celsius * 9 / 5 + 32
    if unit == "켈빈(K)":
        return celsius + 273.15
    raise ValueError(f"알 수 없는 온도 단위: {unit}")


def convert_temperature(value: float, from_unit: str, to_unit: str) -> float:
    return _from_celsius(_to_celsius(value, from_unit), to_unit)


# ---------------------------------------------------------------------------
# 진법 변환
# ---------------------------------------------------------------------------

BASE_OPTIONS = (2, 8, 10, 16)
_BASE_PREFIX = {2: "0b", 8: "0o", 16: "0x"}


def convert_base(text: str, from_base: int, to_base: int) -> str:
    """from_base 진법 문자열을 to_base 진법 문자열로 바꾼다. 접두사(0x 등)는 없이 돌려준다."""
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("변환할 값을 입력해주세요.")
    negative = cleaned.startswith("-")
    if negative:
        cleaned = cleaned[1:]
    prefix = _BASE_PREFIX.get(from_base, "")
    if prefix and cleaned.lower().startswith(prefix):
        cleaned = cleaned[len(prefix):]
    value = int(cleaned, from_base)
    if negative:
        value = -value
    if to_base == 2:
        digits = bin(abs(value))[2:]
    elif to_base == 8:
        digits = oct(abs(value))[2:]
    elif to_base == 16:
        digits = hex(abs(value))[2:].upper()
    elif to_base == 10:
        digits = str(abs(value))
    else:
        raise ValueError(f"지원하지 않는 진법입니다: {to_base}")
    return ("-" if value < 0 else "") + digits


# ---------------------------------------------------------------------------
# 퍼센트 계산 (전체값/비율값/일부값/증감값/증감률)
# ---------------------------------------------------------------------------


def percent_of(base: float, percent: float) -> float:
    """전체값의 비율값(%)만큼은 얼마인지."""
    return base * percent / 100


def percent_ratio(base: float, part: float) -> float:
    """일부값이 전체값의 몇 %인지."""
    if base == 0:
        raise ZeroDivisionError("전체값은 0이 될 수 없습니다.")
    return part / base * 100


def percent_change(base: float, new_value: float) -> float:
    """전체값이 새 값으로 변하면 증감률(%)이 얼마인지."""
    if base == 0:
        raise ZeroDivisionError("전체값은 0이 될 수 없습니다.")
    return (new_value - base) / base * 100


def apply_percent_change(base: float, rate_percent: float) -> float:
    """전체값이 증감률(%)만큼 변하면 결과값이 얼마인지."""
    return base * (1 + rate_percent / 100)


# ---------------------------------------------------------------------------
# 세금(부가세) 계산
# ---------------------------------------------------------------------------


def tax_from_supply(supply: float, rate_percent: float = 10.0) -> tuple[float, float]:
    """공급가액 -> (세액, 합계금액)"""
    tax = supply * rate_percent / 100
    return tax, supply + tax


def tax_from_total(total: float, rate_percent: float = 10.0) -> tuple[float, float]:
    """합계금액 -> (공급가액, 세액) 역산"""
    supply = total / (1 + rate_percent / 100)
    return supply, total - supply


# ---------------------------------------------------------------------------
# 환율 계산 (환율은 실시간 조회 없이 직접 입력)
# ---------------------------------------------------------------------------


def exchange_convert(amount: float, rate: float) -> float:
    """기준 통화 금액에 환율을 곱해 대상 통화 금액을 구한다."""
    return amount * rate


# ---------------------------------------------------------------------------
# 이자 계산 (단리/복리)
# ---------------------------------------------------------------------------

COMPOUND_FREQUENCIES: dict[str, int] = {
    "연 1회": 1,
    "반기 1회": 2,
    "분기 1회": 4,
    "월 1회": 12,
    "일 1회": 365,
}


def simple_interest(principal: float, annual_rate_percent: float, months: float) -> tuple[float, float]:
    """단리: (이자, 원리금 합계)"""
    years = months / 12
    interest = principal * annual_rate_percent / 100 * years
    return interest, principal + interest


def compound_interest(principal: float, annual_rate_percent: float, months: float, compounds_per_year: int) -> tuple[float, float]:
    """복리: (이자, 원리금 합계)"""
    years = months / 12
    n = max(1, compounds_per_year)
    total = principal * (1 + (annual_rate_percent / 100) / n) ** (n * years)
    return total - principal, total

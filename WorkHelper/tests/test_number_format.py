from app.number_format import format_calc_result, format_percent, korean_number


def test_korean_number_basic_units():
    assert korean_number(0) == "영"
    assert korean_number(15) == "십오"
    assert korean_number(100) == "백"
    assert korean_number(9000000) == "구백만"
    assert korean_number(100000000) == "일억"
    assert korean_number(1234567) == "백이십삼만 사천오백육십칠"


def test_korean_number_omits_il_before_man():
    assert korean_number(10000) == "만"
    assert korean_number(12345) == "만 이천삼백사십오"


def test_korean_number_negative_and_overflow():
    assert korean_number(-5000) == "마이너스 오천"
    assert korean_number(10**25) == ""  # 해 단위를 넘으면 병기하지 않는다


def test_integer_result_shows_separator_and_korean():
    display, raw = format_calc_result(900 * 10000)
    assert display == "9,000,000  구백만"
    assert raw == "9000000"  # 복사는 쉼표 없이


def test_float_that_is_integer_is_treated_as_integer():
    display, raw = format_calc_result(3.0)
    assert display.startswith("3  ")
    assert raw == "3"


def test_decimal_result_shows_percent():
    display, raw = format_calc_result(0.0966666)
    assert display == "0.0966666  (9.67%)"
    assert raw == "0.0966666"


def test_format_percent_trims_zeros():
    assert format_percent(0.5) == "50%"
    assert format_percent(0.1234) == "12.34%"
    assert format_percent(0) == "0%"
    assert format_percent(0.00001) == "0.001%"

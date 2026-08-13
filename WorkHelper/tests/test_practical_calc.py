import pytest

from app.practical_calc import (
    apply_percent_change,
    compound_interest,
    convert_base,
    convert_length,
    convert_temperature,
    convert_weight,
    exchange_convert,
    percent_change,
    percent_of,
    percent_ratio,
    simple_interest,
    tax_from_supply,
    tax_from_total,
)


def test_convert_length_km_to_m():
    assert convert_length(1, "km", "m") == pytest.approx(1000.0)


def test_convert_length_mile_to_km():
    assert convert_length(1, "mile(마일)", "km") == pytest.approx(1.609344)


def test_convert_weight_kg_to_lb():
    assert convert_weight(1, "kg", "lb(파운드)") == pytest.approx(2.2046226, rel=1e-5)


def test_convert_temperature_celsius_to_fahrenheit():
    assert convert_temperature(0, "섭씨(°C)", "화씨(°F)") == pytest.approx(32.0)
    assert convert_temperature(100, "섭씨(°C)", "화씨(°F)") == pytest.approx(212.0)


def test_convert_temperature_celsius_to_kelvin():
    assert convert_temperature(0, "섭씨(°C)", "켈빈(K)") == pytest.approx(273.15)


def test_convert_base_decimal_to_hex_and_back():
    assert convert_base("255", 10, 16) == "FF"
    assert convert_base("FF", 16, 10) == "255"


def test_convert_base_binary():
    assert convert_base("10", 10, 2) == "1010"
    assert convert_base("1010", 2, 10) == "10"


def test_convert_base_negative():
    assert convert_base("-10", 10, 16) == "-A"


def test_percent_of():
    assert percent_of(10000, 20) == pytest.approx(2000.0)


def test_percent_ratio():
    assert percent_ratio(10000, 500) == pytest.approx(5.0)


def test_percent_change_increase():
    assert percent_change(10000, 25000) == pytest.approx(150.0)


def test_apply_percent_change():
    assert apply_percent_change(10000, 25) == pytest.approx(12500.0)


def test_percent_ratio_zero_base_raises():
    with pytest.raises(ZeroDivisionError):
        percent_ratio(0, 10)


def test_tax_from_supply_default_vat():
    tax, total = tax_from_supply(10000)
    assert tax == pytest.approx(1000.0)
    assert total == pytest.approx(11000.0)


def test_tax_from_total_round_trip():
    supply, tax = tax_from_total(11000)
    assert supply == pytest.approx(10000.0)
    assert tax == pytest.approx(1000.0)


def test_exchange_convert():
    assert exchange_convert(100, 1350.5) == pytest.approx(135050.0)


def test_simple_interest_one_year():
    interest, total = simple_interest(1_000_000, 5, 12)
    assert interest == pytest.approx(50_000.0)
    assert total == pytest.approx(1_050_000.0)


def test_compound_interest_matches_simple_for_one_period():
    interest, total = compound_interest(1_000_000, 5, 12, 1)
    assert interest == pytest.approx(50_000.0)
    assert total == pytest.approx(1_050_000.0)


def test_compound_interest_monthly_grows_more_than_simple():
    simple, _ = simple_interest(1_000_000, 12, 12)
    compound, _ = compound_interest(1_000_000, 12, 12, 12)
    assert compound > simple

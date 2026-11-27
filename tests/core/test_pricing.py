from datetime import date, time

import pytest

from custom_components.day_ahead_price_forecast.core.errors import FormulaError
from custom_components.day_ahead_price_forecast.core.models import Forecast
from custom_components.day_ahead_price_forecast.core.pricing import PriceCalculator
from custom_components.day_ahead_price_forecast.core.variants import FormulaVariant


@pytest.fixture
def forecast(payload):
    return Forecast.from_dict(payload)


def test_applies_to_known_and_forecast(forecast):
    result = PriceCalculator([FormulaVariant("(P + 0,1) * 2")]).apply(forecast)
    assert result.known[0].value == pytest.approx(0.4)
    assert result.known[0].p10 is None and result.known[0].p90 is None
    point = result.points[0]
    assert (point.value, point.p10, point.p90) == pytest.approx((0.5, 0.4, 0.6))
    assert point.p10 <= point.value <= point.p90
    assert point.h == 1 and point.start == forecast.points[0].start
    assert forecast.points[0].value == 0.15


def test_negative_clamp(forecast):
    variants = [FormulaVariant("P - 0.13")]
    unclamped = PriceCalculator(variants).apply(forecast)
    assert unclamped.points[0].p10 == pytest.approx(-0.03)
    clamped = PriceCalculator(variants, allow_negative=False).apply(forecast)
    assert clamped.points[0].p10 == 0.0
    assert clamped.points[0].value == pytest.approx(0.02)
    assert clamped.known[0].value == 0.0


def test_variant_per_point(forecast):
    variants = [
        FormulaVariant("P"),
        FormulaVariant("P + 1", start_time=time(0, 15), end_time=time(6)),
    ]
    result = PriceCalculator(variants).apply(forecast)
    assert result.points[0].value == 0.15
    assert result.points[1].value == pytest.approx(1.16)
    assert result.known[1].value == 0.12


def test_no_matching_variant(forecast):
    calculator = PriceCalculator([FormulaVariant("P", valid_from=date(2030, 1, 1))])
    with pytest.raises(FormulaError, match="no formula variant"):
        calculator.apply(forecast)


def test_invalid_formula_raises_at_init():
    with pytest.raises(FormulaError):
        PriceCalculator([FormulaVariant("1 - P")])

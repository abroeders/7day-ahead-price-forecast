import pytest

from custom_components.day_ahead_price_forecast.core.errors import ForecastError
from custom_components.day_ahead_price_forecast.zones import ZONES, get_zone


def test_nl_zone_properties():
    zone = get_zone("NL")
    assert zone.code == "NL"
    assert zone.timezone == "Europe/Amsterdam"
    assert zone.currency == "EUR"


def test_lookup_is_case_insensitive():
    assert get_zone("nl") is ZONES["NL"]


def test_unknown_zone_raises():
    with pytest.raises(ForecastError):
        get_zone("XX")


@pytest.mark.parametrize(("value", "ok"), [(0.1, True), (-0.4, True), (-0.6, False), (5.0, False)])
def test_nl_price_plausibility(value, ok):
    assert get_zone("NL").is_valid_price(value) is ok

from datetime import UTC, datetime, timedelta

import pytest

from custom_components.day_ahead_price_forecast.core.errors import ForecastError
from custom_components.day_ahead_price_forecast.core.models import Forecast


def test_parses_sample(payload):
    forecast = Forecast.from_dict(payload)
    assert forecast.zone == "NL"
    assert forecast.node == "a"
    assert forecast.stale is False
    assert forecast.created == datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
    assert forecast.known_until.utcoffset() == timedelta(hours=1)
    assert len(forecast.known) == 2
    assert forecast.known[0].p10 is None and forecast.known[0].h is None
    first = forecast.points[0]
    assert (first.value, first.p10, first.p90, first.h) == (0.15, 0.1, 0.2, 1)
    assert isinstance(forecast.points, tuple)
    assert forecast.accuracy["hours"] == 600


def test_ignores_unknown_fields(payload):
    payload["new_field"] = 1
    payload["forecast"][0]["extra"] = "x"
    assert len(Forecast.from_dict(payload).points) == 2


def test_unknown_schema(payload):
    payload["schema"] = 2
    with pytest.raises(ForecastError, match="schema"):
        Forecast.from_dict(payload)


@pytest.mark.parametrize("key", ["zone", "created", "trained", "known_until", "known", "forecast"])
def test_missing_key(payload, key):
    del payload[key]
    with pytest.raises(ForecastError):
        Forecast.from_dict(payload)


def test_missing_point_key(payload):
    del payload["forecast"][0]["p90"]
    with pytest.raises(ForecastError):
        Forecast.from_dict(payload)


@pytest.mark.parametrize(
    "key, value",
    [("created", "not a date"), ("created", "2026-11-27T12:00:00"), ("known_until", 5)],
)
def test_invalid_datetime(payload, key, value):
    payload[key] = value
    with pytest.raises(ForecastError):
        Forecast.from_dict(payload)


def test_invalid_number(payload):
    payload["forecast"][0]["value"] = "0.15"
    with pytest.raises(ForecastError):
        Forecast.from_dict(payload)


def test_not_an_object():
    with pytest.raises(ForecastError):
        Forecast.from_dict([])


@pytest.mark.parametrize("p10, value, p90", [(0.2, 0.15, 0.3), (0.1, 0.15, 0.14)])
def test_band_violation(payload, p10, value, p90):
    payload["forecast"][0].update(p10=p10, value=value, p90=p90)
    with pytest.raises(ForecastError, match="band"):
        Forecast.from_dict(payload)


def test_band_edges_allowed(payload):
    payload["forecast"][0].update(p10=0.15, value=0.15, p90=0.15)
    assert Forecast.from_dict(payload).points[0].p10 == 0.15

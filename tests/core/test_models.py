from dataclasses import replace
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from custom_components.day_ahead_price_forecast.core.errors import ForecastError
from custom_components.day_ahead_price_forecast.core.models import Forecast

AMS = ZoneInfo("Europe/Amsterdam")


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


def _spread(payload, days):
    """Forecast with one point per day, starting at known_until."""
    start = datetime.fromisoformat(payload["known_until"])
    payload["forecast"] = [
        {
            "start": (start + timedelta(days=d)).isoformat(),
            "end": (start + timedelta(days=d, minutes=15)).isoformat(),
            "value": 0.1,
            "p10": 0.05,
            "p90": 0.2,
            "h": d + 1,
        }
        for d in range(days)
    ]
    return Forecast.from_dict(payload)


@pytest.mark.parametrize(("days", "expected"), [(1, 1), (2, 2), (7, 7), (10, 7)])
def test_limited_to_cuts_after_days(payload, days, expected):
    forecast = _spread(payload, 7)
    assert len(forecast.limited_to(days, AMS).points) == expected


def test_limited_to_counts_calendar_days_over_dst(payload):
    # Clocks go back on 2026-10-25: that local day has 25 hours.
    payload["known_until"] = "2026-10-24T00:00:00+02:00"
    forecast = _spread(payload, 4)
    local_days = [datetime(2026, 10, 24 + d, 0, 0, tzinfo=AMS) for d in range(4)]
    points = tuple(
        replace(p, start=t, end=t + timedelta(minutes=15))
        for p, t in zip(forecast.points, local_days, strict=True)
    )
    dst = replace(forecast, points=points).limited_to(2, AMS)
    assert [p.start.day for p in dst.points] == [24, 25]


def test_limited_to_keeps_known_prices(payload):
    forecast = Forecast.from_dict(payload)
    assert forecast.limited_to(1, AMS).known == forecast.known

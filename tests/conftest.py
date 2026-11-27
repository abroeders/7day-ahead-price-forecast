import copy

import pytest

SAMPLE = {
    "schema": 1,
    "node": "a",
    "zone": "NL",
    "unit": "EUR/kWh",
    "created": "2026-11-27T12:00:00+00:00",
    "trained": "2026-11-27T03:00:00+00:00",
    "stale": False,
    "known_until": "2026-11-28T00:00:00+01:00",
    "known": [
        {"start": "2026-11-27T23:30:00+01:00", "end": "2026-11-27T23:45:00+01:00", "value": 0.1},
        {"start": "2026-11-27T23:45:00+01:00", "end": "2026-11-28T00:00:00+01:00", "value": 0.12},
    ],
    "forecast": [
        {
            "start": "2026-11-28T00:00:00+01:00",
            "end": "2026-11-28T00:15:00+01:00",
            "value": 0.15,
            "p10": 0.1,
            "p90": 0.2,
            "h": 1,
        },
        {
            "start": "2026-11-28T00:15:00+01:00",
            "end": "2026-11-28T00:30:00+01:00",
            "value": 0.16,
            "p10": 0.11,
            "p90": 0.21,
            "h": 1,
        },
    ],
    "accuracy": {"mae": {"1": 0.02}, "bias": {"1": 0.0}, "coverage": {"1": 0.8}, "hours": 600},
}


@pytest.fixture
def payload() -> dict:
    return copy.deepcopy(SAMPLE)

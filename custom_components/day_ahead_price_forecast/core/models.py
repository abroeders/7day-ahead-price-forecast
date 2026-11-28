"""Forecast model objects (contract version 1 of the forecast service)."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, tzinfo
from typing import Any

from .errors import ForecastError

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class PricePoint:
    """One quarter hour; prices are bare market prices in EUR/kWh."""

    start: datetime
    end: datetime
    value: float
    p10: float | None = None
    p90: float | None = None
    h: int | None = None


@dataclass(frozen=True)
class Forecast:
    zone: str
    created: datetime
    trained: datetime
    known_until: datetime
    known: tuple[PricePoint, ...]
    points: tuple[PricePoint, ...]
    accuracy: dict
    node: str
    stale: bool

    def limited_to(self, days: int, tz: tzinfo) -> Forecast:
        """Copy with the forecast cut at ``known_until`` plus ``days`` local calendar days."""
        local = self.known_until.astimezone(tz).replace(tzinfo=None)
        limit = (local + timedelta(days=days)).replace(tzinfo=tz)
        return replace(self, points=tuple(p for p in self.points if p.start < limit))

    @classmethod
    def from_dict(cls, payload: Any) -> Forecast:
        """Parse a /v1/forecast payload; raise ForecastError when invalid."""
        try:
            return cls._parse(payload)
        except ForecastError:
            raise
        except (KeyError, TypeError, ValueError, AttributeError) as err:
            raise ForecastError(f"invalid forecast: {err!r}") from err

    @classmethod
    def _parse(cls, payload: Any) -> Forecast:
        if not isinstance(payload, dict):
            raise ForecastError("forecast is not a JSON object")
        if payload.get("schema") != SCHEMA_VERSION:
            raise ForecastError(f"unknown schema: {payload.get('schema')!r}")
        known = tuple(_point(item, forecast=False) for item in payload["known"])
        points = tuple(_point(item, forecast=True) for item in payload["forecast"])
        accuracy = payload.get("accuracy", {})
        if not isinstance(accuracy, dict):
            raise ForecastError("accuracy is not an object")
        return cls(
            zone=_text(payload["zone"], "zone"),
            created=_time(payload["created"]),
            trained=_time(payload["trained"]),
            known_until=_time(payload["known_until"]),
            known=known,
            points=points,
            accuracy=accuracy,
            node=_text(payload.get("node", ""), "node"),
            stale=_flag(payload.get("stale", False)),
        )


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise ForecastError(f"{name} is not a string")
    return value


def _flag(value: Any) -> bool:
    if not isinstance(value, bool):
        raise ForecastError("stale is not a boolean")
    return value


def _time(value: Any) -> datetime:
    parsed = datetime.fromisoformat(_text(value, "datetime"))
    if parsed.tzinfo is None:
        raise ForecastError(f"datetime without offset: {value!r}")
    return parsed


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ForecastError(f"{name} is not a number: {value!r}")
    if not math.isfinite(value):
        raise ForecastError(f"{name} is not finite")
    return float(value)


def _point(item: Any, *, forecast: bool) -> PricePoint:
    if not isinstance(item, dict):
        raise ForecastError("price point is not an object")
    start = _time(item["start"])
    end = _time(item["end"])
    if end <= start:
        raise ForecastError(f"end not after start: {item['start']!r}")
    value = _number(item["value"], "value")
    if not forecast:
        return PricePoint(start, end, value)
    p10 = _number(item["p10"], "p10")
    p90 = _number(item["p90"], "p90")
    h = item["h"]
    if isinstance(h, bool) or not isinstance(h, int) or h < 1:
        raise ForecastError(f"invalid h: {h!r}")
    if not p10 <= value <= p90:
        raise ForecastError(f"band violated at {item['start']}: {p10} {value} {p90}")
    return PricePoint(start, end, value, p10, p90, h)

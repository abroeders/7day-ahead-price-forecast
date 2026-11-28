"""Interface of a forecast source."""

from __future__ import annotations

from typing import Protocol

from ..core.models import Forecast


class ForecastProvider(Protocol):
    async def fetch(self, zone: str, days: int = 7) -> Forecast:
        """Return the forecast for a zone; raise ForecastError when unavailable.

        ``days`` is a hint that lets the source send less data.
        """

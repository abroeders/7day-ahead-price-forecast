"""Provider that reads the forecast service over HTTP, with failover."""

from __future__ import annotations

import asyncio
import json
import random
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from ..core.errors import ForecastError
from ..core.models import Forecast

HttpGet = Callable[[str, float], Awaitable[tuple[int, bytes]]]

DEFAULT_MAX_AGE = timedelta(hours=3)
DEFAULT_TIMEOUT = 5.0
MAX_DAYS = 7


def _utcnow() -> datetime:
    return datetime.now(UTC)


class RemoteProvider:
    def __init__(
        self,
        servers: Sequence[str],
        http_get: HttpGet,
        max_age: timedelta = DEFAULT_MAX_AGE,
        timeout: float = DEFAULT_TIMEOUT,
        rng: random.Random | None = None,
        now: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._servers = tuple(servers)
        self._http_get = http_get
        self._max_age = max_age
        self._timeout = timeout
        self._rng = rng or random.Random()
        self._now = now
        self._last_node: str | None = None

    @property
    def last_node(self) -> str | None:
        """Node name of the server that served the last successful fetch."""
        return self._last_node

    async def fetch(self, zone: str, days: int = MAX_DAYS) -> Forecast:
        servers = list(self._servers)
        self._rng.shuffle(servers)
        reasons: list[str] = []
        for base in servers:
            url = f"{base.rstrip('/')}/v1/forecast?zone={quote(zone)}&days={days}"
            try:
                status, body = await asyncio.wait_for(
                    self._http_get(url, self._timeout), self._timeout
                )
            except TimeoutError:
                reasons.append(f"{url}: timeout")
                continue
            except Exception as err:  # noqa: BLE001 - any transport failure means failover
                reasons.append(f"{url}: {type(err).__name__}: {err}")
                continue
            if status == 404:
                raise ForecastError(f"unknown zone {zone!r} ({url})")
            if status != 200:
                reasons.append(f"{url}: HTTP {status}")
                continue
            try:
                forecast = Forecast.from_dict(json.loads(body))
            except (ValueError, ForecastError) as err:
                reasons.append(f"{url}: invalid forecast: {err}")
                continue
            if forecast.stale:
                reasons.append(f"{url}: stale")
                continue
            if self._now() - forecast.created > self._max_age:
                reasons.append(f"{url}: forecast too old ({forecast.created.isoformat()})")
                continue
            self._last_node = forecast.node
            return forecast
        raise ForecastError("no server gave a usable forecast: " + "; ".join(reasons))

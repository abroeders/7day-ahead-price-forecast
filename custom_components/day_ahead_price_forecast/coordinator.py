"""Coordinator: one forecast refresh per base controller, shared by its sub-controllers."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_FORECAST_DAYS,
    CONF_ZONE,
    DEFAULT_FORECAST_DAYS,
    DEFAULT_SERVERS,
    DOMAIN,
    UPDATE_INTERVAL,
)
from .core.errors import ForecastError
from .core.models import Forecast
from .providers.base import ForecastProvider
from .providers.remote import RemoteProvider
from .zones import ZONES

_LOGGER = logging.getLogger(__name__)

type ForecastConfigEntry = ConfigEntry[ForecastCoordinator]


class ForecastCoordinator(DataUpdateCoordinator[Forecast]):
    """Fetches the bare market price forecast of one zone."""

    config_entry: ForecastConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ForecastConfigEntry,
        provider: ForecastProvider | None = None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.data[CONF_ZONE]}",
            update_interval=UPDATE_INTERVAL,
        )
        self.zone: str = entry.data[CONF_ZONE]
        self.forecast_days: int = entry.data.get(CONF_FORECAST_DAYS, DEFAULT_FORECAST_DAYS)
        self._provider = provider or RemoteProvider(DEFAULT_SERVERS, self._http_get)

    async def _http_get(self, url: str, timeout: float) -> tuple[int, bytes]:
        session = async_get_clientsession(self.hass)
        async with session.get(url) as response:
            return response.status, await response.read()

    @property
    def node(self) -> str | None:
        """Node that served the last successful refresh."""
        return getattr(self._provider, "last_node", None)

    async def _async_update_data(self) -> Forecast:
        try:
            forecast = await self._provider.fetch(self.zone, self.forecast_days)
        except ForecastError as err:
            raise UpdateFailed(str(err)) from err
        # A server that ignores the days parameter still gives the same result.
        tz = await dt_util.async_get_time_zone(ZONES[self.zone].timezone)
        return forecast.limited_to(self.forecast_days, tz or dt_util.UTC)

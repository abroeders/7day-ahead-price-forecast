"""Day-ahead price forecast: a client of the forecast module with formula-based sub-controllers."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .const import DOMAIN
from .coordinator import ForecastConfigEntry, ForecastCoordinator

PLATFORMS = [Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

CARD_URL = f"/{DOMAIN}/day-ahead-price-forecast-card.js"
WWW_URL = f"/{DOMAIN}"
WWW_DIR = Path(__file__).parent / "www"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the Lovelace card and load it in every dashboard."""
    integration = await async_get_integration(hass, DOMAIN)
    await hass.http.async_register_static_paths(
        [StaticPathConfig(WWW_URL, str(WWW_DIR), cache_headers=False)]
    )
    # The version in the query string makes browsers fetch the new card after an update.
    add_extra_js_url(hass, f"{CARD_URL}?v={integration.version}")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ForecastConfigEntry) -> bool:
    coordinator = ForecastCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ForecastConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload(hass: HomeAssistant, entry: ForecastConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)

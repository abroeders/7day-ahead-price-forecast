"""Run the integration lifecycle under blockbuster: any blocking call in the loop fails."""

from blockbuster import blockbuster_ctx
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.day_ahead_price_forecast.const import DOMAIN


async def test_lifecycle_does_not_block_the_event_loop(
    hass: HomeAssistant, entry, provider
) -> None:
    # The dependencies are Home Assistant's own code and set up first, outside the check.
    for dependency in ("http", "frontend"):
        assert await async_setup_component(hass, dependency, {})

    with blockbuster_ctx() as blockbuster:
        # Log output goes to a stream that Home Assistant's test setup owns, not to the integration.
        blockbuster.functions["io.TextIOWrapper.write"].deactivate()

        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED

        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.NOT_LOADED

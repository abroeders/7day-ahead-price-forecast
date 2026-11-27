from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.day_ahead_price_forecast.const import DOMAIN
from custom_components.day_ahead_price_forecast.core.errors import ForecastError

NOW = "2026-11-28T00:20:00+01:00"


def _sub(formula="(P + 0.1) * 2", negative=True):
    return ConfigSubentryData(
        data={"formula": formula, "allow_negative": negative},
        subentry_type="controller",
        title="Purchase",
        unique_id=None,
    )


async def test_config_flow_creates_entry_once(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"zone": "NL"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Netherlands"
    again = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(again["flow_id"], {"zone": "NL"})
    assert result["type"] is FlowResultType.ABORT


async def test_subentry_flow_validates_formula(hass: HomeAssistant, entry, provider) -> None:
    await hass.config_entries.async_setup(entry.entry_id)
    flow = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "controller"), context={"source": "user"}
    )
    bad = await hass.config_entries.subentries.async_configure(
        flow["flow_id"], {"name": "x", "formula": "-P", "allow_negative": True}
    )
    assert bad["errors"] == {"formula": "invalid_formula"}
    ok = await hass.config_entries.subentries.async_configure(
        flow["flow_id"], {"name": "Purchase", "formula": "(P+0.02)*1.21", "allow_negative": False}
    )
    assert ok["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    sub = next(iter(entry.subentries.values()))
    assert sub.title == "Purchase"
    assert sub.data == {"formula": "(P+0.02)*1.21", "allow_negative": False}


async def test_forecast_sensor(hass: HomeAssistant, provider, freezer) -> None:
    freezer.move_to(NOW)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"zone": "NL"},
        unique_id="NL",
        title="Netherlands",
        subentries_data=[_sub()],
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    sensors = [s for s in hass.states.async_all("sensor") if "forecast" in s.attributes]
    assert len(sensors) == 1
    state = sensors[0]
    assert float(state.state) == (0.16 + 0.1) * 2
    assert state.attributes["forecast"][0]["p10"] == (0.1 + 0.1) * 2
    assert len(state.attributes["forecast"]) == 2


async def test_service_state_and_failure(hass: HomeAssistant, entry, provider) -> None:
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    reg = er.async_get(hass)
    ent = next(e for e in reg.entities.values() if e.unique_id.endswith("service_state"))
    state = hass.states.get(ent.entity_id)
    assert state.state == "ok"
    assert state.attributes["node"] == "a"


async def test_setup_retries_when_service_down(hass: HomeAssistant, entry, provider) -> None:
    provider.error = ForecastError("down")
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state.name == "SETUP_RETRY"

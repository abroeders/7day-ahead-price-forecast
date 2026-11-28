from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.day_ahead_price_forecast.const import CONF_ZONE, DOMAIN
from custom_components.day_ahead_price_forecast.core.models import Forecast


@pytest.fixture(autouse=True)
def _enable(enable_custom_integrations):
    return None


class FakeProvider:
    def __init__(self, payload, *_args, **_kwargs):
        self.payload = payload
        self.last_node = "a"
        self.error = None

    async def fetch(self, zone, days=7):
        if self.error:
            raise self.error
        return Forecast.from_dict(self.payload)


@pytest.fixture
def provider(payload):
    fake = FakeProvider(payload)
    with patch(
        "custom_components.day_ahead_price_forecast.coordinator.RemoteProvider",
        return_value=fake,
    ):
        yield fake


@pytest.fixture
def entry(hass):
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_ZONE: "NL"}, unique_id="NL", title="Netherlands"
    )
    entry.add_to_hass(hass)
    return entry

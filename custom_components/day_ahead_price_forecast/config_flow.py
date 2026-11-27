"""Config flow: base controller per zone; sub-controllers as config subentries."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
)

from .const import (
    CONF_ALLOW_NEGATIVE,
    CONF_FORMULA,
    CONF_ZONE,
    DEFAULT_FORMULA,
    DOMAIN,
    SUBENTRY_CONTROLLER,
)
from .core.errors import FormulaError
from .core.formula import parse
from .zones import ZONES


class DayAheadConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_ZONE])
            self._abort_if_unique_id_configured()
            zone = ZONES[user_input[CONF_ZONE]]
            return self.async_create_entry(title=zone.name, data=user_input)
        options = [SelectOptionDict(value=z.code, label=z.name) for z in ZONES.values()]
        schema = vol.Schema(
            {vol.Required(CONF_ZONE): SelectSelector(SelectSelectorConfig(options=options))}
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        return {SUBENTRY_CONTROLLER: ControllerSubentryFlow}


class ControllerSubentryFlow(ConfigSubentryFlow):
    """Add or reconfigure a sub-controller: a name, a formula over P and a negative-price switch."""

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        return await self._form("user", user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        return await self._form("reconfigure", user_input)

    async def _form(self, step_id: str, user_input: dict[str, Any] | None) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        current = self._get_reconfigure_subentry().data if step_id == "reconfigure" else {}
        if user_input is not None:
            try:
                parse(user_input[CONF_FORMULA])
            except FormulaError:
                errors[CONF_FORMULA] = "invalid_formula"
            else:
                data = {
                    CONF_FORMULA: user_input[CONF_FORMULA].strip(),
                    CONF_ALLOW_NEGATIVE: user_input[CONF_ALLOW_NEGATIVE],
                }
                title = user_input["name"].strip()
                if step_id == "reconfigure":
                    return self.async_update_and_abort(
                        self._get_entry(),
                        self._get_reconfigure_subentry(),
                        title=title,
                        data=data,
                    )
                return self.async_create_entry(title=title, data=data)
        values = user_input or {
            "name": self._get_reconfigure_subentry().title if current else "",
            CONF_FORMULA: current.get(CONF_FORMULA, DEFAULT_FORMULA),
            CONF_ALLOW_NEGATIVE: current.get(CONF_ALLOW_NEGATIVE, True),
        }
        schema = vol.Schema(
            {
                vol.Required("name", default=values["name"]): TextSelector(),
                vol.Required(CONF_FORMULA, default=values[CONF_FORMULA]): TextSelector(),
                vol.Required(CONF_ALLOW_NEGATIVE, default=values[CONF_ALLOW_NEGATIVE]): (
                    BooleanSelector()
                ),
            }
        )
        return self.async_show_form(step_id=step_id, data_schema=schema, errors=errors)

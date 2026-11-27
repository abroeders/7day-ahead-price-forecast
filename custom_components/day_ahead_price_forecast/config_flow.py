"""Config flow: base controller per zone; sub-controllers as config subentries."""

from __future__ import annotations

from datetime import date, time
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
    DateSelector,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TimeSelector,
)

from .const import (
    CONF_ALLOW_NEGATIVE,
    CONF_FORMULA,
    CONF_VARIANTS,
    CONF_ZONE,
    DEFAULT_FORMULA,
    DOMAIN,
    SUBENTRY_CONTROLLER,
)
from .core.errors import FormulaError
from .core.formula import parse
from .core.variants import FormulaVariant
from .zones import ZONES

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


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


def variant_from_dict(item: dict[str, Any]) -> FormulaVariant:
    """Build a FormulaVariant from its stored (JSON) form."""
    weekdays = item.get("weekdays")
    return FormulaVariant(
        formula=item[CONF_FORMULA],
        valid_from=date.fromisoformat(item["valid_from"]) if item.get("valid_from") else None,
        start_time=time.fromisoformat(item["start_time"]) if item.get("start_time") else None,
        end_time=time.fromisoformat(item["end_time"]) if item.get("end_time") else None,
        weekdays=frozenset(WEEKDAYS.index(d) for d in weekdays) if weekdays else None,
    )


class ControllerSubentryFlow(ConfigSubentryFlow):
    """Add or reconfigure a sub-controller: formula, negative-price switch and variants."""

    def __init__(self) -> None:
        self._name = ""
        self._data: dict[str, Any] = {}
        self._reconfigure = False

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        return await self._main("user", user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        if not self._reconfigure:
            self._reconfigure = True
            sub = self._get_reconfigure_subentry()
            self._name = sub.title
            self._data = {
                CONF_FORMULA: sub.data[CONF_FORMULA],
                CONF_ALLOW_NEGATIVE: sub.data[CONF_ALLOW_NEGATIVE],
                CONF_VARIANTS: list(sub.data.get(CONF_VARIANTS, [])),
            }
        return await self._main("reconfigure", user_input)

    async def _main(self, step_id: str, user_input: dict[str, Any] | None) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                parse(user_input[CONF_FORMULA])
            except FormulaError:
                errors[CONF_FORMULA] = "invalid_formula"
            else:
                self._name = user_input["name"].strip()
                self._data[CONF_FORMULA] = user_input[CONF_FORMULA].strip()
                self._data[CONF_ALLOW_NEGATIVE] = user_input[CONF_ALLOW_NEGATIVE]
                self._data.setdefault(CONF_VARIANTS, [])
                return await self.async_step_variants()
        values = user_input or {
            "name": self._name,
            CONF_FORMULA: self._data.get(CONF_FORMULA, DEFAULT_FORMULA),
            CONF_ALLOW_NEGATIVE: self._data.get(CONF_ALLOW_NEGATIVE, True),
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

    async def async_step_variants(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        options = ["add_variant", "done"]
        if self._data[CONF_VARIANTS]:
            options.insert(1, "clear_variants")
        return self.async_show_menu(
            step_id="variants",
            menu_options=options,
            description_placeholders={"count": str(len(self._data[CONF_VARIANTS]))},
        )

    async def async_step_clear_variants(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        self._data[CONF_VARIANTS] = []
        return await self.async_step_variants()

    async def async_step_add_variant(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            item = {k: v for k, v in user_input.items() if v not in (None, "", [])}
            try:
                parse(item[CONF_FORMULA])
            except FormulaError:
                errors[CONF_FORMULA] = "invalid_formula"
            if ("start_time" in item) != ("end_time" in item):
                errors["start_time"] = "time_range"
            if not errors:
                self._data[CONF_VARIANTS].append(item)
                return await self.async_step_variants()
        schema = vol.Schema(
            {
                vol.Required(CONF_FORMULA): TextSelector(),
                vol.Optional("valid_from"): DateSelector(),
                vol.Optional("start_time"): TimeSelector(),
                vol.Optional("end_time"): TimeSelector(),
                vol.Optional("weekdays"): SelectSelector(
                    SelectSelectorConfig(
                        options=WEEKDAYS,
                        multiple=True,
                        translation_key="weekday",
                    )
                ),
            }
        )
        return self.async_show_form(step_id="add_variant", data_schema=schema, errors=errors)

    async def async_step_done(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        if self._reconfigure:
            return self.async_update_and_abort(
                self._get_entry(),
                self._get_reconfigure_subentry(),
                title=self._name,
                data=self._data,
            )
        return self.async_create_entry(title=self._name, data=self._data)

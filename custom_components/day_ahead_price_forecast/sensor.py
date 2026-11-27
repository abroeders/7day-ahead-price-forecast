"""Sensors: a forecast sensor per sub-controller and a service-state sensor per base controller."""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .config_flow import variant_from_dict
from .const import CONF_ALLOW_NEGATIVE, CONF_FORMULA, CONF_VARIANTS, DOMAIN
from .coordinator import ForecastConfigEntry, ForecastCoordinator
from .core.models import Forecast, PricePoint
from .core.pricing import PriceCalculator
from .core.variants import FormulaVariant

QUARTER_MINUTES = (0, 15, 30, 45)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ForecastConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [ServiceStateSensor(coordinator, entry)]
        + [AccuracySensor(coordinator, entry, metric) for metric in ACCURACY_METRICS]
    )
    for subentry in entry.subentries.values():
        async_add_entities(
            [
                ForecastSensor(
                    coordinator, entry, subentry.subentry_id, subentry.title, subentry.data
                )
            ],
            config_subentry_id=subentry.subentry_id,
        )


def _device(entry: ForecastConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=f"Day-ahead price forecast {entry.title}",
        entry_type=DeviceEntryType.SERVICE,
    )


class ForecastSensor(CoordinatorEntity[ForecastCoordinator], SensorEntity):
    """Current price of one sub-controller; the quarter-hourly forecast is in the attributes."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_native_unit_of_measurement = "EUR/kWh"
    _attr_suggested_display_precision = 4
    _attr_state_class = SensorStateClass.MEASUREMENT
    _unrecorded_attributes = frozenset({"forecast", "known"})

    def __init__(
        self,
        coordinator: ForecastCoordinator,
        entry: ForecastConfigEntry,
        subentry_id: str,
        title: str,
        data: Mapping[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{subentry_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry_id)},
            name=title,
            via_device=(DOMAIN, entry.entry_id),
            entry_type=DeviceEntryType.SERVICE,
        )
        self._calculator = PriceCalculator(
            [
                FormulaVariant(formula=data[CONF_FORMULA]),
                *(variant_from_dict(v) for v in data.get(CONF_VARIANTS, [])),
            ],
            data[CONF_ALLOW_NEGATIVE],
        )
        self._source: Forecast | None = None
        self._priced: Forecast | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_time_change(self.hass, self._tick, minute=QUARTER_MINUTES, second=1)
        )

    @callback
    def _tick(self, _now: datetime) -> None:
        self.async_write_ha_state()

    @property
    def _forecast(self) -> Forecast | None:
        data = self.coordinator.data
        if data is None:
            return None
        if data is not self._source:
            self._source, self._priced = data, self._calculator.apply(data)
        return self._priced

    def _current(self) -> PricePoint | None:
        forecast = self._forecast
        if forecast is None:
            return None
        now = dt_util.utcnow()
        for point in (*forecast.known, *forecast.points):
            if point.start <= now < point.end:
                return point
        return None

    @property
    def native_value(self) -> float | None:
        point = self._current()
        return None if point is None else round(point.value, 6)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        forecast = self._forecast
        if forecast is None:
            return None
        return {
            "zone": forecast.zone,
            "known_until": forecast.known_until.isoformat(),
            "known": [_dump(p) for p in forecast.known],
            "forecast": [_dump(p) for p in forecast.points],
        }


def _dump(point: PricePoint) -> dict[str, Any]:
    item: dict[str, Any] = {
        "start": point.start.isoformat(),
        "end": point.end.isoformat(),
        "value": round(point.value, 6),
    }
    if point.p10 is not None:
        item["p10"] = round(point.p10, 6)
    if point.p90 is not None:
        item["p90"] = round(point.p90, 6)
    return item


class ServiceStateSensor(CoordinatorEntity[ForecastCoordinator], SensorEntity):
    """State of the forecast service: ok, stale or unavailable; node and age as attributes."""

    _attr_has_entity_name = True
    _attr_translation_key = "service_state"

    def __init__(self, coordinator: ForecastCoordinator, entry: ForecastConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_service_state"
        self._attr_device_info = _device(entry)

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> str:
        data = self.coordinator.data
        if data is None or not self.coordinator.last_update_success:
            return "unavailable"
        return "stale" if data.stale else "ok"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        if data is None:
            return {}
        return {
            "node": self.coordinator.node or data.node,
            "created": data.created.isoformat(),
            "age_minutes": int((dt_util.utcnow() - data.created).total_seconds() // 60),
        }


# metric -> (scale to display unit, unit): MAE and bias in ct/kWh, band coverage in %.
ACCURACY_METRICS: dict[str, tuple[float, str]] = {
    "mae": (100.0, "ct/kWh"),
    "bias": (100.0, "ct/kWh"),
    "coverage": (100.0, PERCENTAGE),
}


class AccuracySensor(CoordinatorEntity[ForecastCoordinator], SensorEntity):
    """How far earlier forecasts were off (bare price): mean over all days, per day as attribute."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(
        self, coordinator: ForecastCoordinator, entry: ForecastConfigEntry, metric: str
    ) -> None:
        super().__init__(coordinator)
        self._metric = metric
        self._scale, self._attr_native_unit_of_measurement = ACCURACY_METRICS[metric]
        self._attr_translation_key = f"accuracy_{metric}"
        self._attr_unique_id = f"{entry.entry_id}_accuracy_{metric}"
        self._attr_device_info = _device(entry)

    def _per_day(self) -> dict[int, float]:
        """Scaled values per horizon day; malformed or missing entries are skipped."""
        data = self.coordinator.data
        raw = data.accuracy.get(self._metric) if data is not None else None
        if not isinstance(raw, dict):
            return {}
        result: dict[int, float] = {}
        for key, value in raw.items():
            try:
                day = int(key)
            except (TypeError, ValueError):
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            if math.isfinite(value):
                result[day] = round(value * self._scale, 4)
        return dict(sorted(result.items()))

    @property
    def native_value(self) -> float | None:
        per_day = self._per_day()
        if not per_day:
            return None
        return round(sum(per_day.values()) / len(per_day), 4)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        attrs: dict[str, Any] = {"per_day": {str(d): v for d, v in self._per_day().items()}}
        hours = data.accuracy.get("hours") if data is not None else None
        if isinstance(hours, int) and not isinstance(hours, bool):
            attrs["hours"] = hours
        return attrs

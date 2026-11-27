"""Registry of the available zone plugins."""

from __future__ import annotations

from ..core.errors import ForecastError
from .base import ZonePlugin
from .nl import NetherlandsZone

ZONES: dict[str, ZonePlugin] = {zone.code: zone for zone in (NetherlandsZone(),)}


def get_zone(code: str) -> ZonePlugin:
    """Return the plugin for a zone code; raise ForecastError when unknown."""
    try:
        return ZONES[code.upper()]
    except KeyError:
        raise ForecastError(f"unknown zone: {code}") from None


__all__ = ["ZONES", "ZonePlugin", "get_zone"]

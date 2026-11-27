"""Interface of a market zone (bidding zone) plugin."""

from __future__ import annotations

from typing import Protocol


class ZonePlugin(Protocol):
    code: str
    name: str
    country: str
    timezone: str
    currency: str

    def is_valid_price(self, value: float) -> bool:
        """Return True when a bare market price is plausible for this zone."""

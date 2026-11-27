"""Zone plugin for the Netherlands (bidding zone NL)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NetherlandsZone:
    code: str = "NL"
    name: str = "Netherlands"
    country: str = "NL"
    timezone: str = "Europe/Amsterdam"
    currency: str = "EUR"

    def is_valid_price(self, value: float) -> bool:
        # Harmonised day-ahead price limits are -500 to 4000 EUR/MWh.
        return -0.5 <= value <= 4.0

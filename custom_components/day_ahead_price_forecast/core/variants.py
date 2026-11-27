"""Formula variants: which formula applies at which date, time of day and weekday."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time


@dataclass(frozen=True)
class FormulaVariant:
    """A formula with optional conditions; weekdays use 0 = Monday."""

    formula: str
    valid_from: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    weekdays: frozenset[int] | None = None

    def matches(self, start: datetime) -> bool:
        """Test the local date and time of start; end_time is exclusive."""
        if self.valid_from is not None and start.date() < self.valid_from:
            return False
        if self.weekdays is not None and start.weekday() not in self.weekdays:
            return False
        if self.start_time is None or self.end_time is None:
            return True
        now = start.time()
        if self.start_time <= self.end_time:
            return self.start_time <= now < self.end_time
        return now >= self.start_time or now < self.end_time


def select_variant(variants: Sequence[FormulaVariant], start: datetime) -> FormulaVariant | None:
    """Latest valid_from wins (None is earliest); on a tie the later variant wins."""
    chosen: FormulaVariant | None = None
    for variant in variants:
        if not variant.matches(start):
            continue
        if chosen is None or _rank(variant) >= _rank(chosen):
            chosen = variant
    return chosen


def _rank(variant: FormulaVariant) -> date:
    return variant.valid_from or date.min

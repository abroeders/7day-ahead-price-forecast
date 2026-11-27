"""Apply price formulas to a forecast."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from .errors import FormulaError
from .formula import Formula, parse
from .models import Forecast, PricePoint
from .variants import FormulaVariant, select_variant


class PriceCalculator:
    """Turns bare market prices into prices with the selected formula variant."""

    def __init__(self, variants: Sequence[FormulaVariant], allow_negative: bool = True) -> None:
        self._variants = tuple(variants)
        self._formulas: dict[FormulaVariant, Formula] = {v: parse(v.formula) for v in variants}
        self._allow_negative = allow_negative

    def apply(self, forecast: Forecast) -> Forecast:
        return replace(
            forecast,
            known=tuple(self._point(p) for p in forecast.known),
            points=tuple(self._point(p) for p in forecast.points),
        )

    def _point(self, point: PricePoint) -> PricePoint:
        variant = select_variant(self._variants, point.start)
        if variant is None:
            raise FormulaError(f"no formula variant matches {point.start.isoformat()}", 0)
        formula = self._formulas[variant]
        return replace(
            point,
            value=self._calc(formula, point.value),
            p10=None if point.p10 is None else self._calc(formula, point.p10),
            p90=None if point.p90 is None else self._calc(formula, point.p90),
        )

    def _calc(self, formula: Formula, price: float) -> float:
        result = formula.evaluate(price)
        return result if self._allow_negative else max(result, 0.0)

from datetime import date, datetime, time

from custom_components.day_ahead_price_forecast.core.variants import (
    FormulaVariant,
    select_variant,
)

MON = datetime(2026, 11, 23, 12, 0)
SAT = datetime(2026, 11, 28, 12, 0)


def test_plain_variant_matches_everything():
    assert FormulaVariant("P").matches(MON)


def test_valid_from():
    variant = FormulaVariant("P", valid_from=date(2026, 11, 28))
    assert not variant.matches(MON)
    assert variant.matches(SAT)


def test_time_window_end_exclusive():
    variant = FormulaVariant("P", start_time=time(7), end_time=time(23))
    assert variant.matches(datetime(2026, 11, 23, 7, 0))
    assert variant.matches(datetime(2026, 11, 23, 22, 45))
    assert not variant.matches(datetime(2026, 11, 23, 23, 0))
    assert not variant.matches(datetime(2026, 11, 23, 6, 45))


def test_window_wraps_midnight():
    variant = FormulaVariant("P", start_time=time(23), end_time=time(7))
    assert variant.matches(datetime(2026, 11, 23, 23, 0))
    assert variant.matches(datetime(2026, 11, 24, 0, 0))
    assert variant.matches(datetime(2026, 11, 24, 6, 45))
    assert not variant.matches(datetime(2026, 11, 24, 7, 0))
    assert not variant.matches(datetime(2026, 11, 24, 12, 0))


def test_weekdays():
    variant = FormulaVariant("P", weekdays=frozenset({5, 6}))
    assert not variant.matches(MON)
    assert variant.matches(SAT)


def test_select_none_when_no_match():
    assert select_variant([FormulaVariant("P", weekdays=frozenset({6}))], MON) is None
    assert select_variant([], MON) is None


def test_select_latest_valid_from_wins():
    old = FormulaVariant("P")
    mid = FormulaVariant("P+1", valid_from=date(2026, 1, 1))
    new = FormulaVariant("P+2", valid_from=date(2026, 11, 1))
    future = FormulaVariant("P+3", valid_from=date(2027, 1, 1))
    assert select_variant([new, old, mid, future], MON) is new
    assert select_variant([old], MON) is old


def test_select_tie_later_wins():
    first = FormulaVariant("P+1", valid_from=date(2026, 1, 1))
    second = FormulaVariant("P+2", valid_from=date(2026, 1, 1))
    assert select_variant([first, second], MON) is second
    assert select_variant([FormulaVariant("P"), FormulaVariant("P+1")], MON).formula == "P+1"

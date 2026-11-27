import pytest

from custom_components.day_ahead_price_forecast.core.errors import FormulaError
from custom_components.day_ahead_price_forecast.core.formula import parse


@pytest.mark.parametrize(
    ("text", "p", "expected"),
    [
        ("P", 0.1, 0.1),
        ("(P+0.0205+0.09174)*1.21", 0.1, (0.1 + 0.0205 + 0.09174) * 1.21),
        ("P-0.0205", 0.1, 0.0795),
        ("(P + 0,02) * 1,21", 0.1, 0.1452),
        ("max(P; 0)", -0.05, 0.0),
        ("min(P, 0.3)", 0.5, 0.3),
        ("min(P; 0,3; 1)", 0.2, 0.2),
        ("P × 2 − 1 + 1", 0.25, 0.5),
        ("+P/2", 0.5, 0.25),
        ("-2*-P", 0.5, 1.0),
        ("1 - -P", 0.5, 1.5),
        ("0*P", 3, 0.0),
        ("-P/-2 + P", 1, 1.5),
        ("5", 1, 5.0),
    ],
)
def test_valid(text, p, expected):
    formula = parse(text)
    assert formula.is_monotonic()
    assert formula.evaluate(p) == pytest.approx(expected)


@pytest.mark.parametrize(
    "text", ["-P", "1-P", "P*P", "P/P", "1/P", "P*-1", "max(P; -P)", "min(P, 1-P)", "-max(P; 0)"]
)
def test_non_monotonic_rejected(text):
    with pytest.raises(FormulaError):
        parse(text)


def test_error_positions():
    with pytest.raises(FormulaError) as err:
        parse("P/0")
    assert err.value.position == 1
    assert "division by zero" in str(err.value)
    with pytest.raises(FormulaError, match="division by zero"):
        parse("P/(1-1)")
    with pytest.raises(FormulaError) as err:
        parse("P + X")
    assert err.value.position == 4
    assert "unknown name" in err.value.message
    with pytest.raises(FormulaError) as err:
        parse("(P + 1")
    assert err.value.position == 6
    with pytest.raises(FormulaError) as err:
        parse("P + * 2")
    assert err.value.position == 4
    with pytest.raises(FormulaError) as err:
        parse("P $ 2")
    assert err.value.position == 2
    with pytest.raises(FormulaError) as err:
        parse("P 2")
    assert err.value.position == 2


@pytest.mark.parametrize("text", ["", "min(P)", "max(P; 1", "min(P,1)", "min(1,5)", "foo(P)", "p"])
def test_syntax_errors(text):
    with pytest.raises(FormulaError):
        parse(text)


def test_decimal_comma_versus_separator():
    assert parse("min(P; 1,5)").evaluate(9) == 1.5
    assert parse("min(P, 1,5)").evaluate(9) == 1.5

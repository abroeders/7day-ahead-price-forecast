"""Static quality checks: translations stay in step, no blocking calls on the event loop."""

import json
import re
from pathlib import Path

COMPONENT = Path(__file__).parent.parent / "custom_components" / "day_ahead_price_forecast"

# Calls that block the event loop; none may appear in the integration unless listed in ALLOWED.
BLOCKING = re.compile(
    r"ZoneInfo\(|\bopen\(|\.read_text\(|\.exists\(|os\.listdir|time\.sleep\(|requests\.|import_module"
)
ALLOWED: dict[str, set[str]] = {}  # file name -> patterns that only run in an executor


def _keys(node, prefix=""):
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _keys(value, f"{prefix}.{key}" if prefix else key)
    else:
        yield prefix


def test_strings_equal_english_translation() -> None:
    strings = json.loads((COMPONENT / "strings.json").read_text())
    english = json.loads((COMPONENT / "translations" / "en.json").read_text())
    assert strings == english


def test_translations_have_the_same_keys() -> None:
    english = set(_keys(json.loads((COMPONENT / "translations" / "en.json").read_text())))
    for path in (COMPONENT / "translations").glob("*.json"):
        assert set(_keys(json.loads(path.read_text()))) == english, path.name


def test_no_blocking_calls() -> None:
    for path in COMPONENT.rglob("*.py"):
        for number, line in enumerate(path.read_text().splitlines(), 1):
            code = line.split("#", 1)[0]
            if BLOCKING.search(code) and path.name not in ALLOWED:
                raise AssertionError(f"{path.name}:{number}: blocking call: {line.strip()}")

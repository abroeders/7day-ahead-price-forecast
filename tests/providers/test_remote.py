import asyncio
import json
import random
from datetime import UTC, datetime, timedelta

import pytest

from custom_components.day_ahead_price_forecast.const import DEFAULT_SERVERS
from custom_components.day_ahead_price_forecast.core.errors import ForecastError
from custom_components.day_ahead_price_forecast.providers.remote import RemoteProvider

A, B = DEFAULT_SERVERS
NOW = datetime(2026, 11, 27, 13, 0, tzinfo=UTC)


class FakeHttp:
    """Answers per base URL; an Exception instance is raised, other values returned."""

    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    async def __call__(self, url, timeout):
        self.calls.append((url, timeout))
        base = url.split("/v1/")[0]
        answer = self.answers[base]
        if isinstance(answer, Exception):
            raise answer
        if callable(answer):
            return await answer()
        return answer


def ok(payload, node="a"):
    return 200, json.dumps({**payload, "node": node}).encode()


def provider(http, **kwargs):
    kwargs.setdefault("rng", random.Random(1))
    return RemoteProvider(DEFAULT_SERVERS, http, now=lambda: NOW, **kwargs)


async def test_fetch_ok(payload):
    http = FakeHttp({A: ok(payload, "a"), B: ok(payload, "b")})
    p = provider(http)
    assert p.last_node is None
    forecast = await p.fetch("NL")
    assert forecast.zone == "NL"
    assert len(http.calls) == 1
    assert http.calls[0][0].endswith("/v1/forecast?zone=NL&days=7")
    assert http.calls[0][1] == 5.0
    assert p.last_node == forecast.node


async def test_shuffles_per_call(payload):
    http = FakeHttp({A: ok(payload, "a"), B: ok(payload, "b")})
    p = provider(http)
    for _ in range(20):
        await p.fetch("NL")
    first_bases = {call[0].split("/v1/")[0] for call in http.calls}
    assert first_bases == {A, B}


async def test_does_not_mutate_servers(payload):
    servers = [A, B]
    http = FakeHttp({A: ok(payload), B: ok(payload)})
    await RemoteProvider(servers, http, now=lambda: NOW).fetch("NL")
    assert servers == [A, B]


async def hang():
    await asyncio.sleep(10)


def stale_answer(payload):
    return ok({**payload, "stale": True})


def old_answer(payload):
    created = (NOW - timedelta(hours=3, minutes=1)).isoformat()
    return ok({**payload, "created": created})


def failures(payload):
    return {
        "exception": ConnectionError("refused"),
        "timeout": hang,
        "http 503": (503, b'{"error": "no forecast"}'),
        "http 500": (500, b""),
        "invalid json": (200, b"<html>"),
        "bad schema": ok({**payload, "schema": 2}),
        "bad band": ok({**payload, "forecast": [{**payload["forecast"][0], "p10": 9.0}]}),
        "stale": stale_answer(payload),
        "too old": old_answer(payload),
    }


@pytest.mark.parametrize("kind", list(failures({"forecast": [{}]})))
async def test_failover_on_each_failure_kind(payload, kind):
    bad = failures(payload)[kind]
    for first, second in ((A, B), (B, A)):
        http = FakeHttp({first: bad, second: ok(payload, "good")})
        p = provider(http, timeout=0.05)
        forecast = await p.fetch("NL")
        assert forecast.node == "good"
        assert p.last_node == "good"


async def test_max_age_boundary(payload):
    created = (NOW - timedelta(hours=1)).isoformat()
    answer = ok({**payload, "created": created})
    http = FakeHttp({A: answer, B: answer})
    await provider(http, max_age=timedelta(hours=1)).fetch("NL")
    with pytest.raises(ForecastError):
        await provider(http, max_age=timedelta(minutes=59)).fetch("NL")


async def test_404_raises_immediately(payload):
    http = FakeHttp({A: (404, b'{"error": "unknown zone: XX"}'), B: (404, b"{}")})
    with pytest.raises(ForecastError, match="unknown zone"):
        await provider(http).fetch("XX")
    assert len(http.calls) == 1


async def test_all_fail_lists_reasons(payload):
    http = FakeHttp({A: ConnectionError("refused"), B: (503, b"")})
    p = provider(http)
    with pytest.raises(ForecastError) as info:
        await p.fetch("NL")
    message = str(info.value)
    assert A in message and B in message
    assert "refused" in message and "HTTP 503" in message
    assert len(http.calls) == 2
    assert p.last_node is None


async def test_last_node_kept_after_failed_fetch(payload):
    answers = {A: ok(payload, "a"), B: ok(payload, "a")}
    http = FakeHttp(answers)
    p = provider(http)
    await p.fetch("NL")
    answers[A] = answers[B] = (503, b"")
    with pytest.raises(ForecastError):
        await p.fetch("NL")
    assert p.last_node == "a"


async def test_requests_days(payload):
    http = FakeHttp({A: ok(payload), B: ok(payload)})
    await provider(http).fetch("NL", 2)
    assert all(call[0].endswith("zone=NL&days=2") for call in http.calls)

from __future__ import annotations

import asyncio

import httpx
import pytest
import respx

from app.voice.errors import GnaniError
from app.voice.gnani_http import GnaniTransport
from app.voice.tts_queue import SingleFlight
from tests.unit.voice.conftest import CountingGuard, SleepRecorder, fixture

OK = httpx.Response(200, json={"ok": True})
R429 = httpx.Response(429, json=fixture("err_rate_limited_429.docs.json"))


async def test_sends_key_header_and_request_id(
    transport: GnaniTransport, router: respx.MockRouter
) -> None:
    route = router.post("/x").mock(return_value=OK)
    await transport.request("POST", "/x", service="stt", timeout_s=1, request_id="rid-1")
    req = route.calls.last.request
    assert req.headers["X-API-Key-ID"] == "test-key"
    assert req.headers["X-API-Request-ID"] == "rid-1"


async def test_retries_429_then_succeeds(
    transport: GnaniTransport, router: respx.MockRouter, sleeps: SleepRecorder,
    guard: CountingGuard,
) -> None:  # fmt: skip
    route = router.post("/x").mock(side_effect=[R429, R429, OK])
    r = await transport.request("POST", "/x", service="tts", timeout_s=1)
    assert r.status_code == 200
    assert route.call_count == 3
    assert len(sleeps.delays) == 2
    assert 0.15 <= sleeps.delays[0] <= 0.25  # 200 ms ± jitter
    assert 0.30 <= sleeps.delays[1] <= 0.50  # 400 ms ± jitter
    assert guard.calls == ["tts"]  # one logical billable call, not one per attempt


async def test_gives_up_after_two_retries(
    transport: GnaniTransport, router: respx.MockRouter
) -> None:
    route = router.post("/x").mock(return_value=httpx.Response(503))
    with pytest.raises(GnaniError) as ei:
        await transport.request("POST", "/x", service="stt", timeout_s=1)
    assert ei.value.kind == "upstream"
    assert route.call_count == 3


@pytest.mark.parametrize("status", [400, 401, 402, 403, 422])
async def test_never_retries_client_errors(
    transport: GnaniTransport, router: respx.MockRouter, status: int
) -> None:
    route = router.post("/x").mock(return_value=httpx.Response(status, json={}))
    with pytest.raises(GnaniError):
        await transport.request("POST", "/x", service="stt", timeout_s=1)
    assert route.call_count == 1


async def test_timeout_is_mapped_and_retried(
    transport: GnaniTransport, router: respx.MockRouter
) -> None:
    route = router.post("/x").mock(side_effect=[httpx.ReadTimeout("slow"), OK])
    r = await transport.request("POST", "/x", service="stt", timeout_s=1)
    assert r.status_code == 200
    assert route.call_count == 2


async def test_network_error_maps_to_upstream(
    transport: GnaniTransport, router: respx.MockRouter
) -> None:
    router.post("/x").mock(side_effect=httpx.ConnectError("dns"))
    with pytest.raises(GnaniError) as ei:
        await transport.request("POST", "/x", service="stt", timeout_s=1)
    assert ei.value.kind == "upstream"


async def test_budget_refusal_happens_before_any_http(router: respx.MockRouter) -> None:
    class Broke:
        async def consume(self, service: str) -> None:
            raise GnaniError("budget")

    route = router.post("/x").mock(return_value=OK)
    async with httpx.AsyncClient(base_url="https://gnani.test") as c:
        t = GnaniTransport(c, api_key="k", gate=SingleFlight(1), guard=Broke())
        with pytest.raises(GnaniError) as ei:
            await t.request("POST", "/x", service="stt", timeout_s=1)
    assert ei.value.kind == "budget"
    assert route.call_count == 0


def test_missing_key_refused() -> None:
    with pytest.raises(GnaniError) as ei:
        GnaniTransport(httpx.AsyncClient(), api_key="", gate=SingleFlight(1), guard=CountingGuard())
    assert ei.value.kind == "auth"


async def test_concurrent_stt_and_tts_are_serialised(
    transport: GnaniTransport, router: respx.MockRouter
) -> None:
    active = peak = 0

    async def slow(_: httpx.Request) -> httpx.Response:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return OK

    router.post("/stt").mock(side_effect=slow)
    router.post("/tts").mock(side_effect=slow)
    await asyncio.gather(
        *(transport.request("POST", "/stt", service="stt", timeout_s=1) for _ in range(3)),
        *(transport.request("POST", "/tts", service="tts", timeout_s=1) for _ in range(3)),
    )
    assert peak == 1


async def test_stream_retries_on_429_then_yields_body(
    transport: GnaniTransport, router: respx.MockRouter
) -> None:
    router.post("/s").mock(side_effect=[R429, httpx.Response(200, text="data: 1\n\n")])
    async with transport.stream("POST", "/s", service="tts", timeout_s=1) as r:
        body = [line async for line in r.aiter_lines()]
    assert body[0] == "data: 1"


async def test_stream_holds_gate_until_body_consumed(
    transport: GnaniTransport, router: respx.MockRouter
) -> None:
    router.post("/s").mock(return_value=httpx.Response(200, text="x"))
    async with transport.stream("POST", "/s", service="tts", timeout_s=1):
        assert transport.gate._sem.locked()
    assert not transport.gate._sem.locked()

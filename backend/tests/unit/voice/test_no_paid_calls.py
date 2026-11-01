"""Guards that keep the suite from ever spending Gnani credits."""

from __future__ import annotations

import os

import httpx
import pytest

from app.config import get_settings
from app.voice.errors import GnaniError
from app.voice.gnani_http import GnaniTransport
from app.voice.tts_queue import SingleFlight
from tests.unit.voice.conftest import CountingGuard


def test_suite_runs_without_a_real_key() -> None:
    assert os.environ.get("KK_BLOCK_PAID_CALLS") == "1"
    assert not get_settings().gnani_configured  # .env key is masked for the whole run


async def test_transport_tripwire_blocks_real_calls() -> None:
    guard = CountingGuard()
    async with httpx.AsyncClient(base_url="https://api.vachana.ai") as c:
        t = GnaniTransport(c, api_key="real-looking-key", gate=SingleFlight(1), guard=guard)
        with pytest.raises(GnaniError) as ei:
            await t.request("POST", "/api/v1/tts/inference", service="tts", timeout_s=1)
    assert ei.value.kind == "budget"
    assert guard.calls == []  # refused before even counting

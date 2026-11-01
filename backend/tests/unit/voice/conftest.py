from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from app.voice.gnani_http import GnaniTransport
from app.voice.tts_queue import SingleFlight

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "gnani"
BASE = "https://gnani.test"


def fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class CountingGuard:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def consume(self, service: str) -> None:
        self.calls.append(service)


class SleepRecorder:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, s: float) -> None:
        self.delays.append(s)


@pytest.fixture
def guard() -> CountingGuard:
    return CountingGuard()


@pytest.fixture
def sleeps() -> SleepRecorder:
    return SleepRecorder()


@pytest.fixture
def router() -> AsyncIterator[respx.MockRouter]:
    with respx.mock(base_url=BASE, assert_all_called=False) as r:
        yield r


@pytest.fixture
async def transport(
    router: respx.MockRouter, guard: CountingGuard, sleeps: SleepRecorder
) -> AsyncIterator[GnaniTransport]:
    async with httpx.AsyncClient(base_url=BASE) as client:
        yield GnaniTransport(
            client, api_key="test-key", gate=SingleFlight(1), guard=guard, sleep=sleeps
        )

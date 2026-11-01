from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.voice.credit_guard import FileCreditGuard
from app.voice.errors import GnaniError
from app.voice.tts_queue import SingleFlight


class Clock:
    def __init__(self, t: datetime) -> None:
        self.t = t

    def __call__(self) -> datetime:
        return self.t


async def test_guard_refuses_past_limit(tmp_path: Path) -> None:
    g = FileCreditGuard(tmp_path / "c.json", limit=2)
    await g.consume("stt")
    await g.consume("tts")
    with pytest.raises(GnaniError) as ei:
        await g.consume("stt")
    assert ei.value.kind == "budget"
    assert g.used_today() == 2


async def test_guard_zero_means_unlimited_but_counts(tmp_path: Path) -> None:
    g = FileCreditGuard(tmp_path / "c.json", limit=0)
    for _ in range(5):
        await g.consume("stt")
    assert g.used_today() == 5


async def test_guard_persists_across_instances(tmp_path: Path) -> None:
    p = tmp_path / "c.json"
    await FileCreditGuard(p, limit=10).consume("stt")
    assert FileCreditGuard(p, limit=10).used_today() == 1


async def test_guard_resets_at_ist_midnight_not_utc(tmp_path: Path) -> None:
    # 18:29 UTC = 23:59 IST (day 1); 18:31 UTC = 00:01 IST (day 2), same UTC date.
    clock = Clock(datetime(2026, 11, 1, 18, 29, tzinfo=UTC))
    g = FileCreditGuard(tmp_path / "c.json", limit=1, now=clock)
    await g.consume("stt")
    with pytest.raises(GnaniError):
        await g.consume("stt")
    clock.t = datetime(2026, 11, 1, 18, 31, tzinfo=UTC)
    await g.consume("stt")  # new IST day
    assert g.used_today() == 1


async def test_guard_survives_corrupt_file(tmp_path: Path) -> None:
    p = tmp_path / "c.json"
    p.write_text("{not json", encoding="utf-8")
    g = FileCreditGuard(p, limit=3)
    await g.consume("stt")
    assert g.used_today() == 1


async def test_single_flight_never_runs_two_at_once() -> None:
    gate = SingleFlight(1)
    active = peak = 0

    async def work() -> None:
        nonlocal active, peak
        async with gate.slot():
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.01)
            active -= 1

    await asyncio.gather(*(work() for _ in range(8)))
    assert peak == 1
    assert gate.waiting == 0


async def test_single_flight_releases_on_error() -> None:
    gate = SingleFlight(1)
    with pytest.raises(RuntimeError):
        async with gate.slot():
            raise RuntimeError("boom")
    async with asyncio.timeout(0.5):  # would deadlock if the slot leaked
        async with gate.slot():
            pass


def test_single_flight_rejects_zero() -> None:
    with pytest.raises(ValueError, match=">= 1"):
        SingleFlight(0)

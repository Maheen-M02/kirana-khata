"""Golden set against REAL Evon (hybrid and evon-only). Run on request: `make test-live`.
Skips unless EVON_BASE_URL answers /models. Evon is self-hosted: costs GPU time, not credits."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

from app.config import Settings, get_settings
from app.nlu.factory import NluStack, build_parser
from app.nlu.schema import NluContext
from tests.golden import GOLDEN_PATH, load_cases, score

pytestmark = pytest.mark.live
HOLDOUT = Path(GOLDEN_PATH).with_name("golden_holdout.yaml")


async def _evon_up(s: Settings) -> bool:
    headers = {"Authorization": f"Bearer {s.evon_api_key.get_secret_value()}"}
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{s.evon_base_url.rstrip('/')}/models", headers=headers)
        return r.status_code == 200
    except httpx.HTTPError:
        return False


@pytest.fixture(params=["hybrid", "evon"])
async def stack(request: pytest.FixtureRequest) -> AsyncIterator[NluStack]:
    s = get_settings()
    if not await _evon_up(s):
        pytest.skip(f"Evon not reachable at {s.evon_base_url}")
    st = build_parser(Settings.model_validate({**s.model_dump(), "nlu_mode": request.param}))
    yield st
    await st.aclose()


@pytest.mark.parametrize("path", [GOLDEN_PATH, HOLDOUT], ids=["golden", "holdout"])
async def test_evon_golden(stack: NluStack, path: Path) -> None:
    cases = load_cases(path)
    ctx = NluContext()
    results = [await stack.parser.parse(c.transcript, ctx) for c in cases]
    report = score(cases, results)
    print(f"\n[{type(stack.parser).__name__}] {path.name}\n{report.table()}")
    assert report.intent_accuracy >= 0.90
    if type(stack.parser).__name__ == "HybridParser":
        assert not report.amount_wrong_unflagged  # rules guard every amount

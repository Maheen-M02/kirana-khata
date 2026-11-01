"""Liveness (/health) and readiness (/ready). Readiness never calls paid Gnani endpoints."""

from __future__ import annotations

from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy import Engine

from app.config import Settings, get_settings
from app.db import get_engine, ping_db

router = APIRouter(tags=["health"])

CheckStatus = Literal["ok", "fail", "skipped", "unconfigured"]


class HealthOut(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "kirana-khata"
    version: str = "0.1.0"


class ReadyOut(BaseModel):
    status: Literal["ok", "degraded"]
    checks: dict[str, CheckStatus]


@router.get("/health", response_model=HealthOut)
async def health() -> HealthOut:
    return HealthOut()


async def check_evon(settings: Settings) -> CheckStatus:
    """Evon is self-hosted (no per-call cost), so a GET /models ping is safe."""
    if settings.nlu_mode == "rules":
        return "skipped"
    headers = {}
    key = settings.evon_api_key.get_secret_value()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            r = await client.get(f"{settings.evon_base_url.rstrip('/')}/models", headers=headers)
        return "ok" if r.status_code == 200 else "fail"
    except httpx.HTTPError:
        return "fail"


def check_db(engine: Engine) -> CheckStatus:
    try:
        ping_db(engine)
    except Exception:
        return "fail"
    return "ok"


@router.get("/ready", response_model=ReadyOut)
async def ready(
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    engine: Annotated[Engine, Depends(get_engine)],
) -> ReadyOut:
    checks: dict[str, CheckStatus] = {
        "db": check_db(engine),
        # Gnani has no free ping endpoint; report config only so /ready never spends credits.
        "gnani": "ok" if settings.gnani_configured else "unconfigured",
        "evon": await check_evon(settings),
    }
    # DB is the hard dependency. Evon down => rules fallback; Gnani missing => degraded voice.
    ok = checks["db"] == "ok" and checks["evon"] != "fail" and checks["gnani"] == "ok"
    if checks["db"] != "ok":
        response.status_code = 503
    return ReadyOut(status="ok" if ok else "degraded", checks=checks)

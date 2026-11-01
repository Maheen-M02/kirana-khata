from __future__ import annotations

import httpx
import respx
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.db import get_engine, make_engine
from app.main import create_app


def test_health_ok(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.headers["x-request-id"]


def test_request_id_is_echoed(client: TestClient) -> None:
    r = client.get("/api/health", headers={"x-request-id": "abc123"})
    assert r.headers["x-request-id"] == "abc123"


def test_ready_degraded_without_gnani_key(client: TestClient) -> None:
    r = client.get("/api/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["checks"] == {"db": "ok", "gnani": "unconfigured", "evon": "skipped"}
    assert body["status"] == "degraded"


def _client_with(settings: Settings) -> TestClient:
    app = create_app()
    engine = make_engine(settings.database_url)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_engine] = lambda: engine
    return TestClient(app)


@respx.mock
def test_ready_ok_with_gnani_key_and_evon_up(settings: Settings) -> None:
    s = Settings.model_validate(
        {**settings.model_dump(), "gnani_api_key": "k", "nlu_mode": "hybrid"}
    )
    respx.get(f"{s.evon_base_url}/models").mock(return_value=httpx.Response(200, json={}))
    with _client_with(s) as c:
        body = c.get("/api/ready").json()
    assert body == {"status": "ok", "checks": {"db": "ok", "gnani": "ok", "evon": "ok"}}


@respx.mock
def test_ready_degraded_when_evon_down(settings: Settings) -> None:
    s = Settings.model_validate(
        {**settings.model_dump(), "gnani_api_key": "k", "nlu_mode": "hybrid"}
    )
    respx.get(f"{s.evon_base_url}/models").mock(side_effect=httpx.ConnectError("down"))
    with _client_with(s) as c:
        body = c.get("/api/ready").json()
    assert body["checks"]["evon"] == "fail"
    assert body["status"] == "degraded"


def test_ready_503_when_db_down(settings: Settings) -> None:
    s = Settings.model_validate(
        {**settings.model_dump(), "database_url": "sqlite:///Z:/no/such/dir/x.db"}
    )
    with _client_with(s) as c:
        r = c.get("/api/ready")
    assert r.status_code == 503
    assert r.json()["checks"]["db"] == "fail"

"""Phase 6: auth (phone + PIN -> httpOnly JWT), shop isolation through real tokens,
login rate limit, body limit, voice rate limit, retention, weak-secret refusal."""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.api import auth as auth_api
from app.api import voice as voice_api
from app.config import Settings, get_settings
from app.core.retention import purge_old_audio
from app.core.security import (
    SESSION_COOKIE,
    AttemptLimiter,
    RateLimiter,
    hash_pin,
    issue_token,
    normalise_phone,
    read_token,
    verify_pin,
)
from app.deps import db_session
from app.ledger import service as svc
from app.main import create_app

SECRET = "x" * 40


def _phone() -> str:
    return "9" + str(uuid.uuid4().int)[:9]


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    settings = Settings.model_validate({"app_env": "test", "jwt_secret": SECRET, "gnani_api_key": "",
                                        "nlu_mode": "rules"})  # fmt: skip
    app = create_app()

    def _session() -> Iterator[Session]:
        s = Session(engine, expire_on_commit=False)
        try:
            yield s
        finally:
            s.close()

    auth_api.login_attempts = AttemptLimiter()  # fresh limiter per test
    app.dependency_overrides[db_session] = _session
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[auth_api._limiter] = lambda: auth_api.login_attempts
    with TestClient(app) as c:
        yield c


def make_shop(engine: Engine, phone: str, pin: str = "4821", name: str = "Dukaan") -> int:
    with Session(engine) as s:
        shop = svc.create_shop(s, name=name, owner_phone=phone, pin_hash=hash_pin(pin))
        s.commit()
        return shop.id


def test_login_sets_httponly_cookie_and_me_works(client: TestClient, engine: Engine) -> None:
    phone = _phone()
    shop_id = make_shop(engine, phone)
    r = client.post(
        "/api/auth/login", json={"phone": f"+91 {phone[:5]} {phone[5:]}", "pin": "4821"}
    )
    assert r.status_code == 200, r.text
    cookie = r.headers["set-cookie"]
    assert SESSION_COOKIE in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert client.get("/api/auth/me").json()["shop_id"] == shop_id
    assert client.get("/api/customers").status_code == 200


def test_everything_requires_login(client: TestClient) -> None:
    for path in ("/api/customers", "/api/ledger/entries", "/api/reports/today", "/api/auth/me"):
        r = client.get(path)
        assert r.status_code == 401
        assert r.json()["error"]["message"] == "Login kijiye."
    assert client.post("/api/voice/turn", data={"transcript": "haan"}).status_code == 401
    assert client.get("/api/health").status_code == 200  # liveness stays public


def test_wrong_pin_is_friendly_and_locks_after_five(client: TestClient, engine: Engine) -> None:
    phone = _phone()
    make_shop(engine, phone)
    for _ in range(5):
        r = client.post("/api/auth/login", json={"phone": phone, "pin": "0000"})
        assert r.status_code == 401
        assert r.json()["error"]["message"] == "Phone ya PIN galat hai."
    r = client.post("/api/auth/login", json={"phone": phone, "pin": "4821"})  # even the right PIN
    assert r.status_code == 429
    assert "15 minute" in r.json()["error"]["message"]


def test_unknown_phone_looks_like_wrong_pin(client: TestClient) -> None:
    r = client.post("/api/auth/login", json={"phone": _phone(), "pin": "1234"})
    assert (r.status_code, r.json()["error"]["message"]) == (401, "Phone ya PIN galat hai.")


def test_forged_and_expired_tokens_are_rejected(client: TestClient, engine: Engine) -> None:
    shop_id = make_shop(engine, _phone())
    client.cookies.set(SESSION_COOKIE, issue_token(shop_id, "some-other-secret-" * 3))
    assert client.get("/api/customers").status_code == 401
    old = issue_token(shop_id, SECRET, now=datetime.now(UTC) - timedelta(days=31))
    client.cookies.set(SESSION_COOKIE, old)
    assert client.get("/api/customers").status_code == 401
    client.cookies.set(SESSION_COOKIE, "not-a-jwt")
    assert client.get("/api/customers").status_code == 401


def test_one_shop_cannot_see_another(client: TestClient, engine: Engine) -> None:
    a, b = make_shop(engine, _phone()), make_shop(engine, _phone())
    with Session(engine) as s:
        theirs = svc.create_customer(s, shop_id=b, display_name="Gupta ji")
        svc.record_entry(s, shop_id=b, type=svc.EntryType.credit_sale, amount_paise=9900,
                         customer_id=theirs.id)  # fmt: skip
        s.commit()
        theirs_id = theirs.id
    client.cookies.set(SESSION_COOKIE, issue_token(a, SECRET))
    assert client.get("/api/customers").json() == []
    assert client.get(f"/api/customers/{theirs_id}").status_code == 404
    r = client.post("/api/ledger/entries", json={"type": "credit_sale", "amount_paise": 100,
                                                 "customer_id": theirs_id})  # fmt: skip
    assert r.status_code == 404
    assert client.get("/api/reports/dues").json()["customers"] == []


def test_logout_clears_cookie(client: TestClient, engine: Engine) -> None:
    phone = _phone()
    make_shop(engine, phone)
    client.post("/api/auth/login", json={"phone": phone, "pin": "4821"})
    r = client.post("/api/auth/logout")
    assert r.status_code == 204
    assert SESSION_COOKIE in r.headers["set-cookie"]
    assert client.get("/api/auth/me").status_code == 401


def test_devanagari_names_round_trip(client: TestClient, engine: Engine) -> None:
    client.cookies.set(SESSION_COOKIE, issue_token(make_shop(engine, _phone()), SECRET))
    r = client.post("/api/customers", json={"display_name": "शर्मा जी", "aliases": ["शर्मा अंकल"]})
    assert r.status_code == 201
    got = client.get(f"/api/customers/{r.json()['id']}").json()
    assert (got["display_name"], got["aliases"]) == ("शर्मा जी", ["शर्मा अंकल"])


def test_body_limit_rejects_before_reading(client: TestClient) -> None:
    r = client.post("/api/voice/turn", content=b"0" * (3 * 1024 * 1024),
                    headers={"content-type": "application/octet-stream"})  # fmt: skip
    assert r.status_code == 413
    assert "chhota" in r.json()["error"]["message"].lower()


def test_voice_turns_are_rate_limited_per_shop(client: TestClient, engine: Engine) -> None:
    voice_api.turn_limiter = RateLimiter(limit=2, window_s=60)
    try:
        client.cookies.set(SESSION_COOKIE, issue_token(make_shop(engine, _phone()), SECRET))
        codes = [client.post("/api/voice/turn", data={"transcript": "aaj kitni bikri hui"}).status_code
                 for _ in range(3)]  # fmt: skip
        assert codes[2] == 429
    finally:
        voice_api.turn_limiter = RateLimiter(limit=30, window_s=60)


def test_weak_jwt_secret_refused_in_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("JWT_SECRET", "change-me")
    try:
        with pytest.raises(RuntimeError, match="JWT_SECRET"):
            create_app()
    finally:
        get_settings.cache_clear()


def test_pin_hashing_and_tokens() -> None:
    h = hash_pin("4821")
    assert h.startswith("scrypt$")
    assert verify_pin("4821", h)
    assert not verify_pin("4822", h)
    assert not verify_pin("48a1", h)
    assert not verify_pin("4821", "!")  # seeded/placeholder hash never logs in
    assert hash_pin("4821") != h  # salted
    with pytest.raises(ValueError, match="4 digits"):
        hash_pin("12345")
    assert read_token(issue_token(7, SECRET), SECRET) == 7
    assert normalise_phone("+91 98765-43210") == "9876543210"
    assert normalise_phone("098765 43210") == "9876543210"


def test_limiters_window() -> None:
    lim = AttemptLimiter(max_failures=2, window_s=10)
    lim.fail("k", now=0)
    lim.fail("k", now=1)
    assert lim.blocked("k", now=5)
    assert not lim.blocked("k", now=12)
    rl = RateLimiter(limit=1, window_s=10)
    assert rl.allow("s", now=0)
    assert not rl.allow("s", now=1)
    assert rl.allow("s", now=11)


def test_audio_retention_deletes_only_old_files(tmp_path: Path) -> None:
    old, new = tmp_path / "1.wav", tmp_path / "2.wav"
    old.write_bytes(b"x")
    new.write_bytes(b"x")
    eight_days = time.time() - 8 * 86400
    os.utime(old, (eight_days, eight_days))
    assert purge_old_audio(tmp_path) == 1
    assert not old.exists()
    assert new.exists()
    assert purge_old_audio(tmp_path / "missing") == 0

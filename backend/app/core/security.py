"""Single-owner auth: phone + 4-digit PIN -> signed JWT in an httpOnly cookie.

- PINs are hashed with scrypt (stdlib) + per-PIN salt; compared in constant time.
- Wrong PINs are rate-limited: 5 failures per phone per 15 minutes (QA checklist).
- JWT: HS256, 30-day expiry, `sub` = shop id. JWT_SECRET must be strong outside dev.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import threading
import time
from collections import deque
from datetime import UTC, datetime, timedelta

import jwt

SESSION_COOKIE = "kk_session"
SESSION_DAYS = 30
PIN_RE = re.compile(r"^\d{4}$")
PHONE_RE = re.compile(r"^\d{10}$")
_SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}
WEAK_SECRETS = frozenset({"", "change-me", "secret", "changeme"})


def normalise_phone(raw: str) -> str:
    """'+91 98765 43210' / '098765-43210' -> '9876543210'."""
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits


def hash_pin(pin: str) -> str:
    if not PIN_RE.match(pin):
        raise ValueError("PIN must be exactly 4 digits")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(pin.encode(), salt=salt, **_SCRYPT)
    return "scrypt$" + base64.b64encode(salt + digest).decode()


def verify_pin(pin: str, stored: str) -> bool:
    if not stored.startswith("scrypt$") or not PIN_RE.match(pin):
        hashlib.scrypt(b"0000", salt=b"x" * 16, **_SCRYPT)  # same cost: no timing oracle
        return False
    raw = base64.b64decode(stored.removeprefix("scrypt$"))
    salt, expected = raw[:16], raw[16:]
    return hmac.compare_digest(hashlib.scrypt(pin.encode(), salt=salt, **_SCRYPT), expected)


def issue_token(shop_id: int, secret: str, now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    payload = {"sub": str(shop_id), "iat": now, "exp": now + timedelta(days=SESSION_DAYS)}
    return jwt.encode(payload, secret, algorithm="HS256")


def read_token(token: str, secret: str) -> int | None:
    """Shop id, or None if the token is missing, forged or expired."""
    try:
        payload = jwt.decode(
            token, secret, algorithms=["HS256"], options={"require": ["exp", "sub"]}
        )
        return int(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        return None


def _t(now: float | None) -> float:
    return time.monotonic() if now is None else now  # `now or ...` would treat 0 as missing


class AttemptLimiter:
    """Sliding-window failure counter (in-process; one backend instance by design)."""

    def __init__(self, max_failures: int = 5, window_s: float = 15 * 60) -> None:
        self.max_failures = max_failures
        self.window_s = window_s
        self._fails: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def _recent(self, key: str, now: float) -> deque[float]:
        q = self._fails.setdefault(key, deque())
        while q and now - q[0] > self.window_s:
            q.popleft()
        return q

    def blocked(self, key: str, now: float | None = None) -> bool:
        with self._lock:
            return len(self._recent(key, _t(now))) >= self.max_failures

    def fail(self, key: str, now: float | None = None) -> None:
        with self._lock:
            t = _t(now)
            self._recent(key, t).append(t)

    def reset(self, key: str) -> None:
        with self._lock:
            self._fails.pop(key, None)


class RateLimiter:
    """Fixed-window request limiter per key (e.g. voice turns per shop per minute)."""

    def __init__(self, limit: int, window_s: float = 60.0) -> None:
        self.limit = limit
        self.window_s = window_s
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        t = _t(now)
        with self._lock:
            q = self._hits.setdefault(key, deque())
            while q and t - q[0] > self.window_s:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(t)
            return True

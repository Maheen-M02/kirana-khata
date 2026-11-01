"""GNANI_CREDIT_GUARD: refuse billable Gnani calls past N per day (Asia/Kolkata) in dev.

Phase 1 keeps the counter in a small JSON file so it survives across processes (the smoke
script and the dev server share it). Phase 3 can move it into the DB without changing callers.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import Protocol
from zoneinfo import ZoneInfo

from app.core.logging import get_logger
from app.voice.errors import GnaniError

log = get_logger(__name__)


class CreditGuard(Protocol):
    async def consume(self, service: str) -> None:
        """Count one billable call or raise GnaniError(kind='budget')."""
        ...


class NoopCreditGuard:
    """Counts nothing, never refuses (prod; tests that don't care)."""

    async def consume(self, service: str) -> None:
        return None


class FileCreditGuard:
    def __init__(
        self,
        path: Path,
        limit: int,
        tz: str = "Asia/Kolkata",
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.path = path
        self.limit = limit  # 0 = unlimited (still counted and logged)
        self._tz = ZoneInfo(tz)
        self._now = now or (lambda: datetime.now(self._tz))
        self._lock = threading.Lock()

    def _today(self) -> date:
        return self._now().astimezone(self._tz).date()

    def _read(self) -> dict[str, int]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
        return {str(k): int(v) for k, v in raw.items()} if isinstance(raw, dict) else {}

    def used_today(self) -> int:
        with self._lock:
            return self._read().get(self._today().isoformat(), 0)

    async def consume(self, service: str) -> None:
        with self._lock:
            day = self._today().isoformat()
            counts = self._read()
            used = counts.get(day, 0)
            if self.limit and used >= self.limit:
                log.warning(
                    "gnani_credit_guard_refused", service=service, used=used, limit=self.limit
                )
                raise GnaniError("budget", f"daily guard {self.limit} reached")
            counts = {day: used + 1}  # keep only today
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(counts), encoding="utf-8")
            tmp.replace(self.path)
        log.info("gnani_billable_call", service=service, used_today=used + 1, limit=self.limit)

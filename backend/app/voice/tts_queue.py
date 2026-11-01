"""Process-wide single-flight gate for *all* Gnani calls.

The skill describes a TTS-only `asyncio.Semaphore(1)`, but the live docs show the
"Only 1 active request is allowed at a time" 429 is per *account* and also applies to STT
(docs/DOC_DIFFS.md #1). So STT and TTS share this one gate. Concurrency is configurable
(`GNANI_MAX_CONCURRENCY`) in case the account limit is raised.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


class SingleFlight:
    def __init__(self, max_concurrency: int = 1) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be >= 1")
        self._sem = asyncio.Semaphore(max_concurrency)
        self.max_concurrency = max_concurrency
        self._waiting = 0

    @property
    def waiting(self) -> int:
        """Callers queued behind the active request(s); exposed for /debug metrics."""
        return self._waiting

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        self._waiting += 1
        try:
            await self._sem.acquire()
        finally:
            self._waiting -= 1
        try:
            yield
        finally:
            self._sem.release()

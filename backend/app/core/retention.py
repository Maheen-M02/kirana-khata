"""Delete retained input audio after 7 days (QA hardening). Runs at startup and every 6 h."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

from app.core.logging import get_logger

log = get_logger(__name__)
RETAIN_S = 7 * 24 * 3600
EVERY_S = 6 * 3600


def purge_old_audio(directory: Path, retain_s: float = RETAIN_S, now: float | None = None) -> int:
    if not directory.is_dir():
        return 0
    cutoff = (now or time.time()) - retain_s
    removed = 0
    for f in directory.glob("*.wav"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
                removed += 1
        except OSError:
            continue
    if removed:
        log.info("audio_retention_purged", removed=removed)
    return removed


async def retention_loop(directory: Path) -> None:
    while True:
        await asyncio.to_thread(purge_old_audio, directory)
        await asyncio.sleep(EVERY_S)

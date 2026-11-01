"""Gnani Timbre TTS: REST (`/api/v1/tts/inference`) and SSE (`/api/v1/tts/sse`), with an
on-disk phrase cache. Text must already be spoken-form ("ek sau bees rupaye", not "₹120")."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import time
from collections.abc import AsyncIterable, AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from app.voice.errors import GnaniError
from app.voice.gnani_http import GnaniTransport

TTS_REST_PATH = "/api/v1/tts/inference"
TTS_SSE_PATH = "/api/v1/tts/sse"
MAX_TEXT_CHARS = 400  # long text returns a 500 upstream; our phrases are short
MP3 = "audio/mpeg"

# Pre-warm these once at startup (Phase 4), never concurrently with live turns.
PREWARM_PHRASES: tuple[str, ...] = (
    "Maaf kijiye, samajh nahi aaya. Dobara boliye.",
    "Entry ho gayi.",
    "Theek hai, cancel kar diya.",
    "Haan ya nahi boliye.",
    "Awaaz saaf nahi aayi, dobara boliye.",
)


@dataclass(frozen=True)
class TtsResult:
    audio: bytes
    content_type: str
    cached: bool
    latency_ms: int


class TextToSpeech(Protocol):
    async def synthesize(self, text: str) -> TtsResult: ...

    def stream(self, text: str) -> AsyncIterator[bytes]: ...


@dataclass(frozen=True)
class SseEvent:
    event: str
    data: str


async def iter_sse(lines: AsyncIterable[str]) -> AsyncIterator[SseEvent]:
    """Minimal SSE parser: `event:` / `data:` fields, blank line dispatches."""
    event: str = "message"
    data: list[str] = []
    async for raw in lines:
        line = raw.rstrip("\r")
        if not line:
            if data:
                yield SseEvent(event, "\n".join(data))
            event, data = "message", []
            continue
        if line.startswith(":"):
            continue
        field, _, value = line.partition(":")
        value = value.removeprefix(" ")
        if field == "event":
            event = value
        elif field == "data":
            data.append(value)
    if data:
        yield SseEvent(event, "\n".join(data))


def decode_chunk(data: str) -> tuple[bytes, bool]:
    """`chunk`/`complete` payload -> (audio bytes, is_final)."""
    try:
        obj = json.loads(data)
        audio = base64.b64decode(obj.get("audio") or "", validate=True)
    except (ValueError, binascii.Error, AttributeError) as e:
        raise GnaniError("upstream", "bad SSE chunk") from e
    return audio, bool(obj.get("is_final", False))


class TtsCache:
    def __init__(self, directory: Path) -> None:
        self.dir = directory

    @staticmethod
    def key(body: dict[str, Any]) -> str:
        return hashlib.sha256(
            json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()

    def _path(self, key: str) -> Path:
        return self.dir / f"{key}.mp3"

    def get(self, key: str) -> bytes | None:
        p = self._path(key)
        return p.read_bytes() if p.exists() else None

    def put(self, key: str, audio: bytes) -> None:
        if not audio:
            return
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self._path(key).with_suffix(".tmp")
        tmp.write_bytes(audio)
        tmp.replace(self._path(key))


def validate_text(text: str) -> str:
    t = " ".join(text.split())
    if not t:
        raise ValueError("TTS text is empty")
    if len(t) > MAX_TEXT_CHARS:
        raise ValueError(f"TTS text longer than {MAX_TEXT_CHARS} chars")
    return t


class GnaniTTS:
    def __init__(
        self,
        transport: GnaniTransport,
        *,
        model: str,
        voice: str,
        language: str,
        speed: float = 0.95,
        cache: TtsCache | None = None,
        timeout_s: float = 15.0,
        sample_rate: int = 24_000,
        bitrate: str = "64k",
    ) -> None:
        self._t = transport
        self.model, self.voice, self.language, self.speed = model, voice, language, speed
        self.cache = cache
        self.timeout_s = timeout_s
        self.audio_config: dict[str, Any] = {
            "sample_rate": sample_rate,
            "num_channels": 1,
            "sample_width": 2,
            "encoding": "linear_pcm",
            "container": "mp3",  # never ogg: it can't stream over SSE (DOC_DIFFS #13)
            "bitrate": bitrate,
        }

    def body(self, text: str) -> dict[str, Any]:
        return {
            "text": validate_text(text),
            "model": self.model,
            "voice": self.voice,
            "language": self.language,
            "speed": self.speed,
            "audio_config": self.audio_config,
        }

    async def synthesize(self, text: str) -> TtsResult:
        body = self.body(text)
        key = TtsCache.key(body)
        t0 = time.perf_counter()
        if self.cache and (hit := self.cache.get(key)) is not None:
            return TtsResult(hit, MP3, cached=True, latency_ms=0)
        r = await self._t.request("POST", TTS_REST_PATH, service="tts",
                                  timeout_s=self.timeout_s, json=body)  # fmt: skip
        audio = r.content
        if not audio:
            raise GnaniError("upstream", "TTS returned empty audio")
        if self.cache:
            self.cache.put(key, audio)
        return TtsResult(
            audio, MP3, cached=False, latency_ms=round((time.perf_counter() - t0) * 1000)
        )

    async def stream(self, text: str) -> AsyncIterator[bytes]:
        """Yield mp3 bytes as Timbre generates them; first chunk = time-to-first-audio."""
        body = self.body(text)
        key = TtsCache.key(body)
        if self.cache and (hit := self.cache.get(key)) is not None:
            yield hit
            return
        collected: list[bytes] = []
        async with self._t.stream("POST", TTS_SSE_PATH, service="tts",
                                  timeout_s=self.timeout_s, json=body) as r:  # fmt: skip
            async for ev in iter_sse(r.aiter_lines()):
                if ev.event == "error":
                    raise GnaniError("upstream", f"TTS SSE error: {ev.data[:200]}")
                if ev.event not in ("chunk", "complete"):
                    continue
                audio, is_final = decode_chunk(ev.data)
                if audio:
                    collected.append(audio)
                    yield audio
                if is_final or ev.event == "complete":
                    break
        if not collected:
            raise GnaniError("upstream", "TTS stream returned no audio")
        if self.cache:
            self.cache.put(key, b"".join(collected))

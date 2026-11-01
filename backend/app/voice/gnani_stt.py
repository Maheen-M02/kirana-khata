"""Gnani Prisma STT over REST (`POST /stt/v3`, multipart). Live-doc shape: docs/DOC_DIFFS.md."""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, ValidationError

from app.voice.errors import GnaniError
from app.voice.gnani_http import GnaniTransport

STT_PATH = "/stt/v3"
# The API detects format from the file-name *extension* (DOC_DIFFS #6).
SUPPORTED_EXTENSIONS = (".wav", ".mp3", ".ogg", ".flac", ".aac", ".m4a")
MAX_KEYTERMS = 200


@dataclass(frozen=True)
class SttResult:
    transcript: str
    request_id: str | None
    model: str | None
    detected_language: str | None
    truncated: bool
    upstream_processing_s: float | None
    upstream_e2e_s: float | None
    latency_ms: int

    @property
    def is_empty(self) -> bool:
        return not self.transcript.strip()


class SpeechToText(Protocol):
    async def transcribe(
        self,
        audio: bytes,
        *,
        filename: str = "audio.wav",
        keyterms: Sequence[str] = (),
        request_id: str | None = None,
    ) -> SttResult: ...


class _SttResponse(BaseModel):
    """v3 200 body. `model`/timings are absent for <0.1 s audio; `truncated` only when true."""

    success: bool = True
    request_id: str | None = None
    transcript: str = ""
    model: str | None = None
    detected_language_code: str | None = None
    truncated: bool = False
    processing_time: float | None = None
    end_to_end_latency: float | None = None


def build_form(
    *, model: str, language: str, fmt: str, keyterms: Sequence[str] = ()
) -> dict[str, str]:
    """Form fields. `format` is always explicit: v3's default flips to digits for a single
    hi-IN/en-IN (DOC_DIFFS #2)."""
    form = {"model": model, "language_code": language, "format": fmt}
    terms = [t.strip() for t in keyterms if t.strip()][:MAX_KEYTERMS]
    if terms:
        form["keyterms"] = json.dumps(terms, ensure_ascii=False)
    return form


def parse_response(body: object, latency_ms: int) -> SttResult:
    try:
        r = _SttResponse.model_validate(body)
    except ValidationError as e:
        raise GnaniError("upstream", "unexpected STT response shape") from e
    if not r.success:
        raise GnaniError("upstream", "STT returned success=false")
    return SttResult(
        transcript=r.transcript.strip(),
        request_id=r.request_id,
        model=r.model,
        detected_language=r.detected_language_code,
        truncated=r.truncated,
        upstream_processing_s=r.processing_time,
        upstream_e2e_s=r.end_to_end_latency,
        latency_ms=latency_ms,
    )


class GnaniSTT:
    def __init__(
        self,
        transport: GnaniTransport,
        *,
        model: str,
        language: str,
        fmt: str,
        timeout_s: float = 10.0,
    ) -> None:
        self._t = transport
        self.model = model
        self.language = language
        self.fmt = fmt
        self.timeout_s = timeout_s

    async def transcribe(
        self,
        audio: bytes,
        *,
        filename: str = "audio.wav",
        keyterms: Sequence[str] = (),
        request_id: str | None = None,
    ) -> SttResult:
        if not filename.lower().endswith(SUPPORTED_EXTENSIONS):
            raise ValueError(f"filename must end with one of {SUPPORTED_EXTENSIONS}")
        if not audio:
            raise GnaniError("bad_audio", "empty audio")
        t0 = time.perf_counter()
        r = await self._t.request(
            "POST",
            STT_PATH,
            service="stt",
            timeout_s=self.timeout_s,
            request_id=request_id,
            files={"audio_file": (filename, audio, "audio/wav")},
            data=build_form(
                model=self.model, language=self.language, fmt=self.fmt, keyterms=keyterms
            ),
        )
        latency_ms = round((time.perf_counter() - t0) * 1000)
        try:
            body = r.json()
        except ValueError as e:
            raise GnaniError("upstream", "STT response was not JSON") from e
        return parse_response(body, latency_ms)

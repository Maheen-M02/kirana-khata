"""In-memory fakes for STT/TTS. Tests and keyless dev use these; they never touch the network."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence

from app.voice.errors import GnaniError
from app.voice.gnani_stt import SttResult
from app.voice.gnani_tts import MP3, TtsResult, validate_text


class FakeSTT:
    """Transcripts keyed by fixture filename (e.g. "sharma_udhaar.wav"), or a `script` queue
    consumed in order (for multi-turn conversations: entry, then "haan")."""

    def __init__(
        self,
        transcripts: Mapping[str, str] | None = None,
        *,
        default: str | None = None,
        error: GnaniError | None = None,
        script: Sequence[str] = (),
    ) -> None:
        self.transcripts = dict(transcripts or {})
        self.script = list(script)
        self.default = default
        self.error = error
        self.calls: list[str] = []

    async def transcribe(
        self,
        audio: bytes,
        *,
        filename: str = "audio.wav",
        keyterms: Sequence[str] = (),
        request_id: str | None = None,
    ) -> SttResult:
        self.calls.append(filename)
        if self.error:
            raise self.error
        if self.script:
            text = self.script.pop(0)
        elif filename in self.transcripts:
            text = self.transcripts[filename]
        elif self.default is not None:
            text = self.default
        else:
            raise KeyError(f"FakeSTT has no transcript for {filename!r}")
        return SttResult(
            transcript=text,
            request_id=request_id or f"fake-{len(self.calls)}",
            model="fake-prisma",
            detected_language="hi-IN" if text else None,
            truncated=False,
            upstream_processing_s=0.0,
            upstream_e2e_s=0.0,
            latency_ms=1,
        )


class FakeTTS:
    """Deterministic fake audio: b"FAKEMP3:" + text. Records every text it was asked to say."""

    def __init__(self, *, error: GnaniError | None = None) -> None:
        self.error = error
        self.calls: list[str] = []

    def _audio(self, text: str) -> bytes:
        return b"FAKEMP3:" + validate_text(text).encode("utf-8")

    async def synthesize(self, text: str) -> TtsResult:
        self.calls.append(text)
        if self.error:
            raise self.error
        return TtsResult(self._audio(text), MP3, cached=False, latency_ms=1)

    async def stream(self, text: str) -> AsyncIterator[bytes]:
        self.calls.append(text)
        if self.error:
            raise self.error
        audio = self._audio(text)
        mid = len(audio) // 2
        yield audio[:mid]
        yield audio[mid:]

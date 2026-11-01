"""Real Gnani calls — SPENDS CREDITS. Run only on request: `uv run pytest -m live`.

Round trip with no recordings needed: Timbre speaks a known Hinglish sentence, ffmpeg converts it,
Prisma transcribes it back. Costs 2 calls (1 TTS + 1 STT); TTS is free on a cache hit.
"""

from __future__ import annotations

import pytest

from app.config import get_settings
from app.voice.audio import prepare_audio
from app.voice.factory import build_voice

pytestmark = pytest.mark.live

SENTENCE = "Sharma ji ne do sau rupaye jama kiye."


@pytest.fixture(autouse=True)
def _needs_key() -> None:
    if not get_settings().gnani_configured:
        pytest.skip("GNANI_API_KEY not set")


async def test_tts_then_stt_round_trip() -> None:
    stack = build_voice(get_settings())
    try:
        speech = await stack.tts.synthesize(SENTENCE)
        assert len(speech.audio) > 1000
        audio = await prepare_audio(speech.audio)
        assert audio.speech_ms > 1000
        r = await stack.stt.transcribe(audio.wav)
    finally:
        await stack.aclose()
    text = r.transcript.lower()
    print(f"\ntranscript={r.transcript!r} lang={r.detected_language} stt={r.latency_ms}ms")
    assert r.request_id
    assert any(w in text for w in ("sharma", "शर्मा")), r.transcript

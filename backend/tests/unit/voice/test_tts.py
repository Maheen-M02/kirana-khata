from __future__ import annotations

import base64
import json
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import respx

from app.voice.errors import GnaniError
from app.voice.fakes import FakeSTT, FakeTTS
from app.voice.gnani_http import GnaniTransport
from app.voice.gnani_tts import GnaniTTS, TtsCache, decode_chunk, iter_sse, validate_text

TEXT = "Sharma ji, ek sau bees rupaye udhaar. Sahi hai?"


def make_tts(t: GnaniTransport, cache_dir: Path | None = None, voice: str = "Poorvi") -> GnaniTTS:
    return GnaniTTS(
        t,
        model="timbre-v2.5",
        voice=voice,
        language="hi-en",
        speed=0.95,
        cache=TtsCache(cache_dir) if cache_dir else None,
    )


def sse_body(*chunks: bytes, error: str | None = None) -> str:
    out = ['event: start\ndata: {"status": "streaming_started"}\n']
    for i, c in enumerate(chunks, 1):
        payload = {"chunk_index": i, "audio": base64.b64encode(c).decode(), "is_final": False}
        out.append(f"event: chunk\ndata: {json.dumps(payload)}\n")
    if error:
        out.append(f'event: error\ndata: {{"type": "error", "message": "{error}"}}\n')
    else:
        done = {"chunk_index": len(chunks) + 1, "audio": "", "is_final": True}
        out.append(f"event: complete\ndata: {json.dumps(done)}\n")
    return "\n".join(out) + "\n"


async def test_rest_body_matches_documented_shape(
    transport: GnaniTransport, router: respx.MockRouter
) -> None:
    route = router.post("/api/v1/tts/inference").mock(
        return_value=httpx.Response(200, content=b"ID3mp3")
    )
    r = await make_tts(transport).synthesize(TEXT)
    assert r.audio == b"ID3mp3"
    assert r.content_type == "audio/mpeg"
    sent = json.loads(route.calls.last.request.content)
    assert sent == {
        "text": TEXT,
        "model": "timbre-v2.5",
        "voice": "Poorvi",
        "language": "hi-en",
        "speed": 0.95,
        "audio_config": {
            "sample_rate": 24000, "num_channels": 1, "sample_width": 2,
            "encoding": "linear_pcm", "container": "mp3", "bitrate": "64k",
        },
    }  # fmt: skip


async def test_cache_hit_skips_api(
    transport: GnaniTransport, router: respx.MockRouter, tmp_path: Path
) -> None:
    route = router.post("/api/v1/tts/inference").mock(
        return_value=httpx.Response(200, content=b"A")
    )
    tts = make_tts(transport, tmp_path)
    first = await tts.synthesize(TEXT)
    second = await tts.synthesize("  Sharma ji,  ek sau bees rupaye udhaar. Sahi hai? ")
    assert (first.cached, second.cached) == (False, True)
    assert second.audio == b"A"
    assert route.call_count == 1


def test_cache_key_depends_on_voice_and_text() -> None:
    a = {"text": "x", "voice": "Poorvi"}
    assert TtsCache.key(a) != TtsCache.key({**a, "voice": "Shivani"})
    assert TtsCache.key(a) != TtsCache.key({**a, "text": "y"})
    assert TtsCache.key(a) == TtsCache.key(dict(reversed(a.items())))


async def test_sse_stream_yields_decoded_chunks_and_caches(
    transport: GnaniTransport, router: respx.MockRouter, tmp_path: Path
) -> None:
    route = router.post("/api/v1/tts/sse").mock(
        return_value=httpx.Response(
            200, text=sse_body(b"AAA", b"BBB"), headers={"content-type": "text/event-stream"}
        )
    )
    tts = make_tts(transport, tmp_path)
    assert [c async for c in tts.stream(TEXT)] == [b"AAA", b"BBB"]
    assert [c async for c in tts.stream(TEXT)] == [b"AAABBB"]  # served from cache
    assert route.call_count == 1


async def test_sse_error_event_raises(transport: GnaniTransport, router: respx.MockRouter) -> None:
    router.post("/api/v1/tts/sse").mock(
        return_value=httpx.Response(200, text=sse_body(b"A", error="Invalid text"))
    )
    with pytest.raises(GnaniError) as ei:
        _ = [c async for c in make_tts(transport).stream(TEXT)]
    assert ei.value.kind == "upstream"


async def test_rest_429_retried(transport: GnaniTransport, router: respx.MockRouter) -> None:
    route = router.post("/api/v1/tts/inference").mock(
        side_effect=[httpx.Response(429, json={}), httpx.Response(200, content=b"ok")]
    )
    assert (await make_tts(transport).synthesize(TEXT)).audio == b"ok"
    assert route.call_count == 2


async def test_iter_sse_handles_multiline_comments_and_crlf() -> None:
    async def lines() -> AsyncIterator[str]:
        for line in [": keepalive", "event: chunk\r", "data: a", "data: b", "", "data: tail"]:
            yield line

    events = [e async for e in iter_sse(lines())]
    assert [(e.event, e.data) for e in events] == [("chunk", "a\nb"), ("message", "tail")]


def test_decode_chunk_rejects_garbage() -> None:
    with pytest.raises(GnaniError):
        decode_chunk('{"audio": "%%%not-base64"}')
    assert decode_chunk('{"audio": "", "is_final": true}') == (b"", True)


@pytest.mark.parametrize("bad", ["", "   ", "x" * 401])
def test_validate_text_rejects_empty_and_long(bad: str) -> None:
    with pytest.raises(ValueError, match="TTS text"):
        validate_text(bad)


async def test_fakes_behave_like_the_protocols() -> None:
    stt = FakeSTT({"a.wav": "Gupta ji ne teen sau jama kiye"})
    r = await stt.transcribe(b"x", filename="a.wav")
    assert r.transcript.startswith("Gupta")
    with pytest.raises(KeyError):
        await stt.transcribe(b"x", filename="missing.wav")
    tts = FakeTTS()
    assert b"".join([c async for c in tts.stream("Entry ho gayi.")]) == b"FAKEMP3:Entry ho gayi."
    assert tts.calls == ["Entry ho gayi."]

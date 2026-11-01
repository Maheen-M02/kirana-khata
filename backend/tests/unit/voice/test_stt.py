from __future__ import annotations

import json

import httpx
import pytest
import respx

from app.voice.errors import GnaniError
from app.voice.gnani_http import GnaniTransport
from app.voice.gnani_stt import GnaniSTT, build_form, parse_response
from tests.unit.voice.conftest import fixture

WAV = b"RIFF\x00\x00\x00\x00WAVEfake"


def make_stt(t: GnaniTransport, fmt: str = "transcribe") -> GnaniSTT:
    return GnaniSTT(t, model="prisma-v3.0", language="hi-IN,en-IN", fmt=fmt)


async def test_success_parses_v3_body(transport: GnaniTransport, router: respx.MockRouter) -> None:
    router.post("/stt/v3").mock(
        return_value=httpx.Response(200, json=fixture("stt_v3_success.docs.json"))
    )
    r = await make_stt(transport).transcribe(WAV)
    assert r.transcript.startswith("शर्मा जी")
    assert r.request_id == "5c1f0a52-6d62-4e0b-9a38-2f2b8a8f7a10"
    assert r.model == "prisma-v3.0"
    assert r.detected_language == "hi-IN"
    assert r.upstream_processing_s == pytest.approx(0.41)
    assert not r.truncated
    assert r.latency_ms >= 0


async def test_multipart_uses_audio_file_field_and_explicit_format(
    transport: GnaniTransport, router: respx.MockRouter
) -> None:
    route = router.post("/stt/v3").mock(
        return_value=httpx.Response(200, json=fixture("stt_v3_success.docs.json"))
    )
    await make_stt(transport, fmt="transliterate").transcribe(WAV, keyterms=["Sharma ji", " "])
    body = route.calls.last.request.content.decode("utf-8", "replace")
    assert 'name="audio_file"; filename="audio.wav"' in body
    assert 'name="model"\r\n\r\nprisma-v3.0' in body
    assert 'name="language_code"\r\n\r\nhi-IN,en-IN' in body
    assert 'name="format"\r\n\r\ntransliterate' in body
    assert 'name="keyterms"\r\n\r\n["Sharma ji"]' in body


def test_form_omits_keyterms_when_empty_and_caps_at_200() -> None:
    assert "keyterms" not in build_form(model="m", language="hi-IN", fmt="verbatim")
    form = build_form(
        model="m", language="hi-IN", fmt="verbatim", keyterms=[f"n{i}" for i in range(300)]
    )
    assert len(json.loads(form["keyterms"])) == 200


def test_empty_transcript_for_tiny_audio_is_not_an_error() -> None:
    r = parse_response(fixture("stt_v3_empty_short_audio.docs.json"), 5)
    assert r.is_empty
    assert r.model is None
    assert r.upstream_processing_s is None


def test_truncated_flag_is_surfaced() -> None:
    assert parse_response(fixture("stt_v3_truncated.docs.json"), 5).truncated


def test_success_false_raises_upstream() -> None:
    with pytest.raises(GnaniError) as ei:
        parse_response({"success": False, "transcript": ""}, 1)
    assert ei.value.kind == "upstream"


async def test_bad_audio_400_is_not_retried(
    transport: GnaniTransport, router: respx.MockRouter
) -> None:
    route = router.post("/stt/v3").mock(
        return_value=httpx.Response(400, json=fixture("err_stt_envelope_bad_audio.docs.json"))
    )
    with pytest.raises(GnaniError) as ei:
        await make_stt(transport).transcribe(WAV)
    assert ei.value.kind == "bad_audio"
    assert route.call_count == 1


async def test_rejects_filename_without_supported_extension(transport: GnaniTransport) -> None:
    with pytest.raises(ValueError, match="filename"):
        await make_stt(transport).transcribe(WAV, filename="clip.webm")


async def test_empty_audio_never_calls_api(
    transport: GnaniTransport, router: respx.MockRouter
) -> None:
    route = router.post("/stt/v3")
    with pytest.raises(GnaniError):
        await make_stt(transport).transcribe(b"")
    assert route.call_count == 0

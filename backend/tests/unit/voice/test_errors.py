from __future__ import annotations

import pytest

from app.voice.errors import FRIENDLY, GnaniError, map_error
from tests.unit.voice.conftest import fixture


@pytest.mark.parametrize(
    ("status", "fixture_name", "kind", "code", "retryable"),
    [
        (400, "err_stt_envelope_bad_audio.docs.json", "bad_audio", "AUDIO_CONVERSION_ERROR", False),
        (422, "err_validation_422.docs.json", "bad_request", "VALIDATION", False),
        (429, "err_rate_limited_429.docs.json", "rate_limit", "RATE_LIMITED", True),
        (504, "err_stt_504.docs.json", "timeout", "UPSTREAM_TIMEOUT", True),
        (400, "err_tts_flat_400.docs.json", "bad_request", None, False),
        (401, "err_invalid_key_401.docs.json", "auth", "INVALID_API_KEY", False),
    ],
)
def test_documented_shapes(
    status: int, fixture_name: str, kind: str, code: str | None, retryable: bool
) -> None:
    err = map_error(status, fixture(fixture_name))
    assert err.kind == kind
    assert err.code == code
    assert err.status == status
    assert err.retryable is retryable


@pytest.mark.parametrize(
    ("status", "kind"),
    [(402, "credits"), (403, "auth"), (500, "upstream"), (503, "upstream"), (418, "upstream")],
)
def test_status_mapping_without_body(status: int, kind: str) -> None:
    assert map_error(status, None).kind == kind


def test_other_400_codes_are_our_bug_not_bad_audio() -> None:
    body = {"success": False, "error": {"type": "INVALID_LANGUAGE_CODE", "message": "x"}}
    assert map_error(400, body).kind == "bad_request"


def test_all_audio_codes_map_to_bad_audio() -> None:
    for code in ("EMPTY_AUDIO", "UNSUPPORTED_AUDIO_FORMAT", "MAX_AUDIO_DURATION_EXCEEDED"):
        assert map_error(400, {"error": {"type": code, "message": ""}}).kind == "bad_audio"


def test_every_kind_has_short_friendly_hinglish() -> None:
    for kind, msg in FRIENDLY.items():
        err = GnaniError(kind)
        assert err.user_message == msg
        assert len(msg) < 80
        assert "error" not in msg.lower()


def test_long_upstream_message_is_truncated() -> None:
    err = map_error(500, {"message": "x" * 5000})
    assert len(err.detail) <= 300

"""Gnani error model + mapping from the five documented error body shapes (see DOC_DIFFS #8)."""

from __future__ import annotations

from typing import Any, Literal

GnaniErrorKind = Literal[
    "auth",  # 401 / 403: bad, missing or out-of-scope key
    "credits",  # 402: Gnani account out of credit
    "rate_limit",  # 429: 1 active request per account
    "bad_audio",  # 400 audio errors (empty / undecodable / too long)
    "bad_request",  # other 400 / 422: our request is wrong (a bug, not the user)
    "upstream",  # 5xx or network failure
    "timeout",  # client timeout or 504 UPSTREAM_TIMEOUT
    "budget",  # our own GNANI_CREDIT_GUARD refused the call
]

# Short, warm Hinglish lines for the UI. Never show raw upstream messages to the shopkeeper.
FRIENDLY: dict[GnaniErrorKind, str] = {
    "auth": "Awaaz service se judne mein dikkat hai. Thodi der baad koshish kijiye.",
    "credits": "Awaaz service ka balance khatam ho gaya hai. Admin ko bataiye.",
    "rate_limit": "Ek second rukiye, phir boliye.",
    "bad_audio": "Awaaz saaf nahi aayi, dobara boliye.",
    "bad_request": "Kuch gadbad ho gayi. Dobara boliye.",
    "upstream": "Awaaz service abhi dheemi hai. Dobara koshish kijiye.",
    "timeout": "Jawab aane mein der ho gayi. Dobara boliye.",
    "budget": "Aaj ki awaaz limit poori ho gayi.",
}

RETRYABLE_KINDS: frozenset[GnaniErrorKind] = frozenset({"rate_limit", "upstream", "timeout"})

_AUDIO_ERROR_CODES = frozenset(
    {
        "EMPTY_AUDIO",
        "UNSUPPORTED_AUDIO_FORMAT",
        "AUDIO_CONVERSION_ERROR",
        "MAX_AUDIO_DURATION_EXCEEDED",
    }
)


class GnaniError(Exception):
    def __init__(
        self,
        kind: GnaniErrorKind,
        detail: str = "",
        *,
        status: int | None = None,
        code: str | None = None,
    ) -> None:
        super().__init__(f"{kind}: {detail}" if detail else kind)
        self.kind: GnaniErrorKind = kind
        self.detail = detail
        self.status = status
        self.code = code

    @property
    def retryable(self) -> bool:
        return self.kind in RETRYABLE_KINDS

    @property
    def user_message(self) -> str:
        return FRIENDLY[self.kind]


def _extract_code_and_message(body: Any) -> tuple[str | None, str]:
    """Pull (code, message) out of any of the documented shapes."""
    if not isinstance(body, dict):
        return None, ""
    # STT envelope: {"success": false, "error": {"type", "message"}}
    err = body.get("error")
    if isinstance(err, dict):
        return _str_or_none(err.get("type")), str(err.get("message", ""))
    detail = body.get("detail")
    # Auth / rate limit: {"detail": {"error_code", "message", "status_code"}}
    if isinstance(detail, dict):
        return _str_or_none(detail.get("error_code")), str(detail.get("message", ""))
    # Validation: {"detail": [{"type", "loc", "msg"}]}
    if isinstance(detail, list) and detail and isinstance(detail[0], dict):
        loc = detail[0].get("loc", [])
        return "VALIDATION", f"{detail[0].get('msg', '')} at {loc}"
    # STT 504: {"error": "Gateway Timeout", "code": "UPSTREAM_TIMEOUT", "message"}
    if "code" in body:
        return _str_or_none(body.get("code")), str(body.get("message", ""))
    # TTS flat: {"success": false, "message", "status_code"}
    return None, str(body.get("message", ""))


def _str_or_none(v: object) -> str | None:
    return v if isinstance(v, str) else None


def map_error(status: int, body: Any) -> GnaniError:
    code, message = _extract_code_and_message(body)
    kind: GnaniErrorKind
    if status in (401, 403):
        kind = "auth"
    elif status == 402:
        kind = "credits"
    elif status == 429:
        kind = "rate_limit"
    elif status == 504:
        kind = "timeout"
    elif status >= 500:
        kind = "upstream"
    elif status == 400 and code in _AUDIO_ERROR_CODES:
        kind = "bad_audio"
    elif status in (400, 404, 405, 413, 415, 422):
        kind = "bad_request"
    else:
        kind = "upstream"
    return GnaniError(kind, message[:300], status=status, code=code)

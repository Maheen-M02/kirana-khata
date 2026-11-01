"""Build the real Gnani voice stack from settings (one shared httpx client + gate + guard)."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.config import Settings
from app.voice.credit_guard import FileCreditGuard
from app.voice.errors import GnaniError
from app.voice.gnani_http import GnaniTransport
from app.voice.gnani_stt import GnaniSTT
from app.voice.gnani_tts import GnaniTTS, TtsCache
from app.voice.tts_queue import SingleFlight


@dataclass
class VoiceStack:
    stt: GnaniSTT
    tts: GnaniTTS
    transport: GnaniTransport
    guard: FileCreditGuard
    client: httpx.AsyncClient

    async def aclose(self) -> None:
        await self.client.aclose()


def build_voice(settings: Settings) -> VoiceStack:
    """Raises GnaniError(kind='auth') if GNANI_API_KEY is empty."""
    if not settings.gnani_configured:
        raise GnaniError("auth", "GNANI_API_KEY is not set")
    client = httpx.AsyncClient(
        base_url=settings.gnani_base_url,
        limits=httpx.Limits(max_connections=4, max_keepalive_connections=2),
    )
    # The daily guard only refuses in dev; elsewhere it still counts and logs every call.
    limit = settings.gnani_credit_guard if settings.app_env == "dev" else 0
    guard = FileCreditGuard(settings.var_dir / "gnani_credits.json", limit=limit, tz=settings.tz)
    transport = GnaniTransport(
        client,
        api_key=settings.gnani_api_key.get_secret_value(),
        gate=SingleFlight(settings.gnani_max_concurrency),
        guard=guard,
    )
    stt = GnaniSTT(
        transport,
        model=settings.gnani_stt_model,
        language=settings.gnani_stt_language,
        fmt=settings.gnani_stt_format,
        timeout_s=settings.gnani_stt_timeout_s,
    )
    tts = GnaniTTS(
        transport,
        model=settings.gnani_tts_model,
        voice=settings.gnani_tts_voice,
        language=settings.gnani_tts_language,
        speed=settings.gnani_tts_speed,
        cache=TtsCache(settings.var_dir / "tts_cache"),
        timeout_s=settings.gnani_tts_timeout_s,
    )
    return VoiceStack(stt=stt, tts=tts, transport=transport, guard=guard, client=client)

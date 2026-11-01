"""Voice loop endpoints (MASTER_PROMPT §6).

POST /api/voice/turn              multipart `audio` (+ `Idempotency-Key` header)
POST /api/voice/{event_id}/confirm JSON {accept?, customer_id?, amount_paise?} OR multipart `audio`
GET  /api/voice/audio/{key}.mp3    cached Timbre audio
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, StrictBool, StrictInt, ValidationError

from app.config import Settings, get_settings
from app.core.errors import AppError
from app.deps import DbSession, ShopId
from app.nlu.parser import IntentParser
from app.voice.gnani_stt import SpeechToText
from app.voice.gnani_tts import TextToSpeech
from app.voice.turn import TurnResult, VoiceTurnService

router = APIRouter(prefix="/voice", tags=["voice"])

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
_KEY_RE = re.compile(r"^[a-f0-9]{64}$")
_IDEM_RE = re.compile(r"^[A-Za-z0-9_\-]{8,64}$")


@dataclass
class VoiceComponents:
    stt: SpeechToText | None
    tts: TextToSpeech | None
    parser: IntentParser
    tts_voice_key: str


def voice_components(request: Request) -> VoiceComponents:
    comps: VoiceComponents | None = getattr(request.app.state, "voice", None)
    if comps is None:
        raise AppError("voice_not_ready", "Awaaz service abhi chalu nahi hai.", 503)
    return comps


Components = Annotated[VoiceComponents, Depends(voice_components)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def _service(db: DbSession, comps: Components, settings: SettingsDep) -> VoiceTurnService:
    return VoiceTurnService(
        db=db,
        stt=comps.stt,
        tts=comps.tts,
        parser=comps.parser,
        audio_dir=settings.var_dir / "audio",
        tts_voice_key=comps.tts_voice_key,
    )


Service = Annotated[VoiceTurnService, Depends(_service)]


class TurnOut(BaseModel):
    event_id: int
    status: str
    stage: str
    transcript: str | None
    intent: dict[str, Any] | None
    confirm_text: str
    confirm_audio_url: str | None
    needs_confirmation: bool
    options: list[dict[str, Any]]
    entry_id: int | None
    customer_id: int | None
    balance_paise: int | None
    latency_ms: dict[str, int]


class ConfirmIn(BaseModel):
    accept: StrictBool | None = None
    customer_id: StrictInt | None = None
    amount_paise: StrictInt | None = Field(default=None, gt=0)


def _out(r: TurnResult) -> TurnOut:
    return TurnOut(**r.to_json())


async def _read_audio(request: Request, settings: Settings) -> tuple[bytes | None, str | None]:
    """Multipart `audio` (and a dev-only `transcript` override for keyless local testing)."""
    form = await request.form(max_files=1, max_fields=5)
    audio_field = form.get("audio")
    transcript = form.get("transcript")
    audio: bytes | None = None
    if audio_field is not None and not isinstance(audio_field, str):
        audio = await audio_field.read(MAX_UPLOAD_BYTES + 1)
        if len(audio) > MAX_UPLOAD_BYTES:
            raise AppError("audio_too_large", "Recording bahut lambi hai. Chhota boliye.", 413)
    if isinstance(transcript, str):
        if settings.app_env == "prod":
            raise AppError("transcript_not_allowed", "Sirf awaaz bhejiye.", 400)
        return audio, transcript[:500]
    if audio is None:
        raise AppError("no_audio", "Awaaz nahi mili. Button dabaye rakh ke boliye.", 400)
    return audio, None


@router.post("/turn", response_model=TurnOut)
async def voice_turn(
    request: Request,
    service: Service,
    shop_id: ShopId,
    settings: SettingsDep,
    idempotency_key: Annotated[str | None, Header()] = None,
) -> TurnOut:
    if idempotency_key is not None and not _IDEM_RE.match(idempotency_key):
        raise AppError("bad_idempotency_key", "Kuch gadbad ho gayi. Dobara boliye.", 400)
    audio, transcript = await _read_audio(request, settings)
    return _out(
        await service.handle_turn(
            shop_id, audio=audio, transcript=transcript, idempotency_key=idempotency_key
        )
    )


@router.post("/{event_id}/confirm", response_model=TurnOut)
async def voice_confirm(
    event_id: int, request: Request, service: Service, shop_id: ShopId, settings: SettingsDep
) -> TurnOut:
    ctype = request.headers.get("content-type", "")
    if ctype.startswith(("multipart/", "application/x-www-form-urlencoded")):
        audio, transcript = await _read_audio(request, settings)
        r = await service.handle_confirm(shop_id, event_id, audio=audio, transcript=transcript)
        return _out(r)
    try:
        body = ConfirmIn.model_validate(await request.json())
    except (ValueError, ValidationError) as e:
        raise AppError("bad_confirm", "Haan ya nahi boliye.", 422) from e
    r = await service.handle_confirm(
        shop_id,
        event_id,
        accept=body.accept,
        customer_id=body.customer_id,
        amount_paise=body.amount_paise,
    )
    return _out(r)


@router.get("/audio/{name}")
def voice_audio(name: str, settings: SettingsDep) -> FileResponse:
    key = name.removesuffix(".mp3")
    if not name.endswith(".mp3") or not _KEY_RE.match(key):
        raise AppError("not_found", "Awaaz nahi mili.", 404)
    path: Path = settings.var_dir / "audio" / "tts" / f"{key}.mp3"
    if not path.is_file():
        raise AppError("not_found", "Awaaz nahi mili.", 404)
    return FileResponse(
        path,
        media_type="audio/mpeg",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )

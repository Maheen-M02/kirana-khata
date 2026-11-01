"""FastAPI app factory."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import auth, health, ledger, voice
from app.config import get_settings
from app.core.errors import AppError, install_error_handlers
from app.core.logging import configure_logging, get_logger
from app.core.retention import retention_loop
from app.core.security import WEAK_SECRETS
from app.nlu.factory import build_parser
from app.voice.factory import build_voice

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Build the Gnani + NLU stacks once (shared httpx clients, one single-flight gate)."""
    settings = get_settings()
    nlu = build_parser(settings)
    stack = build_voice(settings) if settings.gnani_configured else None
    if stack is None:
        log.warning("gnani_not_configured", hint="voice turns need GNANI_API_KEY")
    app.state.voice = voice.VoiceComponents(
        stt=stack.stt if stack else None,
        tts=stack.tts if stack else None,
        parser=nlu.parser,
        tts_voice_key=f"{settings.gnani_tts_model}|{settings.gnani_tts_voice}|{settings.gnani_tts_language}",
    )
    cleaner = asyncio.create_task(retention_loop(settings.var_dir / "audio" / "in"))
    try:
        yield
    finally:
        cleaner.cancel()
        await nlu.aclose()
        if stack is not None:
            await stack.aclose()


MAX_BODY_BYTES = 2 * 1024 * 1024 + 64 * 1024  # 2 MB audio + multipart overhead


def create_app() -> FastAPI:
    settings = get_settings()
    if settings.app_env == "prod" and (
        settings.jwt_secret.get_secret_value() in WEAK_SECRETS
        or len(settings.jwt_secret.get_secret_value()) < 32
    ):
        raise RuntimeError("JWT_SECRET is weak: set a random 32+ char secret in prod")
    configure_logging(json_logs=settings.app_env != "dev")

    app = FastAPI(title="Kirana Khata API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_id_mw(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > MAX_BODY_BYTES:
            err = AppError("too_large", "Recording bahut lambi hai. Chhota boliye.", 413)
            return JSONResponse(
                status_code=413, content={"error": {"code": err.code, "message": err.message}}
            )
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=rid)
        response = await call_next(request)
        response.headers["x-request-id"] = rid
        return response

    install_error_handlers(app)
    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(ledger.router, prefix="/api")
    app.include_router(voice.router, prefix="/api")
    return app


app = create_app()

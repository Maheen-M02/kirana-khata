"""FastAPI app factory."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, ledger, voice
from app.config import get_settings
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging, get_logger
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
    try:
        yield
    finally:
        await nlu.aclose()
        if stack is not None:
            await stack.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
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
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=rid)
        response = await call_next(request)
        response.headers["x-request-id"] = rid
        return response

    install_error_handlers(app)
    app.include_router(health.router, prefix="/api")
    app.include_router(ledger.router, prefix="/api")
    app.include_router(voice.router, prefix="/api")
    return app


app = create_app()

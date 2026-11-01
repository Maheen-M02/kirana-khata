"""FastAPI app factory."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, ledger
from app.config import get_settings
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(json_logs=settings.app_env != "dev")

    app = FastAPI(title="Kirana Khata API", version="0.1.0")

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
    return app


app = create_app()

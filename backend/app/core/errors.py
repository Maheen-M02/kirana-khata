"""App errors and handlers. The shopkeeper never sees a raw error or stack trace."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

log = get_logger(__name__)

FRIENDLY_FALLBACK = "Kuch gadbad ho gayi. Thodi der baad dobara koshish kijiye."


class AppError(Exception):
    """An expected failure with a short, warm Hinglish message for the UI."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(code)
        self.code = code
        self.message = message
        self.status_code = status_code


async def _app_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled_error", path=request.url.path, exc_type=type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal", "message": FRIENDLY_FALLBACK}},
    )


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(Exception, _unhandled_handler)

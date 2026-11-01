"""Request-scoped dependencies."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.errors import AppError
from app.core.security import SESSION_COOKIE, read_token
from app.db import get_session


def db_session() -> Iterator[Session]:
    yield from get_session()


DbSession = Annotated[Session, Depends(db_session)]


def current_shop_id(request: Request, settings: Annotated[Settings, Depends(get_settings)]) -> int:
    """The logged-in shop, from the httpOnly JWT cookie. Every query is scoped by this id,
    so one shop can never read or write another shop's ledger."""
    token = request.cookies.get(SESSION_COOKIE)
    shop_id = read_token(token, settings.jwt_secret.get_secret_value()) if token else None
    if shop_id is None:
        raise AppError("unauthenticated", "Login kijiye.", 401)
    return shop_id


ShopId = Annotated[int, Depends(current_shop_id)]

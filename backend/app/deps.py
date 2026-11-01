"""Request-scoped dependencies."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db import get_session
from app.ledger.models import Shop


def db_session() -> Iterator[Session]:
    yield from get_session()


DbSession = Annotated[Session, Depends(db_session)]


def current_shop_id(db: DbSession) -> int:
    """Phase 3: the single dev shop. Phase 6 replaces this with the phone+PIN JWT cookie;
    every route already scopes all reads/writes by this id, so nothing else changes."""
    shop_id = db.scalar(select(Shop.id).order_by(Shop.id).limit(1))
    if shop_id is None:
        raise AppError("no_shop", "Dukaan abhi setup nahi hui. `make seed` chalaiye.", 503)
    return shop_id


ShopId = Annotated[int, Depends(current_shop_id)]

"""POST /api/auth/login, POST /api/auth/logout, GET /api/auth/me."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.config import Settings, get_settings
from app.core.errors import AppError
from app.core.security import (
    PHONE_RE,
    SESSION_COOKIE,
    SESSION_DAYS,
    AttemptLimiter,
    issue_token,
    normalise_phone,
    verify_pin,
)
from app.deps import DbSession, ShopId
from app.ledger.models import Shop

router = APIRouter(prefix="/auth", tags=["auth"])
login_attempts = AttemptLimiter(max_failures=5, window_s=15 * 60)
BAD_LOGIN = "Phone ya PIN galat hai."


class LoginIn(BaseModel):
    phone: str = Field(min_length=10, max_length=20)
    pin: str = Field(min_length=4, max_length=4)


class MeOut(BaseModel):
    shop_id: int
    name: str
    phone: str


def _limiter() -> AttemptLimiter:
    return login_attempts


@router.post("/login", response_model=MeOut)
def login(
    body: LoginIn,
    request: Request,
    response: Response,
    db: DbSession,
    settings: Annotated[Settings, Depends(get_settings)],
    limiter: Annotated[AttemptLimiter, Depends(_limiter)],
) -> MeOut:
    phone = normalise_phone(body.phone)
    key = f"{phone}|{request.client.host if request.client else '?'}"
    if limiter.blocked(phone) or limiter.blocked(key):
        raise AppError(
            "too_many_attempts", "Bahut baar galat PIN. 15 minute baad koshish kijiye.", 429
        )
    shop = (
        db.scalar(select(Shop).where(Shop.owner_phone == phone)) if PHONE_RE.match(phone) else None
    )
    if shop is None or not verify_pin(body.pin, shop.pin_hash):
        if shop is None:
            verify_pin(body.pin, "")  # equal work either way: don't reveal which phones exist
        limiter.fail(phone)
        limiter.fail(key)
        raise AppError("bad_login", BAD_LOGIN, 401)
    limiter.reset(phone)
    limiter.reset(key)
    response.set_cookie(
        SESSION_COOKIE,
        issue_token(shop.id, settings.jwt_secret.get_secret_value()),
        max_age=SESSION_DAYS * 86400,
        httponly=True,
        secure=settings.app_env == "prod",
        samesite="lax",
        path="/",
    )
    return MeOut(shop_id=shop.id, name=shop.name, phone=shop.owner_phone)


@router.post("/logout", status_code=204)
def logout(response: Response) -> Response:
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.status_code = 204
    return response


@router.get("/me", response_model=MeOut)
def me(shop_id: ShopId, db: DbSession) -> MeOut:
    shop = db.get(Shop, shop_id)
    if shop is None:
        raise AppError("unauthenticated", "Login kijiye.", 401)
    return MeOut(shop_id=shop.id, name=shop.name, phone=shop.owner_phone)

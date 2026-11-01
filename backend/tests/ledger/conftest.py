"""Ledger tests run against the real Alembic schema (so DB triggers + CHECKs are exercised) on
SQLite, and also on Postgres when TEST_DATABASE_URL is set (CI does this). Append-only tables
can't be truncated, so isolation comes from a fresh shop per test, not a fresh DB."""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from app.deps import current_shop_id, db_session
from app.ledger import service as svc
from app.ledger.models import Shop
from app.main import create_app

BACKEND = Path(__file__).resolve().parents[2]
DB_KINDS = ["sqlite"] + (["postgres"] if os.environ.get("TEST_DATABASE_URL") else [])


def _pg_url(url: str) -> str:
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


def migrate(url: str) -> None:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session", params=DB_KINDS)
def engine(
    request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[Engine]:
    if request.param == "sqlite":
        url = f"sqlite:///{tmp_path_factory.mktemp('ledger') / 'ledger.db'}"
    else:
        url = _pg_url(os.environ["TEST_DATABASE_URL"])
        with create_engine(url).begin() as conn:  # clean slate once per session
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
    migrate(url)
    from app.db import make_engine

    eng = make_engine(url)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    session = Session(engine, expire_on_commit=False)
    yield session
    session.rollback()
    session.close()


def new_shop(db: Session) -> Shop:
    shop = svc.create_shop(db, name="Test Kirana", owner_phone=uuid.uuid4().hex[:12], pin_hash="!")
    db.commit()
    return shop


@pytest.fixture
def shop(db: Session) -> Shop:
    return new_shop(db)


@pytest.fixture
def api(engine: Engine, shop: Shop) -> Iterator[TestClient]:
    app = create_app()

    def _session() -> Iterator[Session]:
        s = Session(engine, expire_on_commit=False)
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[db_session] = _session
    app.dependency_overrides[current_shop_id] = lambda: shop.id
    with TestClient(app) as client:
        yield client

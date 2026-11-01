from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.db import get_engine, make_engine
from app.main import create_app


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    # model_validate bypasses env/.env sources, so a developer's local .env never leaks in.
    return Settings.model_validate(
        {
            "app_env": "test",
            "database_url": f"sqlite:///{tmp_path / 'test.db'}",
            "gnani_api_key": "",
            "nlu_mode": "rules",
        }
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    app = create_app()
    engine = make_engine(settings.database_url)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_engine] = lambda: engine
    with TestClient(app) as c:
        yield c
    engine.dispose()

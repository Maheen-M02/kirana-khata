from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.db import get_engine, make_engine
from app.main import create_app


def pytest_configure(config: pytest.Config) -> None:
    """Tests must NEVER spend Gnani credits or call Evon (CLAUDE.md). Unless this run explicitly
    selects `-m live`, blank the keys (env beats .env) and arm the transport tripwire."""
    if "live" in (config.getoption("markexpr") or "").replace("not live", ""):
        return
    os.environ["GNANI_API_KEY"] = ""
    os.environ["EVON_API_KEY"] = ""
    os.environ["NLU_MODE"] = "rules"
    os.environ["KK_BLOCK_PAID_CALLS"] = "1"
    get_settings.cache_clear()


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

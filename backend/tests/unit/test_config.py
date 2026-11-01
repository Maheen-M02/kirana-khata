from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings


def make(**kw: object) -> Settings:
    return Settings.model_validate(kw)  # bypasses env/.env sources


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("postgres://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("postgresql://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("postgresql+psycopg://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("sqlite:///./kirana.db", "sqlite:///./kirana.db"),
    ],
)
def test_database_url_normalised(raw: str, expected: str) -> None:
    assert make(database_url=raw).database_url == expected


def test_secrets_are_not_in_repr() -> None:
    s = make(gnani_api_key="super-secret-key", jwt_secret="jwt-secret")
    assert "super-secret-key" not in repr(s)
    assert "jwt-secret" not in repr(s)
    assert s.gnani_configured


def test_empty_key_is_unconfigured() -> None:
    assert not make(gnani_api_key="").gnani_configured


def test_tts_speed_bounds() -> None:
    with pytest.raises(ValidationError):
        make(gnani_tts_speed=1.3)


def test_stt_format_must_be_known() -> None:
    with pytest.raises(ValidationError):
        make(gnani_stt_format="bogus")

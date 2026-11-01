"""Typed settings loaded from env vars (and `.env` in dev). Never log secret fields."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

NluMode = Literal["hybrid", "evon", "rules"]
SttFormat = Literal["verbatim", "transcribe", "codemix", "transliterate"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["dev", "test", "prod"] = "dev"

    # Gnani
    gnani_api_key: SecretStr = SecretStr("")
    gnani_base_url: str = "https://api.vachana.ai"
    gnani_stt_model: str = "prisma-v3.0"
    gnani_stt_language: str = "hi-IN,en-IN"
    gnani_stt_format: SttFormat = "transcribe"
    gnani_tts_model: str = "timbre-v2.5"
    gnani_tts_voice: str = "Poorvi"
    gnani_tts_language: str = "hi-en"
    gnani_tts_speed: float = Field(default=0.95, ge=0.85, le=1.15)
    gnani_max_concurrency: int = Field(default=1, ge=1)
    gnani_credit_guard: int = Field(default=200, ge=0)

    # Evon
    evon_base_url: str = "http://localhost:8080/v1"
    evon_model: str = "evon"
    evon_api_key: SecretStr = SecretStr("")
    evon_timeout_s: float = 4.0
    nlu_mode: NluMode = "rules"

    # App
    database_url: str = "sqlite:///./kirana.db"
    jwt_secret: SecretStr = SecretStr("change-me")
    frontend_origin: str = "http://localhost:3000"
    tz: str = "Asia/Kolkata"

    @field_validator("database_url")
    @classmethod
    def _normalise_db_url(cls, v: str) -> str:
        """Neon/Render hand out `postgres://` / `postgresql://`; we use psycopg 3."""
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix) :]
        return v

    @property
    def gnani_configured(self) -> bool:
        return bool(self.gnani_api_key.get_secret_value())


@lru_cache
def get_settings() -> Settings:
    return Settings()

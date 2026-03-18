"""
app/config.py — Centralised settings loaded from environment variables.

All configuration is validated at startup via pydantic-settings.
If any required variable is missing the app will refuse to start.
"""

from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------ #
    # Application
    # ------------------------------------------------------------------ #
    ENV: Literal["development", "staging", "production"] = "development"

    # ------------------------------------------------------------------ #
    # Database
    # ------------------------------------------------------------------ #
    DATABASE_URL: str  # must start with postgresql+asyncpg://

    # ------------------------------------------------------------------ #
    # Redis
    # ------------------------------------------------------------------ #
    REDIS_URL: str = "redis://localhost:6379/0"

    # ------------------------------------------------------------------ #
    # JWT
    # ------------------------------------------------------------------ #
    JWT_SECRET_KEY: str
    JWT_REFRESH_SECRET_KEY: str
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ------------------------------------------------------------------ #
    # AWS S3
    # ------------------------------------------------------------------ #
    AWS_ACCESS_KEY_ID: str = "PLACEHOLDER"
    AWS_SECRET_ACCESS_KEY: str = "PLACEHOLDER"
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = "echo-media-dev"

    # ------------------------------------------------------------------ #
    # ID Verification
    # ------------------------------------------------------------------ #
    ID_VERIFY_PROVIDER: Literal["yoti", "clear", "mock"] = "mock"
    ID_VERIFY_API_KEY: str = "PLACEHOLDER"
    ID_VERIFY_CLIENT_ID: str = "PLACEHOLDER"
    ID_VERIFY_WEBHOOK_SECRET: str = "PLACEHOLDER"

    # ------------------------------------------------------------------ #
    # CORS
    # ------------------------------------------------------------------ #
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    # ------------------------------------------------------------------ #
    # Validators
    # ------------------------------------------------------------------ #
    @field_validator("DATABASE_URL")
    @classmethod
    def must_be_async_driver(cls, v: str) -> str:
        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "DATABASE_URL must use the asyncpg driver: "
                "postgresql+asyncpg://user:pass@host/db"
            )
        return v

    @model_validator(mode="after")
    def warn_placeholder_secrets_in_production(self) -> "Settings":
        if self.ENV == "production":
            placeholders = {"PLACEHOLDER", "CHANGE_ME"}
            critical = {
                "JWT_SECRET_KEY": self.JWT_SECRET_KEY,
                "JWT_REFRESH_SECRET_KEY": self.JWT_REFRESH_SECRET_KEY,
                "AWS_ACCESS_KEY_ID": self.AWS_ACCESS_KEY_ID,
                "ID_VERIFY_API_KEY": self.ID_VERIFY_API_KEY,
            }
            for name, val in critical.items():
                if any(p in val for p in placeholders):
                    raise ValueError(
                        f"{name} must not be a placeholder value in production."
                    )
        return self


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton — import this everywhere."""
    return Settings()

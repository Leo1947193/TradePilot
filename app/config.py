from __future__ import annotations

from functools import lru_cache
from urllib.parse import quote

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        extra="ignore",
    )

    postgres_dsn: str | None = None
    postgres_host: str | None = None
    postgres_port: int | None = Field(default=None, ge=1, le=65535)
    postgres_user: str | None = None
    postgres_password: str | None = None
    postgres_db: str | None = None
    postgres_min_pool_size: int = Field(default=1, ge=1)
    postgres_max_pool_size: int = Field(default=10, ge=1)
    postgres_connect_timeout_seconds: float = Field(default=5.0, gt=0)
    news_api_key: str | None = None
    market_data_provider: str = "yfinance"
    news_provider: str = "finnhub"
    macro_calendar_path: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    minimax_api_key: str | None = None
    minimax_base_url: str = "https://api.minimaxi.com/v1"
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    request_timeout_seconds: float = Field(default=8.0, gt=0)

    @model_validator(mode="after")
    def populate_postgres_dsn(self) -> "Settings":
        if self.postgres_dsn:
            return self

        missing_fields = [
            env_name
            for env_name, value in (
                ("POSTGRES_HOST", self.postgres_host),
                ("POSTGRES_PORT", self.postgres_port),
                ("POSTGRES_USER", self.postgres_user),
                ("POSTGRES_PASSWORD", self.postgres_password),
                ("POSTGRES_DB", self.postgres_db),
            )
            if value in (None, "")
        ]
        if missing_fields:
            raise ValueError(
                "POSTGRES_DSN or all of POSTGRES_HOST/POSTGRES_PORT/POSTGRES_USER/"
                "POSTGRES_PASSWORD/POSTGRES_DB must be configured"
            )

        user = quote(self.postgres_user, safe="")
        password = quote(self.postgres_password, safe="")
        object.__setattr__(
            self,
            "postgres_dsn",
            f"postgresql://{user}:{password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}",
        )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

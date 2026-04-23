from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        extra="ignore",
    )

    postgres_dsn: str
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
    minimax_base_url: str = "https://api.minimax.io/v1"
    request_timeout_seconds: float = Field(default=8.0, gt=0)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

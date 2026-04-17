from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import json

import pytest

from app.config import Settings
from app.services.providers.factory import ProviderConfigurationError, build_macro_calendar_provider


def test_settings_include_provider_env_vars(monkeypatch) -> None:
    monkeypatch.setenv("POSTGRES_DSN", "postgresql://user:pass@localhost:5432/tradepilot")
    monkeypatch.setenv("NEWS_API_KEY", "demo-key")
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "yfinance")
    monkeypatch.setenv("NEWS_PROVIDER", "finnhub")
    monkeypatch.setenv("MACRO_CALENDAR_PATH", "/tmp/macro.json")
    monkeypatch.setenv("REQUEST_TIMEOUT_SECONDS", "12.5")

    settings = Settings()

    assert settings.news_api_key == "demo-key"
    assert settings.market_data_provider == "yfinance"
    assert settings.news_provider == "finnhub"
    assert settings.macro_calendar_path == "/tmp/macro.json"
    assert settings.request_timeout_seconds == 12.5


def test_build_macro_calendar_provider_requires_configured_path() -> None:
    settings = Settings(postgres_dsn="postgresql://user:pass@localhost:5432/tradepilot")

    with pytest.raises(ProviderConfigurationError, match="MACRO_CALENDAR_PATH"):
        build_macro_calendar_provider(settings)


def test_build_macro_calendar_provider_returns_working_static_provider(tmp_path) -> None:
    calendar_path = tmp_path / "macro_calendar.json"
    calendar_path.write_text(
        json.dumps(
            [
                {
                    "event_name": "CPI",
                    "country": "US",
                    "category": "inflation",
                    "scheduled_at": "2026-04-19T12:30:00Z",
                    "importance": "high",
                }
            ]
        ),
        encoding="utf-8",
    )
    settings = Settings(
        postgres_dsn="postgresql://user:pass@localhost:5432/tradepilot",
        macro_calendar_path=str(calendar_path),
    )

    provider = build_macro_calendar_provider(settings)
    events = asyncio.run(
        provider.get_macro_events(
            market="US",
            days_ahead=7,
        )
    )

    assert len(events) == 1
    assert events[0].event_name == "CPI"
    assert events[0].scheduled_at == datetime(2026, 4, 19, 12, 30, tzinfo=UTC)

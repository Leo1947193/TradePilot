from __future__ import annotations

from app.config import Settings
from app.services.providers.finnhub_news_provider import FinnhubNewsProvider
from app.services.providers.interfaces import (
    CompanyEventsProvider,
    FinancialDataProvider,
    MacroCalendarProvider,
    MarketDataProvider,
    NewsDataProvider,
)
from app.services.providers.static_macro_calendar import StaticMacroCalendarProvider
from app.services.providers.yfinance_provider import YFinanceProvider


class ProviderConfigurationError(RuntimeError):
    pass


def build_macro_calendar_provider(settings: Settings) -> MacroCalendarProvider:
    if settings.macro_calendar_path is None or not settings.macro_calendar_path.strip():
        raise ProviderConfigurationError("MACRO_CALENDAR_PATH is required for static macro calendar provider")

    return StaticMacroCalendarProvider(settings.macro_calendar_path)


def build_market_data_provider(settings: Settings) -> MarketDataProvider:
    if settings.market_data_provider != "yfinance":
        raise ProviderConfigurationError(
            f"unsupported MARKET_DATA_PROVIDER: {settings.market_data_provider}"
        )

    return YFinanceProvider()


def build_financial_data_provider(settings: Settings) -> FinancialDataProvider:
    return _build_yfinance_backed_provider(settings)


def build_company_events_provider(settings: Settings) -> CompanyEventsProvider:
    return _build_yfinance_backed_provider(settings)


def build_news_data_provider(settings: Settings) -> NewsDataProvider:
    if settings.news_provider != "finnhub":
        raise ProviderConfigurationError(f"unsupported NEWS_PROVIDER: {settings.news_provider}")
    if settings.news_api_key is None or not settings.news_api_key.strip():
        raise ProviderConfigurationError("NEWS_API_KEY is required for Finnhub news provider")

    return FinnhubNewsProvider(
        settings.news_api_key,
        timeout_seconds=settings.request_timeout_seconds,
    )


def _build_yfinance_backed_provider(
    settings: Settings,
) -> YFinanceProvider:
    if settings.market_data_provider != "yfinance":
        raise ProviderConfigurationError(
            f"unsupported MARKET_DATA_PROVIDER: {settings.market_data_provider}"
        )

    return YFinanceProvider()

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.services.providers.dtos import (
    CompanyEvent,
    FinancialSnapshot,
    MacroCalendarEvent,
    MarketBar,
    NewsArticle,
)


@runtime_checkable
class MarketDataProvider(Protocol):
    async def get_daily_bars(self, symbol: str, *, lookback_days: int) -> list[MarketBar]:
        ...

    async def get_benchmark_bars(self, symbol: str, *, lookback_days: int) -> list[MarketBar]:
        ...


@runtime_checkable
class FinancialDataProvider(Protocol):
    async def get_financial_snapshot(self, symbol: str) -> FinancialSnapshot | None:
        ...


@runtime_checkable
class CompanyEventsProvider(Protocol):
    async def get_company_events(self, symbol: str, *, days_ahead: int) -> list[CompanyEvent]:
        ...


@runtime_checkable
class NewsDataProvider(Protocol):
    async def get_company_news(self, symbol: str, *, limit: int) -> list[NewsArticle]:
        ...


@runtime_checkable
class MacroCalendarProvider(Protocol):
    async def get_macro_events(self, *, market: str, days_ahead: int) -> list[MacroCalendarEvent]:
        ...

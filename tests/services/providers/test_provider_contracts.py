from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from app.services.providers.dtos import (
    CompanyEvent,
    FinancialSnapshot,
    MacroCalendarEvent,
    MarketBar,
    NewsArticle,
    ProviderSourceRef,
)
from app.services.providers.interfaces import (
    CompanyEventsProvider,
    FinancialDataProvider,
    MacroCalendarProvider,
    MarketDataProvider,
    NewsDataProvider,
)


def make_source() -> ProviderSourceRef:
    return ProviderSourceRef(
        name="provider-x",
        url="https://example.com/source",
        fetched_at=datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
    )


def test_market_bar_and_related_dtos_validate_expected_fields() -> None:
    source = make_source()

    market_bar = MarketBar(
        symbol="AAPL",
        timestamp=datetime(2026, 4, 17, 13, 0, tzinfo=UTC),
        open=190.0,
        high=193.0,
        low=189.5,
        close=192.0,
        volume=1000000,
        source=source,
    )
    financial_snapshot = FinancialSnapshot(
        symbol="AAPL",
        as_of_date=date(2026, 3, 31),
        gross_margin_pct=45.0,
        operating_margin_pct=30.0,
        source=source,
    )
    company_event = CompanyEvent(
        symbol="AAPL",
        event_type="earnings",
        title="Quarterly earnings call",
        scheduled_at=datetime(2026, 4, 30, 20, 30, tzinfo=UTC),
        category="company",
        url="https://example.com/event",
        source=source,
    )
    news_article = NewsArticle(
        symbol="AAPL",
        title="Apple unveils new product",
        published_at=datetime(2026, 4, 17, 14, 0, tzinfo=UTC),
        source_name="NewsWire",
        url="https://example.com/news",
        category="product",
        source=source,
    )
    macro_event = MacroCalendarEvent(
        event_name="CPI Release",
        country="US",
        category="inflation",
        scheduled_at=datetime(2026, 5, 1, 12, 30, tzinfo=UTC),
        importance="high",
        source=source,
    )

    assert market_bar.symbol == "AAPL"
    assert financial_snapshot.gross_margin_pct == 45.0
    assert company_event.event_type == "earnings"
    assert news_article.source_name == "NewsWire"
    assert macro_event.country == "US"


def test_provider_dtos_require_utc_aware_datetimes() -> None:
    source = make_source()

    with pytest.raises(ValidationError, match="timestamp must be timezone-aware UTC"):
        MarketBar(
            symbol="AAPL",
            timestamp=datetime(2026, 4, 17, 13, 0),
            open=190.0,
            high=193.0,
            low=189.5,
            close=192.0,
            volume=1000000,
            source=source,
        )


def test_financial_snapshot_margin_bounds_are_enforced() -> None:
    with pytest.raises(ValidationError) as exc_info:
        FinancialSnapshot(
            symbol="AAPL",
            as_of_date=date(2026, 3, 31),
            gross_margin_pct=120.0,
            source=make_source(),
        )

    errors = exc_info.value.errors(include_url=False)
    assert errors[0]["loc"] == ("gross_margin_pct",)
    assert errors[0]["type"] == "less_than_equal"


def test_runtime_checkable_provider_protocols_accept_matching_async_implementations() -> None:
    class FakeProvider:
        async def get_daily_bars(self, symbol: str, *, lookback_days: int) -> list[MarketBar]:
            return []

        async def get_benchmark_bars(self, symbol: str, *, lookback_days: int) -> list[MarketBar]:
            return []

        async def get_financial_snapshot(self, symbol: str) -> FinancialSnapshot | None:
            return None

        async def get_company_events(self, symbol: str, *, days_ahead: int) -> list[CompanyEvent]:
            return []

        async def get_company_news(self, symbol: str, *, limit: int) -> list[NewsArticle]:
            return []

        async def get_macro_events(
            self,
            *,
            market: str,
            days_ahead: int,
        ) -> list[MacroCalendarEvent]:
            return []

    provider = FakeProvider()

    assert isinstance(provider, MarketDataProvider)
    assert isinstance(provider, FinancialDataProvider)
    assert isinstance(provider, CompanyEventsProvider)
    assert isinstance(provider, NewsDataProvider)
    assert isinstance(provider, MacroCalendarProvider)

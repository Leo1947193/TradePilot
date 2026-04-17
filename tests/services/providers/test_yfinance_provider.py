from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pandas as pd

from app.services.providers.yfinance_provider import YFinanceProvider


def test_yfinance_provider_maps_daily_bars() -> None:
    provider = YFinanceProvider()
    history = pd.DataFrame(
        {
            "Open": [190.0, 192.0],
            "High": [193.0, 194.0],
            "Low": [189.0, 191.0],
            "Close": [192.5, 193.5],
            "Volume": [1000, 2000],
        },
        index=pd.to_datetime(["2026-04-16", "2026-04-17"], utc=True),
    )
    provider._download_history = lambda symbol, lookback_days: history  # type: ignore[method-assign]

    bars = asyncio.run(provider.get_daily_bars("aapl", lookback_days=30))

    assert [bar.symbol for bar in bars] == ["AAPL", "AAPL"]
    assert bars[0].timestamp == datetime(2026, 4, 16, 0, 0, tzinfo=UTC)
    assert bars[1].close == 193.5
    assert bars[0].source.name == "yfinance"


def test_yfinance_provider_maps_financial_snapshot_from_ticker_info() -> None:
    provider = YFinanceProvider()
    provider._get_ticker = lambda symbol: SimpleNamespace(  # type: ignore[method-assign]
        info={
            "currency": "USD",
            "totalRevenue": 100000000.0,
            "netIncomeToCommon": 25000000.0,
            "trailingEps": 6.5,
            "grossMargins": 0.46,
            "operatingMargins": 0.31,
            "trailingPE": 28.2,
            "marketCap": 3000000000.0,
        },
        calendar={"Earnings Date": datetime(2026, 4, 30, 20, 30, tzinfo=UTC)},
    )

    snapshot = asyncio.run(provider.get_financial_snapshot("aapl"))

    assert snapshot is not None
    assert snapshot.symbol == "AAPL"
    assert snapshot.as_of_date == date(2026, 4, 30)
    assert snapshot.gross_margin_pct == 46.0
    assert snapshot.operating_margin_pct == 31.0
    assert snapshot.market_cap == 3000000000.0


def test_yfinance_provider_returns_company_events_within_window() -> None:
    provider = YFinanceProvider()
    now = datetime.now(UTC)
    provider._get_ticker = lambda symbol: SimpleNamespace(  # type: ignore[method-assign]
        calendar={"Earnings Date": now + timedelta(days=5)},
    )

    events = asyncio.run(provider.get_company_events("aapl", days_ahead=7))

    assert len(events) == 1
    assert events[0].symbol == "AAPL"
    assert events[0].event_type == "earnings"
    assert events[0].scheduled_at.date() == (now + timedelta(days=5)).date()


def test_yfinance_provider_ignores_missing_or_out_of_window_company_events() -> None:
    provider = YFinanceProvider()
    provider._get_ticker = lambda symbol: SimpleNamespace(  # type: ignore[method-assign]
        calendar={"Earnings Date": datetime.now(UTC) + timedelta(days=30)},
    )

    far_events = asyncio.run(provider.get_company_events("aapl", days_ahead=7))
    provider._get_ticker = lambda symbol: SimpleNamespace(calendar={})  # type: ignore[method-assign]
    missing_events = asyncio.run(provider.get_company_events("aapl", days_ahead=7))

    assert far_events == []
    assert missing_events == []

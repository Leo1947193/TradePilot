from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.analysis.technical.multi_timeframe import analyze_multi_timeframe
from app.services.providers.dtos import MarketBar, ProviderSourceRef


def test_analyze_multi_timeframe_classifies_bullish_structure_and_stable_levels() -> None:
    daily_bars = _make_trending_bars("AAPL", start=100.0, step=0.8, count=252)
    weekly_bars = _make_trending_bars("AAPL", start=95.0, step=1.5, count=52, days=7)

    result = analyze_multi_timeframe(daily_bars, weekly_bars)

    assert result.trend_daily == "bullish"
    assert result.trend_weekly == "bullish"
    assert result.ma_alignment == "fully_bullish"
    assert result.low_confidence is False
    assert result.warnings == []
    assert result.key_support == sorted(result.key_support, reverse=True)
    assert result.key_resistance == sorted(result.key_resistance)
    assert all(level <= daily_bars[-1].close for level in result.key_support)
    assert all(level >= daily_bars[-1].close for level in result.key_resistance)


def test_analyze_multi_timeframe_downgrades_missing_weekly_history() -> None:
    daily_bars = _make_trending_bars("MSFT", start=200.0, step=0.5, count=252)
    weekly_bars = _make_trending_bars("MSFT", start=180.0, step=1.0, count=20, days=7)

    result = analyze_multi_timeframe(daily_bars, weekly_bars)

    assert result.trend_daily == "bullish"
    assert result.trend_weekly == "neutral"
    assert result.low_confidence is True
    assert "weekly_bars has fewer than 40 bars" in result.warnings[0]


def test_analyze_multi_timeframe_marks_bearish_alignment() -> None:
    daily_bars = _make_trending_bars("NVDA", start=300.0, step=-0.8, count=252)
    weekly_bars = _make_trending_bars("NVDA", start=320.0, step=-1.5, count=52, days=7)

    result = analyze_multi_timeframe(daily_bars, weekly_bars)

    assert result.trend_daily == "bearish"
    assert result.trend_weekly == "bearish"
    assert result.ma_alignment == "fully_bearish"


def _make_trending_bars(
    symbol: str,
    *,
    start: float,
    step: float,
    count: int,
    days: int = 1,
) -> list[MarketBar]:
    source = ProviderSourceRef(name="fixture", fetched_at=datetime(2026, 4, 22, tzinfo=UTC))
    bars: list[MarketBar] = []
    timestamp = datetime(2025, 1, 1, tzinfo=UTC)
    price = start

    for _ in range(count):
        open_price = price
        close_price = max(price + step, 1.0)
        high_price = max(open_price, close_price) + 1.0
        low_price = min(open_price, close_price) - 1.0
        bars.append(
            MarketBar(
                symbol=symbol,
                timestamp=timestamp,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=1_000_000,
                source=source,
            )
        )
        timestamp += timedelta(days=days)
        price = close_price

    return bars

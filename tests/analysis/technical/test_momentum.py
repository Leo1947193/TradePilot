from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.analysis.technical.momentum import (
    _calculate_adx,
    _calculate_macd_signal,
    _classify_rsi_signal,
    analyze_momentum,
)
from app.services.providers.dtos import MarketBar, ProviderSourceRef


def test_classify_rsi_signal_uses_adx_regime_thresholds() -> None:
    assert _classify_rsi_signal(75.0, 30.0) == "healthy"
    assert _classify_rsi_signal(75.0, 18.0) == "overbought"
    assert _classify_rsi_signal(35.0, 30.0) == "oversold"
    assert _classify_rsi_signal(35.0, None) == "healthy"


def test_calculate_macd_signal_detects_bullish_cross_and_expansion() -> None:
    closes = [100.0] * 30 + [99.0, 98.0, 97.0, 96.0, 97.0, 99.0, 102.0, 106.0, 111.0, 117.0]

    signal, histogram_state = _calculate_macd_signal(closes)

    assert signal == "bullish_cross"
    assert histogram_state == "expanding"


def test_calculate_adx_maps_to_expected_strength_buckets() -> None:
    strong_bars = _make_trending_bars("AAPL", start=100.0, step=1.2, count=80)
    weak_bars = _make_oscillating_bars("AAPL", start=100.0, count=80)

    strong_adx = _calculate_adx(strong_bars)
    weak_adx = _calculate_adx(weak_bars)

    assert strong_adx is not None and strong_adx >= 25
    assert weak_adx is not None and weak_adx < 20


def test_analyze_momentum_aligns_benchmark_dates_and_degrades_without_benchmark() -> None:
    daily_bars = _make_trending_bars("AAPL", start=100.0, step=0.6, count=90)
    benchmark_bars = _make_trending_bars("SPY", start=100.0, step=0.3, count=90)
    benchmark_bars = benchmark_bars[5:]

    result = analyze_momentum(daily_bars, benchmark_bars, benchmark_symbol="SPY")

    assert result.relative_strength is not None
    assert result.benchmark_used == "SPY"
    assert "相对 SPY" in result.momentum_summary

    degraded = analyze_momentum(daily_bars, [], benchmark_symbol=None)

    assert degraded.relative_strength is None
    assert degraded.benchmark_used is None
    assert degraded.low_confidence is True
    assert any("benchmark_bars is missing" in warning for warning in degraded.warnings)


def _make_trending_bars(symbol: str, *, start: float, step: float, count: int) -> list[MarketBar]:
    source = ProviderSourceRef(name="fixture", fetched_at=datetime(2026, 4, 22, tzinfo=UTC))
    bars: list[MarketBar] = []
    timestamp = datetime(2025, 1, 1, tzinfo=UTC)
    price = start

    for _ in range(count):
        open_price = price
        close_price = max(price + step, 1.0)
        high_price = max(open_price, close_price) + 1.2
        low_price = min(open_price, close_price) - 0.8
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
        timestamp += timedelta(days=1)
        price = close_price

    return bars


def _make_oscillating_bars(symbol: str, *, start: float, count: int) -> list[MarketBar]:
    source = ProviderSourceRef(name="fixture", fetched_at=datetime(2026, 4, 22, tzinfo=UTC))
    bars: list[MarketBar] = []
    timestamp = datetime(2025, 1, 1, tzinfo=UTC)
    price = start

    for index in range(count):
        delta = 0.5 if index % 2 == 0 else -0.5
        open_price = price
        close_price = price + delta
        high_price = max(open_price, close_price) + 0.7
        low_price = min(open_price, close_price) - 0.7
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
        timestamp += timedelta(days=1)
        price = close_price

    return bars

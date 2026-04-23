from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import fmean
from typing import Protocol


class BarLike(Protocol):
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


Trend = str
MaAlignment = str


@dataclass(frozen=True)
class MultiTimeframeResult:
    trend_daily: Trend
    trend_weekly: Trend
    ma_alignment: MaAlignment
    key_support: list[float]
    key_resistance: list[float]
    data_completeness_pct: float
    low_confidence: bool
    warnings: list[str]


def analyze_multi_timeframe(
    daily_bars: list[BarLike],
    weekly_bars: list[BarLike],
    *,
    analysis_time: datetime | None = None,
) -> MultiTimeframeResult:
    del analysis_time

    warnings: list[str] = []
    _validate_bars(daily_bars, field_name="daily_bars")
    if weekly_bars:
        _validate_bars(weekly_bars, field_name="weekly_bars")
        if daily_bars[-1].symbol != weekly_bars[-1].symbol:
            raise ValueError("daily_bars and weekly_bars must use the same symbol")

    if len(daily_bars) < 200:
        warnings.append("daily_bars has fewer than 200 bars; trend confidence is degraded")
    if len(weekly_bars) < 40:
        warnings.append("weekly_bars has fewer than 40 bars; weekly trend downgraded to neutral")

    daily_trend = _classify_daily_trend(daily_bars) if daily_bars else "neutral"
    weekly_trend = _classify_weekly_trend(weekly_bars) if len(weekly_bars) >= 40 else "neutral"
    ma_alignment = _classify_ma_alignment(daily_bars) if daily_bars else "mixed"
    support, resistance = _extract_key_levels(daily_bars)

    daily_score = min(len(daily_bars), 252) / 252 * 70.0 if daily_bars else 0.0
    weekly_score = min(len(weekly_bars), 52) / 52 * 30.0 if weekly_bars else 0.0
    data_completeness_pct = round(daily_score + weekly_score, 1)

    return MultiTimeframeResult(
        trend_daily=daily_trend,
        trend_weekly=weekly_trend,
        ma_alignment=ma_alignment,
        key_support=support,
        key_resistance=resistance,
        data_completeness_pct=data_completeness_pct,
        low_confidence=bool(warnings),
        warnings=warnings,
    )


def _validate_bars(bars: list[BarLike], *, field_name: str) -> None:
    if not bars:
        raise ValueError(f"{field_name} must not be empty")

    symbol = bars[0].symbol
    last_timestamp = bars[0].timestamp
    _validate_price_bar(bars[0], field_name=field_name)

    for bar in bars[1:]:
        _validate_price_bar(bar, field_name=field_name)
        if bar.symbol != symbol:
            raise ValueError(f"{field_name} must use a single symbol")
        if bar.timestamp <= last_timestamp:
            raise ValueError(f"{field_name} must be sorted in ascending timestamp order")
        last_timestamp = bar.timestamp


def _validate_price_bar(bar: BarLike, *, field_name: str) -> None:
    if min(bar.open, bar.high, bar.low, bar.close) <= 0:
        raise ValueError(f"{field_name} contains non-positive prices")
    if bar.high < max(bar.open, bar.close) or bar.low > min(bar.open, bar.close):
        raise ValueError(f"{field_name} contains inconsistent OHLC values")


def _classify_daily_trend(bars: list[BarLike]) -> Trend:
    if len(bars) < 200:
        return "neutral"

    closes = [bar.close for bar in bars]
    sma20 = _simple_moving_average(closes, 20)
    sma50 = _simple_moving_average(closes, 50)
    sma200 = _simple_moving_average(closes, 200)
    ema10_series = _ema_series(closes, 10)
    ema21_series = _ema_series(closes, 21)
    ema10 = ema10_series[-1]
    ema21 = ema21_series[-1]
    close = closes[-1]

    bullish = (
        close >= sma20 >= sma50 >= sma200
        and ema10 >= ema21
        and _slope_is_positive(ema10_series, lookback=5)
        and _slope_is_positive(ema21_series, lookback=5)
        and _slope_is_positive(closes, lookback=20)
    )
    bearish = (
        close <= sma20 <= sma50 <= sma200
        and ema10 <= ema21
        and _slope_is_negative(ema10_series, lookback=5)
        and _slope_is_negative(ema21_series, lookback=5)
        and _slope_is_negative(closes, lookback=20)
    )

    if bullish:
        return "bullish"
    if bearish:
        return "bearish"
    return "neutral"


def _classify_weekly_trend(bars: list[BarLike]) -> Trend:
    if len(bars) < 40:
        return "neutral"

    closes = [bar.close for bar in bars]
    sma10 = _simple_moving_average(closes, 10)
    sma40 = _simple_moving_average(closes, 40)
    close = closes[-1]

    if close >= sma10 >= sma40 and _slope_is_positive(closes, lookback=10):
        return "bullish"
    if close <= sma10 <= sma40 and _slope_is_negative(closes, lookback=10):
        return "bearish"
    return "neutral"


def _classify_ma_alignment(bars: list[BarLike]) -> MaAlignment:
    if len(bars) < 200:
        return "mixed"

    closes = [bar.close for bar in bars]
    close = closes[-1]
    ema10 = _ema_series(closes, 10)[-1]
    ema21 = _ema_series(closes, 21)[-1]
    sma20 = _simple_moving_average(closes, 20)
    sma50 = _simple_moving_average(closes, 50)
    sma200 = _simple_moving_average(closes, 200)

    if close >= ema10 >= ema21 and sma20 >= sma50 >= sma200 and ema21 >= sma50:
        return "fully_bullish"
    if close <= ema10 <= ema21 and sma20 <= sma50 <= sma200 and ema21 <= sma50:
        return "fully_bearish"
    if close >= sma50 and ema10 >= ema21 and sma20 >= sma50 and sma50 >= sma200:
        return "partially_bullish"
    return "mixed"


def _extract_key_levels(bars: list[BarLike]) -> tuple[list[float], list[float]]:
    if not bars:
        return [], []

    recent = bars[-min(len(bars), 252) :]
    close = recent[-1].close

    swing_lows: list[float] = []
    swing_highs: list[float] = []
    for index in range(1, len(recent) - 1):
        prev_bar = recent[index - 1]
        bar = recent[index]
        next_bar = recent[index + 1]
        if bar.low <= prev_bar.low and bar.low <= next_bar.low:
            swing_lows.append(bar.low)
        if bar.high >= prev_bar.high and bar.high >= next_bar.high:
            swing_highs.append(bar.high)

    if not swing_lows:
        swing_lows = [min(bar.low for bar in recent)]
    if not swing_highs:
        swing_highs = [max(bar.high for bar in recent)]

    clustered_lows = _cluster_levels(sorted(swing_lows))
    clustered_highs = _cluster_levels(sorted(swing_highs))

    support = [level for level in clustered_lows if level <= close]
    resistance = [level for level in clustered_highs if level >= close]

    support.sort(key=lambda level: (abs(close - level), -level))
    resistance.sort(key=lambda level: (abs(close - level), level))
    return support[:3], resistance[:3]


def _cluster_levels(levels: list[float], *, tolerance_pct: float = 0.015) -> list[float]:
    if not levels:
        return []

    clusters: list[list[float]] = [[levels[0]]]
    for level in levels[1:]:
        cluster = clusters[-1]
        cluster_mean = fmean(cluster)
        if abs(level - cluster_mean) / cluster_mean <= tolerance_pct:
            cluster.append(level)
        else:
            clusters.append([level])

    return [round(fmean(cluster), 2) for cluster in clusters]


def _simple_moving_average(values: list[float], period: int) -> float:
    if len(values) < period:
        raise ValueError(f"need at least {period} values for SMA")
    return fmean(values[-period:])


def _ema_series(values: list[float], period: int) -> list[float]:
    if len(values) < period:
        raise ValueError(f"need at least {period} values for EMA")

    multiplier = 2 / (period + 1)
    seed = fmean(values[:period])
    ema_values = [seed]
    for value in values[period:]:
        ema_values.append((value - ema_values[-1]) * multiplier + ema_values[-1])
    return ema_values


def _slope_is_positive(values: list[float], *, lookback: int) -> bool:
    if len(values) <= lookback:
        return False
    return values[-1] > values[-1 - lookback]


def _slope_is_negative(values: list[float], *, lookback: int) -> bool:
    if len(values) <= lookback:
        return False
    return values[-1] < values[-1 - lookback]
